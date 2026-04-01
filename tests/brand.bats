#!/usr/bin/env bats
# ============================================================================
# ARKA OS — Brand Department + Provider Registry Tests
# ============================================================================

load helpers/setup

# ─── Provider Registry ─────────────────────────────────────────────────────

@test "providers-registry.json is valid JSON" {
  run jq '.' "$REPO_DIR/config/providers-registry.json"
  [ "$status" -eq 0 ]
}

@test "providers-registry.json has _meta with version" {
  run jq -r '._meta.version' "$REPO_DIR/config/providers-registry.json"
  [ "$status" -eq 0 ]
  [ "$output" = "1.0.0" ]
}

@test "providers-registry.json has 4 default providers" {
  run jq '.providers | length' "$REPO_DIR/config/providers-registry.json"
  [ "$status" -eq 0 ]
  [ "$output" = "4" ]
}

@test "providers-registry.json has routing chains" {
  run jq '.routing | keys | length' "$REPO_DIR/config/providers-registry.json"
  [ "$status" -eq 0 ]
  [ "$output" -ge 3 ]
}

@test "Each provider has required fields" {
  local providers
  providers=$(jq -r '.providers | keys[]' "$REPO_DIR/config/providers-registry.json")
  for pid in $providers; do
    run jq -e --arg id "$pid" '.providers[$id] | .name and .base_url and .auth_env and .auth_header and .models' "$REPO_DIR/config/providers-registry.json"
    [ "$status" -eq 0 ] || fail "Provider '$pid' missing required fields"
  done
}

@test "All models have type and description" {
  run jq '[.providers[].models | to_entries[] | select(.value.type == null or .value.description == null)] | length' "$REPO_DIR/config/providers-registry.json"
  [ "$status" -eq 0 ]
  [ "$output" = "0" ]
}

