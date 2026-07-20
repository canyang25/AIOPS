"""Integration tests – scenario loading and offline simulation.

These tests verify that the scenario catalog is well-formed and that the
``simulate()`` function from ``trigger_fault`` runs through successfully for
every defined scenario. Expected keys come from scenarios.json — never hardcoded.
"""

import json
from pathlib import Path

from trigger_fault import SCENARIOS, simulate

_SCENARIOS_PATH = Path(__file__).resolve().parents[1] / "scenarios.json"


class TestScenarioLoading:
    """Verify the SCENARIOS dict matches scenarios.json and required fields."""

    REQUIRED_FIELDS = {
        "alert_id",
        "service",
        "description",
        "expected_root_cause",
        "expected_remediation",
        "healthy_thresholds",
        "metrics",
    }

    def test_scenario_loading(self):
        raw = json.loads(_SCENARIOS_PATH.read_text(encoding="utf-8"))
        assert set(SCENARIOS.keys()) == set(raw.keys())
        assert len(SCENARIOS) >= 1

    def test_scenario_has_required_fields(self):
        for name, scenario in SCENARIOS.items():
            for field in self.REQUIRED_FIELDS:
                assert field in scenario, (
                    f"Scenario '{name}' is missing required field '{field}'"
                )
            # First metric in the hint must have a healthy threshold entry.
            first_metric = scenario["metrics"].split(",")[0].strip()
            assert first_metric in scenario["healthy_thresholds"]


class TestSimulation:
    """Verify simulate() completes without error for all scenarios."""

    def test_simulate_all_scenarios(self):
        for name in SCENARIOS:
            assert simulate(name) == 0, f"simulate('{name}') did not return 0"
