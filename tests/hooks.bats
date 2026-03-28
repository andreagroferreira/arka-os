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
