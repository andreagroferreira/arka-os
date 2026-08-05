"""Migration runner for the ArkaOS Sync Engine — propose-only codemods.

Content sync aligns what ArkaOS *owns* inside a project. It cannot touch
what the project itself built the wrong way because the right way did not
exist yet: a repo scaffolded before a convention landed keeps the old shape
forever, and no amount of re-syncing a managed block will notice.

A migration covers the other half. It carries a detection regex, the paths
worth scanning, and optionally the replacement that would fix it.
Migrations run only for versions newer than the last sync, so an upgrade
surfaces the debt that upgrade exposes — the debt itself predates it.

**Nothing is ever written to a project.** A run with hits produces a single
reviewable proposal under ``~/.arkaos/migration-proposals/``. Rewriting
business logic under the operator, in a live client project, would be
indefensible the first time the regex is wrong — so the tool plans and the
human applies.

Specs come from a user-writable YAML directory, so every one of them is
treated as untrusted input: a bad pattern, an unloadable file or a
runaway regex is recorded against that spec and the sync continues. One
bad migration must never abort a run that has already written to disk.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import ValidationError

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
# Lines longer than this are minified assets or embedded data, not the source
# a migration means. This bounds ordinary work; it is NOT a ReDoS mitigation —
# a nested quantifier backtracks exponentially and blows up on a few dozen
# characters. The actual guard is _REDOS_RE below, which refuses the pattern
# shapes that can do it. Python's `re` has no timeout, so a pattern that gets
# past both would still hang the run: keep specs reviewed.
_MAX_LINE_LENGTH = 4000

_QUANTIFIERS = "+*{"


def has_nested_quantifier(pattern: str) -> bool:
    """True when a quantified group itself contains a quantifier.

    ``(a+)+``, ``(a*)*``, ``((a)+)+`` — the shape behind catastrophic
    backtracking. Walks the parentheses so nesting is seen; a flat regex
    misses ``((a)+)+``. Recognises the common shape, not every pathological
    pattern — it is a guard, not a proof of safety.
    """
    stack: list[int] = []
    i = 0
    while i < len(pattern):
        ch = pattern[i]
        skip = _skip_literal(pattern, i)
        if skip is not None:
            i = skip
            continue
        if ch == "(":
            stack.append(i)
        elif ch == ")" and stack:
            start = stack.pop()
            following = pattern[i + 1 : i + 2]
            if following in _QUANTIFIERS and _contains_quantifier(
                pattern[start + 1 : i]
            ):
                return True
        i += 1
    return False


def _skip_literal(text: str, i: int) -> int | None:
    """Index past an escape or a character class at i, or None if neither."""
    if text[i] == "\\":
        return i + 2
    if text[i] == "[":
        close = text.find("]", i + 1)
        return len(text) if close == -1 else close + 1
    return None


def _contains_quantifier(body: str) -> bool:
    """True when body has a quantifier outside escapes and character classes."""
    i = 0
    while i < len(body):
        skip = _skip_literal(body, i)
        if skip is not None:
            i = skip
            continue
        if body[i] in _QUANTIFIERS:
            return True
        i += 1
    return False


@dataclass
class _Compiled:
    """A spec whose pattern compiled cleanly and is safe to apply."""

    spec: MigrationSpec
    pattern: re.Pattern[str]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_migrations(migrations_dir: Path) -> tuple[list[MigrationSpec], list[str]]:
    """Load every MigrationSpec from migrations_dir. Returns (specs, errors).

    A malformed or incomplete YAML file is recorded and skipped. Raising here
    would abort ``/arka update`` *after* content, agents and skills have
    already been written to disk and *before* the new version is recorded —
    leaving a half-applied sync that the next run cannot see.
    """
    if not migrations_dir.is_dir():
        return [], []
    specs: list[MigrationSpec] = []
    errors: list[str] = []
    for path in sorted(migrations_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            errors.append(f"{path.name}: unreadable ({exc.__class__.__name__})")
            continue
        if not data:
            continue
        try:
            specs.append(MigrationSpec(**data))
        except (ValidationError, TypeError) as exc:
            errors.append(f"{path.name}: invalid spec ({exc.__class__.__name__})")
    return specs, errors


def compile_specs(specs: list[MigrationSpec]) -> tuple[list[_Compiled], list[str]]:
    """Compile every detect pattern up front. Returns (compiled, errors).

    ``replace`` is exercised against a probe so a bad backreference fails
    here, once, rather than mid-scan on the operator's files.
    """
    compiled: list[_Compiled] = []
    errors: list[str] = []
    for spec in specs:
        if has_nested_quantifier(spec.detect):
            errors.append(
                f"{spec.name}: refused — nested quantifier can backtrack "
                "exponentially; rewrite without a quantified group inside a "
                "quantifier"
            )
            continue
        try:
            pattern = re.compile(spec.detect)
            if spec.replace is not None:
                pattern.sub(spec.replace, "")
        except re.error as exc:
            errors.append(f"{spec.name}: bad pattern ({exc})")
            continue
        compiled.append(_Compiled(spec=spec, pattern=pattern))
    return compiled, errors


def pending_migrations(
    specs: list[MigrationSpec], previous_version: str, is_first_sync: bool
) -> list[MigrationSpec]:
    """Return migrations introduced after previous_version.

    A first sync runs none: migrations repair debt that predates a feature,
    and a project seeing ArkaOS for the first time has no upgrade behind it.
    """
    if is_first_sync:
        return []
    return [s for s in specs if is_version_newer(s.added_in, previous_version)]


def scan_project(project: Project, spec: MigrationSpec) -> tuple[list[MigrationHit], bool]:
    """Scan one project for one migration. Returns (hits, was_truncated)."""
    compiled, errors = compile_specs([spec])
    if errors:
        return [], False
    hits, truncated, _ = _scan(project, compiled)
    return hits.get(spec.name, []), bool(truncated)


def run_migrations(
    projects: list[Project], specs: list[MigrationSpec], proposals_dir: Path, version: str
) -> MigrationScanResult:
    """Scan every project for every pending migration and write one proposal."""
    result = MigrationScanResult(migrations_run=[s.name for s in specs])
    if not specs:
        return result

    compiled, compile_errors = compile_specs(specs)
    result.errors.extend(compile_errors)
    if not compiled:
        return result

    for project in projects:
        hits, truncated, errors = _scan(project, compiled)
        for name in (c.spec.name for c in compiled):
            result.hits.extend(hits.get(name, []))
        result.truncated.extend(f"{reason}@{project.name}" for reason in truncated)
        result.errors.extend(f"{project.name}: {e}" for e in errors)

    if result.hits:
        result.proposal_path = str(
            _write_proposal(result, specs, proposals_dir, version)
        )
    return result


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _candidate_files(root: Path, patterns: list[str]) -> tuple[list[Path], bool]:
    """Return (files, hit_file_cap) for one project, skipping vendored trees.

    The cap is returned, not swallowed: a scan that silently stopped at 2000
    files reads as a complete result to whoever gets the proposal.
    """
    if not root.is_dir():
        return [], False
    files: list[Path] = []
    seen: set[Path] = set()
    for pattern in patterns:
        try:
            candidates = root.glob(pattern)
        except (OSError, ValueError):
            continue
        for path in candidates:
            if len(files) >= _MAX_FILES_PER_PROJECT:
                return files, True
            if path in seen or not path.is_file():
                continue
            if _SKIP_DIRS.intersection(path.relative_to(root).parts):
                continue
            seen.add(path)
            files.append(path)
    return files, False


def _scan(
    project: Project, compiled: list[_Compiled]
) -> tuple[dict[str, list[MigrationHit]], list[str], list[str]]:
    """Scan a project once, applying every spec per line.

    One pass over the union of every spec's paths, instead of a fresh glob
    and a fresh read per spec: with dozens of projects the repeated reads
    dominate the run and buy nothing.
    """
    paths = list(dict.fromkeys(p for c in compiled for p in c.spec.paths))
    files, hit_cap = _candidate_files(Path(project.path), paths)
    hits: dict[str, list[MigrationHit]] = {c.spec.name: [] for c in compiled}
    truncated, errors, unreadable = (["file-cap"] if hit_cap else []), [], []
    dropped: set[str] = set()

    for file in files:
        try:
            text = file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            unreadable.append(f"{file.name}: {exc.__class__.__name__}")
            continue
        _scan_text(text, file, project, compiled, hits, dropped, errors)

    # Only a hit that was actually discarded means the list is incomplete.
    # Reporting on `len == cap` claims truncation for a scan that found
    # exactly the cap and lost nothing.
    truncated += [f"{name}:hit-cap" for name in sorted(dropped)]
    if unreadable:
        errors.append(f"{len(unreadable)} file(s) unreadable, first: {unreadable[0]}")
    return hits, truncated, errors


def _scan_text(
    text: str,
    file: Path,
    project: Project,
    compiled: list[_Compiled],
    hits: dict[str, list[MigrationHit]],
    dropped: set[str],
    errors: list[str],
) -> None:
    """Apply every compiled spec to every line of one file."""
    for number, line in enumerate(text.splitlines(), start=1):
        if len(line) > _MAX_LINE_LENGTH:
            continue
        for c in compiled:
            hit = _match_line(c, project, file, number, line, errors)
            if hit is None:
                continue
            bucket = hits[c.spec.name]
            if len(bucket) < _MAX_HITS_PER_MIGRATION:
                bucket.append(hit)
            else:
                dropped.add(c.spec.name)


def _match_line(
    c: _Compiled,
    project: Project,
    file: Path,
    number: int,
    line: str,
    errors: list[str],
) -> MigrationHit | None:
    try:
        if not c.pattern.search(line):
            return None
        proposed = (
            c.pattern.sub(c.spec.replace, line).strip()[:_MAX_EXCERPT]
            if c.spec.replace is not None
            else None
        )
    except re.error as exc:
        message = f"{c.spec.name}: {exc}"
        if message not in errors:
            errors.append(message)
        return None
    return MigrationHit(
        migration=c.spec.name,
        project=project.name,
        file=str(file),
        line=number,
        excerpt=line.strip()[:_MAX_EXCERPT],
        proposed=proposed,
    )


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
        "review each hit and change it yourself, or ignore it.",
        "",
        f"Written for the update that crossed v{version}. Later updates write",
        "their own file and do not refresh this one — delete it once you have",
        "worked through it.",
        "",
    ]
    for name in dict.fromkeys(h.migration for h in result.hits):
        lines += _proposal_section(name, by_name[name], result)
    lines += _proposal_caveats(result)
    path = proposals_dir / f"{version}.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _proposal_caveats(result: MigrationScanResult) -> list[str]:
    """Everything that makes the lists above incomplete, never omitted."""
    lines: list[str] = []
    if result.truncated:
        lines += [
            "## Incomplete scans",
            "",
            "These scans stopped early, so the lists above are not exhaustive.",
            f"`hit-cap` = more than {_MAX_HITS_PER_MIGRATION} hits for that "
            f"migration; `file-cap` = {_MAX_FILES_PER_PROJECT} files reached "
            "for that project and the rest went unscanned.",
            "",
            *[f"- {entry}" for entry in result.truncated],
            "",
        ]
    if result.errors:
        lines += [
            "## Migrations that could not run",
            "",
            *[f"- {entry}" for entry in result.errors],
            "",
        ]
    return lines


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
