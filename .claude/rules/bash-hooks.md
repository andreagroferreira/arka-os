---
paths:
  - "config/hooks/*.sh"
  - "config/hooks/*.ps1"
  - "core/hooks/*.py"
  - "bin/*"
---

# Hook Rules (bash, PowerShell, Python entrypoints)

- Bash wrappers: read stdin with `input=$(cat)` at the top; use jq for
  JSON parsing, python3 as fallback. PowerShell ports mirror the same
  contract with `[Console]::In.ReadToEnd()` + `ConvertFrom-Json`. Python
  entrypoints (`core/hooks/*.py`) use `read_stdin_json()` and emit via
  `emit_additional_context()`/`emit_deny_json()` from `core/hooks/_shared.py`
- Cache expensive operations (git, python3) with TTL
- Context output must ride inside `hookSpecificOutput` with the matching `hookEventName`: `{"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": "..."}}` — a top-level `additionalContext` key is silently ignored by the runtime. Other events carry their own keys in the same wrapper (PreToolUse: `permissionDecision`/`permissionDecisionReason`; CwdChanged: `watchPaths` only — use top-level `systemMessage` there). Emitting nothing, or `{}`, is valid when the hook has nothing to say
- Timeout budget: SessionStart 5s, UserPromptSubmit 20s ceiling with a
  6s in-hook budget (`ARKA_UPS_BUDGET_MS`), PostToolUse 5s
- Never block on network calls (use cached data or skip)
- Exit code 0 = success, exit code 2 = block action
