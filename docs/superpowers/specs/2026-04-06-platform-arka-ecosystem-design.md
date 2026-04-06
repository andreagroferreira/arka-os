# Design: ArkaOS Self-Management Ecosystem (`/platform-arka`)

**Date:** 2026-04-06
**Status:** Approved
**Approach:** Ecosystem Skill (classic pattern, like /client_retail, /edp, /client_commerce)

## Summary

Add ArkaOS itself as an internal WizardingCode project with a dedicated ecosystem orchestrator skill (`/platform-arka`). The ArkaOS product team manages its own development, releases, testing, skill creation, agent management, and self-evolution. Reports to `/wiz` (WizardingCode Internal) for strategic alignment.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Command prefix | `/platform-arka` | Separates "operate ArkaOS" (`/arka`) from "develop the product" (`/platform-arka`) |
| Squad scope | Full-stack product team (9 roles) | ArkaOS has enough layers (Python core, Node.js CLI, React dashboard, skills, agents) to justify a complete team |
| Release workflow | Semi-automatic with confirmation gate | npm publish is irreversible; squad prepares everything, user confirms before publish |
| Auto-evolution | Aggressive with approval | `audit` analyzes gaps, `evolve` proposes and implements improvements with user approval |
| Relation to /wiz | Reports to /wiz | `/wiz` sets strategic priorities, `/platform-arka` executes. ArkaOS appears in `/wiz projects` and `/wiz status` |

## Identity

| Property | Value |
|----------|-------|
| Skill name | `platform-arka` |
| Prefix | `/platform-arka` |
| Path | `/Users/andreagroferreira/AIProjects/arka-os` |
| Stack | Python (core) + Node.js (installer/CLI) + React (dashboard) |
| Reports to | `/wiz` (WizardingCode Internal) |

## Squad — The Platform Team

| Role | Agent Type | Responsibility |
|------|-----------|----------------|
| **Product Owner** | `strategist` | Roadmap, feature prioritization, OKRs, reports to `/wiz` |
| **Core Engineer** | `senior-dev` | Python core — Synapse, workflows, agents, governance |
| **CLI Engineer** | `senior-dev` | Node.js installer, CLI tools, bash hooks |
| **Dashboard Engineer** | `frontend-dev` | React dashboard, API endpoints, WebSocket |
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
| `/platform-arka audit` | Self-analysis: code quality, test gaps, missing skills, agents without DNA, departments without workflows, dead code |
| `/platform-arka evolve` | Propose improvements based on audit — with approval, implements: new skills, new agents, missing workflows, refactors |
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
   - Load recent git history
   - Check current test status

2. Analysis & Planning
   - Product Owner assesses scope and priority
   - Skill Architect identifies affected areas (core/installer/dashboard/skills)
   - Appropriate engineer(s) assigned

3. Plan Presentation & Approval
   - Present plan with affected files, squad roles, estimated scope
   - User approves before execution

4. Execution
   - Features/evolve: branch + worktree isolation
   - Hotfixes/patches: direct on master
   - Squad agents execute in their domain
   - QA Engineer runs tests after changes

5. Quality Gate
   - Marta (CQO) orchestrates review
   - Eduardo (Copy) reviews text output
   - Francisca (Tech) reviews code
   - APPROVED or REJECTED

6. Documentation
   - Update Obsidian at WizardingCode Internal/ArkaOS/
```

### Release Flow

```
1. Pre-flight
   - Run full test suite (pytest + any JS tests)
   - Check git status (clean working tree required)
   - Review changes since last release (git log)

2. Preparation
   - Determine version bump type (patch/minor/major)
   - Update VERSION, package.json, pyproject.toml
   - Generate changelog from commits
   - Commit version bump

3. Confirmation Gate (PAUSE)
   - Show: new version, changelog, files changed
   - User confirms before publish

4. Publish
   - Git push to master
   - GitHub release with notes
   - npm publish
   - Verify package on npm registry

5. Post-release
   - Update Obsidian release log
   - Report to /wiz (project status updated)
```

### Evolve Flow

```
1. Audit (automatic first step)
   - Platform Analyst scans entire codebase:
     - Departments without workflows
     - Agents without complete behavioral DNA
     - Skills referenced but not implemented
     - Test coverage gaps
     - Dead code / unused imports
     - CLAUDE.md accuracy vs actual state

2. Proposal
   - Rank findings by impact (high/medium/low)
   - Present top proposals with rationale
   - User selects which to implement

3. Implementation
   - Skill Architect + appropriate engineer execute
   - Branch + worktree isolation
   - Each improvement as separate commit
   - Tests added/updated for each change

4. Quality Gate
   - Standard QG (Marta, Eduardo, Francisca)
```

## Branch Strategy

| Scenario | Strategy |
|----------|----------|
| Features, evolve improvements | Branch (`feature/*`, `evolve/*`) + worktree isolation, merge after QG |
| Hotfixes, simple patches | Direct on master |
| Releases | Always from master (bump + tag + publish) |

## Registration

### ecosystems.json

```json
{
  "wizardingcode": {
    "projects": [
      {
        "name": "arka-os",
        "role": "product",
        "stack": "Python + Node.js + React",
        "path": "/Users/andreagroferreira/AIProjects/arka-os"
      }
    ]
  }
}
```

### /wiz Integration

- ArkaOS appears in `/wiz projects` and `/wiz status` as active internal project
- `/wiz` can set strategic priorities that `/platform-arka roadmap` reflects
- Revenue tracking: ARKA OS Pro revenue stream tracked in `/wiz finance`

## Obsidian Output

All documentation: `/Users/andreagroferreira/Documents/Personal/Projects/WizardingCode Internal/ArkaOS/`

Structure:
```
WizardingCode Internal/ArkaOS/
  Roadmap.md          - Product roadmap
  Releases/           - Release notes per version
  Audits/             - Self-audit reports
  Evolution Log.md    - What evolved and why
  Metrics.md          - Latest metrics snapshot
```

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `~/.claude/skills/arka-platform-arka/SKILL.md` | Create | Ecosystem skill definition |
| `knowledge/ecosystems.json` | Update | Register ArkaOS under wizardingcode |
| `~/.claude/skills/arka-wizardingcode/SKILL.md` | Update | Add ArkaOS as active project reference |
