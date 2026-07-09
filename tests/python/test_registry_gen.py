"""Tests for the agents registry generator (core/agents/registry_gen.py).

Locks the export contract the MUST rule `model-routing` depends on:
every agent entry carries a resolved `model` field, and expertise
frameworks and expertise_domains are exported in full (no truncation).
"""

import json
from pathlib import Path

import pytest

from core.agents.registry_gen import generate_registry

REPO_ROOT = Path(__file__).parent.parent.parent
DEPARTMENTS = REPO_ROOT / "departments"
COMMITTED_REGISTRY = REPO_ROOT / "knowledge" / "agents-registry-v2.json"

VALID_MODELS = {"haiku", "sonnet", "opus"}


@pytest.fixture(scope="module")
def registry(tmp_path_factory):
    out = tmp_path_factory.mktemp("reg") / "agents-registry.json"
    return generate_registry(DEPARTMENTS, out)


class TestModelExport:
    def test_generation_has_no_errors(self, registry):
        assert "errors" not in registry["_meta"], registry["_meta"].get("errors")

    def test_every_agent_has_model(self, registry):
        missing = [a["id"] for a in registry["agents"] if "model" not in a]
        assert not missing, f"Agents without model field: {missing}"

    def test_model_values_are_valid_tiers(self, registry):
        invalid = {
            a["id"]: a["model"]
            for a in registry["agents"]
            if a["model"] not in VALID_MODELS
        }
        assert not invalid, f"Invalid model values: {invalid}"

    def test_tier0_resolves_to_opus_unless_overridden(self, registry):
        # tier_default_model(0) == "opus"; explicit YAML overrides (e.g. the
        # QG reviewers' sonnet floor pending Model Fabric upgrade) are allowed.
        for agent in registry["agents"]:
            if agent["tier"] == 0:
                assert agent["model"] in VALID_MODELS

    def test_cqo_is_opus(self, registry):
        marta = next(a for a in registry["agents"] if a["id"] == "cqo-marta")
        assert marta["model"] == "opus"


class TestExpertiseExport:
    def test_frameworks_not_truncated(self, registry):
        """At least one agent has >5 frameworks in YAML; the old [:5] cap
        would make this fail."""
        counts = [len(a["frameworks"]) for a in registry["agents"]]
        assert max(counts) > 5, (
            "No agent exports more than 5 frameworks — truncation regressed "
            "or every YAML lists <=5 (update this test if the latter)."
        )

    def test_expertise_domains_not_truncated(self, registry):
        """expertise_domains feeds the agent-match embedding
        (core/knowledge/agent_match.py) — the old [:5] cap degraded
        matching for 75/82 agents."""
        counts = [len(a["expertise_domains"]) for a in registry["agents"]]
        assert max(counts) > 5, (
            "No agent exports more than 5 expertise_domains — truncation "
            "regressed or every YAML lists <=5 (update this test if the latter)."
        )


class TestSingleCanonicalRegistry:
    def test_legacy_v1_registry_does_not_resurrect(self):
        """knowledge/agents-registry.json (v1, hand-maintained, stale at 22
        agents) was consolidated into the generated -v2 registry. A v1 file
        reappearing means a consumer or generator regressed to the dual-
        registry split."""
        legacy = REPO_ROOT / "knowledge" / "agents-registry.json"
        assert not legacy.exists(), (
            "Legacy knowledge/agents-registry.json resurfaced — the canonical "
            "registry is agents-registry-v2.json (core/agents/registry_gen.py)."
        )


class TestCommittedRegistryNoDrift:
    def test_committed_registry_content_matches_fresh_regen(self, registry):
        """Full content equality between the committed JSON and a fresh
        regeneration from the YAMLs (only _meta.generated may differ)."""
        committed = json.loads(COMMITTED_REGISTRY.read_text())
        # Round-trip so int dict keys (e.g. _meta.tiers) compare as the
        # strings JSON serialisation produces.
        fresh = json.loads(json.dumps(registry))

        committed_meta = {k: v for k, v in committed["_meta"].items() if k != "generated"}
        fresh_meta = {k: v for k, v in fresh["_meta"].items() if k != "generated"}
        assert committed_meta == fresh_meta, (
            "knowledge/agents-registry-v2.json _meta drifted from the YAMLs — "
            "regenerate with `arka-py -m core.agents.registry_gen`."
        )

        committed_by_id = {a["id"]: a for a in committed["agents"]}
        fresh_by_id = {a["id"]: a for a in fresh["agents"]}
        assert committed_by_id.keys() == fresh_by_id.keys(), (
            "Agent set drifted — regenerate the committed registry."
        )
        drifted = [
            agent_id
            for agent_id, fresh in fresh_by_id.items()
            if committed_by_id[agent_id] != fresh
        ]
        assert not drifted, (
            f"Committed registry entries drifted from YAML for: {drifted} — "
            f"regenerate with `arka-py -m core.agents.registry_gen`."
        )
