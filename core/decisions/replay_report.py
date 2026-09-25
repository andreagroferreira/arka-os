"""Replay report — N measured runs per site, the D2 proposal, one evidence folder.

``arka-py -m core.decisions.replay_report (--all | --sites a,b) --session <id>
[--runs 2] [--live-window 7d]`` (spec PR5, decision D1).

* Each run is :func:`core.decisions.replay.replay` at the site's REAL
  ceiling (``site_timeout_ms``; there is no ``--timeout-ms``) on a config
  copy with ``cacheTtlSeconds=0``: ``cache.get`` misses by construction,
  so run 2 asks the endpoint again instead of reading run 1's answers.
* A run is **measured** only when ≥ :data:`MIN_REACHED_SHARE` of the
  cases that asked a question reached the endpoint and ≤
  :data:`MAX_UNAVAILABLE_SHARE` of all cases were unavailable. Otherwise
  it is ``not-measured``: it moves no mode and the CLI exits 1.
* The gate per run is the replay gate (Jev ≥ heuristic + 5 pp on the
  answered cases, abstain ≤ 25 %, false escalation ≤ 5 %, MAE ≤ 5.0 for
  slop-score). :func:`core.decisions.promotion.propose_mode` turns the
  runs into a proposal against ``Site.default_mode``; nothing here edits
  config or code.
* Replay calls land in the cost ledger as ``decision-replay``.
* The ``live`` column (``telemetry.summarise`` over ``--live-window``) is
  informational: it never decides a mode.

Writes ``~/.arkaos/quality-gate/<session>/replay-final/``:
``<site>-run<k>.json``, ``REPORT.md``, ``SUMMARY.json``, ``PROPOSALS.json``.
Exit codes: 0 every site measured, 1 some run not measured, 2 usage /
bypass / no transport / bad corpus.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.decisions.config import (
    DecisionsConfig,
    Mode,
    bypassed,
    load_decisions_config,
)
from core.decisions.promotion import ModeProposal, RunGate, RunVerdict, propose_mode
from core.decisions.registry import SITES
from core.decisions.replay import ReplayCase, ReplayReport, default_corpus_path, load_corpus, replay
from core.decisions.telemetry import REPLAY_COST_CATEGORY, SiteSummary, summarise
from core.decisions.transport import Transport, resolve_transport

MIN_REACHED_SHARE = 0.90
MAX_UNAVAILABLE_SHARE = 0.10
OUT_DIRNAME = "replay-final"
SESSION_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
LIVE_WINDOWS: dict[str, str] = {
    "today": "today", "7d": "week", "week": "week", "30d": "month", "month": "month",
    "all": "all",
}
LIVE_DRIFT_ABSTAIN_PCT = 25.0
LIVE_DRIFT_MIN_CALLS = 50
LIVE_DRIFT_PERIODS = frozenset({"week", "month", "all"})  # windows of >= 7 days


@dataclass
class SiteRun:
    """One replay run of one site and whether it counts."""

    run: int
    gate: RunGate
    why_not_measured: str
    report: ReplayReport
    ts: str


@dataclass
class LiveView:
    """Informational live telemetry for one site (never decides a mode)."""

    calls: int
    abstain_attributable_pct: float | None
    fallback_pct: float
    acted_jev_pct: float
    top_fallback_reasons: list[tuple[str, int]]
    live_drift: bool


@dataclass
class SiteResult:
    """Every run of one site, its corpus digest, modes and the proposal."""

    site: str
    corpus_sha256: str
    default_mode: Mode
    effective_mode: Mode
    runs: list[SiteRun]
    proposal: ModeProposal
    live: LiveView | None = None
    cost_usd: float = 0.0
    run_files: list[str] = field(default_factory=list)


@dataclass
class RunContext:
    """What every site's runs share."""

    transport: Transport
    cfg: DecisionsConfig
    operator_cfg: DecisionsConfig
    runs: int
    out_dir: Path
    live: dict[str, SiteSummary]
    live_period: str


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def corpus_digest(site: str) -> str:
    """sha256 of the corpus file as shipped (a relabel changes it)."""
    return hashlib.sha256(default_corpus_path(site).read_bytes()).hexdigest()


