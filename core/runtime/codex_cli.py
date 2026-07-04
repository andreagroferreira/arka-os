"""Codex CLI runtime adapter.

OpenAI's Codex CLI. Supports sandboxed execution and file operations.
More limited than Claude Code: no native hooks, no ArkaOS agent dispatch.

Headless invocation (verified against the installed binary,
codex-cli 0.142.5, `codex exec --help`, 2026-07-04):

    codex exec --json --skip-git-repo-check --sandbox read-only "<prompt>"

``--json`` prints events to stdout as JSONL. Live-verified event shapes:

    {"type":"item.completed","item":{"type":"agent_message","text":"..."}}
    {"type":"turn.completed","usage":{"input_tokens":N,
        "cached_input_tokens":N,"output_tokens":N,
        "reasoning_output_tokens":N}}

Older Codex CLI builds emitted ``{"msg":{"type":"agent_message",
"message":"..."}}`` — parsed defensively too. When no JSONL parses at
all, stdout is treated as raw text with a ``len(text) // 4`` token
estimate (same fallback as the Gemini adapter). stdin is closed
explicitly: with a prompt argument AND piped stdin, ``codex exec``
appends stdin as a ``<stdin>`` block, which a hook/daemon caller must
never trigger.
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


# codex exec runs a full agent turn (reasoning + sandbox bootstrap) — the
# live-verified trivial prompt took ~15s, so 60s (the Gemini budget) is
# too tight a ceiling for real cognitive-layer prompts.
_TIMEOUT_SECONDS = 120
_TOKEN_ESTIMATE_DIVISOR = 4  # Rough chars-per-token heuristic.
_STDERR_CLIP = 200


class CodexCliAdapter(RuntimeAdapter):
    """Adapter for OpenAI's Codex CLI."""

    def get_config(self) -> RuntimeConfig:
        home = Path(expanduser("~"))
        return RuntimeConfig(
            id="codex",
            name="Codex CLI",
            config_dir=home / ".codex",
            skills_dir=home / ".codex" / "skills",
            settings_file=home / ".codex" / "settings.json",
            supports_hooks=False,
            supports_subagents=True,
            supports_mcp=False,
            max_context_tokens=200_000,
        )

    def capabilities(self) -> dict[str, bool]:
        return {
            "agent_dispatch": False,  # descriptor only — no ArkaOS agents
            "headless": True,         # codex exec --json (real, PR-6)
            "file_ops": True,         # native, sandboxed, interactive use
            "hooks": False,
        }

    def inject_context(self, layers: dict[str, str]) -> str:
        """Codex receives context via AGENTS.md instruction file."""
        parts = []
        for name, content in layers.items():
            parts.append(f"## {name}\n{content}")
        return "\n\n".join(parts)

    def dispatch_agent(self, context: AgentContext) -> AgentResult:
        """Codex dispatches agents via its native agent system."""
        return AgentResult(
            agent_id=context.agent_id,
            status="dispatched",
            output=f"Agent {context.agent_id} dispatched via Codex",
            metadata={"runtime": "codex"},
        )

    def spawn_subagent(self, context: AgentContext) -> AgentResult:
        """Codex supports subagents with fresh context."""
        return AgentResult(
            agent_id=context.agent_id,
            status="dispatched",
            output=f"Subagent {context.agent_id} spawned via Codex",
            metadata={"runtime": "codex", "pattern": "subagent"},
        )

    def read_file(self, path: str) -> str:
        raise NotImplementedError("Use Codex CLI's native file read")

    def write_file(self, path: str, content: str) -> None:
        raise NotImplementedError("Use Codex CLI's native file write")

    def edit_file(self, path: str, old: str, new: str) -> None:
        raise NotImplementedError("Use Codex CLI's native file edit")

    def execute_command(self, command: str, timeout: int = 120) -> tuple[str, int]:
        raise NotImplementedError("Use Codex CLI's native shell execution")

    def search_files(self, pattern: str, path: str = ".") -> list[str]:
        raise NotImplementedError("Use Codex CLI's native file search")

    def search_content(self, pattern: str, path: str = ".") -> list[str]:
        raise NotImplementedError("Use Codex CLI's native content search")

    def headless_supported(self) -> bool:
        return shutil.which("codex") is not None

    def headless_complete(
        self,
        prompt: str,
        *,
        max_tokens: int = 2000,
        system: str = "",
    ) -> "LLMResponse":
        """One-shot completion via `codex exec --json`.

        Verified against Codex CLI 0.142.5 (`codex exec --help` + a live
        JSONL probe) on 2026-07-04. Sandbox is read-only and the git-repo
        check is skipped so the call works from any cwd. Raises
        LLMUnavailable on non-zero exit, timeout, or error-only streams.
        """
        from core.runtime.llm_provider import LLMUnavailable

        binary = shutil.which("codex")
        if binary is None:
            raise NotImplementedError(
                "codex CLI not found on PATH — install Codex CLI to "
                "enable headless completion."
            )
        effective_prompt = _merge_system_prompt(prompt, system)
        cmd = [
            binary, "exec", "--json", "--skip-git-repo-check",
            "--sandbox", "read-only", effective_prompt,
        ]
        proc = _run_codex_cli(cmd)
        if proc.returncode != 0:
            stderr_tail = proc.stderr.strip()[:_STDERR_CLIP]
            raise LLMUnavailable(
                f"codex CLI exited {proc.returncode}: {stderr_tail}"
            )
        return _parse_codex_cli_output(proc.stdout)


