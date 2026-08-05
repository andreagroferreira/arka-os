"""Tests for core.sync.skill_syncer — deterministic Phase 4."""

from __future__ import annotations

from pathlib import Path

from core.sync.schema import FeatureSpec
from core.sync.skill_syncer import (
    discover_user_owned_skills,
    sync_all_skills,
    sync_skill,
)

VERSION = "5.10.0"
BODY = "## Forge Integration\n\nComplexity >= 5 routes to The Forge."


def _feature(deprecated_in: str | None = None) -> FeatureSpec:
    return FeatureSpec(
        name="forge-integration",
        added_in="5.0.0",
        mandatory=True,
        section_title="Forge Integration",
        detection_pattern="arka:feature:forge-integration|## Forge Integration",
        content=(
            "<!-- arka:feature:forge-integration:start -->\n"
            f"{BODY}\n"
            "<!-- arka:feature:forge-integration:end -->\n"
        ),
        deprecated_in=deprecated_in,
    )


_SENTINELS = ("flow", "release", "spec")


def _core_repo(tmp_path: Path, slugs: tuple[str, ...] = ("dev", *_SENTINELS)) -> Path:
    root = tmp_path / "repo"
    for slug in slugs:
        target = root / "departments" / "x" / "skills" / slug
        target.mkdir(parents=True)
        (target / "SKILL.md").write_text("core skill\n", encoding="utf-8")
    root.mkdir(parents=True, exist_ok=True)
    return root


