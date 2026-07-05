"""OpenRouter provider — one API key, hundreds of models.

Model Fabric PR-B. One of the backends behind the ``LLMProvider``
Protocol in ``core/runtime/llm_provider.py``; callers go through
``get_llm_provider()`` or pass an explicit model resolved by
``core/runtime/model_router.py`` (e.g. role ``review`` →
``openrouter/deepseek/deepseek-v4-pro``).

OpenAI-compatible ``/api/v1/chat/completions`` via stdlib ``urllib`` —
no extra dependencies, mirroring ``ollama_provider.py``. Key resolution:
``OPENROUTER_API_KEY`` env, then ``~/.arkaos/keys.json``. Model from
constructor, then ``OPENROUTER_MODEL`` env, then
``models.yaml`` alias ``openrouter.default``.

OpenRouter returns token usage (and native cached-token counts for
providers that support caching) in the ``usage`` block; both are
forwarded so cost telemetry stays accurate.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from core.runtime.llm_provider import LLMResponse, LLMUnavailable

_API_BASE = "https://openrouter.ai/api/v1"
_TIMEOUT_S = 180  # frontier models on long prompts; fusion panels wait
_KEYS_PATH = Path.home() / ".arkaos" / "keys.json"

# Attribution headers — OpenRouter ranks apps by these; harmless otherwise.
_APP_HEADERS = {
    "HTTP-Referer": "https://github.com/andreagroferreira/arka-os",
    "X-Title": "ArkaOS",
}


def _read_key_from_keys_json() -> str:
    try:
        data = json.loads(_KEYS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    value = data.get("OPENROUTER_API_KEY", "")
    return value.strip() if isinstance(value, str) else ""


def _default_model_from_fabric() -> str:
    """Resolve the `openrouter.default` alias from models.yaml, if set."""
    try:
        from core.runtime.model_router import load_config
        config, _ = load_config()
    except Exception:
        return ""
    return config.aliases.get("openrouter", {}).get("default", "")


class OpenRouterProvider:
    """Provider that hits the OpenRouter chat-completions API."""

    ENV_KEY = "OPENROUTER_API_KEY"
    ENV_MODEL = "OPENROUTER_MODEL"

    def __init__(self, model: str | None = None, api_base: str | None = None) -> None:
        self._model_override = model
        self._api_base = (api_base or _API_BASE).rstrip("/")

    def name(self) -> str:
        return "openrouter"

    def _resolve_key(self) -> str:
        env_value = os.environ.get(self.ENV_KEY, "").strip()
        return env_value or _read_key_from_keys_json()

    def _resolve_model(self) -> str:
        if self._model_override:
            return self._model_override
        env_value = os.environ.get(self.ENV_MODEL, "").strip()
        return env_value or _default_model_from_fabric()

    def is_available(self) -> bool:
        """Static capability check: a key and a model are configured.

        No network probe — OpenRouter is a paid remote API and this is
        called on every provider-chain walk; a dead network surfaces as
        ``LLMUnavailable`` at call time and the chain moves on.
        """
        return bool(self._resolve_key() and self._resolve_model())

    def complete(
        self,
        prompt: str,
        *,
        max_tokens: int = 2000,
        system: str = "",
    ) -> LLMResponse:
        key = self._resolve_key()
        if not key:
            raise LLMUnavailable(
                "OpenRouter key not configured (set OPENROUTER_API_KEY or "
                "add it via `npx arkaos keys`)"
            )
        model = self._resolve_model()
        if not model:
            raise LLMUnavailable(
                "OpenRouter model not configured (set OPENROUTER_MODEL, pass "
                "model=, or set aliases.openrouter.default in models.yaml)"
            )
        data = self._post_chat(key, self._build_payload(model, prompt, system, max_tokens))
        return self._to_response(data, model)

    def _build_payload(
        self, model: str, prompt: str, system: str, max_tokens: int
    ) -> dict:
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "stream": False,
            "usage": {"include": True},  # cost + cached tokens in response
        }

    def _post_chat(self, key: str, payload: dict) -> dict:
        request = urllib.request.Request(
            f"{self._api_base}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
                **_APP_HEADERS,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=_TIMEOUT_S) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            raise LLMUnavailable(
                f"OpenRouter HTTP {exc.code}: {detail}"
            ) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise LLMUnavailable(f"OpenRouter request failed: {exc}") from exc
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise LLMUnavailable(f"OpenRouter returned invalid JSON: {exc}") from exc

    def _to_response(self, data: dict, model: str) -> LLMResponse:
        if data.get("error"):
            message = data["error"].get("message", "unknown error")
            raise LLMUnavailable(f"OpenRouter error: {message}")
        choices = data.get("choices") or []
        text = ""
        if choices:
            text = ((choices[0].get("message") or {}).get("content") or "").strip()
        usage = data.get("usage") or {}
        cached = int(
            (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0) or 0
        )
        return LLMResponse(
            text=text,
            tokens_in=int(usage.get("prompt_tokens", 0) or 0),
            tokens_out=int(usage.get("completion_tokens", 0) or 0),
            cached_tokens=cached,
            model=str(data.get("model") or model),
        )
