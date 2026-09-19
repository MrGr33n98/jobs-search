from __future__ import annotations

from openings.career import JobMatch, ReviewStatus, SearchProfile


def test_review_is_profile_specific_and_dismiss_does_not_delete_job(client, runtime, job):
    first = SearchProfile(name="Mechanical", target_roles=("Mechanical Engineer",))
    second = SearchProfile(name="DevOps", target_roles=("DevOps Engineer",))
    runtime.db.save_search_profile(first)
    runtime.db.save_search_profile(second)
    runtime.db.upsert_jobs([job])
    runtime.db.save_job_match(
        JobMatch(job_id=job.job_id, search_profile_id=first.id, relevance_score=90)
    )
    runtime.db.save_job_match(
        JobMatch(job_id=job.job_id, search_profile_id=second.id, relevance_score=20)
    )

    response = client.patch(
        f"/api/search-profiles/{first.id}/matches/{job.job_id}",
        json={"review_status": ReviewStatus.DISMISSED.value},
    )
    assert response.status_code == 200
    assert response.json()["review_status"] == "dismissed"
    assert runtime.db.count_jobs() == 1
    first_match = client.get(f"/api/search-profiles/{first.id}/matches").json()["items"][0]
    second_match = client.get(f"/api/search-profiles/{second.id}/matches").json()["items"][0]
    assert first_match["match"]["review_status"] == "dismissed"
    assert second_match["match"]["review_status"] == "new"


def test_add_to_pipeline_is_explicit_and_duplicate_safe(client, runtime, job):
    profile = SearchProfile(name="Pipeline profile")
    runtime.db.save_search_profile(profile)
    runtime.db.upsert_jobs([job])
    match = JobMatch(job_id=job.job_id, search_profile_id=profile.id, relevance_score=80)
    runtime.db.save_job_match(match)

    first = client.post(f"/api/search-profiles/{profile.id}/matches/{job.job_id}/pipeline")
    second = client.post(f"/api/search-profiles/{profile.id}/matches/{job.job_id}/pipeline")
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert client.get("/api/applications").json()["total"] == 1

    applied = client.patch(f"/api/applications/{first.json()['id']}", json={"stage": "applied"})
    assert applied.status_code == 200
    assert applied.json()["stage"] == "applied"
    assert applied.json()["applied_confirmed_at"] is not None


def test_profile_match_filters_are_server_side(client, runtime, job):
    profile = SearchProfile(name="Filter profile")
    runtime.db.save_search_profile(profile)
    runtime.db.upsert_jobs([job])
    runtime.db.save_job_match(
        JobMatch(job_id=job.job_id, search_profile_id=profile.id, relevance_score=88)
    )
    assert (
        client.get(f"/api/search-profiles/{profile.id}/matches", params={"min_score": 90}).json()[
            "total"
        ]
        == 0
    )
    assert (
        client.get(f"/api/search-profiles/{profile.id}/matches", params={"min_score": 80}).json()[
            "total"
        ]
        == 1
    )
