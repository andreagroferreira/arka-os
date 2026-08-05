"""Drift guard: `stop.ps1` must observe the same governance modules as `stop.py`.

`config/hooks/stop.sh` delegates the whole Stop event to
``python -m core.hooks.stop``. The PowerShell port reimplements the event
inline, so every module the Python entrypoint gains has to be mirrored by
hand -- and silently was not: four warn-only detectors, including
``skill_proposer`` (constitution rule ``mandatory-skill-evaluation``),
existed and were wired on POSIX while never running on Windows.

These tests fail when that gap reopens. Static assertions on purpose: they
run identically on every platform and need no pwsh.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
STOP_PS1 = REPO_ROOT / "config" / "hooks" / "stop.ps1"
STOP_PY = REPO_ROOT / "core" / "hooks" / "stop.py"

# Warn-only detectors: they emit proposals or diagnostic state and nothing
# reads their output to gate anything. These MUST be mirrored in the port.
OBSERVED_IN_PS1 = {
    "core.governance.skill_proposer",
    "core.governance.sycophancy_detector",
    "core.governance.phantom_action_check",
    "core.governance.tool_loop_check",
}

# Modules the port deliberately does NOT run. They feed enforcement
# surfaces (closing-marker nags, meta-tag and citation compliance, DNA
# fidelity), so switching them on for Windows needs its own baseline
# rather than riding along with a parity fix. Adding one here is a
# decision, not a default.
DEFERRED_IN_PS1 = {
    # Drains QG reviewer notices into the hook's *output* surface. The
    # port writes no hook output at all, so mirroring it needs the
    # emit-context contract first -- out of scope for a detector fix.
    "core.governance.reviewer_ledger",
    "core.governance.closing_marker_check",
    "core.governance.meta_tag_check",
    "core.governance.kb_cite_check",
    "core.governance.dna_fidelity",
    "core.governance.stop_lint",
    "core.governance.routing_feedback",
}


def _ps1_text() -> str:
    return STOP_PS1.read_text(encoding="utf-8")


def _governance_modules_in_stop_py() -> set[str]:
    text = STOP_PY.read_text(encoding="utf-8")
    return set(re.findall(r"from (core\.governance\.[a-z_]+) import", text))


def test_ps1_runs_every_warn_only_detector() -> None:
    text = _ps1_text()
    missing = sorted(m for m in OBSERVED_IN_PS1 if m not in text)
    assert not missing, (
        "stop.ps1 stopped observing warn-only detectors that stop.py runs: "
        f"{missing}. Windows sessions lose them silently."
    )


def test_skill_proposer_is_reachable_from_the_port() -> None:
    """The regression that motivated this file, pinned on its own."""
    text = _ps1_text()
    assert "core.governance.skill_proposer" in text
    assert "evaluate" in text


def test_no_governance_module_is_silently_unclassified() -> None:
    """Every governance module stop.py imports is mirrored or deferred.

    A new module in stop.py forces an explicit choice here instead of
    quietly never running on Windows.
    """
    known = OBSERVED_IN_PS1 | DEFERRED_IN_PS1
    unclassified = sorted(_governance_modules_in_stop_py() - known)
    assert not unclassified, (
        "stop.py imports governance modules this port has not classified: "
        f"{unclassified}. Mirror them in stop.ps1 (add to OBSERVED_IN_PS1) "
        "or record the decision to defer them (DEFERRED_IN_PS1)."
    )


def test_deferred_modules_stay_out_of_the_port() -> None:
    text = _ps1_text()
    leaked = sorted(m for m in DEFERRED_IN_PS1 if m in text)
    assert not leaked, (
        f"enforcement-coupled modules leaked into stop.ps1: {leaked}. "
        "They need their own Windows baseline first."
    )


def test_governance_block_cannot_break_the_hook() -> None:
    """The added block stays fire-and-forget, like its two siblings."""
    text = _ps1_text()
    assert "$governanceScript" in text
    tail = text.split("$governanceScript", 1)[1]
    assert "try {" in tail and "catch {" in tail, (
        "the governance block must be invoked inside try/catch so a "
        "detector failure never affects the Stop hook"
    )
