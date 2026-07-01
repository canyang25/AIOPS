import requests
import sys
import time


# 根据你的部署情况修改：如果 Dify 实际是在 80 端口，就用 http://121.199.78.214/v1
API_BASE = "http://121.199.78.214/v1"
WORKFLOW_URL = f"{API_BASE}/workflows/run"

# TODO: 替换成你在 Dify Workflow 应用里生成的 API Key
#WORKFLOW_API_KEY = "dify_xxx_your_workflow_api_key"
WORKFLOW_API_KEY = "app-2Ui14Uo2tUkrGnZLVAlDsl5A"

def trigger_fault_scenario(scenario_name: str) -> None:
    """通过调用 Dify Workflow API 触发故障场景"""

    scenarios = {
        "db": {
            "alert_id": "ALERT-DB-001",
            "service": "order-service",
            "severity": "critical",
            "description": "Order API latency increased from 200ms to 1.5s, user complaints rising.",
            "timestamp": "2025-06-04T14:00:00Z",
            "metrics": "response_time, db_connections",
            "expected_root_cause": "Database connection pool misconfiguration",
        },
        "disk": {
            "alert_id": "ALERT-DISK-001",
            "service": "file-service",
            "severity": "high",
            "description": "/data partition usage reached 98%, service unavailable.",
            "timestamp": "2025-06-04T10:30:00Z",
            "metrics": "disk_usage, io_wait",
            "expected_root_cause": "Disk space exhausted",
        },
        "network": {
            "alert_id": "ALERT-NET-001",
            "service": "payment-service",
            "severity": "critical",
            "description": "Payment service network abnormal, failure rate increased.",
            "timestamp": "2025-06-04T16:45:00Z",
            "metrics": "packet_loss, latency",
            "expected_root_cause": "Network partition fault",
        },
    }

    if scenario_name not in scenarios:
        print(f"Unknown scenario '{scenario_name}'. Available: {list(scenarios.keys())}")
        return

    scenario = scenarios[scenario_name]

    print(f"Triggering fault scenario: {scenario_name}")
    print(f"Description: {scenario['description']}")

    # Dify Workflow API 请求体：inputs 对应你在应用里定义的输入变量
    payload = {
        "inputs": scenario,            # 这里的 key 与上面 scenarios 的字段保持一致
        "response_mode": "blocking",   # 阻塞模式：直接等结果
        "user": f"aiops-{scenario_name}",
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {WORKFLOW_API_KEY}",
    }

    try:
        response = requests.post(WORKFLOW_URL, json=payload, headers=headers, timeout=60)
    except Exception as exc:
        print(f"Request error: {exc}")
        return

    if response.status_code == 200:
        try:
            result = response.json()
        except ValueError:
            print("Response is not valid JSON:")
            print(response.text)
            return

        workflow_run_id = result.get("workflow_run_id", "N/A")
        print("Dify workflow started, processing...")
        print(f"Workflow Run ID: {workflow_run_id}")

        # Workflow API 的 outputs 在 result["data"]["outputs"] 里
        outputs = (result.get("data") or {}).get("outputs") or {}
        print("\n=== Workflow outputs (诊断结果) ===")
        print(outputs)

        print("\nExpected analysis flow:")
        print(f" 1. Query metrics for service {scenario['service']} ({scenario['metrics']})")
        print(" 2. Retrieve related error logs")
        print(f" 3. Analyze root cause (model output)")
        print(" 4. (Optional) Execute automated repair via execute_repair tool")
        print(" 5. Generate incident report")
    else:
        print(f"Workflow call failed with status code: {response.status_code}")
        print(f"Response body: {response.text}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python trigger_fault.py [db|disk|network]")
        sys.exit(1)

    trigger_fault_scenario(sys.argv[1])


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

