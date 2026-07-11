"""Routing feedback aggregator (F1-B1 — memory/learning reform).

Closes the telemetry loop the ruflo teardown flagged as ArkaOS's G1 gap:
QG verdicts and gate-judge verdicts are written every review but nothing
ever read them back. This module aggregates both corpora into
``~/.arkaos/routing-scores.json`` — per-department approval scores that
the Synapse L5.5 layer (F1-B2) injects as ``[arka:redo-risk]`` warnings.

Scored table, deliberately NOT Q-learning: sample sizes are dozens, not
thousands (Q would never converge), and the constitution's evidence-flow
demands citable counts — ``approvals=3/9 (30d)`` is auditable, a qTable
weight is not. Recency weighting gives the same "reward changes future
behaviour" property with zero exploration risk.

Sources consumed (both have ``department`` on every record):
    - qg-verdicts.jsonl     (QGVerdict: APPROVED/REJECTED + blockers)
    - judge-verdicts.jsonl  (JudgeVerdict: PASS/REVISE)
specialist-dispatch.jsonl is deliberately NOT consumed in v1: its records
carry tool/file but no department — mapping would require fragile
file-to-department inference, and a wrong attribution is worse than none.

CLI: ``python3 -m core.governance.routing_feedback_cli rebuild|show``
"""

from __future__ import annotations

import json
import math
import os
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

SCORES_ENV = "ARKA_ROUTING_SCORES_PATH"
_WINDOW_DAYS = 90  # records older than this are ignored entirely
_HALF_LIFE_DAYS = 30.0  # recency weight halves every 30 days
_REDO_WINDOW_DAYS = 7  # >=2 REJECTED same deliverable+department within
_TOP_BLOCKERS = 3


class RoutingScore(BaseModel):
    """Per-department evidence the router can cite verbatim."""

    department: str
    approvals: int = 0  # raw QG counts inside the window (citable)
    rejections: int = 0
    smoothed_approval: float = Field(
        default=0.5,
        description="Laplace (a+1)/(a+r+2) over recency-weighted QG counts",
    )
    judge_passes: int = 0  # gate-judge signal, kept separate from QG
    judge_revises: int = 0
    redo_count: int = 0
    top_blocker_patterns: list[str] = Field(default_factory=list)
    samples: int = 0  # QG verdicts backing smoothed_approval


class RoutingScores(BaseModel):
    version: int = 1
    computed_at: str = ""
    window_days: int = _WINDOW_DAYS
    sources: list[str] = Field(default_factory=list)
    scores: list[RoutingScore] = Field(default_factory=list)


def scores_path() -> Path:
    override = os.environ.get(SCORES_ENV, "").strip()
    if override:
        return Path(override)
    return Path.home() / ".arkaos" / "routing-scores.json"


def _age_days(ts: str, now: datetime) -> Optional[float]:
    try:
        parsed = datetime.fromisoformat(ts)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return max(0.0, (now - parsed).total_seconds() / 86400.0)
    except (ValueError, TypeError):
        return None


def _recency_weight(age_days: float) -> float:
    return math.pow(0.5, age_days / _HALF_LIFE_DAYS)


def _windowed(records: list[dict], now: datetime) -> list[tuple[dict, float]]:
    """Pair each in-window record with its recency weight; drop the rest."""
    kept: list[tuple[dict, float]] = []
    for record in records:
        age = _age_days(str(record.get("ts") or ""), now)
        if age is None or age > _WINDOW_DAYS:
            continue
        department = str(record.get("department") or "").strip()
        if not department:
            continue  # unattributable — wrong attribution is worse than none
        kept.append((record, _recency_weight(age)))
    return kept


