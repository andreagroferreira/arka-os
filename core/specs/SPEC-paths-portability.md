---
type: spec
status: approved
feature: paths-portability
project: ArkaOS
version: 2.23.0
pr: PR1 of 6 (Conclave roadmap 2026-05-13)
branch: feature/v2.23.0-paths-portability
date_created: 2026-05-13
date_updated: 2026-05-13
tags: [spec, arkaos, paths, portability, refactor, v2.23.0, conclave-pr1]
---

# SPEC: Paths Portability (v2.23.0)

## Overview

**Problem.** ArkaOS source contains hardcoded user-specific paths (`/Users/andreagroferreira/...`) across SKILL.md files, JSON configs, Python regexes, and cognitive prompts. These break for the **~20K users** currently running ArkaOS with different home directories and OS layouts.

**Goal.** Replace 7 CRITICAL hardcoded paths with profile-driven templates resolved at runtime, with **non-breaking auto-migration** for the existing user base.

**Actors.** ArkaOS core (skill loader, cognition collector, installer migration), end users (via `~/.arkaos/profile.json`).

## Scope

**In scope (PR1 / v2.23.0):**

| # | File | Fix |
|---|---|---|
| 1 | `knowledge/obsidian-config.json:6` | `vault_path` value resolved at load via `path_resolver.resolve_dict` (profile.vaultPath) |
| 2 | `core/cognition/capture/collector.py:15-17` | Regex generated from `profile.projectRoots`; fallback `os.getcwd()` |
| 3 | `departments/kb/skills/knowledge/SKILL.md:25` | `${VAULT_PATH}` template |
| 4 | `departments/ops/skills/operations/SKILL.md:59` | `${VAULT_PATH}` template |
| 5 | `arka/skills/comfyui/SKILL.md:22-23` + `references/workflows.md` | `${ARKA_OS_REPOS}/{purz-comfyui-workflows,lora_tester}` |
| 6 | `config/cognition/prompts/dreaming.md` | `${VAULT_PATH}` template |
| 7 | `config/cognition/prompts/research.md` | `${VAULT_PATH}` template |
| 8 | `departments/dev/skills/scaffold/SKILL.md:19` | `${GIT_HOST}` template, default `github.com` HTTPS |
| — | new `core/runtime/path_resolver.py` | `resolve()`, `resolve_dict()`, `load_profile()` |
| — | new `installer/migrations/v3_path_schema.js` | Auto-migrate `projectsDir` text → `projectRoots` list + `reposRoot` |
| — | skill loader extension | Substitute `${VAR}` tokens at SKILL.md load |
| — | new `tests/python/test_path_resolver.py` | ≥ 15 tests |

**Out of scope (deferred):**

