"""Deterministic, profile-specific scoring for CAREER-01E.

This module intentionally has no HTTP, collector, clock, random or LLM
dependency. The legacy YAML scorer in :mod:`openings.scoring` remains a
separate compatibility path.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from openings.career import CandidateProfile, RemoteEligibility, SearchProfile
from openings.models import Job

SCORING_VERSION = "career-01e-v1"
DEFAULT_WEIGHTS = {
    "role": 45,
    "keywords": 20,
    "skills": 20,
    "location": 10,
    "employment_type": 5,
    "exclusions": -20,
}


def _normalize(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9+#.]+", " ", text.casefold()).strip()


def _contains(term: str, text: str) -> bool:
    normalized = _normalize(term)
    if not normalized:
        return False
    return re.search(rf"(?<![a-z0-9]){re.escape(normalized)}(?![a-z0-9])", text) is not None


def _job_text(job: Job) -> str:
    values = (job.title, job.company, job.location, job.description, job.job_type, job.job_level)
    return _normalize(" ".join(value or "" for value in values))


def _role_match(title: str, profile: SearchProfile) -> tuple[int, str | None]:
    candidates = tuple(dict.fromkeys((*profile.target_roles, *profile.role_aliases)))
    best: tuple[int, str] | None = None
    normalized_title = _normalize(title)
    for role in candidates:
        normalized_role = _normalize(role)
        if not normalized_role:
            continue
        tokens = normalized_role.split()
        if normalized_title == normalized_role:
            candidate = (100, role)
        elif _contains(normalized_role, normalized_title):
            candidate = (90, role)
        elif all(_contains(token, normalized_title) for token in tokens):
            candidate = (70, role)
        else:
            continue
        if best is None or candidate[0] > best[0] or (
            candidate[0] == best[0] and candidate[1].casefold() < best[1].casefold()
        ):
            best = candidate
    return (best[0], f"Role matches {best[1]}") if best else (0, None)


@dataclass(frozen=True)
class ScoreBreakdown:
    role: int
    keywords: int
    skills: int
    location: int
    employment_type: int
    exclusions: int

    def to_dict(self) -> dict[str, int]:
        return {
            "role": self.role,
            "keywords": self.keywords,
            "skills": self.skills,
            "location": self.location,
            "employment_type": self.employment_type,
            "exclusions": self.exclusions,
        }


@dataclass(frozen=True)
class ProfileScoreResult:
    score: int
    eligibility: RemoteEligibility
    match_reasons: tuple[str, ...]
    missing_requirements: tuple[str, ...]
    breakdown: ScoreBreakdown
    scoring_version: str = SCORING_VERSION


def _weights(profile: SearchProfile) -> dict[str, int]:
    values = dict(DEFAULT_WEIGHTS)
    for key, value in profile.scoring_weights.items():
        if key not in values:
            continue
        if value < 0 and key != "exclusions":
            raise ValueError(f"scoring weight {key} must be non-negative")
        values[key] = int(value)
    positive_total = sum(values[key] for key in DEFAULT_WEIGHTS if key != "exclusions")
    if positive_total <= 0:
        raise ValueError("scoring weights must have a positive total")
    return values


def _eligibility(job: Job, profile: SearchProfile) -> RemoteEligibility:
    location = _normalize(job.location)
    profile_locations = tuple(_normalize(value) for value in (*profile.locations, *profile.countries))
    remote = job.is_remote is True or "remote" in location
    if remote:
        if profile.remote_eligibility == RemoteEligibility.RESTRICTED:
            return RemoteEligibility.RESTRICTED
        if profile.remote_scope.value == "unknown":
            return RemoteEligibility.UNKNOWN
        return RemoteEligibility.ELIGIBLE
    if profile.remote_eligibility == RemoteEligibility.ELIGIBLE and profile.location_types:
        return RemoteEligibility.RESTRICTED
    if profile_locations and any(_contains(value, location) for value in profile_locations if value):
        return RemoteEligibility.ELIGIBLE
    if not location:
        return RemoteEligibility.UNKNOWN
    return RemoteEligibility.UNKNOWN


def score(job: Job, search_profile: SearchProfile, candidate_profile: CandidateProfile | None = None) -> ProfileScoreResult:
    """Score one persisted job for one strategy without inventing candidate facts."""
    weights = _weights(search_profile)
    text = _job_text(job)
    role_quality, role_reason = _role_match(job.title, search_profile)
    positive_terms = tuple(dict.fromkeys((*search_profile.include_keywords, *search_profile.skills_priority)))
    keyword_hits = tuple(term for term in positive_terms if _contains(term, text))
    candidate_skills = tuple(candidate_profile.skills if candidate_profile else ())
    skill_hits = tuple(term for term in candidate_skills if _contains(term, text))
    exclusions = tuple(term for term in search_profile.exclude_keywords if _contains(term, text))
    location_ok = bool(search_profile.locations or search_profile.countries) and any(
        _contains(value, _normalize(job.location))
        for value in (*search_profile.locations, *search_profile.countries)
    )
    remote = job.is_remote is True or "remote" in _normalize(job.location)
    location_signal = location_ok or (remote and search_profile.remote_scope.value != "unknown")
    employment_signal = bool(
        search_profile.employment_types
        and job.job_type
        and _normalize(job.job_type) in {_normalize(value) for value in search_profile.employment_types}
    )
    positive_total = sum(weights[key] for key in DEFAULT_WEIGHTS if key != "exclusions")
    raw = {
        "role": round(weights["role"] * role_quality / 100),
        "keywords": round(weights["keywords"] * min(len(keyword_hits), 3) / max(1, min(len(positive_terms), 3))),
        "skills": round(weights["skills"] * min(len(skill_hits), 3) / max(1, min(len(candidate_skills), 3))),
        "location": weights["location"] if location_signal else 0,
        "employment_type": weights["employment_type"] if employment_signal else 0,
        "exclusions": weights["exclusions"] if exclusions else 0,
    }
    # Keep a custom policy on the same 0..100 scale while retaining an exact
    # and auditable component sum.
    scale = 100 / positive_total
    breakdown = ScoreBreakdown(
        role=round(raw["role"] * scale),
        keywords=round(raw["keywords"] * scale),
        skills=round(raw["skills"] * scale),
        location=round(raw["location"] * scale),
        employment_type=round(raw["employment_type"] * scale),
        exclusions=round(raw["exclusions"] * scale),
    )
    score_value = max(0, min(100, sum(breakdown.to_dict().values())))
    reasons = [role_reason] if role_reason else []
    reasons.extend(f"Matched keyword: {term}" for term in keyword_hits)
    reasons.extend(f"Candidate skill found: {term}" for term in skill_hits)
    if location_signal:
        reasons.append("Location or remote scope compatible")
    if employment_signal:
        reasons.append(f"Employment type matches {job.job_type}")
    if exclusions:
        reasons.extend(f"Excluded keyword found: {term}" for term in exclusions)
    return ProfileScoreResult(
        score=score_value,
        eligibility=_eligibility(job, search_profile),
        match_reasons=tuple(reasons),
        missing_requirements=(),
        breakdown=breakdown,
    )
