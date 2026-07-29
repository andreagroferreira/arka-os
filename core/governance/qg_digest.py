"""Integrity digests for the Quality Gate chain (PR-B2).

Two digest primitives supply the material for proving — once PR-B3
wires the verification that consumes them — that reviewers and
verdict refer to the same evidence report:

- ``evidence_digest`` — hashes an EvidenceReport dict.
- ``verdict_digest``  — hashes a QGVerdict dict.

Both return a 64-char lowercase sha256 hex string over canonical JSON
(sorted keys, compact separators): key order and formatting never
change a digest; a content change does — except under the
``report_digest`` key, which ``evidence_digest`` excludes by design so
the digest is stable whether computed before or after embedding.

A working-tree digest deliberately does NOT live here. Three designs
of a ``tree_digest`` were driven through six wrong-digest routes
over ten QG rounds, each reproduced at the gate before acceptance;
``docs/adr/2026-07-29-tree-digest-corpus.md`` records the corpus
durably and is the acceptance spec for the dedicated PR.
``QGVerdict.tree_digest`` is enforced empty until that primitive
exists and survives its own gate.
"""

from __future__ import annotations

import hashlib
import json


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(payload: dict) -> bytes:
    """Canonical JSON: sorted keys, compact separators, UTF-8-encoded
    (surrogatepass, so surrogate-bearing strings serialize rather than
    raise).

    Key order and formatting never change the digest; content does.
    ``allow_nan=False``: NaN/Infinity are invalid JSON and would make
    the canonical form implementation-defined — they raise instead.
    Other non-serializable values raise too, on purpose — a digest
    over a lossy repr would silently stop meaning anything.
    """
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8", "surrogatepass")


def evidence_digest(report: dict) -> str:
    """Digest of an EvidenceReport dict, canonically normalized.

    The report's own ``report_digest`` key (if present) is excluded so
    the digest is stable whether computed before or after embedding.
    """
    payload = {k: v for k, v in report.items() if k != "report_digest"}
    return _sha256(_canonical(payload))


def verdict_digest(verdict: dict) -> str:
    """Digest of a QGVerdict dict, canonically normalized."""
    return _sha256(_canonical(verdict))
