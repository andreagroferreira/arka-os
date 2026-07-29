"""Anti-self-approval guard for Quality Gate aggregate verdicts (PR-B3).

On 2026-07-20 an aggregate verdict entered the eval corpus with zero
reviewer artifacts behind it — the orchestrator's own words, recorded
as a completed gate. This guard makes that shape unrecordable AS AN
AGGREGATE: an aggregate verdict is only recorded when the session's
reviewer ledger holds at least two HOOK-CAPTURED reviewer verdicts,
no evidence_digest present on both sides disagrees (dispatch does not
yet REQUIRE the digest — PR-B4 makes it mandatory; an absent digest
warns instead of refusing, and when reviewers do populate it, as this
PR's own r1 artifacts did, the comparison decides), no CONFIRMED
reviewer blocker disappears silently, and an APPROVED aggregate
stands over no rejecting reviewer.

Only records whose ``source`` is in ``CAPTURE_SOURCES`` count: a
record the orchestrator could write itself (any other source) would
let it fabricate its own quorum, which is the exact disease.

Digest comparison runs against the artifacts on disk — the JSON that
was passed through the gate — never against a re-run of the evidence
engine: ``report_digest`` is per-report, not per-run (a re-run
digests differently on volatile pytest output), so re-running would
refuse every honest aggregate.

Trust boundary, stated honestly: the ledger lives in the operator's
home directory and this guard runs in the same trust domain as the
orchestrator it polices — a determined orchestrator could forge
records with a file write, either to FABRICATE a quorum or to
SUPPRESS an existing verdict (a forged newer record supersedes it —
same capability ceiling, different mechanics). Session ids are
validated against the ledger's safety rule, but nothing yet binds an
aggregate to the runtime session that produced the reviews — a past
session holding two reviewer records is a reusable quorum token
until PR-B4 binds the dispatch side. And ``--kind reviewer``
(record_cli) remains an unguarded label path for reviewer
identities: its ledger cross-reference is provenance, not
admission. The guard turns ACCIDENTAL self-approval into
deliberate, transcript-visible forgery; it does not and cannot make
forgery impossible from inside the same account.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from core.governance.reviewer_ledger import (
    _RECORD_NAME_RE,
    AGGREGATE_NAME,
    CAPTURE_SOURCES,
    IDENTITY_ALIASES,
    REVIEWER_IDS,
    _safe_id,
    _write_temp,
    ledger_root,
)

_MIN_REVIEWERS = 2

# A REFUTED drop needs a reason a reader can act on — "n/a" is not one.
_MIN_REFUTE_DETAIL = 40

# One id per person for operator-facing output: the deployed
# agent-file ids (.claude/agents/<id>.md). The config/constitution.yaml
# spellings are copy-director-eduardo / tech-director-francisca /
# cqo-marta — a different set (reviewer_ledger.py documents the map).
_CANONICAL_IDS = frozenset({"eduardo-copy", "francisca-tech", "marta-cqo"})


@dataclass(frozen=True)
class GuardResult:
    ok: bool
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    reviewers: list[str] = field(default_factory=list)


def _seq(record: dict) -> int:
    try:
        return int(record.get("seq", 0) or 0)
    except (TypeError, ValueError):
        return 0  # a forged seq must not turn the CLI into a traceback


def _session_records(session_id: str) -> list[tuple[str, dict]]:
    """(file name, record) for every readable ledger record, seq order."""
    if not _safe_id(session_id):
        return []
    session_dir = ledger_root() / session_id
    records: list[tuple[str, dict]] = []
    try:
        entries = sorted(session_dir.iterdir())
    except OSError:
        return records
    for item in entries:
        # Only names the ledger itself writes — operator notes, the
        # aggregate record and dot-prefixed files never enter the pool.
        # fullmatch, not match: $ accepts a trailing newline (the same
        # class _safe_id just fixed one file over).
        if item.name.startswith(".") or not _RECORD_NAME_RE.fullmatch(
            item.name
        ):
            continue
        try:
            data = json.loads(item.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict):
            records.append((item.name, data))
    records.sort(key=lambda pair: _seq(pair[1]))
    return records


def _counted(record: dict) -> bool:
    """True when a record counts toward the reviewer quorum.

    REVIEWER_IDS excludes the aggregator by construction — the
    disjointness with AGGREGATOR_IDS is pinned by test (an explicit
    exclusion clause here would be dead code the battery cannot kill).
    """
    reviewer_id = str(record.get("reviewer_id") or "")
    return (
        record.get("source") in CAPTURE_SOURCES
        and reviewer_id in REVIEWER_IDS
        and not record.get("parse_error")
        and isinstance(record.get("verdict"), dict)
    )


def _rejecting(record: dict) -> int:
    """Severity rank: 2 = REJECTED verdict, 1 = carries a CONFIRMED
    blocker, 0 = neither. Distinct ranks keep the r5 survivor shape
    separable — an APPROVED-carrying-CONFIRMED never ties a REJECTED,
    so filename byte order never decides between them."""
    verdict = record.get("verdict") or {}
    if _norm(verdict.get("verdict")) == "rejected":
        return 2
    if any(
        isinstance(b, dict) and _norm(b.get("verdict")) == "confirmed"
        for b in (verdict.get("blockers") or [])
    ):
        return 1
    return 0


def _spelling_winner(
    records: list[tuple[str, dict]]
) -> tuple[str, dict]:
    """The superseding record WITHIN one reviewer_id spelling.

    seq dominates, because here it is trustworthy: the ledger assigns
    it monotonically within a spelling (len of that reviewer_id's
    records + 1). A backwards clock step must not invert two rounds
    (QG r4), so the clock enters only LAST — on equal seq (the
    two-writer divergent-text window, or a reused seq after a record
    was removed) the higher severity wins, then the record clock;
    filename byte order never decides (QG r5).
    """
    return max(records, key=lambda p: (
        _seq(p[1]), _rejecting(p[1]), str(p[1].get("ts") or "")
    ))


def _cross_key(record: dict) -> tuple[int, str, int]:
    """Total order for choosing among spelling winners.

    Across spellings only the clock can prove recency (seq restarts
    per spelling — QG r3: an alias switch hid the newest REJECTED
    under seq ordering; _build_record writes ``ts`` as ISO-8601 UTC,
    so lexicographic order is chronological). A CLOCKLESS rejecting
    record sorts above everything: nothing can prove itself newer
    than it, so it is never superseded — fail-closed. Clocked records
    order by the clock, then severity. A total, transitive order: the
    winner never depends on iteration order (QG r5 M1).
    """
    ts = str(record.get("ts") or "")
    if not ts and _rejecting(record):
        return (1, "", 0)  # unsupersedable
    return (0, ts, _rejecting(record))


def _latest_per_reviewer(
    counted: list[tuple[str, dict]]
) -> list[tuple[str, dict]]:
    """The LATEST record per reviewer identity, two-level.

    A redo round supersedes that reviewer's earlier verdicts. Without
    this no real multi-round session could close honestly: the union
    over every historical record would demand that the final
    aggregate cover blockers already fixed in earlier rounds — or
    record them as REFUTED, which would be a false record (this
    campaign's own sessions hold 14+ rounds in one ledger directory).
    Level one reduces each SPELLING to its winner by seq
    (_spelling_winner); level two chooses among spelling winners by
    the total order of _cross_key — each signal used only where it
    is trustworthy, and both levels are keyed, so the outcome never
    depends on iteration order.
    """
    by_spelling: dict[str, list[tuple[str, dict]]] = {}
    for name, rec in counted:
        by_spelling.setdefault(
            str(rec.get("reviewer_id")), []
        ).append((name, rec))
    latest: dict[str, tuple[str, dict]] = {}
    for records in by_spelling.values():
        name, rec = _spelling_winner(records)
        identity = _identity(str(rec.get("reviewer_id")))
        held = latest.get(identity)
        if held is None or _cross_key(rec) > _cross_key(held[1]):
            latest[identity] = (name, rec)
    return list(latest.values())


def _identity(reviewer_id: str) -> str:
    """Canonical identity: aliases of one person count as ONE reviewer.

    Without this, ``eduardo-copy`` plus ``copy-director-eduardo`` —
    the same director under two dispatch spellings — would satisfy a
    two-reviewer quorum single-handedly. The deployed agent-file id is
    preferred for operator-facing output.
    """
    for group in IDENTITY_ALIASES:
        if reviewer_id in group:
            return next(
                (i for i in sorted(group) if i in _CANONICAL_IDS),
                min(group),
            )
    return reviewer_id


def _norm(text: object) -> str:
    return " ".join(str(text or "").lower().split())


def _tokens(text: object) -> frozenset[str]:
    return frozenset(
        t for t in re.split(r"[^a-z0-9]+", _norm(text)) if t
    )


def _blocker_key(blocker: dict) -> frozenset[str]:
    """Match key: check, else detail, else file — an empty check must
    not make a CONFIRMED blocker permanently uncoverable (liveness)."""
    return (
        _tokens(blocker.get("check"))
        or _tokens(blocker.get("detail"))
        or _tokens(blocker.get("file"))
    )


def _matches(a: frozenset[str], b: frozenset[str]) -> bool:
    """Token-set subset, either direction — never raw substrings.

    A substring rule let an aggregate entry with check "e" cover every
    reviewer blocker containing the letter (reproduced by the gate:
    two one-character REFUTED entries laundered five CONFIRMED
    blockers). Token subsets make coverage mean shared vocabulary.
    """
    return bool(a) and bool(b) and (a <= b or b <= a)


def _covered(key: frozenset[str], aggregate: dict, approved: bool) -> str:
    """Status of one CONFIRMED reviewer blocker against the aggregate.

    Returns "ok", "absent", "bare-refute" (REFUTED without a
    substantive reason) or "carried-approved" (kept un-refuted while
    the aggregate approves — flipping the decision instead of hiding
    the string is laundering too).
    """
    for entry in aggregate.get("blockers") or []:
        if not isinstance(entry, dict):
            continue
        if not _matches(key, _blocker_key(entry)):
            continue
        if _norm(entry.get("verdict")) == "refuted":
            if len(_norm(entry.get("detail"))) < _MIN_REFUTE_DETAIL:
                return "bare-refute"
            return "ok"
        return "carried-approved" if approved else "ok"
    return "absent"


def _digest_reasons(
    aggregate: dict, verdicts: list[tuple[str, dict]]
) -> tuple[list[str], list[str]]:
    """Compare evidence_digest across aggregate and reviewer verdicts."""
    reasons: list[str] = []
    warnings: list[str] = []
    agg_digest = _norm(aggregate.get("evidence_digest"))
    if not agg_digest:
        warnings.append("aggregate carries no evidence_digest")
        return reasons, warnings
    seen_any = False
    for reviewer_id, verdict in verdicts:
        their = _norm(verdict.get("evidence_digest"))
        if not their:
            continue
        seen_any = True
        if their != agg_digest:
            reasons.append(
                f"evidence_digest mismatch: {reviewer_id} reviewed "
                f"{their[:12]}…, aggregate cites {agg_digest[:12]}… — "
                "not the same evidence report"
            )
    if not seen_any:
        warnings.append(
            "no reviewer artifact carries evidence_digest (dispatch "
            "shape — PR-B4 enforces it); digest comparison had nothing "
            "to bite on"
        )
    return reasons, warnings


_COVERAGE_REASONS = {
    "absent": (
        "CONFIRMED blocker '{check}' ({rid}) absent from the aggregate "
        "and not REFUTED — a CONFIRMED finding never disappears silently"
    ),
    "bare-refute": (
        "CONFIRMED blocker '{check}' ({rid}) marked REFUTED without a "
        "substantive reason (>= 40 chars) — a drop needs its reason on "
        "the record"
    ),
    "carried-approved": (
        "CONFIRMED blocker '{check}' ({rid}) carried un-refuted while "
        "the aggregate is APPROVED — flipping the decision does not "
        "close a finding"
    ),
}


def _blocker_reasons(
    aggregate: dict, verdicts: list[tuple[str, dict]], approved: bool
) -> list[str]:
    """CONFIRMED reviewer blockers must not vanish (or be out-voted)."""
    reasons: list[str] = []
    for reviewer_id, verdict in verdicts:
        for blocker in verdict.get("blockers") or []:
            if not isinstance(blocker, dict):
                continue
            if _norm(blocker.get("verdict")) != "confirmed":
                continue
            key = _blocker_key(blocker)
            if not key:
                # Liveness (r2 M2): an unmatchable blocker must name an
                # achievable remedy, not deadlock the session forever.
                reasons.append(
                    f"CONFIRMED blocker with empty check/detail/file "
                    f"({reviewer_id}) cannot be matched — re-dispatch "
                    "the reviewer to file it with an identifiable "
                    "check; the redo round supersedes this record"
                )
                continue
            status = _covered(key, aggregate, approved)
            if status != "ok":
                reasons.append(_COVERAGE_REASONS[status].format(
                    check=_norm(blocker.get("check")) or "(no check field)",
                    rid=reviewer_id,
                ))
    return reasons


def _own_finding_warnings(
    aggregate: dict, verdicts: list[tuple[str, dict]]
) -> list[str]:
    """Aggregate blockers matching no reviewer blocker — warning only.

    Deliberate deviation from the plan's "never invent" literal, on
    record for operator ratification: the aggregate reproducing a
    defect neither reviewer saw is the veto working (marta-cqo-12
    caught a stale evidence doc that way); refusing it would launder
    the defect through.
    """
    reviewer_keys = [
        _blocker_key(b)
        for _, verdict in verdicts
        for b in (verdict.get("blockers") or [])
        if isinstance(b, dict)
    ]
    warnings: list[str] = []
    for entry in aggregate.get("blockers") or []:
        if not isinstance(entry, dict):
            continue
        key = _blocker_key(entry)
        if key and not any(_matches(key, rk) for rk in reviewer_keys):
            warnings.append(
                f"aggregate blocker '{_norm(entry.get('check'))}' matches "
                "no reviewer blocker (aggregate's own finding — allowed, "
                "recorded)"
            )
    return warnings


def _verdict_reasons(
    aggregate: dict, verdicts: list[tuple[str, dict]]
) -> list[str]:
    """An APPROVED aggregate stands over no rejecting reviewer."""
    if _norm(aggregate.get("verdict")) != "approved":
        return []
    return [
        f"{reviewer_id} returned REJECTED — an APPROVED aggregate over "
        "a rejecting reviewer is refused (quality SKILL step 4: any "
        "reviewer rejection loops back)"
        for reviewer_id, verdict in verdicts
        if _norm(verdict.get("verdict")) == "rejected"
    ]


def _quorum_shortfall(
    reviewers: list[str], artifacts: list[str]
) -> GuardResult:
    return GuardResult(
        ok=False,
        reasons=[
            f"{len(reviewers)} hook-captured reviewer verdict(s) in "
            f"the session ledger ({', '.join(reviewers) or 'none'}); "
            f"an aggregate needs >= {_MIN_REVIEWERS} distinct "
            "reviewers that are not the aggregator"
        ],
        artifacts=artifacts,
        reviewers=reviewers,
    )


def check_aggregate(aggregate: dict, session_id: str) -> GuardResult:
    """Refuse an aggregate the session ledger cannot support.

    Quorum, verdicts and blocker coverage are computed over the LATEST
    hook-captured record per reviewer identity — see
    _latest_per_reviewer.
    """
    if not session_id:
        return GuardResult(ok=False, reasons=["--session-id is mandatory"])
    if not _safe_id(session_id):  # refuse loudly, with the reason
        return GuardResult(ok=False, reasons=[
            f"session id {session_id!r} fails the ledger safety rule "
            "(path separators, leading dots and oversize ids are "
            "refused — a session id is a directory name, not a path)"
        ])
    counted = _latest_per_reviewer([
        (name, rec) for name, rec in _session_records(session_id)
        if _counted(rec)
    ])
    reviewers = sorted({
        _identity(str(r.get("reviewer_id"))) for _, r in counted
    })
    if len(reviewers) < _MIN_REVIEWERS:
        return _quorum_shortfall(
            reviewers, [name for name, _ in counted]
        )
    verdicts = [(str(r.get("reviewer_id")), r["verdict"]) for _, r in counted]
    reasons, warnings = _reasons(aggregate, verdicts)
    return GuardResult(
        ok=not reasons,
        reasons=reasons,
        warnings=warnings,
        artifacts=[name for name, _ in counted],
        reviewers=reviewers,
    )


def _reasons(
    aggregate: dict, verdicts: list[tuple[str, dict]]
) -> tuple[list[str], list[str]]:
    """Every refusal reason and warning for one aggregate."""
    approved = _norm(aggregate.get("verdict")) == "approved"
    digest_reasons, warnings = _digest_reasons(aggregate, verdicts)
    reasons = (
        digest_reasons
        + _verdict_reasons(aggregate, verdicts)
        + _blocker_reasons(aggregate, verdicts, approved)
    )
    return reasons, warnings + _own_finding_warnings(aggregate, verdicts)


def write_aggregate(
    session_id: str, aggregate: dict, result: GuardResult
) -> Path | None:
    """Persist the accepted aggregate atomically; None on any failure.

    The caller must treat None as a refusal: an accepted-but-unwritten
    aggregate recorded anyway would be the incident shape again, one
    filesystem error away.
    """
    if not result.ok:  # the guard's own writer never files a refusal
        return None
    if not _safe_id(session_id):  # a hostile id never creates a dir
        return None
    session_dir = ledger_root() / session_id
    try:
        session_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    except OSError:
        return None
    tmp = _write_temp(
        session_dir, AGGREGATE_NAME, _aggregate_record(session_id, aggregate, result)
    )
    if tmp is None:
        return None
    path = session_dir / AGGREGATE_NAME
    try:
        # Atomic replace: a redo round re-issues the aggregate and there
        # must be no window with neither version on disk.
        os.replace(tmp, path)
    except OSError:
        with contextlib.suppress(OSError):
            tmp.unlink(missing_ok=True)
        return None
    return path if path.is_file() else None


def _aggregate_record(
    session_id: str, aggregate: dict, result: GuardResult
) -> dict:
    return {
        "ts": datetime.now(UTC).isoformat(),
        "session_id": session_id,
        "aggregate": aggregate,
        "aggregate_verdict_digest": _aggregate_digest(aggregate),
        "artifacts": result.artifacts,
        "reviewers": result.reviewers,
        "warnings": result.warnings,
    }


def _aggregate_digest(aggregate: dict) -> str:
    try:
        from core.governance.qg_digest import verdict_digest

        return verdict_digest(aggregate)
    except Exception:  # digest is provenance, never a blocker
        return ""