def no_cache_config(cfg: DecisionsConfig) -> DecisionsConfig:
    """``cfg`` with the answer cache off: every run asks the endpoint."""
    return cfg.model_copy(update={"cache_ttl_seconds": 0})


def effective_mode(cfg: DecisionsConfig, site: str) -> Mode:
    """The operator's override when present, else the site default (bypass ignored)."""
    override = cfg.sites.get(site)
    return override.mode if override is not None else SITES[site].default_mode


def measure(report: ReplayReport) -> tuple[RunGate, str]:
    """The run's gate, or ``not-measured`` with the reason."""
    if report.asked is None or report.reached is None:
        return "not-measured", "offline run"
    if report.asked == 0:
        return "not-measured", "no case asked a question"
    reached = report.reached / report.asked
    if reached < MIN_REACHED_SHARE:
        return "not-measured", (f"{reached:.0%} of asked cases reached the endpoint "
                                f"(< {MIN_REACHED_SHARE:.0%})")
    unavailable = report.unavailable / report.cases if report.cases else 1.0
    if unavailable > MAX_UNAVAILABLE_SHARE:
        return "not-measured", f"unavailable {unavailable:.0%} (> {MAX_UNAVAILABLE_SHARE:.0%})"
    return ("pass" if report.gate == "pass" else "fail"), ""


def live_view(summary: SiteSummary | None, period: str) -> LiveView | None:
    """The live column for one site; ``live_drift`` flags a new run + corpus review."""
    if summary is None:
        return None
    pct = summary.abstain_attributable_pct
    drift = (period in LIVE_DRIFT_PERIODS and summary.calls >= LIVE_DRIFT_MIN_CALLS
             and pct is not None and pct > LIVE_DRIFT_ABSTAIN_PCT)
    return LiveView(summary.calls, pct, summary.fallback_pct, summary.acted_jev_pct,
                    list(summary.top_fallback_reasons), drift)


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
                    encoding="utf-8")


def _run_once(
    site: str, k: int, cases: Sequence[ReplayCase], ctx: RunContext, digest: str
) -> SiteRun:
    print(f"replay {site} run {k}/{ctx.runs} ({len(cases)} cases)", file=sys.stderr)
    report = replay(site, cases, transport=ctx.transport, cfg=ctx.cfg)
    gate, why = measure(report)
    run = SiteRun(k, gate, why, report, _now_iso())
    _write_json(ctx.out_dir / f"{site}-run{k}.json", {
        **asdict(report), "run": k, "measured_gate": gate, "why_not_measured": why,
        "corpus_sha256": digest, "cost_category": REPLAY_COST_CATEGORY, "ts": run.ts,
    })
    return run


def run_site(site: str, cases: Sequence[ReplayCase], ctx: RunContext) -> SiteResult:
    """``ctx.runs`` sequential runs of one site, then the D2 proposal."""
    digest = corpus_digest(site)
    runs = [_run_once(site, k, cases, ctx, digest) for k in range(1, ctx.runs + 1)]
    verdicts = [RunVerdict(r.gate, r.report.abstain_rate, digest, r.ts) for r in runs]
    default = SITES[site].default_mode
    return SiteResult(
        site=site, corpus_sha256=digest, default_mode=default,
        effective_mode=effective_mode(ctx.operator_cfg, site), runs=runs,
        proposal=propose_mode(site, default, verdicts),
        live=live_view(ctx.live.get(site), ctx.live_period),
        cost_usd=round(sum(r.report.cost_usd or 0.0 for r in runs), 10),
        run_files=[f"{site}-run{r.run}.json" for r in runs],
    )


# --- rendering ----------------------------------------------------------------


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value:.1%}"


def _num(value: object) -> str:
    return "—" if value is None else str(value)


def _run_row(result: SiteResult, run: SiteRun) -> str:
    r = run.report
    gate = run.gate if not run.why_not_measured else f"not-measured ({run.why_not_measured})"
    return (
        f"| `{result.site}` | {run.run} | {r.cases} | {r.pt_share:.0%} | "
        f"{_pct(r.jev_accuracy)} vs {_pct(r.heuristic_on_answered)} | {_pct(r.abstain_rate)} | "
        f"{_pct(r.false_escalation_rate)} | {_num(r.mean_abs_error)} | "
        f"{_num(r.p50_latency_ms)} | {_num(r.timeout_ms)} | "
        f"{_num(r.reached)}/{_num(r.asked)} | ${(r.cost_usd or 0.0):.6f} | {gate} |"
    )


