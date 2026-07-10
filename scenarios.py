"""Scenario catalog for AutoSRE.

Single source of truth for fault scenarios.  Both ``agent.py`` and
``trigger_fault.py`` import from here so there is no duplication.

Scenarios are loaded from ``scenarios.json`` in the project root.  If the
file is missing the module raises ``FileNotFoundError`` — we deliberately
do not ship hardcoded fallback data so the JSON file remains the sole
source of truth.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_SCENARIOS_PATH = Path(__file__).resolve().parent / "scenarios.json"


def _load_scenarios() -> dict:
    """Load scenarios from scenarios.json.

    ``timestamp_offset_minutes`` is converted to a dynamic ISO 8601
    timestamp relative to *now*.  If absent, a fixed ``timestamp`` field
    is used as-is.
    """
    if not _SCENARIOS_PATH.is_file():
        raise FileNotFoundError(
            f"scenarios.json not found at {_SCENARIOS_PATH}. "
            "This file is required — it defines the fault scenarios."
        )

    with open(_SCENARIOS_PATH, "r", encoding="utf-8") as fh:
        raw: dict = json.load(fh)

    now = datetime.now(timezone.utc)
    scenarios: dict = {}
    for name, data in raw.items():
        scenario = dict(data)  # shallow copy so we don't mutate the parsed JSON
        offset = scenario.pop("timestamp_offset_minutes", None)
        if offset is not None:
            ts = now + timedelta(minutes=offset)
            scenario["timestamp"] = ts.strftime("%Y-%m-%dT%H:%M:%SZ")
        elif "timestamp" not in scenario:
            scenario["timestamp"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        scenarios[name] = scenario

    logger.info("Loaded %d scenario(s) from %s.", len(scenarios), _SCENARIOS_PATH)
    return scenarios


# Module-level scenarios dict — ``from scenarios import SCENARIOS`` works.
SCENARIOS = _load_scenarios()
