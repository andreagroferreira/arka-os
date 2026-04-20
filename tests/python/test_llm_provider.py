"""Tests for the LLM provider abstraction."""

from __future__ import annotations

import json
import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from core.runtime.base import AgentContext, RuntimeAdapter, RuntimeConfig  # noqa: F401
from core.runtime.claude_code import ClaudeCodeAdapter, _parse_claude_json
from core.runtime.codex_cli import CodexCliAdapter
from core.runtime.cursor import CursorAdapter
from core.runtime.gemini_cli import GeminiCliAdapter
from core.runtime.llm_cost_telemetry import read_entries
from core.runtime.llm_provider import (
    AnthropicDirectProvider,
    LLMProvider,
    LLMResponse,
    LLMUnavailable,
    StubProvider,
    SubagentProvider,
    get_llm_provider,
)


# ─── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture()
def tmp_cost_file(tmp_path, monkeypatch):
    path = tmp_path / "llm-cost.jsonl"
    monkeypatch.setenv("ARKA_LLM_COST_PATH", str(path))
    yield path


@pytest.fixture()
def tmp_config(tmp_path):
    path = tmp_path / "config.json"
    return path


def _write_config(path: Path, provider: str | None) -> None:
    data: dict = {}
    if provider is not None:
        data["llm"] = {"provider": provider}
    path.write_text(json.dumps(data), encoding="utf-8")


class _FakeAdapter(RuntimeAdapter):
    """Minimal adapter with controllable headless behaviour."""

    def __init__(self, *, supports: bool = True, response: LLMResponse | None = None,
                 raise_exc: Exception | None = None):
        self._supports = supports
        self._response = response or LLMResponse(
            text="hello", tokens_in=10, tokens_out=20, cached_tokens=0,
            model="test-model",
        )
        self._raise = raise_exc
        self.calls: list[tuple[str, int, str]] = []

    def get_config(self) -> RuntimeConfig:
        return RuntimeConfig(
            id="fake", name="Fake", config_dir=Path("/tmp"),
            skills_dir=Path("/tmp"), settings_file=Path("/tmp/s.json"),
        )

    def inject_context(self, layers): return ""
    def dispatch_agent(self, context): raise NotImplementedError
    def spawn_subagent(self, context): raise NotImplementedError
    def read_file(self, path): raise NotImplementedError
    def write_file(self, path, content): raise NotImplementedError
    def edit_file(self, path, old, new): raise NotImplementedError
    def execute_command(self, command, timeout=120): raise NotImplementedError
    def search_files(self, pattern, path="."): raise NotImplementedError
    def search_content(self, pattern, path="."): raise NotImplementedError

    def headless_supported(self) -> bool:
        return self._supports

    def headless_complete(self, prompt, *, max_tokens=2000, system=""):
        self.calls.append((prompt, max_tokens, system))
        if self._raise is not None:
            raise self._raise
        return self._response


# ─── LLMResponse dataclass ────────────────────────────────────────────


class TestLLMResponse:
    def test_llm_response_is_frozen(self):
        resp = LLMResponse(text="x", tokens_in=0, tokens_out=0, cached_tokens=0, model="m")
        with pytest.raises(Exception):
            resp.text = "changed"  # type: ignore[misc]

    def test_llm_response_equality(self):
        a = LLMResponse("a", 1, 2, 0, "m")
        b = LLMResponse("a", 1, 2, 0, "m")
        assert a == b


# ─── Factory + fallback chain ─────────────────────────────────────────


