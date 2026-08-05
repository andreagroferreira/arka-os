"""Migration runner for the ArkaOS Sync Engine — propose-only codemods.

Content sync aligns what ArkaOS *owns* inside a project. It cannot touch
what the project itself built the wrong way because the right way did not
exist yet: a repo scaffolded before a convention landed keeps the old shape
forever, and no amount of re-syncing a managed block will notice.

A migration closes that half. It carries a detection regex, the paths worth
scanning, and — optionally — the replacement that would fix it. Migrations
run only for versions newer than the last sync, so an upgrade surfaces
exactly the debt that upgrade created.

**Nothing is ever written to a project.** The run produces a single
reviewable proposal under ``~/.arkaos/migration-proposals/``. Rewriting
business logic under the operator, in a live client project, would
be indefensible the first time the regex is wrong — so the tool plans and
the human applies.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from core.sync.manifest import is_version_newer
from core.sync.schema import (
    MigrationHit,
    MigrationScanResult,
    MigrationSpec,
    Project,
)

# Directories that are never the operator's source of truth. Scanning them
# is slow and every hit is noise from a vendored dependency.
_SKIP_DIRS = frozenset(
    {
        ".git",
        "node_modules",
        "vendor",
        "dist",
        "build",
        ".next",
        ".nuxt",
        "__pycache__",
        ".venv",
        "venv",
        "storage",
        "coverage",
    }
)

_MAX_FILES_PER_PROJECT = 2000
_MAX_HITS_PER_MIGRATION = 20
_MAX_EXCERPT = 200


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_migrations(migrations_dir: Path) -> list[MigrationSpec]:
    """Load every MigrationSpec from YAML files in migrations_dir."""
    if not migrations_dir.is_dir():
        return []
    specs: list[MigrationSpec] = []
    for path in sorted(migrations_dir.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if data:
            specs.append(MigrationSpec(**data))
    return specs


def pending_migrations(
    specs: list[MigrationSpec], previous_version: str, is_first_sync: bool
) -> list[MigrationSpec]:
    """Return migrations introduced after previous_version.

    A first sync runs none: migrations repair debt an *upgrade* created, and
    a project seeing ArkaOS for the first time has no upgrade behind it.
    """
    if is_first_sync:
        return []
    return [s for s in specs if is_version_newer(s.added_in, previous_version)]


def scan_project(project: Project, spec: MigrationSpec) -> tuple[list[MigrationHit], bool]:
    """Scan one project for one migration. Returns (hits, was_truncated)."""
    pattern = re.compile(spec.detect)
    hits: list[MigrationHit] = []
    for file in _candidate_files(Path(project.path), spec.paths):
        hits.extend(_scan_file(file, project, spec, pattern))
        if len(hits) >= _MAX_HITS_PER_MIGRATION:
            return hits[:_MAX_HITS_PER_MIGRATION], True
    return hits, False


def run_migrations(
    projects: list[Project], specs: list[MigrationSpec], proposals_dir: Path, version: str
) -> MigrationScanResult:
    """Scan every project for every pending migration and write one proposal."""
    result = MigrationScanResult(migrations_run=[s.name for s in specs])
    if not specs:
        return result

    for spec in specs:
        for project in projects:
            try:
                hits, truncated = scan_project(project, spec)
            except OSError:
                continue
            result.hits.extend(hits)
            if truncated:
                result.truncated.append(f"{spec.name}@{project.name}")

    if result.hits:
        result.proposal_path = str(
            _write_proposal(result, specs, proposals_dir, version)
        )
    return result


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _candidate_files(root: Path, patterns: list[str]):
    """Yield scannable files under root, skipping vendored trees."""
    if not root.is_dir():
        return
    seen: set[Path] = set()
    count = 0
    for pattern in patterns:
        for path in root.glob(pattern):
            if count >= _MAX_FILES_PER_PROJECT:
                return
            if path in seen or not path.is_file():
                continue
            if _SKIP_DIRS.intersection(path.relative_to(root).parts):
                continue
            seen.add(path)
            count += 1
            yield path


def _scan_file(
    file: Path, project: Project, spec: MigrationSpec, pattern: re.Pattern[str]
) -> list[MigrationHit]:
    try:
        text = file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    hits: list[MigrationHit] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not pattern.search(line):
            continue
        hits.append(
            MigrationHit(
                migration=spec.name,
                project=project.name,
                file=str(file),
                line=number,
                excerpt=line.strip()[:_MAX_EXCERPT],
                proposed=(
                    pattern.sub(spec.replace, line).strip()[:_MAX_EXCERPT]
                    if spec.replace is not None
                    else None
                ),
            )
        )
    return hits


def _write_proposal(
    result: MigrationScanResult,
    specs: list[MigrationSpec],
    proposals_dir: Path,
    version: str,
) -> Path:
    proposals_dir.mkdir(parents=True, exist_ok=True)
    by_name = {s.name: s for s in specs}
    lines = [
        f"# ArkaOS migration proposals — v{version}",
        "",
        "Patterns that predate an ArkaOS feature. Nothing here has been applied:",
        "review each hit and change it yourself, or ignore it. This file is",
        "regenerated on every `/arka update`.",
        "",
    ]
    for name in dict.fromkeys(h.migration for h in result.hits):
        lines += _proposal_section(name, by_name[name], result)
    if result.truncated:
        lines += [
            "## Truncated",
            "",
            f"Capped at {_MAX_HITS_PER_MIGRATION} hits per migration per project:",
            *[f"- {entry}" for entry in result.truncated],
            "",
        ]
    path = proposals_dir / f"{version}.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _proposal_section(
    name: str, spec: MigrationSpec, result: MigrationScanResult
) -> list[str]:
    hits = [h for h in result.hits if h.migration == name]
    lines = [f"## {name} — {spec.description}", ""]
    if spec.guidance:
        lines += [spec.guidance, ""]
    for project in dict.fromkeys(h.project for h in hits):
        lines.append(f"### {project}")
        lines.append("")
        for hit in (h for h in hits if h.project == project):
            lines.append(f"- `{hit.file}:{hit.line}`")
            lines.append(f"  - now: `{hit.excerpt}`")
            if hit.proposed is not None:
                lines.append(f"  - proposed: `{hit.proposed}`")
        lines.append("")
    return lines
