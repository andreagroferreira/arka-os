# ADR-0001: Separation of User-Local Data from Installed Core Skill Directory

- **Status:** Proposed
- **Date:** 2026-04-17
- **Deciders:** Marco (CTO), Gabriel (Architect), Andre (Owner)
- **Target release:** v2.19.0
- **Legacy sunset release:** v2.21.0
- **Related branch:** `feat/user-data-separation`
- **Related remediation:** v2.18.1 (private-client-data purge from repo)

## Context

ArkaOS installs its core skill bundle into `~/.claude/skills/arka/` via `npx arkaos install` (and `update`). Historically the same directory has also been used as a scratch space for user-local state:

| Path (current) | Owner | Mutated by |
|---|---|---|
| `~/.claude/skills/arka/projects/*.md` | User | `/arka onboard`, manual edits |
| `~/.claude/skills/arka/projects/<slug>/PROJECT.md` | User | `/arka onboard` |
| `~/.claude/skills/arka/knowledge/ecosystems.json` | User | `/arka onboard`, manual edits |

These files are read by several subsystems:

- `core/sync/engine.py` (sync engine)
- `core/sync/discovery.py` (project discovery)
- `core/cognition/research/profiler.py` (research profiler)
- `config/hooks/cwd-changed.sh` / `.ps1` (runtime ecosystem detection)
- `config/cognition/prompts/dreaming.md` / `research.md` (already reference `~/.arkaos/ecosystems.json`)
- `arka-prompts` MCP server (descriptor surfacing)
- Dashboard API (`scripts/dashboard-api.py`, ecosystems + projects widgets)
- `/arka status`, `/arka onboard`, `/arka standup` skills

Three concrete problems:

1. **Update collision.** Any mechanism that treats `~/.claude/skills/arka/` as installer-owned must race user writes. `npx arkaos@latest update` already has special-case logic for this, which is fragile and will regress.
2. **Privacy incident.** Because the repo ships the *seed* tree for the skill, private client data leaked into git history (remediated in v2.18.1). The root cause is the same directory serving two owners.
3. **Architectural smell.** A read-only versioned artifact (the skill) and a mutable user profile (projects, ecosystems) share the same root. There is no file-level contract a new developer can inspect to know which is which.

The canonical user-data root `~/.arkaos/` already exists and hosts: `sync-state.json`, `profile.json`, `keys.json`, `budget-usage.json`, `tasks.json`, `knowledge.db`, `plans/`, `cognition/`, `logs/`, `media/`, `venv/`, `bin/`. Two categories still live in the wrong place.

## Decision

**Move all user-mutable data out of `~/.claude/skills/arka/` into `~/.arkaos/`. The installed skill directory becomes strictly read-only and installer-managed.**

### Canonical paths (target state, v2.19.0+)

| Concern | New canonical path | Old (deprecated) path |
|---|---|---|
| Project descriptors (flat) | `~/.arkaos/projects/<slug>.md` | `~/.claude/skills/arka/projects/<slug>.md` |
| Project descriptors (nested) | `~/.arkaos/projects/<slug>/PROJECT.md` | `~/.claude/skills/arka/projects/<slug>/PROJECT.md` |
| Ecosystem registry | `~/.arkaos/ecosystems.json` | `~/.claude/skills/arka/knowledge/ecosystems.json` |

### Ownership contract

| Directory | Owner | Mutated by | Wiped on `update`? |
|---|---|---|---|
| `~/.claude/skills/arka/` | Installer (arkaos core) | `npx arkaos install\|update` | Yes (idempotent resync) |
| `~/.arkaos/` | User runtime | hooks, skills, dashboard, user | No (preserved across updates) |

The installer MUST NOT write any file under `~/.arkaos/projects/` or create `~/.arkaos/ecosystems.json` with user data. It MAY create empty parent directories on first install.

### Reader map (who reads what, after v2.19.0)

| Component | Reads | Fallback chain |
|---|---|---|
| `core/sync/engine.py` | ecosystems + descriptors | new → legacy (warn) → empty |
| `core/sync/discovery.py` | ecosystems + descriptors | new → legacy (warn) → empty |
| `core/cognition/research/profiler.py` | ecosystems | new → legacy (warn) → empty |
| `config/hooks/cwd-changed.{sh,ps1}` | ecosystems | new → legacy (warn once per session) → skip |
| `arka-prompts` MCP server | descriptors | new → legacy (warn) → empty |
| Dashboard API (`scripts/dashboard-api.py`) | both | new → legacy (warn) → empty |
| `/arka status` skill | both | new → legacy (warn) → empty |
| `/arka onboard` skill | **writes** new only | never writes legacy |
| `/arka standup` skill | descriptors | new → legacy (warn) → empty |

### Fallback algorithm (transitional, v2.19.0 → v2.20.x)

```
def resolve_user_path(kind):  # kind in {"projects_dir", "ecosystems_json"}
    new = NEW_PATH[kind]          # ~/.arkaos/...
    legacy = LEGACY_PATH[kind]    # ~/.claude/skills/arka/...
    if exists(new):
        return new
    if exists(legacy):
        log.warning(
            "ArkaOS: reading %s from legacy location %s. "
            "This path is deprecated and will be removed in v2.21.0. "
            "Run `/arka update` or `npx arkaos@latest migrate-user-data` to move it.",
            kind, legacy,
        )
        return legacy
    return None  # caller treats as empty
```

Rules:

