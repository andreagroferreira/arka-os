#!/usr/bin/env bash
# ============================================================================
# ARKA OS — UserPromptSubmit Hook (5-Layer Context Injection)
# Injects contextual rules per prompt with caching for performance
# Timeout: 10s | Output: JSON to stdout | Target: <200ms
# ============================================================================

input=$(cat)

# ─── Performance Timing ──────────────────────────────────────────────────
_HOOK_START=$(date +%s 2>/dev/null)
_HOOK_START_NS=$(date +%s%N 2>/dev/null || echo "0")
_hook_ms() {
  local end_ns=$(date +%s%N 2>/dev/null || echo "0")
  if [ "$_HOOK_START_NS" != "0" ] && [ "$end_ns" != "0" ] && [ ${#end_ns} -gt 10 ]; then
    echo $(( (end_ns - _HOOK_START_NS) / 1000000 ))
  else
    echo $(( ($(date +%s) - _HOOK_START) * 1000 ))
  fi
}

# Extract fields
PROMPT=$(echo "$input" | jq -r '.prompt // ""' 2>/dev/null)
CWD=$(echo "$input" | jq -r '.cwd // ""' 2>/dev/null)
SESSION_ID=$(echo "$input" | jq -r '.session_id // ""' 2>/dev/null)

CONTEXT_PARTS=()
ARKA_OS="${ARKA_OS:-$HOME/.claude/skills/arka}"
CACHE_DIR="/tmp/arka-context-cache"
mkdir -p "$CACHE_DIR"

# ─── Cache Helper ─────────────────────────────────────────────────────────
# cache_get <key> <ttl_seconds> — returns cached value or empty
cache_get() {
  local file="$CACHE_DIR/$1"
  local ttl="$2"
  if [ -f "$file" ]; then
    local age=$(( $(date +%s) - $(stat -f%m "$file" 2>/dev/null || stat -c%Y "$file" 2>/dev/null || echo 0) ))
    if [ "$age" -lt "$ttl" ]; then
      cat "$file"
      return 0
    fi
  fi
  return 1
}

cache_set() {
  echo "$2" > "$CACHE_DIR/$1"
}

# ─── L0: Constitution (compressed, 300s cache) ───────────────────────────
L0=$(cache_get "constitution" 300) || {
  REPO_PATH=$(cat "$ARKA_OS/.repo-path" 2>/dev/null || echo "")
  CONSTITUTION_FILE=""
  [ -f "$REPO_PATH/CONSTITUTION.md" ] && CONSTITUTION_FILE="$REPO_PATH/CONSTITUTION.md"
  if [ -n "$CONSTITUTION_FILE" ]; then
    L0="[Constitution] NON-NEGOTIABLE: branch-isolation, obsidian-output, authority-boundaries, security-gate, context-first, solid-clean-code, spec-driven, human-writing, squad-routing, full-visibility, sequential-validation, mandatory-qa, arka-supremacy | QUALITY-GATE: marta-cqo, eduardo-copy, francisca-tech-ux | MUST: conventional-commits, test-coverage, pattern-matching, actionable-output, memory-persistence"
    cache_set "constitution" "$L0"
  else
    L0=""
  fi
}
[ -n "$L0" ] && CONTEXT_PARTS+=("$L0")
_L0_MS=$(_hook_ms)

# ─── L1: Department Routing (no cache — fast string match) ───────────────
PROMPT_LOWER=$(echo "$PROMPT" | tr '[:upper:]' '[:lower:]')
DETECTED_DEPT=""

if echo "$PROMPT_LOWER" | grep -qE '\b(build|code|feature|deploy|test|review|scaffold|debug|refactor|api|migration|stack)\b'; then
  DETECTED_DEPT="dev"
elif echo "$PROMPT_LOWER" | grep -qE '\b(budget|invoice|revenue|forecast|profit|loss|roi|margin|cash.?flow|financial|invest)\b'; then
  DETECTED_DEPT="finance"
elif echo "$PROMPT_LOWER" | grep -qE '\b(social|content|campaign|post|instagram|linkedin|twitter|tiktok|seo|marketing|ads|email.?campaign)\b'; then
  DETECTED_DEPT="marketing"
elif echo "$PROMPT_LOWER" | grep -qE '\b(store|product|shop|shopify|ecommerce|catalog|inventory|cart|checkout|pricing)\b'; then
  DETECTED_DEPT="ecommerce"
elif echo "$PROMPT_LOWER" | grep -qE '\b(strategy|brainstorm|market|swot|competitor|roadmap|pivot|growth)\b'; then
  DETECTED_DEPT="strategy"
elif echo "$PROMPT_LOWER" | grep -qE '\b(task|email|calendar|automate|meeting|workflow|process|schedule|slack|discord|notify)\b'; then
  DETECTED_DEPT="operations"
elif echo "$PROMPT_LOWER" | grep -qE '\b(learn|persona|knowledge|youtube|transcribe|article|research)\b'; then
  DETECTED_DEPT="knowledge"
elif echo "$PROMPT_LOWER" | grep -qE '\b(brand|logo|colors|palette|mockup|photoshoot|brand.?identity|brand.?guide|mood.?board|naming|positioning|visual.?design|motion.?design|brand.?video|social.?kit)\b'; then
  DETECTED_DEPT="brand"
fi
[ -n "$DETECTED_DEPT" ] && CONTEXT_PARTS+=("[dept:$DETECTED_DEPT]")
_L1_MS=$(( $(_hook_ms) - ${_L0_MS:-0} ))

# ─── L2: Agent Memory (30s cache) ────────────────────────────────────────
# Detect agent name from prompt
DETECTED_AGENT=""
if echo "$PROMPT_LOWER" | grep -qE '\bmarco\b|/.*cto\b'; then
  DETECTED_AGENT="cto"
elif echo "$PROMPT_LOWER" | grep -qE '\bpaulo\b|tech.?lead'; then
  DETECTED_AGENT="tech-lead"
elif echo "$PROMPT_LOWER" | grep -qE '\bgabriel\b|architect'; then
  DETECTED_AGENT="architect"
elif echo "$PROMPT_LOWER" | grep -qE '\bandre\b|senior.?dev|backend'; then
  DETECTED_AGENT="senior-dev"
elif echo "$PROMPT_LOWER" | grep -qE '\bdiana\b|frontend.?dev'; then
  DETECTED_AGENT="frontend-dev"
elif echo "$PROMPT_LOWER" | grep -qE '\bbruno\b|security'; then
  DETECTED_AGENT="security"
elif echo "$PROMPT_LOWER" | grep -qE '\bcarlos\b|devops'; then
  DETECTED_AGENT="devops"
elif echo "$PROMPT_LOWER" | grep -qE '\brita\b|\bqa\b'; then
  DETECTED_AGENT="qa"
elif echo "$PROMPT_LOWER" | grep -qE '\blucas\b|analyst'; then
  DETECTED_AGENT="analyst"
elif echo "$PROMPT_LOWER" | grep -qE '\bhelena\b|cfo'; then
  DETECTED_AGENT="cfo"
elif echo "$PROMPT_LOWER" | grep -qE '\bsofia\b|coo'; then
  DETECTED_AGENT="coo"
elif echo "$PROMPT_LOWER" | grep -qE '\bluna\b|content.?creator'; then
  DETECTED_AGENT="content-creator"
elif echo "$PROMPT_LOWER" | grep -qE '\bricardo\b|ecommerce.?manager'; then
  DETECTED_AGENT="ecommerce-manager"
elif echo "$PROMPT_LOWER" | grep -qE '\btomas\b|strategist'; then
  DETECTED_AGENT="strategist"
elif echo "$PROMPT_LOWER" | grep -qE '\bclara\b|knowledge.?curator'; then
  DETECTED_AGENT="knowledge-curator"
elif echo "$PROMPT_LOWER" | grep -qE '\bvalentina\b|creative.?director'; then
  DETECTED_AGENT="creative-director"
elif echo "$PROMPT_LOWER" | grep -qE '\bmateus\b|brand.?strategist'; then
  DETECTED_AGENT="brand-strategist"
elif echo "$PROMPT_LOWER" | grep -qE '\bisabel\b|visual.?designer'; then
  DETECTED_AGENT="visual-designer"
elif echo "$PROMPT_LOWER" | grep -qE '\brafael\b|motion.?designer'; then
  DETECTED_AGENT="motion-designer"
fi

if [ -n "$DETECTED_AGENT" ]; then
  AGENT_CACHE_KEY="agent-${DETECTED_AGENT}"
  AGENT_CTX=$(cache_get "$AGENT_CACHE_KEY" 30) || {
    AGENT_MEM="$HOME/.claude/agent-memory/arka-${DETECTED_AGENT}/MEMORY.md"
    AGENT_CTX="[agent:$DETECTED_AGENT"

    # Inject DISC profile from agents-registry.json (fast jq lookup)
    REPO_PATH=$(cat "$ARKA_OS/.repo-path" 2>/dev/null || echo "")
    REGISTRY_FILE="$REPO_PATH/knowledge/agents-registry.json"
    if [ -f "$REGISTRY_FILE" ] && command -v jq &>/dev/null; then
      DISC_COMBO=$(jq -r --arg id "$DETECTED_AGENT" '.agents[] | select(.id == $id) | .disc.combination // ""' "$REGISTRY_FILE" 2>/dev/null)
      [ -n "$DISC_COMBO" ] && AGENT_CTX+=" disc:$DISC_COMBO"
    fi

    if [ -f "$AGENT_MEM" ]; then
      # Extract last 3 gotchas from agent memory
      GOTCHAS=$(sed -n '/^## Gotchas/,/^## /{ /^## Gotchas/d; /^## /d; /^$/d; p; }' "$AGENT_MEM" 2>/dev/null | head -3)
      if [ -n "$GOTCHAS" ]; then
        AGENT_CTX+=" gotchas: $(echo "$GOTCHAS" | tr '\n' '; ' | head -c 200)"
      fi
    fi

    AGENT_CTX+="]"
    cache_set "$AGENT_CACHE_KEY" "$AGENT_CTX"
  }
  CONTEXT_PARTS+=("$AGENT_CTX")
fi
_L2_MS=$(( $(_hook_ms) - ${_L0_MS:-0} - ${_L1_MS:-0} ))

# ─── L3: Active Project (30s cache) ──────────────────────────────────────
if [ -n "$CWD" ]; then
  PROJECT_CACHE_KEY="project-$(echo "$CWD" | md5 2>/dev/null || echo "$CWD" | md5sum 2>/dev/null | cut -d' ' -f1 || echo "nocache")"
  PROJECT_CTX=$(cache_get "$PROJECT_CACHE_KEY" 30) || {
    PROJECT_CTX=""
    # Check ARKA OS projects/ directory
    REPO_PATH=$(cat "$ARKA_OS/.repo-path" 2>/dev/null || echo "")
    if [ -n "$REPO_PATH" ] && [ -d "$REPO_PATH/projects" ]; then
      for proj_md in "$REPO_PATH/projects"/*/PROJECT.md; do
        [ -f "$proj_md" ] || continue
        PROJ_DIR=$(dirname "$proj_md")
        if [ -f "$PROJ_DIR/.project-path" ]; then
          PROJ_PATH=$(cat "$PROJ_DIR/.project-path" 2>/dev/null)
          if [ -n "$PROJ_PATH" ] && [[ "$CWD" == "$PROJ_PATH"* ]]; then
            PROJ_NAME=$(basename "$PROJ_DIR")
            # Try to extract stack from PROJECT.md
            PROJ_STACK=$(grep -i 'stack\|framework' "$proj_md" 2>/dev/null | head -1 | sed 's/.*: *//' | head -c 50)
            PROJECT_CTX="[project:$PROJ_NAME"
            [ -n "$PROJ_STACK" ] && PROJECT_CTX+=" stack:$PROJ_STACK"
            PROJECT_CTX+="]"
            break
          fi
        fi
      done
    fi

    # Also check installed skills for project paths
    if [ -z "$PROJECT_CTX" ]; then
      for proj_dir in "$HOME/.claude/skills"/arka-*/; do
        [ -d "$proj_dir" ] || continue
        if [ -f "$proj_dir/.project-path" ]; then
          PROJ_PATH=$(cat "$proj_dir/.project-path" 2>/dev/null)
          if [ -n "$PROJ_PATH" ] && [[ "$CWD" == "$PROJ_PATH"* ]]; then
            PROJ_NAME=$(basename "$proj_dir" | sed 's/^arka-//')
            PROJECT_CTX="[project:$PROJ_NAME]"
            break
          fi
        fi
      done
    fi

    cache_set "$PROJECT_CACHE_KEY" "$PROJECT_CTX"
  }
  [ -n "$PROJECT_CTX" ] && CONTEXT_PARTS+=("$PROJECT_CTX")
fi
_L3_MS=$(( $(_hook_ms) - ${_L0_MS:-0} - ${_L1_MS:-0} - ${_L2_MS:-0} ))

# ─── L4: Git Branch Detection (no cache — fast check) ────────────────────
if [ -n "$CWD" ]; then
  CURRENT_BRANCH=$(git -C "$CWD" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
  if [ -n "$CURRENT_BRANCH" ] && [ "$CURRENT_BRANCH" != "main" ] && [ "$CURRENT_BRANCH" != "master" ] && [ "$CURRENT_BRANCH" != "dev" ]; then
    CONTEXT_PARTS+=("[branch:$CURRENT_BRANCH]")
  fi
fi
_L4_MS=$(( $(_hook_ms) - ${_L0_MS:-0} - ${_L1_MS:-0} - ${_L2_MS:-0} - ${_L3_MS:-0} ))

# ─── Gotchas Injection (30s cache) ───────────────────────────────────────
if [ -n "$DETECTED_DEPT" ]; then
  GOTCHA_CACHE_KEY="gotchas-${DETECTED_DEPT}"
  GOTCHA_CTX=$(cache_get "$GOTCHA_CACHE_KEY" 30) || {
    GOTCHA_CTX=""
    GOTCHAS_FILE="$HOME/.arka-os/gotchas.json"
    if [ -f "$GOTCHAS_FILE" ] && command -v jq &>/dev/null; then
      # Get top 2 recurring errors for this department with count >= 3 (include suggestions)
      TOP_GOTCHAS=$(jq -r --arg cat "$DETECTED_DEPT" \
        '[.[] | select(.category == $cat and .count >= 3)] | sort_by(-.count) | .[0:2] | .[] |
         if .suggestion then "\(.pattern) (x\(.count)) \u2192 \(.suggestion)" else "\(.pattern) (x\(.count))" end' \
        "$GOTCHAS_FILE" 2>/dev/null)
      if [ -n "$TOP_GOTCHAS" ]; then
        GOTCHA_CTX="[gotchas:$DETECTED_DEPT $(echo "$TOP_GOTCHAS" | tr '\n' '; ' | head -c 300)]"
      fi
    fi
    cache_set "$GOTCHA_CACHE_KEY" "$GOTCHA_CTX"
  }
  [ -n "$GOTCHA_CTX" ] && CONTEXT_PARTS+=("$GOTCHA_CTX")
fi

# ─── L5: Command Hint (30s cache) ────────────────────────────────────────
# Fast keyword lookup against commands-registry for non-explicit prompts
if [ -n "$PROMPT" ] && ! echo "$PROMPT" | grep -qE '^/(dev|mkt|ecom|fin|ops|strat|kb|arka|do) '; then
  CMD_CACHE_KEY="cmdhint-$(echo "$PROMPT_LOWER" | md5 2>/dev/null || echo "$PROMPT_LOWER" | md5sum 2>/dev/null | cut -d' ' -f1)"
  CMD_HINT=$(cache_get "$CMD_CACHE_KEY" 30) || {
    CMD_HINT=""
    REPO_PATH=$(cat "$ARKA_OS/.repo-path" 2>/dev/null || echo "")
    REGISTRY="$REPO_PATH/knowledge/commands-registry.json"
    if [ -f "$REGISTRY" ] && command -v jq &>/dev/null; then
      # Extract words from prompt and match against registry keywords
      CMD_HINT=$(jq -r --arg prompt "$PROMPT_LOWER" '
        ($prompt | split(" ") | map(select(length > 2))) as $words |
        [.commands[] |
          {id, command, department,
           score: ([.keywords[] | . as $kw |
             if ($words | any(. == $kw)) then 2
             elif ($words | join(" ") | test($kw)) then 3
             else 0 end
           ] | add // 0)}
        ] | sort_by(-.score) | [.[:2][] | select(.score > 0)] |
        if length > 0 then
          map("[hint:\(.command)]") | join(" ")
        else "" end
      ' "$REGISTRY" 2>/dev/null)
    fi
    cache_set "$CMD_CACHE_KEY" "$CMD_HINT"
  }
  [ -n "$CMD_HINT" ] && CONTEXT_PARTS+=("$CMD_HINT")
fi
_L5_MS=$(( $(_hook_ms) - ${_L0_MS:-0} - ${_L1_MS:-0} - ${_L2_MS:-0} - ${_L3_MS:-0} - ${_L4_MS:-0} ))

# ─── Time of Day (no cache) ──────────────────────────────────────────────
HOUR=$(date +%H)
if [ "$HOUR" -lt 12 ]; then
  CONTEXT_PARTS+=("[time:morning]")
elif [ "$HOUR" -lt 18 ]; then
  CONTEXT_PARTS+=("[time:afternoon]")
else
  CONTEXT_PARTS+=("[time:evening]")
fi

# ─── Log Metrics ─────────────────────────────────────────────────────────
_DURATION_MS=$(_hook_ms)
METRICS_FILE="$HOME/.arka-os/hook-metrics.json"
METRICS_LOCK="$HOME/.arka-os/hook-metrics.lock"
mkdir -p "$HOME/.arka-os"
(
  if command -v flock &>/dev/null; then flock -w 2 200; else true; fi
  [ ! -f "$METRICS_FILE" ] && echo '[]' > "$METRICS_FILE"
  NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  jq --argjson dur "$_DURATION_MS" --arg ts "$NOW" --arg hook "user-prompt-submit" \
    --argjson l0 "${_L0_MS:-0}" --argjson l1 "${_L1_MS:-0}" --argjson l2 "${_L2_MS:-0}" \
    --argjson l3 "${_L3_MS:-0}" --argjson l4 "${_L4_MS:-0}" --argjson l5 "${_L5_MS:-0}" \
    '. += [{"hook": $hook, "duration_ms": $dur, "timestamp": $ts, "layers": {"L0": $l0, "L1": $l1, "L2": $l2, "L3": $l3, "L4": $l4, "L5": $l5}}] | .[-500:]' \
    "$METRICS_FILE" > "$METRICS_FILE.tmp" 2>/dev/null && mv "$METRICS_FILE.tmp" "$METRICS_FILE"
) 200>"$METRICS_LOCK" 2>/dev/null

# ─── Output ───────────────────────────────────────────────────────────────
if [ ${#CONTEXT_PARTS[@]} -gt 0 ]; then
  CONTEXT=""
  for part in "${CONTEXT_PARTS[@]}"; do
    CONTEXT+="$part "
  done
  CONTEXT="${CONTEXT% }"

  jq -n --arg ctx "$CONTEXT" '{
    "hookSpecificOutput": {
      "hookEventName": "UserPromptSubmit",
      "additionalContext": $ctx
    }
  }'
else
  echo '{}'
fi
