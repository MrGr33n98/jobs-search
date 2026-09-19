"""Persistence helpers for the additive CAREER-01A domain tables."""

from __future__ import annotations

import json
from datetime import datetime
from dataclasses import replace
from typing import Any

from openings.career import (
    Application,
    ApplicationStage,
    CandidateProfile,
    JobMatch,
    RemoteEligibility,
    RemoteScope,
    ReviewStatus,
    SearchProfile,
    SearchRun,
    SearchRunStatus,
)
from openings.db.base import JOB_COLUMNS, Store, placeholders
from openings.models import Job, parse_datetime


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


def _loads(value: str | None, default: Any) -> Any:
    return json.loads(value) if value else default


def _required_datetime(value: object) -> datetime:
    parsed = parse_datetime(value)
    if parsed is None:
        raise ValueError("stored career timestamp is missing or invalid")
    return parsed


class CareerMixin(Store):
    """Small repository surface; no API or collection behavior is introduced here."""

    def save_candidate_profile(self, profile: CandidateProfile) -> CandidateProfile:
        data = profile.to_dict()
        with self._connection() as conn:
            conn.execute(
                """INSERT INTO candidate_profiles
                (id, display_name, headline, current_location, country, languages_json,
                 skills_json, experience_json, education_json, certifications_json,
                 work_authorizations_json, preferred_work_modes_json, metadata_json,
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET display_name=excluded.display_name,
                headline=excluded.headline, current_location=excluded.current_location,
                country=excluded.country, languages_json=excluded.languages_json,
                skills_json=excluded.skills_json, experience_json=excluded.experience_json,
                education_json=excluded.education_json, certifications_json=excluded.certifications_json,
                work_authorizations_json=excluded.work_authorizations_json,
                preferred_work_modes_json=excluded.preferred_work_modes_json,
                metadata_json=excluded.metadata_json, updated_at=excluded.updated_at""",
                (
                    data["id"],
                    data["display_name"],
                    data["headline"],
                    data["current_location"],
                    data["country"],
                    _json(data["languages"]),
                    _json(data["skills"]),
                    _json(data["experience"]),
                    _json(data["education"]),
                    _json(data["certifications"]),
                    _json(data["work_authorizations"]),
                    _json(data["preferred_work_modes"]),
                    _json(data["metadata"]),
                    data["created_at"],
                    data["updated_at"],
                ),
            )
            conn.commit()
        return profile

    def get_candidate_profile(self) -> CandidateProfile | None:
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM candidate_profiles ORDER BY created_at LIMIT 1"
            ).fetchone()
        if row is None:
            return None
        return CandidateProfile(
            id=row["id"],
            display_name=row["display_name"],
            headline=row["headline"],
            current_location=row["current_location"],
            country=row["country"],
            languages=tuple(_loads(row["languages_json"], [])),
            skills=tuple(_loads(row["skills_json"], [])),
            experience=tuple(_loads(row["experience_json"], [])),
            education=tuple(_loads(row["education_json"], [])),
            certifications=tuple(_loads(row["certifications_json"], [])),
            work_authorizations=tuple(_loads(row["work_authorizations_json"], [])),
            preferred_work_modes=tuple(_loads(row["preferred_work_modes_json"], [])),
            metadata=_loads(row["metadata_json"], {}),
            created_at=_required_datetime(row["created_at"]),
            updated_at=_required_datetime(row["updated_at"]),
        )

    def save_search_profile(self, profile: SearchProfile) -> SearchProfile:
        data = profile.to_dict()
        with self._connection() as conn:
            conn.execute(
                """INSERT INTO search_profiles
                (id, name, description, enabled, target_roles_json, role_aliases_json,
                 include_keywords_json, exclude_keywords_json, skills_priority_json,
                 locations_json, countries_json, location_types_json, remote_scope,
                 remote_eligibility, salary_min, salary_currency, seniority_levels_json,
                 employment_types_json, sources_json, freshness_days, scoring_weights_json,
                 created_at, updated_at, last_run_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET name=excluded.name, description=excluded.description,
                enabled=excluded.enabled, target_roles_json=excluded.target_roles_json,
                role_aliases_json=excluded.role_aliases_json, include_keywords_json=excluded.include_keywords_json,
                exclude_keywords_json=excluded.exclude_keywords_json, skills_priority_json=excluded.skills_priority_json,
                locations_json=excluded.locations_json, countries_json=excluded.countries_json,
                location_types_json=excluded.location_types_json, remote_scope=excluded.remote_scope,
                remote_eligibility=excluded.remote_eligibility, salary_min=excluded.salary_min,
                salary_currency=excluded.salary_currency, seniority_levels_json=excluded.seniority_levels_json,
                employment_types_json=excluded.employment_types_json, sources_json=excluded.sources_json,
                freshness_days=excluded.freshness_days, scoring_weights_json=excluded.scoring_weights_json,
                updated_at=excluded.updated_at, last_run_at=excluded.last_run_at""",
                (
                    data["id"],
                    data["name"],
                    data["description"],
                    data["enabled"],
                    _json(data["target_roles"]),
                    _json(data["role_aliases"]),
                    _json(data["include_keywords"]),
                    _json(data["exclude_keywords"]),
                    _json(data["skills_priority"]),
                    _json(data["locations"]),
                    _json(data["countries"]),
                    _json(data["location_types"]),
                    data["remote_scope"],
                    data["remote_eligibility"],
                    data["salary_min"],
                    data["salary_currency"],
                    _json(data["seniority_levels"]),
                    _json(data["employment_types"]),
                    _json(data["sources"]),
                    data["freshness_days"],
                    _json(data["scoring_weights"]),
                    data["created_at"],
                    data["updated_at"],
                    data["last_run_at"],
                ),
            )
            conn.commit()
        return profile

    def get_search_profile(self, profile_id: str) -> SearchProfile | None:
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM search_profiles WHERE id = ?", (profile_id,)
            ).fetchone()
        if row is None:
            return None
        return SearchProfile(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            enabled=bool(row["enabled"]),
            target_roles=tuple(_loads(row["target_roles_json"], [])),
            role_aliases=tuple(_loads(row["role_aliases_json"], [])),
            include_keywords=tuple(_loads(row["include_keywords_json"], [])),
            exclude_keywords=tuple(_loads(row["exclude_keywords_json"], [])),
            skills_priority=tuple(_loads(row["skills_priority_json"], [])),
            locations=tuple(_loads(row["locations_json"], [])),
            countries=tuple(_loads(row["countries_json"], [])),
            location_types=tuple(_loads(row["location_types_json"], [])),
            remote_scope=RemoteScope(row["remote_scope"]),
            remote_eligibility=RemoteEligibility(row["remote_eligibility"]),
            salary_min=row["salary_min"],
            salary_currency=row["salary_currency"],
            seniority_levels=tuple(_loads(row["seniority_levels_json"], [])),
            employment_types=tuple(_loads(row["employment_types_json"], [])),
            sources=tuple(_loads(row["sources_json"], [])),
            freshness_days=row["freshness_days"],
            scoring_weights=_loads(row["scoring_weights_json"], {}),
            created_at=_required_datetime(row["created_at"]),
            updated_at=_required_datetime(row["updated_at"]),
            last_run_at=parse_datetime(row["last_run_at"]),
        )

    def list_search_profiles(
        self, limit: int = 50, offset: int = 0
    ) -> tuple[list[SearchProfile], int]:
        limit = max(1, min(int(limit), 1000))
        offset = max(0, int(offset))
        with self._connection() as conn:
            total = int(conn.execute("SELECT COUNT(*) FROM search_profiles").fetchone()[0])
            rows = conn.execute(
                "SELECT id FROM search_profiles ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        profiles = [
            profile for row in rows if (profile := self.get_search_profile(row["id"])) is not None
        ]
        return profiles, total

    def disable_search_profile(self, profile_id: str) -> SearchProfile | None:
        profile = self.get_search_profile(profile_id)
        if profile is None:
            return None
        disabled = replace(profile, enabled=False)
        self.save_search_profile(disabled)
        return disabled

    def save_job_match(self, match: JobMatch) -> JobMatch:
        data = {
            "id": match.id,
            "job_id": match.job_id,
            "search_profile_id": match.search_profile_id,
            "relevance_score": match.relevance_score,
            "eligibility": match.eligibility.value,
            "match_reasons": list(match.match_reasons),
            "missing_requirements": list(match.missing_requirements),
            "score_breakdown": match.score_breakdown,
            "score_version": match.score_version,
            "scored_at": match.scored_at.isoformat(),
            "review_status": match.review_status.value,
            "reviewed_at": match.reviewed_at.isoformat() if match.reviewed_at else None,
        }
        with self._connection() as conn:
            conn.execute(
                """INSERT INTO job_matches
                (id, job_id, search_profile_id, relevance_score, eligibility, match_reasons_json,
                 missing_requirements_json, score_breakdown_json, score_version, scored_at,
                 review_status, reviewed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id, search_profile_id) DO UPDATE SET id=excluded.id,
                relevance_score=excluded.relevance_score, eligibility=excluded.eligibility,
                match_reasons_json=excluded.match_reasons_json, missing_requirements_json=excluded.missing_requirements_json,
                score_breakdown_json=excluded.score_breakdown_json, score_version=excluded.score_version,
                scored_at=excluded.scored_at, review_status=excluded.review_status,
                reviewed_at=excluded.reviewed_at""",
                (
                    data["id"],
                    data["job_id"],
                    data["search_profile_id"],
                    data["relevance_score"],
                    data["eligibility"],
                    _json(data["match_reasons"]),
                    _json(data["missing_requirements"]),
                    _json(data["score_breakdown"]),
                    data["score_version"],
                    data["scored_at"],
                    data["review_status"],
                    data["reviewed_at"],
                ),
            )
            conn.commit()
        return match

    def get_jobs_by_ids(self, job_ids: list[str]) -> dict[str, Job]:
        """Load a batch of canonical jobs for profile scoring without N+1 queries."""
        ids = list(dict.fromkeys(job_ids))
        if not ids:
            return {}
        columns = ", ".join(JOB_COLUMNS)
        with self._connection() as conn:
            rows = conn.execute(
                f"SELECT {columns} FROM jobs WHERE job_id IN ({placeholders(len(ids))})", ids
            ).fetchall()
        return {job.job_id: job for row in rows if (job := self.row_to_job(row)) is not None}

    def count_job_matches(self, profile_id: str | None = None) -> int:
        with self._connection() as conn:
            if profile_id is None:
                return int(conn.execute("SELECT COUNT(*) FROM job_matches").fetchone()[0])
            return int(
                conn.execute(
                    "SELECT COUNT(*) FROM job_matches WHERE search_profile_id = ?", (profile_id,)
                ).fetchone()[0]
            )

    def list_job_matches(
        self, profile_id: str, limit: int = 50, offset: int = 0,
        min_score: int | None = None, eligibility: str | None = None,
        review_status: str | None = None,
    ) -> tuple[list[dict[str, Job | JobMatch]], int]:
        limit = max(1, min(int(limit), 1000))
        offset = max(0, int(offset))
        job_columns = ", ".join(f"jobs.{column}" for column in JOB_COLUMNS)
        with self._connection() as conn:
            conditions = ["jm.search_profile_id = ?"]
            query_params: list[object] = [profile_id]
            if min_score is not None:
                conditions.append("jm.relevance_score >= ?")
                query_params.append(min_score)
            if eligibility is not None:
                conditions.append("jm.eligibility = ?")
                query_params.append(eligibility)
            if review_status is not None:
                conditions.append("jm.review_status = ?")
                query_params.append(review_status)
            where = " AND ".join(conditions)
            total = int(conn.execute(f"SELECT COUNT(*) FROM job_matches jm WHERE {where}", query_params).fetchone()[0])
            rows = conn.execute(
                f"SELECT {job_columns}, "
                "jm.id AS match_id, jm.search_profile_id AS match_profile_id, "
                "jm.relevance_score AS match_score, jm.eligibility AS match_eligibility, "
                "jm.match_reasons_json, jm.missing_requirements_json, jm.score_breakdown_json, "
                "jm.score_version, jm.scored_at, jm.review_status, jm.reviewed_at "
                "FROM job_matches jm JOIN jobs ON jobs.job_id = jm.job_id "
                f"WHERE {where} "
                "ORDER BY jm.relevance_score DESC, jm.scored_at DESC, jm.id ASC LIMIT ? OFFSET ?",
                (*query_params, limit, offset),
            ).fetchall()
        result: list[dict[str, Job | JobMatch]] = []
        for row in rows:
            job = self.row_to_job(row)
            match = JobMatch(
                id=row["match_id"],
                job_id=job.job_id,
                search_profile_id=row["match_profile_id"],
                relevance_score=int(row["match_score"]),
                eligibility=RemoteEligibility(row["match_eligibility"]),
                match_reasons=tuple(_loads(row["match_reasons_json"], [])),
                missing_requirements=tuple(_loads(row["missing_requirements_json"], [])),
                score_breakdown=_loads(row["score_breakdown_json"], {}),
                score_version=row["score_version"],
                scored_at=_required_datetime(row["scored_at"]),
                review_status=ReviewStatus(row["review_status"]),
                reviewed_at=parse_datetime(row["reviewed_at"]),
            )
            result.append({"job": job, "match": match})
        return result, total

    def update_job_match_review(
        self, job_id: str, profile_id: str, status: ReviewStatus
    ) -> JobMatch | None:
        now = datetime.now().astimezone()
        with self._connection() as conn:
            cursor = conn.execute(
                "UPDATE job_matches SET review_status = ?, reviewed_at = ? "
                "WHERE job_id = ? AND search_profile_id = ?",
                (status.value, now.isoformat(), job_id, profile_id),
            )
            conn.commit()
        if cursor.rowcount == 0:
            return None
        rows, _total = self.list_job_matches(profile_id, limit=1000, offset=0)
        for item in rows:
            match = item["match"]
            if isinstance(match, JobMatch) and match.job_id == job_id:
                return match
        return None

    def save_application(self, application: Application) -> Application:
        data = application.to_dict()
        with self._connection() as conn:
            conn.execute(
                """INSERT INTO applications
                (id, job_id, stage, source_search_profile_id, source_job_match_id,
                 created_at, updated_at, applied_confirmed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET stage=excluded.stage,
                source_search_profile_id=COALESCE(applications.source_search_profile_id,
                    excluded.source_search_profile_id),
                source_job_match_id=COALESCE(applications.source_job_match_id,
                    excluded.source_job_match_id), updated_at=excluded.updated_at,
                applied_confirmed_at=excluded.applied_confirmed_at""",
                (data["id"], data["job_id"], data["stage"], data["source_search_profile_id"],
                 data["source_job_match_id"], data["created_at"], data["updated_at"],
                 data["applied_confirmed_at"]),
            )
            conn.commit()
        return self.get_application_by_job(application.job_id) or application

    def get_application(self, application_id: str) -> Application | None:
        with self._connection() as conn:
            row = conn.execute("SELECT * FROM applications WHERE id = ?", (application_id,)).fetchone()
        return self._application_from_row(row) if row else None

    def get_application_by_job(self, job_id: str) -> Application | None:
        with self._connection() as conn:
            row = conn.execute("SELECT * FROM applications WHERE job_id = ?", (job_id,)).fetchone()
        return self._application_from_row(row) if row else None

    def list_applications(self, limit: int = 50, offset: int = 0) -> tuple[list[Application], int]:
        limit = max(1, min(int(limit), 1000))
        offset = max(0, int(offset))
        with self._connection() as conn:
            total = int(conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0])
            rows = conn.execute(
                "SELECT * FROM applications ORDER BY updated_at DESC, id ASC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [self._application_from_row(row) for row in rows], total

    def update_application_stage(
        self, application_id: str, stage: ApplicationStage
    ) -> Application | None:
        current = self.get_application(application_id)
        if current is None:
            return None
        now = datetime.now().astimezone()
        confirmed = current.applied_confirmed_at
        if stage is ApplicationStage.APPLIED and confirmed is None:
            confirmed = now
        updated = Application(
            id=current.id,
            job_id=current.job_id,
            stage=stage,
            source_search_profile_id=current.source_search_profile_id,
            source_job_match_id=current.source_job_match_id,
            created_at=current.created_at,
            updated_at=now,
            applied_confirmed_at=confirmed,
        )
        with self._connection() as conn:
            conn.execute(
                "UPDATE applications SET stage = ?, updated_at = ?, applied_confirmed_at = ? "
                "WHERE id = ?",
                (updated.stage.value, updated.updated_at.isoformat(),
                 updated.applied_confirmed_at.isoformat() if updated.applied_confirmed_at else None,
                 updated.id),
            )
            conn.commit()
        return updated

    @staticmethod
    def _application_from_row(row) -> Application:
        return Application(
            id=row["id"],
            job_id=row["job_id"],
            stage=ApplicationStage(row["stage"]),
            source_search_profile_id=row["source_search_profile_id"],
            source_job_match_id=row["source_job_match_id"],
            created_at=_required_datetime(row["created_at"]),
            updated_at=_required_datetime(row["updated_at"]),
            applied_confirmed_at=parse_datetime(row["applied_confirmed_at"]),
        )

    def save_search_run(self, run: SearchRun) -> SearchRun:
        data = {
            "id": run.id,
            "search_profile_id": run.search_profile_id,
            "status": run.status.value,
            "started_at": run.started_at.isoformat(),
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            "sources": list(run.sources),
            "queries": list(run.queries),
            "jobs_found": run.jobs_found,
            "jobs_new": run.jobs_new,
            "jobs_matched": run.jobs_matched,
            "errors": list(run.errors),
            "duration_seconds": run.duration_seconds,
        }
        with self._connection() as conn:
            conn.execute(
                """INSERT INTO search_runs
                (id, search_profile_id, status, started_at, finished_at, sources_json, queries_json,
                 jobs_found, jobs_new, jobs_matched, errors_json, duration_seconds)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET status=excluded.status, finished_at=excluded.finished_at,
                sources_json=excluded.sources_json, queries_json=excluded.queries_json,
                jobs_found=excluded.jobs_found, jobs_new=excluded.jobs_new, jobs_matched=excluded.jobs_matched,
                errors_json=excluded.errors_json, duration_seconds=excluded.duration_seconds""",
                (
                    data["id"],
                    data["search_profile_id"],
                    data["status"],
                    data["started_at"],
                    data["finished_at"],
                    _json(data["sources"]),
                    _json(data["queries"]),
                    data["jobs_found"],
                    data["jobs_new"],
                    data["jobs_matched"],
                    _json(data["errors"]),
                    data["duration_seconds"],
                ),
            )
            conn.commit()
        return run

    def count_search_runs(self, profile_id: str | None = None) -> int:
        with self._connection() as conn:
            if profile_id is None:
                return int(conn.execute("SELECT COUNT(*) FROM search_runs").fetchone()[0])
            return int(
                conn.execute(
                    "SELECT COUNT(*) FROM search_runs WHERE search_profile_id = ?", (profile_id,)
                ).fetchone()[0]
            )

    def list_search_runs(
        self, profile_id: str, limit: int = 50, offset: int = 0
    ) -> tuple[list[SearchRun], int]:
        limit = max(1, min(int(limit), 1000))
        offset = max(0, int(offset))
        with self._connection() as conn:
            total = int(
                conn.execute(
                    "SELECT COUNT(*) FROM search_runs WHERE search_profile_id = ?", (profile_id,)
                ).fetchone()[0]
            )
            rows = conn.execute(
                "SELECT * FROM search_runs WHERE search_profile_id = ? "
                "ORDER BY started_at DESC, id DESC LIMIT ? OFFSET ?",
                (profile_id, limit, offset),
            ).fetchall()
        return [
            SearchRun(
                id=row["id"],
                search_profile_id=row["search_profile_id"],
                status=SearchRunStatus(row["status"]),
                started_at=_required_datetime(row["started_at"]),
                finished_at=parse_datetime(row["finished_at"]),
                sources=tuple(_loads(row["sources_json"], [])),
                queries=tuple(_loads(row["queries_json"], [])),
                jobs_found=int(row["jobs_found"]),
                jobs_new=int(row["jobs_new"]),
                jobs_matched=int(row["jobs_matched"]),
                errors=tuple(_loads(row["errors_json"], [])),
                duration_seconds=row["duration_seconds"],
            )
            for row in rows
        ], total
