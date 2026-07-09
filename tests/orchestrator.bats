#!/usr/bin/env bats
# ============================================================================
# ARKA OS — Universal Orchestrator Tests
# Tests for commands registry, hook L5, and CLI commands
# ============================================================================

load helpers/setup

@test "commands-registry.json is valid JSON with _meta and commands" {
  REGISTRY="$REPO_DIR/knowledge/commands-registry.json"
  [ -f "$REGISTRY" ]
  run jq '._meta.version' "$REGISTRY"
  [ "$status" -eq 0 ]
  [[ "$output" == '"3.0.0"' ]]
  run jq '.commands | type' "$REGISTRY"
  [ "$status" -eq 0 ]
  [[ "$output" == '"array"' ]]
}

@test "commands-registry.json has commands for all 8 departments + arka" {
  REGISTRY="$REPO_DIR/knowledge/commands-registry.json"
  run jq -r '[.commands[].department] | unique | sort | .[]' "$REGISTRY"
  [ "$status" -eq 0 ]
  [[ "$output" == *"arka"* ]]
  [[ "$output" == *"brand"* ]]
  [[ "$output" == *"dev"* ]]
  [[ "$output" == *"ecom"* ]]
  [[ "$output" == *"fin"* ]]
  [[ "$output" == *"kb"* ]]
  [[ "$output" == *"mkt"* ]]
  [[ "$output" == *"ops"* ]]
  [[ "$output" == *"strat"* ]]
}

@test "commands-keywords.json is valid JSON" {
  KEYWORDS="$REPO_DIR/knowledge/commands-keywords.json"
  [ -f "$KEYWORDS" ]
  run jq 'keys | length' "$KEYWORDS"
  [ "$status" -eq 0 ]
  [ "$output" -gt 50 ]
}

@test "all registry commands have required fields" {
  REGISTRY="$REPO_DIR/knowledge/commands-registry.json"
  # Check that no commands are missing required fields
  run jq '[.commands[] | select(.id == null or .command == null or .department == null or .description == null or .keywords == null)] | length' "$REGISTRY"
  [ "$status" -eq 0 ]
  [ "$output" -eq 0 ]
}

@test "no duplicate command IDs in registry" {
  REGISTRY="$REPO_DIR/knowledge/commands-registry.json"
  TOTAL=$(jq '.commands | length' "$REGISTRY")
  UNIQUE=$(jq '[.commands[].id] | unique | length' "$REGISTRY")
  [ "$TOTAL" -eq "$UNIQUE" ]
}

@test "registry generator produces valid output" {
  # M2 consolidation: the generator is the stdlib-only python module;
  # regenerate to a temp path so the committed file stays untouched
  # (the drift lock in test_commands_registry.py compares content).
  run bash -c "cd '$REPO_DIR' && python3 -c \"
from pathlib import Path
from core.registry.generator import generate_commands_registry
reg = generate_commands_registry(Path('.'), Path('$BATS_TEST_TMPDIR/regen.json'))
print(f'Registry generated: {reg[\\\"_meta\\\"][\\\"total_commands\\\"]} commands')
\""
  [ "$status" -eq 0 ]
  [[ "$output" == *"Registry generated"* ]]
  run jq '._meta.total_commands' "$BATS_TEST_TMPDIR/regen.json"
  [ "$status" -eq 0 ]
  [ "$output" -gt 0 ]
}

@test "hook L5 produces command hints for 'create social posts'" {
  # Set up the hook environment
  export ARKA_OS="$TEST_ARKA_OS"
  export HOME="$TEST_HOME"
  mkdir -p "$TEST_ARKA_CONFIG"

  # Copy registry to where the hook can find it
  cp "$REPO_DIR/knowledge/commands-registry.json" "$REPO_DIR/knowledge/commands-registry.json.bak" 2>/dev/null || true

  INPUT='{"prompt":"create social posts about AI","cwd":"/tmp","session_id":"test-123"}'
  run bash -c "echo '$INPUT' | bash '$REPO_DIR/config/hooks/user-prompt-submit.sh'"
  [ "$status" -eq 0 ]

  # Output should contain a hint for /mkt social
  [[ "$output" == *"hint:"* ]] || [[ "$output" == *"dept:marketing"* ]] || [[ "$output" == *"mkt"* ]]
}

@test "hook L5 produces no command hints for explicit slash commands" {
  export ARKA_OS="$TEST_ARKA_OS"
  export HOME="$TEST_HOME"
  mkdir -p "$TEST_ARKA_CONFIG"

  INPUT='{"prompt":"/dev feature auth","cwd":"/tmp","session_id":"test-456"}'
  run bash -c "echo '$INPUT' | bash '$REPO_DIR/config/hooks/user-prompt-submit.sh'"
  [ "$status" -eq 0 ]

  # Output should NOT contain hint tags for explicit commands
  [[ "$output" != *"[hint:"* ]]
}

@test "bin/arka contains commands|registry case" {
  grep -q 'commands|registry)' "$REPO_DIR/bin/arka"
}

@test "registry command count is in expected range (>70)" {
  REGISTRY="$REPO_DIR/knowledge/commands-registry.json"
  TOTAL=$(jq '._meta.total_commands' "$REGISTRY")
  [ "$TOTAL" -gt 70 ]
}
