"""Tests for deterministic rollback against scenario healthy_thresholds."""

from unittest.mock import patch

from scenarios import SCENARIOS
from autosre.agent import _maybe_rollback, _metric_still_unhealthy
from autosre.config import AutoSREConfig


def _scenario_with_thresholds():
    for name, scenario in SCENARIOS.items():
        thresholds = scenario.get("healthy_thresholds") or {}
        if thresholds:
            return name, scenario
    raise AssertionError("no scenario with healthy_thresholds in catalog")


def test_metric_still_unhealthy_respects_max_and_min():
    assert _metric_still_unhealthy(90, {"max": 80}) is True
    assert _metric_still_unhealthy(70, {"max": 80}) is False
    assert _metric_still_unhealthy(5, {"min": 10}) is True
    assert _metric_still_unhealthy(15, {"min": 10}) is False


def test_rollback_skipped_when_healthy():
    _, scenario = _scenario_with_thresholds()
    metric = scenario["metrics"].split(",")[0].strip()
    threshold = scenario["healthy_thresholds"][metric]
    healthy_latest = float(threshold.get("max", 100)) - 1

    cfg = AutoSREConfig(rollback_playbook="rollback.yml")

    with patch(
        "autosre.tools._tool_query_metrics",
        return_value={
            "latest": healthy_latest,
            "avg": healthy_latest,
            "max": healthy_latest,
        },
    ):
        with patch("autosre.agent._dispatch") as dispatch:
            result = _maybe_rollback(scenario, cfg)

    assert result["rollback"] is False
    dispatch.assert_not_called()


def test_rollback_invoked_when_unhealthy():
    _, scenario = _scenario_with_thresholds()
    metric = scenario["metrics"].split(",")[0].strip()
    threshold = scenario["healthy_thresholds"][metric]
    unhealthy_latest = float(threshold.get("max", 0)) + 25

    cfg = AutoSREConfig(rollback_playbook="rollback.yml")

    with patch(
        "autosre.tools._tool_query_metrics",
        return_value={
            "latest": unhealthy_latest,
            "avg": unhealthy_latest,
            "max": unhealthy_latest,
        },
    ):
        with patch(
            "autosre.agent._dispatch",
            return_value={"status": "success"},
        ) as dispatch:
            result = _maybe_rollback(scenario, cfg)

    assert result["rollback"] is True
    assert result["playbook"] == "rollback.yml"
    dispatch.assert_called_once()
    args, _kwargs = dispatch.call_args
    assert args[0] == "run_playbook"
    assert args[1]["playbook"] == "rollback.yml"


def test_rollback_skipped_without_thresholds():
    _, scenario = _scenario_with_thresholds()
    bare = dict(scenario)
    bare.pop("healthy_thresholds", None)
    cfg = AutoSREConfig(rollback_playbook="rollback.yml")
    result = _maybe_rollback(bare, cfg)
    assert result["skipped"] is True
