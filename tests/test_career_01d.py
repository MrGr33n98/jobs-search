from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pandas as pd
import pytest

from openings.career import SearchRunStatus
from openings.collection_profiles import CollectionPlanError, build_collection_plan
from openings.models import SourceRunStats
from openings.sources.collect import CollectResult
from openings.sources.base import frame_from_records


def create_profile(client, **overrides):
    payload = {
        "name": "Profile collection",
        "enabled": True,
        "target_roles": ["Mechanical Engineer"],
        "sources": ["jobspy"],
    }
    payload.update(overrides)
    response = client.post("/api/search-profiles", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def capabilities(source: str = "jobspy"):
    return {"sources": [{"id": source, "available": True, "enabled": True}]}


def test_collection_plan_is_deterministic_and_maps_strategy(config):
    from openings.career import SearchProfile

    profile = SearchProfile(
        name="Mechanical",
        target_roles=("Mechanical Engineer",),
        role_aliases=("Engenheiro Mecânico",),
        include_keywords=("CAD",),
        locations=("São Paulo",),
        countries=("Brazil",),
        employment_types=("fulltime",),
        freshness_days=7,
        sources=("jobspy",),
    )
    first = build_collection_plan(profile, capabilities(), config)
    second = build_collection_plan(profile, capabilities(), config)
    assert first == second
    assert first.queries == ("Mechanical Engineer", "Engenheiro Mecânico", "CAD")
    assert first.locations == ("São Paulo", "Brazil")
    assert first.jobspy_country == "brazil"
    assert first.freshness_days == 7


def test_collection_plan_invalid_country_falls_back_without_crashing(config):
    from openings.career import SearchProfile

    profile = SearchProfile(
        name="Global", target_roles=("Engineer",), countries=("Atlantis",), sources=("jobspy",)
    )
    plan = build_collection_plan(profile, capabilities(), config)
    assert plan.jobspy_country == "worldwide"
    assert "unsupported JobSpy country" in plan.warnings[0]


def test_collection_plan_rejects_unavailable_source(config):
    from openings.career import SearchProfile

    profile = SearchProfile(name="RSS", target_roles=("Engineer",), sources=("rss",))
    with pytest.raises(CollectionPlanError, match="unsupported"):
        build_collection_plan(profile, capabilities(), config)


def test_profile_run_persists_real_run_and_jobs(client, runtime, monkeypatch):
    configured = runtime.config()
    configured.sources.jobspy.enabled = True
    monkeypatch.setattr(runtime, "config", lambda reload=False: configured)
    profile = create_profile(client)
    records = frame_from_records(
        [
            {
                "title": "Mechanical Engineer",
                "company": "Controlled Co",
                "location": "São Paulo",
                "source": "jobspy",
                "external_id": "controlled-1",
                "job_url": "https://example.test/jobs/controlled-1",
                "description": "Mechanical design and CAD.",
            }
        ]
    )
    result = CollectResult(
        frame=records,
        stats=[SourceRunStats(name="jobspy", tasks=1, succeeded=1, rows=1)],
        total_found=1,
    )
    monkeypatch.setattr(
        "openings.application.career.collect_all", lambda config, known=None: result
    )
    response = client.post(f"/api/search-profiles/{profile['id']}/run")
    assert response.status_code == 200, response.text
    run = response.json()
    assert run["status"] == "completed"
    assert run["jobs_found"] == 1
    assert run["jobs_new"] == 1
    assert runtime.db.count_jobs() == 1
    assert runtime.db.count_search_runs(profile["id"]) == 1


def test_profile_run_partial_failure_is_recorded(client, runtime, monkeypatch):
    configured = runtime.config()
    configured.sources.jobspy.enabled = True
    monkeypatch.setattr(runtime, "config", lambda reload=False: configured)
    profile = create_profile(client, name="Partial profile")
    result = CollectResult(
        frame=pd.DataFrame(),
        stats=[
            SourceRunStats(name="jobspy", tasks=1, succeeded=1, rows=0),
            SourceRunStats(name="greenhouse:configured", tasks=1, failed=1, errors=["bad slug"]),
        ],
    )
    monkeypatch.setattr(
        "openings.application.career.collect_all", lambda config, known=None: result
    )
    response = client.post(f"/api/search-profiles/{profile['id']}/run")
    assert response.status_code == 200
    assert response.json()["status"] == SearchRunStatus.PARTIAL.value
    assert "greenhouse:configured: bad slug" in response.json()["errors"]


def test_profile_run_rejects_disabled_profile(client):
    profile = create_profile(client, name="Disabled profile", enabled=False)
    response = client.post(f"/api/search-profiles/{profile['id']}/run")
    assert response.status_code == 409
    assert client.get(f"/api/search-profiles/{profile['id']}/runs").json()["total"] == 0


def test_same_posting_from_two_profiles_remains_one_canonical_job(client, runtime, monkeypatch):
    runtime.config().sources.jobspy.enabled = True
    configured = runtime.config()
    monkeypatch.setattr(runtime, "config", lambda reload=False: configured)
    first = create_profile(client, name="First profile")
    second = create_profile(client, name="Second profile", target_roles=["DevOps Engineer"])
    records = frame_from_records(
        [
            {
                "title": "Mechanical Engineer",
                "company": "Shared Co",
                "location": "Remote",
                "source": "jobspy",
                "external_id": "shared-1",
                "job_url": "https://example.test/jobs/shared-1",
                "description": "Shared posting.",
            }
        ]
    )
    result = CollectResult(
        frame=records,
        stats=[SourceRunStats(name="jobspy", tasks=1, succeeded=1, rows=1)],
        total_found=1,
    )
    monkeypatch.setattr(
        "openings.application.career.collect_all", lambda config, known=None: result
    )
    assert client.post(f"/api/search-profiles/{first['id']}/run").status_code == 200
    assert client.post(f"/api/search-profiles/{second['id']}/run").status_code == 200
    assert runtime.db.count_jobs() == 1
    assert runtime.db.count_job_matches(first["id"]) == 1
    assert runtime.db.count_job_matches(second["id"]) == 1
    first_match = client.get(f"/api/search-profiles/{first['id']}/matches").json()["items"][0]
    second_match = client.get(f"/api/search-profiles/{second['id']}/matches").json()["items"][0]
    assert first_match["match"]["score"] != second_match["match"]["score"]


def test_concurrent_run_for_same_profile_is_rejected(client, runtime, monkeypatch):
    from openings.application.career import SearchProfileAlreadyRunning

    configured = runtime.config()
    configured.sources.jobspy.enabled = True
    monkeypatch.setattr(runtime, "config", lambda reload=False: configured)
    profile = create_profile(client, name="Concurrent profile")
    started = Event()
    release = Event()
    result = CollectResult(
        frame=pd.DataFrame(),
        stats=[SourceRunStats(name="jobspy", tasks=1, succeeded=1)],
    )

    def collect(_config, known=None):
        started.set()
        release.wait(2)
        return result

    monkeypatch.setattr("openings.application.career.collect_all", collect)
    from openings.application.career import CareerApplicationService

    service = CareerApplicationService(runtime)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(service.run_search_profile, profile["id"])
        assert started.wait(2)
        with pytest.raises(SearchProfileAlreadyRunning):
            service.run_search_profile(profile["id"])
        release.set()
        assert first.result().status == SearchRunStatus.COMPLETED
