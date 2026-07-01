import requests
import sys
import time


def trigger_fault_scenario(scenario_name: str) -> None:
    """Trigger a fault scenario by sending an alert to Dify webhook."""

    scenarios = {
        "db": {
            "alert_id": "ALERT-DB-001",
            "service": "order-service",
            "severity": "critical",
            "description": "Order API latency increased from 200ms to 1.5s, user complaints rising.",
            "timestamp": "2025-06-04T14:00:00Z",
            "metrics": ["response_time", "db_connections"],
            "expected_root_cause": "Database connection pool misconfiguration",
        },
        "disk": {
            "alert_id": "ALERT-DISK-001",
            "service": "file-service",
            "severity": "high",
            "description": "/data partition usage reached 98%, service unavailable.",
            "timestamp": "2025-06-04T10:30:00Z",
            "metrics": ["disk_usage", "io_wait"],
            "expected_root_cause": "Disk space exhausted",
        },
        "network": {
            "alert_id": "ALERT-NET-001",
            "service": "payment-service",
            "severity": "critical",
            "description": "Payment service network abnormal, failure rate increased.",
            "timestamp": "2025-06-04T16:45:00Z",
            "metrics": ["packet_loss", "latency"],
            "expected_root_cause": "Network partition fault",
        },
    }

    if scenario_name not in scenarios:
        print(f"Unknown scenario '{scenario_name}'. Available: {list(scenarios.keys())}")
        return

    scenario = scenarios[scenario_name]

    # Dify webhook on your ECS (public IP 121.199.78.214)
    webhook_url = "http://121.199.78.214:8080/api/webhook/fault"

    print(f"Triggering fault scenario: {scenario_name}")
    print(f"Description: {scenario['description']}")

    try:
        response = requests.post(webhook_url, json=scenario, timeout=30)
    except Exception as exc:
        print(f"Request error: {exc}")
        return

    if response.status_code == 200:
        try:
            result = response.json()
        except ValueError:
            result = {}
        print("Dify agent received alert, processing...")
        tracking_id = result.get("tracking_id", "N/A")
        print(f"Tracking ID: {tracking_id}")

        # Simple wait for processing (demo only)
        time.sleep(5)

        print("\nExpected analysis flow:")
        print(f" 1. Query metrics for service {scenario['service']} ({scenario['metrics']})")
        print(" 2. Retrieve related error logs")
        print(f" 3. Analyze root cause: {scenario['expected_root_cause']}")
        print(" 4. Execute automated repair via Ansible mock")
        print(" 5. Generate incident report")
    else:
        print(f"Webhook call failed with status code: {response.status_code}")
        print(f"Response body: {response.text}")


def manual_test() -> None:
    """Manual dialog style test (simulated)."""
    print("\nManual dialog test mode")
    print("Enter a fault description, the AIOps agent will diagnose (simulated).")
    print("Example: 'Order service is slow, please analyze.'")
    print("Enter 'quit' to exit.\n")

    while True:
        user_input = input("You: ").strip()
        if not user_input:
            continue
        if user_input.lower() == "quit":
            break

        print("AIOps Agent: Analyzing your description...")
        print("  [Tool] Querying order-service metrics...")
        print("  [Tool] Retrieving related logs...")
        print("  [Analysis] Detected DB connection pool anomaly...")
        print("  [Action] Rolling back connection pool configuration...")
        print("  Done. Latency back to normal.")
        print("  Report: root cause - database connection pool misconfiguration.")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "manual":
            manual_test()
        else:
            trigger_fault_scenario(sys.argv[1])
    else:
        print("Usage:")
        print("  python trigger_fault.py db       # database fault")
        print("  python trigger_fault.py disk     # disk fault")
        print("  python trigger_fault.py network  # network fault")
        print("  python trigger_fault.py manual   # dialog test")

