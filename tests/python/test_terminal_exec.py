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
        # PR96b — allowlist now mixes `cmd` and `cmd_template` entries.
        binary = (entry.get("cmd") or entry.get("cmd_template"))[0]
        assert binary not in banned, f"{entry['id']} uses {binary}"


# --- PR96b: parameterised commands ---

def test_list_includes_args_schema():
    api = _load_dashboard_api()
    res = api.terminal_commands()
    parameterised = [c for c in res["commands"] if c.get("args")]
    assert len(parameterised) >= 1
    for arg in parameterised[0]["args"]:
        for key in ("name", "label", "choices", "default"):
            assert key in arg


def test_list_does_not_leak_cmd_template():
    """cmd_template is internal; the public listing must NEVER expose it."""
    api = _load_dashboard_api()
    res = api.terminal_commands()
    for c in res["commands"]:
        assert "cmd_template" not in c
        assert "cmd" not in c


def test_exec_uses_default_when_arg_missing():
    """Calling a parameterised command without args must succeed via default."""
    api = _load_dashboard_api()
    res = api.terminal_exec({"command_id": "git-log"})
    # Successful execution returns shape with `command` populated by default.
    assert "command" in res
    assert "10" in res["command"]  # default `count`


def test_exec_rejects_invalid_choice():
    api = _load_dashboard_api()
    res = api.terminal_exec({"command_id": "git-log", "args": {"count": "999"}})
    assert "error" in res
    assert "not in the allowed choices" in res["error"]


def test_exec_rejects_unknown_arg():
    api = _load_dashboard_api()
    res = api.terminal_exec({
        "command_id": "git-log",
        "args": {"count": "10", "evil": "bash -c whoami"},
    })
    assert "error" in res
    assert "unknown arg" in res["error"]


def test_exec_rejects_metachar_payload():
    """Even if the operator slips shell metacharacters into a choice value,
    the choice-set check rejects them before any substitution."""
    api = _load_dashboard_api()
    res = api.terminal_exec({
        "command_id": "git-log",
        "args": {"count": "10; rm -rf /"},
    })
    assert "error" in res
    assert "not in the allowed choices" in res["error"]


def test_resolve_template_substitutes_validated_value():
    api = _load_dashboard_api()
    entry = next(c for c in api.TERMINAL_ALLOWLIST if c["id"] == "git-log")
    argv, err = api._resolve_cmd_template(entry, {"count": "20"})
    assert err is None
    assert "-20" in argv


def test_resolve_template_substitutes_default():
    api = _load_dashboard_api()
    entry = next(c for c in api.TERMINAL_ALLOWLIST if c["id"] == "git-log")
    argv, err = api._resolve_cmd_template(entry, {})
    assert err is None
    assert "-10" in argv  # default
