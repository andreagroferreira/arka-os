"""Replay harness — the evidence gate for moving a site between modes.

Runs a labelled corpus (``config/decisions/corpora/<site>.jsonl``) through
the site's heuristic and, online, through the JEV. Gate (online):

* JEV precision on the cases it answers ≥ heuristic precision on the SAME
  cases + 5 pp;
* abstain rate (abstain + unavailable) ≤ 25 %;
* escalate-only sites: false escalations ≤ 5 % of the cases where the
  heuristic was already right.

Corpus validity (both modes): ≥ 30 cases and ≥ 50 % pt-PT. ``--offline``
scores the heuristic only and passes on a valid corpus.
Exit codes: 0 pass, 1 fail, 2 usage.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, StrictBool, ValidationError

from core.decisions.config import DecisionsConfig, load_decisions_config, threshold_for
from core.decisions.engine import resolve, run_sync
from core.decisions.paths import repo_root
from core.decisions.registry import SITES
from core.decisions.site import Outcome, Site, SiteCall
from core.decisions.sites.prompt import prompt_state
from core.decisions.telemetry import call_cost_usd
from core.decisions.transport import Transport, resolve_transport

MIN_CASES = 30
MIN_PT_SHARE = 0.5
MARGIN = 0.05
MAX_ABSTAIN = 0.25
MAX_FALSE_ESCALATION = 0.05
REPLAY_TIMEOUT_S = 5.0

Gate = Literal["pass", "fail", "offline"]


class ReplayCase(BaseModel):
    """One labelled prompt."""

    model_config = ConfigDict(extra="forbid")

    id: str
    lang: Literal["pt", "en"]
    prompt: str
    prior: list[str] = []
    expected: StrictBool | str


@dataclass
class ReplayReport:
    """Scores and gate verdict for one site's corpus."""

    site: str
    cases: int
    pt_share: float
    heuristic_accuracy: float
    jev_accuracy: float | None = None
    heuristic_on_answered: float | None = None
    act_accuracy: float | None = None
    abstain_rate: float | None = None
    false_escalation_rate: float | None = None
    unavailable: int = 0
    # G3 evidence: median latency of the calls that really went out
    # (cache hits and an open breaker excluded) and their summed cost.
    # None whenever nothing was measured (offline, or every answer from
    # the cache), so "not measured" never reads as "0 ms measured".
    p50_latency_ms: int | None = None
    cost_usd: float | None = None
    by_lang: dict[str, dict[str, float | None]] = field(default_factory=dict)
    gate: Gate = "offline"
    failures: list[str] = field(default_factory=list)


# --- heuristics: the SAME pure functions the live call sites run ------------

def _heuristic_topic_drift(case: ReplayCase) -> bool:
    from core.hooks.user_prompt_submit import keyword_topic_shift

    return keyword_topic_shift(case.prompt, "\n".join(case.prior))


def _heuristic_refine(case: ReplayCase) -> bool:
    from core.hooks.user_prompt_submit import (
        _names_concrete_target,
        _refine_heuristic,
        _wf_classify,
    )

    text = case.prompt
    if not _wf_classify(text) or text.strip().startswith("/"):
        return False
    return not _names_concrete_target(text) and _refine_heuristic(text)


def _heuristic_creation(case: ReplayCase) -> bool:
    from core.hooks.user_prompt_submit import _wf_classify

    return _wf_classify(case.prompt)


def _heuristic_route(case: ReplayCase) -> str:
    from core.synapse.layers import keyword_department

    return keyword_department(case.prompt) or ""


HEURISTICS: dict[str, Callable[[ReplayCase], object]] = {
    "topic-drift": _heuristic_topic_drift,
    "refine": _heuristic_refine,
    "creation-intent": _heuristic_creation,
    "route": _heuristic_route,
}


def default_corpus_path(site: str) -> Path:
    """``config/decisions/corpora/<site>.jsonl`` in this checkout."""
    return repo_root() / "config" / "decisions" / "corpora" / f"{site}.jsonl"


def load_corpus(site: str, path: Path | None = None) -> list[ReplayCase]:
    """Parse a JSONL corpus; ValueError names the first bad line."""
    source = path or default_corpus_path(site)
    cases: list[ReplayCase] = []
    for number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            cases.append(ReplayCase.model_validate(json.loads(line)))
        except (ValueError, ValidationError) as exc:
            raise ValueError(f"{source}:{number}: {exc}") from exc
    return cases