def _mode_cell(result: SiteResult) -> str:
    if result.effective_mode == result.default_mode:
        return result.default_mode
    return f"{result.default_mode} (operator override: {result.effective_mode})"


def _proposal_row(result: SiteResult) -> str:
    p = result.proposal
    return (f"| `{result.site}` | {_mode_cell(result)} | {p.action} → {p.proposed} | "
            f"{p.reason} | `{result.corpus_sha256[:16]}` |")


def _live_row(result: SiteResult) -> str:
    lv = result.live
    if lv is None:
        return f"| `{result.site}` | 0 | — | — | — | — | |"
    reasons = ", ".join(f"{r} {n}" for r, n in lv.top_fallback_reasons) or "—"
    drift = "live-drift" if lv.live_drift else ""
    return (f"| `{result.site}` | {lv.calls} | {_pct_raw(lv.abstain_attributable_pct)} | "
            f"{lv.fallback_pct:.1f}% | {lv.acted_jev_pct:.1f}% | {reasons} | {drift} |")


def _pct_raw(value: float | None) -> str:
    return "—" if value is None else f"{value:.1f}%"


def render_report(results: Sequence[SiteResult], meta: dict[str, Any]) -> str:
    """REPORT.md: runs, proposals, then the informational live column."""
    lines = [
        f"# Replay report — session {meta['session']}", "",
        f"- Generated: {meta['generated_at']}; runs per site: {meta['runs']}; "
        f"answer cache: off (cacheTtlSeconds=0); ceiling: each site's timeout_ms",
        f"- A run counts only when ≥ {MIN_REACHED_SHARE:.0%} of asked cases reached the "
        f"endpoint and ≤ {MAX_UNAVAILABLE_SHARE:.0%} were unavailable",
        f"- Replay cost: ${meta['cost_usd']:.6f} (ledger category `{REPLAY_COST_CATEGORY}`)",
        "", "## Runs", "",
        "| Site | Run | Cases | pt-PT | Jev vs heuristic (answered) | Abstain | False esc. | "
        "MAE | p50 ms | Ceiling ms | Reached | Cost | Gate |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    lines += [_run_row(res, run) for res in results for run in res.runs]
    lines += ["", "## Proposals (rule D2; the PR applies them to `default_mode`)", "",
              "| Site | Mode (default) | Proposal | Why | Corpus sha256 |", "|---|---|---|---|---|"]
    lines += [_proposal_row(res) for res in results]
    lines += ["", f"## Live telemetry ({meta['live_window']}) — informational, never decides "
              "a mode", "",
              "| Site | Calls | Abstain (attributable) | Fallback | Acted Jev | Top fallback "
              "reasons | Flag |", "|---|---|---|---|---|---|---|"]
    lines += [_live_row(res) for res in results]
    return "\n".join(lines) + "\n"


def summary_payload(results: Sequence[SiteResult], meta: dict[str, Any]) -> dict[str, Any]:
    """SUMMARY.json: what the ADR cites per site."""
    sites = {
        res.site: {
            "corpus_sha256": res.corpus_sha256,
            "default_mode": res.default_mode, "effective_mode": res.effective_mode,
            "operator_override": res.effective_mode != res.default_mode,
            "gates": [r.gate for r in res.runs],
            "why_not_measured": [r.why_not_measured for r in res.runs],
            "abstain": [r.report.abstain_rate for r in res.runs],
            "proposal": asdict(res.proposal), "cost_usd": res.cost_usd,
            "live": asdict(res.live) if res.live else None, "run_files": res.run_files,
        }
        for res in results
    }
    return {**meta, "sites": sites}


def write_outputs(results: Sequence[SiteResult], meta: dict[str, Any], out_dir: Path) -> None:
    """REPORT.md, SUMMARY.json and PROPOSALS.json next to the run files."""
    (out_dir / "REPORT.md").write_text(render_report(results, meta), encoding="utf-8")
    _write_json(out_dir / "SUMMARY.json", summary_payload(results, meta))
    _write_json(out_dir / "PROPOSALS.json", [asdict(r.proposal) for r in results])


# --- CLI ----------------------------------------------------------------------


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="arka-py -m core.decisions.replay_report")
    which = parser.add_mutually_exclusive_group(required=True)
    which.add_argument("--all", action="store_true", help="every registered site")
    which.add_argument("--sites", help="comma-separated site names")
    parser.add_argument("--session", required=True, help="quality-gate session id")
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--live-window", choices=sorted(LIVE_WINDOWS), default="7d")
    return parser.parse_args(argv)


