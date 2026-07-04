# 08 · Multi-Runtime

← [Intelligence Loop](07-Intelligence-Loop.md) · [Home](Home.md) · Next: [Knowledge Base →](09-Knowledge-Base.md)

ArkaOS targets four AI coding tools, but they are NOT at parity — and this
page is honest about it. Claude Code is the first-class runtime (hooks,
agent dispatch, enforcement gates). The other three run ArkaOS knowledge
and skills with a reduced feature set.

The single source of truth is the adapter capabilities matrix:

```bash
python -m core.runtime.capabilities_cli          # table
python -m core.runtime.capabilities_cli --json   # machine-readable
```

---

## Runtime support matrix (honest)

| Runtime | Status | agent dispatch | headless | file ops | hooks |
|---|---|---|---|---|---|
| **Claude Code** | First-class | ✅ Agent tool | ✅ `claude -p` | ✅ | ✅ 5 lifecycle points |
| **Gemini CLI** | Headless | ❌ | ✅ `gemini -p --output-format json` | ✅ interactive | ❌ |
| **Codex CLI** | Headless (new, v4.1) | ❌ | ✅ `codex exec --json` | ✅ sandboxed | ❌ |
| **Cursor** | Single-agent / experimental | ❌ | ❌ | ✅ IDE agent mode | ❌ |

What the columns mean: *agent dispatch* — the runtime can spawn ArkaOS
agents/subagents natively; *headless* — the adapter implements a real
one-shot CLI completion (used by the cognitive layer); *file ops* — the
runtime edits files natively when driven interactively; *hooks* — ArkaOS
enforcement (PreToolUse/Stop gates) can attach. Squad orchestration,
quality gates, and the evidence flow are only hard-enforced on Claude
Code; elsewhere they rely on injected instructions.

---

## Modern orchestration primitives

How ArkaOS maps to the current Claude Code orchestration surface:

- **Background subagents (default):** squads ARE background subagents —
  leads dispatch specialists via the Agent tool and keep working while
  they run.
- **Agent Teams + SendMessage:** leads may message a running specialist
  via SendMessage (course-correct without a fresh dispatch) where the
  runtime exposes it.
- **Structured outputs for subagent verdicts:** Quality Gate verdicts
  are structured outputs (APPROVED/REJECTED schema, PR-4 v4.1) — no
  regex-parsing of prose verdicts.
- **Workflow / ultracode:** ArkaOS workflow YAMLs play the same role as
  harness-native workflows — phases, gates, and parallelization declared
  declaratively, executed by the runtime that is available.

---

## Claude Code (primary runtime)

Claude Code is the primary target. It exposes the most integration points.

### Hooks

ArkaOS installs five lifecycle hooks into `~/.claude/settings.json`:

| Hook | Fires | What it does |
|---|---|---|
| `SessionStart` | On session open | Injects `[ARKA:EVIDENCE-FLOW]`; runs the reorganization auto-trigger if today's proposal is missing |
| `Stop` | After every assistant turn | Compliance checks (closing marker, `[arka:meta]`, KB citation, sycophancy) + persists `[arka:gate:N]` transitions via `core/workflow/gate_checkpoint.py` for structured resume |
| `UserPromptSubmit` | Before every prompt | Runs all 12 Synapse layers in-process (`core/hooks/user_prompt_submit.py` → `scripts/synapse-bridge.py::run_bridge`) and injects the resulting context string; adds `[ARKA:WORKFLOW-REQUIRED]` on creation/implementation verbs; runs the 4-check token hygiene pass |
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

Gemini CLI is a headless runtime. It is invoked for cognitive-layer tasks
(auto-documentor, Dreaming, Research) via:

```bash
gemini -p "<prompt>" --output-format json
```

The adapter at `core/runtime/gemini_cli.py` wraps this invocation and surfaces
the same `LLMResponse` dataclass used by all providers. MCP and the 1 M
context window are available in interactive use, but there is no hook
lifecycle and no ArkaOS agent dispatch — enforcement is instruction-only.

---

## Codex CLI

Headless support shipped in v4.1 (PR-6). The adapter
(`core/runtime/codex_cli.py`) runs one-shot completions via:

```bash
codex exec --json --skip-git-repo-check --sandbox read-only "<prompt>"
```

verified against codex-cli 0.142.5 (2026-07-04). The JSONL event stream is
parsed defensively (`item.completed`/`agent_message` for text,
`turn.completed`/`usage` for token counts, legacy `msg` shapes accepted,
plain-text fallback). Execution is sandboxed read-only; there are no hooks
and no ArkaOS agent dispatch.

---

## Cursor

Single-agent, experimental. The Cursor adapter (`core/runtime/cursor.py`)
injects ArkaOS rules via `.cursor/rules` and relies on Cursor's native
agent mode. MCP is supported, so Obsidian, Context7, and the knowledge
vector store connect normally — but there is no subagent spawning, no
headless CLI, and no hook model. `hooks.hardEnforcement` has no effect;
the 4-gate evidence flow relies entirely on the model following the
injected instructions rather than a hard code gate.

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
| `core/runtime/claude_code.py` | Claude Code (hooks, agent dispatch, headless) |
| `core/runtime/gemini_cli.py` | Gemini CLI (headless + MCP) |
| `core/runtime/codex_cli.py` | Codex CLI (headless via `codex exec --json`, sandboxed) |
| `core/runtime/cursor.py` | Cursor (rules injection, single-agent) |
| `core/runtime/capabilities_cli.py` | Support matrix CLI (single source of truth) |
| `core/runtime/llm_provider.py` | LLM provider resolution + fallback chain |
| `core/runtime/subagent.py` | Subagent dispatch (~82 word-token handoff) |
| `core/runtime/ollama_provider.py` | Ollama local provider |

---

Related: [05 · Commands Reference](05-Commands-Reference.md) (the commands that run
across all runtimes), [16 · Configuration](16-Configuration.md) (feature flags
and kill switches, including `llm.provider`).
