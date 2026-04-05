#!/usr/bin/env bash
# ArkaOS Dashboard — Start FastAPI + Nuxt servers
set -euo pipefail

ARKAOS_ROOT="${ARKAOS_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
DASHBOARD_DIR="${ARKAOS_ROOT}/dashboard"
PID_FILE="$HOME/.arkaos/dashboard.pid"
API_PORT="${ARKAOS_DASHBOARD_API_PORT:-3334}"
UI_PORT="${ARKAOS_DASHBOARD_UI_PORT:-3333}"

mkdir -p "$HOME/.arkaos"

# Check if already running
if [ -f "$PID_FILE" ]; then
  api_pid=$(head -1 "$PID_FILE" 2>/dev/null || echo "")
  ui_pid=$(tail -1 "$PID_FILE" 2>/dev/null || echo "")
  if [ -n "$api_pid" ] && kill -0 "$api_pid" 2>/dev/null; then
    echo "Dashboard already running (API PID: $api_pid, UI PID: $ui_pid)"
    echo "  API: http://localhost:${API_PORT}"
    echo "  UI:  http://localhost:${UI_PORT}"
    exit 0
  fi
  rm -f "$PID_FILE"
fi

# Start FastAPI backend
echo "Starting API server on :${API_PORT}..."
ARKAOS_ROOT="$ARKAOS_ROOT" python3 "${ARKAOS_ROOT}/scripts/dashboard-api.py" --port "$API_PORT" &
API_PID=$!

# Check if Nuxt is built
if [ -d "${DASHBOARD_DIR}/.output" ]; then
  echo "Starting dashboard on :${UI_PORT}..."
  PORT="$UI_PORT" node "${DASHBOARD_DIR}/.output/server/index.mjs" &
  UI_PID=$!
elif [ -d "${DASHBOARD_DIR}/node_modules" ]; then
  echo "Starting dashboard (dev mode) on :${UI_PORT}..."
  cd "$DASHBOARD_DIR" && npx nuxt dev --port "$UI_PORT" &
  UI_PID=$!
else
  echo "Dashboard not built. Run: cd dashboard && npm install && npm run build"
  UI_PID=""
fi

# Save PIDs
echo "$API_PID" > "$PID_FILE"
[ -n "${UI_PID:-}" ] && echo "$UI_PID" >> "$PID_FILE"

echo ""
echo "ArkaOS Dashboard running:"
echo "  API: http://localhost:${API_PORT}/api/overview"
[ -n "${UI_PID:-}" ] && echo "  UI:  http://localhost:${UI_PORT}"
echo ""
echo "Stop with: kill \$(cat $PID_FILE)"
