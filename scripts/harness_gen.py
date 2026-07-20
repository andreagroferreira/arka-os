"""Generate harness/ — multi-runtime instruction bundles from one source.

Docs-as-code (marketplace_gen / guide_gen precedent): the ArkaOS
contract — identity, department routing, agent index, evidence
expectations, stack conventions — is COMPILED from the generated
registries and emitted once per supported harness, in that harness's
native instruction format. Nothing here is hand-typed per target;
adding a harness is one small emitter, not a maintained directory.

Targets (v1): codex (AGENTS.md), opencode (AGENTS.md), gemini
(GEMINI.md), zed (.rules), copilot (copilot-instructions.md), cursor
(rules/*.mdc with path-scoped stack rules).

Honesty note baked into every bundle: these are instruction-level
exports — the full ArkaOS engine (Synapse, hooks, Quality Gate
enforcement) runs on runtimes with an adapter; instructions carry the
contract, not the cognition.

Sources (all generated + drift-locked elsewhere):
- ``knowledge/agents-registry-v2.json``  — agents (name/role/dept/tier)
- ``knowledge/commands-registry.json``   — per-department command counts
- ``config/standards/stack-rules/*.md``  — path-scoped stack conventions
- ``VERSION`` + ``scripts/tools/docs_stats.py`` counters

Run: ``~/.arkaos/bin/arka-py scripts/harness_gen.py``

``tests/python/test_harness_gen.py`` drift-gates the committed tree
byte for byte and enforces the size budget — an instruction file that
blows the target's context is the documented anti-pattern.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))

from docs_stats import (
    count_agents,
    count_departments,
    count_skills,
    read_version,
    repo_root,
)

ROOT = repo_root()
HARNESS_DIR = ROOT / "harness"
STACK_RULES_DIR = ROOT / "config" / "standards" / "stack-rules"

# Department prefix -> lead agent name. Leads are tier-1 agents; where a
# department has several squad leads the ORCHESTRATING lead is listed
# (same mapping the routing table in arka/SKILL.md uses).
DEPT_LEADS = {
    "dev": "Paulo", "mkt": "Luna", "brand": "Valentina", "fin": "Helena",
    "strat": "Tomas", "ecom": "Ricardo", "kb": "Clara", "ops": "Daniel",
    "pm": "Carolina", "saas": "Tiago", "landing": "Ines",
    "content": "Rafael", "community": "Beatriz", "sales": "Miguel",
    "lead": "Rodrigo", "org": "Sofia",
}

# Registry department slug -> routing prefix (registry stores directory
# names; the user-facing prefixes differ for four departments).
DIR_TO_PREFIX = {
    "marketing": "mkt", "strategy": "strat", "finance": "fin",
    "leadership": "lead",
}

# Size budget per emitted main file. Instruction files that outgrow the
# target's context stop being read — the budget is the feature.
MAIN_FILE_BUDGET_BYTES = 16_000


def _load_agents() -> list[dict]:
    data = json.loads(
        (ROOT / "knowledge" / "agents-registry-v2.json").read_text())
    return data["agents"]


def _load_command_counts() -> dict[str, int]:
    data = json.loads(
        (ROOT / "knowledge" / "commands-registry.json").read_text())
    return data["_meta"]["departments"]


def _split_frontmatter(text: str) -> tuple[list[str], str]:
    """Return (paths globs, body) from a stack-rules file."""
    if not text.startswith("---"):
        return [], text
    _, fm, body = text.split("---", 2)
    globs = [
        line.strip().lstrip("- ").strip('"')
        for line in fm.strip().splitlines()
        if line.strip().startswith("- ")
    ]
    return globs, body.strip()


def _stack_rules() -> list[tuple[str, list[str], str]]:
    rules = []
    for path in sorted(STACK_RULES_DIR.glob("*.md")):
        globs, body = _split_frontmatter(path.read_text())
        rules.append((path.stem, globs, body))
    return rules


def _department_table(counts: dict[str, int]) -> str:
    # commands-registry keys one department by directory name where the
    # prefix differs ("leadership" for /lead).
    prefix_to_registry = {"lead": "leadership"}
    rows = ["| Prefix | Lead | Commands |", "|---|---|---|"]
    for prefix, lead in DEPT_LEADS.items():
        key = prefix_to_registry.get(prefix, prefix)
        rows.append(f"| `/{prefix}` | {lead} | {counts.get(key, 0)} |")
    return "\n".join(rows)


def _agent_index(agents: list[dict]) -> str:
    by_dept: dict[str, list[dict]] = {}
    for agent in agents:
        prefix = DIR_TO_PREFIX.get(agent["department"], agent["department"])
        by_dept.setdefault(prefix, []).append(agent)
    lines = []
    for prefix in sorted(by_dept):
        members = sorted(
            by_dept[prefix], key=lambda a: (a["tier"], a["name"]))
        listing = " · ".join(
            f"{a['name']} ({a['role']})" for a in members)
        lines.append(f"- **{prefix}**: {listing}")
    return "\n".join(lines)


def _stack_section(rules: list[tuple[str, list[str], str]]) -> str:
    # Rule bodies carry their own "## <Stack> Conventions" title; demote
    # one level so they nest correctly under "## Stack conventions".
    parts = []
    for _stack, _globs, body in rules:
        demoted = "\n".join(
            f"#{line}" if line.startswith("## ") else line
            for line in body.splitlines()
        )
        parts.append(demoted)
    return "\n\n".join(parts)


def _contract_body() -> str:
    version = read_version(ROOT)
    departments = count_departments(ROOT)
    agents_total = count_agents(ROOT)["files"]
    skills = count_skills(ROOT)["core"]
    counts = _load_command_counts()
    agents = _load_agents()
    return f"""# ArkaOS — The Operating System for AI Agent Teams

