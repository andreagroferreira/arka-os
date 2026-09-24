"""core.decisions.registry — every site registered once, in a stable order."""

from __future__ import annotations

from typing import get_args

from core.decisions import replay as rp
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


def test_every_site_is_replayable_and_seeded():
    seed = (repo_root() / "installer" / "config-seed.js").read_text(encoding="utf-8")
    for name in SITES:
        assert name in rp.HEURISTICS and name in rp.EXPECTED, name
        assert rp.default_corpus_path(name).is_file(), name
        assert f'"sites", "{name}"' in seed, name
