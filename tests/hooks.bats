#!/usr/bin/env bats
# ============================================================================
# ARKA OS — Hook Input/Output Contract Tests
# ============================================================================

load helpers/setup

@test "user-prompt-submit.sh outputs valid JSON" {
  input='{"prompt":"build a login feature","cwd":"/tmp","session_id":"test123"}'
  run bash -c "echo '$input' | bash '$REPO_DIR/config/hooks/user-prompt-submit.sh'"
  [ "$status" -eq 0 ]
  echo "$output" | jq empty
}

@test "user-prompt-submit.sh detects dev department" {
  input='{"prompt":"build a login feature","cwd":"/tmp","session_id":"test123"}'
  run bash -c "echo '$input' | bash '$REPO_DIR/config/hooks/user-prompt-submit.sh'"
  [ "$status" -eq 0 ]
  [[ "$output" == *"dept:dev"* ]]
}

@test "user-prompt-submit.sh detects finance department" {
  input='{"prompt":"create a budget forecast","cwd":"/tmp","session_id":"test123"}'
  run bash -c "echo '$input' | bash '$REPO_DIR/config/hooks/user-prompt-submit.sh'"
  [ "$status" -eq 0 ]
  [[ "$output" == *"dept:finance"* ]]
}

@test "user-prompt-submit.sh detects marketing department" {
  input='{"prompt":"create an instagram post","cwd":"/tmp","session_id":"test123"}'
  run bash -c "echo '$input' | bash '$REPO_DIR/config/hooks/user-prompt-submit.sh'"
  [ "$status" -eq 0 ]
  [[ "$output" == *"dept:marketing"* ]]
}

@test "user-prompt-submit.sh includes constitution L0" {
  input='{"prompt":"hello","cwd":"/tmp","session_id":"test123"}'
  run bash -c "export ARKA_OS='$TEST_ARKA_OS' && echo '$input' | bash '$REPO_DIR/config/hooks/user-prompt-submit.sh'"
  [ "$status" -eq 0 ]
  # Real Synapse engine emits the compact "[Constitution]" tag (token-lean,
  # v4.1.1); the bash fallback emits the full rule list. Both carry the word.
  [[ "$output" == *"Constitution"* ]]
}

@test "user-prompt-submit.sh emits no time-of-day tag" {
  # [time:X] removed in #255 (prompt-surface P0): cache-buster with no
  # consumer rule. Locked absent here and by scripts/tools/prompt_lint.py.
  input='{"prompt":"hello","cwd":"/tmp","session_id":"t-time"}'
  run bash -c "export ARKA_OS='$TEST_ARKA_OS' && echo '$input' | bash '$REPO_DIR/config/hooks/user-prompt-submit.sh'"
  [ "$status" -eq 0 ]
  [[ "$output" != *"[time:"* ]]
}

@test "user-prompt-submit.sh handles empty prompt" {
  input='{"prompt":"","cwd":"/tmp","session_id":"test123"}'
  run bash -c "echo '$input' | bash '$REPO_DIR/config/hooks/user-prompt-submit.sh'"
  [ "$status" -eq 0 ]
  echo "$output" | jq empty
}

@test "post-tool-use.sh outputs valid JSON on success" {
  input='{"tool_name":"Bash","tool_output":"Success","exit_code":"0","cwd":"/tmp"}'
  run bash -c "echo '$input' | bash '$REPO_DIR/config/hooks/post-tool-use.sh'"
  [ "$status" -eq 0 ]
  echo "$output" | jq empty
}

@test "post-tool-use.sh tracks errors on non-zero exit" {
  input='{"tool_name":"Bash","tool_output":"Error: ENOENT file not found","exit_code":"1","cwd":"/tmp"}'
  run bash -c "echo '$input' | bash '$REPO_DIR/config/hooks/post-tool-use.sh'"
  [ "$status" -eq 0 ]
  echo "$output" | jq empty
  [ -f "$HOME/.arka-os/gotchas.json" ]
}

@test "post-tool-use.sh skips clean output" {
  input='{"tool_name":"Bash","tool_output":"All good, no issues","exit_code":"0","cwd":"/tmp"}'
  run bash -c "echo '$input' | bash '$REPO_DIR/config/hooks/post-tool-use.sh'"
  [ "$status" -eq 0 ]
  [ "$output" = '{}' ]
}

