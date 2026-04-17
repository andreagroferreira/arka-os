"""Regression tests for the v2 mcp-policy.yaml.

Context: v2.17.5 shipped with an incomplete policy that left MCPs like
arka-prompts, obsidian, laravel-boost, serena and memory-bank unclassified
for common stacks. They fell through to the AI decider which, given no AI
callable was wired in engine.py, returned "deferred" for everything.
Result: projects ended up with only the 4 fallback MCPs active instead of
the 6-10 expected per stack, and department commands (exposed via the
arka-prompts MCP) disappeared from every project.

These tests pin the policy contract so the regression cannot re-appear.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.sync.policy_loader import decide, load_policy


REPO_POLICY = Path(__file__).resolve().parents[2] / "config" / "mcp-policy.yaml"


_CORE_ACTIVE = {
    "arka-prompts",
    "obsidian",
    "context7",
    "memory-bank",
    "gh-grep",
}

_REGISTRY_MCPS = [
    "arka-prompts",
    "obsidian",
    "context7",
    "playwright",
    "memory-bank",
    "clickup",
    "firecrawl",
    "sentry",
    "gh-grep",
    "laravel-boost",
    "serena",
    "nuxt-ui",
    "nuxt",
    "supabase",
    "postgres",
    "next-devtools",
    "shopify-dev",
    "mirakl",
    "canva",
    "slack",
    "discord",
    "whatsapp",
    "teams",
]


@pytest.fixture
def policy():
    return load_policy(REPO_POLICY)


@pytest.mark.parametrize(
    "stack",
    [["laravel"], ["nuxt"], ["react"], ["next"], ["python"], ["vue"], ["shopify"]],
)
def test_no_ambiguous_for_common_stacks(policy, stack):
    """Every registry MCP must be classified as active or deferred for known stacks."""
    d = decide(policy, _REGISTRY_MCPS, stack, None)
    assert d.ambiguous == [], (
        f"stack={stack} has unclassified MCPs: {d.ambiguous}"
    )


@pytest.mark.parametrize(
    "stack",
    [["laravel"], ["nuxt"], ["react"], ["python"], ["vue"], ["shopify"]],
)
def test_core_mcps_always_active(policy, stack):
    """`arka-prompts`, `obsidian`, `context7`, `memory-bank`, and `gh-grep` must be active for any dev stack.

    These power the department command registry, vault access, docs, memory,
    and code search — losing any of them breaks the orchestrator.
    """
    d = decide(policy, list(_CORE_ACTIVE), stack, None)
    assert set(d.active) == _CORE_ACTIVE, (
        f"stack={stack} missing core MCPs: {_CORE_ACTIVE - set(d.active)}"
    )


def test_laravel_activates_laravel_boost_and_serena(policy):
    d = decide(policy, ["laravel-boost", "serena", "postgres"], ["laravel"], None)
    assert set(d.active) == {"laravel-boost", "serena", "postgres"}


def test_nuxt_activates_nuxt_and_playwright(policy):
    d = decide(policy, ["nuxt", "nuxt-ui", "playwright"], ["nuxt"], None)
    assert set(d.active) == {"nuxt", "nuxt-ui", "playwright"}


def test_default_rule_keeps_core_mcps_active(policy):
    """A project with no matching stack still gets the core MCPs."""
    d = decide(policy, list(_CORE_ACTIVE), [], None)
    assert set(d.active) == _CORE_ACTIVE


def test_comms_mcps_deferred_by_default_for_dev_stacks(policy):
    """Slack, Discord, WhatsApp, Teams should stay deferred on code stacks."""
    comms = ["slack", "discord", "whatsapp", "teams"]
    for stack in [["laravel"], ["nuxt"], ["react"], ["python"]]:
        d = decide(policy, comms, stack, None)
        assert set(d.deferred) == set(comms), (
            f"stack={stack} unexpectedly activated comms: active={d.active}"
        )


def test_marketing_ecosystem_activates_canva_and_firecrawl(policy):
    d = decide(policy, ["canva", "firecrawl", "clickup", "postgres"], [], "marketing")
    assert "canva" in d.active
    assert "firecrawl" in d.active
    assert "clickup" in d.active
    assert "postgres" in d.deferred
