#!/usr/bin/env bash
# ArkaOS Dashboard — Start FastAPI + Nuxt servers with dynamic ports
set -euo pipefail

ARKAOS_ROOT="${ARKAOS_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
DASHBOARD_DIR="${ARKAOS_ROOT}/dashboard"
PID_FILE="$HOME/.arkaos/dashboard.pid"
PORT_FILE="$HOME/.arkaos/dashboard.ports"

mkdir -p "$HOME/.arkaos"

# ── Kill existing if running ──
if [ -f "$PID_FILE" ]; then
  while read -r pid; do
    kill "$pid" 2>/dev/null || true
  done < "$PID_FILE"
  rm -f "$PID_FILE" "$PORT_FILE"
  sleep 1
fi

# ── Find available ports ──
find_port() {
  local port=$1
  while lsof -i :"$port" >/dev/null 2>&1; do
    port=$((port + 1))
  done
  echo "$port"
}

# UI first (lower port), API second (higher port) — ensures they don't collide
UI_PORT=$(find_port "${ARKAOS_DASHBOARD_UI_PORT:-3333}")
API_PORT=$(find_port "${ARKAOS_DASHBOARD_API_PORT:-$((UI_PORT + 1))}")

echo ""
echo "  ArkaOS Dashboard"
echo "  ─────────────────"

# ── Start FastAPI backend ──
API_LOG="$HOME/.arkaos/api.log"
echo "  Starting API on :${API_PORT}..."
ARKAOS_ROOT="$ARKAOS_ROOT" python3 "${ARKAOS_ROOT}/scripts/dashboard-api.py" --port "$API_PORT" > "$API_LOG" 2>&1 &
API_PID=$!

# Wait for API with health check (up to 10 seconds)
API_READY=false
for i in $(seq 1 20); do
  sleep 0.5
  if ! kill -0 "$API_PID" 2>/dev/null; then
    break
  fi
  if curl -s "http://localhost:${API_PORT}/api/overview" >/dev/null 2>&1; then
    API_READY=true
    break
  fi
done

if [ "$API_READY" = true ]; then
  echo "  ✓ API: http://localhost:${API_PORT}"
else
  echo "  ⚠ API may still be starting (check log: $API_LOG)"
  if [ -f "$API_LOG" ]; then
    echo "  Last error: $(tail -3 "$API_LOG" | head -1)"
  fi
  # Don't exit — API might still be loading, continue with dashboard
fi

# ── Start Nuxt frontend ──
UI_PID=""
if [ -d "${DASHBOARD_DIR}/.output" ]; then
  echo "  Starting UI on :${UI_PORT}..."
  PORT="$UI_PORT" NUXT_PUBLIC_API_BASE="http://localhost:${API_PORT}" node "${DASHBOARD_DIR}/.output/server/index.mjs" >/dev/null 2>&1 &
  UI_PID=$!
elif [ -d "${DASHBOARD_DIR}/node_modules" ]; then
  echo "  Starting UI (dev) on :${UI_PORT}..."
  cd "$DASHBOARD_DIR" && NUXT_PUBLIC_API_BASE="http://localhost:${API_PORT}" npx nuxt dev --port "$UI_PORT" >/dev/null 2>&1 &
  UI_PID=$!
  cd "$ARKAOS_ROOT"
else
  # Auto-install and start
  echo "  Installing dashboard dependencies..."
  if command -v pnpm >/dev/null 2>&1; then
    (cd "$DASHBOARD_DIR" && pnpm install --silent 2>/dev/null)
  else
    (cd "$DASHBOARD_DIR" && npm install --silent 2>/dev/null)
  fi

  if [ -d "${DASHBOARD_DIR}/node_modules" ]; then
    echo "  Starting UI (dev) on :${UI_PORT}..."
    cd "$DASHBOARD_DIR" && NUXT_PUBLIC_API_BASE="http://localhost:${API_PORT}" npx nuxt dev --port "$UI_PORT" >/dev/null 2>&1 &
    UI_PID=$!
    cd "$ARKAOS_ROOT"
  else
    echo "  ⚠ Dashboard install failed. API-only mode."
  fi
fi

# ── Save state ──
echo "$API_PID" > "$PID_FILE"
[ -n "$UI_PID" ] && echo "$UI_PID" >> "$PID_FILE"
echo "API_PORT=$API_PORT" > "$PORT_FILE"
echo "UI_PORT=$UI_PORT" >> "$PORT_FILE"

echo ""
echo "  ┌──────────────────────────────────────┐"
echo "  │  API: http://localhost:${API_PORT}          │"
[ -n "$UI_PID" ] && echo "  │  UI:  http://localhost:${UI_PORT}          │"
echo "  └──────────────────────────────────────┘"
echo ""
echo "  Stop: npx arkaos dashboard stop"
echo "        or kill \$(cat $PID_FILE)"
echo ""

# Wait for UI to be ready
if [ -n "$UI_PID" ]; then
  sleep 5
  # Open browser
  if command -v open >/dev/null 2>&1; then
    open "http://localhost:${UI_PORT}" 2>/dev/null || true
  fi
fi
