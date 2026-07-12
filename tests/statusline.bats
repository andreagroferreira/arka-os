#!/usr/bin/env bats
# ============================================================================
# ARKA OS — Status Line Tests
# ============================================================================

load helpers/setup

@test "statusline.sh exists and is executable" {
  [ -f "$REPO_DIR/config/statusline.sh" ]
  [ -x "$REPO_DIR/config/statusline.sh" ]
}

@test "statusline.sh produces output" {
  run bash "$REPO_DIR/config/statusline.sh"
  [ "$status" -eq 0 ]
  [ -n "$output" ]
}

@test "statusline.sh output contains ARKA" {
  run bash "$REPO_DIR/config/statusline.sh"
  [ "$status" -eq 0 ]
  [[ "$output" == *"ARKA"* ]]
}

@test "statusline.sh produces exactly 2 lines" {
  run bash "$REPO_DIR/config/statusline.sh"
  [ "$status" -eq 0 ]
  line_count=$(echo "$output" | wc -l | tr -d ' ')
  [ "$line_count" -eq 2 ]
}

# ─── F2-5: workflow gate + budget segment ──────────────────────────────

@test "statusline shows workflow gate when workflow-state.json is active" {
  FAKE_HOME="$BATS_TEST_TMPDIR/home"
  mkdir -p "$FAKE_HOME/.arkaos"
  printf '{"workflow":"dev-feature","phases":{"spec":{"status":"completed"},"gate-2-build":{"status":"in_progress"}},"violations":[]}' \
    > "$FAKE_HOME/.arkaos/workflow-state.json"
  payload='{"model":{"display_name":"Fable 5"},"cwd":"/x/proj","context_window":{"used_percentage":10},"cost":{"total_cost_usd":0.1}}'
  run bash -c "printf '%s' '$payload' | HOME='$FAKE_HOME' bash '$REPO_DIR/config/statusline.sh'"
  [ "$status" -eq 0 ]
  [[ "$output" == *"dev-feature"* ]]
  [[ "$output" == *"G2/2"* ]]
}

@test "statusline shows violations count when present" {
  FAKE_HOME="$BATS_TEST_TMPDIR/home"
  mkdir -p "$FAKE_HOME/.arkaos"
  printf '{"workflow":"wf","phases":{"a":{"status":"in_progress"}},"violations":[{"r":1},{"r":2},{"r":3}]}' \
    > "$FAKE_HOME/.arkaos/workflow-state.json"
  payload='{"model":{"display_name":"m"},"cwd":"/x","context_window":{"used_percentage":5},"cost":{"total_cost_usd":0}}'
  run bash -c "printf '%s' '$payload' | HOME='$FAKE_HOME' bash '$REPO_DIR/config/statusline.sh'"
  [ "$status" -eq 0 ]
  [[ "$output" == *"3"* ]]
}

@test "statusline omits workflow segment when no active workflow" {
  FAKE_HOME="$BATS_TEST_TMPDIR/home"
  mkdir -p "$FAKE_HOME/.arkaos"
  payload='{"model":{"display_name":"Fable 5"},"cwd":"/x/proj","context_window":{"used_percentage":10},"cost":{"total_cost_usd":0.1}}'
  run bash -c "printf '%s' '$payload' | HOME='$FAKE_HOME' bash '$REPO_DIR/config/statusline.sh'"
  [ "$status" -eq 0 ]
  [[ "$output" != *"⚑"* ]]
}

@test "statusline shows budget cap when configured" {
  FAKE_HOME="$BATS_TEST_TMPDIR/home"
  mkdir -p "$FAKE_HOME/.arkaos"
  printf '{"budget":{"hardCapUsd":20}}' > "$FAKE_HOME/.arkaos/config.json"
  payload='{"model":{"display_name":"m"},"cwd":"/x","context_window":{"used_percentage":5},"cost":{"total_cost_usd":8.5}}'
  run bash -c "printf '%s' '$payload' | HOME='$FAKE_HOME' bash '$REPO_DIR/config/statusline.sh'"
  [ "$status" -eq 0 ]
  [[ "$output" == *'$8.50/$20.00'* ]]
}

@test "statusline still produces exactly 2 lines with workflow segment" {
  FAKE_HOME="$BATS_TEST_TMPDIR/home"
  mkdir -p "$FAKE_HOME/.arkaos"
  printf '{"workflow":"wf","phases":{"a":{"status":"in_progress"}},"violations":[{"r":1}]}' \
    > "$FAKE_HOME/.arkaos/workflow-state.json"
  printf '{"budget":{"hardCapUsd":10}}' > "$FAKE_HOME/.arkaos/config.json"
  payload='{"model":{"display_name":"m"},"cwd":"/x","context_window":{"used_percentage":5},"cost":{"total_cost_usd":1}}'
  run bash -c "printf '%s' '$payload' | HOME='$FAKE_HOME' bash '$REPO_DIR/config/statusline.sh'"
  [ "$status" -eq 0 ]
  line_count=$(echo "$output" | wc -l | tr -d ' ')
  [ "$line_count" -eq 2 ]
}
