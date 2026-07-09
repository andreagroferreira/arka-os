"""Client-name leak scanner (PR22 v2.44.0).

Reads the user-local ``~/.arkaos/redaction-clients.json`` and scans
source files / arbitrary text for word-boundary matches. Wired into
the release preflight gate as a blocking check.

Closes a real process gap: PR20 v2.42.0 shipped 9 client names in a
production constant; the Quality Gate did not flag it; operator
caught it manually pre-commit. Automation > checklist.

Empty / missing config is a no-op by design — there are no false
positives in CI clones that lack the operator's local list.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

_DEFAULT_CONFIG_PATH = Path.home() / ".arkaos" / "redaction-clients.json"
_MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB per-file cap
_SCAN_EXTENSIONS: frozenset[str] = frozenset({
    ".py", ".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs",
    ".json", ".yaml", ".yml", ".toml", ".md", ".sh", ".txt",
})
_EXCLUDE_DIRS: frozenset[str] = frozenset({
    "node_modules", "__pycache__", ".venv", ".git", "dist", "build",
})
_LINE_EXCERPT_LIMIT = 200


@dataclass(frozen=True)
class LeakHit:
    """One client-name occurrence in a scanned file."""
    path: Path
    line_number: int
    line_excerpt: str
    matched_token: str


@dataclass(frozen=True)
class ScanReport:
    """Result of a scan."""
    config_path: Path
    pattern_count: int
    files_scanned: int
    hits: list[LeakHit]

    @property
    def clean(self) -> bool:
        return not self.hits


def scan_paths(
    paths: Iterable[Path],
    *,
    config_path: Path | None = None,
) -> ScanReport:
    """Recursively scan the given paths for client-name leaks."""
    cfg = config_path or _DEFAULT_CONFIG_PATH
    patterns = _load_patterns(cfg)
    if not patterns:
        return ScanReport(config_path=cfg, pattern_count=0, files_scanned=0, hits=[])
    regex = _build_regex(patterns)
    hits: list[LeakHit] = []
    files_scanned = 0
    for path in paths:
        for file_path in _iter_scannable_files(Path(path)):
            files_scanned += 1
            hits.extend(_scan_file(file_path, regex))
    return ScanReport(
        config_path=cfg,
        pattern_count=len(patterns),
        files_scanned=files_scanned,
        hits=hits,
    )


def scan_text(
    text: str,
    *,
    config_path: Path | None = None,
) -> list[str]:
    """Return the list of matched tokens (lowercased) found in *text*."""
    cfg = config_path or _DEFAULT_CONFIG_PATH
    patterns = _load_patterns(cfg)
    if not patterns:
        return []
    regex = _build_regex(patterns)
    return [m.group(1).lower() for m in regex.finditer(text)]


def load_redaction_patterns(config_path: Path | None = None) -> tuple[str, ...]:
    """Public accessor for the redaction client list.

    Consumed by core.evals.sanitizer (distillation prerequisite) so the
    scanner and the sanitizer can never disagree on what a client
    identifier is. Returns () when the config is missing or empty.
    """
    return _load_patterns(config_path or _DEFAULT_CONFIG_PATH)


def _load_patterns(config_path: Path) -> tuple[str, ...]:
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
        raw = data.get("clients", [])
        return tuple(
            str(c).strip().lower() for c in raw
            if c and isinstance(c, str)
        )
    except (OSError, json.JSONDecodeError, AttributeError):
        return ()


def _build_regex(patterns: tuple[str, ...]) -> re.Pattern[str]:
    escaped = [re.escape(p) for p in patterns]
    return re.compile(
        r"(?<![a-z0-9])(" + "|".join(escaped) + r")(?![a-z0-9])",
        re.IGNORECASE,
    )


def _iter_scannable_files(root: Path):
    if root.is_file():
        if _is_scannable(root):
            yield root
        return
    if not root.is_dir():
        return
    for entry in sorted(root.rglob("*")):
        if any(part in _EXCLUDE_DIRS for part in entry.parts):
            continue
        if entry.is_file() and _is_scannable(entry):
            yield entry


def _is_scannable(path: Path) -> bool:
    if path.suffix.lower() not in _SCAN_EXTENSIONS:
        return False
    try:
        if path.stat().st_size > _MAX_FILE_BYTES:
            return False
    except OSError:
        return False
    return True


def _scan_file(path: Path, regex: re.Pattern[str]) -> list[LeakHit]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    hits: list[LeakHit] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        for match in regex.finditer(line):
            hits.append(LeakHit(
                path=path,
                line_number=line_no,
                line_excerpt=line[:_LINE_EXCERPT_LIMIT],
                matched_token=match.group(1).lower(),
            ))
    return hits
