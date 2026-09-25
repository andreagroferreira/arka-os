"""Decisions cost and effect: what Jev costs, what it changed, what it could save.

Read-only view for ``/arka decisions`` and ``/arka status`` (spec PR5, D5).

* **Cost** is measured: the LLM cost ledger split into production
  (``category=decision``) and replay-harness runs (``decision-replay``),
  so evidence runs never read as production spend.
* **Effect** is counted per site from ``decisions.jsonl``.
* **Saving** is never measured today. Four sites carry a counterfactual
  (plan numbering): #7 forge-complexity (runs in shadow), #10
  dispatch-role (escalate-only, so it never saves by construction), #11
  qg-prescreen (advisory, never removes a reviewer) and #22
  subagent-discipline (advisory, no ledger row links to a turn). Only #11
  has a dollar figure, and it is a CEILING labelled ``counterfactual``:
  it is never added to the cost and never called a saving.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from core.decisions.paths import telemetry_path
from core.decisions.telemetry import (
    COST_CATEGORY,
    REPLAY_COST_CATEGORY,
    REPLAY_SESSION_ID,
    VALID_PERIODS,
    _period_cutoff,
    _read_jsonl,
)

COUNTERFACTUAL = "counterfactual (ceiling)"
NO_SAVING = "—"
NO_MEASURED_SAVING = (
    "No measured saving is claimable today: forge-complexity and qg-prescreen "
    "do not change what runs, dispatch-role only escalates, and no ledger row "
    "links a subagent to the turn that suggested it. Cost is measured; the "
    "rows below are effect counts and counterfactuals."
)
REVIEWER_CATEGORIES = frozenset({"subagent:eduardo-copy", "subagent:francisca-tech"})
_TIER_ORDER = {"SHALLOW": 0, "STANDARD": 1, "DEEP": 2}

Rows = list[dict[str, Any]]


@dataclass(frozen=True)
class LedgerSplit:
    """Ledger cost of Jev calls: production vs replay runs."""

    production_usd: float = 0.0
    production_calls: int = 0
    replay_usd: float = 0.0
    replay_calls: int = 0


@dataclass(frozen=True)
class Counterfactual:
    """One cost site's effect count and saving status."""

    number: int
    site: str
    effect: str
    count: int
    detail: dict[str, int] = field(default_factory=dict)
    saving: str = NO_SAVING
    ceiling_usd: float | None = None
    not_measurable: str = ""


@dataclass(frozen=True)
class CostEffect:
    """The whole cost-and-effect view of one period."""

    period: str
    ledger: LedgerSplit
    counterfactuals: list[Counterfactual]
    has_data: bool


@dataclass(frozen=True)
class Sources:
    """Where each input lives (tests point these at tmp files)."""

    decisions: Path
    ledger: Path
    verdicts: Path
    activations: Path


def default_sources() -> Sources:
    """The live paths, each honouring its own env override."""
    from core.evals.verdict_labels import _labels_path
    from core.governance import activation_tracker
    from core.runtime.llm_cost_telemetry import _telemetry_path

    return Sources(telemetry_path(), _telemetry_path(), _labels_path(),
                   activation_tracker.TELEMETRY_PATH)


def is_replay_row(row: dict[str, Any]) -> bool:
    """A replay row: ``decision-replay``, or an older ``decision`` row of session "replay"."""
    category = row.get("category")
    return category == REPLAY_COST_CATEGORY or (
        category == COST_CATEGORY and row.get("session_id") == REPLAY_SESSION_ID)


def ledger_split(ledger: Rows) -> LedgerSplit:
    """Sum the ledger's decision rows: production vs replay runs."""
    rep = [r for r in ledger if is_replay_row(r)]
    prod = [r for r in ledger if r.get("category") == COST_CATEGORY and not is_replay_row(r)]
    return LedgerSplit(_usd(prod), len(prod), _usd(rep), len(rep))


def _usd(rows: Rows) -> float:
    return round(sum(float(r.get("estimated_cost_usd") or 0.0) for r in rows), 8)


def _site_rows(decisions: Rows, site: str) -> Rows:
    return [r for r in decisions if r.get("site") == site]


def _tier(dims: object) -> str | None:
    """The Forge tier of a dimensions dict; None unless it has exactly the five dimensions."""
    from core.decisions.sites.forge import DIMENSIONS

    if not isinstance(dims, dict) or set(dims) != set(DIMENSIONS):
        return None
    from core.forge.complexity import calculate_weighted_score, determine_tier
    from core.forge.schema import ComplexityDimensions

    try:
        return determine_tier(calculate_weighted_score(ComplexityDimensions(**dims))).value.upper()
    except (TypeError, ValueError):
        return None


