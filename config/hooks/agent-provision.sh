#!/usr/bin/env bash
# ArkaOS PreToolUse hook for dynamic agent provisioning.
# Intercepts Task tool calls: if subagent_type is not present in the
# project's .claude/agents/, copies it from ArkaOS core when available,
# or blocks with an approval-request message when the agent must be
# created via `/platform-arka agent provision <name>`.

set -euo pipefail

# Hook contract: stdin is a JSON payload with fields tool_name + tool_input.
payload="$(cat)"

tool_name="$(echo "$payload" | jq -r '.tool_name // ""')"
if [ "$tool_name" != "Task" ]; then
    exit 0
fi

subagent_type="$(echo "$payload" | jq -r '.tool_input.subagent_type // ""')"
if [ -z "$subagent_type" ] || [ "$subagent_type" = "null" ]; then
    exit 0
fi

project_root="$(pwd)"
project_agents_dir="$project_root/.claude/agents"
target="$project_agents_dir/${subagent_type}.md"

if [ -f "$target" ]; then
    exit 0
fi

# Agent missing locally — try copying from ArkaOS core.
core_root="${ARKAOS_CORE_ROOT:-}"
if [ -z "$core_root" ]; then
    core_root="$(npm root -g 2>/dev/null)/arkaos"
fi

if [ -d "$core_root/departments" ]; then
    mkdir -p "$project_agents_dir"
    python3 - "$core_root" "$subagent_type" "$target" <<'PY' || true
import os, sys
from pathlib import Path

core = Path(sys.argv[1])
name = sys.argv[2]
target = Path(sys.argv[3])

yaml_path = None
md_path = None
for dept in (core / "departments").iterdir():
    agents = dept / "agents"
    if not agents.is_dir():
        continue
    y = agents / f"{name}.yaml"
    m = agents / f"{name}.md"
    if y.exists() and yaml_path is None:
        yaml_path = y
    if m.exists() and md_path is None:
        md_path = m

if yaml_path is None and md_path is None:
    sys.exit(2)

parts = []
if yaml_path is not None:
    parts.append("---")
    parts.append(yaml_path.read_text().strip())
    parts.append("---")
if md_path is not None:
    parts.append(md_path.read_text().rstrip())

target.write_text("\n".join(parts) + "\n")
PY
    if [ -f "$target" ]; then
        echo "[arka:provisioned] Copied agent '$subagent_type' from ArkaOS core." >&2
        exit 0
    fi
fi

# Agent not in project and not in core — surface an approval-request.
cat >&2 <<MSG
[arka:provision-needed] Agent '$subagent_type' is not installed in this
project and does not exist in ArkaOS core. To create it, run:

    /platform-arka agent provision $subagent_type

This opens the Skill Architect flow which drafts the agent YAML with
4-framework DNA, goes through Quality Gate, and commits to core before
propagating to the project. Blocking dispatch until the agent exists.
MSG
exit 2
