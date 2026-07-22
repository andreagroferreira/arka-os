#!/usr/bin/env bash
# ============================================================================
# ArkaOS — background auto-update (Foundation PR-1)
#
# Invoked daily by the io.wizardingcode.arkaos.updater unit (see
# installer/autoupdate.js) or manually via `npx arkaos autoupdate run`.
#
# Flow: registry check (curl, short timeout) → compare with the installed
# version (~/.arkaos/install-manifest.json) → headless `npx -y
# arkaos@latest update` → OS notification with the outcome. Project sync
# stays supervised: update.js resets sync-state.json, so the next Claude
# session surfaces [arka:update-available] and /arka update runs there.
#
# Every failure path logs and exits 0 — a broken check must never surface
# as a crashing login item.
# ============================================================================
set -u

ARKA_HOME="${HOME}/.arkaos"
LOG_DIR="${ARKA_HOME}/logs"
LOG="${LOG_DIR}/auto-update.log"
LOCK_DIR="${ARKA_HOME}/auto-update.lock"
MANIFEST="${ARKA_HOME}/install-manifest.json"
OPTOUT="${ARKA_HOME}/autoupdate.optout"
PROFILE="${ARKA_HOME}/profile.json"
REGISTRY_URL="https://registry.npmjs.org/arkaos/latest"

FORCE=0
[ "${1:-}" = "--force" ] && FORCE=1

mkdir -p "$LOG_DIR"

log() {
  printf '%s %s\n' "$(date '+%Y-%m-%dT%H:%M:%S')" "$1" >> "$LOG"
}

# Keep the log bounded (~1MB cap, keep the newest half).
rotate_log() {
  local size
  size=$(wc -c < "$LOG" 2>/dev/null || echo 0)
  if [ "${size:-0}" -gt 1048576 ]; then
    tail -c 524288 "$LOG" > "${LOG}.tmp" && mv "${LOG}.tmp" "$LOG"
  fi
}

# JSON field reader: venv python → python3 → sed (last resort).
json_field() {
  local file="$1" field="$2"
  local py="${ARKA_HOME}/venv/bin/python"
  [ -x "$py" ] || py="$(command -v python3 || true)"
  if [ -n "$py" ]; then
    "$py" -c "import json,sys; print(json.load(open(sys.argv[1])).get(sys.argv[2],''))" \
      "$file" "$field" 2>/dev/null && return 0
  fi
  sed -n "s/.*\"${field}\"[[:space:]]*:[[:space:]]*\"\([^\"]*\)\".*/\1/p" "$file" 2>/dev/null | head -1
}

notify() {
  local msg="$1"
  log "notify: $msg"
  case "$(uname -s)" in
    Darwin)
      command -v osascript >/dev/null 2>&1 && \
        osascript -e "display notification \"${msg}\" with title \"ArkaOS\"" >/dev/null 2>&1
      ;;
    Linux)
      command -v notify-send >/dev/null 2>&1 && notify-send "ArkaOS" "$msg" >/dev/null 2>&1
      ;;
  esac
}

# Notification copy follows the installed profile language (pt → pt-PT).
LANG_CODE=""
[ -f "$PROFILE" ] && LANG_CODE="$(json_field "$PROFILE" language)"

msg_updated() {
  if [ "$LANG_CODE" = "pt" ]; then
    echo "Atualizado para v$1. Os projetos sincronizam na próxima sessão Claude."
  else
    echo "Updated to v$1. Projects sync on your next Claude session."
  fi
}
msg_failed() {
  if [ "$LANG_CODE" = "pt" ]; then
    echo "Falha no auto-update (v$1). Corre: npx arkaos@latest update"
  else
    echo "Auto-update failed (v$1). Run: npx arkaos@latest update"
  fi
}

rotate_log

# ── Opt-out and install guards ─────────────────────────────────────────
if [ -f "$OPTOUT" ]; then
  log "skip: user opt-out marker present"
  exit 0
fi
if [ ! -f "$MANIFEST" ]; then
  log "skip: no install-manifest.json — ArkaOS not installed"
  exit 0
fi

# ── Lock (mkdir is atomic); reclaim stale locks older than 2h ──────────
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  if [ -n "$(find "$LOCK_DIR" -maxdepth 0 -mmin +120 2>/dev/null)" ]; then
    log "reclaiming stale lock"
    rmdir "$LOCK_DIR" 2>/dev/null || true
    mkdir "$LOCK_DIR" 2>/dev/null || { log "skip: lock contention"; exit 0; }
  else
    log "skip: another auto-update run holds the lock"
    exit 0
  fi
fi
trap 'rmdir "$LOCK_DIR" 2>/dev/null' EXIT

# launchd/systemd environments miss the node toolchain locations; append
# (not prepend — explicit PATH entries, e.g. test stubs, must win).
export PATH="${PATH}:/opt/homebrew/bin:/usr/local/bin"

INSTALLED="$(json_field "$MANIFEST" version)"
if [ -z "$INSTALLED" ]; then
  log "skip: could not read installed version from manifest"
  exit 0
fi

if ! command -v curl >/dev/null 2>&1; then
  log "skip: curl unavailable"
  exit 0
fi
LATEST_JSON="$(curl -sf --max-time 15 "$REGISTRY_URL" 2>/dev/null || true)"
if [ -z "$LATEST_JSON" ]; then
  log "skip: registry unreachable (offline?)"
  exit 0
fi
TMP_JSON="${ARKA_HOME}/.autoupdate-latest.json"
printf '%s' "$LATEST_JSON" > "$TMP_JSON"
LATEST="$(json_field "$TMP_JSON" version)"
rm -f "$TMP_JSON"
if [ -z "$LATEST" ]; then
  log "skip: could not parse registry response"
  exit 0
fi

# Only ever move FORWARD: a dev/prerelease install newer than the
# registry `latest` must not be silently downgraded (QG, Francisca).
# Ordering compare via python; degraded fallback is plain inequality.
is_newer() { # is_newer LATEST INSTALLED → exit 0 when LATEST > INSTALLED
  local py="${ARKA_HOME}/venv/bin/python"
  [ -x "$py" ] || py="$(command -v python3 || true)"
  if [ -n "$py" ]; then
    "$py" -c '
import re, sys
def key(v):
    core = re.split(r"[-+]", v, maxsplit=1)[0]
    nums = [int(x) for x in re.findall(r"\d+", core)[:3]]
    nums += [0] * (3 - len(nums))
    return (nums, "-" not in v)  # prerelease sorts below its release
sys.exit(0 if key(sys.argv[1]) > key(sys.argv[2]) else 1)' "$1" "$2" 2>/dev/null
    return $?
  fi
  [ "$1" != "$2" ]
}

if [ "$FORCE" -ne 1 ]; then
  if [ "$LATEST" = "$INSTALLED" ]; then
    log "up to date (v${INSTALLED})"
    exit 0
  fi
  if ! is_newer "$LATEST" "$INSTALLED"; then
    log "installed v${INSTALLED} is ahead of registry v${LATEST} — skip"
    exit 0
  fi
fi

if ! command -v npx >/dev/null 2>&1; then
  log "skip: npx unavailable — cannot apply v${LATEST}"
  exit 0
fi

log "updating v${INSTALLED} → v${LATEST}"
if npx -y arkaos@latest update >> "$LOG" 2>&1; then
  log "update to v${LATEST} succeeded"
  notify "$(msg_updated "$LATEST")"
else
  log "update to v${LATEST} FAILED (see log above)"
  notify "$(msg_failed "$LATEST")"
fi
exit 0
