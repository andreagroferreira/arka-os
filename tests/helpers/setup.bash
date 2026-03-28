#!/usr/bin/env bash
# ============================================================================
# ARKA OS — Bats Test Helpers
# Common setup/teardown for all test files
# ============================================================================

# Create temp directories for test isolation
setup() {
  export TEST_TEMP_DIR="$(mktemp -d)"
  export TEST_HOME="$TEST_TEMP_DIR/home"
  export TEST_ARKA_OS="$TEST_HOME/.claude/skills/arka"
  export TEST_AGENTS_DIR="$TEST_HOME/.claude/agents"
  export TEST_ARKA_CONFIG="$TEST_HOME/.arka-os"

  # Clear hook cache to prevent stale L0 strings from previous runs
  rm -f /tmp/arka-context-cache/constitution 2>/dev/null

  mkdir -p "$TEST_ARKA_OS/hooks" "$TEST_ARKA_OS/knowledge" "$TEST_ARKA_OS/mcps"
  mkdir -p "$TEST_AGENTS_DIR"
  mkdir -p "$TEST_ARKA_CONFIG"
  mkdir -p "$TEST_HOME/.local/bin"
  mkdir -p "$TEST_HOME/.claude/agent-memory"

  # Point to repo source
  export REPO_DIR="$(cd "$(dirname "${BATS_TEST_FILENAME}")/.." && pwd)"
  echo "$REPO_DIR" > "$TEST_ARKA_OS/.repo-path"

  # Copy VERSION
  cp "$REPO_DIR/VERSION" "$TEST_ARKA_OS/VERSION"
}

teardown() {
  rm -rf "$TEST_TEMP_DIR"
}

# Helper: create a mock settings.json
create_mock_settings() {
  local settings_file="$TEST_HOME/.claude/settings.json"
  cat > "$settings_file" << 'EOF'
{
  "statusLine": {
    "type": "command",
    "command": "/mock/statusline.sh",
    "padding": 2
  },
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/mock/hooks/user-prompt-submit.sh",
            "timeout": 10
          }
        ]
      }
    ],
    "PreCompact": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/mock/hooks/pre-compact.sh",
            "timeout": 30
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/mock/hooks/post-tool-use.sh",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
EOF
}

# Helper: create mock agent files
create_mock_agents() {
  local count="${1:-19}"
  local agents=("cto" "tech-lead" "architect" "senior-dev" "frontend-dev" "security" "devops" "qa" "analyst" "cfo" "coo" "content-creator" "ecommerce-manager" "strategist" "knowledge-curator" "creative-director" "brand-strategist" "visual-designer" "motion-designer")
  for i in $(seq 0 $((count - 1))); do
    echo "---" > "$TEST_AGENTS_DIR/arka-${agents[$i]}.md"
    echo "name: ${agents[$i]}" >> "$TEST_AGENTS_DIR/arka-${agents[$i]}.md"
    echo "---" >> "$TEST_AGENTS_DIR/arka-${agents[$i]}.md"
  done
}

# Helper: create mock gotchas.json
create_mock_gotchas() {
  cat > "$TEST_ARKA_CONFIG/gotchas.json" << 'EOF'
[
  {
    "pattern": "Error: ENOENT file not found",
    "full_pattern": "Error: ENOENT: no such file or directory",
    "category": "general",
    "tool": "Bash",
    "count": 5,
    "first_seen": "2026-03-15T10:00:00Z",
    "last_seen": "2026-03-16T10:00:00Z",
    "projects": ["test-project"]
  }
]
EOF
}

# Helper: create mock kb-jobs.json
create_mock_kb_jobs() {
  mkdir -p "$TEST_ARKA_CONFIG"
  cat > "$TEST_ARKA_CONFIG/kb-jobs.json" << 'EOF'
{
  "jobs": [
    {
      "id": "abc12345",
      "url": "https://youtube.com/watch?v=test",
      "output_dir": "/tmp/test-media/abc12345",
      "transcription_method": "local-whisper",
      "persona": "Test Persona",
      "status": "ready",
      "title": "Test Video Title",
      "word_count": 1500,
      "error": null,
      "pid": null,
      "created_at": "2026-03-15T10:00:00Z",
      "updated_at": "2026-03-15T10:30:00Z"
    }
  ]
}
EOF
}

# Helper: create mock kb-jobs.json with dead PID
create_mock_kb_jobs_with_dead_pid() {
  mkdir -p "$TEST_ARKA_CONFIG"
  cat > "$TEST_ARKA_CONFIG/kb-jobs.json" << 'EOF'
{
  "jobs": [
    {
      "id": "dead1234",
      "url": "https://youtube.com/watch?v=dead",
      "output_dir": "/tmp/test-media/dead1234",
      "transcription_method": "local-whisper",
      "persona": "",
      "status": "downloading",
      "title": null,
      "word_count": null,
      "error": null,
      "pid": 99999,
      "created_at": "2026-03-15T10:00:00Z",
      "updated_at": "2026-03-15T10:00:00Z"
    }
  ]
}
EOF
}

# Helper: create mock media directory
create_mock_media_dir() {
  local date_dir="$TEST_ARKA_CONFIG/media/2025-01-01"
  mkdir -p "$date_dir/abc12345"
  echo "mock audio" > "$date_dir/abc12345/audio.wav"
  echo "mock transcript" > "$date_dir/abc12345/audio.txt"
  echo '{"title": "Test"}' > "$date_dir/abc12345/metadata.json"
}

# Helper: create mock MCP registry
create_mock_mcp_registry() {
  cp "$REPO_DIR/mcps/registry.json" "$TEST_TEMP_DIR/registry.json"
}
