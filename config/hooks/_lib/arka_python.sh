# shellcheck shell=bash
# ArkaOS shared Python resolver (shell side) — single source of truth.
#
# Mirrors installer/python-resolver.js (getArkaosPython). Every hook, the
# state reader, the agent-provision helper, and the `arka-py` shim source
# THIS file instead of probing for `python3` on their own. Rationale: an
# unrelated project venv first on PATH, or a system python without pyyaml/
# pydantic, silently degrades every gate. The ArkaOS venv is authoritative.
#
# Contract of arka_resolve_python():
#   Echoes the interpreter path and returns 0 when a provisioned ArkaOS
#   interpreter is found; echoes a best-effort fallback and returns 1 when
#   only a bare `python3` remains (caller degrades gracefully). Echoes
#   NOTHING and returns 1 when every remaining candidate is a Microsoft
#   Store App Execution Alias — see arka_python_last_resort().
#
# Resolution order:
#   1. $ARKAOS_PYTHON (explicit operator override), if executable.
#   2. The ArkaOS venv — ~/.arkaos/venv then ~/.arkaos/.venv, python then
#      python3. `[ -x ]` follows symlinks, so a Homebrew-rotated broken
#      symlink is skipped automatically.
#   3. Any python3 on PATH / known locations that can `import yaml`.
#   4. Bare `python3` as a last resort (return 1), or nothing at all when
#      that name — and `python` behind it — is only a Store alias.

# Last-resort name selection, extracted from arka_resolve_python() so the
# branch is reachable from a test: in place it sits behind a PATH probe
# that matches on every POSIX box with a yaml-capable python3, so it can
# only be exercised on the machine it was written for.
#
# Contract: echoes the name to hand back, or NOTHING when every remaining
# candidate is a Store alias. Empty is the point, not an oversight. The
# callers gate on `command -v "$ARKA_PY"` and an alias stub PASSES that
# gate — the file is real, it is just the Python install manager rather
# than an interpreter — so the only value that degrades a hook instead of
# downloading a CPython into the user's project is no value at all.
arka_python_last_resort() {
  local py3 py
  py3="$(command -v python3 2>/dev/null)"
  case "$py3" in
    *[Ww]indows[Aa]pps*) ;;
    # Absent or real: the documented `python3` contract, unchanged. POSIX
    # never reaches the alias branch below.
    *) printf '%s\n' "python3"; return 0 ;;
  esac

  # `python3` is the alias. On a Windows box that HAS a real interpreter,
  # `python` is the name it answers to; on a stock box with none, that is
  # an alias too and we must hand back nothing.
  py="$(command -v python 2>/dev/null)"
  case "$py" in
    "" | *[Ww]indows[Aa]pps*) return 0 ;;
  esac
  printf '%s\n' "python"
}

arka_resolve_python() {
  local cand

  if [ -n "${ARKAOS_PYTHON:-}" ] && [ -x "${ARKAOS_PYTHON}" ]; then
    printf '%s\n' "${ARKAOS_PYTHON}"
    return 0
  fi

  # Scripts/python.exe is the Windows venv layout. Without it, a Git-Bash
  # hook on Windows never matches the venv and always falls through to the
  # PATH probe below -- which is where the Store alias lives.
  for cand in \
      "$HOME/.arkaos/venv/bin/python" \
      "$HOME/.arkaos/venv/bin/python3" \
      "$HOME/.arkaos/venv/Scripts/python.exe" \
      "$HOME/.arkaos/.venv/bin/python" \
      "$HOME/.arkaos/.venv/bin/python3" \
      "$HOME/.arkaos/.venv/Scripts/python.exe"; do
    if [ -x "$cand" ]; then
      printf '%s\n' "$cand"
      return 0
    fi
  done

  # Never probe a Microsoft Store App Execution Alias: under Git Bash on
  # Windows `command -v python3` resolves to .../Microsoft/WindowsApps/
  # python3, which is the Python install manager, not an interpreter. The
  # `import yaml` check RUNS each candidate, and running that one installs
  # a CPython into the current working directory -- the user's project, for
  # a hook. It could not have succeeded anyway: an alias stub carries no
  # site packages. On POSIX nothing ever matches that path: pure no-op.
  #
  # `python` is LAST on purpose. On Windows it is the only real interpreter
  # left once the alias is filtered out; on POSIX one of the entries before
  # it always matches first, so an old box where `python` is Python 2 keeps
  # resolving exactly as it does today.
  for cand in python3 /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3 python; do
    case "$(command -v "$cand" 2>/dev/null)" in
      "") continue ;;
      *[Ww]indows[Aa]pps*) continue ;;
    esac
    if "$cand" -c "import yaml" >/dev/null 2>&1; then
      printf '%s\n' "$cand"
      return 0
    fi
  done

  arka_python_last_resort
  return 1
}

