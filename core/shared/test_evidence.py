"""Test-evidence parsing shared by rule enforcement and evidence checks.

Extracted from ``core.workflow.rules_registry`` (PR-4 evidence Quality
Gate) so ``core.governance.evidence_checks`` can reuse the exact same
coverage/junit parsing instead of duplicating it.
"""

import re
from pathlib import Path
from typing import Optional

TEST_EVIDENCE_FILES: tuple[str, ...] = ("coverage.xml", ".coverage", "junit.xml")

_COVERAGE_LINE_RATE_RE = re.compile(r'<coverage[^>]*\bline-rate="([\d.]+)"')


def find_test_evidence(cwd: Path) -> Optional[Path]:
    """Locate a test-evidence artifact (coverage/junit report or pytest cache)."""
    for name in TEST_EVIDENCE_FILES:
        candidate = cwd / name
        if candidate.is_file():
            return candidate
    cache = cwd / ".pytest_cache"
    return cache if cache.is_dir() else None


def coverage_percent_from_xml(path: Path) -> Optional[float]:
    """Parse total line-rate from a coverage.xml report as a percentage."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    match = _COVERAGE_LINE_RATE_RE.search(text)
    return float(match.group(1)) * 100 if match else None
