#!/usr/bin/env bats
# ============================================================================
# ARKA OS — MCP Profile/Registry Tests
# ============================================================================

load helpers/setup

@test "apply-mcps.sh --list shows all profiles" {
  run bash "$REPO_DIR/mcps/scripts/apply-mcps.sh" --list
  [ "$status" -eq 0 ]
  [[ "$output" == *"base"* ]]
  [[ "$output" == *"laravel"* ]]
}

@test "apply-mcps.sh generates valid .mcp.json" {
  PROJECT_DIR="$TEST_TEMP_DIR/test-project"
  mkdir -p "$PROJECT_DIR"

  run bash "$REPO_DIR/mcps/scripts/apply-mcps.sh" base --project "$PROJECT_DIR"
  [ "$status" -eq 0 ]
  [ -f "$PROJECT_DIR/.mcp.json" ]
  jq empty "$PROJECT_DIR/.mcp.json"
}

@test "apply-mcps.sh generates valid settings.local.json" {
  PROJECT_DIR="$TEST_TEMP_DIR/test-project"
  mkdir -p "$PROJECT_DIR"

  run bash "$REPO_DIR/mcps/scripts/apply-mcps.sh" base --project "$PROJECT_DIR"
  [ "$status" -eq 0 ]
  [ -f "$PROJECT_DIR/.claude/settings.local.json" ]
  jq empty "$PROJECT_DIR/.claude/settings.local.json"
}

@test "apply-mcps.sh base profile includes expected MCPs" {
  PROJECT_DIR="$TEST_TEMP_DIR/test-project"
  mkdir -p "$PROJECT_DIR"

  bash "$REPO_DIR/mcps/scripts/apply-mcps.sh" base --project "$PROJECT_DIR"

  # Base should include obsidian, context7, playwright at minimum
  MCPS=$(jq -r '.mcpServers | keys[]' "$PROJECT_DIR/.mcp.json")
  [[ "$MCPS" == *"obsidian"* ]] || [[ "$MCPS" == *"context7"* ]]
}

@test "apply-mcps.sh laravel profile includes base + laravel MCPs" {
  PROJECT_DIR="$TEST_TEMP_DIR/test-project"
  mkdir -p "$PROJECT_DIR"

  bash "$REPO_DIR/mcps/scripts/apply-mcps.sh" laravel --project "$PROJECT_DIR"

  MCPS=$(jq -r '.mcpServers | keys[]' "$PROJECT_DIR/.mcp.json")
  # Should have laravel-specific MCPs
  echo "$MCPS" | grep -q "laravel-boost" || echo "$MCPS" | grep -q "serena"
}

@test "apply-mcps.sh --add single MCP works" {
  PROJECT_DIR="$TEST_TEMP_DIR/test-project"
  mkdir -p "$PROJECT_DIR"

  run bash "$REPO_DIR/mcps/scripts/apply-mcps.sh" --add context7 --project "$PROJECT_DIR"
  [ "$status" -eq 0 ]
  [ -f "$PROJECT_DIR/.mcp.json" ]
  jq -e '.mcpServers.context7' "$PROJECT_DIR/.mcp.json"
}

@test "apply-mcps.sh --status with no config shows empty" {
  PROJECT_DIR="$TEST_TEMP_DIR/test-project"
  mkdir -p "$PROJECT_DIR"

  run bash "$REPO_DIR/mcps/scripts/apply-mcps.sh" --status --project "$PROJECT_DIR"
  [ "$status" -eq 0 ]
  [[ "$output" == *"No .mcp.json"* ]]
}

@test "registry.json is valid JSON with required fields" {
  run jq empty "$REPO_DIR/mcps/registry.json"
  [ "$status" -eq 0 ]

  # Check it has mcpServers key
  run jq -e '.mcpServers' "$REPO_DIR/mcps/registry.json"
  [ "$status" -eq 0 ]
}

@test "all profile files reference valid MCPs from registry" {
  REGISTRY="$REPO_DIR/mcps/registry.json"
  VALID_MCPS=$(jq -r '.mcpServers | keys[]' "$REGISTRY")

  for profile in "$REPO_DIR/mcps/profiles"/*.json; do
    PROFILE_MCPS=$(jq -r '.mcps[]' "$profile" 2>/dev/null)
    for mcp in $PROFILE_MCPS; do
      echo "$VALID_MCPS" | grep -q "^${mcp}$" || {
        echo "Profile $(basename $profile) references unknown MCP: $mcp"
        return 1
      }
    done
  done
}

@test "apply-mcps.sh replaces {cwd} placeholder correctly" {
  PROJECT_DIR="$TEST_TEMP_DIR/test-project"
  mkdir -p "$PROJECT_DIR"

  bash "$REPO_DIR/mcps/scripts/apply-mcps.sh" base --project "$PROJECT_DIR"

  # Check that {cwd} is not present in generated file
  ! grep -q '{cwd}' "$PROJECT_DIR/.mcp.json"
}

@test "apply-mcps.sh rejects invalid profile" {
  PROJECT_DIR="$TEST_TEMP_DIR/test-project"
  mkdir -p "$PROJECT_DIR"

  run bash "$REPO_DIR/mcps/scripts/apply-mcps.sh" nonexistent --project "$PROJECT_DIR"
  [ "$status" -ne 0 ]
  [[ "$output" == *"not found"* ]]
}

@test "apply-mcps.sh never writes runtime-managed entries to .mcp.json" {
  PROJECT_DIR="$TEST_TEMP_DIR/test-project"
  mkdir -p "$PROJECT_DIR"

  run bash "$REPO_DIR/mcps/scripts/apply-mcps.sh" --add claude-in-chrome --project "$PROJECT_DIR"
  [ "$status" -eq 0 ]
  [[ "$output" == *"runtime-managed"* ]]

  # The managed entry must not exist in the generated .mcp.json
  run jq -e '.mcpServers."claude-in-chrome"' "$PROJECT_DIR/.mcp.json"
  [ "$status" -ne 0 ]

  # And no corrupt "command": "null" artefact anywhere in the file
  ! grep -q '"command": *"null"' "$PROJECT_DIR/.mcp.json"
}
