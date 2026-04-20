"""Gemini CLI runtime adapter.

Google's Gemini CLI. Uses GEMINI.md for instructions and activate_skill for skills.

Headless invocation reference (verified against
https://github.com/google-gemini/gemini-cli docs — Context7 query
on 2026-04-20):

    gemini -p "<prompt>" --output-format json

The JSON payload contains a ``response`` key (the model's text) and a
``stats`` block with ``totalTokenCount`` / token counts. On failure the
payload includes an ``error`` block with diagnostic details. If JSON
parsing fails we fall back to treating stdout as raw text and estimate
tokens via a ``len(text) // 4`` heuristic — better than losing cost
telemetry entirely.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from os.path import expanduser
from typing import TYPE_CHECKING

from core.runtime.base import RuntimeAdapter, RuntimeConfig, AgentContext, AgentResult

if TYPE_CHECKING:
    from core.runtime.llm_provider import LLMResponse


_TIMEOUT_SECONDS = 60
_TOKEN_ESTIMATE_DIVISOR = 4  # Rough chars-per-token heuristic.
_STDERR_CLIP = 200


class GeminiCliAdapter(RuntimeAdapter):
    """Adapter for Google's Gemini CLI."""

    def get_config(self) -> RuntimeConfig:
        home = Path(expanduser("~"))
        return RuntimeConfig(
            id="gemini",
            name="Gemini CLI",
            config_dir=home / ".gemini",
            skills_dir=home / ".gemini" / "skills",
            settings_file=home / ".gemini" / "settings.json",
            supports_hooks=False,
            supports_subagents=True,
            supports_mcp=True,
            max_context_tokens=1_000_000,
        )

    def inject_context(self, layers: dict[str, str]) -> str:
        """Gemini receives context via GEMINI.md instruction file."""
        parts = []
        for name, content in layers.items():
            parts.append(f"## {name}\n{content}")
        return "\n\n".join(parts)

    def dispatch_agent(self, context: AgentContext) -> AgentResult:
        return AgentResult(
            agent_id=context.agent_id,
            status="dispatched",
            output=f"Agent {context.agent_id} dispatched via Gemini CLI",
            metadata={"runtime": "gemini"},
        )

    def spawn_subagent(self, context: AgentContext) -> AgentResult:
        return AgentResult(
            agent_id=context.agent_id,
            status="dispatched",
            output=f"Subagent {context.agent_id} spawned via Gemini CLI",
            metadata={"runtime": "gemini", "pattern": "subagent"},
        )

    def read_file(self, path: str) -> str:
        raise NotImplementedError("Use Gemini CLI's native file read")

    def write_file(self, path: str, content: str) -> None:
        raise NotImplementedError("Use Gemini CLI's native file write")

    def edit_file(self, path: str, old: str, new: str) -> None:
        raise NotImplementedError("Use Gemini CLI's native file edit")

    def execute_command(self, command: str, timeout: int = 120) -> tuple[str, int]:
        raise NotImplementedError("Use Gemini CLI's native shell execution")

    def search_files(self, pattern: str, path: str = ".") -> list[str]:
        raise NotImplementedError("Use Gemini CLI's native file search")

    def search_content(self, pattern: str, path: str = ".") -> list[str]:
        raise NotImplementedError("Use Gemini CLI's native content search")

    def headless_supported(self) -> bool:
        return shutil.which("gemini") is not None

    def headless_complete(
        self,
        prompt: str,
        *,
        max_tokens: int = 2000,
        system: str = "",
    ) -> "LLMResponse":
        from core.runtime.llm_provider import LLMUnavailable

        binary = shutil.which("gemini")
        if binary is None:
            raise NotImplementedError(
                "gemini CLI not found on PATH — install Gemini CLI to "
                "enable headless completion."
            )
        effective_prompt = _merge_system_prompt(prompt, system)
        cmd = [binary, "-p", effective_prompt, "--output-format", "json"]
        proc = _run_gemini_cli(cmd)
        if proc.returncode != 0:
            stderr_tail = proc.stderr.strip()[:_STDERR_CLIP]
            raise LLMUnavailable(
                f"gemini CLI exited {proc.returncode}: {stderr_tail}"
            )
        return _parse_gemini_cli_output(proc.stdout)


def _merge_system_prompt(prompt: str, system: str) -> str:
    # Gemini CLI's -p flag accepts a single prompt; prepend the system
    # text when provided so downstream behaviour matches Claude Code.
    if not system:
        return prompt
    return f"{system}\n\n---\n\n{prompt}"


def _run_gemini_cli(cmd: list[str]) -> subprocess.CompletedProcess:
    from core.runtime.llm_provider import LLMUnavailable

    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise LLMUnavailable(
            f"gemini CLI timed out after {_TIMEOUT_SECONDS}s"
        ) from exc
    except OSError as exc:
        raise LLMUnavailable(f"gemini CLI subprocess failed: {exc}") from exc


def _parse_gemini_cli_output(stdout: str) -> "LLMResponse":
    from core.runtime.llm_provider import LLMResponse

    stripped = stdout.strip()
    if not stripped:
        return LLMResponse(
            text="", tokens_in=0, tokens_out=0, cached_tokens=0, model=""
        )
    payload = _safe_loads(stripped)
    if payload is None:
        # Non-JSON fallback: treat stdout as raw text, estimate tokens.
        return _response_from_plain_text(stripped)
    return _response_from_json_payload(payload)


def _safe_loads(text: str) -> dict | None:
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _response_from_plain_text(text: str) -> "LLMResponse":
    from core.runtime.llm_provider import LLMResponse

    estimate = max(1, len(text) // _TOKEN_ESTIMATE_DIVISOR)
    return LLMResponse(
        text=text,
        tokens_in=0,
        tokens_out=estimate,
        cached_tokens=0,
        model="",
    )


def _response_from_json_payload(payload: dict) -> "LLMResponse":
    from core.runtime.llm_provider import LLMResponse, LLMUnavailable

    error = payload.get("error")
    if isinstance(error, dict) and error:
        message = str(error.get("message") or error).strip()[:_STDERR_CLIP]
        raise LLMUnavailable(f"gemini CLI returned error: {message}")

    text = str(payload.get("response") or payload.get("result") or "")
    tokens_in, tokens_out = _extract_token_counts(payload, text)
    model = str(payload.get("model") or "")
    return LLMResponse(
        text=text,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cached_tokens=0,
        model=model,
    )


def _extract_token_counts(payload: dict, text: str) -> tuple[int, int]:
    stats = payload.get("stats") or payload.get("usageMetadata") or {}
    if isinstance(stats, dict):
        tokens_in = int(stats.get("promptTokenCount") or stats.get("input_tokens") or 0)
        tokens_out = int(
            stats.get("candidatesTokenCount")
            or stats.get("output_tokens")
            or 0
        )
        # Fall back to the rolled-up total when per-side counts are absent.
        if tokens_in == 0 and tokens_out == 0:
            total = int(stats.get("totalTokenCount") or 0)
            if total > 0:
                return 0, total
        return tokens_in, tokens_out
    # No stats block at all — estimate output from text length.
    return 0, max(1, len(text) // _TOKEN_ESTIMATE_DIVISOR)
