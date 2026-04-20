"""Runtime-agnostic LLM provider abstraction.

Three concrete providers, one factory, one fallback chain. The abstraction
is deliberately thin: `complete(prompt, *, max_tokens, system) -> LLMResponse`.
Nothing in this module selects a model. The runtime (Claude Code, Codex,
Gemini, Cursor) or the user's environment (`ANTHROPIC_MODEL`) owns that
decision. Adding a branch like `if "opus" in model: ...` here violates the
LLM-agnostic contract.

Provider order (default factory):
    1. subagent           — shell out to the active runtime's CLI
    2. anthropic-direct   — SDK call with prompt caching (requires env)
    3. stub               — returns empty LLMResponse (template fallback)

Config: `~/.arkaos/config.json`:
    {"llm": {"provider": "subagent"}}
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from core.runtime import registry
from core.runtime.base import RuntimeAdapter
from core.runtime.llm_cost_telemetry import record_cost
from core.runtime.pricing import estimate_cost_usd


_DEFAULT_CONFIG_PATH = Path.home() / ".arkaos" / "config.json"
_FALLBACK_ORDER: tuple[str, ...] = ("subagent", "anthropic-direct", "stub")


# ─── Public dataclass ─────────────────────────────────────────────────


@dataclass(frozen=True)
class LLMResponse:
    text: str
    tokens_in: int
    tokens_out: int
    cached_tokens: int  # 0 if no caching available/used
    model: str  # whatever the runtime/SDK reported; may be ""


# ─── Exceptions ───────────────────────────────────────────────────────


class LLMUnavailable(RuntimeError):
    """Raised when a provider cannot complete a request at call time.

    `is_available()` surfaces the static capability check; this
    exception is for runtime-time failures (timeout, CLI missing,
    subprocess error). Callers typically catch this to fall through to
    the next provider in the chain or to a template path.
    """


# ─── Protocol ─────────────────────────────────────────────────────────


@runtime_checkable
class LLMProvider(Protocol):
    def complete(
        self,
        prompt: str,
        *,
        max_tokens: int = 2000,
        system: str = "",
    ) -> LLMResponse: ...

    def is_available(self) -> bool: ...

    def name(self) -> str: ...


# ─── Provider: Subagent (headless CLI shell-out) ──────────────────────


class SubagentProvider:
    """Delegate completion to the active runtime's headless CLI.

    The runtime — not ArkaOS — picks the model. We never pass one.
    """

    def __init__(self, adapter: RuntimeAdapter | None = None) -> None:
        self._adapter = adapter

    def name(self) -> str:
        return "subagent"

    def _resolve_adapter(self) -> RuntimeAdapter:
        if self._adapter is not None:
            return self._adapter
        runtime_id = registry.detect_runtime()
        return registry.get_adapter(runtime_id)

    def is_available(self) -> bool:
        try:
            adapter = self._resolve_adapter()
        except Exception:  # noqa: BLE001
            return False
        try:
            return adapter.headless_supported()
        except Exception:  # noqa: BLE001
            return False

    def complete(
        self,
        prompt: str,
        *,
        max_tokens: int = 2000,
        system: str = "",
    ) -> LLMResponse:
        adapter = self._resolve_adapter()
        try:
            response = adapter.headless_complete(
                prompt, max_tokens=max_tokens, system=system
            )
        except NotImplementedError as exc:
            raise LLMUnavailable(str(exc)) from exc
        except LLMUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001
            raise LLMUnavailable(
                f"headless_complete failed: {exc.__class__.__name__}: {exc}"
            ) from exc

        _record(
            session_id=os.environ.get("ARKA_SESSION_ID", ""),
            provider=self.name(),
            response=response,
        )
        return response


# ─── Provider: Anthropic Direct (SDK with prompt caching) ─────────────


class AnthropicDirectProvider:
    """Call the Anthropic SDK directly, model read from env var.

    The `anthropic` package is an optional dependency; if it is not
    installed, `is_available()` returns False and the factory skips to
    the next provider.
    """

    ENV_MODEL = "ANTHROPIC_MODEL"
    ENV_API_KEY = "ANTHROPIC_API_KEY"

    def __init__(self, client: object | None = None) -> None:
        self._client = client

    def name(self) -> str:
        return "anthropic-direct"

    def _model_from_env(self) -> str | None:
        value = os.environ.get(self.ENV_MODEL, "").strip()
        return value or None

    def is_available(self) -> bool:
        if self._model_from_env() is None:
            return False
        if self._client is not None:
            return True
        if not os.environ.get(self.ENV_API_KEY, "").strip():
            return False
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return False
        return True

    def _build_client(self) -> object:
        if self._client is not None:
            return self._client
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover — guarded by is_available
            raise LLMUnavailable(
                "anthropic SDK not installed. "
                "Install with `pip install anthropic` or fall back to subagent."
            ) from exc
        return anthropic.Anthropic()

    def _build_system_blocks(self, system: str) -> list[dict[str, object]]:
        # Empty system prompt → skip cache marker. Caching below the
        # provider minimum is a no-op but harmless.
        if not system:
            return []
        return [
            {
                "type": "text",
                "text": system,
                "cache_control": {"type": "ephemeral"},
            }
        ]

    def _build_anthropic_payload(
        self, prompt: str, system: str, max_tokens: int, model: str
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        system_blocks = self._build_system_blocks(system)
        if system_blocks:
            payload["system"] = system_blocks
        return payload

    def complete(
        self,
        prompt: str,
        *,
        max_tokens: int = 2000,
        system: str = "",
    ) -> LLMResponse:
        model = self._model_from_env()
        if model is None:
            raise LLMUnavailable(
                f"{self.ENV_MODEL} not set — AnthropicDirectProvider "
                "cannot select a model."
            )
        client = self._build_client()
        payload = self._build_anthropic_payload(prompt, system, max_tokens, model)
        try:
            raw = client.messages.create(**payload)  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001
            raise LLMUnavailable(
                f"anthropic.messages.create failed: {exc.__class__.__name__}: {exc}"
            ) from exc

        response = _response_from_anthropic(raw, fallback_model=model)
        _record(
            session_id=os.environ.get("ARKA_SESSION_ID", ""),
            provider=self.name(),
            response=response,
        )
        return response


def _response_from_anthropic(raw: object, fallback_model: str) -> LLMResponse:
    text = _extract_anthropic_text(raw)
    usage = getattr(raw, "usage", None)
    tokens_in = int(getattr(usage, "input_tokens", 0) or 0)
    tokens_out = int(getattr(usage, "output_tokens", 0) or 0)
    cache_read = int(getattr(usage, "cache_read_input_tokens", 0) or 0)
    cache_write = int(getattr(usage, "cache_creation_input_tokens", 0) or 0)
    # Cached tokens = cache reads (cache writes are the first pass).
    cached = cache_read
    # Input tokens billed = uncached fresh + cache write (both full
    # price) + cache read (discounted). Expose the sum so downstream
    # pricing sees every billable input token.
    total_input = tokens_in + cache_read + cache_write
    model = str(getattr(raw, "model", "") or fallback_model)
    return LLMResponse(
        text=text,
        tokens_in=total_input,
        tokens_out=tokens_out,
        cached_tokens=cached,
        model=model,
    )


def _extract_anthropic_text(raw: object) -> str:
    content = getattr(raw, "content", None)
    if not content:
        return ""
    parts: list[str] = []
    for block in content:
        block_type = getattr(block, "type", None)
        if block_type == "text":
            parts.append(str(getattr(block, "text", "") or ""))
    return "".join(parts)


# ─── Provider: Stub ───────────────────────────────────────────────────


class StubProvider:
    """Returns an empty LLMResponse. Used in tests and as last fallback."""

    def name(self) -> str:
        return "stub"

    def is_available(self) -> bool:
        return True

    def complete(
        self,
        prompt: str,  # noqa: ARG002
        *,
        max_tokens: int = 2000,  # noqa: ARG002
        system: str = "",  # noqa: ARG002
    ) -> LLMResponse:
        return LLMResponse(
            text="", tokens_in=0, tokens_out=0, cached_tokens=0, model=""
        )


# ─── Factory + fallback chain ─────────────────────────────────────────


_PROVIDERS: dict[str, type] = {
    "subagent": SubagentProvider,
    "anthropic-direct": AnthropicDirectProvider,
    "stub": StubProvider,
}


def _read_provider_config(config_path: Path | None) -> str:
    path = config_path or _DEFAULT_CONFIG_PATH
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _FALLBACK_ORDER[0]
    value = (data.get("llm") or {}).get("provider")
    if isinstance(value, str) and value.strip() in _PROVIDERS:
        return value.strip()
    return _FALLBACK_ORDER[0]


def get_llm_provider(config_path: Path | None = None) -> LLMProvider:
    """Return the first available provider per config + fallback chain.

    If the configured provider fails its `is_available()` check, fall
    back through the `_FALLBACK_ORDER`. Logs each fallback to telemetry
    so operators can see when a provider is silently skipped. The stub
    is always available and ensures a non-null return.
    """
    preferred = _read_provider_config(config_path)
    chain: list[str] = [preferred]
    for name in _FALLBACK_ORDER:
        if name not in chain:
            chain.append(name)

    last: LLMProvider | None = None
    for name in chain:
        provider_cls = _PROVIDERS.get(name)
        if provider_cls is None:
            continue
        instance: LLMProvider = provider_cls()
        last = instance
        if instance.is_available():
            if name != preferred:
                _log_fallback(preferred=preferred, selected=name)
            return instance
        _log_fallback(preferred=preferred, selected=name, reason="unavailable")

    # Stub is always available, so this branch is only a safety net.
    return last if last is not None else StubProvider()


def _log_fallback(preferred: str, selected: str, reason: str = "") -> None:
    # Piggy-back on the cost telemetry file: zero-token, provider-only row.
    # Downstream can group by provider to spot degraded chains.
    record_cost(
        session_id=os.environ.get("ARKA_SESSION_ID", ""),
        provider=f"fallback:{preferred}->{selected}",
        model=reason or "selected",
        tokens_in=0,
        tokens_out=0,
        cached_tokens=0,
        estimated_cost_usd=None,
    )


def _record(session_id: str, provider: str, response: LLMResponse) -> None:
    cost = estimate_cost_usd(
        response.model,
        response.tokens_in,
        response.tokens_out,
        response.cached_tokens,
    )
    record_cost(
        session_id=session_id,
        provider=provider,
        model=response.model,
        tokens_in=response.tokens_in,
        tokens_out=response.tokens_out,
        cached_tokens=response.cached_tokens,
        estimated_cost_usd=cost,
    )
