"""Record a QGVerdict or gate JudgeVerdict as an eval label.

Reads the verdict JSON from stdin (or --file) and appends it to the
matching label corpus (``--kind qg``/``--kind reviewer`` →
qg-verdicts.jsonl, ``--kind judge`` → judge-verdicts.jsonl). Invoked by
the orchestrator right after a verdict lands (see the Quality Gate and
flow skill instructions), closing the "labels gratuitos" loop from the
evals ADR.

``--kind qg`` is the AGGREGATE path and runs the anti-self-approval
guard (PR-B3): ``--session-id`` is mandatory and validated, the
session's reviewer ledger must hold at least two hook-captured
reviewer verdicts, no evidence_digest present on both sides may
disagree (an absent digest warns — PR-B4 makes dispatch populate it),
no CONFIRMED reviewer blocker may disappear silently, and an APPROVED
aggregate may not stand over a rejecting reviewer. The label records
ONLY once AGGREGATE.json is verifiably on disk — an
accepted-but-unwritten aggregate is a refusal, not a success.

``--kind reviewer`` records an individual reviewer's verdict as a
label and cross-references the ledger by ``verdict_digest`` — it never
writes ledger records (only the hook capture may; anything the
orchestrator could write itself would let it fabricate its own
quorum), and it refuses aggregator identities: the aggregator's
verdict enters through the guarded ``--kind qg`` path, never as a
"reviewer" label. For reviewer identities it remains an unguarded
label path — the cross-reference is provenance, not admission.

Unlike the underlying writer (telemetry contract: never raises), this
explicit CLI fails LOUDLY on invalid verdict JSON — a malformed label
recorded silently would poison the corpus.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import ValidationError

from core.evals.verdict_labels import record_judge_label, record_verdict_label
from core.governance.judge import JudgeVerdict
from core.governance.qg_verdict import QGVerdict

if TYPE_CHECKING:  # the runtime import stays lazy (guard pulls pydantic)
    from core.governance.aggregate_guard import GuardResult


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", help="verdict JSON file (default: stdin)")
    parser.add_argument(
        "--kind",
        choices=("qg", "reviewer", "judge"),
        default="qg",
        help=(
            "qg = aggregate QGVerdict, guarded (default); reviewer = "
            "individual reviewer QGVerdict; judge = gate JudgeVerdict"
        ),
    )
    parser.add_argument("--deliverable", default="")
    parser.add_argument("--department", default="")
    parser.add_argument("--eval-task-id", default="")
    parser.add_argument("--session-id", default="")
    parser.add_argument("--round", default="", dest="round_label")
    parser.add_argument("--head", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    raw = _read_raw(args)
    if raw is None:
        return 1
    if args.kind == "judge":
        return _record_judge(raw, args)
    verdict = _parse_qg(raw)
    if verdict is None:
        return 1
    if args.kind == "reviewer":
        return _record_reviewer(verdict, args)
    return _record_aggregate(verdict, args)


def _read_raw(args: argparse.Namespace) -> str | None:
    """Verdict text, or None after a LOUD error (never a traceback)."""
    if not args.file:
        return sys.stdin.read()
    try:
        return Path(args.file).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"error: cannot read --file — {exc}", file=sys.stderr)
        return None


def _parse_qg(raw: str) -> QGVerdict | None:
    try:
        return QGVerdict.model_validate(json.loads(raw))
    except (json.JSONDecodeError, ValidationError) as exc:
        print(f"error: invalid QGVerdict JSON — {exc}", file=sys.stderr)
        return None


def _refuse(reasons: list[str]) -> int:
    for reason in reasons:
        print(f"refused: {reason}", file=sys.stderr)
    print(
        "error: aggregate refused — nothing recorded (anti-self-"
        "approval guard, PR-B3)",
        file=sys.stderr,
    )
    return 1


def _drive_redo(verdict: QGVerdict, session_id: str) -> str:
    from core.governance import redo_counter

    if verdict.verdict == "REJECTED":
        return redo_counter.record_rejected(session_id).to_message()
    redo_counter.reset(session_id)
    return ""


def _record_aggregate(verdict: QGVerdict, args: argparse.Namespace) -> int:
    from core.governance.aggregate_guard import check_aggregate, write_aggregate

    if not args.session_id:
        print(
            "error: --kind qg records an AGGREGATE and requires "
            "--session-id (the guard reads that session's reviewer ledger)",
            file=sys.stderr,
        )
        return 1
    dumped = verdict.model_dump()
    result = check_aggregate(dumped, args.session_id)
    if not result.ok:
        return _refuse(result.reasons)
    aggregate_path = write_aggregate(args.session_id, dumped, result)
    if aggregate_path is None:
        # An accepted-but-unwritten aggregate recorded anyway would be
        # the incident shape again, one filesystem error away.
        return _refuse([
            "AGGREGATE.json could not be written and verified on disk "
            "— a label without its artifact is the incident shape"
        ])
    _record_label(verdict, args)
    print(json.dumps(_accepted_payload(verdict, args, aggregate_path, result)))
    return 0


def _accepted_payload(
    verdict: QGVerdict,
    args: argparse.Namespace,
    aggregate_path: Path,
    result: GuardResult,
) -> dict:
    return {
        "recorded": True,
        "verdict": verdict.verdict,
        "eval_task_id": args.eval_task_id,
        "aggregate": str(aggregate_path),
        "reviewers": result.reviewers,
        "warnings": result.warnings,
        "redo": _drive_redo(verdict, args.session_id),
    }


def _record_reviewer(verdict: QGVerdict, args: argparse.Namespace) -> int:
    from core.governance.reviewer_ledger import AGGREGATOR_IDS

    if verdict.reviewer in AGGREGATOR_IDS:
        print(
            f"error: {verdict.reviewer!r} is an aggregator identity — "
            "an aggregator's verdict is recorded via --kind qg, which "
            "is guarded; recording it as a 'reviewer' label would repeat "
            "the 2026-07-20 incident under a different flag",
            file=sys.stderr,
        )
        return 1
    _record_label(verdict, args)
    print(json.dumps({
        "recorded": True,
        "verdict": verdict.verdict,
        "reviewer": verdict.reviewer,
        "ledger_match": _ledger_match(verdict, args.session_id),
    }))
    return 0


def _ledger_match(verdict: QGVerdict, session_id: str) -> str:
    """Name of the hook-captured record carrying this exact verdict."""
    if not session_id:
        return ""
    try:
        from core.governance.aggregate_guard import _session_records
        from core.governance.qg_digest import verdict_digest

        target = verdict_digest(verdict.model_dump())
        for name, record in _session_records(session_id):
            their = record.get("verdict")
            if not isinstance(their, dict):
                continue
            try:  # digest the NORMALIZED dump — raw dicts differ on defaults
                normalized = QGVerdict.model_validate(their).model_dump()
            except ValidationError:
                continue
            if verdict_digest(normalized) == target:
                return name
    except Exception:  # cross-reference is provenance, never a blocker
        return ""
    return ""


def _record_label(verdict: QGVerdict, args: argparse.Namespace) -> None:
    record_verdict_label(
        verdict,
        deliverable=args.deliverable,
        department=args.department,
        eval_task_id=args.eval_task_id,
        session_id=args.session_id,
        kind=args.kind,
        round_label=args.round_label,
        head=args.head,
    )


def _record_judge(raw: str, args: argparse.Namespace) -> int:
    try:
        verdict = JudgeVerdict.model_validate(json.loads(raw))
    except (json.JSONDecodeError, ValidationError) as exc:
        print(f"error: invalid JudgeVerdict JSON — {exc}", file=sys.stderr)
        return 1
    record_judge_label(
        verdict,
        deliverable=args.deliverable,
        department=args.department,
        session_id=args.session_id,
    )
    print(json.dumps({
        "recorded": True,
        "verdict": verdict.verdict,
        "gate": verdict.gate,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