def selected_sites(ns: argparse.Namespace) -> list[str]:
    """Registry order for ``--all``; ValueError names an unknown site."""
    if ns.all:
        return list(SITES)
    names = [n.strip() for n in str(ns.sites).split(",") if n.strip()]
    unknown = [n for n in names if n not in SITES]
    if unknown or not names:
        raise ValueError(f"unknown site(s): {', '.join(unknown) or '(none given)'}")
    return names


def output_dir(session: str) -> Path:
    """``~/.arkaos/quality-gate/<session>/replay-final`` (HOME read at call time)."""
    if not SESSION_RE.fullmatch(session) or ".." in session:
        raise ValueError(f"invalid session id: {session!r}")
    return Path.home() / ".arkaos" / "quality-gate" / session / OUT_DIRNAME


def _validate(ns: argparse.Namespace) -> tuple[list[str], dict[str, list[ReplayCase]], Path]:
    if ns.runs < 1:
        raise ValueError("--runs must be >= 1")
    names = selected_sites(ns)
    out_dir = output_dir(ns.session)
    # Every corpus is loaded before the first call: a bad one costs nothing.
    return names, {n: load_corpus(n) for n in names}, out_dir


def _context(ns: argparse.Namespace, out_dir: Path) -> RunContext | None:
    operator_cfg = load_decisions_config()
    transport = resolve_transport(operator_cfg)
    if transport is None:
        return None
    period = LIVE_WINDOWS[ns.live_window]
    return RunContext(transport, no_cache_config(operator_cfg), operator_cfg, ns.runs,
                      out_dir, summarise(period).by_site, period)


def _meta(ns: argparse.Namespace, results: Sequence[SiteResult]) -> dict[str, Any]:
    measured = all(r.gate != "not-measured" for res in results for r in res.runs)
    return {"session": ns.session, "generated_at": _now_iso(), "runs": ns.runs,
            "live_window": ns.live_window, "all_measured": measured,
            "cost_usd": round(sum(r.cost_usd for r in results), 10),
            "cost_category": REPLAY_COST_CATEGORY,
            "rule": {"min_reached_share": MIN_REACHED_SHARE,
                     "max_unavailable_share": MAX_UNAVAILABLE_SHARE}}


def _prepare(argv: Sequence[str] | None) -> tuple[RunContext, dict[str, list[ReplayCase]],
                                                    argparse.Namespace] | int:
    try:
        ns = _parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2
    if bypassed():
        print("error: ARKA_BYPASS_DECISIONS=1 — no replay calls", file=sys.stderr)
        return 2
    try:
        names, corpora, out_dir = _validate(ns)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    ctx = _context(ns, out_dir)
    if ctx is None:
        print("error: no transport (set OPENROUTER_API_KEY)", file=sys.stderr)
        return 2
    return ctx, {n: corpora[n] for n in names}, ns


def main(argv: Sequence[str] | None = None) -> int:
    """CLI: 0 every run measured, 1 some run not measured, 2 usage / no transport."""
    prepared = _prepare(argv)
    if isinstance(prepared, int):
        return prepared
    ctx, corpora, ns = prepared
    ctx.out_dir.mkdir(parents=True, exist_ok=True)
    results = [run_site(site, cases, ctx) for site, cases in corpora.items()]
    meta = _meta(ns, results)
    write_outputs(results, meta, ctx.out_dir)
    print(render_report(results, meta))
    print(f"written: {ctx.out_dir}", file=sys.stderr)
    return 0 if meta["all_measured"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
