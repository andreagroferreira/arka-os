"""Tests for Synapse v2 context injection engine."""


from core.synapse.cache import LayerCache
from core.synapse.engine import SynapseEngine, create_default_engine
from core.synapse.layers import (
    BranchLayer,
    CommandHintsLayer,
    ConstitutionLayer,
    DepartmentLayer,
    Layer,
    LayerResult,
    ProjectLayer,
    PromptContext,
)

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

    def test_do_routes_to_orchestrator_empty_tag(self):
        """Both /do and /arka-do should route to orchestrator with empty tag."""
        layer = DepartmentLayer()

        result_do = layer.compute(PromptContext(user_input="/do build landing page"))
        assert result_do.content == ""
        assert result_do.tag == ""

        result_arka_do = layer.compute(PromptContext(user_input="/arka-do build landing page"))
        assert result_arka_do.content == ""
        assert result_arka_do.tag == ""

        # Even with dept keywords, /do and /arka-do route to orchestrator
        result_do_dev = layer.compute(PromptContext(user_input="/do dev feature auth"))
        assert result_do_dev.content == ""
        assert result_do_dev.tag == ""

        result_arka_do_dev = layer.compute(PromptContext(user_input="/arka-do dev feature auth"))
        assert result_arka_do_dev.content == ""
        assert result_arka_do_dev.tag == ""


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

    def test_arka_do_not_skipped_gets_hints(self):
        """/arka-do should NOT be skipped — it needs command hints for sub-commands."""
        commands = [
            {"command": "/dev feature", "keywords": ["feature", "build"]},
            {"command": "/landing funnel", "keywords": ["landing", "funnel"]},
        ]
        layer = CommandHintsLayer(commands=commands)
        result = layer.compute(PromptContext(user_input="/arka-do build landing"))
        assert result.tag != ""  # Should NOT be empty — /arka-do needs hints
        assert "[hint:" in result.tag

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


# --- Engine Tests ---


