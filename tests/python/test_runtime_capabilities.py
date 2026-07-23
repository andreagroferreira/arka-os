"""Tests for the runtime capabilities matrix (PR-6 v4.1.0 — honesty).

``RuntimeAdapter.capabilities()`` is the single source of truth for the
multi-runtime story: Claude Code first-class, Gemini headless, Codex
headless (new), Cursor single-agent/experimental.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from core.runtime.base import (
    AgentContext,
    AgentResult,
    RuntimeAdapter,
    RuntimeConfig,
)
from core.runtime.capabilities_cli import build_matrix, main
from core.runtime.claude_code import ClaudeCodeAdapter
from core.runtime.codex_cli import CodexCliAdapter
from core.runtime.cursor import CursorAdapter
from core.runtime.gemini_cli import GeminiCliAdapter
from core.runtime.opencode import OpenCodeAdapter

_CAP_KEYS = {"agent_dispatch", "headless", "file_ops", "hooks"}
_ALL_ADAPTERS = (
    ClaudeCodeAdapter, CodexCliAdapter, GeminiCliAdapter, CursorAdapter,
    OpenCodeAdapter,
)


class TestAdapterCapabilities:
    @pytest.mark.parametrize("adapter_cls", _ALL_ADAPTERS)
    def test_capabilities_returns_all_keys_as_bools(self, adapter_cls):
        caps = adapter_cls().capabilities()
        assert set(caps) == _CAP_KEYS
        assert all(isinstance(v, bool) for v in caps.values())

    def test_claude_code_is_first_class(self):
        assert ClaudeCodeAdapter().capabilities() == {
            "agent_dispatch": True,
            "headless": True,
            "file_ops": True,
            "hooks": True,
        }

    def test_gemini_is_headless_without_dispatch_or_hooks(self):
        caps = GeminiCliAdapter().capabilities()
        assert caps["headless"] is True
        assert caps["agent_dispatch"] is False
        assert caps["hooks"] is False

    def test_codex_is_headless_after_pr6(self):
        caps = CodexCliAdapter().capabilities()
        assert caps["headless"] is True
        assert caps["agent_dispatch"] is False
        assert caps["hooks"] is False

    def test_cursor_is_single_agent_experimental(self):
        caps = CursorAdapter().capabilities()
        assert caps["headless"] is False
        assert caps["agent_dispatch"] is False
        assert caps["hooks"] is False

    def test_opencode_is_file_ops_only_until_headless_is_verified(self):
        # Foundation PR-6 honesty: `opencode run` exists upstream but is
        # NOT live-verified (codex precedent) — the matrix must not
        # overclaim until that verification lands.
        caps = OpenCodeAdapter().capabilities()
        assert caps["file_ops"] is True
        assert caps["headless"] is False
        assert caps["agent_dispatch"] is False
        assert caps["hooks"] is False

    def test_base_default_is_conservative(self):
        """Unknown adapters must not overclaim: everything False except
        hooks, which mirrors the runtime config."""

        class _MinimalAdapter(RuntimeAdapter):
            def get_config(self) -> RuntimeConfig:
                return RuntimeConfig(
                    id="minimal", name="Minimal",
                    config_dir=None, skills_dir=None, settings_file=None,
                    supports_hooks=False,
                )

            def inject_context(self, layers):
                return ""

            def dispatch_agent(self, context: AgentContext) -> AgentResult:
                return AgentResult(agent_id="x", status="ok", output="")

            def spawn_subagent(self, context: AgentContext) -> AgentResult:
                return AgentResult(agent_id="x", status="ok", output="")

            def read_file(self, path):
                return ""

            def write_file(self, path, content):
                pass

            def edit_file(self, path, old, new):
                pass

            def execute_command(self, command, timeout=120):
                return "", 0

            def search_files(self, pattern, path="."):
                return []

            def search_content(self, pattern, path="."):
                return []

        assert _MinimalAdapter().capabilities() == {
            "agent_dispatch": False,
            "headless": False,
            "file_ops": False,
            "hooks": False,
        }


class TestCapabilitiesCli:
    def test_build_matrix_covers_all_five_runtimes(self):
        matrix = build_matrix()
        assert set(matrix) == {
            "claude-code", "codex", "gemini", "cursor", "opencode",
        }
        for row in matrix.values():
            assert _CAP_KEYS <= set(row)
            assert "headless_available" in row
            assert isinstance(row["headless_available"], bool)

    def test_headless_available_reflects_binary_detection(self):
        with patch("shutil.which", return_value=None):
            matrix = build_matrix()
        assert matrix["codex"]["headless_available"] is False
        assert matrix["gemini"]["headless_available"] is False
        assert matrix["cursor"]["headless_available"] is False

    def test_cli_table_output(self, capsys):
        assert main([]) == 0
        out = capsys.readouterr().out
        assert "claude-code" in out
        assert "agent_dispatch" in out
        assert "cursor" in out

    def test_cli_json_output(self, capsys):
        assert main(["--json"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["claude-code"]["agent_dispatch"] is True
        assert payload["cursor"]["headless"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
