"""core.decisions.registry — every site registered once, in a stable order."""

from __future__ import annotations

import re
from typing import get_args

import pytest

from core.decisions import replay as rp
from core.decisions.config import DecisionsConfig, site_mode
from core.decisions.paths import repo_root
from core.decisions.registry import SITES
from core.decisions.site import StateClass
from core.decisions.sites.command import COMMAND_SITES
from core.decisions.sites.dispatch import DISPATCH_SITES
from core.decisions.sites.forge import FORGE_SITES
from core.decisions.sites.governance import GOVERNANCE_SITES
from core.decisions.sites.prompt import PROMPT_SITES
from core.decisions.sites.quality import QUALITY_SITES

ORDER = (
    "topic-drift", "refine", "creation-intent", "route",
    "bash-effect",
    "forge-departments", "forge-complexity",
    "dispatch-role", "subagent-discipline", "skill-hints",
    "sycophancy", "phantom-action", "skill-proposer", "learning-signal", "ui-in-ts",
    "qg-prescreen", "slop-score",
)
GROUPS = (PROMPT_SITES, COMMAND_SITES, FORGE_SITES, DISPATCH_SITES, GOVERNANCE_SITES,
          QUALITY_SITES)


def test_seventeen_sites_in_a_stable_order():
    assert tuple(SITES) == ORDER and len(SITES) == 17


def test_names_are_unique_across_modules():
    names = [s.name for group in GROUPS for s in group]
    assert len(names) == len(set(names)) == len(SITES)
    assert all(SITES[s.name] is s for group in GROUPS for s in group)


def test_every_state_class_is_known():
    allowed = set(get_args(StateClass))
    assert {s.state_class for s in SITES.values()} <= allowed
    # Content is `diff` whichever hook carries it (ADR PR3 Decision 2).
    assert {n for n, s in SITES.items() if s.state_class == "diff"} == {
        "qg-prescreen", "slop-score", "ui-in-ts"}


# A seed row is ``[["decisions", "sites", ...], value]``; prose in comments
# may name the key, so only code lines count.
SITE_SEED_ROW = re.compile(r"""["']decisions["']\s*,\s*["']sites["']""")


def seed_code(text: str) -> str:
    """The seed with its ``//`` comment lines removed."""
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("//"))


def test_every_site_is_replayable_and_never_seeded():
    """Spec PR5 D3/D4: a corpus per site, and no seeded ``decisions.sites`` row.

    ``Site.default_mode`` is the only default: a seeded mode would be
    indistinguishable from an operator choice after the first seed.
    """
    seed = seed_code((repo_root() / "installer" / "config-seed.js").read_text(encoding="utf-8"))
    assert SITE_SEED_ROW.search(seed) is None
    for name in SITES:
        assert name in rp.HEURISTICS and name in rp.EXPECTED, name
        assert rp.default_corpus_path(name).is_file(), name


SITE_TABLE_HEADER = "| Site | Where | Default mode |"


def claude_md_site_modes(text: str) -> dict[str, str]:
    """``{site: default mode}`` from CLAUDE.md's ``## Typed Decisions (Jev)`` table.

    The mode is the first word of the third cell, before any parenthesis;
    a site listed twice or a row without three cells fails loudly.
    """
    section = text.split("## Typed Decisions (Jev)", 1)[1]
    lines = section.split(SITE_TABLE_HEADER, 1)[1].splitlines()[2:]  # skip |---|
    modes: dict[str, str] = {}
    for line in lines:
        if not line.startswith("|"):
            break
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        assert len(cells) == 3, f"table row without 3 cells: {line!r}"
        mode = re.match(r"[a-z]+", cells[2])
        assert mode is not None and cells[0] not in modes, line
        modes[cells[0]] = mode.group(0)
    return modes


def test_claude_md_site_table_matches_the_registry():
    """Spec PR5 D4: the documented default mode is ``Site.default_mode``, for
    exactly the registered sites (none missing, none extra)."""
    table = claude_md_site_modes((repo_root() / "CLAUDE.md").read_text(encoding="utf-8"))
    assert set(table) == set(SITES), (
        f"missing {sorted(set(SITES) - set(table))}, extra {sorted(set(table) - set(SITES))}")
    drift = {n: (table[n], s.default_mode) for n, s in SITES.items()
             if table[n] != s.default_mode}
    assert drift == {}, f"CLAUDE.md vs registry (doc, code): {drift}"


def test_seed_row_detector_catches_a_seeded_site():
    """The mutant that adds a site row back must fail the test above."""
    mutant = '// decisions.sites.* are not seeded\n  [["decisions", "sites", "route"], "act"],'
    assert SITE_SEED_ROW.search(seed_code(mutant)) is not None
    assert SITE_SEED_ROW.search(seed_code("// [\"decisions\", \"sites\", ...] prose")) is None


@pytest.mark.parametrize("name", ORDER)
def test_absent_config_entry_yields_the_site_default_mode(name, monkeypatch):
    monkeypatch.delenv("ARKA_BYPASS_DECISIONS", raising=False)
    other = next(n for n in ORDER if n != name)
    for cfg in (DecisionsConfig(), DecisionsConfig.model_validate({"sites": {other: "off"}})):
        assert site_mode(cfg, SITES[name]) == SITES[name].default_mode


def test_a_config_entry_is_an_operator_override(monkeypatch):
    monkeypatch.delenv("ARKA_BYPASS_DECISIONS", raising=False)
    cfg = DecisionsConfig.model_validate({"sites": {"refine": "act"}})
    assert SITES["refine"].default_mode == "shadow" and site_mode(cfg, SITES["refine"]) == "act"