@test "pre-compact.sh outputs valid JSON" {
  input='{"session_id":"test-session-123","transcript":"line1\nline2"}'
  run bash -c "echo '$input' | bash '$REPO_DIR/config/hooks/pre-compact.sh'"
  [ "$status" -eq 0 ]
  echo "$output" | jq empty
}

# ─── PR46 v2.65.0 — effort-aware nudge gating ────────────────────────────

@test "user-prompt-submit.sh suppresses KB-cite nudge on low effort" {
  mkdir -p /tmp/arkaos-cite
  sid="effort-low-$$"
  echo '{"passed":false,"reason":"missing","suggestion":"KB-first nudge"}' > "/tmp/arkaos-cite/${sid}.json"
  input='{"prompt":"hi","cwd":"/tmp","session_id":"'${sid}'","effort":{"level":"low"}}'
  run bash -c "echo '$input' | bash '$REPO_DIR/config/hooks/user-prompt-submit.sh'"
  [ "$status" -eq 0 ]
  [[ "$output" != *"[arka:suggest] KB-first nudge"* ]]
}

@test "user-prompt-submit.sh suppresses meta-tag nudge on medium effort" {
  mkdir -p /tmp/arkaos-meta
  sid="effort-med-$$"
  echo '{"passed":false,"reason":"missing","suggestion":"meta-tag nudge"}' > "/tmp/arkaos-meta/${sid}.json"
  input='{"prompt":"hi","cwd":"/tmp","session_id":"'${sid}'","effort":{"level":"medium"}}'
  run bash -c "echo '$input' | bash '$REPO_DIR/config/hooks/user-prompt-submit.sh'"
  [ "$status" -eq 0 ]
  [[ "$output" != *"[arka:suggest] meta-tag nudge"* ]]
}

@test "user-prompt-submit.sh surfaces KB-cite nudge on high effort" {
  mkdir -p /tmp/arkaos-cite
  sid="effort-high-$$"
  echo '{"passed":false,"reason":"missing","suggestion":"KB-first nudge"}' > "/tmp/arkaos-cite/${sid}.json"
  input='{"prompt":"hi","cwd":"/tmp","session_id":"'${sid}'","effort":{"level":"high"}}'
  run bash -c "echo '$input' | bash '$REPO_DIR/config/hooks/user-prompt-submit.sh'"
  [ "$status" -eq 0 ]
  [[ "$output" == *"[arka:suggest] KB-first nudge"* ]]
}

@test "user-prompt-submit.sh surfaces nudges when effort is unset (default high)" {
  mkdir -p /tmp/arkaos-cite
  sid="effort-default-$$"
  echo '{"passed":false,"reason":"missing","suggestion":"KB-first nudge"}' > "/tmp/arkaos-cite/${sid}.json"
  input='{"prompt":"hi","cwd":"/tmp","session_id":"'${sid}'"}'
  run bash -c "echo '$input' | bash '$REPO_DIR/config/hooks/user-prompt-submit.sh'"
  [ "$status" -eq 0 ]
  [[ "$output" == *"[arka:suggest] KB-first nudge"* ]]
}

@test "PR59: user-prompt-submit.sh surfaces closing-marker nudge on high effort" {
  mkdir -p /tmp/arkaos-closing
  sid="closing-high-$$"
  echo '{"passed":false,"reason":"missing","suggestion":"closing-marker nudge"}' > "/tmp/arkaos-closing/${sid}.json"
  input='{"prompt":"hi","cwd":"/tmp","session_id":"'${sid}'","effort":{"level":"high"}}'
  run bash -c "echo '$input' | bash '$REPO_DIR/config/hooks/user-prompt-submit.sh'"
  [ "$status" -eq 0 ]
  [[ "$output" == *"[arka:suggest] closing-marker nudge"* ]]
}

