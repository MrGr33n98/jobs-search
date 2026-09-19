"""REST routes under ``/api``."""

from __future__ import annotations

import hmac
import os
import sqlite3
from typing import Any, Literal

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Response,
    UploadFile,
)
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from openings.application.attachments import AttachmentTooLarge
from openings.application.career import (
    CollectionUnavailable,
    SearchProfileAlreadyRunning,
    SearchProfileDisabled,
    SearchProfileNotFound,
)
from openings.collection_profiles import CollectionPlanError
from openings.application.jobs import VectorStoreUnavailableError
from openings.application.models import AddJobCommand
from openings.career import (
    ApplicationStage,
    LocationType,
    RemoteEligibility,
    RemoteScope,
    ReviewStatus,
)
from openings.db import JOB_SORTS, SORT_DIRECTIONS, JobQuery
from openings.models import POSTING_FIELDS, AttachmentKind, JobStatus, NoteKind
from openings.settings_reference import get_settings_reference
from openings.web.service import get_career_service, get_service

TOKEN_HEADER = "X-Openings-Token"


def api_token() -> str:
    return os.environ.get("OPENINGS_API_TOKEN", "").strip()


def token_presented(expected: str, authorization: str | None, x_token: str | None) -> bool:
    presented = (x_token or "").strip()
    if not presented and authorization and authorization.lower().startswith("bearer "):
        presented = authorization[7:].strip()
    return bool(presented) and hmac.compare_digest(presented, expected)


def require_token(
    authorization: str | None = Header(default=None),
    x_openings_token: str | None = Header(default=None, alias=TOKEN_HEADER),
) -> None:
    expected = api_token()
    if expected and not token_presented(expected, authorization, x_openings_token):
        raise HTTPException(status_code=401, detail="Invalid or missing API token")


public_router = APIRouter(prefix="/api")
router = APIRouter(prefix="/api", dependencies=[Depends(require_token)])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


def _check_statuses(values: list[str]) -> list[str]:
    for value in values:
        try:
            JobStatus(value.strip().lower())
        except ValueError as exc:
            raise ValueError(
                f"unknown status {value!r}; expected one of {', '.join(s.value for s in JobStatus)}"
            ) from exc
    return [value.strip().lower() for value in values]


class JobFilters(BaseModel):
    """Every filter ``GET /jobs``, ``POST /export/jobs`` and MCP accept."""

    model_config = ConfigDict(extra="forbid")

    limit: int = Field(default=50, ge=0, le=1000)
    offset: int = Field(default=0, ge=0)
    statuses: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    labels: list[str] = Field(default_factory=list)
    company: str | None = None
    location: str | None = None
    locations: list[str] = Field(default_factory=list)
    job_types: list[str] = Field(default_factory=list)
    remote: bool | None = None
    min_score: int | None = None
    max_score: int | None = None
    min_salary: float | None = None
    max_salary: float | None = None
    date_posted_from: str | None = None
    date_posted_to: str | None = None
    first_seen_from: str | None = None
    first_seen_to: str | None = None
    last_seen_from: str | None = None
    last_seen_to: str | None = None
    status_changed_from: str | None = None
    status_changed_to: str | None = None
    has_attachments: bool | None = None
    without_labels: bool | None = None
    text: str | None = None
    sort: str = "score"
    direction: str | None = None

    @field_validator("statuses")
    @classmethod
    def _statuses(cls, values: list[str]) -> list[str]:
        return _check_statuses(values)

    @field_validator("sort")
    @classmethod
    def _sort(cls, value: str) -> str:
        if value not in JOB_SORTS:
            raise ValueError(f"sort must be one of {', '.join(JOB_SORTS)}")
        return value

    @field_validator("direction")
    @classmethod
    def _direction(cls, value: str | None) -> str | None:
        if value is not None and value not in SORT_DIRECTIONS:
            raise ValueError("direction must be asc or desc")
        return value

    def to_query(self) -> JobQuery:
        data = self.model_dump()
        for key in ("statuses", "sources", "labels", "locations", "job_types"):
            data[key] = tuple(data[key])
        return JobQuery(**data)


