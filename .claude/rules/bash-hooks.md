---
paths:
  - "config/hooks/*.sh"
  - "bin/*"
---

# Bash Hook Rules

- Always read stdin with `input=$(cat)` at the top
- Use jq for JSON parsing, python3 as fallback
- Cache expensive operations (git, python3) with TTL
- Output must be valid JSON: `{"additionalContext": "..."}`
- Timeout budget: SessionStart 5s, UserPromptSubmit 10s, PostToolUse 5s
- Never block on network calls (use cached data or skip)
- Exit code 0 = success, exit code 2 = block action
