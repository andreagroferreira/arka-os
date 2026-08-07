"""Drift guard: the Windows Stop hook must RUN what `stop.py` runs.

``config/hooks/stop.sh`` delegates the whole Stop event to
``core.hooks.stop``. The PowerShell port reimplements the event, so every
module the Python entrypoint gains has to be mirrored by hand -- and
silently was not: four warn-only detectors, including ``skill_proposer``
(constitution rule ``mandatory-skill-evaluation``), existed and were
wired on POSIX while never running on Windows.

WHY THIS FILE WAS REWRITTEN. Its first version asserted that module NAMES
appeared as substrings of ``stop.ps1``. A name in a comment satisfies
that. Proven by mutation: with every governance call destroyed --
``_eval_skill(last)`` replaced by ``pass``, the other three imports
replaced by ``raise ImportError`` -- and every name left in place, all
five tests passed. The file claimed "These tests fail when that gap
reopens"; it failed only when someone DELETED a string, never when
someone broke the code.

The sweep is now a module (``core.hooks.stop_governance``), so the guard
can do what a text search never could: import it, substitute each
detector, and assert each one is actually reached. What remains textual
is only the one thing that is genuinely text -- that ``stop.ps1``
delegates with ``-m``, matched as an invocation and not as a mention.
"""

from __future__ import annotations

import os
import re
import stat
from pathlib import Path

import pytest

from core.hooks import stop as stop_hook
from core.hooks import stop_governance

REPO_ROOT = Path(__file__).resolve().parents[2]
STOP_PS1 = REPO_ROOT / "config" / "hooks" / "stop.ps1"
STOP_PY = REPO_ROOT / "core" / "hooks" / "stop.py"

SWEEP_MODULE = "core.hooks.stop_governance"

# Warn-only detectors: they emit proposals or diagnostic state and nothing
# reads their output to gate anything. These MUST run in the port.
OBSERVED_IN_PS1 = {name for name, _ in stop_governance.DETECTORS}

# Modules the port deliberately does NOT run, each with the reason it is
# deferred. A dict and not a set on purpose: the previous version gave one
# blanket reason ("they feed enforcement surfaces") that was false for two
# of the seven -- stop_lint and routing_feedback gate nothing, they are
# detached background spawns. An unexplained entry is how a deferral
# becomes permanent, so every value is asserted non-empty below.
DEFERRED_IN_PS1: dict[str, str] = {
    "core.governance.reviewer_ledger": (
        "Drains QG reviewer notices into the hook's OUTPUT surface. This "
        "port writes no hook output at all, so mirroring it needs the "
        "emit-context contract first."
    ),
    "core.governance.closing_marker_check": (
        "Enforcement surface: feeds the closing-marker soft-block. Needs "
        "its own Windows baseline before it can start nagging operators."
    ),
    "core.governance.meta_tag_check": (
        "Enforcement surface: [arka:meta] transparency-tag compliance."
    ),
    "core.governance.kb_cite_check": (
        "Enforcement surface: KB citation soft-block."
    ),
    "core.governance.dna_fidelity": (
        "Enforcement surface: agent DNA fidelity scoring on the closing "
        "message."
    ),
    "core.governance.stop_lint": (
        "NOT an enforcement surface. stop.py spawns a DETACHED scoped lint "
        "batch (subprocess.Popen(..., start_new_session=True)) that writes "
        "stop-lint.jsonl telemetry. The port has no detached-spawn "
        "equivalent, and running it inline would put a lint batch on the "
        "hook's budget."
    ),
    "core.governance.routing_feedback": (
        "NOT an enforcement surface. stop.py checks staleness and then "
        "spawns a DETACHED rebuild of routing-scores.json, consumed by "
        "core/synapse/routing_feedback_layer.py. Same detached-spawn gap "
        "as stop_lint."
    ),
}


def _ps1_text() -> str:
    return STOP_PS1.read_text(encoding="utf-8")


def _invokes(text: str, module: str) -> bool:
    """True when `text` actually runs `python -m <module>`.

    Comment lines go first -- ``#`` opens a comment in PowerShell, in bash
    and in Python -- then the survivors must carry the module behind
    ``-m``, the only shape that runs it. Prose about a module never
    matches; a real invocation always does.

    Twin of ``TestTwinWrapperParity._delegates_to`` in
    ``test_hook_output_contract.py``. Deliberately parses no PowerShell:
    an AST strip would need pwsh installed, and a guard that skips
    wherever pwsh is absent is not a guard on the machines running CI.
    """
    code = "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )
    return re.search(rf"-m\s+{re.escape(module)}(?![\w.])", code) is not None


def _governance_modules_in_stop_py() -> set[str]:
    text = STOP_PY.read_text(encoding="utf-8")
    return set(re.findall(r"from (core\.governance\.[a-z_]+) import", text))


# ── The port delegates, and the delegation is real ────────────────────────


