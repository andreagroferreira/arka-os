"""Tests for the multi-runtime adapter system."""

import pytest
from core.runtime.base import RuntimeAdapter, RuntimeConfig, AgentContext, AgentResult
from core.runtime.registry import get_adapter, list_runtimes
from core.runtime.claude_code import ClaudeCodeAdapter
from core.runtime.codex_cli import CodexCliAdapter
from core.runtime.gemini_cli import GeminiCliAdapter
from core.runtime.cursor import CursorAdapter


class TestRuntimeRegistry:
    """Test runtime adapter registry."""

    def test_get_claude_code_adapter(self):
        adapter = get_adapter("claude-code")
        assert isinstance(adapter, ClaudeCodeAdapter)

    def test_get_codex_adapter(self):
        adapter = get_adapter("codex")
        assert isinstance(adapter, CodexCliAdapter)

    def test_get_gemini_adapter(self):
        adapter = get_adapter("gemini")
        assert isinstance(adapter, GeminiCliAdapter)

    def test_get_cursor_adapter(self):
        adapter = get_adapter("cursor")
        assert isinstance(adapter, CursorAdapter)

    def test_unknown_runtime_raises(self):
        with pytest.raises(ValueError, match="Unknown runtime"):
            get_adapter("unknown-runtime")

    def test_list_runtimes_returns_all_four(self):
        runtimes = list_runtimes()
        assert len(runtimes) == 4
        ids = {r["id"] for r in runtimes}
        assert ids == {"claude-code", "codex", "gemini", "cursor"}


class TestRuntimeConfig:
    """Test runtime configurations."""

    @pytest.mark.parametrize("runtime_id", ["claude-code", "codex", "gemini", "cursor"])
    def test_config_has_required_fields(self, runtime_id):
        adapter = get_adapter(runtime_id)
        config = adapter.get_config()
        assert isinstance(config, RuntimeConfig)
        assert config.id == runtime_id
        assert config.name
        assert config.config_dir
        assert config.skills_dir
        assert config.settings_file
        assert config.max_context_tokens > 0

    def test_claude_code_has_max_features(self):
        adapter = get_adapter("claude-code")
        config = adapter.get_config()
        assert config.supports_hooks is True
        assert config.supports_subagents is True
        assert config.supports_mcp is True
        assert config.max_context_tokens == 1_000_000

    def test_cursor_limited_features(self):
        adapter = get_adapter("cursor")
        config = adapter.get_config()
        assert config.supports_hooks is False
        assert config.supports_subagents is False


class TestContextInjection:
    """Test context injection across runtimes."""

    @pytest.mark.parametrize("runtime_id", ["claude-code", "codex", "gemini", "cursor"])
    def test_inject_context_returns_string(self, runtime_id):
        adapter = get_adapter(runtime_id)
        layers = {"dept": "dev", "agent": "cto", "project": "arkaos"}
        result = adapter.inject_context(layers)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_claude_code_uses_bracket_format(self):
        adapter = get_adapter("claude-code")
        layers = {"dept": "dev", "agent": "cto"}
        result = adapter.inject_context(layers)
        assert "[dept]" in result
        assert "[agent]" in result


class TestAgentDispatch:
    """Test agent dispatching."""

    @pytest.mark.parametrize("runtime_id", ["claude-code", "codex", "gemini", "cursor"])
    def test_dispatch_returns_result(self, runtime_id):
        adapter = get_adapter(runtime_id)
        context = AgentContext(
            agent_id="cto",
            task="Review architecture",
            department="dev",
            tier=0,
        )
        result = adapter.dispatch_agent(context)
        assert isinstance(result, AgentResult)
        assert result.agent_id == "cto"

    def test_cursor_subagent_unsupported(self):
        adapter = get_adapter("cursor")
        context = AgentContext(
            agent_id="cto",
            task="Review architecture",
            department="dev",
            tier=0,
        )
        result = adapter.spawn_subagent(context)
        assert result.status == "unsupported"