def _count_redos(qg: list[tuple[dict, float]]) -> Counter:
    """>=2 REJECTED for the same deliverable+department within the window."""
    rejected_ts: dict[tuple[str, str], list[datetime]] = {}
    for record, _w in qg:
        if str(record.get("verdict")).upper() != "REJECTED":
            continue
        key = (str(record.get("department")), str(record.get("deliverable") or ""))
        try:
            when = datetime.fromisoformat(str(record.get("ts")))
        except (ValueError, TypeError):
            continue
        rejected_ts.setdefault(key, []).append(when)
    redos: Counter = Counter()
    for (department, _deliverable), stamps in rejected_ts.items():
        stamps.sort()
        for earlier, later in zip(stamps, stamps[1:]):
            if (later - earlier).total_seconds() <= _REDO_WINDOW_DAYS * 86400:
                redos[department] += 1
    return redos


def _blocker_patterns(records: list[dict]) -> list[str]:
    counts: Counter = Counter()
    for record in records:
        for blocker in record.get("blockers") or []:
            check = str((blocker or {}).get("check") or "").strip()
            if check:
                counts[check] += 1
    return [check for check, _n in counts.most_common(_TOP_BLOCKERS)]


def _department_score(
    department: str,
    qg: list[tuple[dict, float]],
    judge: list[tuple[dict, float]],
    redos: Counter,
) -> RoutingScore:
    dept_qg = [(r, w) for r, w in qg if r.get("department") == department]
    approvals_w = sum(w for r, w in dept_qg if str(r.get("verdict")).upper() == "APPROVED")
    rejections_w = sum(w for r, w in dept_qg if str(r.get("verdict")).upper() == "REJECTED")
    dept_judge = [(r, w) for r, w in judge if r.get("department") == department]
    rejected_records = [
        r for r, _w in dept_qg if str(r.get("verdict")).upper() == "REJECTED"
    ]
    return RoutingScore(
        department=department,
        approvals=sum(1 for r, _ in dept_qg if str(r.get("verdict")).upper() == "APPROVED"),
        rejections=len(rejected_records),
        smoothed_approval=(approvals_w + 1.0) / (approvals_w + rejections_w + 2.0),
        judge_passes=sum(1 for r, _ in dept_judge if str(r.get("verdict")).upper() == "PASS"),
        judge_revises=sum(1 for r, _ in dept_judge if str(r.get("verdict")).upper() == "REVISE"),
        redo_count=redos.get(department, 0),
        top_blocker_patterns=_blocker_patterns(rejected_records),
        samples=len(dept_qg),
    )


def rebuild(now: datetime | None = None) -> RoutingScores:
    """Aggregate both corpora and atomically write routing-scores.json."""
    from core.evals.verdict_labels import load_judge_labels, load_verdict_labels

    current = now or datetime.now(timezone.utc)
    qg = _windowed(load_verdict_labels(), current)
    judge = _windowed(load_judge_labels(), current)
    departments = sorted(
        {str(r.get("department")) for r, _ in qg}
        | {str(r.get("department")) for r, _ in judge}
    )
    redos = _count_redos(qg)
    result = RoutingScores(
        computed_at=current.isoformat(),
        sources=["qg-verdicts.jsonl", "judge-verdicts.jsonl"],
        scores=[_department_score(d, qg, judge, redos) for d in departments],
    )
    _atomic_write(scores_path(), result)
    return result


def _atomic_write(target: Path, payload: RoutingScores) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=target.parent, prefix=f"{target.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload.model_dump_json(indent=2))
        os.replace(tmp_name, target)
    except OSError:
        Path(tmp_name).unlink(missing_ok=True)


def load_scores() -> Optional[RoutingScores]:
    """Read the scores file; None when absent/invalid (consumer stays inert)."""
    try:
        data: dict[str, Any] = json.loads(scores_path().read_text(encoding="utf-8"))
        if data.get("version") != 1:
            return None
        return RoutingScores(**data)
    except Exception:  # noqa: BLE001 — consumers must never break on this file
        return None


def stale(max_age_seconds: int = 3600) -> bool:
    """True when the scores file is missing or older than the threshold."""
    try:
        mtime = scores_path().stat().st_mtime
    except OSError:
        return True
    return (datetime.now(timezone.utc).timestamp() - mtime) > max_age_seconds
