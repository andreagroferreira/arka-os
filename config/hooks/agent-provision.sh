#!/usr/bin/env bash
# ArkaOS PreToolUse hook for dynamic agent provisioning.
# Intercepts Task tool calls: if subagent_type is not present in the
# project's .claude/agents/, copies it from ArkaOS core when available,
# or surfaces an approval-request message WITHOUT blocking when the
# agent is unknown. The set of valid subagent_types is not enumerable
# here — runtime built-ins (general-purpose, statusline-setup, …)
# change with Claude Code versions and plugins add their own — so any
# blocking arm on "unknown" breaks legitimate dispatches (QG PR-B5 r1
# reproduced exit 2 on general-purpose). Provision when we know the
# name; stand aside when we don't.

set -euo pipefail

# No jq, no payload parse. .claude/rules/bash-hooks.md:11-12 prescribes
# a python3 fallback for jq; this gate is OPTIONAL by design, so it
# stands aside instead of paying a python spawn on every Task call —
# and per the same rules file ("exit code 2 = block action", last
# bullet), exiting 0 here can never break a dispatch.
command -v jq >/dev/null 2>&1 || exit 0

# ─── Shared Python resolver (exports ARKA_PY) ──────────────────────────
# The resolver guards its own ARKA_PY assignment with `|| true`, so sourcing
# is set -e-safe even on the last-resort fallback. The trailing `|| true`
# here is belt-and-suspenders for a partially-updated lib.
_ARKA_LIB="$(dirname "${BASH_SOURCE[0]:-$0}")/_lib/arka_python.sh"
if [ -f "$_ARKA_LIB" ]; then . "$_ARKA_LIB" || true; else ARKA_PY="python3"; fi

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

# Strict allowlist: lowercase alphanumeric + hyphens, max 64 chars, must start with letter.
if [[ ! "$subagent_type" =~ ^[a-z][a-z0-9-]{0,63}$ ]]; then
    # Invalid name — skip hook (do not block) so legitimate workflows continue;
    # the Task dispatch itself will fail naturally if the agent truly doesn't exist.
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
    set +e
    "$ARKA_PY" - "$core_root" "$subagent_type" "$target" <<'PY'
import os, re, sys
from pathlib import Path

core = Path(sys.argv[1]).resolve()
name = sys.argv[2]
target = Path(sys.argv[3]).resolve()

if not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", name):
    sys.exit(2)

departments_root = (core / "departments").resolve()
if not departments_root.exists():
    sys.exit(2)

# Ensure target stays within .claude/agents of the project
expected_parent = target.parent.resolve()
if target.suffix != ".md" or expected_parent.name != "agents":
    sys.exit(2)

yaml_path = None
md_path = None
for dept in departments_root.iterdir():
    agents = dept / "agents"
    if not agents.is_dir():
        continue
    y = (agents / f"{name}.yaml").resolve()
    m = (agents / f"{name}.md").resolve()
    if y.exists() and yaml_path is None:
        try:
            y.relative_to(departments_root)
        except ValueError:
            continue
        yaml_path = y
    if m.exists() and md_path is None:
        try:
            m.relative_to(departments_root)
        except ValueError:
            continue
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

content = "\n".join(parts) + "\n"

# Create the parent only on the arm that actually writes (a dispatch
# of an unknown name must not scatter empty .claude/agents/ dirs), then
# atomic write: temp file in same dir, then os.replace.
target.parent.mkdir(parents=True, exist_ok=True)
tmp = target.with_suffix(".md.tmp")
tmp.write_text(content)
os.replace(tmp, target)
PY
    rc=$?
    set -e

    case "$rc" in
        0)
            echo "[arka:provisioned] Copied agent '$subagent_type' from ArkaOS core." >&2
            exit 0
            ;;
        2)
            # Agent not found in core; fall through to approval-request message below.
            ;;
        *)
            echo "[arka:provision-error] Unexpected error ($rc) while provisioning '$subagent_type'. Dispatch not blocked." >&2
            exit 1
            ;;
    esac
fi

# Agent not in project, and the core lookup either found nothing or
# never ran. Say exactly which, and NEVER block: this name may be a
# runtime built-in or a plugin agent this script cannot know about —
# if it truly doesn't exist, the Task dispatch itself fails with the
# runtime's own error.
if [ -d "$core_root/departments" ]; then
    core_note="no ArkaOS core agent of that name was found (core searched at: $core_root)"
else
    core_note="the ArkaOS core lookup did not run (no departments/ under: ${core_root:-<unset>})"
fi
cat >&2 <<MSG
[arka:provision-needed] Agent '$subagent_type' is not in this project's
.claude/agents/, and $core_note.
If ArkaOS should provide this agent, create it at
.claude/agents/$subagent_type.md, or run 'npx arkaos update' so ArkaOS
core ships a definition this gate can copy.
Runtime built-ins and plugin agents are unaffected — dispatch proceeds.
MSG
exit 0
