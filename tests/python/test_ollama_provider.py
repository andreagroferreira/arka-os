"""Tests for core.runtime.ollama_provider — local-LLM provider."""

from __future__ import annotations

import io
import json
from unittest.mock import patch

import pytest

from core.runtime.llm_provider import LLMUnavailable
from core.runtime.ollama_provider import OllamaProvider


class _FakeResponse:
    def __init__(self, status: int, body: bytes):
        self.status = status
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self._body


def test_name_is_ollama():
    assert OllamaProvider().name() == "ollama"


def test_is_available_true_when_tags_returns_200():
    with patch("core.runtime.ollama_provider.urllib.request.urlopen") as mock:
        mock.return_value = _FakeResponse(200, b"{}")
        assert OllamaProvider().is_available() is True


def test_is_available_false_when_tags_unreachable():
    with patch("core.runtime.ollama_provider.urllib.request.urlopen", side_effect=OSError("connection refused")):
        assert OllamaProvider().is_available() is False


def test_complete_returns_llm_response_with_text_and_tokens():
    payload = json.dumps({
        "message": {"role": "assistant", "content": "  here is the answer  "},
        "prompt_eval_count": 12,
        "eval_count": 34,
    }).encode("utf-8")
    with patch("core.runtime.ollama_provider.urllib.request.urlopen") as mock:
        mock.return_value = _FakeResponse(200, payload)
        response = OllamaProvider(model="qwen3-coder:30b").complete("hi")
    assert response.text == "here is the answer"
    assert response.tokens_in == 12
    assert response.tokens_out == 34
    assert response.cached_tokens == 0
    assert response.model == "qwen3-coder:30b"


def test_complete_falls_back_to_response_field_for_legacy_models():
    """Older models returning the /api/generate shape also work."""
    payload = json.dumps({
        "response": "legacy answer",
        "prompt_eval_count": 5,
        "eval_count": 7,
    }).encode("utf-8")
    with patch("core.runtime.ollama_provider.urllib.request.urlopen") as mock:
        mock.return_value = _FakeResponse(200, payload)
        response = OllamaProvider(model="x").complete("hi")
    assert response.text == "legacy answer"


def test_complete_raises_llm_unavailable_on_network_error():
    with patch("core.runtime.ollama_provider.urllib.request.urlopen", side_effect=OSError("connection refused")):
        with pytest.raises(LLMUnavailable, match="Ollama request failed"):
            OllamaProvider(model="x").complete("hi")


def test_complete_raises_llm_unavailable_on_invalid_json():
    with patch("core.runtime.ollama_provider.urllib.request.urlopen") as mock:
        mock.return_value = _FakeResponse(200, b"{not json")
        with pytest.raises(LLMUnavailable, match="invalid JSON"):
            OllamaProvider(model="x").complete("hi")


def test_complete_raises_when_no_model_configured(monkeypatch):
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    monkeypatch.setattr(
        "core.runtime.ollama_provider._read_profile_model", lambda: None
    )
    # Patch the default to None so we can verify the no-model path
    monkeypatch.setattr(
        "core.runtime.ollama_provider._DEFAULT_MODEL", None
    )
    with pytest.raises(LLMUnavailable, match="model not configured"):
        OllamaProvider().complete("hi")


def test_env_model_overrides_default(monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "qwen3-coder:30b")
    monkeypatch.setattr("core.runtime.ollama_provider._read_profile_model", lambda: None)
    payload = json.dumps({"message": {"content": "x"}, "prompt_eval_count": 1, "eval_count": 1}).encode()
    with patch("core.runtime.ollama_provider.urllib.request.urlopen") as mock:
        mock.return_value = _FakeResponse(200, payload)
        response = OllamaProvider().complete("hi")
    assert response.model == "qwen3-coder:30b"


def test_explicit_model_arg_wins_over_env(monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "from-env")
    monkeypatch.setattr("core.runtime.ollama_provider._read_profile_model", lambda: None)
    payload = json.dumps({"message": {"content": "x"}, "prompt_eval_count": 1, "eval_count": 1}).encode()
    with patch("core.runtime.ollama_provider.urllib.request.urlopen") as mock:
        mock.return_value = _FakeResponse(200, payload)
        response = OllamaProvider(model="from-arg").complete("hi")
    assert response.model == "from-arg"


def test_provider_registered_in_factory_chain():
    from core.runtime.llm_provider import _FALLBACK_ORDER, _PROVIDERS
    assert "ollama" in _PROVIDERS
    assert "ollama" in _FALLBACK_ORDER
    # Ollama should sit between subagent and anthropic-direct in the chain
    sub_idx = _FALLBACK_ORDER.index("subagent")
    ollama_idx = _FALLBACK_ORDER.index("ollama")
    anth_idx = _FALLBACK_ORDER.index("anthropic-direct")
    assert sub_idx < ollama_idx < anth_idx
