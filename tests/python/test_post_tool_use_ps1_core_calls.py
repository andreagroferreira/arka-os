"""The Windows PostToolUse hook must reach core/ for the markers it owns.

Two markers are written by side effect from this hook: the flow marker cache
(`[arka:routing]` / `[arka:trivial]`) and the KB-first evidence marker on a
genuine `mcp__obsidian__*` call. The bash twin gets both by delegating to
``core/hooks/post_tool_use.py``; the PowerShell port reimplements the event,
and neither marker was reaching disk.

Measured 2026-08-10, three defects stacked in one code path:

1. The KB branch did not exist in the port at all, so the research gate could
   never observe a consult on Windows and denied every second external search
   for the rest of the turn (issue #541 is the same .sh/.ps1 divergence
   pattern).
2. The core call flattened its snippet with newline -> "; " and passed it as
   `-c`. `import os; try:;     from ...` is a SyntaxError, so the flow marker
   call had never once succeeded on Windows. A guarded catch and redirected
   stderr hid it.
3. Environment variables were pushed with ``.Add()``, which throws when the
   key is already inherited. With PYTHONPATH exported the whole call became
   a no-op.

These tests RUN the hook. Asserting that "obsidian" appears in the source
would pass against a comment, and would have passed against defects 2 and 3
with the branch present and dead -- which is exactly the state the port was
in halfway through this fix.

Windows-only by construction (the hook reads %USERPROFILE%), so this runs on
the cross-platform CI leg and skips elsewhere rather than pretending to cover
a platform it cannot execute.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK = REPO_ROOT / "config" / "hooks" / "post-tool-use.ps1"
REAL_VENV = Path(os.path.expanduser("~")) / ".arkaos" / "venv"

pytestmark = pytest.mark.skipif(
    os.name != "nt", reason="post-tool-use.ps1 is the Windows hook"
)


def _run(payload: dict, home: Path) -> subprocess.CompletedProcess[str]:
    shell = shutil.which("powershell") or shutil.which("pwsh")
    if not shell:
        pytest.skip("no PowerShell on PATH")
    tmp = home / "T"
    tmp.mkdir(exist_ok=True)
    (home / ".arkaos").mkdir(exist_ok=True)
    # The hook resolves its interpreter at ~/.arkaos/venv first. Junction the
    # real venv in, or the fallback picks a bare system Python that cannot
    # import core.* and the run proves a missing dependency, not a missing
    # marker.
    if REAL_VENV.is_dir():
        subprocess.run(
            ["cmd", "/c", "mklink", "/J",
             str(home / ".arkaos" / "venv"), str(REAL_VENV)],
            capture_output=True, text=True,
        )
    env = {
        **os.environ,
        "USERPROFILE": str(home),
        "TEMP": str(tmp),
        "TMP": str(tmp),
        "ARKAOS_ROOT": str(REPO_ROOT),
    }
    return subprocess.run(
        [shell, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
         "-File", str(HOOK)],
        input=json.dumps(payload), capture_output=True, text=True,
        env=env, cwd=str(REPO_ROOT), timeout=180,
    )


@pytest.fixture()
def home(tmp_path: Path) -> Path:
    return tmp_path


def _kb_marker(home: Path, session: str) -> dict | None:
    path = home / "T" / "arkaos-kb-query" / f"{session}.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def test_obsidian_call_records_the_kb_first_evidence_marker(home: Path) -> None:
    out = _run({
        "tool_name": "mcp__obsidian__search_notes",
        "session_id": "kb-1",
        "cwd": str(REPO_ROOT),
        "tool_input": {"query": "ship of theseus"},
        "tool_response": "3 results",
    }, home)
    assert out.returncode == 0, out.stdout + out.stderr
    marker = _kb_marker(home, "kb-1")
    assert marker is not None, f"no marker written; hook said {out.stdout!r}"
    # kind matters as much as existence: Synapse L2.5 writes "injected" for
    # its automatic context, and the research gate deliberately ignores that
    # one. Only "obsidian" counts as evidence of a real consult.
    assert marker["kind"] == "obsidian"
    assert marker["queries"][0]["query"] == "ship of theseus"


def test_query_hint_falls_back_to_path_then_tool_name(home: Path) -> None:
    _run({
        "tool_name": "mcp__obsidian__read_note",
        "session_id": "kb-2",
        "cwd": str(REPO_ROOT),
        "tool_input": {"path": "Projects/ArkaOS/ArkaOS.md"},
        "tool_response": "ok",
    }, home)
    marker = _kb_marker(home, "kb-2")
    assert marker is not None
    assert marker["queries"][0]["query"] == "Projects/ArkaOS/ArkaOS.md"


def test_non_obsidian_tool_writes_no_kb_marker(home: Path) -> None:
    """The gate must not be satisfiable by unrelated tool traffic."""
    _run({
        "tool_name": "Bash",
        "session_id": "kb-3",
        "cwd": str(REPO_ROOT),
        "tool_input": {"command": "echo hi"},
        "tool_response": {"stdout": "hi", "stderr": ""},
    }, home)
    assert _kb_marker(home, "kb-3") is None


def test_routing_marker_reaches_the_flow_marker_cache(home: Path) -> None:
    """Guards defect 2: a compound snippet must survive the core call.

    This assertion is what fails when someone reverts the stdin-fed
    interpreter to a flattened `-c` argument — the branch stays present and
    readable while doing nothing at all.
    """
    _run({
        "tool_name": "Bash",
        "session_id": "flow-1",
        "cwd": str(REPO_ROOT),
        "assistant_message": "[arka:routing] dev -> devops-eng",
        "tool_input": {"command": "echo hi"},
        "tool_response": {"stdout": "hi", "stderr": ""},
    }, home)
    path = home / "T" / "arkaos-flow-marker" / "flow-1.json"
    assert path.is_file(), "flow marker cache was not written"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["marker_type"] == "routing"
    assert data["dept"] == "dev"
    assert data["lead"] == "devops-eng"


def test_inherited_pythonpath_does_not_disable_the_core_call(home: Path) -> None:
    """Guards defect 3: `.Add()` throws on an already-inherited key.

    A developer with PYTHONPATH exported got a hook that silently did
    nothing, and every other test here would still have passed.
    """
    os.environ["PYTHONPATH"] = str(tempfile.gettempdir())
    try:
        _run({
            "tool_name": "mcp__obsidian__search_notes",
            "session_id": "kb-4",
            "cwd": str(REPO_ROOT),
            "tool_input": {"query": "inherited pythonpath"},
            "tool_response": "ok",
        }, home)
    finally:
        os.environ.pop("PYTHONPATH", None)
    assert _kb_marker(home, "kb-4") is not None
