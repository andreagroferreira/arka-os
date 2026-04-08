# ArkaOS -- Standard Ecosystem Workflow

> All ecosystem skills MUST follow this workflow. No exceptions.
> This is referenced by all ecosystem SKILL.md files.

## Phase 1: Context Loading

- Read ecosystem registry (`~/.claude/skills/arka/knowledge/ecosystems.json`)
- Read project descriptor(s) for affected project(s)
- Read project CLAUDE.md if it exists
- Check git status and current branch
- Load relevant memory from claude-mem

## Phase 2: Context Verification (NON-NEGOTIABLE)

- Restate the request to confirm understanding
- Ask at least 1 clarifying question about scope or intent
- Challenge at least 1 assumption (devil's advocate)
- Search memory/knowledge base for prior related work
- Only proceed after user confirms understanding

## Phase 3: Analysis & Planning

- Identify affected projects within the ecosystem
- Determine which squad roles are needed
- Assess complexity (simple/medium/complex)
- Create execution plan with specific steps

## Phase 4: Plan Presentation & Approval

- Present the plan to the user with:
  - Affected files/projects
  - Squad roles assigned
  - Estimated scope (small/medium/large)
  - Risks or concerns
- Wait for explicit user approval
- Options: Approve / Modify / Cancel

## Phase 5: Execution

- Create feature branch (NON-NEGOTIABLE for code changes)
- Use worktree isolation for multi-file changes
- Squad agents execute in their domain
- Follow TDD where applicable
- Commit frequently with conventional commit messages

## Phase 6: Quality Gate (NON-NEGOTIABLE)

- **Marta** (CQO) orchestrates the review
- **Eduardo** (Copy Director) reviews all text output
- **Francisca** (Tech/UX Director) reviews all code and technical output
- Verdict: APPROVED or REJECTED
- REJECTED -> return to Phase 5 with specific feedback
- APPROVED -> proceed to Phase 7

## Phase 7: Documentation & Report

- Update Obsidian vault with deliverables
- Present final report to user
- Include: what was done, files changed, tests run, next steps
