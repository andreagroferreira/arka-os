"""Tests for core.runtime.openrouter_provider — Model Fabric PR-B."""

from __future__ import annotations

import json
import urllib.error
from unittest.mock import patch

import pytest

from core.runtime.llm_provider import LLMUnavailable
from core.runtime.openrouter_provider import OpenRouterProvider


class _FakeResponse:
    def __init__(self, body: bytes):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self._body


def _chat_body(**overrides) -> bytes:
    payload = {
        "model": "moonshotai/kimi-k2.6",
        "choices": [{"message": {"role": "assistant",
                                 "content": "  fused answer  "}}],
        "usage": {
            "prompt_tokens": 120,
            "completion_tokens": 45,
            "prompt_tokens_details": {"cached_tokens": 80},
        },
    }
    payload.update(overrides)
    return json.dumps(payload).encode("utf-8")


@pytest.fixture(autouse=True)
def _no_ambient_config(monkeypatch, tmp_path):
    """Isolate from the developer machine: no env key, no keys.json."""
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
    monkeypatch.setattr(
        "core.runtime.openrouter_provider._KEYS_PATH",
        tmp_path / "keys.json",
    )


def test_name_is_openrouter():
    assert OpenRouterProvider().name() == "openrouter"


class TestAvailability:
    def test_unavailable_without_key(self):
        assert OpenRouterProvider(model="x/y").is_available() is False

    def test_available_with_env_key_and_model(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
        assert OpenRouterProvider(model="x/y").is_available() is True

    def test_available_with_keys_json(self, monkeypatch, tmp_path):
        keys = tmp_path / "keys.json"
        keys.write_text(json.dumps({"OPENROUTER_API_KEY": "sk-or-file"}), encoding="utf-8")
        monkeypatch.setattr(
            "core.runtime.openrouter_provider._KEYS_PATH", keys
        )
        assert OpenRouterProvider(model="x/y").is_available() is True

    def test_unavailable_with_key_but_no_model(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
        assert OpenRouterProvider().is_available() is False


class TestComplete:
    def test_returns_text_tokens_and_cached(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
        with patch(
            "core.runtime.openrouter_provider.urllib.request.urlopen"
        ) as mock:
            mock.return_value = _FakeResponse(_chat_body())
            response = OpenRouterProvider(model="moonshotai/kimi-k2.6").complete(
                "judge this", system="you are the judge"
            )
        assert response.text == "fused answer"
        assert response.tokens_in == 120
        assert response.tokens_out == 45
        assert response.cached_tokens == 80
        assert response.model == "moonshotai/kimi-k2.6"

    def test_sends_auth_and_usage_accounting(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
        with patch(
            "core.runtime.openrouter_provider.urllib.request.urlopen"
        ) as mock:
            mock.return_value = _FakeResponse(_chat_body())
            OpenRouterProvider(model="x/y").complete("hi", max_tokens=99)
        request = mock.call_args[0][0]
        assert request.get_header("Authorization") == "Bearer sk-or-test"
        sent = json.loads(request.data.decode("utf-8"))
        assert sent["max_tokens"] == 99
        assert sent["usage"] == {"include": True}
        assert sent["messages"][-1] == {"role": "user", "content": "hi"}

    def test_raises_without_key(self):
        with pytest.raises(LLMUnavailable, match="key not configured"):
            OpenRouterProvider(model="x/y").complete("hi")

    def test_raises_without_model(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
        with pytest.raises(LLMUnavailable, match="model not configured"):
            OpenRouterProvider().complete("hi")

    def test_http_error_surfaces_detail(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
        error = urllib.error.HTTPError(
            "https://openrouter.ai", 402, "Payment Required", {},
            __import__("io").BytesIO(b'{"error":"insufficient credits"}'),
        )
        with patch(
            "core.runtime.openrouter_provider.urllib.request.urlopen",
            side_effect=error,
        ):
            with pytest.raises(LLMUnavailable, match="HTTP 402"):
                OpenRouterProvider(model="x/y").complete("hi")

    def test_api_error_payload_raises(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
        body = json.dumps({"error": {"message": "model not found"}}).encode()
        with patch(
            "core.runtime.openrouter_provider.urllib.request.urlopen"
        ) as mock:
            mock.return_value = _FakeResponse(body)
            with pytest.raises(LLMUnavailable, match="model not found"):
                OpenRouterProvider(model="x/y").complete("hi")

    def test_invalid_json_raises(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
        with patch(
            "core.runtime.openrouter_provider.urllib.request.urlopen"
        ) as mock:
            mock.return_value = _FakeResponse(b"<html>gateway timeout</html>")
            with pytest.raises(LLMUnavailable, match="invalid JSON"):
                OpenRouterProvider(model="x/y").complete("hi")


class TestFactoryIntegration:
    def test_registered_in_provider_map(self):
        from core.runtime.llm_provider import _FALLBACK_ORDER, _PROVIDERS
        assert "openrouter" in _PROVIDERS
        assert "openrouter" in _FALLBACK_ORDER

    def test_chain_skips_openrouter_without_key(self, tmp_path):
        """No key configured -> is_available False -> chain moves on."""
        from core.runtime.llm_provider import get_llm_provider
        config = tmp_path / "config.json"
        config.write_text(json.dumps({"llm": {"provider": "openrouter"}}), encoding="utf-8")
        provider = get_llm_provider(config_path=config)
        assert provider.name() != "openrouter"
