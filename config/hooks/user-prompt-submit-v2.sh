#!/usr/bin/env bash
# ============================================================================
# ArkaOS v2 — UserPromptSubmit Hook (Synapse v2 Bridge)
# Calls Python Synapse engine for 8-layer context injection
# Timeout: 10s | Output: JSON to stdout | Target: <100ms
# ============================================================================

input=$(cat)

# ─── Performance Timing ──────────────────────────────────────────────────
_HOOK_START_NS=$(date +%s%N 2>/dev/null || echo "0")
_hook_ms() {
  local end_ns=$(date +%s%N 2>/dev/null || echo "0")
  if [ "$_HOOK_START_NS" != "0" ] && [ "$end_ns" != "0" ] && [ ${#end_ns} -gt 10 ]; then
    echo $(( (end_ns - _HOOK_START_NS) / 1000000 ))
  else
    echo "0"
  fi
}

# ─── Paths ───────────────────────────────────────────────────────────────
ARKAOS_ROOT="${ARKA_OS:-$HOME/.claude/skills/arkaos}"
CACHE_DIR="/tmp/arkaos-context-cache"
CACHE_TTL=300  # Constitution cache: 5 minutes

mkdir -p "$CACHE_DIR" 2>/dev/null

# ─── Extract user input from hook JSON ───────────────────────────────────
user_input=""
if command -v jq &>/dev/null; then
  user_input=$(echo "$input" | jq -r '.userInput // .message // ""' 2>/dev/null)
fi
# Fallback: try to get the raw text
if [ -z "$user_input" ]; then
  user_input=$(echo "$input" | head -c 2000)
fi

# ─── Try Python Synapse engine first ─────────────────────────────────────
python_result=""
if command -v python3 &>/dev/null; then
  python_result=$(python3 -c "
import sys, os
sys.path.insert(0, '${ARKAOS_ROOT}')
try:
    from core.synapse.engine import create_default_engine
    from core.synapse.layers import PromptContext
    from core.governance.constitution import load_constitution
    import subprocess

    # Load constitution for L0
    const_path = '${ARKAOS_ROOT}/config/constitution.yaml'
    compressed = ''
    if os.path.exists(const_path):
        c = load_constitution(const_path)
        compressed = c.compress_for_context()

    # Detect git branch
    branch = ''
    try:
        branch = subprocess.run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                                capture_output=True, text=True, timeout=2).stdout.strip()
    except Exception:
        pass

    # Create engine and inject
    engine = create_default_engine(constitution_compressed=compressed)
    ctx = PromptContext(
        user_input='''${user_input}''',
        cwd=os.getcwd(),
        git_branch=branch,
    )
    result = engine.inject(ctx)
    print(result.context_string)
except Exception as e:
    print(f'[arkaos:error] {e}', file=sys.stderr)
    print('')
" 2>/dev/null)
fi

# ─── Fallback: Bash-only context (if Python unavailable) ────────────────
if [ -z "$python_result" ]; then
  # L0: Constitution (cached)
  L0=""
  L0_CACHE="$CACHE_DIR/l0-constitution"
  if [ -f "$L0_CACHE" ] && [ $(($(date +%s) - $(stat -f%m "$L0_CACHE" 2>/dev/null || stat -c%Y "$L0_CACHE" 2>/dev/null || echo 0))) -lt $CACHE_TTL ]; then
    L0=$(cat "$L0_CACHE")
  else
    L0="[Constitution] NON-NEGOTIABLE: branch-isolation, obsidian-output, authority-boundaries, security-gate, context-first, solid-clean-code, spec-driven, human-writing, squad-routing, full-visibility, sequential-validation, mandatory-qa, arka-supremacy | QUALITY-GATE: marta-cqo, eduardo-copy, francisca-tech-ux | MUST: conventional-commits, test-coverage, pattern-matching, actionable-output, memory-persistence"
    echo "$L0" > "$L0_CACHE" 2>/dev/null
  fi

  # L4: Git branch
  L4=""
  branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
  if [ -n "$branch" ] && [ "$branch" != "main" ] && [ "$branch" != "master" ] && [ "$branch" != "dev" ]; then
    L4="[branch:$branch]"
  fi

  # L7: Time
  hour=$(date +%H)
  if [ "$hour" -ge 5 ] && [ "$hour" -lt 12 ]; then
    L7="[time:morning]"
  elif [ "$hour" -ge 12 ] && [ "$hour" -lt 18 ]; then
    L7="[time:afternoon]"
  else
    L7="[time:evening]"
  fi

  python_result="$L0 $L4 $L7"
fi

# ─── Output ──────────────────────────────────────────────────────────────
echo "{\"additionalContext\": \"$python_result\"}"

# ─── Metrics ─────────────────────────────────────────────────────────────
elapsed=$(_hook_ms)
if [ "$elapsed" -gt 0 ] 2>/dev/null; then
  echo "{\"hook\":\"user-prompt-submit-v2\",\"ms\":$elapsed}" >> "$CACHE_DIR/hook-metrics.jsonl" 2>/dev/null
fi
