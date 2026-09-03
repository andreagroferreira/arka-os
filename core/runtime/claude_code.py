"""Claude Code runtime adapter.

Claude Code is the primary and most capable runtime for ArkaOS.
It supports hooks, subagents (Agent tool), MCP servers, and worktrees.
"""

import json
import os
import re
import shutil
import subprocess
from os.path import expanduser
from pathlib import Path
from typing import TYPE_CHECKING, Any

from core.runtime.base import AgentContext, AgentResult, RuntimeAdapter, RuntimeConfig

if TYPE_CHECKING:
    from core.runtime.llm_provider import LLMResponse


# Claude Code versions that introduced each behaviour ArkaOS gates on.
# Every entry is a changelog "Added"/"Changed" line, verified 2026-09-03
# against code.claude.com/docs/en/changelog. ``supports_feature`` compares
# the detected binary against this table; the installer doctor pins its
# floor to the highest value here (tests/python/test_runtime_claude_code.py).
FEATURE_FLOORS: dict[str, tuple[int, int, int]] = {
    # `fallbackModel` setting — up to three models tried in order
    "fallback_model_setting": (2, 1, 166),
    # subagent forking on by default; interactive spawns run in the background
    "fork_default": (2, 1, 232),
    # TaskCreate/Get/Update/List and TodoWrite removed on frontier models
    "todo_tools_removed": (2, 1, 233),
    # a `{…}` stdout that is not valid JSON is a hook error, not plain text
    "hook_json_strict": (2, 1, 248),
    # PreModelSwitch / PostModelSwitch hook events
    "pre_model_switch": (2, 1, 251),
    # claude-fable-5-1 is the default `fable` model
    "fable_5_1": (2, 1, 257),
    # CLAUDE_CODE_SUBAGENT_MODEL_FORCE
    "subagent_model_force": (2, 1, 257),
    # permissions.blockReadsOutsideWorkingDirectories
    "block_reads_outside_cwd": (2, 1, 257),
}

# Todo/task-tracking tools not offered in an interactive frontier session
# (changelog 2.1.233; the 2.1.259 binary gates exactly these five on its
# own family list opus ≥ 4.8, sonnet ≥ 5, fable ≥ 5, mythos ≥ 5, reading
# the main-loop model). Re-enabled by CLAUDE_CODE_ENABLE_TODO_TOOLS, the
# host's todoToolsOptIn, a bg session, or the tengu_rosy_wren flag — none
# of which the sessions ArkaOS runs use. An agent that declares one of
# them in `tools:` names a tool it is not handed there (Runtime Sync PR4).
FRONTIER_RETIRED_TOOLS: frozenset[str] = frozenset({
    "TodoWrite", "TaskCreate", "TaskGet", "TaskUpdate", "TaskList",
})

