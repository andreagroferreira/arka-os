# Migration Guide: ArkaOS v1 to v2

If you used ArkaOS v1 (the bash-only version installed via `git clone`), this guide walks you through the migration to v2. Your data is preserved, nothing is deleted, and you can roll back if needed.

## What Changed

| Feature | v1 | v2 |
|---------|----|----|
| **Core engine** | Bash scripts only | Python + Node.js + Bash |
| **Agents** | 22 | 65 (3x more) |
| **Departments** | 9 | 17 (8 new departments) |
| **Skills** | ~30 (SKILL.md files) | 244+ (validated, framework-backed) |
| **Workflows** | None (ad-hoc execution) | 24 YAML workflows with phases and gates |
| **Runtimes** | Claude Code only | Claude Code, Codex CLI, Gemini CLI, Cursor |
| **Installation** | `git clone` to `~/.claude/skills/` | `npx arkaos install` to `~/.arkaos/` |
| **Install location** | `~/.claude/skills/arka-os` | `~/.arkaos/` |
| **Context injection** | 5-layer Bash Synapse | 9-layer Python Synapse (<200ms, cached) |
| **Knowledge base** | Manual notes only | Vector DB with semantic search (sqlite-vss) |
| **Dashboard** | None | Nuxt 4 + FastAPI (8 pages, localhost:3333) |
| **Quality Gate** | Optional | Mandatory on every workflow (non-negotiable) |
| **Agent profiles** | Basic role descriptions | 4-framework behavioral DNA (DISC, Enneagram, MBTI, Big Five) |
| **Token tracking** | None | Budget system with per-department limits |
| **Testing** | Minimal | 1836 tests (pytest) |

### New Departments in v2

These departments did not exist in v1:

| Department | Prefix | What It Covers |
|-----------|--------|---------------|
| E-Commerce | `/ecom` | Store audits, CRO, pricing, RFM segmentation |
| Operations | `/ops` | SOPs, GDPR, ISO 27001, SOC 2, automation |
| SaaS | `/saas` | Idea validation, metrics, PLG, micro-SaaS |
| Landing Pages | `/landing` | Sales copy, funnels, offers, VSL scripts |
| Content | `/content` | Viral hooks, YouTube scripts, repurposing |
| Communities | `/community` | Platform setup, membership, gamification |
| Sales | `/sales` | Pipeline, SPIN selling, negotiation |
| Leadership | `/lead` | OKRs, team health, hiring, culture |

## How to Migrate

One command handles everything:

```bash
npx arkaos migrate
```

### What You Will See

```
ArkaOS Migration: v1 --> v2

[1/5] Detecting v1 installation...
  Found: ~/.claude/skills/arka-os
  Version: 1.x (22 agents, 9 departments)

[2/5] Backing up v1...
  Copying to ~/.arkaos-v1-backup
  Preserving session digests (12 files)
  Preserving media files (3 files)
  Backup complete: ~/.arkaos-v1-backup (4.2 MB)

[3/5] Installing v2...
  Installing to ~/.arkaos
  Core engine: Python 3.12.4
  Agents: 65 loaded
  Skills: 244 validated
  Workflows: 24 registered

[4/5] Updating hooks...
  Removed: user-prompt-submit.sh (v1)
  Installed: user-prompt-submit-v2.sh
  Installed: post-tool-use-v2.sh
  Installed: pre-compact-v2.sh

[5/5] Verifying...
  [PASS] v2 installed at ~/.arkaos
  [PASS] Hooks configured for claude-code
  [PASS] Synapse engine responsive (89ms)
  [PASS] v1 backup at ~/.arkaos-v1-backup

Migration complete. Run 'npx arkaos doctor' to verify.
Your v1 backup is at ~/.arkaos-v1-backup -- delete it after confirming v2 works.
```

## Per-Project Migration

After the global migration, initialize each of your projects:

```bash
cd your-project
npx arkaos init
```

This creates `.arkaos.json` with auto-detected stack information. The file feeds into Synapse layer L3 so agents know your project context.

```
Initializing ArkaOS for: your-project

Detected:
  Framework: Laravel 11.x
  Language: PHP 8.3
  Database: MySQL 8.0
  Frontend: Vue 3 (Inertia)
  Testing: PHPUnit + Pest

Created: .arkaos.json
```

Repeat for each project you work on. Projects without `.arkaos.json` still work -- agents just have less context about your stack.

## Auto-Detection

If you forget to migrate, the v2 hooks detect v1 installations automatically. You will see a `[MIGRATION]` tag in your prompt context:

```
[MIGRATION] ArkaOS v1 detected at ~/.claude/skills/arka-os.
Run 'npx arkaos migrate' to upgrade to v2 (65 agents, 244 skills, dashboard).
Your data will be preserved.
```

## Verify After Migration

```bash
npx arkaos doctor
```

All 9 checks should pass:

```
[PASS] Python 3.11+ found
[PASS] Node.js 18+ found
[PASS] ArkaOS installed at ~/.arkaos
[PASS] Hooks configured for claude-code
[PASS] Synapse engine responsive
[PASS] Knowledge DB initialized
[PASS] 65 agents loaded
[PASS] 244 skills validated
[PASS] 24 workflows registered
All checks passed.
```

## Rolling Back

If something goes wrong and you need v1 back:

```bash
# Remove v2
npx arkaos uninstall

# Restore v1 from backup
cp -r ~/.arkaos-v1-backup ~/.claude/skills/arka-os
```

Then manually restore the v1 hooks in your Claude Code settings.

## FAQ

**Will I lose my session digests or saved files?**

No. The migration copies all session digests and media files from v1 to the backup directory. v2 uses a different storage format, so old sessions are preserved in the backup but not imported into v2.

**Do my v1 custom skills transfer?**

Not automatically. v2 skills use a different format (YAML frontmatter, structured sections, proactive triggers). You will need to rewrite custom skills following the [SKILL-STANDARD.md](SKILL-STANDARD.md). The structure is better documented now, so this is straightforward.

**Can I run v1 and v2 side by side?**

No. Both versions use hooks that fire on every prompt. Running both would cause conflicts. The migration removes v1 hooks and installs v2 hooks.

**Do I need to reconfigure my AI runtime?**

No. The migration updates hooks automatically for your detected runtime (Claude Code, Codex, Gemini, or Cursor).

**How long does migration take?**

Under 30 seconds. The backup is the slowest step, and it only copies files.

**What if I never used v1?**

Skip this entirely. Just run `npx arkaos install` and you are set. See [GETTING-STARTED.md](GETTING-STARTED.md).
