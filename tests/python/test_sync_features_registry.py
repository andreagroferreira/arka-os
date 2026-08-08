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

from core.sync.marker_audit import scan_tree
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


_SKILLS_MANIFEST = _ROOT / "knowledge" / "skills-manifest.json"


def _installed_skill_slugs() -> list[str]:
    import json

    manifest = json.loads(_SKILLS_MANIFEST.read_text(encoding="utf-8"))
    return [f"arka-{slug}" for slug in manifest["skills"]]


@pytest.mark.parametrize("path", _FEATURE_FILES, ids=lambda p: p.stem)
def test_detection_pattern_does_not_match_other_skill_slugs(path: Path):
    """QG 2026-08-04 (PR #449 register): the bare `arka-spec` alternative
    also matched the unrelated slug `arka-spec-miner`, so a loader that
    merely mentioned that skill would be scored as already having the
    section and silently skipped for a legitimate injection. Keyword
    alternatives must not fire inside another installed skill's slug."""
    spec = _load(path)
    for slug in _installed_skill_slugs():
        prose = f"See the {slug} skill for details."
        match = re.search(spec.detection_pattern, prose)
        if match is None:
            continue
        # A keyword alternative may legitimately match the exact skill it
        # names (the incidental-token mechanism, sync-engine.md:78) —
        # never a fragment of a longer slug.
        assert match.group(0) == slug, (
            f"{path.name}: detection_pattern {spec.detection_pattern!r} "
            f"matches a fragment of the unrelated installed slug {slug!r}"
        )


def _keyword_alternatives(pattern: str) -> list[str]:
    """Bare-token alternatives of a detection_pattern (marker/heading excluded),
    with any trailing lookahead anchor stripped."""
    import re as _re

    alts = []
    for alt in pattern.split("|"):
        if alt.startswith("arka:feature:") or alt.startswith("## "):
            continue
        alts.append(_re.sub(r"\(\?!\[[^]]*\]\)$", "", alt))
    return alts


@pytest.mark.parametrize("path", _FEATURE_FILES, ids=lambda p: p.stem)
def test_keyword_alternatives_do_not_match_longer_tokens(path: Path):
    """QG 2026-08-04 (PR #450): the manifest-driven collision test was
    vacuous for `arka-forge` (no manifest slug contains "forge"), so a
    revert of that anchor survived the suite. Probes are derived from the
    pattern's own keyword alternatives, locking every anchor regardless
    of what the manifest happens to contain — including digit, underscore
    and uppercase continuations, which `(?![a-z-])` wrongly admitted."""
    spec = _load(path)
    for alt in _keyword_alternatives(spec.detection_pattern):
        for suffix in ("-miner", "2", "_x", "Xtra"):
            probe = f"See the {alt}{suffix} skill for details."
            match = re.search(spec.detection_pattern, probe)
            assert match is None, (
                f"{path.name}: keyword alternative {alt!r} matches inside "
                f"the longer token {alt + suffix!r}"
            )


_REPO_MARKER_DIRS = ("arka", "departments")


def _audit_marker_regions(
    roots: list[Path], specs: dict[str, FeatureSpec]
) -> tuple[int, list[str]]:
    """Audit every marker in `roots`: shape first, then region identity.

    Returns ``(regions_checked, problems)``. Shape comes first on purpose.
    The old version searched for the literal bare marker and `continue`d on
    a miss, so a STAMPED marker (`:start version=5.10.0 hash=…`) was read as
    "no marker in this file" — eight of them, plus whatever drifted inside
    them, sailed through two releases (issue #492). A marker that no literal
    consumer matches is now a NAMED failure, never a skip.
    """
    problems = [v.describe() for root in roots for v in scan_tree(root)]
    checked = 0
    for root in roots:
        for md in sorted(root.rglob("*.md")):
            text = md.read_text(encoding="utf-8")
            for name, spec in specs.items():
                region = re.search(
                    rf"<!-- arka:feature:{name}:start -->.*?"
                    rf"<!-- arka:feature:{name}:end -->",
                    text,
                    re.DOTALL,
                )
                if region is None:
                    continue
                checked += 1
                if region.group(0).strip() != spec.content.strip():
                    problems.append(
                        f"{md}: marker region for {name!r} drifts from the "
                        "registry content"
                    )
    return checked, problems


def test_repo_marker_regions_match_registry_content():
    """Every in-repo file carrying real `arka:feature` markers must hold
    each marker-delimited region byte-identical to the registry `content`
    — the hole that let a stale figure live undetected inside a marked
    block (QG 2026-08-04, PR #450 blocker 3) — and carry the marker in its
    bare form, the only shape every consumer matches (issue #492)."""
    specs = {s.name: s for s in map(_load, _FEATURE_FILES)}
    roots = [_ROOT / base for base in _REPO_MARKER_DIRS]
    checked, problems = _audit_marker_regions(roots, specs)
    assert not problems, "\n".join(problems)
    assert checked, "no in-repo marker regions found — glob or dirs wrong"


def _spec_of(name: str) -> FeatureSpec:
    return next(s for s in map(_load, _FEATURE_FILES) if s.name == name)


def test_stamped_marker_in_a_scanned_tree_is_a_named_violation(tmp_path: Path):
    """RED-locked defect (a) of issue #492, hermetically: a stamped marker
    wrapping DRIFTED content used to be skipped in silence, so the drift
    lock passed. It must now fail, naming path, line and the stamp."""
    spec = _spec_of("quality-gate")
    body = spec.content.strip().splitlines()[1:-1]
    stamped = "\n".join(
        [
            "<!-- arka:feature:quality-gate:start version=5.10.0 hash=deadbeef1234 -->",
            *body,
            "STALE FIGURE THAT THE OLD LOCK NEVER SAW",
            "<!-- arka:feature:quality-gate:end version=5.10.0 hash=deadbeef1234 -->",
        ]
    )
    (tmp_path / "SKILL.md").write_text(f"# Ecosystem\n\n{stamped}\n", encoding="utf-8")

    checked, problems = _audit_marker_regions([tmp_path], {"quality-gate": spec})

    assert checked == 0, "a stamped marker is not a canonical region"
    assert len(problems) == 2, f"start and end must both be named: {problems}"
    assert all("SKILL.md" in p for p in problems)
    assert any("version=5.10.0" in p and ":3:" in p for p in problems)


def test_malformed_marker_in_a_scanned_tree_is_a_named_violation(tmp_path: Path):
    """The mirror case: a marker mangled by hand (no spaces) is equally
    invisible to every literal consumer, so it fails the same way."""
    spec = _spec_of("quality-gate")
    (tmp_path / "SKILL.md").write_text(
        "<!--arka:feature:quality-gate:start-->\n", encoding="utf-8"
    )

    _, problems = _audit_marker_regions([tmp_path], {"quality-gate": spec})

    assert len(problems) == 1
    assert "arka:feature:quality-gate:start" in problems[0]


def test_bare_marker_region_matching_the_registry_is_clean(tmp_path: Path):
    """Control: the canonical shape with canonical content raises nothing —
    the lock must fail on drift, not on everything."""
    spec = _spec_of("quality-gate")
    (tmp_path / "SKILL.md").write_text(spec.content.strip() + "\n", encoding="utf-8")

    checked, problems = _audit_marker_regions([tmp_path], {"quality-gate": spec})

    assert (checked, problems) == (1, [])
