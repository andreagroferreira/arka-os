#!/usr/bin/env bash
# ============================================================================
# ArkaOS — Model-routing gateway ensure
#
# Renders the LiteLLM proxy config from ~/.arkaos/models.yaml, ensures the
# proxy is running, and writes the Claude Code launch env to a file the
# caller sources. Best-effort: any failure returns non-zero so arka-claude
# degrades to a plain `claude` launch — a broken gateway never blocks work.
#
# Contract:
#   in : $ARKA_PY (interpreter), $ARKAOS_ROOT (repo), env ARKA_GATEWAY_PORT
#   out: writes $ARKAOS_HOME/gateway/launch.env on success; exit 0
#        exit non-zero on any failure (caller must degrade)
# ============================================================================
set -uo pipefail

ARKAOS_HOME="${ARKAOS_HOME:-$HOME/.arkaos}"
PORT="${ARKA_GATEWAY_PORT:-4000}"
GW_DIR="$ARKAOS_HOME/gateway"
CONFIG="$GW_DIR/config.yaml"
ENV_FILE="$GW_DIR/launch.env"
LOG="$GW_DIR/litellm.log"
LITELLM="$ARKAOS_HOME/venv/bin/litellm"

warn() { printf '  \033[1;33m⚠  gateway: %s\033[0m\n' "$1" >&2; }

# ─── Preconditions ────────────────────────────────────────────────────────
[ -n "${ARKA_PY:-}" ] || { warn "ARKA_PY unset"; exit 1; }
[ -n "${ARKAOS_ROOT:-}" ] || { warn "ARKAOS_ROOT unset"; exit 1; }
if [ ! -x "$LITELLM" ]; then
  warn "LiteLLM not installed in the ArkaOS venv — run: ~/.arkaos/venv/bin/pip install 'litellm[proxy]'"
  exit 1
fi

# Mode: with an API key -> mixed (quality→Anthropic, execution→Ollama).
# Without one (subscription users) -> local-only: every route runs on the
# local Ollama model, keyless. The main arka-claude keeps the subscription.
LOCAL_FLAG=""
if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  LOCAL_FLAG="--local"
  warn "no ANTHROPIC_API_KEY — local-only mode: the whole session runs on the local Ollama model (use plain arka-claude for subscription/quality work)"
fi

mkdir -p "$GW_DIR"
health() { curl -fsS -m 2 "http://127.0.0.1:$PORT/health/liveliness" >/dev/null 2>&1; }

# ─── Reuse a healthy proxy WITHOUT rotating its key ───────────────────────
# The running proxy validates the ARKA_GATEWAY_KEY it started with; the
# client reads that same value from the existing launch.env. Minting a new
# key on reuse would 401 every request, so the reuse path touches neither
# the key nor launch.env. Changing models.yaml needs ARKA_GATEWAY_RESTART=1.
if [ "${ARKA_GATEWAY_RESTART:-0}" != "1" ] && health && [ -f "$ENV_FILE" ]; then
  exit 0
fi
if health; then                      # RESTART path — old proxy must go
  pkill -f "litellm .*--port $PORT" 2>/dev/null || true
  sleep 1
fi

# ─── Render config from models.yaml ───────────────────────────────────────
# shellcheck disable=SC2086  # LOCAL_FLAG is a single controlled token
if ! PYTHONPATH="$ARKAOS_ROOT" "$ARKA_PY" -m core.runtime.gateway $LOCAL_FLAG > "$CONFIG" 2>/dev/null; then
  warn "could not render gateway config (local-only needs at least one ollama route in models.yaml)"
  exit 1
fi

# ─── Fresh master key + client launch env (created for THIS proxy) ────────
MASTER_KEY="$("$ARKA_PY" -c 'import secrets; print("sk-arka-" + secrets.token_hex(16))')"
export ARKA_GATEWAY_KEY="$MASTER_KEY"

if ! PYTHONPATH="$ARKAOS_ROOT" "$ARKA_PY" -m core.runtime.gateway --env "$MASTER_KEY" > "$ENV_FILE" 2>/dev/null; then
  warn "could not render launch env"
  exit 1
fi
# The proxy reads ANTHROPIC_API_KEY + ARKA_GATEWAY_KEY from its own env.
printf 'ARKA_GATEWAY_KEY=%s\n' "$MASTER_KEY" >> "$ENV_FILE"
chmod 600 "$ENV_FILE" 2>/dev/null || true   # bearer token — owner-only

# Start in the background; ARKA_GATEWAY_KEY + ANTHROPIC_API_KEY inherited.
( ARKA_GATEWAY_KEY="$MASTER_KEY" nohup "$LITELLM" --config "$CONFIG" --port "$PORT" \
    >> "$LOG" 2>&1 & disown 2>/dev/null || true )

# ─── Health-wait (bounded) ────────────────────────────────────────────────
for _ in $(seq 1 30); do
  if health; then exit 0; fi
  sleep 1
done
warn "gateway did not become healthy within 30s (see $LOG)"
exit 1
