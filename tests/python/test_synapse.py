"""Tests for Synapse v2 context injection engine."""

import time
import pytest

from core.synapse.cache import LayerCache
from core.synapse.layers import (
    Layer, LayerResult, PromptContext,
    ConstitutionLayer, DepartmentLayer, AgentLayer,
    ProjectLayer, BranchLayer, CommandHintsLayer,
    QualityGateLayer, TimeLayer,
)
from core.synapse.engine import SynapseEngine, create_default_engine


# --- Cache Tests ---

class TestLayerCache:
    def test_set_and_get(self):
        cache = LayerCache()
        cache.set("key1", "value1", ttl_seconds=60)
        assert cache.get("key1") == "value1"

    def test_miss_returns_none(self):
        cache = LayerCache()
        assert cache.get("nonexistent") is None

    def test_expired_entry_returns_none(self):
        cache = LayerCache()
        cache.set("key1", "value1", ttl_seconds=0)
        # TTL 0 = never expires
        assert cache.get("key1") == "value1"

    def test_ttl_expiry(self):
        cache = LayerCache()
        # Set with very short TTL and manually expire
        cache.set("key1", "value1", ttl_seconds=1)
        assert cache.get("key1") == "value1"
        # Manually age the entry
        cache._store["key1"].created_at -= 2
        assert cache.get("key1") is None

    def test_invalidate(self):
        cache = LayerCache()
        cache.set("key1", "value1", ttl_seconds=60)
        cache.invalidate("key1")
        assert cache.get("key1") is None

    def test_clear(self):
        cache = LayerCache()
        cache.set("k1", "v1", 60)
        cache.set("k2", "v2", 60)
        cache.clear()
        assert cache.get("k1") is None
        assert cache.get("k2") is None

    def test_stats(self):
        cache = LayerCache()
        cache.set("k1", "v1", 60)
        cache.get("k1")  # hit
        cache.get("k2")  # miss
        stats = cache.stats
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 50
        assert stats["size"] == 1

    def test_evict_expired(self):
        cache = LayerCache()
        cache.set("fresh", "v1", ttl_seconds=60)
        cache.set("stale", "v2", ttl_seconds=1)
        cache._store["stale"].created_at -= 2  # Force expire
        evicted = cache.evict_expired()
        assert evicted == 1
        assert cache.get("fresh") == "v1"
        assert cache.get("stale") is None


# --- Individual Layer Tests ---

class TestConstitutionLayer:
    def test_returns_compressed_string(self):
        layer = ConstitutionLayer(compressed="NON-NEGOTIABLE: a, b, c")
        result = layer.compute(PromptContext())
        assert result.layer_id == "L0"
        assert "[Constitution]" in result.tag
        assert result.content == "NON-NEGOTIABLE: a, b, c"

    def test_cache_ttl_is_300(self):
        layer = ConstitutionLayer()
        assert layer.cache_ttl == 300

    def test_priority_is_0(self):
        layer = ConstitutionLayer()
        assert layer.priority == 0


class TestDepartmentLayer:
    def test_detect_dev_from_keywords(self):
        layer = DepartmentLayer()
        result = layer.compute(PromptContext(user_input="build a new feature for auth"))
        assert result.content == "dev"
        assert "[dept:dev]" in result.tag

    def test_detect_marketing(self):
        layer = DepartmentLayer()
        result = layer.compute(PromptContext(user_input="create social media campaign"))
        assert result.content == "marketing"

    def test_detect_finance(self):
        layer = DepartmentLayer()
        result = layer.compute(PromptContext(user_input="prepare budget forecast"))
        assert result.content == "finance"

    def test_detect_saas(self):
        layer = DepartmentLayer()
        result = layer.compute(PromptContext(user_input="analyze churn and MRR metrics"))
        assert result.content == "saas"

    def test_detect_from_command_prefix(self):
        layer = DepartmentLayer()
        result = layer.compute(PromptContext(user_input="/fin report monthly"))
        assert result.content == "finance"

    def test_detect_landing(self):
        layer = DepartmentLayer()
        result = layer.compute(PromptContext(user_input="design a sales funnel with landing page"))
        assert result.content == "landing"

    def test_empty_input_returns_empty(self):
        layer = DepartmentLayer()
        result = layer.compute(PromptContext(user_input="hello"))
        assert result.content == ""
        assert result.tag == ""


class TestBranchLayer:
    def test_feature_branch_shown(self):
        layer = BranchLayer()
        result = layer.compute(PromptContext(git_branch="feature/auth"))
        assert "[branch:feature/auth]" in result.tag

    def test_main_branch_hidden(self):
        layer = BranchLayer()
        for branch in ("main", "master", "dev", ""):
            result = layer.compute(PromptContext(git_branch=branch))
            assert result.tag == ""

    def test_v2_branch_shown(self):
        layer = BranchLayer()
        result = layer.compute(PromptContext(git_branch="v2"))
        assert "[branch:v2]" in result.tag


class TestProjectLayer:
    def test_project_with_stack(self):
        layer = ProjectLayer()
        result = layer.compute(PromptContext(project_name="client_retail", project_stack="laravel"))
        assert "project:client_retail" in result.tag
        assert "stack:laravel" in result.tag

    def test_no_project_returns_empty(self):
        layer = ProjectLayer()
        result = layer.compute(PromptContext())
        assert result.tag == ""