def test_ps1_delegates_the_sweep_to_the_real_module() -> None:
    assert _invokes(_ps1_text(), SWEEP_MODULE), (
        f"stop.ps1 no longer runs `-m {SWEEP_MODULE}`. The sweep must be "
        "delegated, not inlined: an inline copy is unreachable by every "
        "linter and by this test."
    )


def test_the_sweep_is_not_reinlined_as_a_here_string() -> None:
    """The shape this file was rewritten to prevent coming back.

    A here-string full of governance imports is exactly the artefact that
    lost the umask hardening and defeated the old guard.
    """
    text = _ps1_text()
    assert "$governanceScript" not in text, (
        "the governance sweep is inline again — delegate to "
        f"{SWEEP_MODULE} instead"
    )
    inlined = sorted(
        m for m in OBSERVED_IN_PS1
        if re.search(rf"^\s*from {re.escape(m)} import", text, re.MULTILINE)
    )
    assert not inlined, f"detectors imported inline in stop.ps1: {inlined}"


def test_governance_block_cannot_break_the_hook() -> None:
    """The delegation stays fire-and-forget, like its two siblings."""
    text = _ps1_text()
    marker = f"-m {SWEEP_MODULE}"
    assert marker in text, (
        f"no `{marker}` in stop.ps1 — see "
        "test_ps1_delegates_the_sweep_to_the_real_module"
    )
    tail = text.split(marker, 1)[1]
    assert "catch {" in tail, (
        "the governance delegation must sit inside try/catch so a detector "
        "failure never affects the Stop hook"
    )


# ── The sweep actually runs every detector it claims ──────────────────────


# The public entry point each detector MUST call. Patched on the
# governance module itself -- the detectors import lazily, at call time,
# so a substitution here is seen by the real code path.
#
# This table is what makes the guard bite. Substituting the detector
# FUNCTION only proves run() iterates its table; it survives a detector
# whose body has been replaced by `pass`, which is precisely the mutation
# that defeated the previous version of this file. Patching the module
# entry point instead means a neutered detector never calls through and
# fails below.
DETECTOR_ENTRY_POINTS = {
    "core.governance.skill_proposer": "evaluate",
    "core.governance.sycophancy_detector": "detect_sycophancy",
    "core.governance.phantom_action_check": "check_phantom_actions",
    "core.governance.tool_loop_check": "check_tool_loops",
}


def test_entry_point_table_covers_every_observed_detector() -> None:
    """Neither table may grow without the other."""
    assert set(DETECTOR_ENTRY_POINTS) == OBSERVED_IN_PS1, (
        "DETECTOR_ENTRY_POINTS and stop_governance.DETECTORS disagree; a "
        "detector with no entry point here is a detector nothing proves runs"
    )


def test_every_detector_calls_into_its_governance_module(
    monkeypatch, tmp_path
) -> None:
    """The assertion the old guard could not make, and the new one needs.

    Runs the REAL sweep against the REAL detectors, with each governance
    entry point wrapped in a recording spy. A detector that names its
    module but never calls it fails here.
    """
    import importlib

    called: list[str] = []
    for module_name, attr in DETECTOR_ENTRY_POINTS.items():
        module = importlib.import_module(module_name)
        real = getattr(module, attr)

        def _spy(*args, _name=module_name, _real=real, **kwargs):
            called.append(_name)
            return _real(*args, **kwargs)

        monkeypatch.setattr(module, attr, _spy)

    # Contain the two side-effect sinks so a unit test writes nothing to
    # the developer's home or to the shared /tmp.
    monkeypatch.setattr(
        "core.governance.skill_proposer._DEFAULT_OUTPUT_DIR",
        tmp_path / "skill-proposals",
    )
    monkeypatch.setattr(
        "core.hooks.stop.arkaos_temp_dir", lambda *parts: tmp_path.joinpath(*parts)
    )

    stop_governance.run("[arka:gate:4] done", None, "sess-parity")

    assert sorted(called) == sorted(DETECTOR_ENTRY_POINTS), (
        "detectors that never called their governance module: "
        f"{sorted(set(DETECTOR_ENTRY_POINTS) - set(called))}"
    )


@pytest.mark.parametrize("name", sorted(OBSERVED_IN_PS1))
def test_every_observed_detector_is_actually_reached(monkeypatch, name) -> None:
    """run() must reach every entry in its own table.

    Weaker than the test above and kept for the layer it covers: this one
    pins the dispatch loop, that one pins the detector bodies.
    """
    reached: list[str] = []
    index = [n for n, _ in stop_governance.DETECTORS].index(name)

    def _spy(last, raw, safe_sid):
        reached.append(name)

    patched = list(stop_governance.DETECTORS)
    patched[index] = (name, _spy)
    monkeypatch.setattr(stop_governance, "DETECTORS", tuple(patched))

    completed = stop_governance.run("done", None, "sess-parity")
    assert reached == [name], f"{name} was never reached by run()"
    assert name in completed


