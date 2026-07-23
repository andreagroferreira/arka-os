"""OpenCode runtime adapter (Foundation PR-6 + headless follow-up).

OpenCode (opencode.ai) — open-source terminal AI coding agent with
native agents (markdown, ``~/.config/opencode/agents/``), custom
commands (``commands/``), MCP servers (``opencode.json``), AGENTS.md
instructions, and a TypeScript plugin system (``plugins/``). The
installer adapter (installer/adapters/opencode.js) deploys the
generated harness bundle onto those surfaces, including
``plugins/arka.ts``, which bridges OpenCode events into
``core.runtime.opencode_hooks`` (kb-first research gate, frontend
gate, MCP telemetry, stop-hook compliance, compaction context).

Headless invocation (live-verified against the installed binary,
opencode 1.18.4, ``opencode run --help`` + a real probe, 2026-07-23):

    opencode run --format json "<prompt>"

``--format json`` prints JSONL events to stdout. Live-verified shapes:

    {"type":"step_start", "sessionID":"...", "part":{...}}
    {"type":"text","part":{"type":"text","text":"ok",...}}
    {"type":"step_finish","part":{"reason":"stop","tokens":
        {"total":N,"input":N,"output":N,"reasoning":N,
         "cache":{"write":N,"read":N}},"cost":X}}
    {"type":"error","error":{"name":"...","data":{"message":"..."}}}

The error event fires with exit 1 when the user's DEFAULT model/provider
is broken (observed live) — headless_complete surfaces that as
LLMUnavailable with the event message. When no JSONL parses at all,
stdout is treated as raw text with a ``len(text) // 4`` token estimate
(same fallback as the Codex/Gemini adapters). stdin is closed explicitly
(codex precedent — a piped stdin must never leak into the prompt).
"""

import json
import shutil
import subprocess
from os.path import expanduser
from pathlib import Path
from typing import TYPE_CHECKING

from core.runtime.base import AgentContext, AgentResult, RuntimeAdapter, RuntimeConfig

if TYPE_CHECKING:
    from core.runtime.llm_provider import LLMResponse


# `opencode run` is a full agent turn (session bootstrap + provider
# round-trip) — mirror the Codex budget, not the tighter Gemini one.
_TIMEOUT_SECONDS = 120
_TOKEN_ESTIMATE_DIVISOR = 4  # Rough chars-per-token heuristic.
_STDERR_CLIP = 200


class OpenCodeAdapter(RuntimeAdapter):
    """Adapter for OpenCode (terminal AI coding agent)."""

    def get_config(self) -> RuntimeConfig:
        home = Path(expanduser("~"))
        config_dir = home / ".config" / "opencode"
        return RuntimeConfig(
            id="opencode",
            name="OpenCode",
            config_dir=config_dir,
            skills_dir=config_dir / "commands",
            settings_file=config_dir / "opencode.json",
            supports_hooks=(config_dir / "plugins" / "arka.ts").exists(),
            supports_subagents=True,
            supports_mcp=True,
            max_context_tokens=200_000,
        )

    def capabilities(self) -> dict[str, bool]:
        plugin = (
            Path(expanduser("~")) / ".config" / "opencode" / "plugins" / "arka.ts"
        )
        return {
            "agent_dispatch": False,  # native agents exist; no ArkaOS wiring yet
            "headless": True,         # `opencode run` live-verified 2026-07-23
            "file_ops": True,         # terminal agent edits files natively
            # plugins/arka.ts (deployed by the installer adapter) bridges
            # prompt/pre_tool/post_tool/idle/compact events into
            # core.runtime.opencode_hooks — kb-first, frontend gate,
            # telemetry, compliance. True only when actually deployed.
            "hooks": plugin.exists(),
        }

    def inject_context(self, layers: dict[str, str]) -> str:
        """OpenCode reads AGENTS.md and `instructions` config entries."""
        parts = []
        for name, content in layers.items():
            parts.append(f"## {name}\n{content}")
        return "\n\n".join(parts)

    def dispatch_agent(self, context: AgentContext) -> AgentResult:
        """OpenCode selects its own (deployed arka-*) agents internally."""
        return AgentResult(
            agent_id=context.agent_id,
            status="dispatched",
            output=f"Agent {context.agent_id} dispatched via OpenCode",
            metadata={"runtime": "opencode"},
        )

    def spawn_subagent(self, context: AgentContext) -> AgentResult:
        """Native subagents exist (mode: subagent) but ArkaOS cannot
        target them programmatically yet — honest unsupported."""
        return AgentResult(
            agent_id=context.agent_id,
            status="unsupported",
            output=(
                "OpenCode subagents are selected by OpenCode itself; "
                "programmatic ArkaOS dispatch is not wired yet."
            ),
            metadata={"runtime": "opencode", "fallback": "single-agent"},
        )

    def read_file(self, path: str) -> str:
        raise NotImplementedError("Use OpenCode's native file read")

    def write_file(self, path: str, content: str) -> None:
        raise NotImplementedError("Use OpenCode's native file write")

    def edit_file(self, path: str, old: str, new: str) -> None:
        raise NotImplementedError("Use OpenCode's native file edit")

    def execute_command(self, command: str, timeout: int = 120) -> tuple[str, int]:
        raise NotImplementedError("Use OpenCode's native shell tool")

    def search_files(self, pattern: str, path: str = ".") -> list[str]:
        raise NotImplementedError("Use OpenCode's native file search")

    def search_content(self, pattern: str, path: str = ".") -> list[str]:
        raise NotImplementedError("Use OpenCode's native content search")

    def headless_supported(self) -> bool:
        return shutil.which("opencode") is not None

    def headless_complete(
        self,
        prompt: str,
        *,
        max_tokens: int = 2000,
        system: str = "",
    ) -> "LLMResponse":
        """One-shot completion via `opencode run --format json`.

        Verified against opencode 1.18.4 (live probe, 2026-07-23). The
        model comes from the user's opencode config; a broken default
        provider surfaces as an error event -> LLMUnavailable. Raises
        LLMUnavailable on non-zero exit or timeout.
        """
        from core.runtime.llm_provider import LLMUnavailable

        binary = shutil.which("opencode")
        if binary is None:
            raise NotImplementedError(
                "opencode CLI not found on PATH — install OpenCode to "
                "enable headless completion."
            )
        effective_prompt = _merge_system_prompt(prompt, system)
        cmd = [binary, "run", "--format", "json", effective_prompt]
        proc = _run_opencode_cli(cmd)
        if proc.returncode != 0:
            # The error event carries the actionable message (observed
            # live with a broken default model); stderr is often empty.
            event_message = _first_error_message(proc.stdout)
            detail = event_message or proc.stderr.strip()[:_STDERR_CLIP]
            raise LLMUnavailable(
                f"opencode run exited {proc.returncode}: {detail}"
            )
        return _parse_opencode_output(proc.stdout)