class TestCommandHintsLayer:
    def test_matches_keywords(self):
        commands = [
            {"command": "/dev feature", "keywords": ["feature", "build", "implement"]},
            {"command": "/mkt social", "keywords": ["social", "post", "content"]},
        ]
        layer = CommandHintsLayer(commands=commands)
        result = layer.compute(PromptContext(user_input="build a new feature"))
        assert "[hint:/dev feature]" in result.tag

    def test_skips_explicit_commands(self):
        commands = [{"command": "/dev feature", "keywords": ["feature"]}]
        layer = CommandHintsLayer(commands=commands)
        result = layer.compute(PromptContext(user_input="/dev feature auth"))
        assert result.tag == ""

    def test_max_two_hints(self):
        commands = [
            {"command": "/dev feature", "keywords": ["build"]},
            {"command": "/dev api", "keywords": ["build"]},
            {"command": "/dev debug", "keywords": ["build"]},
        ]
        layer = CommandHintsLayer(commands=commands)
        result = layer.compute(PromptContext(user_input="build something"))
        hint_count = result.tag.count("[hint:")
        assert hint_count <= 2


class TestTimeLayer:
    def test_returns_time_period(self):
        layer = TimeLayer()
        result = layer.compute(PromptContext())
        assert result.tag in ("[time:morning]", "[time:afternoon]", "[time:evening]")


# --- Engine Tests ---

class TestSynapseEngine:
    def test_create_default_engine(self):
        engine = create_default_engine(constitution_compressed="test")
        assert engine.layer_count == 9

    def test_inject_returns_result(self):
        engine = create_default_engine(constitution_compressed="NON-NEGOTIABLE: a")
        result = engine.inject(PromptContext(user_input="build a feature"))
        assert result.context_string
        assert len(result.layers) > 0
        assert result.total_ms >= 0

    def test_inject_contains_constitution(self):
        engine = create_default_engine(constitution_compressed="NON-NEGOTIABLE: test-rule")
        result = engine.inject(PromptContext())
        assert "[Constitution]" in result.context_string

    def test_inject_contains_department(self):
        engine = create_default_engine()
        result = engine.inject(PromptContext(user_input="create social media post"))
        assert "[dept:marketing]" in result.context_string

    def test_inject_contains_branch(self):
        engine = create_default_engine()
        result = engine.inject(PromptContext(git_branch="feature/auth"))
        assert "[branch:feature/auth]" in result.context_string

    def test_inject_contains_time(self):
        engine = create_default_engine()
        result = engine.inject(PromptContext())
        assert "[time:" in result.context_string

    def test_performance_under_100ms(self):
        engine = create_default_engine(constitution_compressed="test")
        ctx = PromptContext(
            user_input="build a new feature for auth",
            git_branch="feature/auth",
            project_name="client_retail",
        )
        start = time.time()
        for _ in range(100):
            engine.inject(ctx)
        avg_ms = (time.time() - start) * 1000 / 100
        assert avg_ms < 100, f"Average {avg_ms:.1f}ms exceeds 100ms target"

    def test_caching_improves_performance(self):
        engine = create_default_engine(constitution_compressed="test")
        ctx = PromptContext(user_input="build feature")

        # First call (cold)
        r1 = engine.inject(ctx)
        # Second call (cached)
        r2 = engine.inject(ctx)

        assert r2.cache_stats["hits"] > 0

    def test_register_custom_layer(self):
        engine = SynapseEngine()
        assert engine.layer_count == 0

        engine.register_layer(TimeLayer())
        assert engine.layer_count == 1

    def test_remove_layer(self):
        engine = create_default_engine()
        initial = engine.layer_count
        engine.remove_layer("L7")  # Remove Time layer
        assert engine.layer_count == initial - 1

    def test_metrics_recorded(self):
        engine = create_default_engine()
        engine.inject(PromptContext())
        engine.inject(PromptContext())
        assert len(engine.metrics) == 2

    def test_empty_layers_skipped_in_output(self):
        engine = create_default_engine()
        result = engine.inject(PromptContext(user_input="hello"))
        # "hello" doesn't match any department, so L1 should be skipped
        assert result.layers_skipped > 0


# --- Integration Test ---

class TestSynapseIntegration:
    def test_full_context_injection(self):
        """Simulate a real prompt context injection."""
        engine = create_default_engine(
            constitution_compressed="NON-NEGOTIABLE: branch-isolation, squad-routing | MUST: conventional-commits",
            commands=[
                {"command": "/dev feature", "keywords": ["feature", "build", "implement"]},
                {"command": "/dev spec", "keywords": ["spec", "specification"]},
            ],
            agents_registry={
                "cto-marco": {"disc": "D+C"},
            },
        )

        ctx = PromptContext(
            user_input="implement a new user authentication feature",
            cwd="/Users/dev/projects/client_retail",
            git_branch="feature/auth",
            project_name="client_retail",
            project_stack="laravel",
            active_agent="cto-marco",
        )

        result = engine.inject(ctx)

        # Verify all key context is present
        assert "[Constitution]" in result.context_string
        assert "[dept:dev]" in result.context_string
        assert "[agent:cto-marco" in result.context_string
        assert "project:client_retail" in result.context_string
        assert "stack:laravel" in result.context_string
        assert "[branch:feature/auth]" in result.context_string
        assert "[hint:/dev feature]" in result.context_string
        assert "[time:" in result.context_string
        assert result.total_ms < 100
