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

OpenCode first-class (Foundation PR-6): beyond AGENTS.md, the opencode
target emits its native surfaces — agents/*.md (curated cut: C-suite +
squad leads, frontmatter per opencode.ai/docs/agents), commands/*.md
(one router command per department, $ARGUMENTS template per
opencode.ai/docs/commands), and opencode.json (reference fragment the
installer adapter merges NON-destructively into the user's config).

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

# Stack slug -> display name for user-facing frontmatter (title() would
# render "Php").
STACK_DISPLAY = {
    "laravel": "Laravel", "node": "Node", "nuxt": "Nuxt", "php": "PHP",
    "python": "Python", "react": "React", "vue": "Vue",
}


def _load_agents() -> list[dict]:
    data = json.loads(
        (ROOT / "knowledge" / "agents-registry-v2.json").read_text(encoding="utf-8"))
    return data["agents"]


def _load_command_counts() -> dict[str, int]:
    data = json.loads(
        (ROOT / "knowledge" / "commands-registry.json").read_text(encoding="utf-8"))
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
        globs, body = _split_frontmatter(path.read_text(encoding="utf-8"))
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

## Stack Conventions

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
    main = body.split("## Stack Conventions")[0].rstrip()
    main += (
        "\n\n## Stack Conventions\n\nPath-scoped rules in this directory "
        "(`arkaos-stack-*.mdc`) apply automatically to matching files.\n"
    )
    files["rules/arkaos.mdc"] = (
        f"---\ndescription: ArkaOS v{version} agent-team contract\n"
        f"alwaysApply: true\n---\n\n{main}\n"
    )
    for stack, globs, rule_body in _stack_rules():
        globs_line = ", ".join(globs)
        display = STACK_DISPLAY.get(stack, stack.title())
        files[f"rules/arkaos-stack-{stack}.mdc"] = (
            f"---\ndescription: ArkaOS {display} stack conventions\n"
            f"globs: {globs_line}\nalwaysApply: false\n---\n\n"
            f"{rule_body}\n"
        )
    return files


def _curated_agents(agents: list[dict]) -> list[dict]:
    """C-suite (tier 0) + squad leads (tier 1) — the cut that becomes
    native agent files. Specialists stay in the AGENTS.md index; 89
    files would blow the harness read budget."""
    cut = [a for a in agents if a["tier"] <= 1]
    return sorted(cut, key=lambda a: (a["tier"], a["department"], a["name"]))


def _agent_markdown(agent: dict) -> str:
    version = read_version(ROOT)
    prefix = DIR_TO_PREFIX.get(agent["department"], agent["department"])
    domains = ", ".join(agent.get("expertise_domains", [])[:6])
    traits = " · ".join(
        t for t in (
            agent.get("disc", {}).get("label", ""),
            agent.get("enneagram", {}).get("label", ""),
            agent.get("mbti", ""),
        ) if t
    )
    lines = [
        "---",
        f'description: "{agent["role"]} — ArkaOS /{prefix} department"',
        "mode: subagent",
        "---",
        "",
        f"You are {agent['name']}, {agent['role']} of the ArkaOS /{prefix} "
        f"department (v{version}; generated by scripts/harness_gen.py — "
        "do not edit).",
    ]
    if domains:
        lines += ["", f"Expertise: {domains}."]
    if traits:
        lines += ["", f"Behavioral profile: {traits}."]
    lines += [
        "",
        "Work the ArkaOS way: announce routing "
        f"(`[arka:routing] {prefix} -> {DEPT_LEADS.get(prefix, agent['name'])}`), "
        "plan before code, report real exit codes over narration, and "
        "state honestly what is unfinished before delivering.",
        "",
    ]
    return "\n".join(lines)


def _opencode_agent_files() -> dict[str, str]:
    curated = _curated_agents(_load_agents())
    files = {
        f"opencode/agents/arka-{agent['id']}.md": _agent_markdown(agent)
        for agent in curated
    }
    # Model-tier sidecar: the installer adapter maps each tier onto the
    # user's own opencode model/small_model at deploy time (the bundle
    # cannot hardcode a provider — opencode runs on any provider).
    files["opencode/agents-meta.json"] = json.dumps(
        {
            f"arka-{agent['id']}.md": agent.get("model", "sonnet")
            for agent in curated
        },
        indent=2,
    ) + "\n"
    return files


def _opencode_command_files() -> dict[str, str]:
    """One router command per department: /arka-<prefix> <request>."""
    files: dict[str, str] = {}
    for prefix, lead in DEPT_LEADS.items():
        files[f"opencode/commands/arka-{prefix}.md"] = (
            "---\n"
            f'description: "ArkaOS /{prefix} department ({lead})"\n'
            "---\n\n"
            f"[arka:routing] {prefix} -> {lead}\n\n"
            f"Handle the following as the ArkaOS /{prefix} department, "
            f"orchestrated by {lead}. Follow the AGENTS.md contract "
            "(plan approval, evidence over narration, quality gate; "
            "generated by scripts/harness_gen.py):\n\n"
            "$ARGUMENTS\n"
        )
    return files


def _opencode_config() -> str:
    """Reference opencode.json fragment. The installer adapter merges it
    NON-destructively — user keys always win; this file is never copied
    over an existing config verbatim. ``~`` placeholders are expanded by
    the adapter against the installing user's home directory. User-local
    MCPs (obsidian vault, graphify endpoint) are seeded adapter-side from
    ~/.arkaos/profile.json and ~/.arkaos/config.json, not here."""
    config = {
        "$schema": "https://opencode.ai/config.json",
        "mcp": {
            "arka-tools": {
                "type": "local",
                "command": ["npx", "-y", "arkaos", "mcp", "start"],
                "enabled": True,
            },
            "arka-prompts": {
                "type": "local",
                "command": [
                    "uv",
                    "--directory",
                    "~/.claude/skills/arka/mcp-server",
                    "run",
                    "server.py",
                ],
                "enabled": True,
            },
            "memory-bank": {
                "type": "local",
                "command": ["npx", "-y", "@allpepper/memory-bank-mcp"],
                "environment": {"MEMORY_BANK_ROOT": "~/memory-bank"},
                "enabled": True,
            },
        },
    }
    return json.dumps(config, indent=2) + "\n"


def _opencode_plugin() -> str:
    """Source of the opencode governance plugin (hooks parity). Lives in
    installer/assets so the plugin is reviewable TS, not generated text."""
    path = ROOT / "installer" / "assets" / "opencode" / "arka.ts"
    return path.read_text(encoding="utf-8")


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
    files["opencode/opencode.json"] = _opencode_config()
    files["opencode/plugins/arka.ts"] = _opencode_plugin()
    files.update(_opencode_agent_files())
    files.update(_opencode_command_files())
    return files


def check_budget(files: dict[str, str]) -> list[str]:
    over = []
    for rel, content in files.items():
        size = len(content.encode("utf-8"))
        if size > MAIN_FILE_BUDGET_BYTES:
            over.append(f"{rel}: {size} bytes > {MAIN_FILE_BUDGET_BYTES}")
    return over


def write_bundle(files: dict[str, str], harness_dir: Path) -> None:
    """Write the bundle, removing files a previous run left behind."""
    if harness_dir.exists():
        for stale in harness_dir.rglob("*"):
            if stale.is_file():
                rel = str(stale.relative_to(harness_dir))
                if rel not in files:
                    stale.unlink()
    for rel, content in files.items():
        target = harness_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def main() -> int:
    files = generate()
    over = check_budget(files)
    if over:
        print("BUDGET EXCEEDED:\n  " + "\n  ".join(over))
        return 1
    write_bundle(files, HARNESS_DIR)
    total = sum(len(c.encode()) for c in files.values())
    targets = len({rel.split("/")[0] for rel in files})
    print(
        f"harness generated: {len(files)} files, {targets} targets, "
        f"{total} bytes total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