# --- scoring -----------------------------------------------------------------

Row = tuple[ReplayCase, object, Outcome | None]


def _rate(hits: int, total: int) -> float | None:
    return round(hits / total, 4) if total else None


def _accuracy(rows: Sequence[Row], pick: Callable[[Row], object]) -> float | None:
    return _rate(sum(1 for r in rows if pick(r) == r[0].expected), len(rows))


def _answered(rows: Sequence[Row]) -> list[Row]:
    return [r for r in rows if r[2] is not None and r[2].jev is not None]


def _false_escalation(site: Site, rows: Sequence[Row]) -> float | None:
    if site.direction != "escalate_only":
        return None
    at_risk = [r for r in rows if r[1] == r[0].expected]
    wrong = [r for r in at_risk if r[2] is not None and r[2].acted_on == "jev"
             and r[2].value != r[0].expected]
    return _rate(len(wrong), len(at_risk))


def _by_lang(rows: Sequence[Row], online: bool) -> dict[str, dict[str, float | None]]:
    out: dict[str, dict[str, float | None]] = {}
    for lang in sorted({r[0].lang for r in rows}):
        subset = [r for r in rows if r[0].lang == lang]
        entry = {"cases": float(len(subset)), "heuristic": _accuracy(subset, lambda r: r[1])}
        if online:
            entry["jev"] = _accuracy(_answered(subset), lambda r: r[2].jev if r[2] else None)
        out[lang] = entry
    return out


def _base_report(site: Site, rows: Sequence[Row]) -> ReplayReport:
    pt = sum(1 for r in rows if r[0].lang == "pt")
    return ReplayReport(
        site=site.name, cases=len(rows), pt_share=_rate(pt, len(rows)) or 0.0,
        heuristic_accuracy=_accuracy(rows, lambda r: r[1]) or 0.0,
    )


def _online_scores(site: Site, rows: Sequence[Row], report: ReplayReport) -> None:
    answered = _answered(rows)
    report.jev_accuracy = _accuracy(answered, lambda r: r[2].jev if r[2] else None)
    report.heuristic_on_answered = _accuracy(answered, lambda r: r[1])
    report.act_accuracy = _accuracy(rows, lambda r: r[2].value if r[2] else r[1])
    report.abstain_rate = _rate(len(rows) - len(answered), len(rows))
    report.false_escalation_rate = _false_escalation(site, rows)
    report.unavailable = sum(1 for r in rows if r[2] is None or r[2].reason not in
                             ("jev", "abstain", "shadow", "downgrade-blocked"))


def _corpus_failures(report: ReplayReport) -> list[str]:
    failures = []
    if report.cases < MIN_CASES:
        failures.append(f"corpus has {report.cases} cases (< {MIN_CASES})")
    if report.pt_share < MIN_PT_SHARE:
        failures.append(f"pt-PT share {report.pt_share:.0%} (< {MIN_PT_SHARE:.0%})")
    return failures


def _gate_failures(report: ReplayReport) -> list[str]:
    failures = []
    jev, base = report.jev_accuracy, report.heuristic_on_answered
    if jev is None or base is None:
        failures.append("JEV answered no case")
    elif jev < base + MARGIN:
        failures.append(f"JEV precision {jev:.1%} < heuristic {base:.1%} + {MARGIN:.0%}")
    if report.abstain_rate is not None and report.abstain_rate > MAX_ABSTAIN:
        failures.append(f"abstain {report.abstain_rate:.1%} > {MAX_ABSTAIN:.0%}")
    fe = report.false_escalation_rate
    if fe is not None and fe > MAX_FALSE_ESCALATION:
        failures.append(f"false escalation {fe:.1%} > {MAX_FALSE_ESCALATION:.0%}")
    return failures


@dataclass(frozen=True)
class CallSample:
    """What one replay call cost: latency when it went out, and USD."""

    latency_ms: int | None
    cost_usd: float


