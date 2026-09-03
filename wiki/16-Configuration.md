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
    "frontendGate": "warn",
    "specialistEnforcement": false,
    "shadowDeny": true,
    "kbFirst": true
  }
}
```

| Key | Default | What it controls |
|---|---|---|
| `hooks.hardEnforcement` | `true` | Gates `Write`, `Edit`, `NotebookEdit`, `Task`, and `Skill` tool calls (plus Bash commands classified as effects) behind a `PreToolUse` hook that requires a `[arka:routing]` or `[arka:trivial]` marker in the recent assistant messages. When `false`, the shadow-deny telemetry (`hooks.shadowDeny` below — on unless you disable it) records what the gate would have decided, without blocking. Has no effect on Cursor (no `PreToolUse` hook support). |
| `hooks.frontendGate` | `"warn"` | Frontend excellence gate on UI file edits (`.vue`, `.tsx`, stylesheets, `.html`, …): requires the structured `[arka:design] benchmark=<Company> skills=<comma,list>` marker in the recent assistant messages. `"warn"` (or absent) nudges and allows; `"hard"`/`true` denies without the marker; `"off"`/`false` disables the gate. In warn and off modes, shadow-deny records what hard mode would have decided. |
| `hooks.specialistEnforcement` | `false` | Specialist-dispatch gate: blocks squad leads from writing to specialist-owned files (per `config/agent-ownership.yaml`) without dispatching the owning specialist. When `false`, shadow-deny records what the gate would have decided. |
| `hooks.shadowDeny` | `true` (implicit) | Shadow-deny telemetry: while an enforcement flag above is off (or its gate is in warn mode), the gate still evaluates and records `would_block` + `shadow_reason` + `shadow_ms` in its telemetry file — always allowing, never printing. This is the data that gates the future hard-enforcement flip (promotion needs would_block < 5% and zero sequences of more than 2 consecutive would-blocks in a session, over ≥ 7 days and ≥ 300 gated calls). Kill switch: set it to `false` if hook latency regresses by more than 50 ms at p90 — measure the pre-side from `shadow_ms` and the post-side from the `hook-metrics.json` entries with `delegation` benign, `shadow` true, and `enforcement` false. Only an explicit falsy value disables it — a missing file, corrupt JSON, or missing key all mean `true`. |
| `hooks.kbFirst` | `true` (seeded) | Research gate: on the first external research attempt (`Context7`, `WebSearch`, `WebFetch`, `Firecrawl`) without a prior Obsidian query, emits a nudge listing top 3 vault hits and allows the call; on the second attempt in the same turn, denies. Seeded to `true` by the installer when unset; an explicit `false` disables it and is preserved. |

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
| `UserPromptSubmit` | 20 s | Synapse context injection, workflow-required tag, token hygiene |
| `PostToolUse` | 5 s | Error pattern tracking, budget accounting |
| `PostToolUseFailure` | 5 s | Failed tool calls (the runtime fires this event, not `PostToolUse`, when a tool throws) — same entrypoint |
| `PreCompact` | 30 s | Session digest save, agent memory preservation |
| `CwdChanged` | 5 s | Project context reload on directory change |

The `UserPromptSubmit` runtime ceiling is 20 seconds, with a 6 s in-hook
budget (`ARKA_UPS_BUDGET_MS`) that trims optional stages before the
ceiling is reached. Hooks must exit 0 and never block execution —
suggestions from the token hygiene check are advisory only.

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
| `telemetry/enforcement.jsonl` | One record per tool-call gate decision: tool name, reason, allowed/blocked, plus the shadow-deny fields (`would_block`, `shadow_reason`, `shadow_ms`). Used by `/arka enforcement`. |
| `telemetry/frontend-gate.jsonl` | One record per UI-file gate decision (frontend excellence gate), including the shadow-deny fields. |
| `telemetry/specialist-dispatch.jsonl` | One record per specialist-dispatch gate decision, including bypass accounting and the shadow-deny fields. |
| `hook-metrics.json` | Rolling window (last 500) of hook run durations. Post-tool-use entries written by the Python hook on POSIX carry `enforcement`/`shadow` flag labels and a `delegation` kind (benign/stateful/error); the shadow-forced population for the shadow-deny kill switch is the `delegation` benign, `shadow` true, `enforcement` false subset. |
| `telemetry/compliance.jsonl` | One record per stop-hook check: closing marker, `[arka:meta]` tag, KB citation, sycophancy verdict. Used by `/arka compliance`. |
| `reorganize-proposals/<date>.md` | Daily reorganization proposals from `/arka reorganize`. Never auto-applied. |
| `plans/` | Plans saved during Gate 2 (PLAN) of the evidence flow. |
| `workflow-state.json` | Gate checkpoints written by the Stop hook (`core/workflow/gate_checkpoint.py`): current gate, per-gate status, Gate-3 test evidence. A per-session copy lives under `sessions/<id>/` and powers resume after interruptions. |

---

Related: [08 · Multi-Runtime](08-Multi-Runtime.md) (LLM provider and runtime
selection), [05 · Commands Reference](05-Commands-Reference.md) (the `/arka keys`
and `/arka costs` commands).
