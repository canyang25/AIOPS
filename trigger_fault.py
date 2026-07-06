"""Trigger a fault scenario against the AIOps agent.

Sends a fault alert to a Dify Workflow app, which then autonomously queries
metrics/logs, diagnoses a root cause, runs a remediation playbook, and writes
an incident report.

Configuration comes from environment variables (see .env.example):
    DIFY_API_BASE           e.g. http://localhost/v1
    DIFY_WORKFLOW_API_KEY   your Dify workflow app key (starts with "app-")

Usage:
    python trigger_fault.py db                 # send the DB scenario to Dify
    python trigger_fault.py disk --simulate    # offline walkthrough, no server
    python trigger_fault.py --list             # list available scenarios
"""

import argparse
import os
import sys

import requests

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # dotenv is optional; env vars still work without it.
    pass


DIFY_API_BASE = os.getenv("DIFY_API_BASE", "http://localhost/v1")
DIFY_WORKFLOW_API_KEY = os.getenv("DIFY_WORKFLOW_API_KEY", "")
WORKFLOW_URL = f"{DIFY_API_BASE.rstrip('/')}/workflows/run"

SCENARIOS = {
    "db": {
        "alert_id": "ALERT-DB-001",
        "service": "order-service",
        "severity": "critical",
        "description": "Order API latency increased from 200ms to 1.5s, user complaints rising.",
        "timestamp": "2025-06-04T14:00:00Z",
        "metrics": "response_time, db_connections",
        "expected_root_cause": "Database connection pool misconfiguration",
        "expected_remediation": "restore_db_pool.yml (max_connections 50 -> 200)",
    },
    "disk": {
        "alert_id": "ALERT-DISK-001",
        "service": "file-service",
        "severity": "high",
        "description": "/data partition usage reached 98%, service unavailable.",
        "timestamp": "2025-06-04T10:30:00Z",
        "metrics": "disk_usage, io_wait",
        "expected_root_cause": "Disk space exhausted",
        "expected_remediation": "clean_disk_space.yml (free ~15GB of temp files)",
    },
    "network": {
        "alert_id": "ALERT-NET-001",
        "service": "payment-service",
        "severity": "critical",
        "description": "Payment service network abnormal, failure rate increased.",
        "timestamp": "2025-06-04T16:45:00Z",
        "metrics": "packet_loss, latency",
        "expected_root_cause": "Network partition fault",
        "expected_remediation": "restart_service.yml (restart payment-service)",
    },
}


def send_to_dify(scenario_name: str) -> int:
    """Send the scenario to the Dify Workflow API and print the result."""
    scenario = SCENARIOS[scenario_name]

    if not DIFY_WORKFLOW_API_KEY:
        print("Error: DIFY_WORKFLOW_API_KEY is not set.")
        print("Copy .env.example to .env and add your key, or run with --simulate.")
        return 1

    payload = {
        "inputs": scenario,
        "response_mode": "blocking",
        "user": f"aiops-{scenario_name}",
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DIFY_WORKFLOW_API_KEY}",
    }

    print(f"Triggering fault scenario '{scenario_name}' -> {WORKFLOW_URL}")
    print(f"  {scenario['description']}\n")

    try:
        response = requests.post(WORKFLOW_URL, json=payload, headers=headers, timeout=60)
    except requests.RequestException as exc:
        print(f"Request failed: {exc}")
        return 1

    if response.status_code != 200:
        print(f"Workflow call failed (HTTP {response.status_code}):")
        print(response.text)
        return 1

    try:
        result = response.json()
    except ValueError:
        print("Response was not valid JSON:")
        print(response.text)
        return 1

    print(f"Workflow Run ID: {result.get('workflow_run_id', 'N/A')}")
    outputs = (result.get("data") or {}).get("outputs") or {}
    print("\n=== Agent output ===")
    print(outputs)
    return 0


def simulate(scenario_name: str) -> int:
    """Print the closed-loop the agent runs, without contacting any server."""
    scenario = SCENARIOS[scenario_name]

    print(f"[SIMULATED] Fault scenario: {scenario_name}")
    print(f"  Alert:   {scenario['alert_id']} ({scenario['severity']})")
    print(f"  Service: {scenario['service']}")
    print(f"  Symptom: {scenario['description']}\n")

    steps = [
        f"Query metrics from Prometheus  -> {scenario['service']}: {scenario['metrics']}",
        f"Retrieve logs from ELK         -> scanning for ERROR/WARN on {scenario['service']}",
        f"Diagnose root cause (LLM)      -> {scenario['expected_root_cause']}",
        f"Execute remediation (Ansible)  -> {scenario['expected_remediation']}",
        "Generate incident report        -> summary + timeline + resolution",
    ]
    for i, step in enumerate(steps, 1):
        print(f"  {i}. {step}")

    print("\nRun the real loop by pointing DIFY_* env vars at a live Dify workflow.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("scenario", nargs="?", choices=sorted(SCENARIOS), help="fault scenario to trigger")
    parser.add_argument("--simulate", action="store_true", help="print the agent loop offline (no server needed)")
    parser.add_argument("--list", action="store_true", help="list available scenarios and exit")
    args = parser.parse_args()

    if args.list:
        print("Available scenarios:")
        for name, s in SCENARIOS.items():
            print(f"  {name:8} {s['service']:16} {s['description']}")
        return 0

    if not args.scenario:
        parser.print_help()
        return 1

    return simulate(args.scenario) if args.simulate else send_to_dify(args.scenario)


if __name__ == "__main__":
    sys.exit(main())
