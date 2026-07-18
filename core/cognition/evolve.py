"""Evolve — turn accumulated cross-project signals into instinct proposals.

Propose-only, LLM-free. The engine ingests the raw signals sessions
already accumulate (``~/.arkaos/gotchas.json`` — error patterns with
occurrence counts and the projects they appeared in) into the
``InsightStore`` as deterministic instincts: confidence derives from the
occurrence count inside the [0.3, 0.9] band, evidence_count mirrors the
raw count, and the record id is a stable digest of (source, title,
project) so re-ingestion is idempotent. It then renders a markdown
proposal at ``~/.arkaos/evolve-proposals/<date>.md`` with the
cross-project promotion candidates (``InsightStore.promotable`` — this
module is that API's first production caller) and the strongest
instincts.

Boundaries: Dreaming owns vault clustering (LLM, multi-backend) — evolve
never re-clusters markdown; it consumes structured stores only. Nothing
is promoted, modified, or deleted: the proposal file is the only output
(the reorganizer contract). Client identifiers are redacted and
project names are never rendered — only distinct-project counts.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from core.cognition.insights.store import InsightStore
from core.cognition.memory.schemas import (
    INSTINCT_CONFIDENCE_MAX,
    INSTINCT_CONFIDENCE_MIN,
    ActionableInsight,
)
from core.cognition.reorganizer import md_escape, redact_clients

_DEFAULT_OUTPUT_DIR = Path.home() / ".arkaos" / "evolve-proposals"
_DEFAULT_GOTCHAS_PATH = Path.home() / ".arkaos" / "gotchas.json"
_DEFAULT_DB_PATH = Path.home() / ".arkaos" / "insights.db"
_PROPOSAL_FILENAME_FMT = "%Y-%m-%d.md"
_CONFIDENCE_STEP = 0.1
_TOP_INSTINCTS = 10


@dataclass(frozen=True)
class PromotionCandidate:
    """Cross-project instinct eligible for promotion (propose-only)."""

    title: str
    project_count: int
    mean_confidence: float
    evidence_count: int


@dataclass(frozen=True)
class EvolveReport:
    """Evolve run outcome. Never contains client or project identifiers."""

    date: str
    ingested: int
    pending_instincts: int
    candidates: list[PromotionCandidate] = field(default_factory=list)
    proposal_path: str | None = None


def derive_confidence(count: int) -> float:
    """Occurrence count -> confidence, deterministic, inside the band."""
    raw = INSTINCT_CONFIDENCE_MIN + _CONFIDENCE_STEP * (max(1, count) - 1)
    return min(INSTINCT_CONFIDENCE_MAX, raw)


def _stable_id(source: str, title: str, project: str) -> str:
    digest = hashlib.sha1(f"{source}:{title}:{project}".encode())
    return digest.hexdigest()[:32]


def _load_gotchas(gotchas_path: Path) -> list[dict]:
    try:
        data = json.loads(gotchas_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    entries = data.get("gotchas") if isinstance(data, dict) else data
    return [e for e in entries or [] if isinstance(e, dict)]


def _instinct_from_gotcha(gotcha: dict, project: str) -> ActionableInsight | None:
    title = str(gotcha.get("pattern") or "").strip()
    if not title or not project.strip():
        return None
    count = int(gotcha.get("count") or 1)
    return ActionableInsight(
        id=_stable_id("gotcha", title, project),
        project=project,
        trigger="evolve-ingest",
        category="technical",
        severity="improve" if count >= 5 else "consider",
        title=title,
        description=str(gotcha.get("full_pattern") or title),
        recommendation=str(gotcha.get("suggestion") or "").strip()
        or "Recurring signal — consider a rule, skill, or fix.",
        context=f"tool={gotcha.get('tool', '?')} count={count}",
        confidence=derive_confidence(count),
        evidence_count=max(1, count),
    )


def ingest_gotchas(store: InsightStore, gotchas_path: Path) -> int:
    """Mirror gotcha signals into the store as project-scoped instincts.

    Deterministic derivation from the source of truth: re-ingesting
    recomputes the same ids and values (INSERT OR REPLACE), so repeat
    runs are idempotent.
    """
    ingested = 0
    for gotcha in _load_gotchas(gotchas_path):
        projects = gotcha.get("projects") or []
        for project in {str(p) for p in projects if str(p).strip()}:
            insight = _instinct_from_gotcha(gotcha, project)
            if insight is None:
                continue
            store.save(insight)
            ingested += 1
    return ingested


def _candidates(
    store: InsightStore, min_projects: int, min_confidence: float,
) -> list[PromotionCandidate]:
    titles = store.promotable(
        min_projects=min_projects, min_confidence=min_confidence
    )
    rows = [i for i in store.get_all_pending() if i.scope == "project"]
    out: list[PromotionCandidate] = []
    for title in titles:
        group = [i for i in rows if i.title == title]
        if not group:
            continue
        out.append(
            PromotionCandidate(
                title=title,
                project_count=len({i.project for i in group}),
                mean_confidence=round(
                    sum(i.confidence for i in group) / len(group), 2
                ),
                evidence_count=sum(i.evidence_count for i in group),
            )
        )
    return out


def build_proposal(
    *,
    db_path: Path | None = None,
    gotchas_path: Path | None = None,
    output_dir: Path | None = None,
    dry_run: bool = False,
    min_projects: int = 2,
    min_confidence: float = 0.8,
) -> EvolveReport:
    """Ingest signals, compute promotion candidates, write the proposal."""
    store = InsightStore(db_path or _DEFAULT_DB_PATH)
    ingested = ingest_gotchas(store, gotchas_path or _DEFAULT_GOTCHAS_PATH)
    pending = store.get_all_pending()
    candidates = _candidates(store, min_projects, min_confidence)
    date = datetime.now(UTC).strftime("%Y-%m-%d")
    markdown = _render(date, ingested, pending, candidates)
    if dry_run:
        print(markdown)
        return EvolveReport(date, ingested, len(pending), candidates)
    path = _write_report(markdown, output_dir)
    return EvolveReport(date, ingested, len(pending), candidates, str(path))


def _render_candidate(candidate: PromotionCandidate) -> str:
    title = md_escape(redact_clients(candidate.title))
    return (
        f"| {title} | {candidate.project_count} | "
        f"{candidate.mean_confidence:.2f} | {candidate.evidence_count} |"
    )


def _render_instinct(insight: ActionableInsight) -> str:
    title = md_escape(redact_clients(insight.title))
    rec = md_escape(redact_clients(insight.recommendation))
    return (
        f"- **{title}** — confidence {insight.confidence:.2f}, "
        f"evidence {insight.evidence_count}. {rec}"
    )


def _render(
    date: str,
    ingested: int,
    pending: list[ActionableInsight],
    candidates: list[PromotionCandidate],
) -> str:
    strongest = sorted(
        pending, key=lambda i: (i.confidence, i.evidence_count), reverse=True
    )[:_TOP_INSTINCTS]
    lines = [
        f"# Evolve proposal — {date}",
        "",
        "> Propose-only: nothing was promoted or modified. Review and",
        "> act via the squads; promotion stays a deliberate operator call.",
        "",
        "## Summary",
        "",
        f"- Instincts ingested this run: **{ingested}**",
        f"- Pending instincts in store: **{len(pending)}**",
        f"- Promotion candidates: **{len(candidates)}**",
        "",
        "## Promotion candidates (cross-project)",
        "",
    ]
    if candidates:
        lines += [
            "| Instinct | Projects | Mean confidence | Evidence |",
            "|---|---|---|---|",
            *[_render_candidate(c) for c in candidates],
        ]
    else:
        lines.append("None yet — needs the same signal in 2+ projects.")
    lines += ["", "## Strongest instincts", ""]
    if strongest:
        lines += [_render_instinct(i) for i in strongest]
    else:
        lines.append("Store is empty — no signals accumulated yet.")
    return "\n".join(lines) + "\n"


def _write_report(markdown: str, output_dir: Path | None) -> Path:
    """Atomic markdown write to an allowlisted output directory."""
    out = _validate_output_dir(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    report_path = out / datetime.now(UTC).strftime(
        _PROPOSAL_FILENAME_FMT
    )
    tmp_path = report_path.with_suffix(f".tmp-{os.getpid()}.md")
    tmp_path.write_text(markdown, encoding="utf-8")
    os.replace(tmp_path, report_path)
    return report_path


def _validate_output_dir(output_dir: Path | None) -> Path:
    """Allowlist writes to ~/.arkaos or the system tempdir (defence in
    depth — same contract as the reorganizer)."""
    if output_dir is None:
        return _DEFAULT_OUTPUT_DIR
    resolved = Path(output_dir).expanduser().resolve()
    allowed_roots = (
        (Path.home() / ".arkaos").resolve(),
        Path(tempfile.gettempdir()).resolve(),
    )
    for root in allowed_roots:
        try:
            resolved.relative_to(root)
            return resolved
        except ValueError:
            continue
    raise ValueError(
        "output_dir must be under one of "
        f"{[str(r) for r in allowed_roots]}; got {resolved}"
    )