- `install.sh:25, 631-634` (GitHub URL hardcode + Mac-only Obsidian detection) → **PR2 v2.24.0** (cross-OS installer is the natural home for OS-aware logic)
- 50+ docs/superpowers/plans hardcoded paths (LOW priority, examples only) → **PR6 v2.28.0** cleanup pass
- Vision bridge migration (test_vision_bridge.py + scripts/tools/vision/*) → file was discarded; not relevant to PR1
- Migration of installed user skills under `~/.claude/skills/arka/` — installer rewrites these from source on every update; fixing source covers it

## Acceptance Criteria

1. **Zero CRITICAL grep hits.** Given a fresh checkout of `feature/v2.23.0-paths-portability`, when `grep -rn "/Users/andreagroferreira" core/ arka/ installer/ config/ departments/ knowledge/ --exclude-dir=node_modules --exclude-dir=__pycache__ --exclude-dir=.git --exclude-dir=docs` runs, then it returns **0 CRITICAL hits**. Hits inside `docs/superpowers/plans/` are tracked but acceptable (PR6 cleanup).

2. **Synthetic install works end-to-end.** Given `$HOME=/tmp/testuser` and `~/.arkaos/profile.json` containing `{"version":"3","vaultPath":"/tmp/testuser/vault","reposRoot":"/tmp/testuser/repos","projectRoots":["/tmp/testuser/code"]}`, when every SKILL.md is loaded, then `${VAULT_PATH}`, `${ARKA_OS_REPOS}` and `${GIT_HOST}` resolve to the configured values with zero `${` leakage.

3. **20K-user safe migration.** Given a legacy profile.json missing `projectRoots` and `reposRoot`, when `npx arkaos@latest update` runs, then:
   - `projectRoots` is derived from parsing `projectsDir` text (regex extracts absolute paths).
   - If parsing finds 0 paths, sensible defaults are applied (`["~/Herd","~/Work","~/AIProjects"]`).
   - `reposRoot` defaults to `~/AIProjects` (or first match containing `AIProjects` if any).
   - `version` bumps to `"3"`, `migrated_at` timestamp added.
   - A `.bak-<timestamp>` backup is written first.
   - `[arka:migrated] profile.json schema v2 → v3` logged.

4. **Hard error on truly missing profile.** Given `~/.arkaos/profile.json` is absent or unparseable JSON, when any `path_resolver` call runs, then `ProfileMissingError("Run /arka setup to configure ArkaOS paths")` is raised. No silent fallback.

5. **Env-var override.** Given `ARKAOS_VAULT_PATH=/tmp/override` is set, when `${VAULT_PATH}` is resolved, then the env var wins over profile. Same for `ARKAOS_REPOS_ROOT`, `ARKAOS_PROJECT_ROOTS`, `ARKAOS_GIT_HOST`. Empty string is treated as unset.

6. **Regression-free.** Given PR1 is merged, when full pytest suite runs, then all existing 542+ tests pass and ≥ 15 new path_resolver tests pass. Coverage ≥ 80%.

7. **Migration idempotent.** Given migration ran once, when it runs again, then profile.json is unchanged (no version re-bump, no second backup).

## Data Model

| Field (new in profile.json v3) | Type | Default | Source |
|---|---|---|---|
| `version` | `"3"` (str) | — | bumped by migration |
| `projectRoots` | `list[str]` | `["~/Herd","~/Work","~/AIProjects"]` | parsed from `projectsDir` text on migration |
| `reposRoot` | `str` | `"~/AIProjects"` | matches first path containing `AIProjects`, else default |
| `migrated_at` | ISO8601 `str` | — | written at migration time |

**Backwards-compat fields kept verbatim:** `language`, `market`, `role`, `company`, `projectsDir` (kept for human reference), `vaultPath`, `created`, `updated`.

## API Contracts

### `core/runtime/path_resolver.py`

```python
class ProfileMissingError(RuntimeError):
    """Raised when ~/.arkaos/profile.json is absent or unparseable."""

@dataclass
class ProfileV3:
    version: str
    vault_path: str          # ${VAULT_PATH}
    repos_root: str          # ${ARKA_OS_REPOS}
    project_roots: list[str] # ${PROJECT_ROOTS}
    raw: dict                # full profile.json for forward-compat

def load_profile() -> ProfileV3:
    """Load and cache ~/.arkaos/profile.json. Raises ProfileMissingError."""

def resolve(template: str) -> str:
    """Substitute known tokens. Unknown tokens pass through unchanged.

    Tokens:
      ${VAULT_PATH}      -> ARKAOS_VAULT_PATH env or profile.vaultPath
      ${ARKA_OS_REPOS}   -> ARKAOS_REPOS_ROOT env or profile.reposRoot
      ${PROJECT_ROOTS}   -> os.pathsep-joined profile.projectRoots
      ${GIT_HOST}        -> ARKAOS_GIT_HOST env or "github.com"
      ${HOME}            -> os.path.expanduser("~")
    """

def resolve_dict(d: dict) -> dict:
    """Recursively resolve string values in a JSON-shaped dict."""

def project_root_regex() -> re.Pattern:
    """Compile regex from profile.projectRoots for collector.py."""
```

### Skill loader extension

Find existing skill loader (likely `core/agents/loader.py` or `arka/skills/.../loader`); extend:

```python
def load_skill_markdown(path: Path) -> str:
    return path_resolver.resolve(path.read_text())
```

### Migration script `installer/migrations/v3_path_schema.js`

```javascript
function migrateV3(profile) {
  if (profile.version === "3" || profile.projectRoots) return profile;
  const roots = parseProjectsDirText(profile.projectsDir);
  const reposRoot = roots.find(r => r.includes("AIProjects")) || "~/AIProjects";
  return { ...profile, version: "3", projectRoots: roots,
           reposRoot, migrated_at: new Date().toISOString() };
}
```

Wired into `installer/migrate-user-data.js` (existing framework).

## Edge Cases

1. **`projectsDir` text is empty / null** → defaults applied (no error).
2. **`vaultPath` empty string** → treated as missing → `ProfileMissingError`.
3. **SKILL.md contains literal `${SOME_BASH_VAR}` for agent instructions** → resolver only touches the 5 known tokens; unknown tokens pass through.
4. **Windows path separators in `${PROJECT_ROOTS}`** → uses `os.pathsep` (`;` on Windows, `:` on Unix). Internal storage is POSIX `/`.
5. **Digest path from foreign OS** (cross-machine Obsidian sync) → `_detect_project` falls back to `os.getcwd()` if no `projectRoots` match (existing behaviour).
6. **Concurrent calls during migration** → migration uses temp-file + atomic rename; safe.
7. **User edits profile.json manually mid-session** → load_profile is cached per-process; re-import to refresh. Documented.
8. **Migration corrupts profile** → `.bak-<timestamp>` rollback file always exists.

## Test Scenarios

| # | Scenario | Type | Expected |
|---|---|---|---|
| 1 | `resolve("${VAULT_PATH}/foo")` with `vaultPath="/v"` | Unit | `"/v/foo"` |
| 2 | `resolve("${HOME}/bar")` | Unit | `"$HOME/bar"` expanded |
| 3 | `resolve("${UNKNOWN}/baz")` | Unit | `"${UNKNOWN}/baz"` unchanged |
| 4 | `resolve` with absent profile.json | Unit | `ProfileMissingError` |
| 5 | `resolve` with `ARKAOS_VAULT_PATH=/x` | Unit | env wins over profile |
| 6 | `resolve_dict` on obsidian-config.json fixture | Unit | All string values resolved |
| 7 | `_detect_project` with `projectRoots=["~/Herd"]` | Unit | matches path under `~/Herd` |
| 8 | `_detect_project` on Windows-style path | Unit | matches with `\` separator |
| 9 | `load_skill_markdown` on kb SKILL.md | Integration | `${VAULT_PATH}` substituted |
| 10 | full pytest suite | Regression | all 542+ tests pass |
| 11 | `migrateV3` on legacy profile (v2 schema) | Integration | new fields added, old kept, .bak written |
| 12 | `migrateV3` idempotent (second run no-op) | Integration | profile unchanged, no second .bak |
| 13 | Grep audit (CRITICAL paths) | Audit | 0 hits in core/ arka/ installer/ config/ departments/ knowledge/ |
| 14 | `scaffold SKILL.md ${GIT_HOST}` | Integration | `github.com` default |
| 15 | `comfyui SKILL.md ${ARKA_OS_REPOS}` | Integration | substituted correctly |
| 16 | `migrateV3` with empty `projectsDir` | Unit | defaults applied, no crash |
| 17 | env vars with empty string values | Unit | treated as unset, profile wins |

## Dependencies

- No external deps. Reuses existing `installer/migrate-user-data.js` framework + `core/specs/` Living Specs engine.
- New Python module only depends on stdlib (`json`, `os`, `pathlib`, `re`, `dataclasses`).

## Migration Plan for 20K Users

`npx arkaos@latest update` runs `migrate-user-data.js` which includes the new `migrateV3` step. Flow:

1. Read `~/.arkaos/profile.json`. If absent → skip migration (user must run `/arka setup`).
2. If `version === "3"` or `projectRoots` exists → no-op (idempotent).
3. Otherwise:
   - Write backup: `~/.arkaos/profile.json.bak-<unix-timestamp>`.
   - Parse `projectsDir` text with `/((?:\/Users|\/home|[A-Z]:\\Users)\/\S+?\/(?:Herd|Work|AIProjects|code|repos))/g`.
   - Apply defaults if parsing yields 0 results.
   - Atomic write: temp file + `fs.rename`.
   - Log `[arka:migrated] profile.json schema v2 → v3 ({N} roots, repos=...)` to `~/.arkaos/logs/migrate.log`.

**Rollback procedure (documented in installer):** restore `.bak-<timestamp>` over profile.json.

## Quality Gate Criteria

Marta (CQO) requires APPROVED from all three reviewers:

- **Eduardo (Copy):** All SKILL.md files read naturally after substitution — no `${` leakage in human-facing prose. Error messages clear and actionable.
- **Francisca (Tech):** path_resolver handles all 8 edge cases. Migration is atomic + idempotent + reversible. 17 test scenarios all green. No crash on corrupt profile.
- **Marta (CQO):** Migration verified non-breaking by simulating 5 different legacy profile shapes (André's current one + 4 synthetic variants representing common 20K-user variations).

## References

- Plan: `~/.arkaos/plans/2026-05-13-arkaos-next-level-conclave.md` (PR1 section)
- Memory: [[project_next_level_conclave]]
- KB: [[2026-04-29-claude-code-2-1-122-and-2-1-123]] (Claude Code features unblocked by 2.1.122)
- Existing Specs in this project: [[SPEC-cognitive-layer-feedback-loop]], [[SPEC-wave1-single-source-of-truth]]
