"""MCP policy loader and matcher for the ArkaOS Sync Engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class PolicyRule:
    match: dict
    active: list[str] = field(default_factory=list)
    deferred: list[str] = field(default_factory=list)
    ambiguous: list[str] = field(default_factory=list)


@dataclass
class Policy:
    rules: list[PolicyRule]


@dataclass
class PolicyDecision:
    active: list[str]
    deferred: list[str]
    ambiguous: list[str]


def load_policy(path: Path) -> Policy:
    """Load and parse an mcp-policy.yaml file."""
    data = yaml.safe_load(path.read_text()) or {}
    rules = [
        PolicyRule(
            match=r.get("match", {}),
            active=list(r.get("active", [])),
            deferred=list(r.get("deferred", [])),
            ambiguous=list(r.get("ambiguous", [])),
        )
        for r in data.get("policies", [])
    ]
    return Policy(rules=rules)


def decide(
    policy: Policy,
    mcps: list[str],
    stack: list[str],
    ecosystem: str | None,
) -> PolicyDecision:
    """Apply the first matching rule and classify each MCP.

    MCPs explicitly listed in the matched rule go to active/deferred/ambiguous
    as declared. Any MCP not explicitly classified falls through to ambiguous
    (the AI fallback decides).
    """
    if not mcps:
        return PolicyDecision(active=[], deferred=[], ambiguous=[])

    rule = _first_match(policy, stack, ecosystem)
    if rule is None:
        return PolicyDecision(active=[], deferred=[], ambiguous=list(mcps))

    active: list[str] = []
    deferred: list[str] = []
    ambiguous: list[str] = []

    for mcp in mcps:
        if mcp in rule.active:
            active.append(mcp)
        elif mcp in rule.deferred:
            deferred.append(mcp)
        else:
            ambiguous.append(mcp)

    return PolicyDecision(active=active, deferred=deferred, ambiguous=ambiguous)


def _first_match(
    policy: Policy, stack: list[str], ecosystem: str | None
) -> PolicyRule | None:
    stack_set = {s.lower() for s in stack}
    for rule in policy.rules:
        match = rule.match
        if match.get("default"):
            return rule
        stack_inc = match.get("stack_includes")
        if stack_inc and any(s.lower() in stack_set for s in stack_inc):
            return rule
        eco = match.get("ecosystem")
        if eco and ecosystem and eco == ecosystem:
            return rule
    return None
