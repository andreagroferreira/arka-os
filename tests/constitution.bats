#!/usr/bin/env bats
# ============================================================================
# ARKA OS — Constitution Rules + New Skills Tests
# ============================================================================

load helpers/setup

@test "constitution has 9 NON-NEGOTIABLE rules" {
  count=$(grep -c '^\d\+\.' "$REPO_DIR/CONSTITUTION.md" | head -1 || true)
  # Count numbered items under NON-NEGOTIABLE section (before MUST section)
  count=$(sed -n '/^## NON-NEGOTIABLE/,/^## MUST/p' "$REPO_DIR/CONSTITUTION.md" | grep -c '^\d\+\.')
  [ "$count" -eq 9 ]
}

@test "constitution includes solid-clean-code rule" {
  grep -q "SOLID" "$REPO_DIR/CONSTITUTION.md"
}

@test "constitution includes spec-driven rule" {
  grep -q "Spec-Driven Development" "$REPO_DIR/CONSTITUTION.md"
}

@test "constitution includes human-writing rule" {
  grep -q "Human Writing" "$REPO_DIR/CONSTITUTION.md"
}

@test "constitution L0 string includes new rules" {
  grep -q "solid-clean-code, spec-driven, human-writing, squad-routing" "$REPO_DIR/CONSTITUTION.md"
}

@test "constitution includes squad-routing rule" {
  grep -q "Squad Routing" "$REPO_DIR/CONSTITUTION.md"
}

@test "spec skill SKILL.md exists" {
  [ -f "$REPO_DIR/departments/dev/skills/spec/SKILL.md" ]
}

@test "spec skill has correct frontmatter name" {
  grep -q "name: dev-spec" "$REPO_DIR/departments/dev/skills/spec/SKILL.md"
}

@test "human-writing skill SKILL.md exists" {
  [ -f "$REPO_DIR/arka/skills/human-writing/SKILL.md" ]
}

@test "human-writing skill has correct frontmatter name" {
  grep -q "name: human-writing" "$REPO_DIR/arka/skills/human-writing/SKILL.md"
}

@test "dev SKILL.md references Phase 0 Specification" {
  grep -q "PHASE 0: SPECIFICATION" "$REPO_DIR/departments/dev/SKILL.md"
}

@test "dev SKILL.md references SOLID in self-critique" {
  grep -q "Single Responsibility" "$REPO_DIR/departments/dev/SKILL.md"
}

@test "dev SKILL.md has spec sub-skill in table" {
  grep -q "departments/dev/skills/spec/SKILL.md" "$REPO_DIR/departments/dev/SKILL.md"
}

@test "dev SKILL.md lists /dev spec commands" {
  grep -q "/dev spec <description>" "$REPO_DIR/departments/dev/SKILL.md"
  grep -q "/dev spec validate" "$REPO_DIR/departments/dev/SKILL.md"
  grep -q "/dev spec list" "$REPO_DIR/departments/dev/SKILL.md"
}

@test "arka SKILL.md has Core Skills section" {
  grep -q "Core Skills" "$REPO_DIR/arka/SKILL.md"
  grep -q "human-writing" "$REPO_DIR/arka/SKILL.md"
}

@test "commands registry includes dev-spec commands" {
  jq -e '.commands[] | select(.id == "dev-spec")' "$REPO_DIR/knowledge/commands-registry.json" > /dev/null
  jq -e '.commands[] | select(.id == "dev-spec-validate")' "$REPO_DIR/knowledge/commands-registry.json" > /dev/null
  jq -e '.commands[] | select(.id == "dev-spec-list")' "$REPO_DIR/knowledge/commands-registry.json" > /dev/null
}

@test "hook L0 injection includes new NON-NEGOTIABLE rules" {
  input='{"prompt":"hello","cwd":"/tmp","session_id":"test123"}'
  run bash -c "export ARKA_OS='$TEST_ARKA_OS' && echo '$input' | bash '$REPO_DIR/config/hooks/user-prompt-submit.sh'"
  [ "$status" -eq 0 ]
  [[ "$output" == *"solid-clean-code"* ]]
  [[ "$output" == *"spec-driven"* ]]
  [[ "$output" == *"human-writing"* ]]
  [[ "$output" == *"squad-routing"* ]]
}

@test "arka SKILL.md has Squad Routing NON-NEGOTIABLE section" {
  grep -q "Squad Routing (NON-NEGOTIABLE)" "$REPO_DIR/arka/SKILL.md"
}

@test "arka SKILL.md forbids generic assistant responses" {
  grep -q "never responds as a generic assistant" "$REPO_DIR/arka/SKILL.md"
}
