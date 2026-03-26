#!/usr/bin/env bats
# ============================================================================
# ARKA OS — Doctor Health Check Tests
# ============================================================================

load helpers/setup

@test "arka-doctor runs without errors" {
  run bash "$REPO_DIR/bin/arka-doctor"
  # Should not crash (exit 0 even with warnings)
  [ "$status" -eq 0 ]
}

@test "arka-doctor --json outputs valid JSON array" {
  run bash "$REPO_DIR/bin/arka-doctor" --json
  [ "$status" -eq 0 ]
  echo "$output" | jq empty
  # Should be an array
  type=$(echo "$output" | jq -r 'type')
  [ "$type" = "array" ]
}

@test "arka-doctor --json has 16 checks" {
  run bash "$REPO_DIR/bin/arka-doctor" --json
  [ "$status" -eq 0 ]
  count=$(echo "$output" | jq 'length')
  [ "$count" -eq 16 ]
}

@test "arka-doctor --json checks have required fields" {
  run bash "$REPO_DIR/bin/arka-doctor" --json
  [ "$status" -eq 0 ]
  # Every check should have name, status, severity, description
  missing=$(echo "$output" | jq '[.[] | select(.name == null or .status == null or .severity == null or .description == null)] | length')
  [ "$missing" -eq 0 ]
}

@test "arka-doctor --json includes claude-cli check" {
  run bash "$REPO_DIR/bin/arka-doctor" --json
  [ "$status" -eq 0 ]
  has_claude=$(echo "$output" | jq '[.[] | select(.name == "claude-cli")] | length')
  [ "$has_claude" -eq 1 ]
}

@test "arka-doctor --json includes agent-memory check" {
  run bash "$REPO_DIR/bin/arka-doctor" --json
  [ "$status" -eq 0 ]
  has_check=$(echo "$output" | jq '[.[] | select(.name == "agent-memory")] | length')
  [ "$has_check" -eq 1 ]
}

@test "arka-doctor --json includes install-manifest check" {
  run bash "$REPO_DIR/bin/arka-doctor" --json
  [ "$status" -eq 0 ]
  has_check=$(echo "$output" | jq '[.[] | select(.name == "install-manifest")] | length')
  [ "$has_check" -eq 1 ]
}

@test "arka-doctor --json includes gotchas check" {
  run bash "$REPO_DIR/bin/arka-doctor" --json
  [ "$status" -eq 0 ]
  has_check=$(echo "$output" | jq '[.[] | select(.name == "gotchas")] | length')
  [ "$has_check" -eq 1 ]
}

@test "arka-doctor --json includes plugins check" {
  run bash "$REPO_DIR/bin/arka-doctor" --json
  [ "$status" -eq 0 ]
  has_check=$(echo "$output" | jq '[.[] | select(.name == "plugins")] | length')
  [ "$has_check" -eq 1 ]
}

@test "arka-doctor status values are valid" {
  run bash "$REPO_DIR/bin/arka-doctor" --json
  [ "$status" -eq 0 ]
  invalid=$(echo "$output" | jq '[.[] | select(.status != "pass" and .status != "warn" and .status != "fail")] | length')
  [ "$invalid" -eq 0 ]
}

@test "arka-doctor severity values are valid" {
  run bash "$REPO_DIR/bin/arka-doctor" --json
  [ "$status" -eq 0 ]
  invalid=$(echo "$output" | jq '[.[] | select(.severity != "fail" and .severity != "warn")] | length')
  [ "$invalid" -eq 0 ]
}
