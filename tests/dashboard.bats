#!/usr/bin/env bats
# ============================================================================
# ARKA OS — Dashboard Launcher Tests (ensure mode, v4.1.2)
# ============================================================================

load helpers/setup

# Stub curl so health checks are deterministic. $1 = exit code.
stub_curl() {
  local exit_code="$1"
  mkdir -p "$TEST_HOME/.local/bin"
  cat > "$TEST_HOME/.local/bin/curl" << EOF
#!/usr/bin/env bash
exit $exit_code
EOF
  chmod +x "$TEST_HOME/.local/bin/curl"
}

write_ports_file() {
  mkdir -p "$TEST_HOME/.arkaos"
  cat > "$TEST_HOME/.arkaos/dashboard.ports" << 'EOF'
API_PORT=3338
UI_PORT=3337
EOF
}

@test "ensure mode exits 0 without restart when API and UI are healthy" {
  write_ports_file
  stub_curl 0
  HOME="$TEST_HOME" PATH="$TEST_HOME/.local/bin:$PATH" \
    run bash "$REPO_DIR/scripts/start-dashboard.sh" ensure
  [ "$status" -eq 0 ]
  [[ "$output" == *"already running"* ]]
}

@test "ensure mode falls through to full start when health check fails" {
  write_ports_file
  stub_curl 1
  # No venv in TEST_HOME, so the fall-through hits the venv guard (exit 1)
  # — proving ensure did NOT early-exit on an unhealthy dashboard.
  HOME="$TEST_HOME" PATH="$TEST_HOME/.local/bin:$PATH" \
    run bash "$REPO_DIR/scripts/start-dashboard.sh" ensure
  [ "$status" -eq 1 ]
  [[ "$output" == *"venv unavailable"* ]]
}

@test "ensure mode falls through when no ports file exists" {
  mkdir -p "$TEST_HOME/.arkaos"
  stub_curl 0
  HOME="$TEST_HOME" PATH="$TEST_HOME/.local/bin:$PATH" \
    run bash "$REPO_DIR/scripts/start-dashboard.sh" ensure
  [ "$status" -eq 1 ]
  [[ "$output" == *"venv unavailable"* ]]
}