def _merge_system_prompt(prompt: str, system: str) -> str:
    # `opencode run` takes a single message; prepend the system text so
    # downstream behaviour matches the other adapters.
    if not system:
        return prompt
    return f"{system}\n\n---\n\n{prompt}"


def _run_opencode_cli(cmd: list[str]) -> subprocess.CompletedProcess:
    from core.runtime.llm_provider import LLMUnavailable

    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_TIMEOUT_SECONDS,
            check=False,
            # codex precedent: piped stdin must never leak into the run.
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired as err:
        raise LLMUnavailable(
            f"opencode run timed out after {_TIMEOUT_SECONDS}s"
        ) from err


def _iter_events(stdout: str):
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            yield json.loads(line)
        except (ValueError, TypeError):
            continue


def _first_error_message(stdout: str) -> str:
    for event in _iter_events(stdout):
        if event.get("type") == "error":
            data = (event.get("error") or {}).get("data") or {}
            message = data.get("message") or (event.get("error") or {}).get("name")
            if message:
                return str(message)[:_STDERR_CLIP]
    return ""


def _parse_opencode_output(stdout: str) -> "LLMResponse":
    """Parse the live-verified JSONL stream (see module docstring)."""
    from core.runtime.llm_provider import LLMResponse, LLMUnavailable

    texts: list[str] = []
    tokens_in = 0
    tokens_out = 0
    cached = 0
    saw_event = False
    for event in _iter_events(stdout):
        saw_event = True
        kind = event.get("type")
        part = event.get("part") or {}
        if kind == "text" and part.get("type") == "text":
            texts.append(str(part.get("text", "")))
        elif kind == "step_finish":
            tokens = part.get("tokens") or {}
            tokens_in += int(tokens.get("input") or 0)
            tokens_out += int(tokens.get("output") or 0)
            cached += int((tokens.get("cache") or {}).get("read") or 0)
        elif kind == "error":
            message = _first_error_message(stdout) or "unknown opencode error"
            raise LLMUnavailable(f"opencode run error event: {message}")
    if saw_event:
        return LLMResponse(
            text="".join(texts),
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cached_tokens=cached,
            model="",  # events carry no model id (verified 1.18.4)
        )
    # No JSONL parsed — degrade to raw text (codex/gemini fallback).
    raw = stdout.strip()
    return LLMResponse(
        text=raw,
        tokens_in=0,
        tokens_out=max(1, len(raw) // _TOKEN_ESTIMATE_DIVISOR) if raw else 0,
        cached_tokens=0,
        model="",
    )
