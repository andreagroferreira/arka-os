# arka-rothbard100 — workflows

Referenced from SKILL.md. Read only when needed.

## Orchestration Workflow (Standard — 8 Phases)

For EVERY `/rothbard100` request that modifies code or content:

### Phase 1 — Context Loading
1. Read the ecosystem registry: `~/.claude/skills/arka/knowledge/ecosystems.json`
2. Read project files: `~/.claude/skills/arka/projects/rothbard100-landing/PROJECT.md`
3. Read CLAUDE.md from affected project
4. Check memory for prior related work and user feedback

### Phase 2 — Analysis & Planning

**Before planning, verify context:**
- Restate the request to confirm understanding
- Ask at least 1 clarifying question about scope or intent
- Challenge at least 1 assumption (devil's advocate)

1. Analyze the request against the ecosystem context
2. Determine complexity tier (Quick / Standard / Complex)
3. If Complex → route to `/arka-forge` for multi-perspective planning
4. Determine which squad roles are needed
5. Create execution plan with:
   - **Affected projects** (which ones)
   - **Squad members involved** (which roles)
   - **Steps** (numbered, with responsible role)
   - **Risks/considerations** (cross-project impact, brand consistency, event deadlines)
   - **Estimated scope** (files to change)

### Phase 3 — Specification (for features/new components)
If the task creates new functionality:
1. Define acceptance criteria (testable, BDD-style)
2. Define scope (in scope / out of scope)
3. Define edge cases
4. User approves spec before implementation

For bug fixes, refactors, content updates, and config changes: skip this phase.

### Phase 4 — Plan Presentation & Approval
Present the plan:

```
═══ ROTHBARD 100 — Execution Plan ═══

📋 REQUEST: [summary of what was asked]
🔧 COMPLEXITY: [Quick / Standard / Complex]

🎯 AFFECTED PROJECTS:
  • [project] — [what changes]

👥 SQUAD:
  • [role] — [responsibility in this task]

📝 STEPS:
  1. [step] — [role]
  2. [step] — [role]
  ...

⚠️ CONSIDERATIONS:
  • [risk/note]

═══════════════════════════════
```

Ask for user approval: "Approve", "Modify", or "Cancel"

### Phase 5 — Execution
1. Only proceed after approval
2. Execute using **worktree isolation** for code changes (NON-NEGOTIABLE)
3. Each squad role runs as the appropriate agent type (dispatch real agents)
4. Content Creator adapts all text — never mechanical copy-paste
5. Cross-project changes are coordinated

### Phase 6 — Self-Critique (NON-NEGOTIABLE)
Before quality gate, the executing agent(s) must:
1. Review own output against the plan and spec
2. Check for regressions, missing edge cases, i18n consistency
3. Verify build passes (`pnpm build`)
4. Flag any concerns or deviations from plan

### Phase 7 — Quality Gate (NON-NEGOTIABLE)

Before any output reaches the user:
- **Marta** (CQO) orchestrates the review
- **Eduardo** (Copy Director) reviews all text output for spelling, grammar, tone, clarity, AI patterns
- **Francisca** (Tech/UX Director) reviews all code and technical output for quality, security, correctness

**Verdict:** APPROVED or REJECTED. Binary. No "approved with caveats."
- APPROVED → proceed to Documentation phase
- REJECTED → return to Execution phase with specific feedback, fix, re-submit

### Phase 8 — Documentation & Report
1. Update Obsidian documentation if the change is significant
2. Present execution report:

```
═══ ROTHBARD 100 — Execution Report ═══

✅ COMPLETED:
  • [what was done]

📁 FILES CHANGED:
  • [project]: [files]

🧪 BUILD:
  • [build result]

📝 DOCS UPDATED:
  • [obsidian pages updated]

═══════════════════════════════════
```

## /rothbard100 status

Check the status of all Rothbard 100 projects:

```bash
# For each project:
cd <project_path>
git status
git log --oneline -5
git branch --show-current
```

Present as:

```
═══ ROTHBARD 100 — Ecosystem Status ═══

📦 ROTHBARD100-LANDING (Nuxt 4 + Nuxt UI v4 — SSG)
  Branch: [branch]
  Last commit: [hash] — [message] ([date])
  Status: [clean/uncommitted changes]

═══════════════════════════════════
```

## /rothbard100 content

For content tasks, the Content Creator role takes the lead:
1. Understand the event messaging and libertarian context
2. Write persuasive, bold copy aligned with the brand
3. All copy lives in `i18n/locales/*.json` — never hardcode text
4. 5 locales must be updated: pt (default), en, fr, es, de
5. SEO/Marketing role reviews for conversion optimization
6. Frontend Developer implements in components if needed

## /rothbard100 seo

SEO audit covers:
1. Meta tags (title, description, OG tags, Twitter cards)
2. Structured data (Event schema, Organization schema)
3. Performance audit (Core Web Vitals, Lighthouse)
4. Image optimization (@nuxt/image usage)
5. Accessibility (WCAG 2.1 AA minimum)
6. Mobile responsiveness

## /rothbard100 context

Show full ecosystem context:
1. Read all project files and CLAUDE.md
2. Present architecture, tech stack, components, conventions, current state

## /rothbard100 scaffold <name>

When scaffolding a new project:
1. Use `/arka-scaffold` skill with the appropriate template
2. Register the project in `ecosystems.json`
3. Create a project detail file in `~/.claude/skills/arka/projects/<name>/PROJECT.md`
4. Update SKILL.md's ecosystem overview table
5. Create Obsidian documentation
