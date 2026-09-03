"""Regression guard: every hook payload conforms to the Claude Code contract.

The runtime only recognises an allowlisted set of top-level keys on hook
stdout; anything else — notably a bare ``{"additionalContext": ...}`` — is
an unrecognised key it silently ignores. Proven 2026-07-26: the
UserPromptSubmit entrypoint emitted the bare key since the v4.1.0 PR-6
consolidation, so [ARKA:ROUTE], [ARKA:WORKFLOW-REQUIRED] and the entire
Synapse block were computed and discarded on every turn. These tests pin
every entrypoint, and the shell/PowerShell wrappers, to the accepted shape
so the bug class cannot be reintroduced in core/hooks or config/hooks.

Runtime Sync PR1 (2.1.248 contract): stdout is parsed as ONE JSON object
when it starts with ``{`` and ends with ``}``. Two lines that each set a
field are a parse failure — reported as a hook error, and on SessionStart
and UserPromptSubmit the text is NOT added as context (before 2.1.248 it
was treated as plain text). So every emitting entrypoint must print
exactly one document, and every stdout path — including the ones the
minimal fixtures never reach (PreToolUse deny, Stop reviewer notices) —
is pinned below. Mutation-proven: a truncated ``json.dumps`` or a second
emission fails these tests.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import ClassVar

import pytest
from hook_shell import BASH

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
        # Degraded/forced fallback is the only PowerShell-side emitter —
        # the real payload comes from core.hooks.user_prompt_submit.
        '"hookEventName": "UserPromptSubmit"',
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


def _assert_single_document(stdout: str, event_name: str) -> dict:
    """The whole stdout must be one JSON object (2.1.248 contract).

    The runtime does not read line by line: a stdout of two objects that
    each set a field is a parse failure, so ``json.loads`` over the full
    text — not over each line — is the assertion that matches it.
    """
    lines = [line for line in stdout.strip().splitlines() if line.strip()]
    assert len(lines) == 1, (
        f"expected exactly one JSON document on stdout for {event_name}, "
        f"got {len(lines)} non-empty lines: {lines!r}"
    )
    payload = json.loads(stdout.strip())
    assert isinstance(payload, dict), f"stdout is not a JSON object: {stdout!r}"
    _assert_payload_shape(lines[0], event_name)
    return payload


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

    def test_pre_tool_use_deny_payload_shape(self, capsys):
        """PreToolUse's only stdout path is the deny payload. The
        subprocess fixture takes the silent path (a Read is never gated),
        so the emitter is pinned here — a broken ``json.dumps`` in
        ``emit_deny_json`` fails this test, and so does a second line.
        """
        import core.hooks.pre_tool_use as ptu

        reason = "KB-first: consult the vault before external research"
        rc = ptu._deny(reason)
        assert rc == 2, "a deny also exits 2: stderr blocks even where the JSON is unparsed"
        captured = capsys.readouterr()
        payload = _assert_single_document(captured.out, "PreToolUse")
        hso = payload["hookSpecificOutput"]
        assert hso["permissionDecision"] == "deny"
        assert hso["permissionDecisionReason"] == reason
        assert captured.err.strip() == reason, "stderr carries the human reason"

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
        payload = _assert_single_document(result.stdout, event_name)
        assert (
            payload.get("hookSpecificOutput", {}).get("hookEventName") == event_name
        ), (
            f"{module} never emitted hookSpecificOutput with "
            f"hookEventName={event_name!r} — the declared event went "
            "unasserted (vacuous case)"
        )

    def test_stop_relays_reviewer_notices_as_one_document(
        self, contract_home, monkeypatch
    ):
        """Stop's only stdout path — reviewer notices queued at SubagentStop.

        The parametrized fixture cannot reach it (nothing queued → silent),
        so the emitter would go unexercised. Seed a notice through the
        ledger API under the contract HOME — the WRITER is redirected, HOME
        is not monkeypatched in-process (import-time ``Path.home()``
        constants elsewhere would be poisoned) — then run the entrypoint
        for real with HOME pointed at the same tree.
        """
        from core.governance import reviewer_ledger

        session_id = "contract-stop-notice"
        ledger_root = contract_home / ".arkaos" / "quality-gate"
        monkeypatch.setattr(reviewer_ledger, "ledger_root", lambda: ledger_root)
        nudge = "QA nudge: route the deliverable through the Quality Gate"
        reviewer_ledger.queue_notice(session_id, None, nudge)
        assert (ledger_root / session_id / "NOTICES.jsonl").is_file(), (
            "the seed never landed — the test would go vacuous"
        )

        result = _run_module(
            "core.hooks.stop",
            {"session_id": session_id, "transcript_path": ""},
            contract_home,
        )
        assert result.returncode == 0, result.stderr
        payload = _assert_single_document(result.stdout, "Stop")
        hso = payload["hookSpecificOutput"]
        assert hso["hookEventName"] == "Stop"
        assert nudge in hso["additionalContext"]


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

    Both directions test the same predicate — ``_delegates_to`` — and it
    matches the INVOCATION, never the bare module name. A substring search
    cannot tell delegation from discussion: a wrapper that merely mentions
    ``core.hooks.stop`` in a comment satisfies the positive assertion while
    delegating nothing, and, in the other direction, documenting the module
    a file does NOT delegate to breaks the inverted guard for no reason.
    Both failures were live: the second landed as a cross-PR test break the
    moment a comment in stop.ps1 named the module its own guard forbids.
    """

    # Twins whose .sh delegates the whole event to one python module. Both
    # sides must name that module — that is the parity contract.
    DELEGATING_TWINS: ClassVar[dict[str, str]] = {
        "session-start": "core.hooks.session_start",
        "session-end": "core.hooks.session_end",
        "subagent-stop": "core.hooks.subagent_stop",
        "user-prompt-submit": "core.hooks.user_prompt_submit",
    }

    # Known drift, recorded rather than hidden. These .ps1 files do call
    # Python, but through inline scripts against specific functions instead
    # of delegating the event to the module its .sh twin uses. They are a
    # different architecture, not a missing one, so failing CI on them today
    # would block unrelated work — but leaving them undocumented is how the
    # session-start drift survived. Moving one of these into
    # DELEGATING_TWINS is the definition of done for porting it.
    KNOWN_DRIFTED_TWINS: ClassVar[dict[str, str]] = {
        "pre-tool-use": "core.hooks.pre_tool_use",
        "post-tool-use": "core.hooks.post_tool_use",
        "stop": "core.hooks.stop",
    }

    @staticmethod
    def _delegates_to(text: str, module: str) -> bool:
        """True when `text` actually runs `python -m <module>`.

        Two filters, because either alone is escapable. Comment lines go
        first — ``#`` opens a comment in PowerShell, in bash and in the
        Python here-strings these wrappers embed, so one rule covers all
        three. Then the survivors must carry the module behind ``-m``,
        which is the only shape that runs it. Prose about a module never
        matches; a real invocation always does, whatever else the file
        says about it.

        Deliberately parses no PowerShell. An AST-based strip would need
        pwsh installed, and a guard that skips wherever pwsh is absent is
        not a guard on the machines that run CI.
        """
        code = "\n".join(
            line for line in text.splitlines() if not line.lstrip().startswith("#")
        )
        return re.search(rf"-m\s+{re.escape(module)}(?![\w.])", code) is not None

    @pytest.mark.parametrize("stem,module", sorted(DELEGATING_TWINS.items()))
    def test_twins_delegate_to_the_same_producer(self, stem, module):
        sh_path = HOOKS_SH_DIR / f"{stem}.sh"
        ps1_path = HOOKS_SH_DIR / f"{stem}.ps1"
        if not ps1_path.is_file():
            pytest.skip(f"{stem}.ps1 not shipped")

        sh_text = sh_path.read_text(encoding="utf-8", errors="replace")
        ps1_text = ps1_path.read_text(encoding="utf-8", errors="replace")

        assert self._delegates_to(sh_text, module), (
            f"{sh_path.name} no longer runs `-m {module}` — update this "
            "test deliberately, or the twin contract is meaningless"
        )
        assert self._delegates_to(ps1_text, module), (
            f"{ps1_path.name} does not run `-m {module}` while its .sh "
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
        assert not self._delegates_to(ps1_text, module), (
            f"{ps1_path.name} now runs `-m {module}` — move '{stem}' from "
            "KNOWN_DRIFTED_TWINS to DELEGATING_TWINS so the parity contract "
            "starts guarding it"
        )

    def test_delegation_predicate_reads_invocations_not_prose(self):
        """The predicate itself, pinned in both directions.

        Without this, `_delegates_to` is only ever exercised on files that
        happen to agree with it, and the substring guard it replaced looked
        equally healthy right up to the release where a comment broke it.
        """
        module = "core.hooks.stop"
        # Prose is not delegation — in any of the three comment dialects.
        assert not self._delegates_to("# core.hooks.stop, which runs a lot", module)
        assert not self._delegates_to("  # python -m core.hooks.stop (the twin)", module)
        assert not self._delegates_to('"""Mirror of core.hooks.stop._write."""', module)
        assert not self._delegates_to("import core.hooks.stop", module)
        # A longer module name must not satisfy a shorter one.
        assert not self._delegates_to("python -m core.hooks.stop_governance", module)
        # Delegation is delegation, in either language, however spelled.
        assert self._delegates_to('"$ARKA_PY" -m core.hooks.stop', module)
        assert self._delegates_to("& $env:ARKA_PY -m core.hooks.stop", module)
        assert self._delegates_to("exec python3  -m core.hooks.stop\n", module)

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
            [BASH, str(HOOKS_SH_DIR / "user-prompt-submit.sh")],
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


DEGRADED_LOG_REL = Path(".arkaos") / "telemetry" / "hook-degraded.jsonl"


class TestDegradedTelemetryParity:
    """Three writers, one record (#502).

    The degraded-run telemetry has three independent implementations, one
    per surface: ``record_degraded()`` in core/hooks/_shared.py,
    ``arka_hook_degraded()`` in config/hooks/_lib/arka_python.sh, and
    ``recordDegraded()`` in the Node fast-path shim that a POSIX install
    actually registers. They append to the SAME file, so a reader consumes
    all three interchangeably — and any drift between them surfaces as a
    parse error or a missing field, in production, months later.

    This is the twin-parity problem of TestTwinWrapperParity one level
    down, and it is guarded the same way: not by grepping three languages
    for a shape, but by RUNNING each writer against a sandboxed HOME and
    comparing what lands on disk.
    """

    EXPECTED_KEYS: ClassVar[list[str]] = ["ts", "hook", "reason", "detail"]
    TS_RE: ClassVar[re.Pattern] = re.compile(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z"
    )

    @staticmethod
    def _lines(home: Path) -> list[str]:
        path = home / DEGRADED_LOG_REL
        if not path.is_file():
            return []
        return [
            line for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    @staticmethod
    def _emit_python(home: Path) -> subprocess.CompletedProcess:
        env = dict(os.environ)
        env.update({
            "HOME": str(home), "USERPROFILE": str(home),
            "PYTHONPATH": str(REPO_ROOT),
        })
        return subprocess.run(
            [sys.executable, "-c",
             "from core.hooks._shared import record_degraded;"
             "record_degraded('pre-tool-use', 'parity', 'from python')"],
            capture_output=True, text=True, timeout=30, env=env, check=False,
        )

    @staticmethod
    def _emit_shell(home: Path) -> subprocess.CompletedProcess:
        env = dict(os.environ)
        env.update({"HOME": str(home), "USERPROFILE": str(home)})
        lib = HOOKS_SH_DIR / "_lib" / "arka_python.sh"
        return subprocess.run(
            [BASH, "-c",
             f'. "{lib}"\n'
             'arka_hook_degraded "pre-tool-use" "parity" "from shell"\n'],
            capture_output=True, text=True, timeout=30, env=env, check=False,
        )

    @staticmethod
    def _emit_node(home: Path, tmp_path: Path) -> subprocess.CompletedProcess:
        """Drive the real shim into its delegate-target-missing fail-open.

        The shim is copied WITHOUT its sibling .sh, which is the deployed
        state this branch exists for; the kill switch sends it straight to
        delegate() so no manifest or engine is needed. Nothing is stubbed —
        the line under test is written by the shipped code path.
        """
        lonely = tmp_path / "lonely-hooks"
        lonely.mkdir(exist_ok=True)
        shutil.copy(HOOKS_SH_DIR / "pre-tool-use.cjs", lonely / "pre-tool-use.cjs")
        return subprocess.run(
            ["node", str(lonely / "pre-tool-use.cjs")],
            input="{}", capture_output=True, text=True, timeout=30, check=False,
            env={
                "PATH": os.environ.get("PATH", ""),
                "HOME": str(home),
                "ARKA_HOOK_FASTPATH": "0",
            },
        )

    def _emit(self, surface: str, home: Path, tmp_path: Path):
        if surface == "python":
            return self._emit_python(home)
        if surface == "shell":
            return self._emit_shell(home)
        if shutil.which("node") is None:
            pytest.skip("node not available — cannot execute the .cjs writer")
        return self._emit_node(home, tmp_path)

    @pytest.mark.parametrize("surface", ["python", "shell", "node"])
    def test_each_writer_emits_the_same_record_shape(self, surface, tmp_path):
        home = tmp_path / f"home-{surface}"
        home.mkdir()

        result = self._emit(surface, home, tmp_path)

        assert result.returncode == 0, result.stderr
        lines = self._lines(home)
        assert len(lines) == 1, f"{surface} wrote {len(lines)} lines, expected 1"
        record = json.loads(lines[0])
        assert list(record) == self.EXPECTED_KEYS, (
            f"{surface} emits {list(record)} — the three writers append to one "
            "file, so a reader cannot tolerate a fourth shape"
        )
        assert record["hook"] == "pre-tool-use"
        assert self.TS_RE.fullmatch(record["ts"]), (
            f"{surface} ts={record['ts']!r} is not the shared UTC "
            "second-precision form"
        )
        assert isinstance(record["detail"], str)

    @pytest.mark.parametrize("surface", ["python", "shell", "node"])
    def test_no_writer_speaks_on_stdout_or_stderr(self, surface, tmp_path):
        # The rule that makes this telemetry safe to leave on: Claude Code
        # surfaces hook stderr to the user as an error, and stdout is the
        # hook's decision payload. A writer that touches either turns a
        # silent degradation into visible noise, or corrupts the decision.
        home = tmp_path / f"quiet-{surface}"
        home.mkdir()

        result = self._emit(surface, home, tmp_path)

        assert result.stdout == "", f"{surface} writer wrote to stdout"
        assert result.stderr == "", f"{surface} writer wrote to stderr"

    def test_all_three_writers_target_one_file(self, tmp_path):
        # Same HOME for all three: a reader tails ONE path, so three
        # records must land in one file, in order, one line each.
        home = tmp_path / "shared-home"
        home.mkdir()
        if shutil.which("node") is None:
            pytest.skip("node not available — cannot execute the .cjs writer")

        for surface in ("python", "shell", "node"):
            assert self._emit(surface, home, tmp_path).returncode == 0

        records = [json.loads(line) for line in self._lines(home)]
        assert len(records) == 3
        assert {r["detail"] for r in records} >= {"from python", "from shell"}
        assert all(list(r) == self.EXPECTED_KEYS for r in records)

    def test_powershell_chain_is_not_instrumented_and_the_scope_says_so(self):
        """Recorded deferral, made executable.

        pre-tool-use.ps1 is a PARALLEL chain, not a wrapper around an
        instrumented one: it embeds its own Python here-strings and never
        reaches record_degraded, arka_hook_degraded or the shim. Its
        fail-open exits are still silent — deliberately deferred, never
        quietly claimed as covered by a "cross-platform" telemetry.

        Inverted guard, in the shape of KNOWN_DRIFTED_TWINS above: whoever
        instruments the .ps1 gets a failure here pointing at the
        bookkeeping, so the deferral cannot outlive the debt it records.
        """
        text = (HOOKS_SH_DIR / "pre-tool-use.ps1").read_text(encoding="utf-8")
        for marker in ("hook-degraded", "arka_hook_degraded", "record_degraded"):
            assert marker not in text, (
                f"pre-tool-use.ps1 now carries {marker!r} — the Windows chain "
                "is being instrumented. Move it out of this guard and give it "
                "its own coverage instead of leaving a stale deferral here."
            )

        # PowerShell-level `exit 0` sites, counted so the deferral names a
        # size rather than gesturing at "Windows is out of scope":
        #   6 fail-open  — empty stdin, unparsable stdin, no interpreter,
        #                  missing enforcer, empty decision, unparsable
        #                  decision. Every one of these allows without the
        #                  gate chain ever deciding, and says nothing.
        #   2 decisions  — the non-flow-gated fast allow, and an enforcer
        #                  decision.allow. Correctly silent.
        # Three further import-failure allows live INSIDE the embedded
        # here-strings (sys.exit(0)), one per gate, and are equally silent.
        code = [
            line for line in text.splitlines()
            if not line.lstrip().startswith("#")
        ]
        exits = sum(len(re.findall(r"\bexit 0\b", line)) for line in code)
        assert exits == 8, (
            f"pre-tool-use.ps1 has {exits} `exit 0` sites, not the 8 this "
            "guard was written against (6 fail-open + 2 decisions). Re-classify "
            "the new one and update the count — an uncounted fail-open on "
            "Windows is exactly the silence #502 exists to end."
        )
        heredoc_exits = sum(
            len(re.findall(r"sys\.exit\(0\)", line)) for line in code
        )
        assert heredoc_exits == 3, (
            f"pre-tool-use.ps1 embeds {heredoc_exits} import-failure allows, "
            "not the 3 recorded here"
        )