# Sourcing this file exports ARKA_PY once, so hooks can `exec "$ARKA_PY" ...`
# without each re-running the probe. Callers that need the return code call
# arka_resolve_python directly.
#
# `|| true` is REQUIRED: arka_resolve_python returns 1 on the last-resort
# fallback, and under `set -e` a failing command substitution in an
# assignment aborts the sourcing file mid-way (reproduced on bash 3.2.57).
# We still want ARKA_PY set to the fallback value, so swallow the status and
# keep the export unconditional.
ARKA_PY="$(arka_resolve_python)" || true
export ARKA_PY

# Contract of arka_resolve_root():
#   Echoes the ArkaOS root for `-m core.*` execution. env ARKAOS_ROOT wins
#   unconditionally (explicit operator override stays loud and debuggable).
#   Guessed candidates are validated on core/sync/__init__.py — the marker
#   that distinguishes the full package from the cognitive scheduler's
#   partial ~/.arkaos/core copy — because `.repo-path` points at an npx
#   cache that `npm cache clean` can purge at any time. Chain:
#   .repo-path (validated) → ~/.arkaos/lib snapshot (validated, written by
#   the installer) → .repo-path even without core (legacy VERSION readers)
#   → ~/.arkaos → ARKA_OS env → ~/.claude/skills/arkaos.
arka_resolve_root() {
  if [ -n "${ARKAOS_ROOT:-}" ]; then
    printf '%s\n' "$ARKAOS_ROOT"
    return 0
  fi
  local repo=""
  if [ -f "$HOME/.arkaos/.repo-path" ]; then
    repo="$(cat "$HOME/.arkaos/.repo-path" 2>/dev/null || true)"
  fi
  if [ -n "$repo" ] && [ -f "$repo/core/sync/__init__.py" ]; then
    printf '%s\n' "$repo"
    return 0
  fi
  if [ -f "$HOME/.arkaos/lib/core/sync/__init__.py" ]; then
    printf '%s\n' "$HOME/.arkaos/lib"
    return 0
  fi
  if [ -n "$repo" ] && [ -d "$repo" ]; then
    printf '%s\n' "$repo"
    return 0
  fi
  if [ -d "$HOME/.arkaos" ]; then
    printf '%s\n' "$HOME/.arkaos"
    return 0
  fi
  printf '%s\n' "${ARKA_OS:-$HOME/.claude/skills/arkaos}"
}

# ─── Degraded-run telemetry ────────────────────────────────────────────
# A hook that fails open and says nothing is indistinguishable from a hook
# that ran and allowed. That ambiguity is not hypothetical: an ArkaOS venv
# that could not `import pydantic` made every gate on one machine allow
# silently for months, and the same silence previously kept two real bugs
# invisible while manufacturing a third that never existed (Cross-Machine
# Lab, X3).
#
# Two hard rules, both deliberate:
#
#   1. NEVER write to stderr. Claude Code surfaces hook stderr to the user
#      as an error, so a diagnostic there converts a silent degradation
#      into visible noise on every event — trading one bad failure mode
#      for a worse one. The record goes to a file; only a reader who wants
#      it pays for it.
#   2. NEVER change the exit code. Fail-open is the correct posture for a
#      governance hook: a broken interpreter must not block the user's
#      work. This makes the degradation legible, not fatal.
#
# One JSON line per event, appended. Failure to write is swallowed —
# telemetry must never be the thing that breaks a hook.
#
# Growth cap: mirrors DEGRADED_LOG_MAX_BYTES in core/hooks/_shared.py. This
# writer needs it MORE than the Python one, not less — the cases it records
# (no interpreter, missing entrypoint) fire on every single tool call, so an
# uncapped log on a broken machine is the runaway, not a corner case.
ARKA_DEGRADED_MAX_BYTES=5242880

