# `/platform-arka` Ecosystem Skill — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a dedicated `/platform-arka` ecosystem orchestrator skill so ArkaOS can manage its own development, releases, testing, and self-evolution as a WizardingCode internal product.

**Architecture:** Three files: one new skill definition (`SKILL.md`), one JSON registry update (`ecosystems.json`), and one existing skill update (`arka-wizardingcode/SKILL.md`). No Python/JS code — this is purely configuration and skill authoring.

**Tech Stack:** Markdown (SKILL.md with YAML frontmatter), JSON (ecosystems.json)

---

### Task 1: Create the `/platform-arka` ecosystem skill

**Files:**
- Create: `~/.claude/skills/arka-platform-arka/SKILL.md`

- [ ] **Step 1: Create the skill directory**

```bash
mkdir -p ~/.claude/skills/arka-platform-arka
```

- [ ] **Step 2: Write the SKILL.md file**

Create `~/.claude/skills/arka-platform-arka/SKILL.md` with this exact content:

```markdown
---
name: platform-arka
description: >
  ArkaOS platform ecosystem orchestrator. Self-managing product development for ArkaOS —
  the core WizardingCode product. Full-stack product team: Python core engine, Node.js
  installer/CLI, React dashboard, skills, agents, departments. Manages features, fixes,
  releases (semi-auto with confirmation gate), test suite (542+ pytest), self-auditing,
  and auto-evolution (detects gaps, proposes and implements improvements).
  Reports to /wiz (WizardingCode Internal) for strategic alignment.
  Use when user says "platform-arka", "arkaos dev", "arkaos feature", "arkaos release",
  "arkaos audit", "arkaos evolve", "platform", or wants to develop/improve ArkaOS itself.
---

# ArkaOS Platform — Product Development Ecosystem

Self-managing product development orchestrator for ArkaOS.
**The system that evolves itself.**

## Project

| Property | Value |
|----------|-------|
| **Product** | ArkaOS |
| **Company** | WizardingCode |
| **Path** | `/Users/andreagroferreira/AIProjects/arka-os` |
| **Stack** | Python (core engine) + Node.js (installer/CLI) + React (dashboard) |
| **Reports to** | `/wiz` (WizardingCode Internal) |
| **Version file** | `VERSION` (also in `package.json`, `pyproject.toml`) |
| **Tests** | `pytest` (542+ tests in `tests/python/`) |

## Architecture

```
ArkaOS Product
├── core/                  Python — Synapse, workflows, agents, governance, runtime
├── installer/             Node.js — CLI entry point, runtime detection, adapters
├── scripts/               Dashboard — React UI + FastAPI backend
├── departments/           17 departments — agents, skills, workflows (YAML + MD)
├── config/                Constitution, governance rules
├── knowledge/             Ecosystems registry, agent registry
└── tests/python/          542+ pytest tests
```

## Squad — The Platform Team

| Role | Agent Type | Responsibility |
|------|-----------|----------------|
| **Product Owner** | `strategist` | Roadmap, feature prioritization, OKRs, reports to `/wiz` |
| **Core Engineer** | `senior-dev` | Python core — Synapse, workflows, agents, governance |
| **CLI Engineer** | `senior-dev` | Node.js installer, CLI tools, bash hooks |
| **Dashboard Engineer** | `frontend-dev` | React dashboard, FastAPI endpoints, WebSocket |
| **Skill Architect** | `architect` | Skill design, agent YAML, department structure |
| **DevOps** | `devops` | npm publish, GitHub releases, CI/CD, version management |
| **QA Engineer** | `qa` | pytest suite (542+ tests), integration tests, regression |
| **Security Engineer** | `security` | Dependency audit, OWASP, installer security |
| **Platform Analyst** | `analyst` | Self-analysis, gap detection, evolution proposals |

## Commands

### Standard Product Commands

| Command | Description |
|---------|-------------|
| `/platform-arka` | General — describe what you need, orchestrator routes |
| `/platform-arka status` | Project status (version, test coverage, open issues, recent releases) |
| `/platform-arka feature <desc>` | Plan and implement a new feature |
| `/platform-arka fix <desc>` | Debug and fix an issue |
| `/platform-arka test` | Run full pytest suite + report |
| `/platform-arka review` | Code review of recent changes |
| `/platform-arka docs` | Update documentation (CLAUDE.md, CONTRIBUTING, Obsidian) |

### Release Pipeline

| Command | Description |
|---------|-------------|
| `/platform-arka release <type>` | Semi-auto release: bump (patch/minor/major), changelog, commit. Pauses for confirmation before push + npm publish + GitHub release |
| `/platform-arka release status` | Check latest release, npm version, GitHub tags |

### Auto-Evolution Commands

| Command | Description |
|---------|-------------|
| `/platform-arka audit` | Self-analysis: code quality, test gaps, missing skills, agents without DNA, departments without workflows, dead code, CLAUDE.md accuracy |
| `/platform-arka evolve` | Propose improvements based on audit — with approval, implements: new skills, agents, workflows, refactors |
| `/platform-arka roadmap` | View/update product roadmap, synced with `/wiz` priorities |
| `/platform-arka metrics` | Coverage, agent count, skill count, department completeness, version history |

### Skill & Agent Management

| Command | Description |
|---------|-------------|
| `/platform-arka skill create <name>` | Scaffold a new skill (SKILL.md + registration) |
| `/platform-arka skill list` | List all skills with status |
| `/platform-arka agent create <name>` | Create new agent YAML with behavioral DNA |
| `/platform-arka agent validate` | Validate all agent YAMLs (4-framework consistency) |
| `/platform-arka department <name>` | Department health check (agents, skills, workflows) |

## Orchestration Workflows

### Standard Flow (feature, fix, docs)

```
1. Context Loading
   - Read CLAUDE.md, VERSION, package.json, pyproject.toml
   - Load recent git history (git log --oneline -20)
   - Check current test status (pytest --tb=no -q)

