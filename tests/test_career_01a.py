import sqlite3
import pytest

from openings.career import (
    CandidateProfile,
    JobMatch,
    LocationType,
    RemoteEligibility,
    RemoteScope,
    SearchProfile,
    SearchRun,
    SearchRunStatus,
)
from openings.db import JobDatabase, current_version, migrate, rollback
from openings.db.schema import SCHEMA
from tests.conftest import make_job


def table_names(connection: sqlite3.Connection) -> set[str]:
    return {
        row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }


def test_migration_fresh_db_is_versioned_and_additive(tmp_path):
    path = tmp_path / "fresh.db"
    database = JobDatabase(path)
    with database._connection() as conn:
        assert current_version(conn) == 3
        versions = conn.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()
        assert [row[0] for row in versions] == [1, 2, 3]
        names = table_names(conn)
        assert {
            "jobs",
            "postings",
            "runs",
            "candidate_profiles",
            "search_profiles",
            "job_matches",
            "search_runs",
            "applications",
        } <= names
        columns = {row[1] for row in conn.execute("PRAGMA table_info(jobs)")}
        assert "relevance_score" in columns
        match_columns = {row[1] for row in conn.execute("PRAGMA table_info(job_matches)")}
        assert {"review_status", "reviewed_at"} <= match_columns
    database.close()


def test_migration_existing_legacy_db_adopts_without_recreating_rows(tmp_path):
    path = tmp_path / "legacy.db"
    connection = sqlite3.connect(path)
    connection.executescript(SCHEMA)
    connection.execute(
        "INSERT INTO jobs (job_id, identity, title, company, location, source, first_seen, last_seen, relevance_score, status, status_changed_at) "
        "VALUES ('legacy', 'identity', 'Role', 'Company', 'Remote', 'manual', '2026-09-01', '2026-09-01', 77, 'new', '2026-09-01T00:00:00+00:00')"
    )
    connection.commit()
    connection.close()

    database = JobDatabase(path)
    assert database.get_job("legacy").relevance_score == 77
    with database._connection() as conn:
        assert current_version(conn) == 3
        assert conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 3
    database.close()


def test_migration_is_idempotent(tmp_path):
    database = JobDatabase(tmp_path / "repeat.db")
    with database._connection() as conn:
        before = conn.total_changes
        assert migrate(conn) == 3
        assert migrate(conn) == 3
        assert conn.total_changes == before
        assert conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 3
    database.close()


def test_rollback_v2_preserves_legacy_and_can_reapply(tmp_path):
    database = JobDatabase(tmp_path / "rollback.db")
    database.upsert_jobs([make_job(relevance_score=91)])
    with database._connection() as conn:
        assert rollback(conn, 1) == 1
        assert current_version(conn) == 1
        assert conn.execute("SELECT relevance_score FROM jobs").fetchone()[0] == 91
        assert "job_matches" not in table_names(conn)
        assert migrate(conn) == 3
        assert "job_matches" in table_names(conn)
    database.close()


def test_candidate_profile_unknown_is_not_fabricated():
    profile = CandidateProfile()
    assert profile.display_name is None
    assert profile.languages == ()
    assert profile.certifications == ()
    with pytest.raises(ValueError, match="experience"):
        CandidateProfile(experience=("not evidence",))


def test_search_profile_validates_strategy_fields_and_unknowns():
    profile = SearchProfile(
        name="Mechanical Engineering",
        target_roles=("Mechanical Engineer",),
        location_types=(LocationType.UNKNOWN,),
        remote_scope=RemoteScope.UNKNOWN,
        remote_eligibility=RemoteEligibility.UNKNOWN,
        sources=("jobspy", "greenhouse"),
    )
    assert profile.remote_eligibility is RemoteEligibility.UNKNOWN
    with pytest.raises(ValueError, match="name is required"):
        SearchProfile()
    with pytest.raises(ValueError, match="unsupported search profile source"):
        SearchProfile(name="x", sources=("not-an-adapter",))
    with pytest.raises(ValueError, match="salary_min"):
        SearchProfile(name="x", salary_min=-1)


def test_job_match_unique_pair_and_search_run_profile_linkage(db, job):
    profile = SearchProfile(name="A")
    db.save_search_profile(profile)
    db.upsert_jobs([job])
    db.save_job_match(JobMatch(job_id=job.job_id, search_profile_id=profile.id, relevance_score=10))
    db.save_job_match(JobMatch(job_id=job.job_id, search_profile_id=profile.id, relevance_score=20))
    assert db.count_job_matches(profile.id) == 1
    run = SearchRun(search_profile_id=profile.id, status=SearchRunStatus.COMPLETED)
    db.save_search_run(run)
    assert db.count_search_runs(profile.id) == 1
    with pytest.raises(sqlite3.IntegrityError):
        db.save_search_run(SearchRun(search_profile_id="missing"))
