"""CAREER-01A domain models.

These models contain strategy and factual candidate data only. Collection
infrastructure remains in the legacy global configuration.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


class RemoteScope(StrEnum):
    BRAZIL = "brazil"
    LATAM = "latam"
    GLOBAL = "global"
    COUNTRY_RESTRICTED = "country_restricted"
    UNKNOWN = "unknown"


class RemoteEligibility(StrEnum):
    ELIGIBLE = "eligible"
    LIKELY_ELIGIBLE = "likely_eligible"
    RESTRICTED = "restricted"
    UNKNOWN = "unknown"


class LocationType(StrEnum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"
    UNKNOWN = "unknown"


class SearchRunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class ReviewStatus(StrEnum):
    NEW = "new"
    INTERESTED = "interested"
    SAVED = "saved"
    DISMISSED = "dismissed"


class ApplicationStage(StrEnum):
    INTERESTED = "interested"
    PREPARING = "preparing"
    READY_TO_APPLY = "ready_to_apply"
    APPLIED = "applied"
    INTERVIEWING = "interviewing"
    OFFER = "offer"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


SUPPORTED_SEARCH_SOURCES = frozenset(
    {
        "jobspy",
        "rss",
        "jobcloud",
        "adzuna",
        "manual",
        "greenhouse",
        "lever",
        "ashby",
        "smartrecruiters",
        "workday",
        "joincom",
        "workable",
        "rippling",
        "bamboohr",
        "oracle",
        "personio",
        "recruitee",
        "breezy",
    }
)


def _new_id() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _strings(values: object, name: str) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple)) or not all(isinstance(value, str) for value in values):
        raise ValueError(f"{name} must be a list of strings")
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = value.strip()
        if clean and clean.casefold() not in seen:
            result.append(clean)
            seen.add(clean.casefold())
    return tuple(result)


def _json_object(value: object, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    try:
        json.dumps(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be JSON serializable") from exc
    return dict(value)


@dataclass(frozen=True)
class CandidateProfile:
    """Facts explicitly supplied about the candidate; omitted stays unknown."""

    id: str = field(default_factory=_new_id)
    display_name: str | None = None
    headline: str | None = None
    current_location: str | None = None
    country: str | None = None
    languages: tuple[str, ...] = ()
    skills: tuple[str, ...] = ()
    experience: tuple[dict[str, Any], ...] = ()
    education: tuple[dict[str, Any], ...] = ()
    certifications: tuple[str, ...] = ()
    work_authorizations: tuple[str, ...] = ()
    preferred_work_modes: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("candidate profile id is required")
        for name in (
            "languages",
            "skills",
            "certifications",
            "work_authorizations",
            "preferred_work_modes",
        ):
            _strings(getattr(self, name), f"candidate_profile.{name}")
        for name in ("experience", "education"):
            entries = getattr(self, name)
            if not isinstance(entries, (list, tuple)) or not all(
                isinstance(item, dict) for item in entries
            ):
                raise ValueError(f"candidate_profile.{name} must be a list of objects")
        _json_object(self.metadata, "candidate_profile.metadata")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "display_name": self.display_name,
            "headline": self.headline,
            "current_location": self.current_location,
            "country": self.country,
            "languages": list(self.languages),
            "skills": list(self.skills),
            "experience": list(self.experience),
            "education": list(self.education),
            "certifications": list(self.certifications),
            "work_authorizations": list(self.work_authorizations),
            "preferred_work_modes": list(self.preferred_work_modes),
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass(frozen=True)
class SearchProfile:
    """A current opportunity strategy, independent from candidate facts."""

    id: str = field(default_factory=_new_id)
    name: str = ""
    description: str | None = None
    enabled: bool = False
    target_roles: tuple[str, ...] = ()
    role_aliases: tuple[str, ...] = ()
    include_keywords: tuple[str, ...] = ()
    exclude_keywords: tuple[str, ...] = ()
    skills_priority: tuple[str, ...] = ()
    locations: tuple[str, ...] = ()
    countries: tuple[str, ...] = ()
    location_types: tuple[LocationType, ...] = ()
    remote_scope: RemoteScope = RemoteScope.UNKNOWN
    remote_eligibility: RemoteEligibility = RemoteEligibility.UNKNOWN
    salary_min: float | None = None
    salary_currency: str | None = None
    seniority_levels: tuple[str, ...] = ()
    employment_types: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()
    freshness_days: int | None = None
    scoring_weights: dict[str, int] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)
    last_run_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("search profile id is required")
        if not self.name.strip():
            raise ValueError("search profile name is required")
        for name in (
            "target_roles",
            "role_aliases",
            "include_keywords",
            "exclude_keywords",
            "skills_priority",
            "locations",
            "countries",
            "seniority_levels",
        ):
            _strings(getattr(self, name), f"search_profile.{name}")
        object.__setattr__(
            self, "location_types", tuple(LocationType(value) for value in self.location_types)
        )
        object.__setattr__(self, "remote_scope", RemoteScope(self.remote_scope))
        object.__setattr__(self, "remote_eligibility", RemoteEligibility(self.remote_eligibility))
        sources = tuple(source.strip().lower() for source in self.sources)
        invalid = next(
            (source for source in sources if source not in SUPPORTED_SEARCH_SOURCES), None
        )
        if invalid is not None:
            raise ValueError(f"unsupported search profile source: {invalid}")
        object.__setattr__(self, "sources", tuple(dict.fromkeys(sources)))
        employment = tuple(value.strip().lower() for value in self.employment_types)
        allowed = {
            "fulltime",
            "parttime",
            "contract",
            "internship",
            "temporary",
            "volunteer",
            "other",
        }
        invalid = next((value for value in employment if value not in allowed), None)
        if invalid is not None:
            raise ValueError(f"unsupported employment type: {invalid}")
        object.__setattr__(self, "employment_types", tuple(dict.fromkeys(employment)))
        if self.salary_min is not None and self.salary_min < 0:
            raise ValueError("search profile salary_min must be non-negative")
        if self.freshness_days is not None and self.freshness_days < 1:
            raise ValueError("search profile freshness_days must be at least 1")
        if not all(
            isinstance(value, int) and not isinstance(value, bool)
            for value in self.scoring_weights.values()
        ):
            raise ValueError("search profile scoring_weights must contain integers")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "enabled": self.enabled,
            "target_roles": list(self.target_roles),
            "role_aliases": list(self.role_aliases),
            "include_keywords": list(self.include_keywords),
            "exclude_keywords": list(self.exclude_keywords),
            "skills_priority": list(self.skills_priority),
            "locations": list(self.locations),
            "countries": list(self.countries),
            "location_types": [value.value for value in self.location_types],
            "remote_scope": self.remote_scope.value,
            "remote_eligibility": self.remote_eligibility.value,
            "salary_min": self.salary_min,
            "salary_currency": self.salary_currency,
            "seniority_levels": list(self.seniority_levels),
            "employment_types": list(self.employment_types),
            "sources": list(self.sources),
            "freshness_days": self.freshness_days,
            "scoring_weights": dict(self.scoring_weights),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
        }


@dataclass(frozen=True)
class JobMatch:
    id: str = field(default_factory=_new_id)
    job_id: str = ""
    search_profile_id: str = ""
    relevance_score: int = 0
    eligibility: RemoteEligibility = RemoteEligibility.UNKNOWN
    match_reasons: tuple[str, ...] = ()
    missing_requirements: tuple[str, ...] = ()
    score_breakdown: dict[str, Any] = field(default_factory=dict)
    score_version: str = "career-01a-v1"
    scored_at: datetime = field(default_factory=_now)
    review_status: ReviewStatus = ReviewStatus.NEW
    reviewed_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.job_id.strip() or not self.search_profile_id.strip():
            raise ValueError("job_match job_id and search_profile_id are required")
        _strings(self.match_reasons, "job_match.match_reasons")
        _strings(self.missing_requirements, "job_match.missing_requirements")
        _json_object(self.score_breakdown, "job_match.score_breakdown")
        object.__setattr__(self, "review_status", ReviewStatus(self.review_status))

    @property
    def scoring_version(self) -> str:
        """Canonical CAREER-01E name; ``score_version`` remains DB compatible."""
        return self.score_version


@dataclass(frozen=True)
class Application:
    id: str = field(default_factory=_new_id)
    job_id: str = ""
    stage: ApplicationStage = ApplicationStage.INTERESTED
    source_search_profile_id: str | None = None
    source_job_match_id: str | None = None
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)
    applied_confirmed_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.job_id.strip():
            raise ValueError("application job_id is required")
        object.__setattr__(self, "stage", ApplicationStage(self.stage))
        if self.stage is ApplicationStage.APPLIED and self.applied_confirmed_at is None:
            raise ValueError("applied stage requires explicit confirmation timestamp")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "job_id": self.job_id,
            "stage": self.stage.value,
            "source_search_profile_id": self.source_search_profile_id,
            "source_job_match_id": self.source_job_match_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "applied_confirmed_at": self.applied_confirmed_at.isoformat()
            if self.applied_confirmed_at
            else None,
        }


@dataclass(frozen=True)
class SearchRun:
    id: str = field(default_factory=_new_id)
    search_profile_id: str = ""
    status: SearchRunStatus = SearchRunStatus.PENDING
    started_at: datetime = field(default_factory=_now)
    finished_at: datetime | None = None
    sources: tuple[str, ...] = ()
    queries: tuple[str, ...] = ()
    jobs_found: int = 0
    jobs_new: int = 0
    jobs_matched: int = 0
    errors: tuple[str, ...] = ()
    duration_seconds: float | None = None

    def __post_init__(self) -> None:
        if not self.search_profile_id.strip():
            raise ValueError("search_run search_profile_id is required")
        for name in ("sources", "queries", "errors"):
            _strings(getattr(self, name), f"search_run.{name}")
        for name in ("jobs_found", "jobs_new", "jobs_matched"):
            if getattr(self, name) < 0:
                raise ValueError(f"search_run {name} must be non-negative")
        if self.duration_seconds is not None and self.duration_seconds < 0:
            raise ValueError("search_run duration_seconds must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "search_profile_id": self.search_profile_id,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "sources": list(self.sources),
            "queries": list(self.queries),
            "jobs_found": self.jobs_found,
            "jobs_new": self.jobs_new,
            "jobs_matched": self.jobs_matched,
            "errors": list(self.errors),
            "duration_seconds": self.duration_seconds,
        }
