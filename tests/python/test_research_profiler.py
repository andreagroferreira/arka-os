"""Tests for ResearchProfiler — adaptive topic inference from project ecosystems."""

import json
import pytest
from pathlib import Path

from core.cognition.research import ResearchProfiler, ResearchProfile, ResearchTopic


# --- Fixtures ---

@pytest.fixture()
def ecosystems_file(tmp_path: Path) -> Path:
    """Write a minimal ecosystems.json and return its path."""
    data = {
        "ecosystems": {
            "fovory": {
                "name": "Fovory",
                "description": "Supplier-to-Shopify integration engine for e-commerce.",
                "type": "internal",
                "tech_stack": {
                    "frontend": ["Vue 3", "TypeScript"],
                    "backend": ["Laravel 13", "PHP 8.4"],
                    "shopify": ["Shopify GraphQL Admin API"],
                },
            },
            "edp": {
                "name": "EDP",
                "description": "Enterprise integration architecture platform for EDP energy utility.",
                "type": "client",
                "tech_stack": {
                    "frontend": ["Vue 3", "Inertia.js"],
                    "backend": ["Python 3.12", "FastAPI"],
                    "ai": ["pydantic-ai"],
                },
            },
        }
    }
    path = tmp_path / "ecosystems.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.fixture()
def profiler(ecosystems_file: Path) -> ResearchProfiler:
    return ResearchProfiler(ecosystems_path=str(ecosystems_file))


# --- Tests ---

class TestInferStacks:
    def test_infer_stacks(self, profiler: ResearchProfiler) -> None:
        """Extracts canonical stack names from tech_stack entries."""
        profile = profiler.build_profile()
        assert "laravel" in profile.stacks
        assert "vue" in profile.stacks
        assert "shopify-liquid" in profile.stacks
        assert "python" in profile.stacks

    def test_stacks_are_unique(self, profiler: ResearchProfiler) -> None:
        """Duplicate stacks across ecosystems appear only once."""
        profile = profiler.build_profile()
        assert len(profile.stacks) == len(set(profile.stacks))

    def test_stacks_are_sorted(self, profiler: ResearchProfiler) -> None:
        """Returned stacks list is alphabetically sorted."""
        profile = profiler.build_profile()
        assert profile.stacks == sorted(profile.stacks)


class TestInferDomains:
    def test_infer_domains(self, profiler: ResearchProfiler) -> None:
        """Extracts at least one domain from the ecosystems."""
        profile = profiler.build_profile()
        assert len(profile.domains) >= 1

    def test_ecommerce_domain_detected(self, profiler: ResearchProfiler) -> None:
        """Fovory description triggers ecommerce domain."""
        profile = profiler.build_profile()
        assert "ecommerce" in profile.domains

    def test_enterprise_domain_detected(self, profiler: ResearchProfiler) -> None:
        """EDP description triggers enterprise domain."""
        profile = profiler.build_profile()
        assert "enterprise" in profile.domains

    def test_domains_are_unique(self, profiler: ResearchProfiler) -> None:
        """Each domain appears only once."""
        profile = profiler.build_profile()
        assert len(profile.domains) == len(set(profile.domains))


class TestGeneratesTopics:
    def test_generates_topics(self, profiler: ResearchProfiler) -> None:
        """Topics are generated when stacks are present."""
        profile = profiler.build_profile()
        assert len(profile.topics) > 0

    def test_topics_have_search_queries(self, profiler: ResearchProfiler) -> None:
        """Every topic contains at least one search query."""
        profile = profiler.build_profile()
        for topic in profile.topics:
            assert len(topic.search_queries) >= 1, f"{topic.name} has no queries"

    def test_laravel_topic_generated(self, profiler: ResearchProfiler) -> None:
        """Laravel stack produces a matching research topic."""
        profile = profiler.build_profile()
        names = [t.name for t in profile.topics]
        assert any("laravel" in n.lower() for n in names)

    def test_topics_source_is_valid(self, profiler: ResearchProfiler) -> None:
        """All topic sources are valid literals."""
        valid_sources = {"stack", "domain", "tool", "business"}
        profile = profiler.build_profile()
        for topic in profile.topics:
            assert topic.source in valid_sources, f"Invalid source: {topic.source}"


class TestEmptyEcosystems:
    def test_empty_ecosystems_file(self, tmp_path: Path) -> None:
        """Handles an ecosystems file with no ecosystems gracefully."""
        path = tmp_path / "empty.json"
        path.write_text(json.dumps({"ecosystems": {}}), encoding="utf-8")
        profiler = ResearchProfiler(ecosystems_path=str(path))
        profile = profiler.build_profile()
        assert profile.stacks == []
        assert profile.domains == []
        assert profile.topics == []

    def test_missing_file(self, tmp_path: Path) -> None:
        """Handles a missing file without raising."""
        profiler = ResearchProfiler(ecosystems_path=str(tmp_path / "nonexistent.json"))
        profile = profiler.build_profile()
        assert isinstance(profile, ResearchProfile)
        assert profile.stacks == []

    def test_empty_tech_stack(self, tmp_path: Path) -> None:
        """Handles ecosystem with no tech_stack key."""
        data = {"ecosystems": {"minimal": {"name": "Minimal", "description": "Just a test."}}}
        path = tmp_path / "minimal.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        profiler = ResearchProfiler(ecosystems_path=str(path))
        profile = profiler.build_profile()
        assert isinstance(profile, ResearchProfile)


class TestProfileToYaml:
    def test_profile_to_yaml(self, profiler: ResearchProfiler) -> None:
        """YAML output contains all expected top-level keys."""
        profile = profiler.build_profile()
        output = profile.to_yaml()
        assert "stacks:" in output
        assert "domains:" in output
        assert "topics:" in output
        assert "tools:" in output
        assert "business_interests:" in output
        assert "competitors:" in output

    def test_yaml_is_parseable(self, profiler: ResearchProfiler) -> None:
        """YAML output can be parsed back to a dict."""
        import yaml
        profile = profiler.build_profile()
        parsed = yaml.safe_load(profile.to_yaml())
        assert isinstance(parsed, dict)
        assert "stacks" in parsed
        assert isinstance(parsed["stacks"], list)

    def test_yaml_contains_stack_values(self, profiler: ResearchProfiler) -> None:
        """YAML stacks list reflects the inferred stacks."""
        import yaml
        profile = profiler.build_profile()
        parsed = yaml.safe_load(profile.to_yaml())
        assert "laravel" in parsed["stacks"]
