#!/usr/bin/env bats
# ============================================================================
# ARKA OS — Constitution Rules + New Skills Tests
# ============================================================================

load helpers/setup

@test "constitution has 13 NON-NEGOTIABLE rules" {
  count=$(grep -c '^\d\+\.' "$REPO_DIR/CONSTITUTION.md" | head -1 || true)
  # Count numbered items under NON-NEGOTIABLE section (before Quality Gate section)
  count=$(sed -n '/^## NON-NEGOTIABLE/,/^## Quality Gate/p' "$REPO_DIR/CONSTITUTION.md" | grep -c '^\d\+\.')
  [ "$count" -eq 13 ]
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
  grep -q "solid-clean-code, spec-driven, human-writing, squad-routing, full-visibility, sequential-validation, mandatory-qa, arka-supremacy" "$REPO_DIR/CONSTITUTION.md"
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

@test "constitution includes full-visibility rule" {
  grep -q "Full Visibility" "$REPO_DIR/CONSTITUTION.md"
}

@test "constitution includes sequential-validation rule" {
  grep -q "Sequential Task Validation" "$REPO_DIR/CONSTITUTION.md"
}

@test "constitution includes mandatory-qa rule" {
  grep -q "Mandatory Complete QA" "$REPO_DIR/CONSTITUTION.md"
}

@test "constitution includes arka-supremacy rule" {
  grep -q "ARKA OS Supremacy" "$REPO_DIR/CONSTITUTION.md"
}

@test "constitution has Quality Gate section" {
  grep -q "## Quality Gate (Mandatory)" "$REPO_DIR/CONSTITUTION.md"
}

@test "constitution Quality Gate names all 3 supervisors" {
  grep -q "Marta (CQO" "$REPO_DIR/CONSTITUTION.md"
  grep -q "Eduardo (Copy" "$REPO_DIR/CONSTITUTION.md"
  grep -q "Francisca (Technical" "$REPO_DIR/CONSTITUTION.md"
}

@test "quality gate agent files exist" {
  [ -f "$REPO_DIR/departments/quality/agents/cqo.md" ]
  [ -f "$REPO_DIR/departments/quality/agents/copy-director.md" ]
  [ -f "$REPO_DIR/departments/quality/agents/tech-ux-director.md" ]
}

@test "quality gate agents are tier 0" {
  grep -q "tier: 0" "$REPO_DIR/departments/quality/agents/cqo.md"
  grep -q "tier: 0" "$REPO_DIR/departments/quality/agents/copy-director.md"
  grep -q "tier: 0" "$REPO_DIR/departments/quality/agents/tech-ux-director.md"
}

@test "quality gate agents have veto authority" {
  grep -q "veto: true" "$REPO_DIR/departments/quality/agents/cqo.md"
  grep -q "veto: true" "$REPO_DIR/departments/quality/agents/copy-director.md"
  grep -q "veto: true" "$REPO_DIR/departments/quality/agents/tech-ux-director.md"
}

@test "quality gate agents have DISC profiles" {
  grep -q 'combination: "C+D"' "$REPO_DIR/departments/quality/agents/cqo.md"
  grep -q 'combination: "C+S"' "$REPO_DIR/departments/quality/agents/copy-director.md"
  grep -q 'combination: "D+C"' "$REPO_DIR/departments/quality/agents/tech-ux-director.md"
}

@test "agents-registry.json has 22 agents" {
  count=$(jq '.agents | length' "$REPO_DIR/knowledge/agents-registry.json")
  [ "$count" -eq 22 ]
}

@test "agents-registry.json includes quality department" {
  jq -e '.agents[] | select(.department == "quality")' "$REPO_DIR/knowledge/agents-registry.json" > /dev/null
  count=$(jq '[.agents[] | select(.department == "quality")] | length' "$REPO_DIR/knowledge/agents-registry.json")
  [ "$count" -eq 3 ]
}

@test "hook L0 injection includes quality gate and new rules" {
  input='{"prompt":"hello","cwd":"/tmp","session_id":"test123"}'
  run bash -c "export ARKA_OS='$TEST_ARKA_OS' && echo '$input' | bash '$REPO_DIR/config/hooks/user-prompt-submit.sh'"
  [ "$status" -eq 0 ]
  [[ "$output" == *"full-visibility"* ]]
  [[ "$output" == *"sequential-validation"* ]]
  [[ "$output" == *"mandatory-qa"* ]]
  [[ "$output" == *"arka-supremacy"* ]]
  [[ "$output" == *"QUALITY-GATE"* ]]
}

@test "dev SKILL.md has Quality Gate phase" {
  grep -q "PHASE 8: QUALITY GATE" "$REPO_DIR/departments/dev/SKILL.md"
}

@test "dev SKILL.md has 10-phase workflow" {
  grep -q "10 phases" "$REPO_DIR/departments/dev/SKILL.md"
}
