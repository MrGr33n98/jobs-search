"""Application services for CAREER-01B.

This layer owns the REST-facing use cases. It intentionally does not invoke
collectors or the scheduler; profile execution belongs to a later wave.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import threading
from typing import Any

from openings.career import (
    Application,
    ApplicationStage,
    CandidateProfile,
    LocationType,
    RemoteEligibility,
    RemoteScope,
    ReviewStatus,
    SearchProfile,
    SearchRun,
    SearchRunStatus,
)
from openings.collection_profiles import (
    build_collection_plan,
    effective_collection_config,
    excluded_keywords_filter,
)
from openings.models import Job, utcnow
from openings.scoring import partition_by_thresholds, score_jobs
from openings.profile_scoring import score as score_profile_job
from openings.sources.collect import collect_all
from openings.sources.ats import FETCHERS
from openings.sources.base import JOB_TYPES


class SearchProfileNotFound(LookupError):
    pass


class CollectionUnavailable(RuntimeError):
    pass


class SearchProfileDisabled(RuntimeError):
    pass


class SearchProfileAlreadyRunning(RuntimeError):
    pass


_PROFILE_LOCKS: dict[str, threading.Lock] = {}
_PROFILE_LOCKS_GUARD = threading.Lock()


def _now() -> datetime:
    return datetime.now(timezone.utc)


class CareerApplicationService:
    def __init__(self, runtime):
        self.runtime = runtime

    @property
    def db(self):
        return self.runtime.db

    def get_candidate_profile(self) -> CandidateProfile | None:
        return self.db.get_candidate_profile()

    def update_candidate_profile(self, changes: dict[str, Any]) -> CandidateProfile:
        current = self.db.get_candidate_profile()
        if current is None:
            profile = CandidateProfile(**changes)
        else:
            profile = replace(current, **changes, updated_at=_now())
        return self.db.save_candidate_profile(profile)

    def list_search_profiles(self, limit: int, offset: int) -> tuple[list[SearchProfile], int]:
        return self.db.list_search_profiles(limit, offset)

    def get_search_profile(self, profile_id: str) -> SearchProfile:
        profile = self.db.get_search_profile(profile_id)
        if profile is None:
            raise SearchProfileNotFound(profile_id)
        return profile

    def create_search_profile(self, data: dict[str, Any]) -> SearchProfile:
        return self.db.save_search_profile(SearchProfile(**data))

    def update_search_profile(self, profile_id: str, changes: dict[str, Any]) -> SearchProfile:
        current = self.get_search_profile(profile_id)
        return self.db.save_search_profile(replace(current, **changes, updated_at=_now()))

    def disable_search_profile(self, profile_id: str) -> SearchProfile:
        profile = self.db.disable_search_profile(profile_id)
        if profile is None:
            raise SearchProfileNotFound(profile_id)
        return profile

    def get_matches(
        self, profile_id: str, limit: int, offset: int, min_score: int | None = None,
        eligibility: str | None = None, review_status: str | None = None,
    ) -> dict[str, Any]:
        self.get_search_profile(profile_id)
        items, total = self.db.list_job_matches(
            profile_id, limit, offset, min_score, eligibility, review_status
        )
        return {
            "items": [
                {
                    "job": item["job"].to_summary(),
                    "match": {
                        "id": item["match"].id,
                        "job_id": item["match"].job_id,
                        "search_profile_id": item["match"].search_profile_id,
                        "score": item["match"].relevance_score,
                        "relevance_score": item["match"].relevance_score,
                        "eligibility": item["match"].eligibility.value,
                        "match_reasons": list(item["match"].match_reasons),
                        "missing_requirements": list(item["match"].missing_requirements),
                        "score_breakdown": item["match"].score_breakdown,
                        "score_version": item["match"].score_version,
                        "scoring_version": item["match"].scoring_version,
                        "review_status": item["match"].review_status.value,
                        "reviewed_at": item["match"].reviewed_at.isoformat()
                        if item["match"].reviewed_at else None,
                        "scored_at": item["match"].scored_at.isoformat(),
                    },
                }
                for item in items
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    def review_match(self, profile_id: str, job_id: str, status: ReviewStatus):
        self.get_search_profile(profile_id)
        match = self.db.update_job_match_review(job_id, profile_id, status)
        if match is None:
            raise LookupError("JobMatch not found")
        return match

    def add_to_pipeline(self, profile_id: str, job_id: str) -> Application:
        profile = self.get_search_profile(profile_id)
        job = self.db.get_job(job_id)
        if job is None:
            raise LookupError("Job not found")
        match = next(
            (item["match"] for item in self.db.list_job_matches(profile.id, 1000, 0)[0]
             if item["match"].job_id == job_id),
            None,
        )
        existing = self.db.get_application_by_job(job_id)
        if existing is not None:
            return existing
        application = Application(
            job_id=job_id,
            source_search_profile_id=profile.id,
            source_job_match_id=match.id if match else None,
        )
        return self.db.save_application(application)

    def list_applications(self, limit: int, offset: int) -> dict[str, Any]:
        items, total = self.db.list_applications(limit, offset)
        result = []
        for application in items:
            job = self.db.get_job(application.job_id)
            if job is not None:
                origin = (
                    self.db.get_search_profile(application.source_search_profile_id).name
                    if application.source_search_profile_id
                    and self.db.get_search_profile(application.source_search_profile_id)
                    else None
                )
                result.append({
                    "application": application.to_dict(),
                    "job": job.to_summary(),
                    "source_search_profile_name": origin,
                })
        return {"items": result, "total": total, "limit": limit, "offset": offset}

    def update_application_stage(self, application_id: str, stage: ApplicationStage) -> Application:
        application = self.db.update_application_stage(application_id, stage)
        if application is None:
            raise LookupError("Application not found")
        return application

    def get_runs(self, profile_id: str, limit: int, offset: int) -> dict[str, Any]:
        self.get_search_profile(profile_id)
        items, total = self.db.list_search_runs(profile_id, limit, offset)
        return {
            "items": [
                {
                    "id": item.id,
                    "search_profile_id": item.search_profile_id,
                    "status": item.status.value,
                    "started_at": item.started_at.isoformat(),
                    "finished_at": item.finished_at.isoformat() if item.finished_at else None,
                    "sources": list(item.sources),
                    "queries": list(item.queries),
                    "jobs_found": item.jobs_found,
                    "jobs_new": item.jobs_new,
                    "jobs_matched": item.jobs_matched,
                    "errors": list(item.errors),
                    "duration_seconds": item.duration_seconds,
                }
                for item in items
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    def run_search_profile(self, profile_id: str) -> SearchRun:
        profile = self.get_search_profile(profile_id)
        if not profile.enabled:
            raise SearchProfileDisabled(profile_id)
        with _PROFILE_LOCKS_GUARD:
            lock = _PROFILE_LOCKS.setdefault(profile_id, threading.Lock())
        if not lock.acquire(blocking=False):
            raise SearchProfileAlreadyRunning(profile_id)
        try:
            latest, _total = self.db.list_search_runs(profile_id, limit=1, offset=0)
            if latest and latest[0].status == SearchRunStatus.RUNNING:
                raise SearchProfileAlreadyRunning(profile_id)
            global_config = self.runtime.config(reload=True)
            capabilities = self.capabilities()
            plan = build_collection_plan(profile, capabilities, global_config)
            effective = effective_collection_config(profile, plan, global_config)
            run = SearchRun(
                search_profile_id=profile.id,
                status=SearchRunStatus.RUNNING,
                sources=plan.sources,
                queries=plan.queries,
                errors=plan.warnings,
            )
            self.db.save_search_run(run)
            try:
                collected = collect_all(effective.config, known=self.db.known_external_ids)
                frame = excluded_keywords_filter(collected.frame, profile.exclude_keywords)
                run = replace(
                    run,
                    sources=tuple(stat.name for stat in collected.stats),
                    jobs_found=len(frame),
                    errors=tuple((*run.errors, *collected.errors)),
                )
                result = self._persist_profile_jobs(effective.config, frame)
                run = replace(run, jobs_new=result.new_count)
                matched, scoring_errors = self.score_jobs_for_profile(
                    profile.id, result.new_ids + result.updated_ids
                )
                run = replace(run, jobs_matched=matched, errors=(*run.errors, *scoring_errors))
                if collected.every_task_failed:
                    status = SearchRunStatus.FAILED
                elif run.errors:
                    status = SearchRunStatus.PARTIAL
                else:
                    status = SearchRunStatus.COMPLETED
            except Exception as exc:  # noqa: BLE001 - persist the real failed run
                run = replace(
                    run, status=SearchRunStatus.FAILED, errors=(*run.errors, f"run: {exc}")
                )
                raise
            finally:
                finished = utcnow()
                run = replace(
                    run,
                    status=locals().get("status", SearchRunStatus.FAILED),
                    finished_at=finished,
                    duration_seconds=max(0.0, (finished - run.started_at).total_seconds()),
                )
                self.db.save_search_run(run)
                self.db.save_search_profile(
                    replace(profile, last_run_at=finished, updated_at=finished)
                )
            return run
        finally:
            lock.release()

    def _persist_profile_jobs(self, config, frame):
        if frame.empty:
            from openings.db.jobs import UpsertResult

            return UpsertResult()
        scored = score_jobs(frame, config)
        partitions = partition_by_thresholds(scored, config)
        jobs = [Job.from_row(record) for record in partitions.to_save.to_dict("records")]
        return self.db.upsert_jobs(jobs)

    def score_job_for_profile(self, job_id: str, profile_id: str):
        profile = self.get_search_profile(profile_id)
        job = self.db.get_job(job_id)
        if job is None:
            raise LookupError(job_id)
        result = score_profile_job(job, profile, self.db.get_candidate_profile())
        from openings.career import JobMatch

        return self.db.save_job_match(
            JobMatch(
                job_id=job.job_id,
                search_profile_id=profile.id,
                relevance_score=result.score,
                eligibility=result.eligibility,
                match_reasons=result.match_reasons,
                missing_requirements=result.missing_requirements,
                score_breakdown=result.breakdown.to_dict(),
                score_version=result.scoring_version,
            )
        )

    def score_jobs_for_profile(
        self, profile_id: str, job_ids: list[str]
    ) -> tuple[int, tuple[str, ...]]:
        """Batch score discovered canonical jobs for one profile."""
        profile = self.get_search_profile(profile_id)
        candidate = self.db.get_candidate_profile()
        jobs = self.db.get_jobs_by_ids(job_ids)
        matched = 0
        errors: list[str] = []
        for job_id in dict.fromkeys(job_ids):
            try:
                job = jobs.get(job_id)
                if job is None:
                    raise LookupError(job_id)
                result = score_profile_job(job, profile, candidate)
                from openings.career import JobMatch

                self.db.save_job_match(
                    JobMatch(
                        job_id=job.job_id,
                        search_profile_id=profile.id,
                        relevance_score=result.score,
                        eligibility=result.eligibility,
                        match_reasons=result.match_reasons,
                        missing_requirements=result.missing_requirements,
                        score_breakdown=result.breakdown.to_dict(),
                        score_version=result.scoring_version,
                    )
                )
                matched += 1
            except Exception as exc:  # noqa: BLE001 - isolate one bad persisted job
                errors.append(f"scoring:{job_id}: {exc}")
        return matched, tuple(errors)

    def capabilities(self) -> dict[str, Any]:
        config = self.runtime.config()
        configured_ats = {company.ats for company in config.sources.companies}
        sources: list[dict[str, Any]] = []
        source_names = ("jobspy", "rss", "jobcloud", "adzuna", "manual", *FETCHERS.keys())
        for source in dict.fromkeys(source_names):
            if source == "jobspy":
                enabled = config.sources.jobspy.enabled
                reason = None if enabled else "disabled in legacy configuration"
            elif source == "rss":
                enabled = bool(config.sources.feeds)
                reason = None if enabled else "no legacy feeds configured"
            elif source == "jobcloud":
                enabled = config.sources.jobcloud.enabled
                reason = None if enabled else "disabled in legacy configuration"
            elif source == "adzuna":
                enabled = config.sources.adzuna.enabled
                reason = None if enabled else "disabled in legacy configuration"
            elif source == "manual":
                enabled = False
                reason = "manual source is not a collection adapter"
            else:
                enabled = source in configured_ats
                reason = None if enabled else "no legacy company adapter configured"
            sources.append({"id": source, "available": True, "enabled": enabled, "reason": reason})
        return {
            "sources": sources,
            "location_types": [value.value for value in LocationType],
            "remote_scopes": [value.value for value in RemoteScope],
            "remote_eligibilities": [value.value for value in RemoteEligibility],
            "employment_types": list(JOB_TYPES) + ["other"],
        }
