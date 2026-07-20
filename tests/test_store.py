"""Tests for the SQLite incident store — values come from SCENARIOS."""

from scenarios import SCENARIOS
from autosre.store import IncidentStore


def _sample():
    name = sorted(SCENARIOS.keys())[0]
    return name, SCENARIOS[name]


def test_save_and_get_incident(tmp_path):
    name, scenario = _sample()
    db = tmp_path / "test.db"
    store = IncidentStore(str(db))

    incident_id = store.save_incident(
        alert_id=scenario["alert_id"],
        service=scenario["service"],
        scenario=name,
        severity=scenario.get("severity", ""),
        status="resolved",
        report_path="reports/test.md",
        report_text="# Incident\nRoot cause: pool",
        backend="groq",
        model="llama-3.3-70b-versatile",
        duration_ms=1234,
        metadata={"trace_id": "abc"},
    )

    assert isinstance(incident_id, int)
    assert incident_id >= 1

    row = store.get_incident(incident_id)
    assert row is not None
    assert row["alert_id"] == scenario["alert_id"]
    assert row["service"] == scenario["service"]
    assert row["scenario"] == name
    assert row["backend"] == "groq"
    assert row["metadata"]["trace_id"] == "abc"


def test_get_history_order_and_filter(tmp_path):
    names = sorted(SCENARIOS.keys())
    a_name, a = names[0], SCENARIOS[names[0]]
    b_name, b = names[1 % len(names)], SCENARIOS[names[1 % len(names)]]
    db = tmp_path / "hist.db"
    store = IncidentStore(str(db))

    store.save_incident(alert_id=a["alert_id"], scenario=a_name, service=a["service"])
    store.save_incident(alert_id=b["alert_id"], scenario=b_name, service=b["service"])
    store.save_incident(alert_id=a["alert_id"], scenario=a_name, service=a["service"])

    history = store.get_history(limit=10)
    assert len(history) == 3
    assert history[0]["id"] > history[1]["id"]

    filtered = store.get_history(alert_id=a["alert_id"])
    assert len(filtered) >= 1
    assert all(r["alert_id"] == a["alert_id"] for r in filtered)


def test_get_missing_incident(tmp_path):
    store = IncidentStore(str(tmp_path / "empty.db"))
    assert store.get_incident(999) is None


def test_module_helpers(tmp_path, monkeypatch):
    from autosre import store as store_mod

    name, scenario = _sample()
    db = str(tmp_path / "helpers.db")
    monkeypatch.setattr(store_mod, "_default_store", None)

    iid = store_mod.save_incident(
        alert_id=scenario["alert_id"], scenario=name, db_path=db
    )
    assert store_mod.get_incident(iid, db_path=db)["alert_id"] == scenario["alert_id"]
    assert len(store_mod.get_history(db_path=db)) == 1
