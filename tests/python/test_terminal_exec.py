"""Tests for the terminal command runner (PR95a v3.51.0)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_dashboard_api():
    if "dashboard_api" in sys.modules:
        return sys.modules["dashboard_api"]
    repo = Path(__file__).resolve().parents[2]
    path = repo / "scripts" / "dashboard-api.py"
    spec = importlib.util.spec_from_file_location("dashboard_api", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["dashboard_api"] = module
    spec.loader.exec_module(module)
    return module


def test_list_returns_allowlist():
    api = _load_dashboard_api()
    res = api.terminal_commands()
    assert "commands" in res
    assert "total" in res
    assert res["total"] == len(res["commands"])
    assert len(res["commands"]) >= 4


def test_list_entries_have_required_fields():
    api = _load_dashboard_api()
    res = api.terminal_commands()
    for c in res["commands"]:
        for key in ("id", "label", "description"):
            assert key in c
            assert c[key]


def test_list_does_not_leak_cmd_arrays():
    """The list endpoint must NOT return the raw cmd[] — defence in depth."""
    api = _load_dashboard_api()
    res = api.terminal_commands()
    for c in res["commands"]:
        assert "cmd" not in c


def test_exec_rejects_non_object_body():
    api = _load_dashboard_api()
    res = api.terminal_exec("not a dict")
    assert "error" in res


def test_exec_rejects_missing_command_id():
    api = _load_dashboard_api()
    res = api.terminal_exec({})
    assert "error" in res
    assert "command_id" in res["error"]


def test_exec_rejects_non_allowlisted_command():
    api = _load_dashboard_api()
    res = api.terminal_exec({"command_id": "rm-rf-everything"})
    assert "error" in res
    assert "allowlist" in res["error"]


def test_exec_rejects_shell_metachar_in_id():
    """Even if the id contains shell metacharacters, the lookup must miss."""
    api = _load_dashboard_api()
    res = api.terminal_exec({"command_id": "git-status; rm -rf /"})
    assert "error" in res


def test_exec_runs_git_status():
    """Smoke test for one allowlisted command. Best-effort — runs git
    against the repo cwd, which works in CI + dev."""
    api = _load_dashboard_api()
    res = api.terminal_exec({"command_id": "git-status"})
    assert "stdout" in res
    assert "stderr" in res
    assert "exit_code" in res
    assert "duration_ms" in res
    assert "command" in res
    assert "git status" in res["command"]


def test_allowlist_has_no_shell_invocations():
    """Defence in depth: nothing in the allowlist should invoke a shell."""
    api = _load_dashboard_api()
    banned = {"bash", "sh", "zsh", "fish", "eval", "exec"}
    for entry in api.TERMINAL_ALLOWLIST:
        binary = entry["cmd"][0]
        assert binary not in banned, f"{entry['id']} uses {binary}"
