"""Tests for core.runtime.gemini_cli headless completion.

Syntax verified 2026-04-20 against the Gemini CLI documentation
(Context7 /google-gemini/gemini-cli). Canonical headless form is:

    gemini -p "<prompt>" --output-format json

JSON payload contains ``response`` (text), ``stats`` (tokens), and
optionally ``error``. When parsing fails we fall back to treating
stdout as raw text and estimating tokens via ``len(text) // 4``.

These tests mock subprocess at the adapter boundary — they never
shell out to the real binary.
"""

from __future__ import annotations

import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from core.runtime.gemini_cli import GeminiCliAdapter
from core.runtime.llm_provider import LLMUnavailable


def _fake_completed(returncode: int, stdout: str, stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=["gemini", "-p", "hi", "--output-format", "json"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


class TestHeadlessComplete:
    """Behaviour of ``GeminiCliAdapter.headless_complete``."""

    def test_raises_not_implemented_when_binary_missing(self):
        adapter = GeminiCliAdapter()
        with patch("shutil.which", return_value=None):
            with pytest.raises(NotImplementedError, match="not found on PATH"):
                adapter.headless_complete("hello")

    def test_headless_supported_true_when_binary_present(self):
        adapter = GeminiCliAdapter()
        with patch("shutil.which", return_value="/opt/homebrew/bin/gemini"):
            assert adapter.headless_supported() is True

    def test_headless_supported_false_when_binary_missing(self):
        adapter = GeminiCliAdapter()
        with patch("shutil.which", return_value=None):
            assert adapter.headless_supported() is False

    def test_parses_json_response_with_stats(self):
        adapter = GeminiCliAdapter()
        payload = {
            "response": "Generated text here.",
            "stats": {
                "promptTokenCount": 42,
                "candidatesTokenCount": 17,
                "totalTokenCount": 59,
            },
            "model": "gemini-2.0-flash",
        }
        completed = _fake_completed(0, json.dumps(payload))
        with patch("shutil.which", return_value="/opt/homebrew/bin/gemini"):
            with patch("subprocess.run", return_value=completed) as mock_run:
                response = adapter.headless_complete("hi")

        # Subprocess invocation invariants: list form, -p + --output-format json.
        args = mock_run.call_args.args[0]
        assert args[0].endswith("gemini")
        assert "-p" in args
        assert "--output-format" in args and "json" in args
        assert response.text == "Generated text here."
        assert response.tokens_in == 42
        assert response.tokens_out == 17
        assert response.cached_tokens == 0
        assert response.model == "gemini-2.0-flash"

    def test_raises_on_non_zero_exit(self):
        adapter = GeminiCliAdapter()
        completed = _fake_completed(1, "", stderr="quota exhausted")
        with patch("shutil.which", return_value="/opt/homebrew/bin/gemini"):
            with patch("subprocess.run", return_value=completed):
                with pytest.raises(LLMUnavailable, match="exited 1"):
                    adapter.headless_complete("hi")

    def test_raises_on_timeout(self):
        adapter = GeminiCliAdapter()

        def _timeout(*_args, **_kwargs):
            raise subprocess.TimeoutExpired(cmd=["gemini"], timeout=60)

        with patch("shutil.which", return_value="/opt/homebrew/bin/gemini"):
            with patch("subprocess.run", side_effect=_timeout):
                with pytest.raises(LLMUnavailable, match="timed out"):
                    adapter.headless_complete("hi")

    def test_raises_on_oserror(self):
        adapter = GeminiCliAdapter()
        with patch("shutil.which", return_value="/opt/homebrew/bin/gemini"):
            with patch("subprocess.run", side_effect=OSError("perm denied")):
                with pytest.raises(LLMUnavailable, match="subprocess failed"):
                    adapter.headless_complete("hi")

    def test_error_key_in_payload_raises_unavailable(self):
        adapter = GeminiCliAdapter()
        payload = {"error": {"message": "safety block triggered"}}
        completed = _fake_completed(0, json.dumps(payload))
        with patch("shutil.which", return_value="/opt/homebrew/bin/gemini"):
            with patch("subprocess.run", return_value=completed):
                with pytest.raises(LLMUnavailable, match="gemini CLI returned error"):
                    adapter.headless_complete("hi")

    def test_plain_text_fallback_estimates_tokens(self):
        """When stdout is not JSON, treat as raw text and estimate tokens."""
        adapter = GeminiCliAdapter()
        # 40-char output → ~10 tokens via len // 4 heuristic.
        completed = _fake_completed(0, "a" * 40)
        with patch("shutil.which", return_value="/opt/homebrew/bin/gemini"):
            with patch("subprocess.run", return_value=completed):
                response = adapter.headless_complete("hi")
        assert response.text == "a" * 40
        assert response.tokens_out == 10
        assert response.tokens_in == 0

    def test_empty_stdout_returns_empty_response(self):
        adapter = GeminiCliAdapter()
        completed = _fake_completed(0, "")
        with patch("shutil.which", return_value="/opt/homebrew/bin/gemini"):
            with patch("subprocess.run", return_value=completed):
                response = adapter.headless_complete("hi")
        assert response.text == ""
        assert response.tokens_in == 0
        assert response.tokens_out == 0

    def test_system_prompt_prepended_to_user_prompt(self):
        adapter = GeminiCliAdapter()
        completed = _fake_completed(0, json.dumps({"response": "ok"}))
        with patch("shutil.which", return_value="/opt/homebrew/bin/gemini"):
            with patch("subprocess.run", return_value=completed) as mock_run:
                adapter.headless_complete("user question", system="You are a helper.")
        args = mock_run.call_args.args[0]
        idx = args.index("-p")
        merged = args[idx + 1]
        assert "You are a helper." in merged
        assert "user question" in merged

    def test_falls_back_to_total_token_count_when_per_side_absent(self):
        adapter = GeminiCliAdapter()
        payload = {"response": "hi", "stats": {"totalTokenCount": 99}}
        completed = _fake_completed(0, json.dumps(payload))
        with patch("shutil.which", return_value="/opt/homebrew/bin/gemini"):
            with patch("subprocess.run", return_value=completed):
                response = adapter.headless_complete("hi")
        assert response.tokens_in == 0
        assert response.tokens_out == 99


class TestImprovedCodexTodoMessage:
    """The Codex TODO error must mention the install command."""

    def test_message_includes_install_hint(self):
        from core.runtime.codex_cli import CodexCliAdapter

        adapter = CodexCliAdapter()
        # When codex is installed (patch `which`), the real method is
        # reached and must raise with the actionable TODO message.
        with patch("shutil.which", return_value="/usr/local/bin/codex"):
            with pytest.raises(NotImplementedError) as exc_info:
                adapter.headless_complete("hi")
        message = str(exc_info.value)
        assert "npm install -g @openai/codex-cli" in message
        assert "codex --help" in message
        assert "SubagentProvider" in message


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
