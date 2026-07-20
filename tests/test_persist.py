"""Persist failed / timeout incident rows."""

from unittest.mock import patch

from scenarios import SCENARIOS
from autosre.agent import run_agent
from autosre.store import IncidentStore


def test_persist_failed_backend(tmp_path, monkeypatch):
    name = sorted(SCENARIOS.keys())[0]
    scenario = SCENARIOS[name]
    db = tmp_path / "fail.db"
    monkeypatch.setenv("AUTOSRE_DB_PATH", str(db))
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    monkeypatch.delenv("LLM_FALLBACK_CHAIN", raising=False)

    with patch(
        "autosre.agent.resolve_backend",
        return_value={
            "kind": "openai",
            "provider": "groq",
            "base_url": "http://llm.test/v1",
            "api_key": "x",
            "model": "m",
        },
    ):
        with patch(
            "autosre.agent._run_openai_compatible",
            side_effect=RuntimeError("boom"),
        ):
            try:
                run_agent(name, fallback=False)
            except RuntimeError:
                pass

    store = IncidentStore(str(db))
    rows = store.get_history(alert_id=scenario["alert_id"])
    assert rows
    assert rows[0]["status"] == "failed"
    assert "boom" in (rows[0]["metadata"] or {}).get("error", "")


def test_persist_empty_report_as_failed(tmp_path, monkeypatch):
    name = sorted(SCENARIOS.keys())[0]
    scenario = SCENARIOS[name]
    db = tmp_path / "empty.db"
    monkeypatch.setenv("AUTOSRE_DB_PATH", str(db))

    with patch(
        "autosre.agent.resolve_backend",
        return_value={
            "kind": "openai",
            "provider": "groq",
            "base_url": "http://llm.test/v1",
            "api_key": "x",
            "model": "m",
        },
    ):
        with patch("autosre.agent._run_openai_compatible", return_value=""):
            code = run_agent(name, fallback=False)

    assert code == 1
    store = IncidentStore(str(db))
    rows = store.get_history(alert_id=scenario["alert_id"])
    assert rows
    assert rows[0]["status"] in {"failed", "timeout"}