def _skill(skills_dir: Path, name: str, text: str) -> Path:
    folder = skills_dir / name
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "SKILL.md"
    path.write_text(text, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Discovery — scope control
# ---------------------------------------------------------------------------


def test_core_shipped_skills_are_excluded(tmp_path: Path) -> None:
    core = _core_repo(tmp_path)
    skills = tmp_path / "skills"
    _skill(skills, "arka-dev", "core\n")
    _skill(skills, "arka-acme", "ecosystem\n")

    found = discover_user_owned_skills(skills, core)

    assert [p.parent.name for p in found] == ["arka-acme"]


def test_discovery_fails_closed_without_a_core_repo(tmp_path: Path) -> None:
    """No core repo means no way to tell core from user-owned — sync nothing."""
    skills = tmp_path / "skills"
    _skill(skills, "arka-dev", "core\n")
    _skill(skills, "arka-acme", "ecosystem\n")

    assert discover_user_owned_skills(skills, tmp_path / "missing") == []
    assert discover_user_owned_skills(skills, _core_repo(tmp_path, ())) == []


def test_discovery_fails_closed_on_a_partial_core_repo(tmp_path: Path) -> None:
    """The guard used to check only for ZERO slugs.

    A sparse, shallow or mid-checkout repo behind .repo-path carries a few
    SKILL.md files — enough to pass a truthiness check, and then every
    installed skill is classified user-owned and rewritten.
    """
    skills = tmp_path / "skills"
    for name in ("arka-dev", "arka-release", "arka-acme"):
        _skill(skills, name, "x\n")

    partial = _core_repo(tmp_path, ("dev",))

    assert discover_user_owned_skills(skills, partial) == []


# ---------------------------------------------------------------------------
# Syncing
# ---------------------------------------------------------------------------


def test_stale_block_is_rewritten_on_disk(tmp_path: Path) -> None:
    skills = tmp_path / "skills"
    path = _skill(
        skills,
        "arka-acme",
        "# arka-acme\n\n"
        "<!-- arka:feature:forge-integration:start version=4.0.0 hash=000000000000 -->\n"
        "## Forge Integration\n\nOLD\n"
        "<!-- arka:feature:forge-integration:end -->\n\n"
        "## Acme specifics\n\nInternal integration notes.\n",
    )

    result = sync_skill(path, [_feature()], VERSION)
    text = path.read_text(encoding="utf-8")

    assert result.status == "updated"
    assert result.features_updated == ["forge-integration"]
    assert "OLD" not in text
    assert "Complexity >= 5 routes to The Forge." in text
    assert "Internal integration notes." in text


def test_diverged_section_is_left_alone_and_proposed(tmp_path: Path) -> None:
    skills = tmp_path / "skills"
    original = (
        "# arka-globex\n\n"
        "## Forge Integration\n\nComplexity >= 5 routes to The Forge.\n- extra project rule\n"
    )
    path = _skill(skills, "arka-globex", original)

    result = sync_skill(path, [_feature()], VERSION)

    assert result.status == "pending"
    assert result.features_pending == ["forge-integration"]
    assert path.read_text(encoding="utf-8") == original
    proposal = Path(result.proposal_path or "")
    assert proposal.exists()
    body = proposal.read_text(encoding="utf-8")
    assert "extra project rule" in body
    assert "```diff" in body


def test_sync_is_idempotent_across_runs(tmp_path: Path) -> None:
    skills = tmp_path / "skills"
    path = _skill(skills, "arka-acme", "# arka-acme\n\n## Commands\n\ntable\n")

    first = sync_skill(path, [_feature()], VERSION)
    after_first = path.read_text(encoding="utf-8")
    second = sync_skill(path, [_feature()], VERSION)

    assert first.status == "updated"
    assert second.status == "unchanged"
    assert path.read_text(encoding="utf-8") == after_first


def test_restamp_reported_separately_from_real_change(tmp_path: Path) -> None:
    skills = tmp_path / "skills"
    path = _skill(skills, "arka-acme", "# arka-acme\n")
    sync_skill(path, [_feature()], "5.9.0")

    result = sync_skill(path, [_feature()], VERSION)

    assert result.status == "restamped"
    assert result.features_restamped == ["forge-integration"]
    assert result.features_updated == []
    assert f"version={VERSION}" in path.read_text(encoding="utf-8")


def test_sync_all_skills_covers_only_user_owned(tmp_path: Path) -> None:
    core = _core_repo(tmp_path)
    skills = tmp_path / "skills"
    _skill(skills, "arka-dev", "# core skill\n")
    _skill(skills, "arka-acme", "# arka-acme\n")

    results = sync_all_skills(skills, core, [_feature()], VERSION)

    assert [r.skill_name for r in results] == ["arka-acme"]
    assert "arka:feature" not in (skills / "arka-dev" / "SKILL.md").read_text()


def test_unreadable_skill_is_reported_not_raised(tmp_path: Path) -> None:
    skills = tmp_path / "skills"
    folder = skills / "arka-broken"
    folder.mkdir(parents=True)

    result = sync_skill(folder / "SKILL.md", [_feature()], VERSION)

    assert result.status == "error"
    assert result.error


# ---------------------------------------------------------------------------
# QG remediation — proposal lifecycle and malformed markers
# ---------------------------------------------------------------------------


def test_malformed_markers_leave_the_file_alone_and_are_reported(tmp_path: Path) -> None:
    skills = tmp_path / "skills"
    original = (
        "# arka-acme\n\n<!-- arka:feature:forge-integration:start -->\n\n"
        "## Deploy runbook\n\nIRREPLACEABLE\n"
    )
    path = _skill(skills, "arka-acme", original)

    result = sync_skill(path, [_feature()], VERSION)

    assert result.status == "malformed"
    assert result.features_malformed == ["forge-integration"]
    assert path.read_text(encoding="utf-8") == original
    body = Path(result.proposal_path or "").read_text(encoding="utf-8")
    assert "markers broken" in body
    assert "unbalanced" in body


def test_resolved_proposal_is_deleted_on_the_next_sync(tmp_path: Path) -> None:
    """A stale proposal is a permanent false to-do carrying a diff of project text."""
    skills = tmp_path / "skills"
    diverged = "# arka-acme\n\n" + BODY + "\n- extra project rule\n"
    path = _skill(skills, "arka-acme", diverged)

    first = sync_skill(path, [_feature()], VERSION)
    proposal = Path(first.proposal_path or "")
    assert proposal.exists()

    path.write_text("# arka-acme\n\n" + BODY + "\n", encoding="utf-8")
    second = sync_skill(path, [_feature()], VERSION)

    assert second.status == "updated"
    assert second.proposal_path is None
    assert not proposal.exists()


def test_proposal_never_claims_the_whole_file_was_untouched(tmp_path: Path) -> None:
    """One feature pending while another is injected still rewrites the file."""
    skills = tmp_path / "skills"
    other = FeatureSpec(
        name="quality-gate",
        added_in="5.0.0",
        mandatory=True,
        section_title="Quality Gate",
        detection_pattern="arka:feature:quality-gate",
        content=(
            "<!-- arka:feature:quality-gate:start -->\n"
            "## Quality Gate\n\nMarta vetoes.\n"
            "<!-- arka:feature:quality-gate:end -->\n"
        ),
        deprecated_in=None,
    )
    original = "# arka-acme\n\n" + BODY + "\n- extra project rule\n"
    path = _skill(skills, "arka-acme", original)

    result = sync_skill(path, [_feature(), other], VERSION)

    assert result.status == "updated"
    assert path.read_text(encoding="utf-8") != original
    body = Path(result.proposal_path or "").read_text(encoding="utf-8")
    assert "untouched" not in body
    assert "may have been updated in this run" in body


def test_retired_feature_never_tells_the_operator_to_align_it(tmp_path: Path) -> None:
    """Complying with the old wording deleted the operator's own section."""
    skills = tmp_path / "skills"
    path = _skill(
        skills, "arka-acme", "# arka-acme\n\n" + BODY + "\n- extra project rule\n"
    )

    result = sync_skill(path, [_feature(deprecated_in="5.10.0")], VERSION)

    body = Path(result.proposal_path or "").read_text(encoding="utf-8")
    assert "Do not align it with the canonical text" in body
    assert "retired by ArkaOS" in body


def test_proposal_diff_reads_installed_to_canonical(tmp_path: Path) -> None:
    skills = tmp_path / "skills"
    path = _skill(
        skills, "arka-acme", "# arka-acme\n\n" + BODY + "\n- extra project rule\n"
    )

    result = sync_skill(path, [_feature()], VERSION)

    body = Path(result.proposal_path or "").read_text(encoding="utf-8")
    assert "--- your installed section" in body
    assert "+++ arkaos canonical" in body
    assert "-- extra project rule" in body
