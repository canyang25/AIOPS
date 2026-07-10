"""Mock Ansible Tower service for AIOPS.

Accepts playbook execution requests and returns simulated results.  Playbook
definitions are loaded from ``fixtures/playbooks.json``; if the file is missing
the built-in defaults are used.

Phase-3 state-aware behaviour:
  After a successful playbook run whose definition contains a ``remediates``
  field, the mock notifies the Prometheus and ELK mocks so that subsequent
  metric/log queries reflect the remediation.

Additional endpoints:
  GET  /api/v1/playbooks  – return the playbook catalogue
"""

from flask import Flask, request, jsonify
import json
import logging
import os
import time

import requests as http_requests  # renamed to avoid shadowing flask.request

logger = logging.getLogger(__name__)

app = Flask(__name__)
execution_logs: list = []

# ---------------------------------------------------------------------------
# Configuration (via environment variables)
# ---------------------------------------------------------------------------
PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL", "http://localhost:9091")
ELK_URL = os.environ.get("ELK_URL", "http://localhost:9093")

def _load_playbooks():
    """Load playbook definitions from the fixture file."""
    fixture_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "fixtures", "playbooks.json"
    )
    if not os.path.exists(fixture_path):
        raise FileNotFoundError(f"Fixture file {fixture_path} not found")
    with open(fixture_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
        logger.info("Loaded playbook definitions from %s", fixture_path)
        return data


# Playbook catalogue (loaded once at startup)
_playbooks: dict = _load_playbooks()


def _match_playbook(raw_name: str) -> str:
    """Fuzzy-match the caller's playbook name against registered keywords.

    Iterates over all playbook definitions and returns the first whose
    ``match_keywords`` list contains at least one token present in *raw_name*.
    Returns ``"unknown"`` when no playbook matches.
    """
    for playbook_name, definition in _playbooks.items():
        keywords = definition.get("match_keywords", [])
        for kw in keywords:
            if kw in raw_name:
                return playbook_name
    return "unknown"


def _notify_remediation(playbook_name: str, remediation: dict):
    """Best-effort POST to Prometheus and ELK mocks after a successful remediation."""
    service = remediation.get("service")
    metrics_override = remediation.get("metrics", {})

    # Notify Prometheus mock with new metric ranges
    try:
        resp = http_requests.post(
            f"{PROMETHEUS_URL}/api/v1/remediated",
            json={"service": service, "metrics": metrics_override},
            timeout=3,
        )
        logger.info(
            "Notified Prometheus for remediation (%s): status %s",
            service,
            resp.status_code,
        )
    except Exception:
        logger.warning(
            "Failed to notify Prometheus mock at %s (best-effort, continuing)",
            PROMETHEUS_URL,
            exc_info=True,
        )

    # Inject a recovery log entry into the ELK mock
    try:
        log_entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "level": "INFO",
            "message": f"Service recovered after remediation: {playbook_name}",
        }
        resp = http_requests.post(
            f"{ELK_URL}/_inject",
            json={"service": service, "log": log_entry},
            timeout=3,
        )
        logger.info(
            "Injected recovery log into ELK for service '%s': status %s",
            service,
            resp.status_code,
        )
    except Exception:
        logger.warning(
            "Failed to inject log into ELK mock at %s (best-effort, continuing)",
            ELK_URL,
            exc_info=True,
        )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/health", methods=["GET"], strict_slashes=False)
def health():
    return jsonify({"status": "ok", "service": "mock-ansible"})

@app.route("/api/v1/execute", methods=["GET", "POST", "PUT"], strict_slashes=False)
def execute_playbook():
    """Execute a playbook by fuzzy-matching the caller's intent."""
    logger.debug("Ansible received request – path: %s", request.path)

    # Generously extract data regardless of content type
    data: dict = {}
    if request.is_json:
        data = request.get_json(force=True, silent=True) or {}
    else:
        data = request.form.to_dict() or request.args.to_dict()

    # Extract the playbook name provided by the caller (lowered for matching)
    playbook_raw = str(data.get("playbook", "")).lower()
    hosts = data.get("hosts", ["localhost"])

    logger.debug("Caller requested playbook: %s", playbook_raw)

    # Fuzzy-match against registered playbook keywords
    playbook = _match_playbook(playbook_raw)

    log_entry = {
        "id": len(execution_logs) + 1,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "playbook": playbook,
        "raw_playbook_from_llm": playbook_raw,
        "hosts": hosts,
        "status": "executing",
    }
    execution_logs.append(log_entry)

    # Simulate execution latency
    time.sleep(float(os.environ.get('MOCK_LATENCY', '1')))

    if playbook == "unknown":
        result = {
            "status": "unknown",
            "message": f"Executed unknown playbook: {playbook_raw}",
        }
    else:
        result = _playbooks[playbook].get("result", {
            "status": "success",
            "message": f"Playbook {playbook} executed.",
        })

    log_entry["status"] = result.get("status", "unknown")
    log_entry["result"] = result

    # Phase 3: if remediation metadata exists and execution succeeded, notify mocks
    if result.get("status") == "success" and playbook != "unknown":
        remediation = _playbooks[playbook].get("remediates")
        if remediation:
            _notify_remediation(playbook, remediation)

    return jsonify(result)


@app.route("/api/v1/playbooks", methods=["GET"], strict_slashes=False)
def list_playbooks():
    """Return the playbook catalogue (name + description for each)."""
    catalogue = {
        name: {"description": defn.get("description", "")}
        for name, defn in _playbooks.items()
    }
    return jsonify({"status": "success", "playbooks": catalogue})


# Catch-all fallback route – intercepts unknown paths and delegates to execute
@app.route("/", defaults={"path": ""}, methods=["GET", "POST", "PUT"])
@app.route("/<path:path>", methods=["GET", "POST", "PUT"])
def catch_all(path=""):
    logger.warning("Catch-all route triggered – unexpected path: /%s", path)
    return execute_playbook()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    app.run(host="0.0.0.0", port=9092, debug=False)