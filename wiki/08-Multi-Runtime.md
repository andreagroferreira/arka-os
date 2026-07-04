# 08 · Multi-Runtime

← [Intelligence Loop](07-Intelligence-Loop.md) · [Home](Home.md) · Next: [Knowledge Base →](09-Knowledge-Base.md)

ArkaOS runs on four AI coding tools. Every department, every skill, and every
workflow works regardless of which runtime you use. The only things that differ
are how hooks attach and which native capabilities are available.

---

## Runtime overview

| Runtime | Status | Key capabilities |
|---|---|---|
| **Claude Code** | Primary | Hooks (5 lifecycle points), subagents, MCP, 1 M context |
| **Gemini CLI** | Supported | Subagents, MCP, 1 M context, headless via `gemini -p` |
| **Codex CLI** | Supported | Subagents, sandboxed execution |
| **Cursor** | Supported | Agent mode, MCP |

---

## Claude Code (primary runtime)

Claude Code is the primary target. It exposes the most integration points.

### Hooks

ArkaOS installs five lifecycle hooks into `~/.claude/settings.json`:

| Hook | Fires | What it does |
|---|---|---|
| `SessionStart` | On session open | Injects `[ARKA:EVIDENCE-FLOW]`; runs the reorganization auto-trigger if today's proposal is missing |
| `Stop` | After every assistant turn | Compliance checks (closing marker, `[arka:meta]`, KB citation, sycophancy) + persists `[arka:gate:N]` transitions via `core/workflow/gate_checkpoint.py` for structured resume |
| `UserPromptSubmit` | Before every prompt | Calls `scripts/synapse-bridge.py` — runs all 12 Synapse layers and injects the resulting context string; adds `[ARKA:WORKFLOW-REQUIRED]` on creation/implementation verbs; runs the 4-check token hygiene pass |
| `PostToolUse` | After every tool call | Tracks error patterns to `gotchas.json`; records tool usage for budget accounting |
| `PreCompact` | Before context compaction | Saves a session digest to Obsidian; preserves agent memory and task state |
| `CwdChanged` | On directory change | Reloads project context (`CLAUDE.md`, `.arkaos.json`, stack detection) |

A `PreToolUse` gate on the `Task` tool handles agent provisioning. When
`hooks.hardEnforcement` is `true`, a second `PreToolUse` hook blocks `Write`,
`Edit`, `MultiEdit`, and `Task` when no `[arka:routing]` or `[arka:trivial]`
marker is present in the recent assistant messages.

### Subagents

ArkaOS dispatches subagents — fresh Claude Code instances per task — via the
`Task` tool. Each subagent receives a compact handoff (~82 word-tokens for a
representative task — see [Benchmarks](11-Benchmarks.md)) that includes the
agent role, the task description, constraints, and the relevant project
context. This keeps each subagent's context clean and avoids state accumulation
across tasks.

### MCP

Claude Code's MCP support lets ArkaOS tools like the Obsidian connector,
Context7, Firecrawl, and the knowledge vector store run as first-class tools
inside the session. The installer writes per-project `.mcp.json` files during
`/arka update`.

### 1 M context

The extended context window is used by the evidence flow to hold large specs,
full test suites, and multi-file diffs without compaction. The `PreCompact`
hook fires when compaction is unavoidable, preserving continuity.

---

## Gemini CLI

Gemini CLI is a fully supported runtime. It is invoked headlessly for
cognitive-layer tasks (auto-documentor, Dreaming, Research) via:

```bash
gemini -p "<prompt>" --output-format json
```

The adapter at `core/runtime/gemini_cli.py` wraps this invocation and surfaces
the same `LLMResponse` dataclass used by all providers. Skills and workflows
work without modification — the runtime choice is transparent to department
logic.

Gemini CLI also supports MCP and a 1 M context window, making it a capable
primary runtime for teams that prefer it.

---

## Codex CLI

The Codex CLI adapter (`core/runtime/codex.py`) runs ArkaOS in a sandboxed
execution environment. Subagents work, but the sandbox limits some shell
operations. Suitable for teams where network isolation is a requirement.

---

## Cursor

The Cursor adapter (`core/runtime/cursor.py`) uses Cursor's native agent mode
and injects ArkaOS rules via `.cursor/rules`. MCP is supported, so Obsidian,
Context7, and the knowledge vector store connect normally.

The `PreToolUse` enforcement gate is not available in Cursor's hook model;
`hooks.hardEnforcement` has no effect there. The 4-gate evidence flow still runs — it
just relies on the model following the injected instructions rather than a hard
code gate.

---

## LLM wiring — zero model hardcoding

The cognitive layer (auto-documentor, Dreaming, Research) makes LLM calls that
are fully runtime-agnostic. There is no hardcoded model name anywhere in the
codebase. The active provider is resolved at call time from
`~/.arkaos/config.json` under the key `llm.provider`:

| Provider | How the call is made |
|---|---|
| `subagent` (default) | Headless CLI of the active runtime (`claude -p`, `gemini -p …`) |
| `anthropic-direct` | Anthropic SDK; model is read from the `ANTHROPIC_MODEL` env var — no code default |
| `ollama` | Local Ollama server; model configured in `config.json` |
| `stub` | Template synthesiser — used in tests and when no real provider is available |

The fallback chain is `subagent → anthropic-direct → stub` and never raises.
This means ArkaOS keeps working even if the headless CLI is unavailable — it
falls back to a direct API call, then to a structured template.

```json
// ~/.arkaos/config.json — switch to Anthropic direct
{"llm": {"provider": "anthropic-direct"}}
```

Prompt caching is on by default for the `anthropic-direct` provider
(5-minute TTL, `cache_control: ephemeral` on the system block).

---

## Installing for a specific runtime

```bash
npx arkaos install --runtime claude-code
npx arkaos install --runtime gemini
npx arkaos install --runtime codex
npx arkaos install --runtime cursor
```

If you omit `--runtime`, the installer auto-detects the runtime based on what
is available on your `PATH` and in your home directory.

---

## Adapter source files

| File | Runtime |
|---|---|
| `core/runtime/claude_code.py` | Claude Code (hooks, CLAUDE.md injection) |
| `core/runtime/gemini_cli.py` | Gemini CLI (headless + MCP) |
| `core/runtime/codex_cli.py` | Codex CLI (sandboxed) |
| `core/runtime/cursor.py` | Cursor (rules injection) |
| `core/runtime/llm_provider.py` | LLM provider resolution + fallback chain |
| `core/runtime/subagent.py` | Subagent dispatch (~82 word-token handoff) |
| `core/runtime/ollama_provider.py` | Ollama local provider |

---

Related: [05 · Commands Reference](05-Commands-Reference.md) (the commands that run
across all runtimes), [16 · Configuration](16-Configuration.md) (feature flags
and kill switches, including `llm.provider`).