# Built-in tool names Claude Code 2.1.259 knows, for validating an agent's
# `tools:` frontmatter (tests/python/test_agent_tools_resolve.py). Three
# sources, read 2026-09-03: the binary's BUILTIN_TOOL_NAMES policy list,
# the binary's built-in tool registry, and the tool set a 2.1.259 session
# exposes. Retired names stay in — they are still built-ins on older
# models — and FRONTIER_RETIRED_TOOLS is the separate, gating set.
# `mcp__*` names are per-server and validated by prefix, not listed here.
KNOWN_BUILTIN_TOOLS: frozenset[str] = frozenset({
    # file and shell
    "Bash", "BashOutput", "KillShell", "PowerShell", "Tmux", "Monitor", "REPL",
    "JavaScript", "Read", "Edit", "MultiEdit", "Write", "NotebookEdit",
    "NotebookRead", "Glob", "Grep", "LS", "LSP", "Snip",
    # todo/task tracking (retired on frontier models) + background tasks
    "TodoWrite", "TaskCreate", "TaskGet", "TaskUpdate", "TaskList",
    "TaskStop", "TaskOutput",
    # agents, skills, planning
    "Agent", "Task", "Skill", "Workflow", "ToolSearch", "AskUserQuestion",
    "EnterPlanMode", "ExitPlanMode", "EnterWorktree", "ExitWorktree",
    # web and MCP resources
    "WebFetch", "WebSearch", "WebBrowser", "ReadMcpResourceTool",
    "ReadMcpResourceDirTool", "ListMcpResourcesTool", "RefreshMcpTools",
    "SearchMcpRegistry", "ListConnectors", "SuggestConnectors",
    # scheduling, sessions, messaging
    "CronCreate", "CronDelete", "CronList", "ScheduleWakeup", "RemoteTrigger",
    "SendMessage", "SendUserMessage", "ListAgents", "ListPeers", "Brief",
    "PushNotification", "SendFeedback", "SendFile", "SendUserFile",
    "SubscribePR", "EndConversation",
    # artifacts, design, review, plugins
    "Artifact", "DesignSync", "ClaudeDesign", "Projects", "ConnectGitHub",
    "ReportFindings", "ObserverReport", "propose_skills",
    "SuggestPluginInstall", "SuggestSkills", "ListPlugins", "ListSkills",
    "SearchPlugins", "SearchSkills",
})

# Truths no version changes; everything else falls through to the config.
_STATIC_FEATURES: dict[str, bool] = {
    "parallel_agents": True,
    "worktrees": True,
}

# Operator/test override, read on every call (never cached): pin the
# version a gateway build reports, or simulate an older binary in tests.
VERSION_ENV = "ARKA_CLAUDE_VERSION"
_VERSION_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")
_PROBE_TIMEOUT_SECONDS = 10
# The `fallbackModel` chain ArkaOS seeds into ~/.claude/settings.json and
# hands the scheduler (Runtime Sync PR3). Tried in order when the primary
# model is overloaded or unavailable; the runtime caps chains at three after
# de-duplication. installer/fallback-model.js carries the same list —
# tests/python/test_scheduler_daemon.py pins the two to each other.
DEFAULT_FALLBACK_MODELS: tuple[str, ...] = ("claude-opus-5", "claude-sonnet-5")

# Cache for the `claude --version` probe, keyed by the binary probed ("" =
# the PATH lookup). In-memory only: a disk cache would let one session
# answer for the next.
_probe_cache: dict[str, tuple[int, int, int] | None] = {}


