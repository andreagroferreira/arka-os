"""Regression guard: every hook payload conforms to the Claude Code contract.

The runtime only recognises an allowlisted set of top-level keys on hook
stdout; anything else — notably a bare ``{"additionalContext": ...}`` — is
an unrecognised key it silently ignores. Proven 2026-07-26: the
UserPromptSubmit entrypoint emitted the bare key since the v4.1.0 PR-6
consolidation, so [ARKA:ROUTE], [ARKA:WORKFLOW-REQUIRED] and the entire
Synapse block were computed and discarded on every turn. These tests pin
every entrypoint, and the shell/PowerShell wrappers, to the accepted shape
so the bug class cannot be reintroduced in core/hooks or config/hooks.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from core.hooks._shared import additional_context_payload, emit_additional_context

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_PY_DIR = REPO_ROOT / "core" / "hooks"
HOOKS_SH_DIR = REPO_ROOT / "config" / "hooks"

# The Claude Code hook-output surface, audited against the 2.1.220 binary
# (top-level zod schema `Uzg`: continue, suppressOutput, stopReason,
# decision, reason, systemMessage, terminalSequence, hookSpecificOutput;
# unioned with the async-marker variant {async, asyncTimeout}). A key
# outside this set is ignored by the runtime — emitting one is always
# a bug.
TOP_LEVEL_ALLOWLIST = {
    "hookSpecificOutput",
    "systemMessage",
    "continue",
    "stopReason",
    "suppressOutput",
    "decision",
    "reason",
    "terminalSequence",
    "async",
    "asyncTimeout",
}

# (module, expected hookEventName, minimal valid stdin payload, behaviour)
# behaviour "emits": the fixture payload must produce at least one JSON
# line, each shape-checked, and at least one line MUST carry
# hookSpecificOutput with the declared hookEventName — a declared event
# that is never asserted is a vacuous case. behaviour "empty-object": the
# fixture exercises the nothing-to-say path and must print exactly "{}"
# (post_tool_use's violation path is pinned separately, in-process, by
# TestHelperUnit.test_post_tool_use_violation_payload_shape). behaviour
# "silent": the fixture must produce NO stdout.
# NOTE session_end: the 2.1.220 hookSpecificOutput union has NO SessionEnd
# variant, so silence is that entrypoint's permanent contract — if it ever
# starts emitting context, the payload would be unreachable by design.
ENTRYPOINTS = [
    ("core.hooks.session_start", "SessionStart", {}, "emits"),
    (
        "core.hooks.user_prompt_submit",
        "UserPromptSubmit",
        {"userInput": "hello there", "session_id": "contract-ups"},
        "emits",
    ),
    (
        "core.hooks.pre_tool_use",
        "PreToolUse",
        {
            "tool_name": "Read", "session_id": "contract-pre",
            "transcript_path": "", "cwd": "/tmp", "tool_input": {},
        },
        "silent",
    ),
    (
        "core.hooks.post_tool_use",
        "PostToolUse",
        {
            "tool_name": "Read", "session_id": "contract-post",
            "transcript_path": "", "cwd": "/tmp",
            "tool_input": {}, "tool_output": "",
        },
        "empty-object",
    ),
    (
        "core.hooks.subagent_stop",
        "SubagentStop",
        {"session_id": "contract-sas", "transcript_path": ""},
        "silent",
    ),
    (
        "core.hooks.stop",
        "Stop",
        {"session_id": "contract-stop", "transcript_path": ""},
        "silent",
    ),
    (
        "core.hooks.session_end",
        "SessionEnd",
        {"session_id": "contract-end", "transcript_path": ""},
        "silent",
    ),
]

# Positive shape expectation per PowerShell wrapper, anchored PER EMITTER
# (a whole-file substring can be satisfied by the wrong occurrence —
# user-prompt-submit.ps1 has two emitters and each must carry the nested
# shape independently). cwd-changed.ps1 emits top-level systemMessage
# only (CwdChanged accepts no additionalContext).
PS1_EXPECTED_MARKERS = {
    "user-prompt-submit.ps1": [
        # v1-migration early-exit emitter
        "hookEventName = 'UserPromptSubmit'; additionalContext = $msg",
        # main emitter
        "hookEventName = 'UserPromptSubmit'; additionalContext = $additionalContext",
    ],
    "cwd-changed.ps1": [
        "systemMessage = $context",
    ],
}


def _run_module(module: str, payload: dict, home: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.update({
        "HOME": str(home),
        "ARKAOS_ROOT": str(REPO_ROOT),
        "PYTHONPATH": str(REPO_ROOT),
    })
    for bypass in ("ARKA_BYPASS_KB_FIRST", "ARKA_BYPASS_FLOW"):
        env.pop(bypass, None)
    return subprocess.run(
        [sys.executable, "-m", module],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
        check=False,
    )


@pytest.fixture
def contract_home(tmp_path):
    home = tmp_path / "home"
    (home / ".arkaos").mkdir(parents=True)
    (home / ".arkaos" / "config.json").write_text(
        json.dumps({"hooks": {"kbFirst": True, "hardEnforcement": False}}),
        encoding="utf-8",
    )
    return home


def _assert_payload_shape(line: str, event_name: str) -> None:
    payload = json.loads(line)
    assert isinstance(payload, dict), f"hook stdout is not a JSON object: {line!r}"
    unknown = set(payload) - TOP_LEVEL_ALLOWLIST
    assert not unknown, (
        f"top-level keys the runtime ignores: {sorted(unknown)} — "
        "context must ride inside hookSpecificOutput.additionalContext"
    )
    assert "additionalContext" not in payload, (
        "bare top-level additionalContext is silently discarded by Claude "
        "Code — wrap it in hookSpecificOutput with a hookEventName"
    )
    hso = payload.get("hookSpecificOutput")
    if hso is not None:
        assert hso.get("hookEventName") == event_name, (
            f"hookEventName mismatch: expected {event_name!r}, "
            f"payload was {payload!r}"
        )


class TestHelperUnit:
    """In-process coverage of the single construction site."""

    def test_payload_shape(self):
        payload = additional_context_payload("UserPromptSubmit", "ctx")
        assert payload == {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": "ctx",
            }
        }

    def test_no_top_level_additional_context(self):
        payload = additional_context_payload("PostToolUse", "ctx")
        assert "additionalContext" not in payload
        assert set(payload) <= TOP_LEVEL_ALLOWLIST

    def test_emit_prints_one_json_line(self, capsys):
        emit_additional_context("SubagentStop", "nudge text")
        out = capsys.readouterr().out.strip().splitlines()
        assert len(out) == 1, f"expected exactly one stdout line, got {out!r}"
        _assert_payload_shape(out[0], "SubagentStop")

    def test_post_tool_use_violation_payload_shape(self, monkeypatch, capsys):
        """Pins the PostToolUse additionalContext at runtime.

        The subprocess fixture only exercises the nothing-to-say "{}"
        path, and the source greps cannot see an emitter built through a
        variable — this is the test that goes red if the violation
        emitter regresses to the bare shape (proven gap: a
        dict(additionalContext=...) mutation stayed green before it).
        """
        import core.hooks.post_tool_use as ptu

        for side_effect in (
            "_confirm_flow_authorization",
            "_record_cqo_rejected",
            "_record_pattern_stub",
            "_record_activation",
            "_store_gotcha",
            "_enqueue_cognition_capture",
            "_log_metrics",
        ):
            monkeypatch.setattr(ptu, side_effect, lambda *a, **k: None)
        monkeypatch.setattr(
            ptu, "_detect_rule_violations",
            lambda payload: ("VIOLATION [test-rule]: pinned", []),
        )
        monkeypatch.setattr(
            ptu, "_workflow_sections_with_fallback",
            lambda payload, root, persist, msg: msg,
        )
        rc = ptu.main({
            "tool_name": "Bash", "session_id": "contract-post-violation",
            "transcript_path": "", "cwd": "/tmp",
            "tool_input": {"command": "boom"},
            "tool_response": {"stdout": "", "stderr": "error: something broke"},
        })
        assert rc == 0
        lines = capsys.readouterr().out.strip().splitlines()
        assert len(lines) == 1, f"expected one payload line, got {lines!r}"
        _assert_payload_shape(lines[0], "PostToolUse")
        hso = json.loads(lines[0])["hookSpecificOutput"]
        assert hso["hookEventName"] == "PostToolUse"
        assert hso["additionalContext"] == "VIOLATION [test-rule]: pinned"

    def test_failure_event_violation_echoes_its_own_event_name(
        self, monkeypatch, capsys
    ):
        """A violation on a PostToolUseFailure turn must carry THAT event
        name — the runtime drops context whose hookEventName differs
        from the event it invoked (live probe, QG round 3).
        """
        import core.hooks.post_tool_use as ptu

        for side_effect in (
            "_confirm_flow_authorization",
            "_record_cqo_rejected",
            "_record_pattern_stub",
            "_record_activation",
            "_store_gotcha",
            "_enqueue_cognition_capture",
            "_log_metrics",
        ):
            monkeypatch.setattr(ptu, side_effect, lambda *a, **k: None)
        monkeypatch.setattr(
            ptu, "_detect_rule_violations",
            lambda payload: ("VIOLATION [test-rule]: failure-turn", []),
        )
        monkeypatch.setattr(
            ptu, "_workflow_sections_with_fallback",
            lambda payload, root, persist, msg: msg,
        )
        rc = ptu.main({
            "hook_event_name": "PostToolUseFailure",
            "tool_name": "Edit", "session_id": "contract-failure-violation",
            "transcript_path": "", "cwd": "/tmp",
            "tool_input": {"file_path": "/app/x.py"},
            "error": "String to replace not found in file.",
            "is_interrupt": False,
        })
        assert rc == 0
        lines = capsys.readouterr().out.strip().splitlines()
        assert len(lines) == 1, f"expected one payload line, got {lines!r}"
        _assert_payload_shape(lines[0], "PostToolUseFailure")
        hso = json.loads(lines[0])["hookSpecificOutput"]
        assert hso["hookEventName"] == "PostToolUseFailure"
        assert hso["additionalContext"] == "VIOLATION [test-rule]: failure-turn"


class TestPythonEntrypoints:
    @pytest.mark.parametrize(
        "module,event_name,payload,behaviour",
        ENTRYPOINTS,
        ids=[m for m, _, _, _ in ENTRYPOINTS],
    )
    def test_stdout_shape(
        self, contract_home, module, event_name, payload, behaviour
    ):
        result = _run_module(module, payload, contract_home)
        assert result.returncode == 0, result.stderr
        lines = [
            line for line in result.stdout.strip().splitlines() if line.strip()
        ]
        if behaviour == "silent":
            assert not lines, (
                f"{module} was expected to stay silent under this fixture "
                f"but emitted: {lines!r}"
            )
            return
        if behaviour == "empty-object":
            assert lines == ["{}"], (
                f"{module} was expected to print exactly '{{}}' under this "
                f"fixture but emitted: {lines!r}"
            )
            return
        assert lines, f"{module} emitted nothing — the case went vacuous"
        for line in lines:
            _assert_payload_shape(line, event_name)
        assert any(
            json.loads(line).get("hookSpecificOutput", {}).get("hookEventName")
            == event_name
            for line in lines
        ), (
            f"{module} never emitted hookSpecificOutput with "
            f"hookEventName={event_name!r} — the declared event went "
            "unasserted (vacuous case)"
        )


class TestSourceGuards:
    def test_no_bare_additional_context_in_python_hooks(self):
        pattern = re.compile(r"json\.dumps\(\s*\{\s*[\"']additionalContext[\"']")
        offenders = [
            f"{path.name}: {match.group(0)!r}"
            for path in sorted(HOOKS_PY_DIR.glob("*.py"))
            for match in [pattern.search(path.read_text(encoding="utf-8"))]
            if match
        ]
        assert not offenders, (
            f"bare additionalContext emitters in core/hooks: {offenders}"
        )

    def test_no_bare_additional_context_in_shell_wrappers(self):
        # Catches the literal fallback strings, the jq envelopes, and the
        # PowerShell pscustomobject shape — how the bug survived in the
        # wrappers after the Python consolidation fixed nothing here.
        patterns = [
            re.compile(r"\{\s*\"additionalContext\""),   # sh JSON literals
            re.compile(r"\{additionalContext:"),          # jq object syntax
            re.compile(r"@\{\s*additionalContext\s*="),   # ps1 pscustomobject
        ]
        offenders = []
        for suffix in ("*.sh", "*.ps1", "*.cjs"):
            for path in sorted(HOOKS_SH_DIR.rglob(suffix)):
                text = path.read_text(encoding="utf-8", errors="replace")
                for pattern in patterns:
                    if pattern.search(text):
                        offenders.append(f"{path.relative_to(REPO_ROOT)}")
                        break
        assert not offenders, (
            f"bare additionalContext emitters in config/hooks: {offenders}"
        )

    def test_ps1_wrappers_carry_the_expected_shape(self):
        # Positive assertion (the negative greps above cannot see an
        # emitter built through a variable): each emitter in each .ps1
        # must carry the nested shape independently — anchored per
        # emitter, so the wrong occurrence cannot satisfy the check.
        # Reviewed by source only — pwsh is not guaranteed here.
        for name, markers in PS1_EXPECTED_MARKERS.items():
            text = (HOOKS_SH_DIR / name).read_text(encoding="utf-8")
            for marker in markers:
                assert marker in text, (
                    f"{name} no longer carries {marker!r} — an emitter's "
                    "payload shape changed without updating this test"
                )


class TestTwinWrapperParity:
    """Guards against twin drift between the .sh and .ps1 wrappers.

    A wrapper pair drifts silently: both run, both exit 0, both emit valid
    JSON — and one of them quietly stops carrying half the payload. That is
    exactly how session-start.ps1 spent releases emitting only the banner
    while session-start.sh delegated to Python and shipped the four
    operating contracts (EVIDENCE-FLOW, META-TAG, AUTHORITY, MODEL-FABRIC)
    to the model. A source diff of the two files would not have caught it:
    they are different languages and were never meant to match line for
    line. What must match is the *producer they delegate to*.
    """

    # Twins whose .sh delegates the whole event to one python module. Both
    # sides must name that module — that is the parity contract.
    DELEGATING_TWINS = {
        "session-start": "core.hooks.session_start",
        "session-end": "core.hooks.session_end",
        "subagent-stop": "core.hooks.subagent_stop",
    }

    # Known drift, recorded rather than hidden. These .ps1 files do call
    # Python, but through inline scripts against specific functions instead
    # of delegating the event to the module its .sh twin uses. They are a
    # different architecture, not a missing one, so failing CI on them today
    # would block unrelated work — but leaving them undocumented is how the
    # session-start drift survived. Moving one of these into
    # DELEGATING_TWINS is the definition of done for porting it.
    KNOWN_DRIFTED_TWINS = {
        "pre-tool-use": "core.hooks.pre_tool_use",
        "post-tool-use": "core.hooks.post_tool_use",
        "stop": "core.hooks.stop",
        "user-prompt-submit": "core.hooks.user_prompt_submit",
    }

    @pytest.mark.parametrize("stem,module", sorted(DELEGATING_TWINS.items()))
    def test_twins_delegate_to_the_same_producer(self, stem, module):
        sh_path = HOOKS_SH_DIR / f"{stem}.sh"
        ps1_path = HOOKS_SH_DIR / f"{stem}.ps1"
        if not ps1_path.is_file():
            pytest.skip(f"{stem}.ps1 not shipped")

        sh_text = sh_path.read_text(encoding="utf-8", errors="replace")
        ps1_text = ps1_path.read_text(encoding="utf-8", errors="replace")

        assert module in sh_text, (
            f"{sh_path.name} no longer delegates to {module} — update this "
            "test deliberately, or the twin contract is meaningless"
        )
        assert module in ps1_text, (
            f"{ps1_path.name} does not delegate to {module} while its .sh "
            f"twin does. This is the session-start failure mode: the "
            f"PowerShell side reimplements part of the payload, drifts as "
            f"the producer evolves, and silently ships less context to the "
            f"model on Windows. Delegate to {module} instead of porting the "
            "payload."
        )

    @pytest.mark.parametrize("stem,module", sorted(KNOWN_DRIFTED_TWINS.items()))
    def test_known_drift_is_still_drifted(self, stem, module):
        # Inverted guard: when someone ports one of these, this test fails
        # and points at the bookkeeping. Prevents the allowlist from
        # outliving the debt it records.
        ps1_path = HOOKS_SH_DIR / f"{stem}.ps1"
        if not ps1_path.is_file():
            pytest.skip(f"{stem}.ps1 not shipped")
        ps1_text = ps1_path.read_text(encoding="utf-8", errors="replace")
        assert module not in ps1_text, (
            f"{ps1_path.name} now delegates to {module} — move '{stem}' from "
            "KNOWN_DRIFTED_TWINS to DELEGATING_TWINS so the parity contract "
            "starts guarding it"
        )

    def test_session_start_ps1_does_not_rebuild_the_banner(self):
        # Narrow regression pin for the bug this class was written for: the
        # old .ps1 read profile.json and laid out the box itself. A wrapper
        # that reads the profile is a wrapper that has started reimplementing
        # the producer again.
        text = (HOOKS_SH_DIR / "session-start.ps1").read_text(encoding="utf-8")
        assert "profile.json" not in text, (
            "session-start.ps1 reads profile.json again — the banner is "
            "built by core.hooks.session_start, not by the wrapper"
        )


class TestShellFallbackParity:
    def test_user_prompt_submit_fallback_shape(self, contract_home):
        env = dict(os.environ)
        env.update({
            "HOME": str(contract_home),
            "ARKAOS_ROOT": str(REPO_ROOT),
            "ARKA_HOOK_FORCE_FALLBACK": "1",
        })
        result = subprocess.run(
            ["bash", str(HOOKS_SH_DIR / "user-prompt-submit.sh")],
            input=json.dumps({"userInput": "hello"}),
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        line = result.stdout.strip().splitlines()[0]
        _assert_payload_shape(line, "UserPromptSubmit")
        payload = json.loads(line)
        assert "[Constitution]" in (
            payload["hookSpecificOutput"]["additionalContext"]
        )
