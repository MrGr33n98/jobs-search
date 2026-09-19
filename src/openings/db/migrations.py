"""Small, deterministic SQLite migration runner.

The pre-migration application created its schema with ``CREATE TABLE IF NOT
EXISTS`` and had no version marker. Version 1 therefore represents that
legacy schema. Existing databases are adopted in place; new databases receive
the same schema through migration 1. Migration 2 is the additive CAREER-01A
domain foundation.
"""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from openings.db.schema import SCHEMA

MIGRATIONS_TABLE = "schema_migrations"
LEGACY_TABLES = frozenset(
    {"jobs", "postings", "job_labels", "notes", "attachments", "events", "embeddings", "runs"}
)

CAREER_01A_SCHEMA = """
CREATE TABLE IF NOT EXISTS candidate_profiles (
    id TEXT PRIMARY KEY,
    display_name TEXT,
    headline TEXT,
    current_location TEXT,
    country TEXT,
    languages_json TEXT NOT NULL DEFAULT '[]',
    skills_json TEXT NOT NULL DEFAULT '[]',
    experience_json TEXT NOT NULL DEFAULT '[]',
    education_json TEXT NOT NULL DEFAULT '[]',
    certifications_json TEXT NOT NULL DEFAULT '[]',
    work_authorizations_json TEXT NOT NULL DEFAULT '[]',
    preferred_work_modes_json TEXT NOT NULL DEFAULT '[]',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS search_profiles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    enabled BOOLEAN NOT NULL DEFAULT 0,
    target_roles_json TEXT NOT NULL DEFAULT '[]',
    role_aliases_json TEXT NOT NULL DEFAULT '[]',
    include_keywords_json TEXT NOT NULL DEFAULT '[]',
    exclude_keywords_json TEXT NOT NULL DEFAULT '[]',
    skills_priority_json TEXT NOT NULL DEFAULT '[]',
    locations_json TEXT NOT NULL DEFAULT '[]',
    countries_json TEXT NOT NULL DEFAULT '[]',
    location_types_json TEXT NOT NULL DEFAULT '[]',
    remote_scope TEXT NOT NULL DEFAULT 'unknown',
    remote_eligibility TEXT NOT NULL DEFAULT 'unknown',
    salary_min REAL,
    salary_currency TEXT,
    seniority_levels_json TEXT NOT NULL DEFAULT '[]',
    employment_types_json TEXT NOT NULL DEFAULT '[]',
    sources_json TEXT NOT NULL DEFAULT '[]',
    freshness_days INTEGER,
    scoring_weights_json TEXT NOT NULL DEFAULT '{}',
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    last_run_at TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_search_profiles_enabled ON search_profiles(enabled);

CREATE TABLE IF NOT EXISTS job_matches (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    search_profile_id TEXT NOT NULL REFERENCES search_profiles(id) ON DELETE CASCADE,
    relevance_score INTEGER NOT NULL,
    eligibility TEXT NOT NULL DEFAULT 'unknown',
    match_reasons_json TEXT NOT NULL DEFAULT '[]',
    missing_requirements_json TEXT NOT NULL DEFAULT '[]',
    score_breakdown_json TEXT NOT NULL DEFAULT '{}',
    score_version TEXT NOT NULL DEFAULT 'legacy-v1',
    scored_at TIMESTAMP NOT NULL,
    UNIQUE (job_id, search_profile_id)
);
CREATE INDEX IF NOT EXISTS idx_job_matches_job_id ON job_matches(job_id);
CREATE INDEX IF NOT EXISTS idx_job_matches_search_profile_id ON job_matches(search_profile_id);

CREATE TABLE IF NOT EXISTS search_runs (
    id TEXT PRIMARY KEY,
    search_profile_id TEXT NOT NULL REFERENCES search_profiles(id) ON DELETE CASCADE,
    status TEXT NOT NULL,
    started_at TIMESTAMP NOT NULL,
    finished_at TIMESTAMP,
    sources_json TEXT NOT NULL DEFAULT '[]',
    queries_json TEXT NOT NULL DEFAULT '[]',
    jobs_found INTEGER NOT NULL DEFAULT 0,
    jobs_new INTEGER NOT NULL DEFAULT 0,
    jobs_matched INTEGER NOT NULL DEFAULT 0,
    errors_json TEXT NOT NULL DEFAULT '[]',
    duration_seconds REAL
);
CREATE INDEX IF NOT EXISTS idx_search_runs_profile_date
    ON search_runs(search_profile_id, started_at DESC);
"""

CAREER_01F_SCHEMA = """
ALTER TABLE job_matches ADD COLUMN review_status TEXT NOT NULL DEFAULT 'new';
ALTER TABLE job_matches ADD COLUMN reviewed_at TIMESTAMP;
CREATE INDEX IF NOT EXISTS idx_job_matches_review_status
    ON job_matches(search_profile_id, review_status);

CREATE TABLE IF NOT EXISTS applications (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL UNIQUE REFERENCES jobs(job_id) ON DELETE CASCADE,
    stage TEXT NOT NULL DEFAULT 'interested',
    source_search_profile_id TEXT REFERENCES search_profiles(id) ON DELETE SET NULL,
    source_job_match_id TEXT,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    applied_confirmed_at TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_applications_stage ON applications(stage);
CREATE INDEX IF NOT EXISTS idx_applications_source_profile
    ON applications(source_search_profile_id);
"""


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    sql: str
    rollback: Callable[[sqlite3.Connection], None] | None = None

    @property
    def checksum(self) -> str:
        return hashlib.sha256(self.sql.encode("utf-8")).hexdigest()