@test "Routing chain references valid provider/model pairs" {
  local result
  result=$(jq -r '
    .providers as $p |
    [.routing[][] |
      split("/") | .[0] as $pid | .[1:] | join("/") as $mid |
      if $p[$pid].models[$mid] then empty else "\($pid)/\($mid)" end
    ] | join(", ")
  ' "$REPO_DIR/config/providers-registry.json")
  [ -z "$result" ] || fail "Invalid routing references: $result"
}

# ─── arka-providers CLI ────────────────────────────────────────────────────

@test "arka-providers script exists and is executable" {
  [ -x "$REPO_DIR/bin/arka-providers" ]
}

@test "arka-providers --json produces valid JSON" {
  run bash "$REPO_DIR/bin/arka-providers" --json
  [ "$status" -eq 0 ]
  echo "$output" | jq '.' > /dev/null 2>&1
}

@test "arka-providers list shows providers" {
  run bash "$REPO_DIR/bin/arka-providers"
  [ "$status" -eq 0 ]
  [[ "$output" == *"OpenAI"* ]]
  [[ "$output" == *"Replicate"* ]]
  [[ "$output" == *"FAL"* ]]
  [[ "$output" == *"OpenRouter"* ]]
}

@test "arka-providers routing shows chains" {
  run bash "$REPO_DIR/bin/arka-providers" routing
  [ "$status" -eq 0 ]
  [[ "$output" == *"image-generation"* ]]
  [[ "$output" == *"video-generation"* ]]
}

# ─── Brand Department Structure ────────────────────────────────────────────

@test "Brand SKILL.md exists" {
  [ -f "$REPO_DIR/departments/brand/SKILL.md" ]
}

@test "Brand SKILL.md has 12 commands" {
  local count
  count=$(grep -c '| `/brand ' "$REPO_DIR/departments/brand/SKILL.md")
  [ "$count" -eq 12 ]
}

@test "Brand SKILL.md has valid frontmatter" {
  run sed -n '1,/^---$/p' "$REPO_DIR/departments/brand/SKILL.md"
  [ "$status" -eq 0 ]
  echo "$output" | grep -q "name: brand"
}

# ─── Brand Agents ──────────────────────────────────────────────────────────

@test "All 4 brand agent files exist" {
  [ -f "$REPO_DIR/departments/brand/agents/creative-director.md" ]
  [ -f "$REPO_DIR/departments/brand/agents/brand-strategist.md" ]
  [ -f "$REPO_DIR/departments/brand/agents/visual-designer.md" ]
  [ -f "$REPO_DIR/departments/brand/agents/motion-designer.md" ]
}

@test "Brand agents have valid YAML frontmatter with disc" {
  for agent_file in "$REPO_DIR"/departments/brand/agents/*.md; do
    [ -f "$agent_file" ] || continue
    grep -q "^disc:" "$agent_file" || fail "Missing disc: in $(basename "$agent_file")"
    grep -q "^tier:" "$agent_file" || fail "Missing tier: in $(basename "$agent_file")"
    grep -q "^name:" "$agent_file" || fail "Missing name: in $(basename "$agent_file")"
    grep -q "^memory_path:" "$agent_file" || fail "Missing memory_path: in $(basename "$agent_file")"
  done
}

@test "Brand agents have correct DISC profiles" {
  run grep 'combination:' "$REPO_DIR/departments/brand/agents/creative-director.md"
  [[ "$output" == *"S+I"* ]]

  run grep 'combination:' "$REPO_DIR/departments/brand/agents/brand-strategist.md"
  [[ "$output" == *"C+I"* ]]

  run grep 'combination:' "$REPO_DIR/departments/brand/agents/visual-designer.md"
  [[ "$output" == *"I+S"* ]]

  run grep 'combination:' "$REPO_DIR/departments/brand/agents/motion-designer.md"
  [[ "$output" == *"D+I"* ]]
}

@test "Brand agents have correct tiers" {
  run grep '^tier:' "$REPO_DIR/departments/brand/agents/creative-director.md"
  [[ "$output" == *"1"* ]]

  for agent in brand-strategist visual-designer motion-designer; do
    run grep '^tier:' "$REPO_DIR/departments/brand/agents/$agent.md"
    [[ "$output" == *"2"* ]] || fail "$agent should be tier 2"
  done
}

# ─── provider-call.sh ──────────────────────────────────────────────────────

@test "provider-call.sh exists and is executable" {
  [ -f "$REPO_DIR/departments/brand/scripts/provider-call.sh" ]
  chmod +x "$REPO_DIR/departments/brand/scripts/provider-call.sh"
  [ -x "$REPO_DIR/departments/brand/scripts/provider-call.sh" ]
}

@test "provider-call.sh --list runs without error" {
  run bash "$REPO_DIR/departments/brand/scripts/provider-call.sh" --list
  [ "$status" -eq 0 ]
}

# ─── MCP Profile ───────────────────────────────────────────────────────────

@test "Brand MCP profile exists and is valid JSON" {
  run jq '.' "$REPO_DIR/mcps/profiles/brand.json"
  [ "$status" -eq 0 ]
}

@test "Brand MCP profile extends base and includes canva" {
  run jq -r '._meta.extends' "$REPO_DIR/mcps/profiles/brand.json"
  [ "$output" = "base" ]

  run jq '.mcps | any(. == "canva")' "$REPO_DIR/mcps/profiles/brand.json"
  [ "$output" = "true" ]
}

# ─── Integration ───────────────────────────────────────────────────────────

@test "agents-registry.json has 22 agents" {
  run jq '.agents | length' "$REPO_DIR/knowledge/agents-registry.json"
  [ "$status" -eq 0 ]
  [ "$output" = "22" ]
}

@test "agents-registry.json includes all 4 brand agents" {
  for agent_id in creative-director brand-strategist visual-designer motion-designer; do
    run jq -e --arg id "$agent_id" '.agents[] | select(.id == $id)' "$REPO_DIR/knowledge/agents-registry.json"
    [ "$status" -eq 0 ] || fail "Missing agent: $agent_id"
  done
}

@test "agents-registry.json team_composition counts are correct" {
  local total
  total=$(jq '[.team_composition.by_disc_primary | to_entries[].value] | add' "$REPO_DIR/knowledge/agents-registry.json")
  [ "$total" = "22" ]
}

@test "MCP registry includes canva entry" {
  run jq -e '.mcpServers.canva' "$REPO_DIR/mcps/registry.json"
  [ "$status" -eq 0 ]
}