def _merge_system_prompt(prompt: str, system: str) -> str:
    # codex exec takes a single prompt argument; prepend the system text
    # when provided so downstream behaviour matches the other adapters.
    if not system:
        return prompt
    return f"{system}\n\n---\n\n{prompt}"


def _run_codex_cli(cmd: list[str]) -> subprocess.CompletedProcess:
    from core.runtime.llm_provider import LLMUnavailable

    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
            check=False,
            # CRITICAL: with a prompt arg AND piped stdin, codex exec
            # appends stdin as a <stdin> block — close it explicitly.
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired as exc:
        raise LLMUnavailable(
            f"codex CLI timed out after {_TIMEOUT_SECONDS}s"
        ) from exc
    except OSError as exc:
        raise LLMUnavailable(f"codex CLI subprocess failed: {exc}") from exc


def _agent_message_from_event(event: dict) -> str | None:
    """Extract agent message text from a JSONL event (both shapes)."""
    item = event.get("item")
    if isinstance(item, dict) and item.get("type") == "agent_message":
        return str(item.get("text") or "")
    msg = event.get("msg")
    if isinstance(msg, dict) and msg.get("type") == "agent_message":
        return str(msg.get("message") or "")
    return None


def _usage_from_event(event: dict) -> dict | None:
    """Extract the usage block from a turn.completed / token_count event."""
    if event.get("type") == "turn.completed":
        usage = event.get("usage")
        if isinstance(usage, dict):
            return usage
    msg = event.get("msg")
    if isinstance(msg, dict) and msg.get("type") == "token_count":
        info = msg.get("info")
        if isinstance(info, dict):
            total = info.get("total_token_usage")
            if isinstance(total, dict):
                return total
    return None


def _error_from_event(event: dict) -> str | None:
    if event.get("type") == "error":
        return str(event.get("message") or "codex CLI error")
    item = event.get("item")
    if isinstance(item, dict) and item.get("type") == "error":
        return str(item.get("message") or "codex CLI error")
    return None


def _parse_codex_cli_output(stdout: str) -> "LLMResponse":
    from core.runtime.llm_provider import LLMResponse, LLMUnavailable

    stripped = stdout.strip()
    if not stripped:
        return LLMResponse(
            text="", tokens_in=0, tokens_out=0, cached_tokens=0, model=""
        )

    text: str | None = None
    usage: dict | None = None
    error: str | None = None
    parsed_any = False
    for line in stripped.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(event, dict):
            continue
        parsed_any = True
        message = _agent_message_from_event(event)
        if message is not None:
            text = message  # last agent message wins
        found_usage = _usage_from_event(event)
        if found_usage is not None:
            usage = found_usage
        found_error = _error_from_event(event)
        if found_error is not None:
            error = found_error

    if not parsed_any:
        # Non-JSONL fallback: treat stdout as raw text, estimate tokens.
        return _response_from_plain_text(stripped)
    if text is None:
        # Error items can coexist with a successful agent message (e.g.
        # skills-budget warnings) — only fail when NO message arrived.
        raise LLMUnavailable(
            f"codex CLI returned no agent message"
            f"{': ' + error[:_STDERR_CLIP] if error else ''}"
        )

    tokens_in, tokens_out, cached = _token_counts(usage, text)
    return LLMResponse(
        text=text,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cached_tokens=cached,
        model="",  # the JSONL stream does not report the model id
    )


def _response_from_plain_text(text: str) -> "LLMResponse":
    from core.runtime.llm_provider import LLMResponse

    estimate = max(1, len(text) // _TOKEN_ESTIMATE_DIVISOR)
    return LLMResponse(
        text=text, tokens_in=0, tokens_out=estimate, cached_tokens=0, model=""
    )


def _token_counts(usage: dict | None, text: str) -> tuple[int, int, int]:
    if not isinstance(usage, dict):
        return 0, max(1, len(text) // _TOKEN_ESTIMATE_DIVISOR), 0
    try:
        tokens_in = int(usage.get("input_tokens") or 0)
        tokens_out = int(usage.get("output_tokens") or 0)
        cached = int(usage.get("cached_input_tokens") or 0)
    except (TypeError, ValueError):
        return 0, max(1, len(text) // _TOKEN_ESTIMATE_DIVISOR), 0
    if tokens_in == 0 and tokens_out == 0:
        return 0, max(1, len(text) // _TOKEN_ESTIMATE_DIVISOR), cached
    return tokens_in, tokens_out, cached