def parse_version(text: str | None) -> tuple[int, int, int] | None:
    """The first dotted triple in ``text`` (``"2.1.259 (Claude Code)"``)."""
    match = _VERSION_RE.search(text or "")
    if match is None:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def _probe_binary(binary: str | None = None) -> tuple[int, int, int] | None:
    binary = binary or shutil.which("claude")
    if not binary:
        return None
    try:
        result = subprocess.run(
            [binary, "--version"],
            capture_output=True,
            text=True,
            timeout=_PROBE_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    stdout = result.stdout if isinstance(result.stdout, str) else ""
    stderr = result.stderr if isinstance(result.stderr, str) else ""
    return parse_version(stdout) or parse_version(stderr)


def detect_claude_code_version(binary: str | None = None) -> tuple[int, int, int] | None:
    """The Claude Code version on this machine, or None when unknowable.

    ``ARKA_CLAUDE_VERSION`` wins when set to a non-blank value and is read
    on every call (a blank value counts as unset). ``binary`` names the
    executable to probe when the caller resolved it itself — a daemon
    under launchd has no PATH worth asking; None means the PATH lookup.
    Each binary is probed once per process and cached in memory only.
    """
    override = os.environ.get(VERSION_ENV)
    if override is not None and override.strip():
        return parse_version(override)
    key = binary or ""
    if key not in _probe_cache:
        _probe_cache[key] = _probe_binary(binary)
    return _probe_cache[key]


def reset_version_cache() -> None:
    """Forget the probed version (tests, or after an in-place upgrade)."""
    _probe_cache.clear()


class ClaudeCodeAdapter(RuntimeAdapter):
    """Adapter for Anthropic's Claude Code CLI."""

    def get_config(self) -> RuntimeConfig:
        home = Path(expanduser("~"))
        return RuntimeConfig(
            id="claude-code",
            name="Claude Code",
            config_dir=home / ".claude",
            skills_dir=home / ".claude" / "skills",
            settings_file=home / ".claude" / "settings.json",
            supports_hooks=True,
            supports_subagents=True,
            supports_mcp=True,
            max_context_tokens=1_000_000,
        )

    def capabilities(self) -> dict[str, bool]:
        return {
            "agent_dispatch": True,   # Agent tool — real subagent dispatch
            "headless": True,         # claude -p
            "file_ops": True,         # native Read/Write/Edit tools
            "hooks": True,            # 11 registrations on 10 events — core/harness/spec.py
        }

    def inject_context(self, layers: dict[str, str]) -> str:
        """Claude Code receives context via UserPromptSubmit hook.

        The hook script concatenates all layers into a single
        additionalContext string that Claude sees in system-reminder tags.
        """
        parts = []
        for name, content in layers.items():
            parts.append(f"[{name}] {content}")
        return " ".join(parts)

    def dispatch_agent(self, context: AgentContext) -> AgentResult:
        """In Claude Code, agents are dispatched via the Agent tool.

        The orchestrator provides the agent type via subagent_type parameter.
        Claude Code handles the actual execution.
        """
        # This is a specification of intent — actual execution happens
        # through Claude Code's native Agent tool
        return AgentResult(
            agent_id=context.agent_id,
            status="dispatched",
            output=f"Agent {context.agent_id} dispatched for: {context.task}",
            metadata={
                "runtime": "claude-code",
                "subagent_type": context.agent_id,
                "department": context.department,
            },
        )

    def spawn_subagent(self, context: AgentContext) -> AgentResult:
        """Spawn a fresh Claude Code subagent.

        Uses the Agent tool with a complete task description.
        Each subagent gets a fresh 1M token context window.
        """
        return AgentResult(
            agent_id=context.agent_id,
            status="dispatched",
            output=f"Subagent {context.agent_id} spawned for: {context.task}",
            metadata={
                "runtime": "claude-code",
                "pattern": "subagent",
                "fresh_context": True,
            },
        )

    def read_file(self, path: str) -> str:
        """Claude Code uses the Read tool natively."""
        # This maps to the Read tool in Claude Code
        raise NotImplementedError("Use Claude Code's native Read tool")

    def write_file(self, path: str, content: str) -> None:
        """Claude Code uses the Write tool natively."""
        raise NotImplementedError("Use Claude Code's native Write tool")

    def edit_file(self, path: str, old: str, new: str) -> None:
        """Claude Code uses the Edit tool natively."""
        raise NotImplementedError("Use Claude Code's native Edit tool")

    def execute_command(self, command: str, timeout: int = 120) -> tuple[str, int]:
        """Claude Code uses the Bash tool natively."""
        raise NotImplementedError("Use Claude Code's native Bash tool")

    def search_files(self, pattern: str, path: str = ".") -> list[str]:
        """Claude Code uses the Glob tool natively."""
        raise NotImplementedError("Use Claude Code's native Glob tool")

    def search_content(self, pattern: str, path: str = ".") -> list[str]:
        """Claude Code uses the Grep tool natively."""
        raise NotImplementedError("Use Claude Code's native Grep tool")

    def supports_feature(self, feature: str) -> bool:
        """Version-gated where the runtime changed; config-backed or static otherwise.

        A feature in ``FEATURE_FLOORS`` is supported only when the detected
        binary meets its floor; an unknown version answers the conservative
        False and never raises. ``hooks``/``subagents``/``mcp`` come from
        the config; ``parallel_agents``/``worktrees`` are static truths.
        """
        floor = FEATURE_FLOORS.get(feature)
        if floor is not None:
            version = detect_claude_code_version()
            return version is not None and version >= floor
        if feature in _STATIC_FEATURES:
            return _STATIC_FEATURES[feature]
        return super().supports_feature(feature)

    def headless_supported(self) -> bool:
        return shutil.which("claude") is not None

    def headless_complete(
        self,
        prompt: str,
        *,
        max_tokens: int = 2000,
        system: str = "",
    ) -> "LLMResponse":
        from core.runtime.llm_provider import LLMUnavailable

        binary = shutil.which("claude")
        if binary is None:
            raise NotImplementedError(
                "claude CLI not found on PATH — install Claude Code to enable "
                "headless completion via this adapter."
            )
        cmd = [binary, "-p", prompt, "--output-format", "json"]
        if system:
            cmd.extend(["--append-system-prompt", system])
        proc = _run_claude_cli(cmd)
        if proc.returncode != 0:
            raise LLMUnavailable(
                f"claude CLI exited {proc.returncode}: {proc.stderr.strip()[:200]}"
            )
        return _parse_claude_cli_output(proc.stdout)


def _run_claude_cli(cmd: list[str]) -> subprocess.CompletedProcess:
    from core.runtime.llm_provider import LLMUnavailable

    # On Windows the caller is often a console-less pythonw.exe (scheduler
    # daemon, dreaming). Spawning the console-subsystem claude.exe without
    # this flag allocates a visible console window per call; closing it kills
    # the child with 0xC000013A and the cluster is silently skipped.
    # CREATE_NO_WINDOW is absent on POSIX, where 0 means "no extra flags".
    no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        return subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=60, check=False,
            creationflags=no_window
        )
    except subprocess.TimeoutExpired as exc:
        raise LLMUnavailable("claude CLI timed out after 60s") from exc
    except OSError as exc:
        raise LLMUnavailable(f"claude CLI subprocess failed: {exc}") from exc


