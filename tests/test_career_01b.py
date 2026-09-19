import json

from openings.career import JobMatch, SearchRun, SearchRunStatus
from tests.conftest import make_job


def create_profile(client, **overrides):
    payload = {"name": "Backend Strategy", "target_roles": ["Backend Engineer"]}
    payload.update(overrides)
    response = client.post("/api/search-profiles", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_candidate_profile_empty_patch_and_unknown_preservation(client):
    empty = client.get("/api/candidate-profile")
    assert empty.status_code == 200 and empty.json() == {"profile": None}

    updated = client.patch(
        "/api/candidate-profile",
        json={"display_name": "Felipe", "skills": ["Python"]},
    )
    assert updated.status_code == 200
    profile = updated.json()["profile"]
    assert profile["display_name"] == "Felipe"
    assert profile["skills"] == ["Python"]
    assert profile["languages"] == []
    assert profile["certifications"] == []


def test_candidate_profile_rejects_arbitrary_and_malformed_fields(client):
    assert client.patch("/api/candidate-profile", json={"invented": True}).status_code == 422
    assert (
        client.patch("/api/candidate-profile", json={"experience": ["not an object"]}).status_code
        == 422
    )


def test_search_profile_crud_validation_and_safe_disable(client):
    created = create_profile(
        client,
        sources=["jobspy", "greenhouse"],
        location_types=["unknown"],
        remote_eligibility="unknown",
    )
    profile_id = created["id"]
    listed = client.get("/api/search-profiles?limit=1")
    assert listed.status_code == 200 and listed.json()["total"] == 1
    assert client.get(f"/api/search-profiles/{profile_id}").json()["name"] == "Backend Strategy"
    assert (
        client.patch(f"/api/search-profiles/{profile_id}", json={"enabled": True}).json()["enabled"]
        is True
    )
    duplicate = client.post("/api/search-profiles", json={"name": "Backend Strategy"})
    assert duplicate.status_code == 409
    assert (
        client.post("/api/search-profiles", json={"name": "x", "sources": ["fake"]}).status_code
        == 422
    )
    disabled = client.delete(f"/api/search-profiles/{profile_id}")
    assert disabled.status_code == 200 and disabled.json()["enabled"] is False
    assert client.get(f"/api/search-profiles/{profile_id}").status_code == 200
    assert client.get("/api/search-profiles/missing").status_code == 404


def test_capabilities_are_backend_derived_and_do_not_expose_internals(client):
    response = client.get("/api/search-profiles/capabilities")
    assert response.status_code == 200
    data = response.json()
    source_ids = {source["id"] for source in data["sources"]}
    assert {"jobspy", "greenhouse", "workday"} <= source_ids
    serialized = json.dumps(data)
    for secret_or_internal in (
        "OPENINGS_API_TOKEN",
        "proxy",
        "parallelism",
        "timeout_seconds",
        "data_dir",
    ):
        assert secret_or_internal not in serialized


def test_matches_and_runs_are_empty_and_disabled_run_is_safe(client):
    profile = create_profile(client)
    profile_id = profile["id"]
    assert client.get(f"/api/search-profiles/{profile_id}/matches?limit=1").json() == {
        "items": [],
        "total": 0,
        "limit": 1,
        "offset": 0,
    }
    assert client.get(f"/api/search-profiles/{profile_id}/runs?limit=1").json() == {
        "items": [],
        "total": 0,
        "limit": 1,
        "offset": 0,
    }
    run = client.post(f"/api/search-profiles/{profile_id}/run")
    assert run.status_code == 409
    assert "disabled" in run.json()["detail"]
    assert client.get(f"/api/search-profiles/{profile_id}/runs").json()["total"] == 0


def test_matches_and_runs_serialize_persisted_rows(client, runtime, job):
    profile = create_profile(client)
    profile_id = profile["id"]
    runtime.db.upsert_jobs([make_job()])
    runtime.db.save_job_match(
        JobMatch(job_id=job.job_id, search_profile_id=profile_id, relevance_score=88)
    )
    runtime.db.save_search_run(
        SearchRun(search_profile_id=profile_id, status=SearchRunStatus.COMPLETED)
    )
    matches = client.get(f"/api/search-profiles/{profile_id}/matches").json()
    assert matches["total"] == 1
    assert matches["items"][0]["match"]["relevance_score"] == 88
    runs = client.get(f"/api/search-profiles/{profile_id}/runs").json()
    assert runs["total"] == 1 and runs["items"][0]["status"] == "completed"


def test_new_endpoints_reuse_existing_token_gate(client, runtime, monkeypatch):
    monkeypatch.setenv("OPENINGS_API_TOKEN", "secret")
    from fastapi.testclient import TestClient
    from openings.web.app import create_app

    with TestClient(create_app()) as token_client:
        assert token_client.get("/api/search-profiles").status_code == 401
        assert (
            token_client.get(
                "/api/search-profiles", headers={"X-Openings-Token": "wrong"}
            ).status_code
            == 401
        )
        assert (
            token_client.get(
                "/api/search-profiles", headers={"X-Openings-Token": "secret"}
            ).status_code
            == 200
        )
