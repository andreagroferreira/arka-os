"""Tests for core.sync.policy_loader — MCP policy matching."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.sync.policy_loader import (
    PolicyDecision,
    load_policy,
    decide,
)


@pytest.fixture
def policy_file(tmp_path: Path) -> Path:
    p = tmp_path / "policy.yaml"
    p.write_text(
        "version: 1\n"
        "policies:\n"
        "  - match: {stack_includes: [laravel]}\n"
        "    active: [context7, postgres]\n"
        "    deferred: [canva, clickup]\n"
        "    ambiguous: []\n"
        "  - match: {ecosystem: marketing}\n"
        "    active: [canva, gmail]\n"
        "    deferred: [postgres]\n"
        "    ambiguous: []\n"
        "  - match: {default: true}\n"
        "    active: [context7]\n"
        "    deferred: []\n"
        "    ambiguous: ['*']\n"
    )
    return p


def test_load_policy_returns_rules_in_order(policy_file: Path) -> None:
    policy = load_policy(policy_file)
    assert len(policy.rules) == 3
    assert policy.rules[0].active == ["context7", "postgres"]


def test_decide_matches_laravel_stack(policy_file: Path) -> None:
    policy = load_policy(policy_file)
    decision = decide(
        policy, mcps=["context7", "postgres", "canva", "firecrawl"],
        stack=["laravel"], ecosystem=None,
    )
    assert decision.active == ["context7", "postgres"]
    assert decision.deferred == ["canva"]
    assert decision.ambiguous == ["firecrawl"]


def test_decide_marketing_ecosystem_overrides_stack(policy_file: Path) -> None:
    policy = load_policy(policy_file)
    decision = decide(
        policy, mcps=["canva", "gmail", "postgres"],
        stack=["unknown"], ecosystem="marketing",
    )
    assert "canva" in decision.active
    assert "postgres" in decision.deferred


def test_decide_falls_back_to_default_with_ambiguous_wildcard(policy_file: Path) -> None:
    policy = load_policy(policy_file)
    decision = decide(
        policy, mcps=["context7", "something-new"],
        stack=["rust"], ecosystem=None,
    )
    assert "context7" in decision.active
    assert "something-new" in decision.ambiguous


def test_decide_returns_empty_lists_for_empty_mcps(policy_file: Path) -> None:
    policy = load_policy(policy_file)
    decision = decide(policy, mcps=[], stack=["laravel"], ecosystem=None)
    assert decision.active == []
    assert decision.deferred == []
    assert decision.ambiguous == []


def test_first_rule_wins(policy_file: Path) -> None:
    policy = load_policy(policy_file)
    # laravel stack AND marketing ecosystem: first (laravel) wins
    decision = decide(
        policy, mcps=["canva"],
        stack=["laravel"], ecosystem="marketing",
    )
    # canva is deferred in laravel rule, active in marketing rule
    # laravel matched first → deferred
    assert decision.deferred == ["canva"]
    assert decision.active == []