def test_one_failing_detector_does_not_stop_the_others(monkeypatch) -> None:
    """Fire-and-forget is per detector, not for the batch."""
    reached: list[str] = []

    def _boom(last, raw, safe_sid):
        raise RuntimeError("detector exploded")

    def _ok(name):
        def _inner(last, raw, safe_sid):
            reached.append(name)
        return _inner

    names = [n for n, _ in stop_governance.DETECTORS]
    patched = [(names[0], _boom)] + [(n, _ok(n)) for n in names[1:]]
    monkeypatch.setattr(stop_governance, "DETECTORS", tuple(patched))

    completed = stop_governance.run("done", None, "sess-parity")
    assert reached == names[1:], "a raising detector aborted the sweep"
    assert names[0] not in completed, "a raising detector was reported as run"


def test_main_is_a_noop_without_a_transcript(monkeypatch) -> None:
    monkeypatch.delenv("TRANSCRIPT_PATH_VAL", raising=False)
    called: list[int] = []
    monkeypatch.setattr(
        stop_governance, "run", lambda *a, **k: called.append(1) or []
    )
    assert stop_governance.main() == 0
    assert not called, "main() ran the sweep with no transcript to read"


# ── The state writer is the canonical one, hardening included ─────────────


def test_sweep_uses_the_canonical_state_writer() -> None:
    """B4, closed by identity rather than by inspection.

    The port used to define its own ``_write_tmp_state`` whose docstring
    claimed to mirror ``core.hooks.stop._write_tmp_state`` while dropping
    its ``umask(0o077)``. Identity is the only assertion a future copy
    cannot pass.
    """
    assert stop_governance._write_tmp_state is stop_hook._write_tmp_state


def test_state_files_are_owner_only(tmp_path, monkeypatch) -> None:
    """Executed proof, not a reading of the source.

    Under a normal 0o022 umask the unhardened copy produced file 0644 /
    dir 0755; the canonical writer produces 0600 / 0700. The payloads are
    transcript-derived (sycophancy signals, phantom-action claims quoting
    assistant text) and land in a shared /tmp whenever the PowerShell
    adapter runs on POSIX.
    """
    monkeypatch.setattr(
        "core.hooks.stop.arkaos_temp_dir", lambda *parts: tmp_path.joinpath(*parts)
    )
    prev = os.umask(0o022)
    try:
        stop_governance._write_tmp_state("arkaos-phantom", "sess-perm", {"a": 1})
    finally:
        os.umask(prev)

    state_dir = tmp_path / "arkaos-phantom"
    state_file = state_dir / "sess-perm.json"
    assert state_file.is_file()
    assert stat.S_IMODE(state_file.stat().st_mode) == 0o600, (
        "state file is group/world readable; it carries transcript-derived "
        "payloads and PowerShell runs on POSIX too"
    )
    assert stat.S_IMODE(state_dir.stat().st_mode) == 0o700


# ── Nothing drifts in unclassified, nothing deferred leaks in ─────────────


def test_no_governance_module_is_silently_unclassified() -> None:
    """Every governance module stop.py imports is mirrored or deferred.

    A new module in stop.py forces an explicit choice here instead of
    quietly never running on Windows.
    """
    known = OBSERVED_IN_PS1 | set(DEFERRED_IN_PS1)
    unclassified = sorted(_governance_modules_in_stop_py() - known)
    assert not unclassified, (
        "stop.py imports governance modules this port has not classified: "
        f"{unclassified}. Run them in core/hooks/stop_governance.py "
        "(DETECTORS) or record the decision to defer them, WITH A REASON "
        "(DEFERRED_IN_PS1)."
    )


def test_every_deferral_carries_its_own_reason() -> None:
    """"Adding one here is a decision, not a default" — made enforceable.

    The previous version stated that rule and could not hold it: entries
    were bare strings in a set, and two of the seven had no reason at all
    while the file's blanket explanation was false for both.
    """
    unexplained = sorted(k for k, v in DEFERRED_IN_PS1.items() if not v.strip())
    assert not unexplained, (
        f"deferred without a reason: {unexplained}. Say why, specifically — "
        "'enforcement surface' is not true of every deferral."
    )
    lazy = sorted(k for k, v in DEFERRED_IN_PS1.items() if len(v.strip()) < 40)
    assert not lazy, f"deferral reason too thin to audit: {lazy}"


def test_deferred_modules_stay_out_of_the_port() -> None:
    sweep_src = Path(stop_governance.__file__).read_text(encoding="utf-8")
    haystack = _ps1_text() + "\n" + sweep_src
    leaked = sorted(
        m for m in DEFERRED_IN_PS1
        if re.search(rf"^\s*from {re.escape(m)} import", haystack, re.MULTILINE)
    )
    assert not leaked, (
        f"deferred modules are being run by the port: {leaked}. Each needs "
        "its own Windows baseline first — and its reason updated here."
    )