class TestSynapseEngine:
    def test_create_default_engine(self):
        engine = create_default_engine(constitution_compressed="test")
        # PR3.5 v3.74.1 added L2.6 AgentExperiencesLayer: 10 -> 11.
        # PR4 v3.75.0 added L7.5 PatternLibraryLayer: 11 -> 12.
        # PR-3 v4.1 added L2.7 GraphContextLayer: 12 -> 13.
        # Prompt-surface P0 2026-07-08 removed L7 TimeLayer: 13 -> 12.
        # Interaction Reform PR8 added L7.6 RecipeLayer: 12 -> 13.
        assert engine.layer_count == 15

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

    def test_inject_excludes_time_tag(self):
        # L7 TimeLayer removed (prompt-surface P0 2026-07-08): per-turn
        # cache-buster with no consumer rule.
        engine = create_default_engine()
        result = engine.inject(PromptContext())
        assert "[time:" not in result.context_string

    def test_repeat_injection_is_fully_served_from_cache(self):
        # PR5 v3.76.0 replaced a 100ms wall-clock budget with a cache-effect
        # check, because the budget reproduced the antipattern under full-suite
        # contention. The intent was right, but the replacement stayed timing-
        # dependent through a back door.
        #
        # The replaced `hit_rate >= 50` was a WALL-CLOCK TTL CLIFF, not a
        # rounding artifact (QG redo 3, measured): five of the cacheable
        # layers carry cache_ttl=30 and the 100-injection loop itself ran
        # ~28-30s. Finish under 30s and no entry expires -> 495 hits ->
        # hit_rate 50 -> pass. Take a ~2s contention spike and one entry
        # expires mid-loop -> 494 -> 49 -> fail. The test measured how fast
        # the machine was, and it sat one miss away from the threshold.
        #
        # A percentage over 1000 lookups is also the wrong quantity: layers
        # that produce no content are never cached (engine.py caches only a
        # non-empty tag), so they count a miss forever without ever being an
        # amortization failure. What matters is the steady state — once warm,
        # every cacheable layer is served from cache on the next injection.
        # Two injections, no timing dependency, no boundary.
        engine = create_default_engine(constitution_compressed="test")
        ctx = PromptContext(
            user_input="build a new feature for auth",
            git_branch="feature/auth",
            project_name="client_retail",
        )
        # Independent floor: how many layers SHOULD cache for this fixture.
        # Without it the two measured numbers co-move — suppressing the cache
        # write in 4 of 5 layers still yields gained == cached_entries == 1,
        # so an 80% cache collapse would pass (QG redo 3 mutation test).
        expected_entries = sum(
            1 for layer in engine._layers
            if layer.cache_ttl > 0 and layer.compute(ctx).tag
        )

        engine.clear_cache()
        engine.inject(ctx)  # warm-up: every cacheable layer computes fresh
        before = engine.cache_stats["hits"]
        engine.inject(ctx)  # steady state: must be served entirely from cache
        gained = engine.cache_stats["hits"] - before
        cached_entries = engine.cache_stats["size"]

        assert cached_entries == expected_entries, (
            f"cached {cached_entries} entries, expected {expected_entries} — "
            f"a layer that produces a tag stopped caching "
            f"(stats={engine.cache_stats})"
        )
        assert gained == cached_entries, (
            f"repeat injection reused {gained} of {cached_entries} cached "
            f"entries; every warm entry must hit (stats={engine.cache_stats})"
        )

    def test_caching_improves_performance(self):
        engine = create_default_engine(constitution_compressed="test")
        ctx = PromptContext(user_input="build feature")

        # First call (cold)
        engine.inject(ctx)
        # Second call (cached)
        r2 = engine.inject(ctx)

        assert r2.cache_stats["hits"] > 0

    def test_register_custom_layer(self):
        engine = SynapseEngine()
        assert engine.layer_count == 0

        engine.register_layer(BranchLayer())
        assert engine.layer_count == 1

    def test_remove_layer(self):
        engine = create_default_engine()
        initial = engine.layer_count
        engine.remove_layer("L4")  # Remove Branch layer
        assert engine.layer_count == initial - 1

    def test_cache_never_serves_one_prompts_result_to_another(self):
        # Regression (2026-07-09): the layer cache key ignored user_input,
        # so within the TTL window L5 served one prompt's hints to a
        # DIFFERENT prompt — including explicit slash commands whose
        # hints must be suppressed. Input-sensitive layers now hash the
        # prompt into the key.
        engine = create_default_engine(commands=[
            {"id": "dev-feature", "command": "/dev feature <desc>",
             "keywords": ["build", "feature"]},
        ])
        r1 = engine.inject(PromptContext(user_input="build a feature"))
        assert "[hint:" in r1.context_string
        r2 = engine.inject(PromptContext(user_input="/dev feature auth"))
        assert "[hint:" not in r2.context_string

    def test_session_sensitive_layer_not_cached_across_sessions(self):
        # Regression (2026-07-09 E2E audit): the cache key ignored
        # session_id, so a concurrent session's cache hit suppressed
        # L3.5's compute() — and with it KBSessionCache.store() — for
        # the second session. Session-sensitive layers now key on
        # ctx.extra["session_id"]; everything else still shares.
        class SessionProbe(Layer):
            computed = 0

            @property
            def id(self):
                return "LTEST"

            @property
            def name(self):
                return "SessionProbe"

            @property
            def cache_ttl(self):
                return 60

            @property
            def session_sensitive(self):
                return True

            def compute(self, ctx):
                SessionProbe.computed += 1
                return LayerResult(
                    layer_id=self.id, tag="[probe]", content="[probe]",
                    tokens_est=1, compute_ms=0, cached=False,
                )

        engine = SynapseEngine()
        engine.register_layer(SessionProbe())

        engine.inject(PromptContext(extra={"session_id": "sess-a"}))
        engine.inject(PromptContext(extra={"session_id": "sess-b"}))
        assert SessionProbe.computed == 2, (
            "session B was served session A's cached result"
        )
        engine.inject(PromptContext(extra={"session_id": "sess-a"}))
        assert SessionProbe.computed == 2, (
            "repeat injection for the same session must hit the cache"
        )

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
            constitution_compressed=(
                "NON-NEGOTIABLE: branch-isolation, squad-routing "
                "| MUST: conventional-commits"
            ),
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
        assert "[time:" not in result.context_string  # L7 removed (P0 2026-07-08)
        # PR4.5 v3.75.1 — replaced the original hard 100ms wall-clock budget
        # with a SEMANTIC cache-effect check. Any wall-clock budget tighter
        # than the host's CI variance is brittle (Marta's QG-T1 on the first
        # cleanup pass: 100ms warm budget reproduced the original flake at
        # a tighter threshold). The new contract is "the second injection
        # must benefit from the layer cache" — contention-immune.
        assert "[Constitution]" in result.context_string  # cold call already verified above
        warm = engine.inject(ctx)
        cache_hits = warm.cache_stats.get("hits", 0)
        assert cache_hits > 0, (
            f"expected cache to register hits on second inject; "
            f"got cache_stats={warm.cache_stats}"
        )