@test "PR59: user-prompt-submit.sh suppresses closing-marker nudge on low effort" {
  mkdir -p /tmp/arkaos-closing
  sid="closing-low-$$"
  echo '{"passed":false,"reason":"missing","suggestion":"closing-marker nudge"}' > "/tmp/arkaos-closing/${sid}.json"
  input='{"prompt":"hi","cwd":"/tmp","session_id":"'${sid}'","effort":{"level":"low"}}'
  run bash -c "echo '$input' | bash '$REPO_DIR/config/hooks/user-prompt-submit.sh'"
  [ "$status" -eq 0 ]
  [[ "$output" != *"[arka:suggest] closing-marker nudge"* ]]
}

@test "user-prompt-submit.sh reads CLAUDE_EFFORT env var when JSON omits effort" {
  mkdir -p /tmp/arkaos-cite
  sid="effort-env-$$"
  echo '{"passed":false,"reason":"missing","suggestion":"KB-first nudge"}' > "/tmp/arkaos-cite/${sid}.json"
  input='{"prompt":"hi","cwd":"/tmp","session_id":"'${sid}'"}'
  run bash -c "export CLAUDE_EFFORT=low && echo '$input' | bash '$REPO_DIR/config/hooks/user-prompt-submit.sh'"
  [ "$status" -eq 0 ]
  [[ "$output" != *"[arka:suggest] KB-first nudge"* ]]
}

@test "settings-template.json is valid JSON" {
  run jq empty "$REPO_DIR/config/settings-template.json"
  [ "$status" -eq 0 ]
}

@test "settings-template.json has all 3 hook types" {
  run jq -r '.hooks | keys[]' "$REPO_DIR/config/settings-template.json"
  [ "$status" -eq 0 ]
  [[ "$output" == *"UserPromptSubmit"* ]]
  [[ "$output" == *"PreCompact"* ]]
  [[ "$output" == *"PostToolUse"* ]]
}


# ─── OWASP A03 — injection hardening (cwd-changed / session-start) ──────
# Inputs are written to a file and piped via cat, so single quotes in the
# malicious payload don't break the test harness itself. The RCE tests use
# REAL directories (the hook exits at its `-d` guard otherwise) whose
# basename carries a valid-Python payload, and set HOME so the resolver
# actually executes — each is proven to fire on the stashed vulnerable hook.

@test "cwd-changed.sh: cwd interpolated into Python source cannot execute (no eval)" {
  # Reproduces the headline vector: the pre-fix hook interpolated the cwd
  # straight into the Python source (`cwd = '$NEW_CWD'`). A real directory
  # whose basename closes that string and runs os.system fires the sentinel
  # on the vulnerable hook; the fix reads cwd from ARKA_CWD so it cannot.
  # The payload uses os.environ['S'] for the sentinel path so the directory
  # basename stays slash-free (a path with '/' can't be one dir name).
  local sentinel="$TEST_TEMP_DIR/src-pwned"
  local base="x'; import os; os.system('touch ' + os.environ['S']); y='"
  local d="$TEST_TEMP_DIR/$base"
  mkdir -p "$d"
  # A present ecosystems.json makes the resolver run (the injection point).
  mkdir -p "$TEST_HOME/.arkaos"
  echo '{"ecosystems":{}}' > "$TEST_HOME/.arkaos/ecosystems.json"
  local inf="$TEST_TEMP_DIR/in.json"
  jq -nc --arg c "$d" '{cwd:$c,session_id:"a03"}' > "$inf"
  run bash -c "export HOME='$TEST_HOME' S='$sentinel'; cat '$inf' | bash '$REPO_DIR/config/hooks/cwd-changed.sh'"
  [ "$status" -eq 0 ]
  [ ! -f "$sentinel" ]
  [ -z "$output" ] || echo "$output" | jq empty
}

@test "cwd-changed.sh: emits valid JSON or nothing for a normal cwd" {
  local inf="$TEST_TEMP_DIR/in.json"
  echo '{"cwd":"/tmp","session_id":"a03"}' > "$inf"
  run bash -c "export HOME='$TEST_HOME'; cat '$inf' | bash '$REPO_DIR/config/hooks/cwd-changed.sh'"
  [ "$status" -eq 0 ]
  [ -z "$output" ] || echo "$output" | jq empty
}

