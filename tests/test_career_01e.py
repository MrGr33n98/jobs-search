from __future__ import annotations

from openings.career import CandidateProfile, RemoteEligibility, RemoteScope, SearchProfile
from openings.profile_scoring import SCORING_VERSION, score


def make_job(**overrides):
    from openings.models import Job

    values = {
        "title": "Backend Engineer",
        "company": "Acme",
        "location": "Remote",
        "source": "manual",
        "job_url": "https://example.test/job/1",
        "description": "Python services.",
        "relevance_score": 35,
    }
    values.update(overrides)
    return Job.from_row(values)


def profile(**overrides):
    values = {
        "name": "Mechanical",
        "target_roles": ("Mechanical Engineer",),
        "include_keywords": ("SolidWorks",),
        "locations": ("São Paulo",),
        "remote_scope": RemoteScope.UNKNOWN,
    }
    values.update(overrides)
    return SearchProfile(**values)


def test_profile_score_is_deterministic_bounded_and_explainable():
    job = make_job(
        title="Senior Mechanical Engineer",
        location="São Paulo",
        description="SolidWorks and product design.",
        relevance_score=77,
    )
    strategy = profile()
    first = score(job, strategy, None)
    second = score(job, strategy, None)
    assert first == second
    assert 0 <= first.score <= 100
    assert sum(first.breakdown.to_dict().values()) == first.score
    assert first.scoring_version == SCORING_VERSION
    assert job.relevance_score == 77


def test_role_matching_avoids_generic_engineer_false_positive():
    strategy = profile()
    matching = score(make_job(title="Senior Mechanical Engineer"), strategy)
    unrelated = score(make_job(title="Software Engineer"), strategy)
    assert matching.score > unrelated.score
    assert any("Role matches" in reason for reason in matching.match_reasons)


def test_alias_and_exclusion_are_deterministic():
    strategy = profile(
        target_roles=(), role_aliases=("Engenheiro Mecânico",), exclude_keywords=("internship",)
    )
    result = score(
        make_job(title="Engenheiro Mecânico", description="CAD internship"), strategy
    )
    assert result.score < 100
    assert any("Excluded keyword" in reason for reason in result.match_reasons)


def test_unknown_candidate_data_is_not_a_missing_qualification():
    result = score(
        make_job(title="Mechanical Engineer", description="Kubernetes required"),
        profile(),
        CandidateProfile(),
    )
    assert result.missing_requirements == ()


def test_unknown_remote_eligibility_is_not_rejected():
    result = score(make_job(location="Remote", is_remote=True), profile())
    assert result.eligibility == RemoteEligibility.UNKNOWN


def test_same_job_can_have_independent_profile_scores(db):
    from openings.career import JobMatch

    job = make_job(title="Mechanical Engineer")
    db.upsert_jobs([job])
    mechanical = profile()
    devops = SearchProfile(name="DevOps", target_roles=("DevOps Engineer",))
    db.save_search_profile(mechanical)
    db.save_search_profile(devops)
    first = score(job, mechanical)
    second = score(job, devops)
    db.save_job_match(
        JobMatch(job_id=job.job_id, search_profile_id=mechanical.id, relevance_score=first.score,
                 eligibility=first.eligibility, match_reasons=first.match_reasons,
                 score_breakdown=first.breakdown.to_dict(), score_version=first.scoring_version)
    )
    db.save_job_match(
        JobMatch(job_id=job.job_id, search_profile_id=devops.id, relevance_score=second.score,
                 eligibility=second.eligibility, match_reasons=second.match_reasons,
                 score_breakdown=second.breakdown.to_dict(), score_version=second.scoring_version)
    )
    assert db.count_jobs() == 1
    assert db.count_job_matches() == 2
    assert first.score != second.score
