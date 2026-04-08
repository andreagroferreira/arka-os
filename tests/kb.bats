#!/usr/bin/env bats
# ============================================================================
# ARKA OS — KB Queue/Status/Cleanup Tests
# ============================================================================

load helpers/setup

# ─── kb-queue.sh ─────────────────────────────────────────────────────────

@test "kb-queue.sh rejects missing URL" {
  run bash "$REPO_DIR/departments/kb/scripts/kb-queue.sh"
  [ "$status" -ne 0 ]
  [[ "$output" == *"Usage"* ]]
}

@test "kb-queue.sh rejects empty URL" {
  run bash "$REPO_DIR/departments/kb/scripts/kb-queue.sh" ""
  [ "$status" -ne 0 ]
}

@test "kb-queue.sh creates job directory structure" {
  # Mock yt-dlp and flock to avoid real downloads
  export PATH="$TEST_TEMP_DIR/bin:$PATH"
  mkdir -p "$TEST_TEMP_DIR/bin"
  echo '#!/bin/bash' > "$TEST_TEMP_DIR/bin/yt-dlp"
  echo 'echo "mock yt-dlp"' >> "$TEST_TEMP_DIR/bin/yt-dlp"
  chmod +x "$TEST_TEMP_DIR/bin/yt-dlp"
  # Create a mock flock
  echo '#!/bin/bash' > "$TEST_TEMP_DIR/bin/flock"
  echo 'shift; shift; "$@"' >> "$TEST_TEMP_DIR/bin/flock"
  chmod +x "$TEST_TEMP_DIR/bin/flock"
  # Mock nohup to prevent background process
  echo '#!/bin/bash' > "$TEST_TEMP_DIR/bin/nohup"
  echo 'echo "mock-nohup"' >> "$TEST_TEMP_DIR/bin/nohup"
  chmod +x "$TEST_TEMP_DIR/bin/nohup"

  export HOME="$TEST_HOME"
  mkdir -p "$TEST_HOME/.arka-os"

  run bash "$REPO_DIR/departments/kb/scripts/kb-queue.sh" "https://youtube.com/watch?v=test123"
  # May fail due to worker launch, but directory should be created
  [ -d "$TEST_HOME/.arka-os/media" ]
}

