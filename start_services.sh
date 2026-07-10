#!/usr/bin/env bash
# Start the mock observability backends as local Python processes.
# No Docker required — just Python 3.10+ and Flask.
#
# Usage:
#   ./start_services.sh          # start all three mock services in the background
#   ./start_services.sh --stop   # stop all running mock services

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PIDS_DIR="$SCRIPT_DIR/.pids"
mkdir -p "$PIDS_DIR"

stop_services() {
    echo "Stopping mock services..."
    for pidfile in "$PIDS_DIR"/*.pid; do
        [ -f "$pidfile" ] || continue
        pid=$(cat "$pidfile")
        name=$(basename "$pidfile" .pid)
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" && echo "  ✓ Stopped $name (PID $pid)"
        else
            echo "  · $name already stopped"
        fi
        rm -f "$pidfile"
    done
}

if [ "${1:-}" = "--stop" ]; then
    stop_services
    exit 0
fi

# Stop any previously running instances first
stop_services 2>/dev/null || true

echo "Starting mock services..."
cd "$SCRIPT_DIR"

python3 tools/mock_prometheus.py > /dev/null 2>&1 &
echo $! > "$PIDS_DIR/mock_prometheus.pid"
echo "  ✓ Mock Prometheus  → http://localhost:9091  (PID $!)"

python3 tools/mock_elk.py > /dev/null 2>&1 &
echo $! > "$PIDS_DIR/mock_elk.pid"
echo "  ✓ Mock ELK         → http://localhost:9093  (PID $!)"

python3 tools/mock_ansible.py > /dev/null 2>&1 &
echo $! > "$PIDS_DIR/mock_ansible.pid"
echo "  ✓ Mock Ansible     → http://localhost:9092  (PID $!)"

# Wait briefly for services to bind
sleep 1

# Health check
OK=0
for port in 9091 9093 9092; do
    if curl -sf "http://localhost:$port" > /dev/null 2>&1; then
        OK=$((OK + 1))
    fi
done

if [ "$OK" -eq 3 ]; then
    echo ""
    echo "All services running. Run the agent with:"
    echo "  python3 agent.py db"
    echo ""
    echo "Stop services later with:"
    echo "  ./start_services.sh --stop"
else
    echo ""
    echo "⚠ Some services may not have started. Check that ports 9091-9093 are free."
fi
