"""Guard against stale model references (Runtime Sync 2026-09-03).

The operator's decision: Opus 4.x → Opus 5, Fable 5 → Fable 5.1, and the
weakest lane ArkaOS routes to is Sonnet 5 — never Haiku. Living code, config,
skills and docs must not name the old lanes. History (CHANGELOG, ADRs, dated
plans/specs) and the price table (old rows keep old sessions priced) are the
only places allowed to.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent

STALE = re.compile(
    r"\bopus-4-[5-8]\b|Opus 4\.[5-8]\b"
    r"|\bclaude-fable-5(?![-.\w])|Fable 5(?![.\d\w])"
    r"|haiku-4-5|Haiku 4\.5|^\s*model:\s*haiku\b",
    re.M,
)
ALLOWED_FILES = {
    "CHANGELOG.md",
    "core/runtime/pricing.py",          # old rows keep old sessions priced
    "tests/python/test_pricing.py",     # pins those historical rows
    "core/runtime/model_router.py",     # LEGACY_MODEL_IDS map
    "tests/python/test_model_router.py",
    "tests/python/test_model_references.py",
}
ALLOWED_PREFIXES = ("docs/adr/", "docs/superpowers/", "docs/strategy/")
TEXT_SUFFIXES = {".py", ".md", ".yaml", ".yml", ".json", ".js", ".cjs", ".mjs",
                 ".sh", ".bats", ".vue", ".ts", ".toml", ".txt"}


def _tracked_text_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    return [
        f for f in out
        if Path(f).suffix in TEXT_SUFFIXES
        and f not in ALLOWED_FILES
        and not f.startswith(ALLOWED_PREFIXES)
    ]


_PROSE_SURFACES = ("config/claude-agents/", "departments/")
_PROSE_ALLOWED = re.compile(
    r"never routed|never haiku|legacy YAML|LEGACY_MODEL_IDS|no shipped agent", re.I
)
_PROSE_HAIKU = re.compile(r"\bhaiku\b", re.I)


@pytest.mark.parametrize("sample", [
    "claude-opus-4-8", "best: claude-opus-4-8", "claude-opus-4-7[1m]",
    "claude-fable-5", "Opus 4.8", "  model: haiku", "claude-haiku-4-5-20251001",
])
def test_stale_regex_catches_retired_ids(sample):
    """The guard proves itself: every retired form the sweep removed must match."""
    assert STALE.search(sample), sample


@pytest.mark.parametrize("sample", [
    "claude-opus-5", "claude-fable-5-1", "Fable 5.1", "claude-sonnet-5",
    "claude-opus-5[1m]", "model: sonnet",
])
def test_stale_regex_ignores_current_ids(sample):
    assert not STALE.search(sample), sample


def test_no_prose_routes_to_haiku_in_shipped_instruction_surfaces():
    """QG B4: an agent definition or department hub that says "haiku" in
    prose still routes a non-gateway session to real Haiku. Only sentences
    that explicitly ban or scope it are allowed."""
    hits: list[str] = []
    for rel in _tracked_text_files():
        if not rel.startswith(_PROSE_SURFACES) or not rel.endswith(".md"):
            continue
        text = (REPO / rel).read_text(encoding="utf-8")
        for i, line in enumerate(text.splitlines(), 1):
            if _PROSE_HAIKU.search(line) and not _PROSE_ALLOWED.search(line):
                hits.append(f"{rel}:{i}: {line.strip()[:100]}")
    assert not hits, "instruction surfaces still route to Haiku:\n" + "\n".join(hits[:40])


def test_no_stale_model_references_outside_history():
    hits: list[str] = []
    for rel in _tracked_text_files():
        try:
            text = (REPO / rel).read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for m in STALE.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            hits.append(f"{rel}:{line}: {m.group(0)}")
    assert not hits, "stale model references (Opus 4.x / Fable 5 / Haiku):\n" + "\n".join(hits[:40])
