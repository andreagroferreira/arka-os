"""Tests for core.runtime.codex_cli headless completion (PR-6 v4.1.0).

Syntax verified 2026-07-04 against the installed binary (codex-cli
0.142.5, `codex exec --help`) plus a live JSONL probe. Canonical
headless form:

    codex exec --json --skip-git-repo-check --sandbox read-only "<prompt>"

Live-verified event shapes:
    {"type":"item.completed","item":{"type":"agent_message","text":"..."}}
    {"type":"turn.completed","usage":{"input_tokens":N,
        "cached_input_tokens":N,"output_tokens":N}}

These tests mock subprocess at the adapter boundary — they never shell
out to the real binary.
"""

from __future__ import annotations

import json
import subprocess
from unittest.mock import patch

import pytest

from core.runtime.codex_cli import CodexCliAdapter
from core.runtime.llm_provider import LLMUnavailable


def _jsonl(*events: dict) -> str:
    return "\n".join(json.dumps(e) for e in events)


def _fake_completed(
    returncode: int, stdout: str, stderr: str = ""
) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=["codex", "exec", "--json", "hi"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


class TestHeadlessComplete:
    """Behaviour of ``CodexCliAdapter.headless_complete``."""

    def test_raises_not_implemented_when_binary_missing(self):
        adapter = CodexCliAdapter()
        with patch("shutil.which", return_value=None):
            with pytest.raises(NotImplementedError, match="not found on PATH"):
                adapter.headless_complete("hello")

    def test_parses_jsonl_agent_message_and_usage(self):
        adapter = CodexCliAdapter()
        stdout = _jsonl(
            {"type": "thread.started", "thread_id": "t-1"},
            {"type": "turn.started"},
            {"type": "item.completed",
             "item": {"id": "item_1", "type": "agent_message",
                      "text": "pong"}},
            {"type": "turn.completed",
             "usage": {"input_tokens": 21431, "cached_input_tokens": 4992,
                       "output_tokens": 23,
                       "reasoning_output_tokens": 16}},
        )
        completed = _fake_completed(0, stdout)
        with patch("shutil.which", return_value="/usr/local/bin/codex"):
            with patch("subprocess.run", return_value=completed) as mock_run:
                response = adapter.headless_complete("ping")

        # Invocation invariants: list form, exec + --json, sandboxed,
        # stdin closed (with a prompt arg AND piped stdin, codex exec
        # appends stdin as a <stdin> block).
        args = mock_run.call_args.args[0]
        assert args[0].endswith("codex")
        assert args[1] == "exec"
        assert "--json" in args
        assert "--skip-git-repo-check" in args
        assert "--sandbox" in args and "read-only" in args
        assert mock_run.call_args.kwargs["stdin"] == subprocess.DEVNULL

        assert response.text == "pong"
        assert response.tokens_in == 21431
        assert response.tokens_out == 23
        assert response.cached_tokens == 4992
        assert response.model == ""

    def test_last_agent_message_wins(self):
        adapter = CodexCliAdapter()
        stdout = _jsonl(
            {"type": "item.completed",
             "item": {"type": "agent_message", "text": "draft"}},
            {"type": "item.completed",
             "item": {"type": "agent_message", "text": "final"}},
        )
        completed = _fake_completed(0, stdout)
        with patch("shutil.which", return_value="/usr/local/bin/codex"):
            with patch("subprocess.run", return_value=completed):
                response = adapter.headless_complete("hi")
        assert response.text == "final"

    def test_parses_legacy_msg_event_shape(self):
        adapter = CodexCliAdapter()
        stdout = _jsonl(
            {"id": "0", "msg": {"type": "agent_message",
                                "message": "legacy reply"}},
            {"id": "1", "msg": {"type": "token_count",
                                "info": {"total_token_usage": {
                                    "input_tokens": 10,
                                    "cached_input_tokens": 2,
                                    "output_tokens": 5}}}},
        )
        completed = _fake_completed(0, stdout)
        with patch("shutil.which", return_value="/usr/local/bin/codex"):
            with patch("subprocess.run", return_value=completed):
                response = adapter.headless_complete("hi")
        assert response.text == "legacy reply"
        assert response.tokens_in == 10
        assert response.tokens_out == 5
        assert response.cached_tokens == 2

    def test_error_item_alongside_message_does_not_fail(self):
        """Skills-budget warnings arrive as error items in a successful
        run (observed live) — only an error WITHOUT a message fails."""
        adapter = CodexCliAdapter()
        stdout = _jsonl(
            {"type": "item.completed",
             "item": {"type": "error", "message": "skills budget"}},
            {"type": "item.completed",
             "item": {"type": "agent_message", "text": "ok"}},
        )
        completed = _fake_completed(0, stdout)
        with patch("shutil.which", return_value="/usr/local/bin/codex"):
            with patch("subprocess.run", return_value=completed):
                response = adapter.headless_complete("hi")
        assert response.text == "ok"

    def test_error_only_stream_raises_unavailable(self):
        adapter = CodexCliAdapter()
        stdout = _jsonl({"type": "error", "message": "auth expired"})
        completed = _fake_completed(0, stdout)
        with patch("shutil.which", return_value="/usr/local/bin/codex"):
            with patch("subprocess.run", return_value=completed):
                with pytest.raises(LLMUnavailable, match="auth expired"):
                    adapter.headless_complete("hi")

    def test_raises_on_non_zero_exit(self):
        adapter = CodexCliAdapter()
        completed = _fake_completed(1, "", stderr="not logged in")
        with patch("shutil.which", return_value="/usr/local/bin/codex"):
            with patch("subprocess.run", return_value=completed):
                with pytest.raises(LLMUnavailable, match="exited 1"):
                    adapter.headless_complete("hi")

    def test_raises_on_timeout(self):
        adapter = CodexCliAdapter()

        def _timeout(*_args, **_kwargs):
            raise subprocess.TimeoutExpired(cmd=["codex"], timeout=120)

        with patch("shutil.which", return_value="/usr/local/bin/codex"):
            with patch("subprocess.run", side_effect=_timeout):
                with pytest.raises(LLMUnavailable, match="timed out"):
                    adapter.headless_complete("hi")

    def test_raises_on_oserror(self):
        adapter = CodexCliAdapter()
        with patch("shutil.which", return_value="/usr/local/bin/codex"):
            with patch("subprocess.run", side_effect=OSError("perm denied")):
                with pytest.raises(LLMUnavailable, match="subprocess failed"):
                    adapter.headless_complete("hi")

    def test_plain_text_fallback_estimates_tokens(self):
        adapter = CodexCliAdapter()
        completed = _fake_completed(0, "a" * 40)
        with patch("shutil.which", return_value="/usr/local/bin/codex"):
            with patch("subprocess.run", return_value=completed):
                response = adapter.headless_complete("hi")
        assert response.text == "a" * 40
        assert response.tokens_out == 10
        assert response.tokens_in == 0

    def test_empty_stdout_returns_empty_response(self):
        adapter = CodexCliAdapter()
        completed = _fake_completed(0, "")
        with patch("shutil.which", return_value="/usr/local/bin/codex"):
            with patch("subprocess.run", return_value=completed):
                response = adapter.headless_complete("hi")
        assert response.text == ""
        assert response.tokens_in == 0
        assert response.tokens_out == 0

    def test_system_prompt_prepended_to_user_prompt(self):
        adapter = CodexCliAdapter()
        completed = _fake_completed(0, _jsonl(
            {"type": "item.completed",
             "item": {"type": "agent_message", "text": "ok"}},
        ))
        with patch("shutil.which", return_value="/usr/local/bin/codex"):
            with patch("subprocess.run", return_value=completed) as mock_run:
                adapter.headless_complete(
                    "user question", system="You are a helper."
                )
        merged = mock_run.call_args.args[0][-1]
        assert "You are a helper." in merged
        assert "user question" in merged


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