class TestFactory:
    def test_default_is_subagent_when_config_missing(self, tmp_config, tmp_cost_file):
        # Force SubagentProvider to be unavailable so we don't hit the
        # real runtime; verify the returned provider honours the chain.
        with patch.object(SubagentProvider, "is_available", return_value=True):
            provider = get_llm_provider(config_path=tmp_config)
        assert isinstance(provider, SubagentProvider)

    def test_reads_config(self, tmp_config, tmp_cost_file):
        _write_config(tmp_config, "stub")
        provider = get_llm_provider(config_path=tmp_config)
        assert isinstance(provider, StubProvider)

    def test_invalid_provider_in_config_falls_back(self, tmp_config, tmp_cost_file):
        _write_config(tmp_config, "nonsense")
        # Force SubagentProvider unavailable; we expect stub (end of chain).
        with patch.object(SubagentProvider, "is_available", return_value=False), \
             patch.object(AnthropicDirectProvider, "is_available", return_value=False):
            provider = get_llm_provider(config_path=tmp_config)
        assert isinstance(provider, StubProvider)

    def test_fallback_chain_skips_unavailable(self, tmp_config, tmp_cost_file):
        _write_config(tmp_config, "subagent")
        with patch.object(SubagentProvider, "is_available", return_value=False), \
             patch.object(AnthropicDirectProvider, "is_available", return_value=False):
            provider = get_llm_provider(config_path=tmp_config)
        assert isinstance(provider, StubProvider)

    def test_fallback_chain_logs_telemetry(self, tmp_config, tmp_cost_file):
        _write_config(tmp_config, "subagent")
        with patch.object(SubagentProvider, "is_available", return_value=False), \
             patch.object(AnthropicDirectProvider, "is_available", return_value=False):
            get_llm_provider(config_path=tmp_config)
        entries = read_entries(tmp_cost_file)
        # Each skipped provider + the final selection should emit a row.
        assert any(e["provider"].startswith("fallback:") for e in entries)

    def test_anthropic_direct_selected_when_configured(self, tmp_config, tmp_cost_file):
        _write_config(tmp_config, "anthropic-direct")
        with patch.object(AnthropicDirectProvider, "is_available", return_value=True):
            provider = get_llm_provider(config_path=tmp_config)
        assert isinstance(provider, AnthropicDirectProvider)

    def test_returns_provider_protocol(self, tmp_config, tmp_cost_file):
        _write_config(tmp_config, "stub")
        provider = get_llm_provider(config_path=tmp_config)
        assert isinstance(provider, LLMProvider)


# ─── SubagentProvider ─────────────────────────────────────────────────


class TestSubagentProvider:
    def test_uses_active_runtime(self, tmp_cost_file):
        adapter = _FakeAdapter()
        provider = SubagentProvider(adapter=adapter)
        result = provider.complete("hi", max_tokens=100, system="sys")
        assert result.text == "hello"
        assert adapter.calls == [("hi", 100, "sys")]

    def test_is_available_when_adapter_supports(self):
        adapter = _FakeAdapter(supports=True)
        assert SubagentProvider(adapter=adapter).is_available() is True

    def test_is_available_false_when_adapter_refuses(self):
        adapter = _FakeAdapter(supports=False)
        assert SubagentProvider(adapter=adapter).is_available() is False

    def test_raises_on_unsupported_runtime(self, tmp_cost_file):
        adapter = _FakeAdapter(raise_exc=NotImplementedError("Cursor unsupported"))
        provider = SubagentProvider(adapter=adapter)
        with pytest.raises(LLMUnavailable, match="Cursor unsupported"):
            provider.complete("hi")

    def test_timeout_raises_llm_unavailable(self, tmp_cost_file):
        import subprocess
        adapter = _FakeAdapter(raise_exc=subprocess.TimeoutExpired(cmd="claude", timeout=60))
        provider = SubagentProvider(adapter=adapter)
        with pytest.raises(LLMUnavailable):
            provider.complete("hi")

    def test_records_cost_on_success(self, tmp_cost_file):
        adapter = _FakeAdapter(response=LLMResponse(
            text="ok", tokens_in=5, tokens_out=10, cached_tokens=0,
            model="claude-opus-4-7",
        ))
        provider = SubagentProvider(adapter=adapter)
        provider.complete("hi")
        entries = read_entries(tmp_cost_file)
        assert any(e["provider"] == "subagent" for e in entries)

    def test_name(self):
        assert SubagentProvider().name() == "subagent"


