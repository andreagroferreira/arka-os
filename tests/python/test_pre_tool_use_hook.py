"""End-to-end hook tests for config/hooks/pre-tool-use.sh.

Pipes a realistic JSON payload through the bash hook and asserts that
nudge / deny behaviour surfaces correctly on stderr and stdout.

Also covers the shell half of the degraded-run telemetry (#502): the
wrapper's own fail-open exits, and arka_run_hook's rule for which exit
codes count as a degradation. The Python half lives in
tests/python/test_core_hooks_entrypoints.py; the cross-surface schema
parity is pinned in tests/python/test_hook_output_contract.py.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from hook_shell import BASH

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_PATH = REPO_ROOT / "config" / "hooks" / "pre-tool-use.sh"
LIB_PATH = REPO_ROOT / "config" / "hooks" / "_lib" / "arka_python.sh"


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
    (vault / "Laravel Service Pattern.md").write_text(
        "# Laravel Service Pattern\n", encoding="utf-8"
    )

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
        [BASH, str(HOOK_PATH)],
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


# ─── degraded-run telemetry, shell surface (#502) ────────────────────────

# POSIX-only, and not an omission. The subject of these tests is the .sh
# wrapper and its shared lib — the chain a POSIX install runs. Windows runs
# pre-tool-use.ps1, a parallel implementation that reaches none of this and
# is explicitly deferred (see TestDegradedTelemetryParity in
# tests/python/test_hook_output_contract.py). The fixtures below are POSIX
# constructs besides: a symlink farm, an exec bit, and PATH semantics that
# Git Bash on Windows does not reproduce. A manufactured red on the
# report-only Windows leg would teach reviewers to ignore that leg.
posix_only = pytest.mark.skipif(
    os.name != "posix", reason="POSIX wrapper; Windows runs the .ps1 chain"
)


def _degraded_lines(home: Path) -> list[dict]:
    """Parsed records from the shell writer, or [] when it wrote nothing.

    Parsed, never grepped: the shell builds this JSON with printf, so a
    record it cannot express correctly is a record nobody can read.
    """
    path = home / ".arkaos" / "telemetry" / "hook-degraded.jsonl"
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _bash(script: str, home: Path, extra_env: dict | None = None):
    env = dict(os.environ)
    env.update({"HOME": str(home), "USERPROFILE": str(home)})
    env.update(extra_env or {})
    return subprocess.run(
        [BASH, "-c", script],
        capture_output=True, text=True, timeout=30, env=env, check=False,
    )


def _stub_interpreter(tmp_path: Path, status: int) -> Path:
    """A fake $ARKA_PY that writes on both streams and exits `status`.

    Stands in for the real interpreter so the exit-code rule can be tested
    at every value that matters — 2 (deny) and 3 (crashed) are otherwise
    unreachable on demand.
    """
    stub = tmp_path / f"stub-py-{status}"
    stub.write_text(
        "#!/usr/bin/env bash\n"
        "printf 'stub-stdout'\n"
        "printf 'stub-stderr' >&2\n"
        f"exit {status}\n",
        encoding="utf-8",
    )
    stub.chmod(0o755)
    return stub


@posix_only
class TestArkaRunHookExitCodeRule:
    """Which exit codes are a degradation, and which are a decision.

    The distinction is the whole design: 0 and 2 are the documented allow
    and deny — a gate doing its job — while anything else means the
    entrypoint never got to decide. Recording a deny would bury the real
    signal under a line per blocked tool call; not recording a crash is the
    silence this telemetry exists to end.
    """

    @staticmethod
    def _run(tmp_path: Path, home: Path, status: int):
        stub = _stub_interpreter(tmp_path, status)
        return _bash(
            f'. "{LIB_PATH}"\n'
            f'ARKA_PY="{stub}"\n'
            'arka_run_hook "pre-tool-use" core.hooks.pre_tool_use\n'
            "exit $?\n",
            home,
        )

    @pytest.mark.parametrize("status", [0, 2])
    def test_decisions_are_not_recorded(self, tmp_path, status):
        home = tmp_path / "home"
        home.mkdir()
        result = self._run(tmp_path, home, status)
        assert result.returncode == status
        assert _degraded_lines(home) == [], (
            f"exit {status} is a decision, not a degradation"
        )

    @pytest.mark.parametrize("status", [1, 3])
    def test_failures_are_recorded(self, tmp_path, status):
        home = tmp_path / "home"
        home.mkdir()
        result = self._run(tmp_path, home, status)
        assert result.returncode == status, "the exit code passes through"
        lines = _degraded_lines(home)
        assert len(lines) == 1
        assert lines[0]["hook"] == "pre-tool-use"
        assert lines[0]["reason"] == "entrypoint-failed"
        assert f"exit={status}" in lines[0]["detail"]
        assert "core.hooks.pre_tool_use" in lines[0]["detail"]

    def test_recording_never_touches_the_child_streams(self, tmp_path):
        # The record is a side channel: stdout is the hook's decision
        # payload and stderr is what Claude Code shows the user, so the
        # telemetry must be invisible in both even when it fires.
        home = tmp_path / "home"
        home.mkdir()
        result = self._run(tmp_path, home, 1)
        assert result.stdout == "stub-stdout"
        assert result.stderr == "stub-stderr"


@posix_only
class TestArkaHookDegradedWriter:
    """The shell writer itself: JSON it emits by hand, and its growth cap."""

    def test_control_characters_do_not_break_the_json(self, tmp_path):
        # Regression pin for the PR review's probe: a tab or \001 in the
        # detail used to reach printf raw, and a raw control byte inside a
        # JSON string is a parse error — one degraded event carrying a
        # Python traceback poisoned the line for every reader.
        #
        # Written to a file rather than passed to `bash -c`: the payload is
        # a study in escaping, and a second quoting layer would make the
        # test prove things about the test harness instead of the writer.
        home = tmp_path / "home"
        home.mkdir()
        script = tmp_path / "emit.sh"
        script.write_text(
            f'. "{LIB_PATH}"\n'
            + r"""detail="$(printf 'want\tgot\001ctl\nline2 "q" back\\slash')"
