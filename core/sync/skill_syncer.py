"""Skill syncer for the ArkaOS Sync Engine — deterministic Phase 4.

Phase 4 used to be an AI subagent whose only instruction was "inject the
feature section if it is missing". That can never bring a skill forward:
once a section exists it is frozen, whatever the core doctrine says. This
module replaces it with the same managed-block contract the engine already
applies to ``.claude/CLAUDE.md`` — canonical content is rewritten on every
sync, project-authored content around it is untouched.

**Scope.** Only *user-owned* skills are synced: those installed under
``~/.claude/skills/arka-*`` whose slug has no ``SKILL.md`` anywhere in the
core repo. Core skills ship from npm and are already replaced wholesale by
``npx arkaos update``; rewriting them here would fight the installer.
Ecosystem skills exist only on the
operator's machine, which is exactly why they drift.

**Divergence is never overwritten.** A legacy section whose text differs
from the canonical body is left alone and written to a ``.arkaos-adopt.md``
proposal instead, for the operator to reconcile. Aligning by deletion would
destroy the customisation that made the section worth keeping.
"""

from __future__ import annotations

import difflib
from pathlib import Path

from core.sync.feature_merger import SkillMergeReport, merge_skill
from core.sync.schema import FeatureSpec, SkillSyncResult

_PROPOSAL_SUFFIX = ".arkaos-adopt.md"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def core_skill_slugs(core_root: Path) -> set[str]:
    """Return every skill slug that ships from the core repo."""
    return {
        path.parent.name
        for path in core_root.rglob("SKILL.md")
        if "node_modules" not in path.parts
    }


def discover_user_owned_skills(skills_dir: Path, core_root: Path) -> list[Path]:
    """Return SKILL.md paths for installed skills the core repo does not ship.

    Fail-closed: without a readable core repo there is no way to tell a core
    skill from a user-owned one, and treating every installed skill as
    user-owned would rewrite all 300+ of them. An unusable core root syncs
    nothing.
    """
    if not skills_dir.is_dir() or not core_root.is_dir():
        return []
    core_slugs = core_skill_slugs(core_root)
    if not core_slugs:
        return []
    return [
        path
        for path in sorted(skills_dir.glob("arka-*/SKILL.md"))
        if path.parent.name.removeprefix("arka-") not in core_slugs
    ]


def sync_skill(
    skill_file: Path, features: list[FeatureSpec], version: str
) -> SkillSyncResult:
    """Sync one skill file; never raises."""
    try:
        return _do_sync(skill_file, features, version)
    except Exception as exc:  # one bad skill must never stop the whole run
        return SkillSyncResult(
            skill_name=skill_file.parent.name, status="error", error=str(exc)
        )


def sync_all_skills(
    skills_dir: Path, core_root: Path, features: list[FeatureSpec], version: str
) -> list[SkillSyncResult]:
    """Sync every user-owned skill against the canonical feature registry."""
    return [
        sync_skill(skill_file, features, version)
        for skill_file in discover_user_owned_skills(skills_dir, core_root)
    ]


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _do_sync(
    skill_file: Path, features: list[FeatureSpec], version: str
) -> SkillSyncResult:
    skill_name = skill_file.parent.name
    original = skill_file.read_text(encoding="utf-8")
    report = merge_skill(original, skill_name, features, version)

    if report.new_text != original:
        skill_file.write_text(report.new_text, encoding="utf-8")

    pending = report.by_status("pending_adoption", "pending_removal")
    proposal = _write_proposal(skill_file, report) if pending else None

    return SkillSyncResult(
        skill_name=skill_name,
        status=_status_for(report, pending),
        features_added=report.by_status("injected"),
        features_removed=report.by_status("removed"),
        features_updated=report.by_status("updated"),
        features_restamped=report.by_status("restamped"),
        features_adopted=report.by_status("adopted"),
        features_pending=pending,
        proposal_path=str(proposal) if proposal else None,
    )


def _status_for(report: SkillMergeReport, pending: list[str]) -> str:
    """Rank the outcome: real change > pending review > restamp > no-op."""
    if report.by_status("injected", "updated", "adopted", "removed"):
        return "updated"
    if pending:
        return "pending"
    if report.by_status("restamped"):
        return "restamped"
    return "unchanged"


def _write_proposal(skill_file: Path, report: SkillMergeReport) -> Path:
    """Write a reviewable adoption proposal beside the skill file."""
    lines = [
        f"# Adoption proposal — {report.skill_name}",
        "",
        "These sections have diverged from the ArkaOS canonical text. The sync",
        "left the installed file untouched: reconcile them by hand, then delete",
        "this file. Once a section matches the canonical body it is adopted into",
        "a managed block automatically and stays aligned from then on.",
        "",
    ]
    for result in report.results:
        if result.status not in ("pending_adoption", "pending_removal"):
            continue
        lines += _proposal_section(result.feature, result.status, result)
    proposal = skill_file.with_name(skill_file.name + _PROPOSAL_SUFFIX)
    proposal.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return proposal


def _proposal_section(name: str, status: str, result) -> list[str]:
    verb = "deprecated upstream" if status == "pending_removal" else "diverged"
    diff = difflib.unified_diff(
        result.canonical_body.splitlines(),
        result.legacy_body.splitlines(),
        fromfile="arkaos-canonical",
        tofile="installed",
        lineterm="",
    )
    return [f"## {name} — {verb}", "", "```diff", *diff, "```", ""]