def _drop_career_01a(conn: sqlite3.Connection) -> None:
    """Rollback only objects owned by migration 2."""
    for statement in (
        "DROP INDEX IF EXISTS idx_search_runs_profile_date",
        "DROP INDEX IF EXISTS idx_job_matches_search_profile_id",
        "DROP INDEX IF EXISTS idx_job_matches_job_id",
        "DROP INDEX IF EXISTS idx_search_profiles_enabled",
        "DROP TABLE IF EXISTS search_runs",
        "DROP TABLE IF EXISTS job_matches",
        "DROP TABLE IF EXISTS search_profiles",
        "DROP TABLE IF EXISTS candidate_profiles",
    ):
        conn.execute(statement)


def _drop_career_01f(conn: sqlite3.Connection) -> None:
    """Rollback indexes/table owned by 01F; SQLite cannot drop columns safely."""
    for statement in (
        "DROP INDEX IF EXISTS idx_applications_source_profile",
        "DROP INDEX IF EXISTS idx_applications_stage",
        "DROP TABLE IF EXISTS applications",
        "DROP INDEX IF EXISTS idx_job_matches_review_status",
    ):
        conn.execute(statement)


MIGRATIONS = (
    Migration(1, "legacy_schema_baseline", SCHEMA),
    Migration(2, "career_01a_domain_foundation", CAREER_01A_SCHEMA, _drop_career_01a),
    Migration(
        3, "career_01f_review_and_application_foundation", CAREER_01F_SCHEMA, _drop_career_01f
    ),
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tables(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {str(row[0]) for row in rows}


def _ensure_migrations_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            checksum TEXT NOT NULL,
            applied_at TIMESTAMP NOT NULL
        )
        """
    )


def _adopt_legacy_schema(conn: sqlite3.Connection) -> None:
    if conn.execute("SELECT 1 FROM schema_migrations WHERE version = 1").fetchone():
        return
    existing = _tables(conn) - {MIGRATIONS_TABLE}
    legacy = existing & LEGACY_TABLES
    if not legacy:
        return
    if legacy != LEGACY_TABLES:
        missing = ", ".join(sorted(LEGACY_TABLES - legacy))
        raise RuntimeError(f"Cannot adopt partial legacy schema; missing tables: {missing}")
    migration = MIGRATIONS[0]
    conn.execute(
        "INSERT INTO schema_migrations(version, name, checksum, applied_at) VALUES (?, ?, ?, ?)",
        (migration.version, migration.name, migration.checksum, _utc_now()),
    )


def _applied(conn: sqlite3.Connection) -> dict[int, tuple[str, str]]:
    rows = conn.execute(
        "SELECT version, name, checksum FROM schema_migrations ORDER BY version"
    ).fetchall()
    return {int(row[0]): (str(row[1]), str(row[2])) for row in rows}


def _execute_sql(conn: sqlite3.Connection, sql: str) -> None:
    """Execute the bundled DDL without executescript's implicit COMMIT."""
    for statement in (part.strip() for part in sql.split(";")):
        if statement:
            conn.execute(statement)


def migrate(conn: sqlite3.Connection) -> int:
    """Apply all pending migrations and return the resulting schema version."""
    conn.commit()
    conn.execute("BEGIN")
    try:
        _ensure_migrations_table(conn)
        _adopt_legacy_schema(conn)
        applied = _applied(conn)
        for migration in MIGRATIONS:
            if migration.version in applied:
                name, checksum = applied[migration.version]
                if name != migration.name or checksum != migration.checksum:
                    raise RuntimeError(f"Migration {migration.version} checksum/name mismatch")
                continue
            if migration.version != max(applied, default=0) + 1:
                raise RuntimeError(f"Migration sequence gap before version {migration.version}")
            _execute_sql(conn, migration.sql)
            conn.execute(
                "INSERT INTO schema_migrations(version, name, checksum, applied_at) VALUES (?, ?, ?, ?)",
                (migration.version, migration.name, migration.checksum, _utc_now()),
            )
            applied[migration.version] = (migration.name, migration.checksum)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return max(applied, default=0)


def rollback(conn: sqlite3.Connection, target_version: int) -> int:
    """Rollback migrations down to target_version without touching legacy data."""
    if target_version < 1:
        raise ValueError("Rollback below legacy schema version 1 is not supported")
    conn.commit()
    conn.execute("BEGIN")
    try:
        _ensure_migrations_table(conn)
        applied = _applied(conn)
        current = max(applied, default=0)
        if target_version > current:
            raise ValueError(f"Cannot rollback forward from {current} to {target_version}")
        for migration in reversed(MIGRATIONS):
            if migration.version <= target_version or migration.version not in applied:
                continue
            if migration.rollback is None:
                raise RuntimeError(f"Migration {migration.version} has no rollback")
            migration.rollback(conn)
            conn.execute("DELETE FROM schema_migrations WHERE version = ?", (migration.version,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return target_version


def current_version(conn: sqlite3.Connection) -> int:
    if MIGRATIONS_TABLE not in _tables(conn):
        return 0
    row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
    return int(row[0] or 0)