2. Analysis & Planning
   - Product Owner assesses scope and priority
   - Skill Architect identifies affected areas (core/installer/dashboard/skills)
   - Assign appropriate engineer(s) based on affected layers

3. Plan Presentation & Approval
   - Present plan: affected files, squad roles, scope estimate
   - User approves before any code execution

4. Execution
   - Features/evolve: branch (feature/* or evolve/*) + worktree isolation
   - Hotfixes/patches: direct on master
   - Squad agents execute in their domain
   - QA Engineer runs tests after changes

5. Quality Gate
   - Marta (CQO) orchestrates review
   - Eduardo (Copy) reviews all text output
   - Francisca (Tech) reviews all code
   - APPROVED or REJECTED — no exceptions

6. Documentation
   - Update Obsidian at WizardingCode Internal/ArkaOS/
```

### Release Flow

```
1. Pre-flight
   - Run full test suite: cd /Users/andreagroferreira/AIProjects/arka-os && python -m pytest tests/ --tb=short -q
   - Check git status (must be clean working tree)
   - Review changes since last release: git log $(git describe --tags --abbrev=0)..HEAD --oneline

2. Preparation
   - Determine version bump type (patch/minor/major) from changes
   - Update VERSION, package.json version, pyproject.toml version
   - Generate changelog from conventional commits
   - Commit: git commit -m "chore: bump to vX.Y.Z"

3. Confirmation Gate (PAUSE)
   - Present to user: new version number, changelog summary, files changed count
   - WAIT for explicit user confirmation before proceeding
   - If user declines: revert bump commit, stop

4. Publish (only after user confirms)
   - git push origin master
   - gh release create vX.Y.Z --title "vX.Y.Z" --notes "<changelog>"
   - npm publish
   - Verify: npm view arkaos version

5. Post-release
   - Save release notes to Obsidian: WizardingCode Internal/ArkaOS/Releases/vX.Y.Z.md
   - Update metrics snapshot
```

### Audit Flow

```
1. Platform Analyst scans the codebase:

   a. Department completeness:
      - List all departments/ subdirectories
      - Check each has: agents/*.yaml, skills/*/SKILL.md, workflows/*.yaml
      - Flag departments missing any component

   b. Agent validation:
      - Parse all departments/*/agents/*.yaml
      - Verify 4-framework behavioral DNA (DISC, Enneagram, Big Five, MBTI)
      - Flag agents with incomplete profiles

   c. Skill coverage:
      - List all ~/.claude/skills/arka-*/SKILL.md
      - Cross-reference with department command tables
      - Flag commands without corresponding skills

   d. Test coverage:
      - Run: python -m pytest tests/ --tb=no -q
      - Count test files vs source files
      - Flag untested modules

   e. Code quality:
      - Check for unused imports, dead code patterns
      - Verify CLAUDE.md accuracy against actual file structure
      - Check VERSION consistency across package.json, pyproject.toml, VERSION

2. Present findings ranked by impact (high/medium/low)
3. Save audit report to Obsidian: WizardingCode Internal/ArkaOS/Audits/YYYY-MM-DD.md
```

### Evolve Flow

```
1. Run audit (automatic first step — reuse audit flow above)

2. Proposal
   - Filter audit findings to actionable improvements
   - Rank by impact and effort (quick wins first)
   - Present top 5 proposals with:
     - What: description of the improvement
     - Why: impact on ArkaOS quality/completeness
     - How: which squad member(s) implement it
     - Effort: small/medium/large
   - User selects which proposals to implement

3. Implementation
   - Create branch: evolve/YYYY-MM-DD-<description>
   - Use worktree isolation
   - Each improvement as a separate commit with conventional commit message
   - QA Engineer runs tests after each change

4. Quality Gate
   - Marta (CQO) orchestrates final review
   - Eduardo (Copy) reviews any text changes
   - Francisca (Tech) reviews any code changes
   - APPROVED → merge to master
   - REJECTED → fix and re-submit
```

### Status Command

```
1. Read current version from VERSION file
2. Run: python -m pytest tests/ --tb=no -q (capture pass/fail/total)
3. Run: git log --oneline -10 (recent activity)
4. Run: git describe --tags --abbrev=0 (latest release tag)
5. Count: departments, agents, skills, tests
6. Present formatted status:

   === ArkaOS Platform Status ===
   Version: X.Y.Z
   Latest Release: vX.Y.Z (YYYY-MM-DD)
   Tests: X passed / Y total
   Departments: 17 | Agents: 65 | Skills: 244+
   Recent commits: [last 5]
   Reports to: /wiz (WizardingCode Internal)
   ==============================
```

### Metrics Command

```
1. Count files:
   - departments/*/agents/*.yaml → agent count
   - ~/.claude/skills/arka-*/SKILL.md → skill count
   - departments/ subdirectories → department count
   - tests/python/ test files → test count

2. Check completeness:
   - Departments with all 3 components (agents, skills, workflows)
   - Agents with full 4-framework DNA

3. Version history:
   - git tag --sort=-version:refname | head -10

4. Present formatted metrics dashboard
```

### Skill Create Command

```
1. Ask for skill name and target department
2. Create directory: ~/.claude/skills/arka-<name>/
3. Scaffold SKILL.md with:
   - YAML frontmatter (name, description)
   - Command table template
   - Squad roles section
   - Orchestration workflow template
4. Inform user to register in settings.json if needed
```

### Agent Create Command

```
1. Ask for agent name, department, and role
2. Scaffold YAML file at departments/<dept>/agents/<name>.yaml with:
   - Basic identity (name, role, department)
   - 4-framework DNA template (DISC, Enneagram, Big Five, MBTI) with placeholders
3. Run agent validate to check consistency
```

## Branch Strategy

| Scenario | Branch Pattern | Isolation |
|----------|---------------|-----------|
| Features | `feature/<desc>` | Worktree |
| Evolution improvements | `evolve/<desc>` | Worktree |
| Hotfixes, simple patches | Direct on `master` | None |
| Releases | From `master` | None (bump + tag + publish) |

## /wiz Integration

- ArkaOS appears in `/wiz projects` and `/wiz status` as an active internal project
- `/wiz` can set strategic priorities that `/platform-arka roadmap` reflects
- Revenue tracking: ARKA OS Pro revenue stream tracked via `/wiz finance`
- Roadmap syncs: `/platform-arka roadmap` references `/wiz` OKRs when available

## Obsidian Output

All documentation: `/Users/andreagroferreira/Documents/Personal/Projects/WizardingCode Internal/ArkaOS/`

```
WizardingCode Internal/ArkaOS/
├── Roadmap.md              — Product roadmap and priorities
├── Releases/               — Release notes per version
│   ├── v2.4.0.md
│   ├── v2.4.1.md
│   └── ...
├── Audits/                 — Self-audit reports
│   └── YYYY-MM-DD.md
├── Evolution Log.md        — What evolved and why (append-only)
└── Metrics.md              — Latest metrics snapshot
```
```

- [ ] **Step 3: Verify the file was created correctly**

```bash
head -5 ~/.claude/skills/arka-platform-arka/SKILL.md
```

Expected output:
```
---
name: platform-arka
description: >
  ArkaOS platform ecosystem orchestrator. Self-managing product development for ArkaOS —
  the core WizardingCode product. Full-stack product team: Python core engine, Node.js
```

- [ ] **Step 4: Commit**

```bash
cd /Users/andreagroferreira/AIProjects/arka-os
git add ~/.claude/skills/arka-platform-arka/SKILL.md
git commit -m "feat: add /platform-arka ecosystem skill for ArkaOS self-management"
```

Note: If `~/.claude/skills/` is outside the repo, this file won't be tracked by git. That's expected — skills live in the user's Claude config directory, not in the repo. Skip the git commit for this file and commit it together with the ecosystems.json change in Task 2.

---

### Task 2: Register ArkaOS in ecosystems.json

**Files:**
- Modify: `/Users/andreagroferreira/AIProjects/arka-os/knowledge/ecosystems.json`

- [ ] **Step 1: Update ecosystems.json**

Replace the entire content of `/Users/andreagroferreira/AIProjects/arka-os/knowledge/ecosystems.json` with:

```json
{
  "_meta": {
    "description": "ARKA OS — Project Ecosystem Registry",
    "updated": "2026-04-06"
  },
  "ecosystems": {
    "wizardingcode": {
      "projects": [
        {
          "name": "arka-os",
          "role": "product",
          "stack": "Python + Node.js + React",
          "path": "/Users/andreagroferreira/AIProjects/arka-os",
          "skill": "/platform-arka",
          "description": "ArkaOS — The Operating System for AI Agent Teams"
        }
      ]
    }
  }
}
```

- [ ] **Step 2: Verify JSON is valid**

```bash
python3 -c "import json; json.load(open('/Users/andreagroferreira/AIProjects/arka-os/knowledge/ecosystems.json')); print('Valid JSON')"
```

Expected output: `Valid JSON`

- [ ] **Step 3: Commit**

```bash
cd /Users/andreagroferreira/AIProjects/arka-os
git add knowledge/ecosystems.json
git commit -m "feat: register ArkaOS as WizardingCode internal project in ecosystem registry"
```

---

### Task 3: Update `/wiz` skill to reference ArkaOS as active project

**Files:**
- Modify: `~/.claude/skills/arka-wizardingcode/SKILL.md`

- [ ] **Step 1: Add ArkaOS to the /wiz skill's project list**

In `~/.claude/skills/arka-wizardingcode/SKILL.md`, find the section `## Revenue Streams (To Build)` (line 140). Insert a new section **before** it (after the `/wiz invoice <client>` command table, around line 138):

```markdown
## Active Internal Projects

| Project | Skill | Stack | Status |
|---------|-------|-------|--------|
| **ArkaOS** | `/platform-arka` | Python + Node.js + React | Active — v2.4.4 |

ArkaOS is the core WizardingCode product. Use `/platform-arka` for all ArkaOS development work.
The `/wiz projects` and `/wiz status` commands should include ArkaOS status from the ecosystem registry.
```

- [ ] **Step 2: Update the /wiz build command description**

In the same file, find the `/wiz build` workflow section (line 126-131). After step 7, add:

```markdown
8. If building an ArkaOS feature, route to `/platform-arka feature` instead
```

- [ ] **Step 3: Verify the changes look correct**

```bash
grep -n "Active Internal Projects\|platform-arka" ~/.claude/skills/arka-wizardingcode/SKILL.md
```

Expected: Lines showing the new section header and references to `/platform-arka`.

- [ ] **Step 4: Commit**

Since this file is outside the git repo (`~/.claude/skills/`), no git commit is needed. The skill is loaded by Claude Code from the user's config directory.

---

### Task 4: Final verification

- [ ] **Step 1: Verify all three files exist and are correct**

```bash
echo "=== Skill ===" && head -3 ~/.claude/skills/arka-platform-arka/SKILL.md && echo "" && echo "=== Ecosystems ===" && cat /Users/andreagroferreira/AIProjects/arka-os/knowledge/ecosystems.json && echo "" && echo "=== Wiz Reference ===" && grep "platform-arka" ~/.claude/skills/arka-wizardingcode/SKILL.md
```

Expected:
- Skill shows `name: platform-arka` frontmatter
- Ecosystems shows `arka-os` under `wizardingcode.projects`
- Wiz skill references `/platform-arka` in at least 2 places

- [ ] **Step 2: Commit the ecosystems.json change (the only in-repo change)**

```bash
cd /Users/andreagroferreira/AIProjects/arka-os
git add knowledge/ecosystems.json
git commit -m "feat: add /platform-arka ecosystem — ArkaOS as WizardingCode internal project

- Register ArkaOS in ecosystems.json under wizardingcode
- Ecosystem skill created at ~/.claude/skills/arka-platform-arka/
- /wiz skill updated to reference ArkaOS as active project"
```

- [ ] **Step 3: Verify git status is clean**

```bash
git status
```

Expected: `nothing to commit, working tree clean`