def _model_from_payload(payload: dict[str, Any]) -> str:
    """The model id a `claude -p --output-format json` run actually used.

    The payload carries no top-level ``model`` key (2.1.259 capture in
    tests/python/fixtures/claude_p_output_json_2_1_259.json); the ids live
    under ``modelUsage`` keyed by model, one entry per model the turn
    touched. Pick the entry with the largest input volume, fall back to a
    top-level ``model`` for older or gateway payloads, else "" — which the
    cost recorder then reports as an unpriceable row instead of $0.00.
    """
    usage = payload.get("modelUsage")
    if isinstance(usage, dict) and usage:
        def _volume(item: tuple[str, object]) -> int:
            entry = item[1] if isinstance(item[1], dict) else {}
            return sum(
                int(entry.get(k) or 0)
                for k in ("inputTokens", "cacheReadInputTokens", "cacheCreationInputTokens")
            )
        model, _ = max(usage.items(), key=_volume)
        if model:
            return str(model)
    return str(payload.get("model") or "")


def _parse_claude_cli_output(stdout: str) -> "LLMResponse":
    from core.runtime.llm_provider import LLMResponse

    payload = json.loads(stdout) if stdout.strip() else {}
    text = str(payload.get("result") or payload.get("response") or "")
    usage = payload.get("usage") or {}
    tokens_in = int(usage.get("input_tokens") or 0)
    tokens_out = int(usage.get("output_tokens") or 0)
    cache_read = int(usage.get("cache_read_input_tokens") or 0)
    cache_write = int(usage.get("cache_creation_input_tokens") or 0)
    total_input = tokens_in + cache_read + cache_write
    model = _model_from_payload(payload)
    return LLMResponse(
        text=text,
        tokens_in=total_input,
        tokens_out=tokens_out,
        cached_tokens=cache_read,
        model=model,
    )


# Backward compatibility alias — tests and external importers that used
# the old helper name continue to work without modification.
_parse_claude_json = _parse_claude_cli_output
