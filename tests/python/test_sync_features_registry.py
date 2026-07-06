"""Locking test: the feature registry must be self-detecting.

Each `core/sync/features/*.yaml` drives the /arka update Phase 4 sync:
`detection_pattern` decides whether a feature section already exists in
an ecosystem SKILL.md, and `content` is what gets injected when it does
not. If the pattern does not match the feature's own content (the
v4.3.2-era state of forge.yaml and spec-gate.yaml), every naive sync
re-injects a duplicate section — the registry lies to its consumer.

The contract locked here:
- `content` is wrapped in `<!-- arka:feature:<name>:start/end -->`
  markers (the removal anchor, already in use in deployed skills);
- `detection_pattern` matches the feature's own `content`, so injected
  sections are always detected on the next run;
- the pattern also matches a bare `## <section_title>` heading, so
  legacy or operator-customized sections (unmarked) are never duplicated.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from core.sync.schema import FeatureSpec

_ROOT = Path(__file__).resolve().parents[2]
_FEATURES_DIR = _ROOT / "core" / "sync" / "features"
_FEATURE_FILES = sorted(_FEATURES_DIR.glob("*.yaml"))


def _load(path: Path) -> FeatureSpec:
    return FeatureSpec(**yaml.safe_load(path.read_text(encoding="utf-8")))


def test_registry_is_not_empty():
    assert _FEATURE_FILES, f"no feature YAMLs found in {_FEATURES_DIR}"


@pytest.mark.parametrize("path", _FEATURE_FILES, ids=lambda p: p.stem)
def test_content_is_wrapped_in_feature_markers(path: Path):
    spec = _load(path)
    lines = spec.content.strip().splitlines()
    assert lines[0] == f"<!-- arka:feature:{spec.name}:start -->", (
        f"{path.name}: content must open with the start marker "
        f"(removal/detection anchor for deprecation)"
    )
    assert lines[-1] == f"<!-- arka:feature:{spec.name}:end -->", (
        f"{path.name}: content must close with the end marker"
    )


@pytest.mark.parametrize("path", _FEATURE_FILES, ids=lambda p: p.stem)
def test_detection_pattern_matches_own_content(path: Path):
    spec = _load(path)
    assert re.search(spec.detection_pattern, spec.content), (
        f"{path.name}: detection_pattern {spec.detection_pattern!r} does not "
        "match the feature's own content — a naive sync would re-inject a "
        "duplicate section on every run"
    )


@pytest.mark.parametrize("path", _FEATURE_FILES, ids=lambda p: p.stem)
def test_detection_pattern_matches_bare_section_heading(path: Path):
    """Deployed skills predating the markers (and operator-customized
    sections, e.g. bespoke Workflow Tiers tables) carry only the plain
    `## <section_title>` heading. Detection must catch those too."""
    spec = _load(path)
    bare_section = f"## {spec.section_title}\n\ncustom operator content\n"
    assert re.search(spec.detection_pattern, bare_section), (
        f"{path.name}: detection_pattern {spec.detection_pattern!r} misses a "
        f"bare '## {spec.section_title}' section — customized ecosystem "
        "skills would get a duplicate section injected"
    )


# Realistic summary-line prose from real department SKILLs (ops:23, dev:28):
# mentions the same people/tiers WITHOUT being the injected sections. A
# pattern that matches this text would mark the feature "present" in a
# skill that lacks the section, and a mandatory section is never injected
# — the mirror image of the duplicate-injection bug.
_SUMMARY_LINE_PROSE = (
    "# Some Ecosystem\n\n"
    "Quality supervision: Marta (CQO) + Eduardo (copy) + Francisca (tech) "
    "review everything — absolute veto.\n"
    "Workflows: Enterprise (10-phase), Focused (4-phase), Specialist "
    "(2-phase), selected by complexity.\n"
    "Specs live under docs/ and planning is multi-agent.\n"
)


@pytest.mark.parametrize("path", _FEATURE_FILES, ids=lambda p: p.stem)
def test_detection_pattern_does_not_overmatch_summary_prose(path: Path):
    spec = _load(path)
    match = re.search(spec.detection_pattern, _SUMMARY_LINE_PROSE)
    assert match is None, (
        f"{path.name}: detection_pattern {spec.detection_pattern!r} matches "
        f"unrelated summary prose ({match.group(0)!r}) — the feature would be "
        "considered present and its mandatory section never injected"
    )