def _ask(
    site: Site, case: ReplayCase, heuristic: object, transport: Transport, cfg: DecisionsConfig
) -> tuple[Outcome, CallSample]:
    call = SiteCall(site, heuristic)
    response, reason, latency = run_sync(
        [call], prompt_state(case.prompt, case.prior), transport=transport,
        cfg=cfg, timeout_s=REPLAY_TIMEOUT_S, session_id="replay",
    )
    outcome = resolve(call, response, "act", threshold_for(cfg, site), reason)
    went_out = reason != "cache-hit" and not reason.startswith("backoff")
    fresh = reason == "ok" and response is not None
    cost = (call_cost_usd(transport, response.usage) or 0.0) if fresh and response else 0.0
    return outcome, CallSample(latency if went_out else None, cost)


def _call_scores(samples: Sequence[CallSample], report: ReplayReport) -> None:
    latencies = [s.latency_ms for s in samples if s.latency_ms is not None]
    if not latencies:
        report.p50_latency_ms = report.cost_usd = None
        return
    report.p50_latency_ms = int(statistics.median(latencies))
    report.cost_usd = round(sum(s.cost_usd for s in samples), 10)


def replay(
    site: str, cases: Sequence[ReplayCase], *, transport: Transport | None, offline: bool = False
) -> ReplayReport:
    """Score ``cases`` for ``site``; offline (or no transport) = heuristic only."""
    target = SITES[site]
    heuristic = HEURISTICS[site]
    online = not offline and transport is not None
    cfg = load_decisions_config()  # the operator's thresholds are what ships
    rows: list[Row] = []
    samples: list[CallSample] = []
    for case in cases:
        h = heuristic(case)
        outcome = None
        if online and transport:
            outcome, sample = _ask(target, case, h, transport, cfg)
            samples.append(sample)
        rows.append((case, h, outcome))
    report = _base_report(target, rows)
    report.by_lang = _by_lang(rows, online)
    if online:
        _online_scores(target, rows, report)
        _call_scores(samples, report)
    report.failures = _corpus_failures(report) + (_gate_failures(report) if online else [])
    report.gate = "fail" if report.failures else ("pass" if online else "offline")
    return report


def _call_line(report: ReplayReport) -> str:
    if report.abstain_rate is None:  # set only by an online run
        return "- p50 latency / cost: not measured (offline)"
    if report.p50_latency_ms is None or report.cost_usd is None:
        return "- p50 latency / cost: not measured (all cache hits)"
    return f"- p50 latency: {report.p50_latency_ms} ms; cost: ${report.cost_usd:.6f}"


def _render(report: ReplayReport) -> str:
    lines = [f"# Replay — {report.site} ({report.gate})",
             f"- cases: {report.cases} (pt-PT {report.pt_share:.0%})",
             f"- heuristic accuracy: {report.heuristic_accuracy:.1%}"]
    if report.jev_accuracy is not None:
        lines += [f"- JEV precision (answered): {report.jev_accuracy:.1%} vs heuristic "
                  f"{(report.heuristic_on_answered or 0):.1%} on the same cases",
                  f"- act accuracy: {(report.act_accuracy or 0):.1%}",
                  f"- abstain: {(report.abstain_rate or 0):.1%} (unavailable {report.unavailable})"]
    lines.append(_call_line(report))
    if report.false_escalation_rate is not None:
        lines.append(f"- false escalation: {report.false_escalation_rate:.1%}")
    for lang, scores in report.by_lang.items():
        lines.append(f"- {lang}: " + ", ".join(f"{k}={v}" for k, v in scores.items()))
    lines += [f"- FAIL: {f}" for f in report.failures]
    return "\n".join(lines)


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m core.decisions.replay")
    parser.add_argument("--site", required=True, choices=sorted(SITES))
    parser.add_argument("--corpus", type=Path, default=None)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI: exit 0 pass/offline-valid, 1 gate failed, 2 usage error."""
    try:
        ns = _parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2
    try:
        cases = load_corpus(ns.site, ns.corpus)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    transport = None if ns.offline else resolve_transport(load_decisions_config())
    if not ns.offline and transport is None:
        print("error: no transport (set OPENROUTER_API_KEY) — or pass --offline", file=sys.stderr)
        return 2
    report = replay(ns.site, cases, transport=transport, offline=ns.offline)
    print(json.dumps(asdict(report), ensure_ascii=False, indent=2) if ns.json else _render(report))
    return 0 if report.gate != "fail" else 1


if __name__ == "__main__":
    raise SystemExit(main())
