"""Mode promotion/demotion rule — pure, no IO (spec PR5, decision D2).

:func:`propose_mode` reads a site's replay history and proposes a mode.
It never writes config or code: the PR applies an accepted proposal to
``Site.default_mode`` by hand, with an evidence comment.

* ``shadow → act``: the last :data:`PROMOTE_RUNS` measured runs pass on
  the same corpus digest (``qg-prescreen`` also needs abstain ≤
  :data:`PRESCREEN_MAX_ABSTAIN` in each: a margin, not the limit).
* ``act → shadow``: at least :data:`DEMOTE_FAILS` fails among the last
  :data:`DEMOTE_WINDOW` measured runs; exactly one fail is ``watch``
  (stays ``act``, recorded in the report).
* ``off`` is never proposed and never changed.
* A ``not-measured`` run counts for neither side.
* A changed corpus digest restarts the window: a relabel never inherits
  the runs of the old corpus.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from core.decisions.config import Mode

RunGate = Literal["pass", "fail", "not-measured"]
Action = Literal["promote", "demote", "watch", "keep"]

PROMOTE_RUNS = 2
DEMOTE_WINDOW = 3
DEMOTE_FAILS = 2
PRESCREEN_SITE = "qg-prescreen"
PRESCREEN_MAX_ABSTAIN = 0.20


@dataclass(frozen=True)
class RunVerdict:
    """One replay run of one site, as the rule sees it."""

    gate: RunGate
    abstain: float | None
    corpus_sha256: str
    ts: str = ""


@dataclass(frozen=True)
class ModeProposal:
    """What the rule proposes for one site; ``proposed == current`` unless it moves."""

    site: str
    current: Mode
    proposed: Mode
    action: Action
    reason: str
    runs_considered: int
    corpus_sha256: str | None


def current_window(runs: Sequence[RunVerdict]) -> list[RunVerdict]:
    """Measured runs on the latest corpus digest, oldest first.

    ``not-measured`` runs are dropped; the window is the trailing stretch
    whose digest equals the newest measured run's, so a digest change
    restarts the count.
    """
    measured = [r for r in runs if r.gate != "not-measured"]
    if not measured:
        return []
    digest = measured[-1].corpus_sha256
    window: list[RunVerdict] = []
    for run in reversed(measured):
        if run.corpus_sha256 != digest:
            break
        window.append(run)
    return list(reversed(window))


def _proposal(
    site: str, current: Mode, proposed: Mode, action: Action, reason: str,
    window: Sequence[RunVerdict],
) -> ModeProposal:
    digest = window[-1].corpus_sha256 if window else None
    return ModeProposal(site, current, proposed, action, reason, len(window), digest)


def _abstain_within_margin(run: RunVerdict) -> bool:
    return run.abstain is not None and run.abstain <= PRESCREEN_MAX_ABSTAIN


def _promotion(site: str, window: Sequence[RunVerdict]) -> ModeProposal:
    last = list(window[-PROMOTE_RUNS:])
    if len(last) < PROMOTE_RUNS:
        return _proposal(site, "shadow", "shadow", "keep",
                         f"{len(last)} measured run(s) on this corpus; "
                         f"promotion needs {PROMOTE_RUNS}", window)
    if any(r.gate != "pass" for r in last):
        return _proposal(site, "shadow", "shadow", "keep",
                         f"not every one of the last {PROMOTE_RUNS} measured runs passed", window)
    if site == PRESCREEN_SITE and not all(_abstain_within_margin(r) for r in last):
        return _proposal(site, "shadow", "shadow", "keep",
                         f"abstain above the {PRESCREEN_MAX_ABSTAIN:.0%} prescreen margin",
                         window)
    return _proposal(site, "shadow", "act", "promote",
                     f"last {PROMOTE_RUNS} measured runs passed on the same corpus", window)


def _demotion(site: str, window: Sequence[RunVerdict]) -> ModeProposal:
    last = list(window[-DEMOTE_WINDOW:])
    fails = sum(1 for r in last if r.gate == "fail")
    summary = f"{fails} fail(s) in the last {len(last)} measured run(s)"
    if fails >= DEMOTE_FAILS:
        return _proposal(site, "act", "shadow", "demote", summary, window)
    if fails == 1:
        return _proposal(site, "act", "act", "watch", summary, window)
    return _proposal(site, "act", "act", "keep", summary, window)


def propose_mode(site: str, current: Mode, runs: Sequence[RunVerdict]) -> ModeProposal:
    """The rule's proposal for ``site`` given its run history (oldest first)."""
    window = current_window(runs)
    if current == "off":
        return _proposal(site, "off", "off", "keep", "off is never changed by the rule", window)
    if current == "act":
        return _demotion(site, window)
    return _promotion(site, window)