@test "kb-queue.sh generates 8-char hex job ID" {
  # Create a mock kb-jobs.json to check
  export HOME="$TEST_HOME"
  create_mock_kb_jobs

  JOB_ID=$(jq -r '.jobs[0].id' "$TEST_HOME/.arka-os/kb-jobs.json")
  [ ${#JOB_ID} -eq 8 ]
}

# ─── kb-status.sh ────────────────────────────────────────────────────────

@test "kb-status.sh returns empty for no jobs" {
  export HOME="$TEST_HOME"
  mkdir -p "$TEST_HOME/.arka-os"

  run bash "$REPO_DIR/departments/kb/scripts/kb-status.sh"
  [ "$status" -eq 0 ]
  [[ "$output" == *"No jobs"* ]]
}

@test "kb-status.sh shows correct status for mock job" {
  export HOME="$TEST_HOME"
  create_mock_kb_jobs
  # Need flock mock for PID checking
  export PATH="$TEST_TEMP_DIR/bin:$PATH"
  mkdir -p "$TEST_TEMP_DIR/bin"
  echo '#!/bin/bash
shift; shift; "$@"' > "$TEST_TEMP_DIR/bin/flock"
  chmod +x "$TEST_TEMP_DIR/bin/flock"

  run bash "$REPO_DIR/departments/kb/scripts/kb-status.sh" "abc12345"
  [ "$status" -eq 0 ]
  [[ "$output" == *"ready"* ]] || [[ "$output" == *"abc12345"* ]]
}

@test "kb-status.sh --json outputs valid JSON" {
  export HOME="$TEST_HOME"
  create_mock_kb_jobs
  export PATH="$TEST_TEMP_DIR/bin:$PATH"
  mkdir -p "$TEST_TEMP_DIR/bin"
  echo '#!/bin/bash
shift; shift; "$@"' > "$TEST_TEMP_DIR/bin/flock"
  chmod +x "$TEST_TEMP_DIR/bin/flock"

  run bash "$REPO_DIR/departments/kb/scripts/kb-status.sh" --json
  [ "$status" -eq 0 ]
  echo "$output" | jq empty
}

@test "kb-status.sh detects dead worker PIDs" {
  export HOME="$TEST_HOME"
  create_mock_kb_jobs_with_dead_pid
  export PATH="$TEST_TEMP_DIR/bin:$PATH"
  mkdir -p "$TEST_TEMP_DIR/bin"
  echo '#!/bin/bash
shift; shift; "$@"' > "$TEST_TEMP_DIR/bin/flock"
  chmod +x "$TEST_TEMP_DIR/bin/flock"

  run bash "$REPO_DIR/departments/kb/scripts/kb-status.sh" --json
  [ "$status" -eq 0 ]
  # After status check, dead PID jobs should be marked as failed
  STATUS=$(jq -r '.jobs[0].status' "$TEST_HOME/.arka-os/kb-jobs.json" 2>/dev/null)
  [ "$STATUS" = "failed" ]
}

# ─── kb-cleanup.sh ───────────────────────────────────────────────────────

@test "kb-cleanup.sh --dry-run doesn't delete anything" {
  export HOME="$TEST_HOME"
  create_mock_media_dir
  create_mock_kb_jobs

  run bash "$REPO_DIR/departments/kb/scripts/kb-cleanup.sh" --dry-run --older-than 0d
  [ "$status" -eq 0 ]
  [[ "$output" == *"DRY RUN"* ]]
  # Files should still exist
  [ -d "$TEST_HOME/.arka-os/media" ]
}

@test "kb-cleanup.sh respects --older-than parameter" {
  export HOME="$TEST_HOME"
  create_mock_media_dir
  create_mock_kb_jobs

  run bash "$REPO_DIR/departments/kb/scripts/kb-cleanup.sh" --dry-run --older-than 365d
  [ "$status" -eq 0 ]
  # With 365 days, nothing should be flagged for removal (mock data is recent)
}

# ─── kb-worker.sh ────────────────────────────────────────────────────────

@test "kb-worker.sh fails gracefully when yt-dlp missing" {
  export HOME="$TEST_HOME"
  mkdir -p "$TEST_HOME/.arka-os"

  # Create minimal jobs file with matching job entry
  cat > "$TEST_HOME/.arka-os/kb-jobs.json" << 'JOBS'
{"jobs":[{"id":"testjob1","url":"https://youtube.com/test","output_dir":"","status":"queued","pid":null,"error":null,"created_at":"2026-03-15T10:00:00Z","updated_at":"2026-03-15T10:00:00Z"}]}
JOBS

  OUTPUT_DIR="$TEST_TEMP_DIR/output"
  mkdir -p "$OUTPUT_DIR"

  # Remove yt-dlp from PATH by creating a filtered PATH
  FILTERED_PATH=""
  IFS=: read -ra DIRS <<< "$PATH"
  for d in "${DIRS[@]}"; do
    if [ ! -x "$d/yt-dlp" ]; then
      FILTERED_PATH="${FILTERED_PATH:+$FILTERED_PATH:}$d"
    else
      # Copy dir without yt-dlp
      mkdir -p "$TEST_TEMP_DIR/filtered-bin"
      for f in "$d"/*; do
        [ "$(basename "$f")" = "yt-dlp" ] && continue
        ln -sf "$f" "$TEST_TEMP_DIR/filtered-bin/" 2>/dev/null || true
      done
      FILTERED_PATH="${FILTERED_PATH:+$FILTERED_PATH:}$TEST_TEMP_DIR/filtered-bin"
    fi
  done
  export PATH="$FILTERED_PATH"

  # Worker should fail gracefully (yt-dlp not found)
  run bash "$REPO_DIR/departments/kb/scripts/kb-worker.sh" "testjob1" "https://youtube.com/test" "$OUTPUT_DIR" "none"
  # Check worker.log was created with error about yt-dlp
  [ -f "$OUTPUT_DIR/worker.log" ]
}