class JobIds(BaseModel):
    job_ids: list[str] = Field(min_length=1)


class StatusRequest(JobIds):
    status: JobStatus
    note: str | None = None


class BlacklistRequest(JobIds):
    note: str | None = None


class LabelsRequest(JobIds):
    labels: list[str] = Field(min_length=1)


class MergeRequest(BaseModel):
    primary_id: str
    other_ids: list[str] = Field(min_length=1)


class AddJobRequest(BaseModel):
    title: str = Field(min_length=1)
    company: str = Field(min_length=1)
    location: str = ""
    job_url: str | None = None
    description: str | None = None
    date_posted: str | None = None
    job_type: str | None = None
    is_remote: bool | None = None
    job_level: str | None = None
    min_amount: float | None = None
    max_amount: float | None = None
    currency: str | None = None
    salary_interval: str | None = None
    company_url: str | None = None
    source: str | None = None
    external_id: str | None = None
    status: JobStatus = JobStatus.SHORTLISTED
    labels: list[str] = Field(default_factory=list)
    note: str | None = None


class UpdateJobRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1)
    company: str | None = Field(default=None, min_length=1)
    location: str | None = None
    job_url: str | None = None
    description: str | None = None
    date_posted: str | None = None
    job_type: str | None = None
    is_remote: bool | None = None
    job_level: str | None = None
    min_amount: float | None = None
    max_amount: float | None = None
    currency: str | None = None
    salary_interval: str | None = None
    company_url: str | None = None

    def changes(self) -> dict[str, Any]:
        return {
            key: value
            for key, value in self.model_dump(exclude_unset=True).items()
            if key in POSTING_FIELDS
        }


class NoteRequest(BaseModel):
    kind: NoteKind = NoteKind.NOTE
    title: str | None = None
    body: str = Field(min_length=1)


class NoteUpdateRequest(BaseModel):
    kind: NoteKind | None = None
    title: str | None = None
    body: str | None = Field(default=None, min_length=1)


class AttachmentUpdateRequest(BaseModel):
    kind: AttachmentKind | None = None
    note: str | None = None
    filename: str | None = Field(default=None, min_length=1)


class LabelRenameRequest(BaseModel):
    old: str = Field(min_length=1)
    new: str = Field(min_length=1)


class LabelDeleteRequest(BaseModel):
    label: str = Field(min_length=1)


class ScoreRequest(BaseModel):
    score: int
    dry_run: bool = False


class DaysRequest(BaseModel):
    days: int = Field(ge=1)
    dry_run: bool = False


class ExportRequest(BaseModel):
    format: Literal["csv", "json"] = "csv"
    job_ids: list[str] | None = None
    filters: JobFilters | None = None


class CandidateProfilePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, min_length=1)
    headline: str | None = Field(default=None, min_length=1)
    current_location: str | None = Field(default=None, min_length=1)
    country: str | None = Field(default=None, min_length=1)
    languages: list[str] | None = None
    skills: list[str] | None = None
    experience: list[dict[str, Any]] | None = None
    education: list[dict[str, Any]] | None = None
    certifications: list[str] | None = None
    work_authorizations: list[str] | None = None
    preferred_work_modes: list[str] | None = None
    metadata: dict[str, Any] | None = None


class SearchProfileCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    description: str | None = None
    enabled: bool = False
    target_roles: list[str] = Field(default_factory=list)
    role_aliases: list[str] = Field(default_factory=list)
    include_keywords: list[str] = Field(default_factory=list)
    exclude_keywords: list[str] = Field(default_factory=list)
    skills_priority: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    countries: list[str] = Field(default_factory=list)
    location_types: list[LocationType] = Field(default_factory=list)
    remote_scope: RemoteScope = RemoteScope.UNKNOWN
    remote_eligibility: RemoteEligibility = RemoteEligibility.UNKNOWN
    salary_min: float | None = Field(default=None, ge=0)
    salary_currency: str | None = None
    seniority_levels: list[str] = Field(default_factory=list)
    employment_types: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    freshness_days: int | None = Field(default=None, ge=1)
    scoring_weights: dict[str, int] = Field(default_factory=dict)


class SearchProfilePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1)
    description: str | None = None
    enabled: bool | None = None
    target_roles: list[str] | None = None
    role_aliases: list[str] | None = None
    include_keywords: list[str] | None = None
    exclude_keywords: list[str] | None = None
    skills_priority: list[str] | None = None
    locations: list[str] | None = None
    countries: list[str] | None = None
    location_types: list[LocationType] | None = None
    remote_scope: RemoteScope | None = None
    remote_eligibility: RemoteEligibility | None = None
    salary_min: float | None = Field(default=None, ge=0)
    salary_currency: str | None = None
    seniority_levels: list[str] | None = None
    employment_types: list[str] | None = None
    sources: list[str] | None = None
    freshness_days: int | None = Field(default=None, ge=1)
    scoring_weights: dict[str, int] | None = None


class ReviewMatchRequest(BaseModel):
    review_status: ReviewStatus


class ApplicationStageRequest(BaseModel):
    stage: ApplicationStage


def _profile_data(model: BaseModel, *, partial: bool = False) -> dict[str, Any]:
    return model.model_dump(exclude_unset=partial)


def _job_query(
    limit: int = Query(50, ge=0, le=1000),
    offset: int = Query(0, ge=0),
    statuses: list[str] | None = Query(None),
    sources: list[str] | None = Query(None),
    labels: list[str] | None = Query(None),
    company: str | None = None,
    location: str | None = None,
    locations: list[str] | None = Query(None),
    job_types: list[str] | None = Query(None),
    remote: bool | None = None,
    min_score: int | None = None,
    max_score: int | None = None,
    min_salary: float | None = None,
    max_salary: float | None = None,
    date_posted_from: str | None = None,
    date_posted_to: str | None = None,
    first_seen_from: str | None = None,
    first_seen_to: str | None = None,
    last_seen_from: str | None = None,
    last_seen_to: str | None = None,
    status_changed_from: str | None = None,
    status_changed_to: str | None = None,
    has_attachments: bool | None = None,
    without_labels: bool | None = None,
    text: str | None = None,
    sort: str = Query("score"),
    direction: str | None = None,
) -> JobQuery:
    try:
        filters = JobFilters(
            limit=limit,
            offset=offset,
            statuses=statuses or [],
            sources=sources or [],
            labels=labels or [],
            company=company,
            location=location,
            locations=locations or [],
            job_types=job_types or [],
            remote=remote,
            min_score=min_score,
            max_score=max_score,
            min_salary=min_salary,
            max_salary=max_salary,
            date_posted_from=date_posted_from,
            date_posted_to=date_posted_to,
            first_seen_from=first_seen_from,
            first_seen_to=first_seen_to,
            last_seen_from=last_seen_from,
            last_seen_to=last_seen_to,
            status_changed_from=status_changed_from,
            status_changed_to=status_changed_to,
            has_attachments=has_attachments,
            without_labels=without_labels,
            text=text,
            sort=sort,
            direction=direction,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return filters.to_query()


# ---------------------------------------------------------------------------
# Public
# ---------------------------------------------------------------------------


@public_router.get("/dashboard/auth")
def dashboard_auth() -> dict[str, bool]:
    return {"token_required": bool(api_token())}


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------


@router.get("/jobs")
def list_jobs(query: JobQuery = Depends(_job_query)) -> dict[str, Any]:
    page = get_service().list_jobs(JobQuery(**{**query.__dict__, "limit": query.limit or 1}))
    return page.to_dict()


@router.post("/jobs")
def add_job(payload: AddJobRequest, response: Response) -> dict[str, Any]:
    command = AddJobCommand(
        **{**payload.model_dump(exclude={"labels"}), "labels": tuple(payload.labels)}
    )
    result = get_service().add_job(command)
    if not result.success:
        raise HTTPException(status_code=409, detail=result.message)
    response.status_code = 201 if result.message == "created" else 200
    return result.to_dict()


@router.get("/jobs/facets")
def facets(limit: int = Query(50, ge=1, le=1000), q: str | None = None) -> dict[str, Any]:
    return get_service().get_facets(limit=limit, q=q)


@router.get("/jobs/search/semantic")
def semantic_search(
    q: str | None = Query(None, min_length=1),
    job_id: str | None = None,
    n_results: int = Query(10, ge=1, le=100),
    min_score: int | None = None,
    source: str | None = None,
    statuses: list[str] | None = Query(None),
) -> list[dict[str, Any]]:
    if not q and not job_id:
        raise HTTPException(status_code=422, detail="q or job_id is required")
    try:
        results = get_service().search_similar(
            q,
            job_id=job_id,
            n_results=n_results,
            min_score=min_score,
            source=source,
            statuses=_check_statuses(statuses or []),
        )
    except VectorStoreUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return [result.to_dict() for result in results]


@router.post("/jobs/status")
def set_status(payload: StatusRequest) -> dict[str, Any]:
    return get_service().set_status(payload.job_ids, payload.status, payload.note).to_dict()


@router.post("/jobs/labels")
def add_labels(payload: LabelsRequest) -> dict[str, Any]:
    return get_service().add_labels(payload.job_ids, payload.labels).to_dict()


@router.post("/jobs/labels/remove")
def remove_labels(payload: LabelsRequest) -> dict[str, Any]:
    return get_service().remove_labels(payload.job_ids, payload.labels).to_dict()


@router.post("/jobs/delete")
def delete_jobs(payload: JobIds) -> dict[str, Any]:
    return get_service().delete_jobs(payload.job_ids).to_dict()


@router.post("/jobs/merge")
def merge_jobs(payload: MergeRequest) -> dict[str, Any]:
    result = get_service().merge_jobs(payload.primary_id, payload.other_ids)
    if not result.success:
        raise HTTPException(status_code=404, detail=result.message)
    return result.to_dict()


@router.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    detail = get_service().get_job_detail(job_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return detail.to_dict()


@router.patch("/jobs/{job_id}")
def update_job(job_id: str, payload: UpdateJobRequest) -> dict[str, Any]:
    changes = payload.changes()
    if not changes:
        raise HTTPException(status_code=422, detail="No editable field given")
    updated = get_service().update_job(job_id, changes)
    if updated is None:
        raise HTTPException(status_code=404, detail="Job not found")
    detail = get_service().get_job_detail(job_id)
    return detail.to_dict() if detail else updated.to_dict()


@router.get("/jobs/{job_id}/similar")
def similar_jobs(job_id: str, n_results: int = Query(10, ge=1, le=50)) -> list[dict[str, Any]]:
    if get_service().get_job(job_id) is None:
        raise HTTPException(status_code=404, detail="Job not found")
    try:
        results = get_service().search_similar(job_id=job_id, n_results=n_results)
    except VectorStoreUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return [result.to_dict() for result in results]


@router.get("/jobs/{job_id}/bundle.zip")
def job_bundle(job_id: str) -> Response:
    bundle = get_service().build_bundle(job_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="Job not found")
    content, filename = bundle
    return Response(
        content=content,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/jobs/{job_id}/notes", status_code=201)
def add_note(job_id: str, payload: NoteRequest) -> dict[str, Any]:
    note = get_service().add_note(job_id, payload.kind, payload.body, payload.title)
    if note is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return note.to_dict()


@router.put("/jobs/{job_id}/notes/{note_id}")
def update_note(job_id: str, note_id: int, payload: NoteUpdateRequest) -> dict[str, Any]:
    try:
        note = get_service().update_note(
            job_id, note_id, body=payload.body, title=payload.title, kind=payload.kind
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    return note.to_dict()


@router.delete("/jobs/{job_id}/notes/{note_id}")
def delete_note(job_id: str, note_id: int) -> dict[str, Any]:
    if not get_service().delete_note(job_id, note_id):
        raise HTTPException(status_code=404, detail="Note not found")
    return {"success": True}


@router.post("/jobs/{job_id}/attachments", status_code=201)
async def upload_attachment(
    job_id: str,
    file: UploadFile = File(...),
    kind: AttachmentKind = Form(AttachmentKind.OTHER),
    note: str | None = Form(None),
) -> dict[str, Any]:
    content = await file.read()
    try:
        attachment = get_service().add_attachment(
            job_id, kind=kind, filename=file.filename or "attachment", content=content, note=note
        )
    except AttachmentTooLarge as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if attachment is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return attachment.to_dict()


@router.get("/jobs/{job_id}/attachments/{attachment_id}")
def download_attachment(job_id: str, attachment_id: int, inline: bool = False) -> FileResponse:
    found = get_service().get_attachment_file(job_id, attachment_id)
    if found is None:
        raise HTTPException(status_code=404, detail="Attachment not found")
    attachment, path = found
    disposition = "inline" if inline else "attachment"
    return FileResponse(
        path,
        filename=attachment.filename,
        content_disposition_type=disposition,
    )


@router.patch("/jobs/{job_id}/attachments/{attachment_id}")
def update_attachment(
    job_id: str, attachment_id: int, payload: AttachmentUpdateRequest
) -> dict[str, Any]:
    attachment = get_service().update_attachment(
        job_id, attachment_id, kind=payload.kind, note=payload.note, filename=payload.filename
    )
    if attachment is None:
        raise HTTPException(status_code=404, detail="Attachment not found")
    return attachment.to_dict()


@router.delete("/jobs/{job_id}/attachments/{attachment_id}")
def delete_attachment(job_id: str, attachment_id: int) -> dict[str, Any]:
    if not get_service().delete_attachment(job_id, attachment_id):
        raise HTTPException(status_code=404, detail="Attachment not found")
    return {"success": True}


@router.get("/attachments")
def list_attachments(
    kind: AttachmentKind | None = None,
    statuses: list[str] | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    try:
        clean = _check_statuses(statuses or [])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    entries, total = get_service().list_attachments(
        kind=kind, statuses=clean, limit=limit, offset=offset
    )
    return {
        "items": [entry.to_dict() for entry in entries],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------


@router.get("/labels")
def list_labels() -> list[dict[str, Any]]:
    return get_service().get_facets(limit=1000)["labels"]


@router.post("/labels/rename")
def rename_label(payload: LabelRenameRequest) -> dict[str, Any]:
    return get_service().rename_label(payload.old, payload.new).to_dict()


@router.post("/labels/delete")
def delete_label(payload: LabelDeleteRequest) -> dict[str, Any]:
    return get_service().delete_label(payload.label).to_dict()


# ---------------------------------------------------------------------------
# Blacklist
# ---------------------------------------------------------------------------


@router.get("/blacklist")
def list_blacklist(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    text: str | None = None,
    company: str | None = None,
    location: str | None = None,
) -> dict[str, Any]:
    page = get_service().list_jobs(
        JobQuery(
            limit=limit,
            offset=offset,
            statuses=(JobStatus.BLACKLISTED.value,),
            text=text,
            company=company,
            location=location,
            sort="updated",
        )
    )
    return page.to_dict()


@router.post("/blacklist")
def blacklist_jobs(payload: BlacklistRequest) -> dict[str, Any]:
    return get_service().blacklist_jobs(payload.job_ids, payload.note).to_dict()


@router.post("/blacklist/remove")
def unblacklist_jobs(payload: JobIds) -> dict[str, Any]:
    return get_service().unblacklist_jobs(payload.job_ids).to_dict()


# ---------------------------------------------------------------------------
# Sources, runs, statistics, settings
# ---------------------------------------------------------------------------


@router.get("/candidate-profile")
def get_candidate_profile() -> dict[str, Any]:
    profile = get_career_service().get_candidate_profile()
    return {"profile": profile.to_dict() if profile else None}


@router.patch("/candidate-profile")
def update_candidate_profile(payload: CandidateProfilePatch) -> dict[str, Any]:
    try:
        profile = get_career_service().update_candidate_profile(
            _profile_data(payload, partial=True)
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"profile": profile.to_dict()}


@router.get("/search-profiles")
def list_search_profiles(
    limit: int = Query(50, ge=1, le=1000), offset: int = Query(0, ge=0)
) -> dict[str, Any]:
    profiles, total = get_career_service().list_search_profiles(limit, offset)
    return {
        "items": [profile.to_dict() for profile in profiles],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("/search-profiles", status_code=201)
def create_search_profile(payload: SearchProfileCreate) -> dict[str, Any]:
    try:
        profile = get_career_service().create_search_profile(_profile_data(payload))
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="search profile name already exists") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return profile.to_dict()


@router.get("/search-profiles/capabilities")
def search_profile_capabilities() -> dict[str, Any]:
    return get_career_service().capabilities()


@router.get("/search-profiles/{profile_id}")
def get_search_profile(profile_id: str) -> dict[str, Any]:
    try:
        return get_career_service().get_search_profile(profile_id).to_dict()
    except SearchProfileNotFound as exc:
        raise HTTPException(status_code=404, detail="Search profile not found") from exc


@router.patch("/search-profiles/{profile_id}")
def update_search_profile(profile_id: str, payload: SearchProfilePatch) -> dict[str, Any]:
    changes = _profile_data(payload, partial=True)
    if not changes:
        raise HTTPException(status_code=422, detail="No editable field given")
    try:
        profile = get_career_service().update_search_profile(profile_id, changes)
    except SearchProfileNotFound as exc:
        raise HTTPException(status_code=404, detail="Search profile not found") from exc
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="search profile name already exists") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return profile.to_dict()


@router.delete("/search-profiles/{profile_id}")
def disable_search_profile(profile_id: str) -> dict[str, Any]:
    try:
        profile = get_career_service().disable_search_profile(profile_id)
    except SearchProfileNotFound as exc:
        raise HTTPException(status_code=404, detail="Search profile not found") from exc
    return profile.to_dict()


@router.get("/search-profiles/{profile_id}/matches")
def search_profile_matches(
    profile_id: str,
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    min_score: int | None = Query(None, ge=0, le=100),
    eligibility: RemoteEligibility | None = None,
    review_status: ReviewStatus | None = None,
) -> dict[str, Any]:
    try:
        return get_career_service().get_matches(
            profile_id, limit, offset, min_score, eligibility.value if eligibility else None,
            review_status.value if review_status else None,
        )
    except SearchProfileNotFound as exc:
        raise HTTPException(status_code=404, detail="Search profile not found") from exc


@router.patch("/search-profiles/{profile_id}/matches/{job_id}")
def review_search_profile_match(
    profile_id: str, job_id: str, payload: ReviewMatchRequest
) -> dict[str, Any]:
    try:
        match = get_career_service().review_match(profile_id, job_id, payload.review_status)
    except SearchProfileNotFound as exc:
        raise HTTPException(status_code=404, detail="Search profile not found") from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "job_id": match.job_id,
        "search_profile_id": match.search_profile_id,
        "review_status": match.review_status.value,
        "reviewed_at": match.reviewed_at.isoformat() if match.reviewed_at else None,
    }


@router.get("/search-profiles/{profile_id}/runs")
def search_profile_runs(
    profile_id: str,
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    try:
        return get_career_service().get_runs(profile_id, limit, offset)
    except SearchProfileNotFound as exc:
        raise HTTPException(status_code=404, detail="Search profile not found") from exc


@router.get("/applications")
def list_applications(
    limit: int = Query(50, ge=1, le=1000), offset: int = Query(0, ge=0)
) -> dict[str, Any]:
    return get_career_service().list_applications(limit, offset)


@router.post("/search-profiles/{profile_id}/matches/{job_id}/pipeline", status_code=201)
def add_match_to_pipeline(profile_id: str, job_id: str) -> dict[str, Any]:
    try:
        application = get_career_service().add_to_pipeline(profile_id, job_id)
    except SearchProfileNotFound as exc:
        raise HTTPException(status_code=404, detail="Search profile not found") from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return application.to_dict()


@router.patch("/applications/{application_id}")
def update_application_stage(
    application_id: str, payload: ApplicationStageRequest
) -> dict[str, Any]:
    try:
        return get_career_service().update_application_stage(application_id, payload.stage).to_dict()
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/search-profiles/{profile_id}/run")
def run_search_profile(profile_id: str) -> dict[str, Any]:
    try:
        return get_career_service().run_search_profile(profile_id).to_dict()
    except SearchProfileNotFound as exc:
        raise HTTPException(status_code=404, detail="Search profile not found") from exc
    except SearchProfileDisabled as exc:
        raise HTTPException(status_code=409, detail="Search profile is disabled") from exc
    except SearchProfileAlreadyRunning as exc:
        raise HTTPException(status_code=409, detail="Search profile already running") from exc
    except CollectionPlanError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except CollectionUnavailable as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc


@router.get("/sources")
def list_sources() -> list[dict[str, Any]]:
    return [source.to_dict() for source in get_service().list_sources()]


@router.get("/companies/{company}/statuses")
def company_statuses(company: str) -> dict[str, int]:
    return get_service().company_status_counts(company)


@router.get("/runs")
def list_runs(limit: int = Query(20, ge=1, le=200)) -> list[dict[str, Any]]:
    return [run.to_dict() for run in get_service().list_runs(limit)]


@router.get("/runs/status")
def run_status() -> dict[str, Any]:
    return get_service().run_status()


@router.post("/runs", status_code=202)
def request_run() -> dict[str, Any]:
    return get_service().request_run()


@router.get("/stats")
def statistics() -> dict[str, Any]:
    return get_service().get_statistics()


@router.get("/distribution")
def distribution(bin_size: int = Query(5, ge=1, le=100)) -> list[list[int]]:
    return get_service().get_score_distribution(bin_size)


@router.get("/settings")
def settings_summary() -> dict[str, Any]:
    return get_service().settings_summary()


@router.get("/settings/reference")
def settings_reference() -> PlainTextResponse:
    return PlainTextResponse(get_settings_reference(), media_type="text/markdown")


# ---------------------------------------------------------------------------
# Export and cleanup
# ---------------------------------------------------------------------------


def _export_response(result) -> Response:
    return Response(
        content=result.content,
        media_type=result.media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{result.filename}"',
            "X-Openings-Export-Rows": str(result.row_count),
            "X-Openings-Export-Total": str(result.total),
        },
    )


@router.get("/export/jobs")
def export_jobs(
    format: Literal["csv", "json"] = "csv", query: JobQuery = Depends(_job_query)
) -> Response:
    return _export_response(get_service().export_jobs(query=query, fmt=format))


@router.post("/export/jobs")
def export_selected(payload: ExportRequest) -> Response:
    service = get_service()
    if payload.job_ids is not None:
        result = service.export_jobs(job_ids=payload.job_ids, fmt=payload.format)
    else:
        query = (payload.filters or JobFilters()).to_query()
        result = service.export_jobs(query=query, fmt=payload.format)
    return _export_response(result)


@router.get("/cleanup/preview")
def cleanup_preview() -> dict[str, int]:
    return get_service().preview_cleanup().to_dict()


@router.post("/cleanup/run")
def cleanup_run() -> dict[str, int]:
    return get_service().run_cleanup().to_dict()


@router.post("/cleanup/delete-below-score")
def cleanup_below_score(payload: ScoreRequest) -> dict[str, Any]:
    return get_service().delete_below_score(payload.score, dry_run=payload.dry_run).to_dict()


@router.post("/cleanup/delete-stale")
def cleanup_stale(payload: DaysRequest) -> dict[str, Any]:
    return get_service().delete_stale(payload.days, dry_run=payload.dry_run).to_dict()
