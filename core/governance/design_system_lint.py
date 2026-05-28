"""Design System Linter — PR6 Squad Intelligence Upgrade v3.77.0.

Scans a project for forbidden patterns declared in its design-system.yaml.
Opt-in per project: no YAML at root means no violations. Advisory-only in
v3.77.0; pre-commit hook integration lands in v3.77.x.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field  # noqa: F401 (asdict kept for callers)
from pathlib import Path
from typing import Iterator

import yaml


# ─── Dataclasses ──────────────────────────────────────────────────────────────

@dataclass
class DesignSystem:
    """Loaded design-system.yaml for a project."""

    version: int = 1
    project: str = ""
    tokens: dict = field(default_factory=dict)
    allowed_components: list[str] = field(default_factory=list)
    file_globs: list[str] = field(default_factory=list)
    forbidden_patterns: list[dict] = field(default_factory=list)


@dataclass
class DesignViolation:
    file: str         # relative to project_path, forward slashes
    line: int         # 1-indexed
    pattern: str      # the regex string from forbidden_patterns
    suggestion: str   # suggestion text from forbidden_patterns
    matched_text: str  # the actual matched substring (cap 200 chars)


# ─── Internal helpers ─────────────────────────────────────────────────────────

def _default_file_globs() -> list[str]:
    return ["**/*.vue", "**/*.tsx", "**/*.jsx"]


def _escape_glob_literal(s: str) -> str:
    """Escape a literal glob segment (no ** inside)."""
    return re.escape(s).replace(r"\*", "[^/]*").replace(r"\?", "[^/]")


def _glob_to_regex(glob_pattern: str) -> re.Pattern[str]:
    """Translate a glob pattern (with ** support) to a compiled regex.

    Gitignore convention: ``**/`` = zero-or-more ``dir/`` prefixes (including
    zero), so ``**/*.vue`` matches both ``App.vue`` and ``src/App.vue``.
    Bare ``*`` = any non-slash run; ``?`` = one non-slash char.
    """
    # Split on ** tokens, keeping them as delimiters.
    tokens = re.split(r"(\*\*)", glob_pattern)
    result = ""
    for i, tok in enumerate(tokens):
        if tok != "**":
            result += _escape_glob_literal(tok)
            continue
        nxt = tokens[i + 1] if i + 1 < len(tokens) else ""
        if nxt.startswith("/"):
            # **/ → consume the slash, emit zero-or-more dir/ groups.
            tokens[i + 1] = nxt[1:]
            result += "(?:[^/]+/)*"
        else:
            # trailing ** or ** not followed by / → match any remaining path.
            result += ".*"
    return re.compile(f"^{result}$")


def _glob_match(pattern: str, rel_path: str) -> bool:
    """Return True when rel_path (forward slashes) matches the glob pattern."""
    try:
        return bool(_glob_to_regex(pattern).match(rel_path))
    except re.error:
        return False


def _iter_matching_files(
    project_path: Path, file_globs: list[str]
) -> Iterator[Path]:
    """Yield all files under project_path matching any glob in file_globs."""
    seen: set[Path] = set()
    for glob in file_globs:
        for path in project_path.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(project_path).as_posix()
            if _glob_match(glob, rel) and path not in seen:
                seen.add(path)
                yield path


def _is_excluded(rel_path: str, exclude_paths: list[str]) -> bool:
    """Return True if rel_path matches any exclude_paths glob or is design-system.yaml."""
    if rel_path == "design-system.yaml":
        return True
    return any(_glob_match(exc, rel_path) for exc in exclude_paths)


def _scan_file_for_pattern(
    file_path: Path,
    project_path: Path,
    compiled_re: re.Pattern[str],
    pattern: str,
    suggestion: str,
) -> Iterator[DesignViolation]:
    """Read one file and yield a DesignViolation for every regex match."""
    rel = file_path.relative_to(project_path).as_posix()
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return
    for lineno, line in enumerate(text.splitlines(), start=1):
        for match in compiled_re.finditer(line):
            yield DesignViolation(
                file=rel,
                line=lineno,
                pattern=pattern,
                suggestion=suggestion,
                matched_text=match.group(0)[:200],
            )


# ─── Public API ───────────────────────────────────────────────────────────────

def load_design_system(project_path: Path) -> DesignSystem | None:
    """Load design-system.yaml from project_path root.

    Returns None when the file is absent or malformed.
    """
    yaml_path = project_path / "design-system.yaml"
    if not yaml_path.is_file():
        return None
    try:
        raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return None
    if not isinstance(raw, dict):
        return None
    return DesignSystem(
        version=int(raw.get("version") or 1),
        project=str(raw.get("project") or ""),
        tokens=dict(raw.get("tokens") or {}),
        allowed_components=list(raw.get("allowed_components") or []),
        file_globs=list(raw.get("file_globs") or []),
        forbidden_patterns=list(raw.get("forbidden_patterns") or []),
    )


def lint_project(project_path: Path) -> list[DesignViolation]:
    """Scan project_path for design-system violations.

    Returns an empty list when the project path does not exist, has no
    design-system.yaml, or the YAML is malformed.
    """
    if not project_path.is_dir():
        return []
    ds = load_design_system(project_path)
    if ds is None:
        return []
    globs = ds.file_globs if ds.file_globs else _default_file_globs()
    violations: list[DesignViolation] = []
    for fp_dict in ds.forbidden_patterns:
        if not isinstance(fp_dict, dict):
            continue
        _collect_pattern_violations(project_path, globs, fp_dict, violations)
    return violations


def _collect_pattern_violations(
    project_path: Path,
    file_globs: list[str],
    fp_dict: dict,
    violations: list[DesignViolation],
) -> None:
    """Compile one forbidden pattern and append matching violations in-place."""
    raw_pattern = fp_dict.get("pattern", "")
    suggestion = fp_dict.get("suggestion", "")
    exclude_paths: list[str] = list(fp_dict.get("exclude_paths") or [])
    try:
        compiled = re.compile(raw_pattern)
    except re.error:
        return
    for file_path in _iter_matching_files(project_path, file_globs):
        rel = file_path.relative_to(project_path).as_posix()
        if _is_excluded(rel, exclude_paths):
            continue
        violations.extend(
            _scan_file_for_pattern(file_path, project_path, compiled, raw_pattern, suggestion)
        )