arka_hook_degraded() {
  local hook="${1:-unknown}" reason="${2:-unknown}" detail="${3:-}"
  local dir="$HOME/.arkaos/telemetry"
  local file="$dir/hook-degraded.jsonl"
  local stamp bytes
  stamp="$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null)" || stamp=""
  # Keep detail on one line and out of the JSON grammar's way. Every C0
  # control character (and DEL) becomes a space: a raw tab, \r or \001
  # reaching the printf below emits a byte JSON forbids inside a string, so
  # one degraded event carrying a Python traceback used to poison the whole
  # line for every reader. Translated rather than deleted so words do not
  # fuse — "expected\tgot" must stay two tokens. LC_ALL=C keeps the range
  # byte-wise; tr pads set2 by repeating its last character (POSIX).
  detail="$(printf '%s' "$detail" | LC_ALL=C tr '\000-\037\177' ' ' \
    | cut -c1-400)"
  detail="${detail//\\/\\\\}"
  detail="${detail//\"/\\\"}"
  if [ -f "$file" ]; then
    bytes="$(wc -c < "$file" 2>/dev/null | tr -d ' ')"
    case "$bytes" in
      '' | *[!0-9]*) ;;
      *)
        if [ "$bytes" -ge "$ARKA_DEGRADED_MAX_BYTES" ]; then
          mv -f "$file" "$file.1" 2>/dev/null || true
        fi
        ;;
    esac
  fi
  {
    mkdir -p "$dir" 2>/dev/null &&
      printf '{"ts":"%s","hook":"%s","reason":"%s","detail":"%s"}\n' \
        "$stamp" "$hook" "$reason" "$detail" >> "$file"
  } 2>/dev/null || true
  return 0
}

# Run a hook entrypoint under the resolved interpreter, recording the
# degraded cases instead of exec'ing into silence.
#
# ─── Deliberate divergence: this path does NOT `exec` ───────────────────
# Every other .sh wrapper (post-tool-use, session-start, session-end,
# subagent-stop, user-prompt-submit) still ends in `exec "$ARKA_PY" -m …`.
# This one cannot, and the reason is structural rather than stylistic:
# `exec` REPLACES the shell with Python, so there is no surviving process
# to read the exit status afterwards. Recording "the entrypoint failed"
# requires observing the status the entrypoint exited with, which requires
# outliving it. Restoring `exec` here would silently delete the
# entrypoint-failed record — the single most valuable one, since it is the
# only witness to a broken interpreter that resolves but cannot run.
#
# Two measured costs, accepted knowingly:
#   1. One extra live process (this shell) for the hook's lifetime.
#   2. On a hard kill of the wrapper (Claude Code's 10s timeout), the
#      Python child is reparented to PID 1 instead of dying with the
#      shell — an orphan for the remainder of its own run. Not fixable by
#      trapping: bash defers trap handling until the foreground command
#      returns, and backgrounding the child would redirect its stdin from
#      /dev/null in a non-interactive shell, which breaks the hook's stdin
#      contract outright. The orphan is short-lived and harmless; a hook
#      that cannot report its own failure is neither.
#
# Exit codes pass through UNCHANGED. Note which ones are NOT failures:
#   0  allow
#   2  the documented deny/block code — a gate doing its job, never logged
# Anything else means the entrypoint did not get to decide, which is
# exactly the case worth a record.
arka_run_hook() {
  local hook="$1" module="$2" status
  "$ARKA_PY" -m "$module"
  status=$?
  if [ "$status" -ne 0 ] && [ "$status" -ne 2 ]; then
    arka_hook_degraded "$hook" "entrypoint-failed" "exit=$status module=$module py=$ARKA_PY"
  fi
  return "$status"
}
