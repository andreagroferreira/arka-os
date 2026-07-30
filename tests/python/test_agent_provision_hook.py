"""Behavioral tests for config/hooks/agent-provision.sh (PR-B5, QG r1 B1).

The registration tests pin only the settings shape; these run the
SCRIPT. The load-bearing contract: the gate NEVER blocks (exit 2) on an
unknown subagent_type — runtime built-ins (general-purpose,
statusline-setup, …) and plugin agents are names this script cannot
enumerate, and blocking them broke legitimate dispatches (reproduced in
QG round 1). Provision when the name is known to ArkaOS core; stand
aside otherwise.
"""

from __future__ import annotations

import json
import platform
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "config" / "hooks" / "agent-provision.sh"

pytestmark = pytest.mark.skipif(
    platform.system() == "Windows", reason="bash hook (POSIX-only)"
)


def _run(payload: dict, cwd: Path, core_root: str = "") -> subprocess.CompletedProcess:
    env = {
        "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
        "HOME": str(cwd),
        "ARKAOS_CORE_ROOT": core_root,
    }
    return subprocess.run(
        ["bash", str(SCRIPT)],
        input=json.dumps(payload).encode("utf-8"),
        cwd=cwd,
        env=env,
        capture_output=True,
        timeout=15,
        check=False,
    )


def test_unknown_builtin_type_never_blocks(tmp_path):
    """The QG r1 reproduction, inverted: general-purpose passes."""
    proc = _run(
        {"tool_name": "Task", "tool_input": {"subagent_type": "general-purpose"}},
        tmp_path,
    )
    assert proc.returncode == 0, proc.stderr.decode()
    assert b"provision-needed" in proc.stderr
    assert b"dispatch proceeds" in proc.stderr


def test_non_task_tool_is_ignored(tmp_path):
    proc = _run({"tool_name": "Write", "tool_input": {}}, tmp_path)
    assert proc.returncode == 0
    assert proc.stderr == b""


def test_existing_project_agent_passes_silently(tmp_path):
    agents = tmp_path / ".claude" / "agents"
    agents.mkdir(parents=True)
    (agents / "my-agent.md").write_text("---\nname: my-agent\n---\n")
    proc = _run(
        {"tool_name": "Task", "tool_input": {"subagent_type": "my-agent"}},
        tmp_path,
    )
    assert proc.returncode == 0
    assert proc.stderr == b""


def test_known_core_agent_is_provisioned(tmp_path):
    """A departments/*/agents/ name is copied into the project."""
    proc = _run(
        {"tool_name": "Task", "tool_input": {"subagent_type": "architect"}},
        tmp_path,
        core_root=str(REPO_ROOT),
    )
    assert proc.returncode == 0, proc.stderr.decode()
    assert b"[arka:provisioned]" in proc.stderr
    target = tmp_path / ".claude" / "agents" / "architect.md"
    assert target.is_file(), "provisioning must materialise the agent"


def test_invalid_name_is_ignored(tmp_path):
    proc = _run(
        {"tool_name": "Task", "tool_input": {"subagent_type": "../evil"}},
        tmp_path,
    )
    assert proc.returncode == 0
    assert proc.stderr == b""


def test_missing_jq_stands_aside(tmp_path):
    """QG r2 FM1: the jq guard had no regression pin. A PATH with the
    script's other tools but no jq must exit 0 before parsing."""
    import shutil

    bindir = tmp_path / "bin"
    bindir.mkdir()
    for tool in ("bash", "cat", "dirname"):
        real = shutil.which(tool, path="/usr/bin:/bin")
        assert real, f"{tool} must exist for this test"
        (bindir / tool).symlink_to(real)
    proc = subprocess.run(
        ["bash", str(SCRIPT)],
        input=b'{"tool_name":"Task","tool_input":{"subagent_type":"x"}}',
        cwd=tmp_path,
        env={"PATH": str(bindir), "HOME": str(tmp_path)},
        capture_output=True,
        timeout=15,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr.decode()


def test_unknown_name_never_creates_directories(tmp_path):
    """QG r2 FM2: the mkdir used to run before the core lookup, so any
    dispatch of an unknown name scattered empty .claude/agents/ dirs.
    Only the arm that writes an agent may create its parent."""
    proc = _run(
        {"tool_name": "Task", "tool_input": {"subagent_type": "general-purpose"}},
        tmp_path,
        core_root=str(REPO_ROOT),
    )
    assert proc.returncode == 0
    assert not (tmp_path / ".claude").exists(), (
        "an unknown-name dispatch must leave the filesystem untouched"
    )


def test_script_never_emits_blocking_exit_code():
    """Structural pin: no bash-level `exit 2` — exit 2 is the
    PreToolUse BLOCK code and the whole point of QG r1 B1 is that this
    gate never blocks. The embedded Python's `sys.exit(2)` is an
    internal not-found signal consumed by the bash `case`, never the
    script's own exit status, so the pin matches bash statements only
    (column-0 in this script; the heredoc body is indented)."""
    import re

    text = SCRIPT.read_text(encoding="utf-8")
    assert not re.search(r"^exit 2\b", text, re.MULTILINE), (
        "agent-provision.sh must never block a Task dispatch"
    )