- Readers never merge both paths. First hit wins.
- The deprecation warning is emitted **once per process** per kind, to avoid log spam in hot paths (e.g. `cwd-changed` on every directory change).
- Writers in `/arka onboard` create the new path **and only the new path**. They do not touch legacy even if it exists.

### Sunset plan

| Release | Behaviour |
|---|---|
| v2.19.0 | New paths introduced. Readers fall back to legacy with deprecation warning. Migration tool available (`npx arkaos@latest migrate` or automatic on first `update`). `/arka onboard` writes to new path only. |
| v2.20.x | No functional change. Warnings remain. Grace window for users who skipped v2.19.0. |
| **v2.21.0** | Legacy fallback **removed**. Readers ignore `~/.claude/skills/arka/projects/` and `~/.claude/skills/arka/knowledge/ecosystems.json`. Installer actively deletes them on next `update` (with a one-line report). |

## Consequences

### Positive

- **Update safety.** `npx arkaos update` can treat `~/.claude/skills/arka/` as a fully-managed artifact (wipe + resync) without ever risking user data.
- **Privacy by construction.** The repo-shipped seed tree contains zero paths that users would mutate. The v2.18.1 class of leak cannot happen again from these two paths.
- **Clear mental model.** Contributors can state a one-line rule: "If ArkaOS writes it at runtime, it lives in `~/.arkaos/`. If the installer ships it, it lives in `~/.claude/skills/arka/`."
- **Dashboard simplification.** All dashboard user-state reads consolidate under one root (`~/.arkaos/`), matching how `budget-usage.json`, `tasks.json`, `knowledge.db` already behave.
- **Aligns with existing drift.** `config/cognition/prompts/dreaming.md` and `research.md` already reference `~/.arkaos/ecosystems.json` — this ADR ratifies what was already partially true.

### Negative

- **Transitional complexity.** Every reader gains a 3-tier fallback for two releases. Six code locations must be updated in lockstep (Phase D).
- **Migration risk.** Users on v2.18.x who skip v2.19.0 and v2.20.x and jump directly to v2.21.0 lose their descriptors unless the final installer runs the migration unconditionally. Mitigation: v2.21.0 installer runs migration on first launch regardless of source version.
- **Cross-platform paths.** `cwd-changed.ps1` must be updated alongside `cwd-changed.sh`. Historically Windows parity has lagged; Phase D must include both.
- **Test surface.** Every existing `test_sync_*.py` fixture that writes to `skills/arka/knowledge/ecosystems.json` must be updated. Regression tests for the fallback path must be added.

### Neutral

- Disk footprint unchanged; we move files, not duplicate them.
- User-visible commands unchanged. `/arka onboard`, `/arka status`, `/arka standup` keep the same UX.
- The `install-manifest.json` schema may need a `user_data_root` field for forward compat, but does not require a version bump of the manifest itself.

## Migration strategy

### Forward migration (v2.18.x → v2.19.0)

Executed by `installer/migrate-user-data.js`, called from:

1. `npx arkaos@latest update` (automatic, idempotent).
2. `npx arkaos@latest migrate-user-data` (manual, for users who want to trigger it before running `update`; distinct from the existing v1→v2 `migrate` command).
3. First invocation of `/arka update` that detects the mismatch (AI-supervised fallback).

Steps:

1. Ensure `~/.arkaos/projects/` exists.
2. For each `~/.claude/skills/arka/projects/*.md` and `~/.claude/skills/arka/projects/*/PROJECT.md`:
   - If the destination does not exist, **move** (not copy) to `~/.arkaos/projects/`.
   - If the destination already exists, leave the source in place and log a conflict; user resolves manually.
3. If `~/.arkaos/ecosystems.json` does not exist and `~/.claude/skills/arka/knowledge/ecosystems.json` does, move it.
4. Write a migration report to `~/.arkaos/logs/migration-<timestamp>.log` listing moved files, skipped files, and conflicts.
5. Do **not** delete the legacy directories in v2.19.0 — only move contents. Empty directories remain to signal "migrated" and are cleaned up in v2.21.0.

### Backward compatibility (v2.19.0 → v2.20.x)

- Readers use the fallback chain defined above.
- If a user reverts to v2.18.x after migrating, they lose visibility of descriptors until they either copy them back manually or re-upgrade. This is acceptable for an alpha-series product; it is documented in the v2.19.0 release notes.

### Rollback

If v2.19.0 ships broken: users can run a one-line command shipped in the release notes to move files back, or `git checkout v2.18.1` on the installer. No schema changes, no data loss — the move is reversible.

## Out of scope

- **Vector DB (`knowledge.db`) relocation.** Already in `~/.arkaos/`.
- **Obsidian vault path.** User-configured, handled by `profile.json`.
- **MCP profile storage.** Separate concern; tracked for a future ADR.
- **Per-project `.arkaos/` descriptors** (inside each project repo). Those are intentionally repo-local and not affected by this ADR.
- **Windows registry / AppData relocation.** `~/.arkaos/` (i.e. `%USERPROFILE%\.arkaos\`) remains the canonical root on Windows; no shift to `%APPDATA%` in this ADR.
- **Renaming `~/.arkaos/` itself.** Out of scope and not on the roadmap.

## References

- `docs/superpowers/specs/2026-04-11-sync-engine-design.md`
- `docs/superpowers/plans/2026-04-08-arka-update-sync.md`
- `departments/ops/skills/update/references/sync-engine.md`
- v2.18.1 release notes (private-data remediation)
- `installer/migrate.js` (existing v1→v2 migration pattern)
