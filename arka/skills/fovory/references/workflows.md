# arka-fovory — workflows

Referenced from SKILL.md. Read only when needed.

## Orchestration Workflow — Enterprise (Features)

For `/fovory feature` and `/fovory forge`, follow ALL phases in order:

### Phase 0 — Specification (NON-NEGOTIABLE for code work)

Before ANY code, invoke the `arka-spec` skill to create a living spec:
1. Interactive spec creation with the user (scope, requirements, constraints)
2. User must APPROVE the spec before proceeding
3. Spec is the contract — all subsequent phases validate against it
4. Skip ONLY if user explicitly says "skip spec" or provides a pre-approved spec

### Phase 0.5 — Forge Analysis (for complex requests)

Auto-invoke The Forge (`arka-forge`) when:
- Request touches **multiple modules** (e.g., supplier driver + enrichment pipeline)
- Request involves **architecture decisions** (new patterns, data model changes)
- Request spans **multiple squads** (dev + store ops)
- User explicitly calls `/fovory forge <description>`

The Forge provides:
- Complexity scoring across 5 dimensions
- 3 parallel explorer subagents (Pragmatic, Architectural, Contrarian)
- Critic synthesis with risk identification
- Approved ForgePlan before execution begins

Skip when: simple features, single-module changes, or user says "skip forge".

### Phase 1 — Context Loading
1. Read the ecosystem registry: `~/.claude/skills/arka/knowledge/ecosystems.json`
2. Read project file: `~/.claude/skills/arka/projects/fovory-supplier-sync/PROJECT.md`
3. Read CLAUDE.md from `~/Herd/fovory-supplier-sync/CLAUDE.md` (if code work)
4. Identify whether request is **code** (routes to dev squad) or **store ops** (routes to ops/marketing squad)

### Phase 2 — Analysis & Planning

**Before planning, verify context:**
- Restate the request to confirm understanding
- Ask at least 1 clarifying question about scope or intent
- Challenge at least 1 assumption (devil's advocate)
- Check memory/knowledge base for prior related work

1. Analyze the request against ecosystem context (and Forge output if available)
2. Determine which squad roles are needed
3. Create a detailed execution plan with:
   - **Request summary**
   - **Affected area** (supplier-sync codebase / Shopify store / both)
   - **Squad members involved** (which roles)
   - **Steps** (numbered, with responsible role)
   - **Risks/considerations**
   - **Estimated scope** (files to change, tests to write)

### Phase 3 — Plan Presentation & Approval
1. Present the plan to the user:

```
=== Fovory — Execution Plan ===

WORKFLOW: [Enterprise / Focused / Specialist]

REQUEST: [summary]

SPEC: [spec reference or "inline"]

AFFECTED:
  - [fovory-supplier-sync / Shopify store / both]

SQUAD:
  - [role] — [responsibility in this task]

STEPS:
  1. [step] — [role]
  2. [step] — [role]
  ...

CONSIDERATIONS:
  - [risk/note]

================================
```

2. Ask for user approval:
   - "Approve plan and proceed?"
   - Options: "Approve", "Modify", "Cancel"

### Phase 4 — Execution
1. Only proceed after approval
2. **Code changes**: Use worktree isolation (NON-NEGOTIABLE)
3. Each squad role runs as the appropriate agent type
4. Follow project conventions from CLAUDE.md strictly:
   - UDashboardPanel layout pattern (never raw divs)
   - UModal for forms (never USlideover)
   - Dropzone for file uploads (never native inputs)
   - `bun run build` (never npm)
   - Always paginate lists
   - Pest tests + Playwright E2E mandatory
5. Run `vendor/bin/pint --dirty --format agent` after PHP changes
6. Run `php artisan test --compact` to verify

### Phase 5 — Self-Critique & Security Audit
1. **Self-Critique**: Review own implementation against the spec — identify gaps, edge cases, missed requirements
2. **Security Audit** (for code work): Check against OWASP Top 10, validate input sanitization, auth/authz, SQL injection, XSS
3. Fix any issues found before proceeding to Quality Gate

### Phase 6 — Quality Gate (NON-NEGOTIABLE)

**Marta** (CQO) dispatches **Eduardo** and **Francisca** IN PARALLEL:

**Eduardo** (Copy Director) checks:
- Spelling errors, grammar mistakes
- Wrong accentuation (critical for pt-PT)
- AI cliches (no "leverage", "utilize", "streamline", "robust")
- Tone consistency across all text output
- Culturally appropriate language

**Francisca** (Tech/UX Director) checks:
- SOLID principles and Clean Code compliance
- Test coverage (target: >=80%)
- OWASP Top 10 security
- Core Web Vitals and performance
- UX/WCAG AA accessibility
- Data integrity and product data accuracy
- For store ops: pricing accuracy, translations, images, inventory sync

**Verdict:** APPROVED or REJECTED. Binary, no caveats, no exceptions.
- APPROVED → proceed to Documentation phase
- REJECTED → return to Execution phase with specific feedback, fix, re-submit

### Phase 7 — Documentation & Report
1. Update Obsidian documentation if significant
2. Present execution report:

```
=== Fovory — Execution Report ===

WORKFLOW: [Enterprise / Focused / Specialist]

COMPLETED:
  - [what was done]

FILES CHANGED:
  - [files]

TESTS:
  - [test results — X passed / Y assertions]

QUALITY GATE:
  - Eduardo: [APPROVED/REJECTED — notes]
  - Francisca: [APPROVED/REJECTED — notes]

DOCS UPDATED:
  - [obsidian pages updated]

=================================
```

## Orchestration Workflow — Focused (Bugs, Refactors, Store Ops)

For `/fovory debug`, `/fovory refactor`, and store operation commands:
- Skip Phase 0 (Spec) and Phase 0.5 (Forge)
- Follow Phases: **1 → 2 → 3 → 4 → 5 → 6 → 7**
- Phase 5 (Self-Critique) focuses on root cause validation (bugs) or data accuracy (store ops)

## Orchestration Workflow — Specialist (Reviews, Tests)

For `/fovory review`, `/fovory test`:
- Skip Phases 0, 0.5, 1, 2, 3
- Follow Phases: **4 → 6 → 7** (Execute → Quality Gate → Report)
- Direct execution with quality validation

## /fovory status

Check the status of the ecosystem:

```bash
# fovory-supplier-sync
cd ~/Herd/fovory-supplier-sync
git status
git log --oneline -5
git branch --show-current
php artisan test --compact 2>&1 | tail -3
```

Present as:

```
=== Fovory — Ecosystem Status ===

CODE: fovory-supplier-sync (Laravel 13 + Vue 3)
  Branch: [branch]
  Last commit: [hash] — [message] ([date])
  Status: [clean/uncommitted changes]
  Tests: [X passed / Y assertions]

STORE: Fovory Shopify
  [Shopify MCP status if available]

==================================
```

## /fovory context

Show full ecosystem context:
1. Read all project files and CLAUDE.md
2. Present architecture, tech stack, modules, conventions, current state
