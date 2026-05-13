"""Ollama provider — local LLM inference via the localhost API.

One of several backends behind the `LLMProvider` Protocol in
``core/runtime/llm_provider.py``. The cognitive layer never imports
this class directly; it goes through ``get_llm_provider()`` which
selects from a configurable chain (subagent → ollama → anthropic-direct
→ stub by default; user-configurable in ``~/.arkaos/config.json``).

Communicates with the local Ollama service at the standard
``http://localhost:11434`` endpoint via stdlib ``urllib`` — no extra
dependencies. Model picked from ``OLLAMA_MODEL`` env var, then
``profile.json:cognitiveModel``, then a sensible default. Whichever
the user has chosen sticks to a single chat completion call per
``complete()`` invocation.

See ``docs/adr/2026-05-13-cognitive-layer-pivot-to-hooks.md`` and the
PR8 v2.30.0 commit for the architectural rationale.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from core.runtime.llm_provider import LLMResponse, LLMUnavailable


_OLLAMA_HOST = "http://localhost:11434"
_DEFAULT_MODEL = "gemma3:27b"  # fallback only — most users override via env / profile
_GENERATE_TIMEOUT_S = 120  # nightly Dreaming run — large prompts allowed


class OllamaProvider:
    """Provider that hits the local Ollama daemon for chat completion."""

    ENV_HOST = "OLLAMA_HOST"
    ENV_MODEL = "OLLAMA_MODEL"

    def __init__(self, model: str | None = None, host: str | None = None) -> None:
        self._model_override = model
        self._host = host or os.environ.get(self.ENV_HOST, _OLLAMA_HOST)

    def name(self) -> str:
        return "ollama"

    def is_available(self) -> bool:
        """Cheap reachability check against ``/api/tags``."""
        url = f"{self._host.rstrip('/')}/api/tags"
        try:
            with urllib.request.urlopen(url, timeout=1.5) as response:
                return response.status == 200
        except (urllib.error.URLError, TimeoutError, OSError):
            return False

    def complete(
        self,
        prompt: str,
        *,
        max_tokens: int = 2000,
        system: str = "",
    ) -> LLMResponse:
        model = self._resolve_model()
        if not model:
            raise LLMUnavailable("Ollama model not configured (set OLLAMA_MODEL or profile.cognitiveModel)")

        payload = self._build_payload(model, prompt, system, max_tokens)
        data = self._post_generate(payload)
        return self._to_response(data, model)

    def _resolve_model(self) -> str | None:
        if self._model_override:
            return self._model_override
        env_value = os.environ.get(self.ENV_MODEL, "").strip()
        if env_value:
            return env_value
        profile_model = _read_profile_model()
        if profile_model:
            return profile_model
        return _DEFAULT_MODEL

    def _build_payload(self, model: str, prompt: str, system: str, max_tokens: int) -> dict:
        """Build /api/chat payload.

        Using the chat endpoint (not /api/generate) means Ollama applies
        the model's official chat template, which is critical for
        instruction-tuned models like Qwen, Gemma, Mistral — without the
        template most models burn through their token budget before
        emitting visible content. Smoke-tested 2026-05-13 against
        qwen3-coder:30b which returned the expected "hi" in 2 tokens.
        """
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"num_predict": max_tokens},
        }

    def _post_generate(self, payload: dict) -> dict:
        url = f"{self._host.rstrip('/')}/api/chat"
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url, data=body, headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(request, timeout=_GENERATE_TIMEOUT_S) as response:
                raw = response.read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise LLMUnavailable(f"Ollama request failed: {exc}") from exc
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise LLMUnavailable(f"Ollama returned invalid JSON: {exc}") from exc

    def _to_response(self, data: dict, model: str) -> LLMResponse:
        message = data.get("message", {}) or {}
        text = (message.get("content") or data.get("response") or "").strip()
        tokens_in = int(data.get("prompt_eval_count", 0) or 0)
        tokens_out = int(data.get("eval_count", 0) or 0)
        return LLMResponse(
            text=text,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cached_tokens=0,  # Ollama does not surface a cache signal
            model=model,
        )


def _read_profile_model() -> str | None:
    path = Path.home() / ".arkaos" / "profile.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    value = data.get("cognitiveModel")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None