def forge_complexity(decisions: Rows) -> Counterfactual:
    """#7: rows where Jev's dimensions give another Forge tier than the heuristic's."""
    up = down = 0
    for row in _site_rows(decisions, "forge-complexity"):
        h, j = _tier(row.get("heuristic_result")), _tier(row.get("jev_result"))
        if h is None or j is None or h == j:
            continue
        if _TIER_ORDER[j] > _TIER_ORDER[h]:
            up += 1
        else:
            down += 1
    return Counterfactual(
        7, "forge-complexity", "counterfactual: tier would differ", up + down,
        {"up": up, "down": down},
        not_measurable="cost of a tier: the ledger has no Forge category")


def dispatch_role(decisions: Rows) -> Counterfactual:
    """#10: escalations Jev acted on; downgrades the rule blocked."""
    rows = _site_rows(decisions, "dispatch-role")
    escalated = sum(1 for r in rows if r.get("acted_on") == "jev"
                    and r.get("jev_result") != r.get("heuristic_result"))
    blocked = sum(1 for r in rows if r.get("reason") == "downgrade-blocked")
    return Counterfactual(
        10, "dispatch-role", "escalations acted on", escalated,
        {"downgrade_blocked": blocked},
        saving=f"{NO_SAVING} escalate-only: never saves by construction",
        not_measurable="whether the orchestrator followed the marker (Task model has no hook)")


def _prescreen_rounds(verdicts: Rows) -> list[tuple[str, str]]:
    """``(predicted, final)`` per QG round that carried a prescreen, lower case."""
    out: list[tuple[str, str]] = []
    for row in verdicts:
        pre = row.get("prescreen")
        if isinstance(pre, dict) and pre.get("verdict") in ("approved", "rejected"):
            out.append((str(pre["verdict"]), str(row.get("verdict") or "").lower()))
    return out


def _rejected_sessions(verdicts: Rows) -> set[str]:
    return {str(r.get("session_id") or "") for r in verdicts
            if isinstance(r.get("prescreen"), dict)
            and r["prescreen"].get("verdict") == "rejected"
            and str(r.get("verdict") or "").upper() == "REJECTED"} - {""}


def qg_prescreen(verdicts: Rows, ledger: Rows) -> Counterfactual:
    """#11: prediction accuracy and the reviewer-cost ceiling of correct rejections.

    The ceiling sums the reviewers' ledger cost over whole SESSIONS with a
    correctly predicted rejection: the ledger has no round id, so this
    over-counts by design (an upper bound, never an estimate).
    """
    rounds = _prescreen_rounds(verdicts)
    agree = sum(1 for predicted, final in rounds if predicted == final)
    sessions = _rejected_sessions(verdicts)
    ceiling = _usd([r for r in ledger if r.get("category") in REVIEWER_CATEGORIES
                    and str(r.get("session_id") or "") in sessions])
    return Counterfactual(
        11, "qg-prescreen", "rounds with a prescreen", len(rounds),
        {"agree_with_final": agree, "sessions_rejected_as_predicted": len(sessions)},
        saving=COUNTERFACTUAL, ceiling_usd=ceiling,
        not_measurable="real saving: the prescreen never skips a reviewer")


def _isolate_value(row: dict[str, Any]) -> object:
    return row.get("jev_result") if row.get("acted_on") == "jev" else row.get("heuristic_result")


def subagent_discipline(decisions: Rows, activations: Rows) -> Counterfactual:
    """#22: turns told not to isolate, and how many of their sessions launched a subagent."""
    no_turns = [r for r in _site_rows(decisions, "subagent-discipline")
                if _isolate_value(r) is False]
    sessions = {str(r.get("session_id") or "") for r in no_turns} - {""}
    launched = {str(a.get("session_id") or "") for a in activations} & sessions
    return Counterfactual(
        22, "subagent-discipline", "turns marked isolate=no", len(no_turns),
        {"sessions": len(sessions), "sessions_with_a_subagent": len(launched)},
        saving=f"{NO_SAVING} correlation per session, not attribution",
        not_measurable="a subagent that was not launched leaves no trace")


def _load(sources: Sources, cutoff: datetime | None) -> dict[str, Rows]:
    paths = {"decisions": sources.decisions, "ledger": sources.ledger,
             "verdicts": sources.verdicts, "activations": sources.activations}
    return {name: _read_jsonl(path, cutoff)[0] for name, path in paths.items()}


def cost_effect(
    period: str = "today", *, sources: Sources | None = None, now: datetime | None = None
) -> CostEffect:
    """Cost, effect and counterfactuals of one period (today | week | month | all)."""
    if period not in VALID_PERIODS:
        raise ValueError(f"invalid period: {period!r}")
    data = _load(sources or default_sources(), _period_cutoff(period, now))
    split = ledger_split(data["ledger"])
    rows = [forge_complexity(data["decisions"]), dispatch_role(data["decisions"]),
            qg_prescreen(data["verdicts"], data["ledger"]),
            subagent_discipline(data["decisions"], data["activations"])]
    has_data = bool(split.production_calls or split.replay_calls or data["decisions"]
                    or any(r.count for r in rows))
    return CostEffect(period, split, rows, has_data)
