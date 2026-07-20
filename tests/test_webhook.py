"""Tests for the Alertmanager webhook FastAPI app.

Payloads and expected scenario names are derived from SCENARIOS — no hardcoding.
"""

import pytest
from fastapi.testclient import TestClient

from scenarios import SCENARIOS
from autosre.config import AutoSREConfig
from autosre.webhook import create_app, _map_alertmanager_to_scenario


def _sample_scenario_name() -> str:
    return sorted(SCENARIOS.keys())[0]


def _payload_for(scenario_name: str) -> dict:
    scenario = SCENARIOS[scenario_name]
    labels = {"service": scenario["service"]}
    labels.update(scenario.get("webhook_labels") or {})
    return {
        "alerts": [
            {
                "status": "firing",
                "labels": labels,
                "annotations": {"summary": scenario["description"]},
            }
        ]
    }


@pytest.fixture()
def client(tmp_path):
    cfg = AutoSREConfig(db_path=str(tmp_path / "wh.db"), port=8080, webhook_token="")
    app = create_app(cfg)
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def authed_client(tmp_path):
    cfg = AutoSREConfig(
        db_path=str(tmp_path / "wh-auth.db"),
        port=8080,
        webhook_token="test-secret-token",
    )
    app = create_app(cfg)
    with TestClient(app) as c:
        yield c


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_incidents_empty(client):
    resp = client.get("/incidents")
    assert resp.status_code == 200
    assert resp.json()["incidents"] == []


def test_alertmanager_accepts_known_scenario(client, monkeypatch):
    monkeypatch.setattr("autosre.agent.run_agent", lambda *a, **k: 0)
    name = _sample_scenario_name()
    resp = client.post("/webhook/alertmanager", json=_payload_for(name))
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "accepted"
    assert body["scenario"] == name
    assert "trace_id" in body


def test_alertmanager_rejects_unknown(client):
    resp = client.post(
        "/webhook/alertmanager",
        json={"alerts": [{"labels": {"service": "unknown-svc"}, "annotations": {}}]},
    )
    assert resp.status_code == 422


def test_map_uses_catalog_service():
    name = _sample_scenario_name()
    assert _map_alertmanager_to_scenario(_payload_for(name)) == name


def test_busy_queue_returns_429(client):
    client.app.state.busy = True
    name = _sample_scenario_name()
    resp = client.post("/webhook/alertmanager", json=_payload_for(name))
    assert resp.status_code == 429
    assert resp.json()["status"] == "busy"


def test_webhook_requires_bearer_when_configured(authed_client):
    name = _sample_scenario_name()
    payload = _payload_for(name)
    denied = authed_client.post("/webhook/alertmanager", json=payload)
    assert denied.status_code == 401

    bad = authed_client.post(
        "/webhook/alertmanager",
        json=payload,
        headers={"Authorization": "Bearer wrong"},
    )
    assert bad.status_code == 401


def test_webhook_accepts_valid_bearer(authed_client, monkeypatch):
    monkeypatch.setattr("autosre.agent.run_agent", lambda *a, **k: 0)
    name = _sample_scenario_name()
    resp = authed_client.post(
        "/webhook/alertmanager",
        json=_payload_for(name),
        headers={"Authorization": "Bearer test-secret-token"},
    )
    assert resp.status_code == 202


def test_get_incident(client, tmp_path):
    store = client.app.state.store
    name = _sample_scenario_name()
    scenario = SCENARIOS[name]
    iid = store.save_incident(
        alert_id=scenario["alert_id"],
        service=scenario["service"],
        scenario=name,
        status="resolved",
    )
    resp = client.get(f"/incidents/{iid}")
    assert resp.status_code == 200
    assert resp.json()["incident"]["alert_id"] == scenario["alert_id"]

    missing = client.get("/incidents/999999")
    assert missing.status_code == 404