arka_hook_degraded "pre-tool-use" "entrypoint-failed" "$detail"
""",
            encoding="utf-8",
        )

        result = _bash(f'"{BASH}" "{script}"', home)

        assert result.returncode == 0, result.stderr
        raw = (
            home / ".arkaos" / "telemetry" / "hook-degraded.jsonl"
        ).read_text(encoding="utf-8")
        assert raw.count("\n") == 1, "one event is one line"
        record = json.loads(raw)  # the assertion: it parses at all
        assert set(record) == {"ts", "hook", "reason", "detail"}
        # Control characters become spaces — translated, not deleted, so
        # "want" and "got" stay two tokens — while the quote and the
        # backslash survive intact through the hand-rolled JSON escaping.
        assert record["detail"] == 'want got ctl line2 "q" back\\slash'

    def test_rotates_once_past_the_cap(self, tmp_path):
        # This writer needs the cap more than the Python one: the cases it
        # records (no interpreter, missing entrypoint) fire on EVERY tool
        # call, so a broken machine writes a line per event indefinitely.
        home = tmp_path / "home"
        telemetry = home / ".arkaos" / "telemetry"
        telemetry.mkdir(parents=True)
        log = telemetry / "hook-degraded.jsonl"
        log.write_bytes(b"x" * (5 * 1024 * 1024))

        result = _bash(
            f'. "{LIB_PATH}"\n'
            'arka_hook_degraded "pre-tool-use" "after-rotation" "d"\n',
            home,
        )

        assert result.returncode == 0, result.stderr
        rotated = telemetry / "hook-degraded.jsonl.1"
        assert rotated.is_file(), "the oversized log is kept, not deleted"
        assert rotated.stat().st_size == 5 * 1024 * 1024
        assert [r["reason"] for r in _degraded_lines(home)] == ["after-rotation"]

    def test_does_not_rotate_below_the_cap(self, tmp_path):
        home = tmp_path / "home"
        telemetry = home / ".arkaos" / "telemetry"
        telemetry.mkdir(parents=True)
        log = telemetry / "hook-degraded.jsonl"
        log.write_bytes(b"x" * (5 * 1024 * 1024 - 1))
        _bash(
            f'. "{LIB_PATH}"\n'
            'arka_hook_degraded "pre-tool-use" "still-appending" "d"\n',
            home,
        )
        assert not (telemetry / "hook-degraded.jsonl.1").exists()


# Utilities the wrapper and the writer shell out to. A PATH holding these
# and nothing else is half of what makes the no-interpreter branch
# reachable: the resolver's last resort hands back the bare name `python3`,
# and only an absent `python3` makes the wrapper's `command -v` fail.
_SANDBOX_UTILS = ("date", "tr", "cut", "mkdir", "wc", "mv", "dirname", "cat")


def _no_usable_interpreter_env(tmp_path: Path, home: Path) -> dict:
    """An environment in which arka_resolve_python finds nothing runnable.

    Two halves, because the resolver is deliberately hard to starve. An
    empty-but-for-coreutils PATH removes the bare `python3` and `python`
    candidates, but the loop also probes ABSOLUTE paths (/opt/homebrew,
    /usr/local, /usr/bin) that `command -v` finds whatever PATH says. Those
    are eliminated by a broken PYTHONHOME, which makes every interpreter on
    the box abort during init — so each `import yaml` probe fails and the
    resolver falls through to its last resort, the bare name `python3` that
    the sandboxed PATH cannot find.

    The real resolver runs throughout: nothing here is stubbed, which is
    the point — this is the machine state (#502's motivating incident) of
    an install whose interpreter resolves to a name that cannot run.
    """
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    for name in _SANDBOX_UTILS:
        found = shutil.which(name)
        if found is None:
            pytest.skip(f"{name} not on PATH — cannot build a python-less PATH")
        target = bindir / name
        if not target.exists():
            target.symlink_to(found)
    assert shutil.which("python3", path=str(bindir)) is None
    return {
        "PATH": str(bindir),
        "PYTHONHOME": str(tmp_path / "no-such-pythonhome"),
        "HOME": str(home),
        "USERPROFILE": str(home),
        "ARKAOS_ROOT": str(REPO_ROOT),
    }


@posix_only
class TestWrapperFailOpenPaths:
    """The wrapper's own two silent exits, and the split-deploy stubs."""

    def test_missing_interpreter_is_recorded_and_still_allows(self, tmp_path):
        home = tmp_path / "home"
        home.mkdir()
        result = subprocess.run(
            [BASH, str(HOOK_PATH)],
            input=json.dumps({
                "tool_name": "Read", "session_id": "no-interp",
                "transcript_path": "", "cwd": "/tmp", "tool_input": {},
            }),
            capture_output=True, text=True, timeout=30, check=False,
            env=_no_usable_interpreter_env(tmp_path, home),
        )
        assert result.returncode == 0, "fail-open: no interpreter still allows"
        assert result.stdout == "", "an allow emits no stdout"
        lines = _degraded_lines(home)
        assert [r["reason"] for r in lines] == ["no-interpreter"]
        assert "ARKA_PY=" in lines[0]["detail"]

    def test_missing_entrypoint_is_recorded_and_still_allows(self, tmp_path):
        # The wrapper is copied out of the repo on purpose: in place, its
        # self-root fallback ($0/../..) finds the real core/hooks and the
        # branch is unreachable.
        hooks = tmp_path / "elsewhere" / "hooks"
        (hooks / "_lib").mkdir(parents=True)
        shutil.copy(HOOK_PATH, hooks / "pre-tool-use.sh")
        shutil.copy(LIB_PATH, hooks / "_lib" / "arka_python.sh")
        home = tmp_path / "home"
        home.mkdir()

        result = _bash(
            f'"{BASH}" "{hooks / "pre-tool-use.sh"}" '
            f'<<< \'{{"tool_name":"Read","session_id":"no-entry"}}\'',
            home,
            {"ARKAOS_ROOT": str(tmp_path / "not-arkaos")},
        )

        assert result.returncode == 0, result.stderr
        assert result.stdout == ""
        lines = _degraded_lines(home)
        assert [r["reason"] for r in lines] == ["entrypoint-missing"]
        assert str(tmp_path / "not-arkaos") in lines[0]["detail"]

    def test_split_deploy_without_the_lib_still_runs_the_hook(self, tmp_path):
        # Telemetry is an observer, never a dependency: a wrapper deployed
        # without _lib must fall back to no-op stubs and keep gating, not
        # die on `arka_run_hook: command not found`.
        hooks = tmp_path / "split" / "hooks"
        hooks.mkdir(parents=True)
        shutil.copy(HOOK_PATH, hooks / "pre-tool-use.sh")
        home = tmp_path / "home"
        (home / ".arkaos").mkdir(parents=True)
        (home / ".arkaos" / "config.json").write_text(
            json.dumps({"hooks": {"kbFirst": False, "hardEnforcement": False}}),
            encoding="utf-8",
        )

        result = _bash(
            f'"{BASH}" "{hooks / "pre-tool-use.sh"}" '
            f'<<< \'{{"tool_name":"Read","session_id":"split","tool_input":{{}}}}\'',
            home,
            {"ARKAOS_ROOT": str(REPO_ROOT)},
        )

        assert result.returncode == 0, result.stderr
        assert "command not found" not in result.stderr
        assert result.stdout == ""