@test "cwd-changed.sh: cwd with a single quote does not crash the resolver" {
  local d="$TEST_TEMP_DIR/it's a dir"
  mkdir -p "$d"
  local inf="$TEST_TEMP_DIR/in.json"
  jq -nc --arg c "$d" '{cwd:$c,session_id:"a03"}' > "$inf"
  run bash -c "cat '$inf' | bash '$REPO_DIR/config/hooks/cwd-changed.sh'"
  [ "$status" -eq 0 ]
  [ -z "$output" ] || echo "$output" | jq empty
}

@test "cwd-changed.sh: command-substitution in ecosystem name is not eval'd" {
  # The real eval RCE vector: a poisoned ecosystems.json whose name carries
  # a command substitution. The pre-fix hook eval'd the Python output, so
  # $(touch sentinel) fired the moment cwd matched the project. Post-fix the
  # value is read as JSON via jq and never re-evaluated.
  local sentinel="$TEST_TEMP_DIR/eco-pwned"
  local eco="$TEST_HOME/.arkaos/ecosystems.json"
  mkdir -p "$(dirname "$eco")"
  jq -nc --arg n "x\$(touch $sentinel)" \
    '{ecosystems:{evil:{name:$n,projects:["a03proj"]}}}' > "$eco"
  local d="$TEST_TEMP_DIR/a03proj"
  mkdir -p "$d"
  local inf="$TEST_TEMP_DIR/in.json"
  jq -nc --arg c "$d" '{cwd:$c,session_id:"a03"}' > "$inf"
  run bash -c "export HOME='$TEST_HOME'; cat '$inf' | bash '$REPO_DIR/config/hooks/cwd-changed.sh'"
  [ "$status" -eq 0 ]
  [ ! -f "$sentinel" ]
  [ -z "$output" ] || echo "$output" | jq empty
}

@test "session-start.sh: profile name with triple quotes yields valid JSON" {
  local prof="$TEST_HOME/.arkaos/profile.json"
  mkdir -p "$(dirname "$prof")"
  jq -nc '{name:"a'\'''\'''\''b\"c",company:"W"}' > "$prof"
  run bash -c "export HOME='$TEST_HOME'; echo '{}' | bash '$REPO_DIR/config/hooks/session-start.sh'"
  [ "$status" -eq 0 ]
  echo "$output" | jq empty
}

# ─── F1-A3: session-start memory-recap wiring (QG blocker B1) ──────────

@test "session-start.sh exports the hook PWD to the entrypoint, not \$REPO" {
  # Fake interpreter that logs argv + ARKA_HOOK_CWD — proves the WIRING
  # without python deps: the exported cwd must be the project dir the
  # hook ran in, never the installer repo (F2-2: cwd travels via env,
  # captured BEFORE the cd — the F1-A3 expansion lesson).
  FAKE_HOME="$BATS_TEST_TMPDIR/home"
  WORKDIR="$BATS_TEST_TMPDIR/client-projX"
  LOG="$BATS_TEST_TMPDIR/argv.log"
  mkdir -p "$FAKE_HOME/.arkaos" "$WORKDIR"
  echo "$REPO_DIR" > "$FAKE_HOME/.arkaos/.repo-path"
  FAKE_PY="$BATS_TEST_TMPDIR/fake-python"
  printf '#!/usr/bin/env bash\necho "argv:$* cwd:$ARKA_HOOK_CWD" >> "%s"\nexit 0\n' "$LOG" > "$FAKE_PY"
  chmod +x "$FAKE_PY"

  run bash -c "cd '$WORKDIR' && echo '{}' | HOME='$FAKE_HOME' ARKAOS_PYTHON='$FAKE_PY' bash '$REPO_DIR/config/hooks/session-start.sh'"
  [ "$status" -eq 0 ]

  grep -q "argv:-m core.hooks.session_start cwd:$WORKDIR" "$LOG"
  ! grep -q "cwd:$REPO_DIR" "$LOG"
}

# ─── F2-1: hook latency harness ────────────────────────────────────────

@test "hooks-bench.sh emits valid JSON with all hook entries" {
  run bash "$REPO_DIR/benchmarks/hooks-bench.sh" 1
  [ "$status" -eq 0 ]
  echo "$output" | jq empty
  count=$(echo "$output" | jq '.hooks | length')
  [ "$count" -eq 7 ]
  p50=$(echo "$output" | jq '.hooks."pre-tool-use".p50_ms')
  [ "$p50" -ge 0 ]
}
