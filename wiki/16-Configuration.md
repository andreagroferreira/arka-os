# 16 · Configuration

← [Home](Home.md)

ArkaOS is configured through one JSON file, a handful of environment
variables, and the in-session `/arka keys` command. This page covers all
three, with the exact key names and default values sourced from the code.

---

## Main config file

**Path:** `~/.arkaos/config.json`

The installer creates this file with defaults. Edit it by hand or via
`/arka update` — it survives updates.

### LLM provider

```json
{
  "llm": {
    "provider": "subagent"
  }
}
```

| Value | How calls are made | Notes |
|---|---|---|
| `"subagent"` | Headless CLI of the active runtime | Default. Uses `claude -p`, `gemini -p`, etc. |
| `"anthropic-direct"` | Anthropic SDK | Model set by `ANTHROPIC_MODEL` env var; no code default |
| `"ollama"` | Local Ollama server | Requires Ollama running locally |
| `"stub"` | Template synthesiser | Tests only; produces structured output without an LLM call |

Fallback chain: `subagent → anthropic-direct → stub`. The chain never raises —
if `subagent` is unavailable, it falls through silently.

### Synapse feature flags

```json
{
  "synapse": {
    "l25KbContext": true
  }
}
```

| Key | Default | What it controls |
|---|---|---|
| `synapse.l25KbContext` | `true` | Enables Synapse L2.5 — semantic search of the Obsidian vault injected into every prompt before the model starts planning. Disable for debugging; see also `ARKA_BYPASS_L25`. |

### Hook feature flags

```json
{
  "hooks": {
    "hardEnforcement": true,
    "kbFirst": false
  }
}
```

| Key | Default | What it controls |
|---|---|---|
| `hooks.hardEnforcement` | `true` | Gates `Write`, `Edit`, `MultiEdit`, and `Task` tool calls behind a `PreToolUse` hook that requires a `[arka:routing]` or `[arka:trivial]` marker in the recent assistant messages. When `false`, violations are logged but not blocked. Has no effect on Cursor (no `PreToolUse` hook support). |
| `hooks.kbFirst` | `false` | Research gate: on the first external research attempt (`Context7`, `WebSearch`, `WebFetch`, `Firecrawl`) without a prior Obsidian query, emits a nudge listing top 3 vault hits and allows the call; on the second attempt in the same turn, denies. Dormant at `false` until you enable it. |

---

## Kill switches (environment variables)

Kill switches disable specific subsystems for one invocation. They are
respected everywhere in the codebase and are listed in the enforcement
telemetry when used.

| Variable | Set to | Effect |
|---|---|---|
| `ARKA_BYPASS_FLOW` | `1` | Disables the `PreToolUse` flow enforcer for the current invocation. The `[arka:routing]` marker requirement is skipped. Intended for installer and `/arka update` internal calls. Usage is recorded in enforcement telemetry. |
| `ARKA_BYPASS_L25` | `1` | Disables Synapse L2.5 KB injection for the current invocation. Useful when diagnosing slow Synapse warm-up or when the vault is not available. |
| `ARKA_BYPASS_KB_FIRST` | `1` | Disables the research gate even when `hooks.kbFirst` is `true`. Audited — every bypass is recorded with the optional `ARKA_BYPASS_KB_FIRST_REASON` value. |

Usage:

```bash
ARKA_BYPASS_FLOW=1 claude  # Open Claude Code without flow enforcement this session
ARKA_BYPASS_L25=1 claude   # Open without Synapse L2.5 KB injection
```

---

## API key management

Keys are stored in `~/.arkaos/keys.json` with `600` permissions (owner read/write
only). They are also resolved from environment variables at call time — if an
environment variable is set, it takes priority over the stored value.

### Managing keys

```bash
npx arkaos keys              # Interactive key manager (terminal)
/arka keys                   # Same, inside an AI session
```

### Keys stored

| Environment variable | Provider | Used for |
|---|---|---|
| `OPENAI_API_KEY` | OpenAI | Whisper transcription, embeddings |
| `GOOGLE_API_KEY` | Google | Gemini API, Google Cloud AI |
| `FAL_API_KEY` | fal.ai | Image generation, video generation |

### Setting a key manually

```bash
npx arkaos keys set OPENAI_API_KEY sk-proj-...
npx arkaos keys set GOOGLE_API_KEY AIza...
npx arkaos keys list
```

Or export in your shell profile to skip persistent storage:

```bash
export OPENAI_API_KEY=sk-proj-...
```

---

## Hook configuration

Hooks are configured in `~/.claude/settings.json` (Claude Code) or the
equivalent settings file for other runtimes. The installer writes this
automatically. The template lives at `config/settings-template.json`.

| Hook | Timeout | Purpose |
|---|---|---|
| `SessionStart` | 5 s | Evidence-flow contract injection, reorganization auto-trigger |
| `UserPromptSubmit` | 10 s | Synapse context injection, workflow-required tag, token hygiene |
| `PostToolUse` | 5 s | Error pattern tracking, budget accounting |
| `PreCompact` | 30 s | Session digest save, agent memory preservation |
| `CwdChanged` | 5 s | Project context reload on directory change |

The `UserPromptSubmit` budget is 10 seconds. Hooks must exit 0 and never
block execution — suggestions from the token hygiene check are advisory only.

---

## Project-level config (`.arkaos.json`)

Running `npx arkaos init` in a project directory creates `.arkaos.json` with
auto-detected stack information:

```json
{
  "stack": "laravel",
  "language": "php",
  "version": "11.x",
  "runtime": "claude-code"
}
```

This file is read by Synapse L3 (Project layer) on every prompt, so the agent
always knows what framework and language version it is working with.

---

## Telemetry files

ArkaOS writes operational data to `~/.arkaos/`:

| File | Contents |
|---|---|
| `telemetry/llm-cost.jsonl` | One record per LLM call: tokens, cache hits, estimated cost in USD. Append-only. Used by `/arka costs`. |
| `telemetry/enforcement.jsonl` | One record per tool-call gate decision: tool name, reason, allowed/blocked. Used by `/arka enforcement`. |
| `telemetry/compliance.jsonl` | One record per stop-hook check: closing marker, `[arka:meta]` tag, KB citation, sycophancy verdict. Used by `/arka compliance`. |
| `reorganize-proposals/<date>.md` | Daily reorganization proposals from `/arka reorganize`. Never auto-applied. |
| `plans/` | Plans saved during Gate 2 (PLAN) of the evidence flow. |
| `workflow-state.json` | Gate checkpoints written by the Stop hook (`core/workflow/gate_checkpoint.py`): current gate, per-gate status, Gate-3 test evidence. A per-session copy lives under `sessions/<id>/` and powers resume after interruptions. |

---

Related: [08 · Multi-Runtime](08-Multi-Runtime.md) (LLM provider and runtime
selection), [05 · Commands Reference](05-Commands-Reference.md) (the `/arka keys`
and `/arka costs` commands).
