"""Mechanical carry advisor for QG redo rounds (Gate Economy PR-3).

A redo round used to re-dispatch every reviewer because the digest
chain invalidates their artifacts the moment the evidence report
changes. ``QGDigestCarry`` exists precisely to carry a still-valid
review across that mismatch — but composing one by hand needs the
reviewer's digest from the ledger plus a substantive reason, so in
practice nobody did (0 uses across 234 recorded verdicts, while the
QG triad burned ~950 dispatches in 108 sessions). This module derives
the eligible carries MECHANICALLY from the session ledger and the
delta since the reviewer's round.

Domains are deliberately coarse and every edge fails closed to
re-dispatch:

  - Eduardo (copy) carries only over a PURE-CODE delta.
  - Francisca (tech) carries only over a PURE-PROSE delta.
  - Mixed, empty, or unknown-suffix deltas carry nobody.
  - Only APPROVED artifacts carry — a REJECTED review is never
    carried: either the fix touched the domain (re-dispatch) or the
    round was not ready for the gate at all.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import PurePosixPath
from typing import Any

from core.governance.aggregate_guard import (
    _counted,
    _identity,
    _latest_per_reviewer,
    _session_records,
)

CODE_SUFFIXES = frozenset({
    ".py", ".js", ".ts", ".tsx", ".jsx", ".vue", ".php", ".rb", ".go",
    ".rs", ".sql", ".sh", ".css", ".scss",
})
PROSE_SUFFIXES = frozenset({".md", ".mdx", ".txt"})

# Canonical identity fragment → the ONE delta kind that reviewer's
# review survives. Anything not listed always re-dispatches.
_SURVIVES: dict[str, str] = {
    "eduardo": "code",
    "francisca": "prose",
}


def delta_kind(delta_files: list[str]) -> str:
    """``"code"`` | ``"prose"`` | ``"mixed"`` for a delta file list.

    An empty list or any unknown suffix is ``"mixed"`` — the advisor
    must fail closed when it cannot prove what the delta touches.
    """
    if not delta_files:
        return "mixed"
    kinds: set[str] = set()
    for name in delta_files:
        suffix = PurePosixPath(name.strip()).suffix.lower()
        if suffix in CODE_SUFFIXES:
            kinds.add("code")
        elif suffix in PROSE_SUFFIXES:
            kinds.add("prose")
        else:
            return "mixed"
    return kinds.pop() if len(kinds) == 1 else "mixed"


def _survives(reviewer_id: str, kind: str) -> bool:
    identity = _identity(str(reviewer_id or ""))
    for fragment, survived in _SURVIVES.items():
        if fragment in identity:
            return kind == survived
    return False


def _artifact_digest(record: dict[str, Any]) -> str:
    verdict = record.get("verdict")
    if not isinstance(verdict, dict):
        return ""
    return str(verdict.get("evidence_digest") or "")


def carry_candidates(
    session_id: str, delta_files: list[str]
) -> dict[str, Any]:
    """Eligible digest carries for a redo round, from the ledger.

    Returns ``{"session_id", "delta_kind", "carries", "re_dispatch"}``
    where ``carries`` entries are ready to paste verbatim into the
    aggregate's ``digest_carries`` and ``re_dispatch`` names every
    reviewer identity that must re-run, each with its reason.
    """
    kind = delta_kind(delta_files)
    carries: list[dict[str, str]] = []
    re_dispatch: list[dict[str, str]] = []
    counted = [
        (name, rec)
        for name, rec in _session_records(session_id)
        if _counted(rec)
    ]
    for _, record in _latest_per_reviewer(counted):
        reviewer_id = str(record.get("reviewer_id") or "")
        verdict = record.get("verdict") or {}
        digest = _artifact_digest(record)
        blocked = _carry_block_reason(verdict, digest, reviewer_id, kind)
        if blocked:
            re_dispatch.append({"reviewer": reviewer_id, "why": blocked})
            continue
        carries.append({
            "reviewer": reviewer_id,
            "evidence_digest": digest,
            "reason": (
                f"delta since digest {digest[:12]} is {kind}-only "
                f"({len(delta_files)} file(s)); this reviewer's domain "
                "is untouched — mechanical carry (Gate Economy PR-3)"
            ),
        })
    return {
        "session_id": session_id,
        "delta_kind": kind,
        "carries": carries,
        "re_dispatch": re_dispatch,
    }


def _carry_block_reason(
    verdict: dict[str, Any], digest: str, reviewer_id: str, kind: str
) -> str:
    """Why this artifact cannot carry — empty string when it can."""
    if str(verdict.get("verdict") or "").upper() != "APPROVED":
        return "last artifact is not APPROVED — a rejection never carries"
    if not digest:
        return "artifact has no evidence_digest — nothing to carry"
    if kind == "mixed":
        return "delta is mixed/unknown — every domain may be touched"
    if not _survives(reviewer_id, kind):
        return f"the {kind} delta touches this reviewer's domain"
    return ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m core.governance.carry_advisor",
        description=(
            "Derive mechanical QG digest carries for a redo round."
        ),
    )
    parser.add_argument("session_id")
    parser.add_argument(
        "--delta-files",
        default="",
        help="comma-separated files changed since the last round",
    )
    args = parser.parse_args(argv)
    delta = [f for f in (args.delta_files or "").split(",") if f.strip()]
    print(json.dumps(carry_candidates(args.session_id, delta), indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