> v{version} — {agents_total} agents, {departments} departments, \
{skills} skills. Generated by `scripts/harness_gen.py`; do not edit.

You are operating within ArkaOS. Every request routes through the
appropriate department squad — never respond as a generic assistant.

## How to work

1. **Route** every request to a department (table below) and say so:
   `[arka:routing] <dept> -> <lead>`.
2. **Plan before code.** State the plan and wait for explicit approval
   on non-trivial work.
3. **Evidence over narration.** Run the real tests and report the real
   exit code; a claim about code that was never executed is not a
   result.
4. **Quality Gate.** Before delivering, review the work as a critical
   second reader (copy AND technical) and say honestly what is
   unfinished. Nothing ships with known defects undisclosed.

## Departments

{_department_table(counts)}

## Agents

Adopt the matching persona when executing department work:

{_agent_index(agents)}

## Stack conventions

Apply the section matching the files you touch.

{_stack_section(_stack_rules())}

## Scope of this file

Instruction-level export for this runtime. The full ArkaOS engine —
context injection, hooks, enforced quality gates, knowledge base — runs
on runtimes with a native adapter (`npx arkaos install`). This file
carries the contract so the team behaves like ArkaOS anywhere.
"""


def _cursor_files() -> dict[str, str]:
    """Cursor gets native path-scoped rules instead of one flat file."""
    version = read_version(ROOT)
    files: dict[str, str] = {}
    body = _contract_body()
    # Strip the stack section from the always-on rule — stacks ship as
    # individually scoped .mdc files below, Cursor's native strength.
    main = body.split("## Stack conventions")[0].rstrip()
    main += (
        "\n\n## Stack conventions\n\nPath-scoped rules in this directory "
        "(`arkaos-stack-*.mdc`) apply automatically to matching files.\n"
    )
    files["rules/arkaos.mdc"] = (
        f"---\ndescription: ArkaOS v{version} agent-team contract\n"
        f"alwaysApply: true\n---\n\n{main}\n"
    )
    for stack, globs, rule_body in _stack_rules():
        globs_line = ", ".join(globs)
        files[f"rules/arkaos-stack-{stack}.mdc"] = (
            f"---\ndescription: ArkaOS {stack} stack conventions\n"
            f"globs: {globs_line}\nalwaysApply: false\n---\n\n"
            f"{rule_body}\n"
        )
    return files


def generate() -> dict[str, str]:
    """Return {relative path under harness/: content}."""
    body = _contract_body()
    files: dict[str, str] = {
        "codex/AGENTS.md": body,
        "opencode/AGENTS.md": body,
        "gemini/GEMINI.md": body,
        "zed/.rules": body,
        "copilot/copilot-instructions.md": body,
    }
    for rel, content in _cursor_files().items():
        files[f"cursor/{rel}"] = content
    return files


def check_budget(files: dict[str, str]) -> list[str]:
    over = []
    for rel, content in files.items():
        size = len(content.encode("utf-8"))
        if size > MAIN_FILE_BUDGET_BYTES:
            over.append(f"{rel}: {size} bytes > {MAIN_FILE_BUDGET_BYTES}")
    return over


def main() -> int:
    files = generate()
    over = check_budget(files)
    if over:
        print("BUDGET EXCEEDED:\n  " + "\n  ".join(over))
        return 1
    if HARNESS_DIR.exists():
        for stale in HARNESS_DIR.rglob("*"):
            if stale.is_file():
                rel = str(stale.relative_to(HARNESS_DIR))
                if rel not in files:
                    stale.unlink()
    for rel, content in files.items():
        target = HARNESS_DIR / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    total = sum(len(c.encode()) for c in files.values())
    print(
        f"harness generated: {len(files)} files, 6 targets, "
        f"{total} bytes total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
