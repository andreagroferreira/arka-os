#!/usr/bin/env bats
# ============================================================================
# ARKA OS — DISC Framework Tests
# Tests for disc-profiles.json, agents-registry.json, validator, and hook
# ============================================================================

load helpers/setup

@test "disc-profiles.json is valid JSON with 4 profiles" {
  run jq '.profiles | keys | length' "$REPO_DIR/config/disc-profiles.json"
  [ "$status" -eq 0 ]
  [ "$output" = "4" ]
}

@test "disc-profiles.json has all required combination keys" {
  run jq '.combinations | keys | length' "$REPO_DIR/config/disc-profiles.json"
  [ "$status" -eq 0 ]
  [ "$output" -ge 8 ]
}

@test "agents-registry.json is valid JSON with 22 agents" {
  run jq '.agents | length' "$REPO_DIR/knowledge/agents-registry.json"
  [ "$status" -eq 0 ]
  [ "$output" = "22" ]
}

@test "agents-registry.json team_composition counts match agents array" {
  local d_count=$(jq '[.agents[] | select(.disc.primary == "D")] | length' "$REPO_DIR/knowledge/agents-registry.json")
  local i_count=$(jq '[.agents[] | select(.disc.primary == "I")] | length' "$REPO_DIR/knowledge/agents-registry.json")
  local s_count=$(jq '[.agents[] | select(.disc.primary == "S")] | length' "$REPO_DIR/knowledge/agents-registry.json")
  local c_count=$(jq '[.agents[] | select(.disc.primary == "C")] | length' "$REPO_DIR/knowledge/agents-registry.json")

  local reg_d=$(jq '.team_composition.by_disc_primary.D' "$REPO_DIR/knowledge/agents-registry.json")
  local reg_i=$(jq '.team_composition.by_disc_primary.I' "$REPO_DIR/knowledge/agents-registry.json")
  local reg_s=$(jq '.team_composition.by_disc_primary.S' "$REPO_DIR/knowledge/agents-registry.json")
  local reg_c=$(jq '.team_composition.by_disc_primary.C' "$REPO_DIR/knowledge/agents-registry.json")

  [ "$d_count" = "$reg_d" ]
  [ "$i_count" = "$reg_i" ]
  [ "$s_count" = "$reg_s" ]
  [ "$c_count" = "$reg_c" ]
}

@test "All agent files have disc: block in YAML frontmatter" {
  local agents=$(jq -r '.agents[].file' "$REPO_DIR/knowledge/agents-registry.json")
  for agent_file in $agents; do
    local full_path="$REPO_DIR/$agent_file"
    [ -f "$full_path" ] || fail "Agent file not found: $full_path"
    # Check for disc: in YAML frontmatter (between --- markers)
    run sed -n '1,/^---$/{ /^---$/d; p; }' "$full_path"
    echo "$output" | grep -q "disc:" || fail "Missing disc: in $agent_file"
  done
}

@test "All disc.primary values are valid (D, I, S, C)" {
  run jq -r '.agents[].disc.primary' "$REPO_DIR/knowledge/agents-registry.json"
  [ "$status" -eq 0 ]
  while IFS= read -r val; do
    [[ "$val" =~ ^[DISC]$ ]] || fail "Invalid disc.primary: $val"
  done <<< "$output"
}

@test "All disc.secondary values differ from disc.primary" {
  run jq -r '.agents[] | "\(.disc.primary) \(.disc.secondary)"' "$REPO_DIR/knowledge/agents-registry.json"
  [ "$status" -eq 0 ]
  while IFS= read -r line; do
    local primary=$(echo "$line" | cut -d' ' -f1)
    local secondary=$(echo "$line" | cut -d' ' -f2)
    [ "$primary" != "$secondary" ] || fail "primary == secondary for: $line"
  done <<< "$output"
}

@test "disc-team-validator.sh produces output" {
  export REGISTRY="$REPO_DIR/knowledge/agents-registry.json"
  run bash "$REPO_DIR/config/disc-team-validator.sh"
  [ "$status" -eq 0 ]
  [[ "$output" == *"ARKA OS"* ]]
  [[ "$output" == *"Dominant"* ]]
}

@test "disc-team-validator.sh detects S underrepresentation" {
  export REGISTRY="$REPO_DIR/knowledge/agents-registry.json"
  run bash "$REPO_DIR/config/disc-team-validator.sh"
  [ "$status" -eq 0 ]
  [[ "$output" == *"Low"* ]] || [[ "$output" == *"underrepresented"* ]]
}

@test "user-prompt-submit.sh includes disc: in agent context" {
  # Create a mock agents-registry.json in the test environment
  mkdir -p "$TEST_ARKA_OS/knowledge"
  cp "$REPO_DIR/knowledge/agents-registry.json" "$TEST_ARKA_OS/../../../knowledge/agents-registry.json" 2>/dev/null || true

  # Test that the hook script contains disc injection logic
  run grep -c "disc" "$REPO_DIR/config/hooks/user-prompt-submit.sh"
  [ "$status" -eq 0 ]
  [ "$output" -ge 1 ]
}