class TestContentChannel:
    """Full-text layer blocks must reach the caller, not just the tags.

    QG blocker (redo 4): engine.inject built context_string from TAGS only and
    LayerResult.content had no consumer anywhere — so every block a layer
    produced (Obsidian KB context, graph context) was discarded while its tag
    still advertised the injection to the model.
    """

    @staticmethod
    def _layer(ttl: int, tag: str, content: str, emits: bool = True):
        class _L(Layer):
            @property
            def id(self): return "LX"
            @property
            def name(self): return "Block"
            @property
            def input_sensitive(self): return False
            @property
            def cache_ttl(self): return ttl
            @property
            def emits_block(self): return emits
            @property
            def priority(self): return 5
            def compute(self, ctx): return LayerResult("LX", tag, content, 4, 0, False)
        return _L()

    def test_content_block_is_returned(self):
        engine = SynapseEngine()
        engine.register_layer(self._layer(0, "[kb-context:1]", "[arka:kb-context]\nbody"))
        result = engine.inject(PromptContext(user_input="q"))
        assert result.content_blocks == ["[arka:kb-context]\nbody"]
        assert result.context_string == "[kb-context:1]"  # tag line stays compact

    def test_content_survives_a_cache_hit(self):
        """A cached layer must replay its block, not its tag.

        The cache stored the tag alone, so a hit reconstructed content=tag —
        feeding the model a marker in place of the block it announces.
        """
        engine = SynapseEngine()
        engine.register_layer(self._layer(30, "[kb-context:1]", "[arka:kb-context]\nbody"))
        ctx = PromptContext(user_input="q")
        engine.inject(ctx)
        second = engine.inject(ctx)
        assert second.layers[0].cached is True
        assert second.content_blocks == ["[arka:kb-context]\nbody"]

    def test_tag_only_layer_contributes_no_block(self):
        engine = SynapseEngine()
        engine.register_layer(self._layer(0, "[dept:dev]", "[dept:dev]", emits=False))
        assert engine.inject(PromptContext(user_input="q")).content_blocks == []

    def test_tag_value_content_is_not_a_block(self):
        """The case that shipped: content is the tag's value, not a block.

        `[dept:dev]` carries content "dev", `[branch:x]` carries "x". Under the
        old `content != tag` rule every one of those became a free-floating
        unlabeled line in every prompt. Only a layer that OPTS IN emits.
        """
        engine = SynapseEngine()
        engine.register_layer(self._layer(0, "[dept:dev]", "dev", emits=False))
        assert engine.inject(PromptContext(user_input="q")).content_blocks == []
