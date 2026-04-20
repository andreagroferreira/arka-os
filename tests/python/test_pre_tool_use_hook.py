"""End-to-end hook tests for config/hooks/pre-tool-use.sh.

Pipes a realistic JSON payload through the bash hook and asserts that
nudge / deny behaviour surfaces correctly on stderr and stdout.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_PATH = REPO_ROOT / "config" / "hooks" / "pre-tool-use.sh"


pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None,
    reason="bash not available on this platform",
)


@pytest.fixture
def hook_env(tmp_path, monkeypatch):
    """Isolated env: enables kbFirst feature flag and redirects all state.

    Inherits the full os.environ (so PATH / system python remain intact)
    and overlays only the ArkaOS-specific variables we care about.
    """
    import os

    home = tmp_path / "home"
    (home / ".arkaos" / "audit").mkdir(parents=True)
    (home / ".arkaos" / "telemetry").mkdir(parents=True)
    (home / ".arkaos" / "config.json").write_text(
        json.dumps({"hooks": {"kbFirst": True, "hardEnforcement": False}}),
        encoding="utf-8",
    )
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "Laravel Service Pattern.md").write_text("# Laravel Service Pattern\n")

    env = dict(os.environ)
    env.update({
        "HOME": str(home),
        "ARKAOS_ROOT": str(REPO_ROOT),
        "PYTHONPATH": str(REPO_ROOT),
        "ARKA_KB_QUERY_DIR": str(tmp_path / "kb-query"),
        "ARKA_KB_VIOLATION_DIR": str(tmp_path / "kb-violation"),
        "ARKAOS_VAULT": str(vault),
    })
    env.pop("ARKA_BYPASS_KB_FIRST", None)
    return {"env": env, "tmp_path": tmp_path}


def _run_hook(payload: dict, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(HOOK_PATH)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=15,
        env=env,
        check=False,
    )


def test_hook_nudges_on_first_external_research_call(hook_env):
    payload = {
        "tool_name": "WebSearch",
        "session_id": "hook-session-nudge",
        "transcript_path": "",
        "cwd": str(hook_env["tmp_path"]),
        "tool_input": {"query": "laravel service pattern"},
    }

    result = _run_hook(payload, hook_env["env"])

    # Nudge is an allow-with-advisory: exit code is 0, stderr carries the nudge.
    assert result.returncode == 0, f"expected nudge-allow, got {result.returncode}\n{result.stderr}"
    assert "[arka:kb-nudge]" in result.stderr


def test_hook_denies_on_second_external_research_call(hook_env):
    payload = {
        "tool_name": "WebSearch",
        "session_id": "hook-session-deny",
        "transcript_path": "",
        "cwd": str(hook_env["tmp_path"]),
        "tool_input": {"query": "laravel service pattern"},
    }

    # First call: nudge.
    first = _run_hook(payload, hook_env["env"])
    assert first.returncode == 0

    # Second call in the same turn: deny.
    second = _run_hook(payload, hook_env["env"])
    assert second.returncode == 2, f"expected deny, got {second.returncode}\n{second.stderr}"
    assert "[ARKA:KB-FIRST]" in second.stderr

    # The structured hookSpecificOutput JSON must be on stdout.
    stdout = second.stdout.strip()
    assert stdout, "deny path must emit hookSpecificOutput JSON on stdout"
    payload_out = json.loads(stdout)
    assert payload_out["hookSpecificOutput"]["permissionDecision"] == "deny"
