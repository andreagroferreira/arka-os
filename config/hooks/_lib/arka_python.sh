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
#   only a bare `python3` remains (caller degrades gracefully).
#
# Resolution order:
#   1. $ARKAOS_PYTHON (explicit operator override), if executable.
#   2. The ArkaOS venv — ~/.arkaos/venv then ~/.arkaos/.venv, python then
#      python3. `[ -x ]` follows symlinks, so a Homebrew-rotated broken
#      symlink is skipped automatically.
#   3. Any python3 on PATH / known locations that can `import yaml`.
#   4. Bare `python3` as a last resort (return 1).

arka_resolve_python() {
  local cand

  if [ -n "${ARKAOS_PYTHON:-}" ] && [ -x "${ARKAOS_PYTHON}" ]; then
    printf '%s\n' "${ARKAOS_PYTHON}"
    return 0
  fi

  for cand in \
      "$HOME/.arkaos/venv/bin/python" \
      "$HOME/.arkaos/venv/bin/python3" \
      "$HOME/.arkaos/.venv/bin/python" \
      "$HOME/.arkaos/.venv/bin/python3"; do
    if [ -x "$cand" ]; then
      printf '%s\n' "$cand"
      return 0
    fi
  done

  for cand in python3 /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3; do
    if command -v "$cand" >/dev/null 2>&1 && "$cand" -c "import yaml" >/dev/null 2>&1; then
      printf '%s\n' "$cand"
      return 0
    fi
  done

  printf '%s\n' "python3"
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