# ─── AnthropicDirectProvider ──────────────────────────────────────────


class TestAnthropicDirectProvider:
    def test_requires_env_var(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
        assert AnthropicDirectProvider().is_available() is False

    def test_is_available_false_without_api_key(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_MODEL", "claude-opus-4-7")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        # Client not injected → checks real env; real SDK unlikely to be
        # present in test env, but either way no API key means False.
        assert AnthropicDirectProvider().is_available() is False

    def test_is_available_true_with_injected_client(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_MODEL", "claude-opus-4-7")
        fake_client = MagicMock()
        assert AnthropicDirectProvider(client=fake_client).is_available() is True

    def test_complete_raises_when_model_unset(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
        fake_client = MagicMock()
        provider = AnthropicDirectProvider(client=fake_client)
        with pytest.raises(LLMUnavailable, match="ANTHROPIC_MODEL"):
            provider.complete("hi")

    def test_enables_prompt_caching_on_system(self, monkeypatch, tmp_cost_file):
        monkeypatch.setenv("ANTHROPIC_MODEL", "claude-opus-4-7")
        fake_raw = SimpleNamespace(
            content=[SimpleNamespace(type="text", text="answer")],
            usage=SimpleNamespace(
                input_tokens=10, output_tokens=5,
                cache_read_input_tokens=0, cache_creation_input_tokens=0,
            ),
            model="claude-opus-4-7",
        )
        fake_client = MagicMock()
        fake_client.messages.create.return_value = fake_raw
        provider = AnthropicDirectProvider(client=fake_client)
        provider.complete("hi", system="sys prompt")
        payload = fake_client.messages.create.call_args.kwargs
        assert payload["system"][0]["cache_control"] == {"type": "ephemeral"}
        assert payload["system"][0]["text"] == "sys prompt"

    def test_omits_system_when_empty(self, monkeypatch, tmp_cost_file):
        monkeypatch.setenv("ANTHROPIC_MODEL", "claude-opus-4-7")
        fake_raw = SimpleNamespace(
            content=[SimpleNamespace(type="text", text="x")],
            usage=SimpleNamespace(
                input_tokens=1, output_tokens=1,
                cache_read_input_tokens=0, cache_creation_input_tokens=0,
            ),
            model="claude-opus-4-7",
        )
        fake_client = MagicMock()
        fake_client.messages.create.return_value = fake_raw
        AnthropicDirectProvider(client=fake_client).complete("hi")
        payload = fake_client.messages.create.call_args.kwargs
        assert "system" not in payload

    def test_extracts_usage_from_response(self, monkeypatch, tmp_cost_file):
        monkeypatch.setenv("ANTHROPIC_MODEL", "claude-opus-4-7")
        fake_raw = SimpleNamespace(
            content=[SimpleNamespace(type="text", text="ok")],
            usage=SimpleNamespace(
                input_tokens=100, output_tokens=50,
                cache_read_input_tokens=20, cache_creation_input_tokens=30,
            ),
            model="claude-opus-4-7",
        )
        fake_client = MagicMock()
        fake_client.messages.create.return_value = fake_raw
        provider = AnthropicDirectProvider(client=fake_client)
        resp = provider.complete("hi")
        assert resp.tokens_in == 150  # 100 + 20 + 30
        assert resp.tokens_out == 50
        assert resp.cached_tokens == 20
        assert resp.model == "claude-opus-4-7"

    def test_records_cost(self, monkeypatch, tmp_cost_file):
        monkeypatch.setenv("ANTHROPIC_MODEL", "claude-opus-4-7")
        fake_raw = SimpleNamespace(
            content=[SimpleNamespace(type="text", text="ok")],
            usage=SimpleNamespace(
                input_tokens=10, output_tokens=5,
                cache_read_input_tokens=0, cache_creation_input_tokens=0,
            ),
            model="claude-opus-4-7",
        )
        fake_client = MagicMock()
        fake_client.messages.create.return_value = fake_raw
        AnthropicDirectProvider(client=fake_client).complete("hi")
        entries = read_entries(tmp_cost_file)
        assert any(e["provider"] == "anthropic-direct" for e in entries)

    def test_sdk_failure_wraps_as_llm_unavailable(self, monkeypatch, tmp_cost_file):
        monkeypatch.setenv("ANTHROPIC_MODEL", "claude-opus-4-7")
        fake_client = MagicMock()
        fake_client.messages.create.side_effect = RuntimeError("500")
        provider = AnthropicDirectProvider(client=fake_client)
        with pytest.raises(LLMUnavailable, match="RuntimeError"):
            provider.complete("hi")

    def test_name(self):
        assert AnthropicDirectProvider().name() == "anthropic-direct"


# ─── StubProvider ─────────────────────────────────────────────────────


class TestStubProvider:
    def test_returns_empty_response(self):
        resp = StubProvider().complete("anything", max_tokens=100, system="sys")
        assert resp.text == ""
        assert resp.tokens_in == 0
        assert resp.tokens_out == 0
        assert resp.cached_tokens == 0
        assert resp.model == ""

    def test_is_available_always(self):
        assert StubProvider().is_available() is True

    def test_never_raises(self):
        # StubProvider must tolerate any input shape.
        StubProvider().complete("")
        StubProvider().complete("x" * 100_000, max_tokens=1, system="y" * 10_000)

    def test_name(self):
        assert StubProvider().name() == "stub"


# ─── No hardcoded model branches in source ────────────────────────────


def _strip_docstrings_and_comments(source: str) -> str:
    # Remove triple-double-quoted docstrings.
    cleaned = re.sub(r'""".*?"""', "", source, flags=re.DOTALL)
    # Remove triple-single-quoted strings just in case.
    cleaned = re.sub(r"'''.*?'''", "", cleaned, flags=re.DOTALL)
    # Strip comments line by line (naive, fine for our own source).
    cleaned = re.sub(r"#.*", "", cleaned)
    return cleaned


class TestNoModelHardcoding:
    """Guard rail: the provider module must not branch on model names."""

    def test_no_conditional_on_opus_sonnet_haiku(self):
        source = Path(
            "core/runtime/llm_provider.py"
        ).read_text(encoding="utf-8")
        stripped = _strip_docstrings_and_comments(source)
        # Forbid `if ...opus...`, `elif ...sonnet...`, `== "haiku"`, etc.
        forbidden = re.compile(
            r"(?:if|elif)\s+[^\n]*(opus|sonnet|haiku)",
            re.IGNORECASE,
        )
        assert forbidden.search(stripped) is None, (
            "llm_provider.py must not contain conditional branches "
            "keyed on model names — the runtime decides the model."
        )

    def test_no_model_equality_check(self):
        source = Path(
            "core/runtime/llm_provider.py"
        ).read_text(encoding="utf-8")
        stripped = _strip_docstrings_and_comments(source)
        assert re.search(r'==\s*"(opus|sonnet|haiku)"', stripped) is None

    def test_pricing_module_is_only_place_models_appear(self):
        # Provider file must not inline model names anywhere except as
        # comments/docstrings.
        source = Path(
            "core/runtime/llm_provider.py"
        ).read_text(encoding="utf-8")
        stripped = _strip_docstrings_and_comments(source)
        for hardcoded in ("claude-opus", "claude-sonnet", "claude-haiku", "gpt-4"):
            assert hardcoded not in stripped, (
                f"{hardcoded!r} leaked into llm_provider.py executable code"
            )


# ─── Adapter headless_complete smoke ─────────────────────────────────


class TestAdapterHeadless:
    def test_claude_code_parses_json_response(self):
        stdout = json.dumps({
            "result": "hi there",
            "model": "claude-opus-4-7",
            "usage": {
                "input_tokens": 10, "output_tokens": 5,
                "cache_read_input_tokens": 2, "cache_creation_input_tokens": 3,
            },
        })
        resp = _parse_claude_json(stdout)
        assert resp.text == "hi there"
        assert resp.tokens_in == 15  # 10 + 2 + 3
        assert resp.tokens_out == 5
        assert resp.cached_tokens == 2
        assert resp.model == "claude-opus-4-7"

    def test_claude_code_missing_cli_raises_not_implemented(self, monkeypatch):
        monkeypatch.setattr(
            "core.runtime.claude_code.shutil.which", lambda _name: None
        )
        with pytest.raises(NotImplementedError, match="claude CLI not found"):
            ClaudeCodeAdapter().headless_complete("hi")

    def test_codex_adapter_refuses_until_verified(self):
        with pytest.raises(NotImplementedError):
            CodexCliAdapter().headless_complete("hi")

    def test_gemini_adapter_refuses_until_verified(self):
        with pytest.raises(NotImplementedError):
            GeminiCliAdapter().headless_complete("hi")

    def test_cursor_never_supports_headless(self):
        assert CursorAdapter().headless_supported() is False
        with pytest.raises(NotImplementedError, match="Cursor"):
            CursorAdapter().headless_complete("hi")

    def test_claude_code_shells_out_successfully(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            "core.runtime.claude_code.shutil.which",
            lambda _name: "/fake/claude",
        )
        fake_stdout = json.dumps({
            "result": "reply", "model": "claude-opus-4-7",
            "usage": {"input_tokens": 1, "output_tokens": 1,
                      "cache_read_input_tokens": 0,
                      "cache_creation_input_tokens": 0},
        })

        def fake_run(cmd, **kwargs):
            return SimpleNamespace(returncode=0, stdout=fake_stdout, stderr="")

        monkeypatch.setattr("core.runtime.claude_code.subprocess.run", fake_run)
        resp = ClaudeCodeAdapter().headless_complete(
            "hi", max_tokens=100, system="sys"
        )
        assert resp.text == "reply"
        assert resp.model == "claude-opus-4-7"

    def test_claude_code_non_zero_exit_raises(self, monkeypatch):
        monkeypatch.setattr(
            "core.runtime.claude_code.shutil.which",
            lambda _name: "/fake/claude",
        )

        def fake_run(cmd, **kwargs):
            return SimpleNamespace(
                returncode=2, stdout="", stderr="boom"
            )

        monkeypatch.setattr("core.runtime.claude_code.subprocess.run", fake_run)
        with pytest.raises(LLMUnavailable, match="exited 2"):
            ClaudeCodeAdapter().headless_complete("hi")

    def test_claude_code_timeout_raises(self, monkeypatch):
        import subprocess as sp
        monkeypatch.setattr(
            "core.runtime.claude_code.shutil.which",
            lambda _name: "/fake/claude",
        )

        def fake_run(cmd, **kwargs):
            raise sp.TimeoutExpired(cmd="claude", timeout=60)

        monkeypatch.setattr("core.runtime.claude_code.subprocess.run", fake_run)
        with pytest.raises(LLMUnavailable, match="timed out"):
            ClaudeCodeAdapter().headless_complete("hi")

    def test_claude_code_os_error_raises(self, monkeypatch):
        monkeypatch.setattr(
            "core.runtime.claude_code.shutil.which",
            lambda _name: "/fake/claude",
        )

        def fake_run(cmd, **kwargs):
            raise OSError("EACCES")

        monkeypatch.setattr("core.runtime.claude_code.subprocess.run", fake_run)
        with pytest.raises(LLMUnavailable, match="subprocess failed"):
            ClaudeCodeAdapter().headless_complete("hi")

    def test_claude_code_headless_supported_when_cli_present(self, monkeypatch):
        monkeypatch.setattr(
            "core.runtime.claude_code.shutil.which",
            lambda _name: "/fake/claude",
        )
        assert ClaudeCodeAdapter().headless_supported() is True

    def test_claude_code_headless_unsupported_when_cli_missing(self, monkeypatch):
        monkeypatch.setattr(
            "core.runtime.claude_code.shutil.which",
            lambda _name: None,
        )
        assert ClaudeCodeAdapter().headless_supported() is False
