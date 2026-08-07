"""Anti-self-approval guard for Quality Gate aggregate verdicts (PR-B3).

On 2026-07-20 an aggregate verdict entered the eval corpus with zero
reviewer artifacts behind it — the orchestrator's own words, recorded
as a completed gate. This guard makes that shape unrecordable AS AN
AGGREGATE: an aggregate verdict is only recorded when the session's
reviewer ledger holds at least two HOOK-CAPTURED reviewer verdicts,
the digest chain holds (PR-B4 dispatch shape: the aggregate and every
counted reviewer artifact must carry evidence_digest, and each
reviewer's digest must match the aggregate's — or be excused by an
explicit, justified ``digest_carries`` entry naming the report that
reviewer actually reviewed), no CONFIRMED reviewer blocker disappears
silently, and an APPROVED aggregate stands over no rejecting reviewer.

Severity is verdict-aware (PR-B4): fabrication vectors — quorum, an
APPROVED over a rejecting reviewer, a vanishing CONFIRMED blocker —
refuse regardless of verdict; dispatch-shape issues (digest chain,
session binding) refuse only an APPROVED aggregate and demote to
warnings on a REJECTED one, so a rejection label survives exactly the
case where the CQO catches a bad delta.

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
same capability ceiling, different mechanics). Session binding
(PR-B4) closes the COMMON reuse path, not every path: the SessionEnd
hook stamps a session's ledger directory (``.ended``), and an
APPROVED aggregate citing a stamped session is refused. A session
that crashes never fires SessionEnd and stays unstamped — and in
observed practice SessionEnd fires for a minority of sessions, so an
unstamped ledger proves nothing about liveness. A session still open
elsewhere is citable from this one, and the stamp itself is a file
the same account could delete: the binding is evidence from the
hook boundary, not a cryptographic seal. ``--kind
reviewer`` (record_cli) likewise remains an unguarded label path for
reviewer identities: its ledger cross-reference is provenance, not
admission. The guard turns ACCIDENTAL self-approval into deliberate,
transcript-visible forgery; it does not and cannot make forgery
impossible from inside the same account.
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


def _carries(aggregate: dict) -> dict[str, dict]:
    """Declared digest carries, keyed by canonical reviewer identity."""
    carries: dict[str, dict] = {}
    for entry in aggregate.get("digest_carries") or []:
        if isinstance(entry, dict):
            carries[_identity(str(entry.get("reviewer") or ""))] = entry
    return carries


def _carry_issue(
    reviewer_id: str, their: str, agg_digest: str, carry: dict | None
) -> str | None:
    """Why a digest mismatch is NOT excused by a declared carry.

    None means the carry stands: it names the digest the reviewer's own
    artifact carries, with a substantive reason. Anything else is the
    plain mismatch — an undeclared carry, a carry pointing at a digest
    the reviewer never reviewed, or a bare justification.
    """
    if carry is None:
        return (
            f"evidence_digest mismatch: {reviewer_id} reviewed "
            f"{their[:12]}…, aggregate cites {agg_digest[:12]}… — not "
            "the same evidence report; re-dispatch the reviewer or "
            "declare a justified digest_carries entry (PR-B4)"
        )
    if _norm(carry.get("evidence_digest")) != their:
        return (
            f"digest carry for {reviewer_id} names "
            f"{_norm(carry.get('evidence_digest'))[:12]}… but the "
            f"reviewer's artifact carries {their[:12]}… — a carry must "
            "cite the report that reviewer actually reviewed"
        )
    if len(_norm(carry.get("reason"))) < _MIN_REFUTE_DETAIL:
        return (
            f"digest carry for {reviewer_id} lacks a substantive reason "
            f"(>= {_MIN_REFUTE_DETAIL} chars — the same bar as a REFUTED "
            "drop): why does the earlier review still stand?"
        )
    return None


_MISSING_AGGREGATE_DIGEST = (
    "aggregate carries no evidence_digest — the dispatch shape (PR-B4) "
    "requires the aggregator to cite the report it aggregated "
    "(report_digest from the evidence --json output)"
)
_MISSING_REVIEWER_DIGEST = (
    "{rid} artifact carries no evidence_digest — the dispatch must "
    "populate it (PR-B4 dispatch shape); re-dispatch that reviewer "
    "with the report_digest"
)
_CARRY_ACCEPTED = (
    "digest carry accepted: {rid} reviewed {their}… while the "
    "aggregate cites {agg}… — justification on the record"
)


def _digest_issues(
    aggregate: dict, verdicts: list[tuple[str, dict]]
) -> tuple[list[str], list[str]]:
    """Dispatch-shape and integrity issues on the digest chain (PR-B4).

    Returns (issues, notes). Issues are verdict-aware at the caller:
    they refuse an APPROVED aggregate and are demoted to warnings on a
    REJECTED one. Notes (accepted carries) are always warnings — a
    carry is legitimate, and legitimate is not invisible.
    """
    issues: list[str] = []
    notes: list[str] = []
    agg_digest = _norm(aggregate.get("evidence_digest"))
    if not agg_digest:
        issues.append(_MISSING_AGGREGATE_DIGEST)
    carries = _carries(aggregate)
    for reviewer_id, verdict in verdicts:
        their = _norm(verdict.get("evidence_digest"))
        if not their:
            issues.append(_MISSING_REVIEWER_DIGEST.format(rid=reviewer_id))
            continue
        if not agg_digest or their == agg_digest:
            continue
        issue = _carry_issue(
            reviewer_id, their, agg_digest, carries.get(_identity(reviewer_id))
        )
        if issue is not None:
            issues.append(issue)
        else:
            notes.append(_CARRY_ACCEPTED.format(
                rid=reviewer_id, their=their[:12], agg=agg_digest[:12]
            ))
    return issues, notes


def _ended_issues(session_id: str, artifact_names: list[str]) -> list[str]:
    """A stamped session is not a live quorum (PR-B4 session binding).

    M4 hardening (PR-B5): the stamp only outlaws records that PREDATE
    it. A counted record captured strictly after the stamp's mtime
    proves the hook boundary came back to life under this session id —
    never observed on the dev machine, where the stamp shipped one
    release earlier and the ledger held a single stamped session when
    this was written; the refusal must not outlive its own evidence.
    Ties and unreadable mtimes keep the refusal: equality cannot
    distinguish before from after, and fail-closed is the guard's
    resting state.
    """
    from core.governance.reviewer_ledger import ENDED_NAME

    session_dir = ledger_root() / session_id
    stamp = session_dir / ENDED_NAME
    if not stamp.is_file():
        return []
    try:
        newest = max(
            (session_dir / name).stat().st_mtime for name in artifact_names
        )
        if newest > stamp.stat().st_mtime:
            return []
    except (OSError, ValueError):
        pass  # no readable counted record newer than the stamp
    return [
        f"session {session_id} is marked ended (SessionEnd stamped its "
        "ledger) — a past session's reviewer records are not a reusable "
        "quorum token; run the reviews in the live session"
    ]


def _check_key_warnings(
    verdicts: list[tuple[str, dict]]
) -> list[str]:
    """CONFIRMED blockers filed without a check key — warning only.

    Coverage still matches on detail/file tokens (_blocker_key keeps
    liveness), but the dispatch shape asks reviewers to name the
    evidence check so coverage means shared vocabulary, not prose luck.
    """
    warnings: list[str] = []
    for reviewer_id, verdict in verdicts:
        for blocker in verdict.get("blockers") or []:
            if not isinstance(blocker, dict):
                continue
            if _norm(blocker.get("verdict")) != "confirmed":
                continue
            if not _tokens(blocker.get("check")) and _blocker_key(blocker):
                warnings.append(
                    f"CONFIRMED blocker ({reviewer_id}) filed without a "
                    "check key — matched on detail/file tokens; the "
                    "dispatch shape (PR-B4) asks for the evidence check "
                    "name in 'check'"
                )
    return warnings


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
    reasons, warnings = _reasons(
        aggregate, verdicts, session_id, [name for name, _ in counted]
    )
    return GuardResult(
        ok=not reasons,
        reasons=reasons,
        warnings=warnings,
        artifacts=[name for name, _ in counted],
        reviewers=reviewers,
    )


def _reasons(
    aggregate: dict,
    verdicts: list[tuple[str, dict]],
    session_id: str,
    artifact_names: list[str],
) -> tuple[list[str], list[str]]:
    """Every refusal reason and warning for one aggregate.

    Two severities, split on the aggregate's own verdict (PR-B4 item 7).
    Fabrication vectors — an APPROVED standing over a rejecting
    reviewer, a CONFIRMED blocker vanishing — refuse regardless of
    verdict. Dispatch-shape issues (digest chain, session binding)
    refuse only an APPROVED aggregate: refusing a REJECTED one over
    shape would throw away the rejection label in exactly the case
    where the CQO catches a bad delta, and a recorded rejection
    launders nothing — the redo loop continues either way.
    """
    approved = _norm(aggregate.get("verdict")) == "approved"
    issues, notes = _digest_issues(aggregate, verdicts)
    issues += _ended_issues(session_id, artifact_names)
    reasons = (
        _verdict_reasons(aggregate, verdicts)
        + _blocker_reasons(aggregate, verdicts, approved)
    )
    warnings = (
        notes
        + _check_key_warnings(verdicts)
        + _own_finding_warnings(aggregate, verdicts)
    )
    if approved:
        return issues + reasons, warnings
    demoted = [
        f"{issue} [recorded anyway: the refusal is verdict-aware "
        "(PR-B4) — a REJECTED label is never lost to dispatch shape]"
        for issue in issues
    ]
    return reasons, demoted + warnings


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
