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
  [[ "$output" == *"Constitution"* ]]
  [[ "$output" == *"solid-clean-code"* ]]
  [[ "$output" == *"spec-driven"* ]]
  [[ "$output" == *"human-writing"* ]]
  [[ "$output" == *"squad-routing"* ]]
}

@test "user-prompt-submit.sh includes time context" {
  input='{"prompt":"hello","cwd":"/tmp","session_id":"test123"}'
  run bash -c "echo '$input' | bash '$REPO_DIR/config/hooks/user-prompt-submit.sh'"
  [ "$status" -eq 0 ]
  [[ "$output" == *"time:"* ]]
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
