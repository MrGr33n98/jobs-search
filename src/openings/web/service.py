"""The service the web process hands to every route and tool."""

from __future__ import annotations

from openings.application.jobs import JobApplicationService
from openings.application.career import CareerApplicationService
from openings.runtime import get_runtime


def get_service() -> JobApplicationService:
    return get_runtime().service


def get_career_service() -> CareerApplicationService:
    return CareerApplicationService(get_runtime())
