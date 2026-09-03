"""Every deployed agent's ``tools:`` resolves on Claude Code 2.1.259 (Runtime Sync PR4).

Since 2.1.233 the todo/task-tracking tools (``TaskCreate/Get/Update/List``,
``TodoWrite``) are not offered on the frontier families — the 2.1.259 binary
gates them on its own list (opus ≥ 4.8, sonnet ≥ 5, fable ≥ 5, mythos ≥ 5)
unless ``CLAUDE_CODE_ENABLE_TODO_TOOLS`` is set. ``paulo-tech-lead.md`` declared
``TaskCreate`` and told the Tech Lead to open every job with it. These
tests pin every ``tools:`` line in ``config/claude-agents/`` to the known
built-in names, and the retired five to absence.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from core.runtime.claude_code import FRONTIER_RETIRED_TOOLS, KNOWN_BUILTIN_TOOLS

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "config" / "claude-agents"
_TOOLS_LINE = re.compile(r"^tools:\s*(.+?)\s*$", re.M)


def _frontmatter(text: str) -> str:
    assert text.startswith("---\n"), "agent file without frontmatter"
    end = text.index("\n---", 4)
    return text[4:end]


def declared_tools(path: Path) -> list[str]:
    """The ``tools:`` list of one agent file; empty when the key is absent
    (an agent without the key inherits every tool)."""
    match = _TOOLS_LINE.search(_frontmatter(path.read_text(encoding="utf-8")))
    if match is None:
        return []
    return [tool.strip() for tool in match.group(1).split(",") if tool.strip()]


def agent_files() -> list[Path]:
    files = sorted(AGENTS_DIR.glob("*.md"))
    assert len(files) >= 80, f"agent corpus shrank to {len(files)} — extraction break?"
    return files


def _known(tool: str) -> bool:
    return tool in KNOWN_BUILTIN_TOOLS or tool.startswith("mcp__")


class TestRetiredTools:
    def test_the_retired_set_is_the_changelog_five(self) -> None:
        assert (
            frozenset({"TodoWrite", "TaskCreate", "TaskGet", "TaskUpdate", "TaskList"})
            == FRONTIER_RETIRED_TOOLS
        )
        assert FRONTIER_RETIRED_TOOLS <= KNOWN_BUILTIN_TOOLS, (
            "retired names are still built-ins on older models — keep them known"
        )

    @pytest.mark.parametrize("path", agent_files(), ids=lambda p: p.stem)
    def test_no_agent_declares_a_retired_tool(self, path: Path) -> None:
        retired = [t for t in declared_tools(path) if t in FRONTIER_RETIRED_TOOLS]
        assert retired == [], (
            f"{path.name} declares {retired}: not offered on frontier models "
            "since Claude Code 2.1.233 — the workflow state carries the plan "
            "(core/workflow/gate_checkpoint.py), not a runtime todo list"
        )

    @pytest.mark.parametrize("path", agent_files(), ids=lambda p: p.stem)
    def test_every_declared_tool_is_a_known_builtin(self, path: Path) -> None:
        unknown = [t for t in declared_tools(path) if not _known(t)]
        assert unknown == [], (
            f"{path.name} declares {unknown}: not a Claude Code 2.1.259 built-in "
            "(KNOWN_BUILTIN_TOOLS) nor an mcp__ tool — a typo or a retired name"
        )

    def test_the_corpus_has_declared_tool_lines(self) -> None:
        """The hand-written four declare tools; a parametrized pass over
        agents that declare nothing would be vacuous."""
        declaring = [p.name for p in agent_files() if declared_tools(p)]
        assert "paulo-tech-lead.md" in declaring
        assert len(declaring) >= 4

    def test_parser_reads_the_real_shape(self, tmp_path: Path) -> None:
        agent = tmp_path / "x.md"
        agent.write_text(
            "---\nname: x\ntools: Read, Grep, Glob, Bash, Agent, TaskCreate\n"
            "model: sonnet\n---\n\n# body\n",
            encoding="utf-8",
        )
        assert declared_tools(agent) == ["Read", "Grep", "Glob", "Bash", "Agent", "TaskCreate"]
        assert [t for t in declared_tools(agent) if t in FRONTIER_RETIRED_TOOLS] == ["TaskCreate"]
        agent.write_text("---\nname: y\nmodel: sonnet\n---\n", encoding="utf-8")
        assert declared_tools(agent) == []


class TestKnownBuiltins:
    def test_known_builtins_carry_the_tools_this_runtime_offers(self) -> None:
        for tool in (
            "Read",
            "Write",
            "Edit",
            "Bash",
            "Glob",
            "Grep",
            "Agent",
            "Skill",
            "WebFetch",
            "WebSearch",
            "AskUserQuestion",
            "ToolSearch",
            "NotebookEdit",
            "ExitPlanMode",
            "TaskOutput",
            "TaskStop",
        ):
            assert tool in KNOWN_BUILTIN_TOOLS, tool

    def test_known_builtins_are_names_not_patterns(self) -> None:
        assert all(re.fullmatch(r"[A-Za-z_]+", t) for t in KNOWN_BUILTIN_TOOLS)
