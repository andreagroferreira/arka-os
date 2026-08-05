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


def _core_repo(tmp_path: Path, slugs: tuple[str, ...] = ("dev", "release")) -> Path:
    root = tmp_path / "repo"
    for slug in slugs:
        target = root / "departments" / "x" / "skills" / slug
        target.mkdir(parents=True)
        (target / "SKILL.md").write_text("core skill\n", encoding="utf-8")
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
