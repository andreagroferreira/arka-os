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

@test "statusline shows the violations warning glyph, not just a digit" {
  FAKE_HOME="$BATS_TEST_TMPDIR/home"
  mkdir -p "$FAKE_HOME/.arkaos"
  printf '{"workflow":"wf","phases":{"a":{"status":"in_progress"}},"violations":[{"r":1},{"r":2},{"r":3}]}' \
    > "$FAKE_HOME/.arkaos/workflow-state.json"
  payload='{"model":{"display_name":"m"},"cwd":"/x","context_window":{"used_percentage":5},"cost":{"total_cost_usd":0}}'
  run bash -c "printf '%s' '$payload' | HOME='$FAKE_HOME' bash '$REPO_DIR/config/statusline.sh'"
  [ "$status" -eq 0 ]
  # The warning glyph + count, not a bare digit that could be the gate.
  [[ "$output" == *"3"* ]]
  [[ "$output" == *$'\xe2\x9a\xa0'* ]]
}

@test "QG B1: violations warning survives the no-in_progress state" {
  # Completed workflow (no in_progress phase) with violations: the tab
  # delimiter used to collapse the empty gate field and DROP the warning.
  FAKE_HOME="$BATS_TEST_TMPDIR/home"
  mkdir -p "$FAKE_HOME/.arkaos"
  printf '{"workflow":"wf","phases":{"a":{"status":"completed"}},"violations":[{"r":1},{"r":2},{"r":3},{"r":4}]}' \
    > "$FAKE_HOME/.arkaos/workflow-state.json"
  payload='{"model":{"display_name":"m"},"cwd":"/x","context_window":{"used_percentage":5},"cost":{"total_cost_usd":0}}'
  run bash -c "printf '%s' '$payload' | HOME='$FAKE_HOME' bash '$REPO_DIR/config/statusline.sh'"
  [ "$status" -eq 0 ]
  [[ "$output" == *$'\xe2\x9a\xa0'*"4"* ]]    # warning present with count 4
  # ANSI colours sit between fields, so match "G1/1" alone (not "wf G1/1").
  [[ "$output" == *"G1/1"* ]]                     # gate clamped to 1, NOT 4
}

@test "QG B4: a workflow name with escape/newline never breaks 2 lines" {
  FAKE_HOME="$BATS_TEST_TMPDIR/home"
  mkdir -p "$FAKE_HOME/.arkaos"
  printf '{"workflow":"evil\u001b[31mX\ninjected","phases":{"a":{"status":"in_progress"}},"violations":[]}' \
    > "$FAKE_HOME/.arkaos/workflow-state.json"
  payload='{"model":{"display_name":"m"},"cwd":"/x","context_window":{"used_percentage":5},"cost":{"total_cost_usd":0}}'
  run bash -c "printf '%s' '$payload' | HOME='$FAKE_HOME' bash '$REPO_DIR/config/statusline.sh'"
  [ "$status" -eq 0 ]
  line_count=$(printf '%s' "$output" | grep -c '')
  [ "$line_count" -eq 2 ]
}

@test "QG M2: gate index is positional, not grepped from the phase name" {
  # in_progress phase named "gate-5-x" but at position 3 of 3 -> G3/3.
  FAKE_HOME="$BATS_TEST_TMPDIR/home"
  mkdir -p "$FAKE_HOME/.arkaos"
  printf '{"workflow":"wf","phases":{"a":{"status":"completed"},"b":{"status":"completed"},"gate-5-x":{"status":"in_progress"}},"violations":[]}' \
    > "$FAKE_HOME/.arkaos/workflow-state.json"
  payload='{"model":{"display_name":"m"},"cwd":"/x","context_window":{"used_percentage":5},"cost":{"total_cost_usd":0}}'
  run bash -c "printf '%s' '$payload' | HOME='$FAKE_HOME' bash '$REPO_DIR/config/statusline.sh'"
  [ "$status" -eq 0 ]
  [[ "$output" == *"G3/3"* ]]
  [[ "$output" != *"G5"* ]]
}

@test "QG M4: a non-numeric budget cap is omitted, not rendered as 0.00" {
  FAKE_HOME="$BATS_TEST_TMPDIR/home"
  mkdir -p "$FAKE_HOME/.arkaos"
  printf '{"budget":{"hardCapUsd":"lots"}}' > "$FAKE_HOME/.arkaos/config.json"
  payload='{"model":{"display_name":"m"},"cwd":"/x","context_window":{"used_percentage":5},"cost":{"total_cost_usd":8.5}}'
  run bash -c "printf '%s' '$payload' | HOME='$FAKE_HOME' bash '$REPO_DIR/config/statusline.sh'"
  [ "$status" -eq 0 ]
  [[ "$output" != *"/\$"* ]]
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
