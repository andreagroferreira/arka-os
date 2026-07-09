#!/usr/bin/env bats
# ============================================================================
# ARKA OS — Constitution Rules + New Skills Tests
# ============================================================================

load helpers/setup

@test "constitution has 6 NON-NEGOTIABLE rules" {
  # Constitution 2.0 (PR-5, 2026-07-08): 26 -> 6 by the gate-verifiability
  # admission test; 16 -> MUST, 4 -> SHOULD.
  count=$(sed -n '/^## NON-NEGOTIABLE/,/^## Quality Gate/p' "$REPO_DIR/CONSTITUTION.md" | grep -c '^[0-9]\+\.')
  [ "$count" -eq 6 ]
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

@test "constitution L0 string includes the Constitution 2.0 top-level rules" {
  grep -q "branch-isolation, security-gate, mandatory-qa, evidence-flow, arkaos-not-yes-man, excellence-mandate" "$REPO_DIR/CONSTITUTION.md"
}

@test "constitution includes squad-routing rule" {
  grep -q "Squad Routing" "$REPO_DIR/CONSTITUTION.md"
}

@test "spec skill SKILL.md exists" {
  [ -f "$REPO_DIR/departments/dev/skills/spec/SKILL.md" ]
}

@test "spec skill has correct frontmatter name" {
  grep -q "name: arka-dev-spec" "$REPO_DIR/departments/dev/skills/spec/SKILL.md"
}

@test "human-writing skill SKILL.md exists" {
  [ -f "$REPO_DIR/arka/skills/human-writing/SKILL.md" ]
}

@test "human-writing skill has correct frontmatter name" {
  grep -q "name: arka-human-writing" "$REPO_DIR/arka/skills/human-writing/SKILL.md"
}

@test "dev SKILL.md references Phase 0 Specification" {
  grep -q "Phase 0: SPECIFICATION" "$REPO_DIR/departments/dev/SKILL.md"
}

@test "dev SKILL.md references SOLID in self-critique" {
  grep -q "SELF-CRITIQUE" "$REPO_DIR/departments/dev/SKILL.md"
  grep -q "Clean Code + SOLID" "$REPO_DIR/departments/dev/SKILL.md"
}

@test "dev SKILL.md has spec command in table" {
  grep -q "/dev spec <description>" "$REPO_DIR/departments/dev/SKILL.md"
}

@test "dev spec commands live in the commands registry" {
  jq -e '.commands[] | select(.id == "dev-spec-validate")' "$REPO_DIR/knowledge/commands-registry.json" > /dev/null
  jq -e '.commands[] | select(.id == "dev-spec-list")' "$REPO_DIR/knowledge/commands-registry.json" > /dev/null
}

@test "arka SKILL.md has System Commands and KB-first doctrine" {
  grep -q "## System Commands" "$REPO_DIR/arka/SKILL.md"
  grep -q "## KB-First Research" "$REPO_DIR/arka/SKILL.md"
}

@test "commands registry includes dev-spec commands" {
  jq -e '.commands[] | select(.id == "dev-spec")' "$REPO_DIR/knowledge/commands-registry.json" > /dev/null
  jq -e '.commands[] | select(.id == "dev-spec-validate")' "$REPO_DIR/knowledge/commands-registry.json" > /dev/null
  jq -e '.commands[] | select(.id == "dev-spec-list")' "$REPO_DIR/knowledge/commands-registry.json" > /dev/null
}

@test "hook L0 injection includes the Constitution 2.0 top-level rules" {
  # Constitution 2.0 (PR-5, 2026-07-08): 6 NON-NEGOTIABLE; squad-routing
  # and spec-driven now appear in the MUST excerpt of the L0 string.
  # ARKA_HOOK_FORCE_FALLBACK -> deterministic bash fallback content.
  input='{"prompt":"hello","cwd":"/tmp","session_id":"test123"}'
  run bash -c "export ARKA_OS='$TEST_ARKA_OS' ARKA_HOOK_FORCE_FALLBACK=1 && echo '$input' | bash '$REPO_DIR/config/hooks/user-prompt-submit.sh'"
  [ "$status" -eq 0 ]
  [[ "$output" == *"branch-isolation"* ]]
  [[ "$output" == *"evidence-flow"* ]]
  [[ "$output" == *"excellence-mandate"* ]]
  [[ "$output" == *"squad-routing"* ]]
}

@test "arka SKILL.md has Squad Routing MUST section" {
  # Constitution 2.0 (PR-5, 2026-07-08): squad-routing demoted to MUST.
  grep -q "Squad Routing (MUST)" "$REPO_DIR/arka/SKILL.md"
}

@test "arka SKILL.md forbids generic assistant responses" {
  grep -q "as a generic assistant" "$REPO_DIR/arka/SKILL.md"
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
  grep -q "Francisca (Tech" "$REPO_DIR/CONSTITUTION.md"
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

@test "agents-registry-v2.json agent count matches _meta.total_agents" {
  count=$(jq '.agents | length' "$REPO_DIR/knowledge/agents-registry-v2.json")
  meta=$(jq '._meta.total_agents' "$REPO_DIR/knowledge/agents-registry-v2.json")
  [ "$count" -eq "$meta" ]
  [ "$count" -ge 60 ]
}

@test "agents-registry-v2.json includes quality department" {
  jq -e '.agents[] | select(.department == "quality")' "$REPO_DIR/knowledge/agents-registry-v2.json" > /dev/null
  count=$(jq '[.agents[] | select(.department == "quality")] | length' "$REPO_DIR/knowledge/agents-registry-v2.json")
  [ "$count" -eq 3 ]
}

@test "hook L0 injection includes quality gate and new rules" {
  # Constitution 2.0 (PR-5): full-visibility/sequential-validation/
  # arka-supremacy demoted to MUST and no longer in the L0 excerpt.
  # ARKA_HOOK_FORCE_FALLBACK -> deterministic bash fallback content.
  input='{"prompt":"hello","cwd":"/tmp","session_id":"test123"}'
  run bash -c "export ARKA_OS='$TEST_ARKA_OS' ARKA_HOOK_FORCE_FALLBACK=1 && echo '$input' | bash '$REPO_DIR/config/hooks/user-prompt-submit.sh'"
  [ "$status" -eq 0 ]
  [[ "$output" == *"mandatory-qa"* ]]
  [[ "$output" == *"arkaos-not-yes-man"* ]]
  [[ "$output" == *"persona-vs-artifact"* ]]
  [[ "$output" == *"QUALITY-GATE"* ]]
}

@test "dev SKILL.md has Quality Gate phase" {
  grep -q "QUALITY GATE" "$REPO_DIR/departments/dev/SKILL.md"
}

@test "dev SKILL.md has 10-phase workflow" {
  grep -q "10 Phases" "$REPO_DIR/departments/dev/SKILL.md"
}
