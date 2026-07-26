"""Reviewer verdict ledger — the direct channel from QG reviewers to disk.

Before this module, a reviewer's QGVerdict existed only as subagent final
text inside the aggregator's context: 81 corpus records, 80 authored by
the aggregator, zero by a reviewer. This ledger captures every reviewer
dispatch at the HOOK boundary — a surface the reviewer cannot fail to
use and the aggregator cannot distort — so the operator can read each
verdict verbatim and tamper-evident:

    ~/.arkaos/quality-gate/<session_id>/<reviewer_id>-<seq>.json

Each record carries the reviewer's COMPLETE returned text (untruncated),
its sha256, the parsed QGVerdict when a fenced block is present (parse
failures are recorded, never silent), and the capture source. PostToolUse
is the primary writer (tool_output is the literal returned string);
SubagentStop is the independent cross-check — a divergence between the
two sources for the same dispatch is itself a tamper signal.

Sanitisation boundary, on purpose: the ledger is a LOCAL-ONLY surface
(files 0600, directory 0700, never shipped, never a training corpus).
When the redaction config is missing the raw text is stored with
``sanitized: false`` instead of being erased — erasing the reviewer's
words is the relay failure this module exists to end. The eval corpus
writer (``core.evals.verdict_labels``) keeps its fail-closed contract.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Reviewer identities: constitution ids (config/constitution.yaml,
# quality_gate.agents), deployed agent-file names, and the legacy persona
# names still present in older projects. The aggregator ids are captured
# too — the aggregate belongs on the same audit surface.
REVIEWER_IDS = frozenset({
    "copy-director-eduardo",
    "tech-director-francisca",
    "eduardo-copy",
    "francisca-tech",
    "copy-director",
    "tech-ux-director",
})
AGGREGATOR_IDS = frozenset({"cqo-marta", "marta-cqo", "cqo"})
LEDGER_IDS = REVIEWER_IDS | AGGREGATOR_IDS

_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
# Primary contract: a fenced ```arka-qgverdict block. Compatibility: a
# plain ```json fence whose body parses and carries a "verdict" key —
# the shape the deployed reviewer agents emit today.
_VERDICT_FENCE_RE = re.compile(
    r"```arka-qgverdict\s*\n(.*?)```", re.DOTALL
)
_JSON_FENCE_RE = re.compile(r"```json\s*\n(.*?)```", re.DOTALL)


def ledger_root() -> Path:
    """Resolved at call time so tests can repoint HOME."""
    return Path.home() / ".arkaos" / "quality-gate"


def is_reviewer(agent_id: str) -> bool:
    """True when the agent id belongs to the QG review surface."""
    return agent_id in LEDGER_IDS


def _extract_verdict(raw_output: str) -> tuple[dict | None, str | None]:
    """Parse the verdict block. Returns (verdict, parse_error)."""
    match = _VERDICT_FENCE_RE.search(raw_output)
    candidates = [match.group(1)] if match else [
        body.group(1)
        for body in _JSON_FENCE_RE.finditer(raw_output)
    ]
    parse_error: str | None = None
    for body in candidates:
        try:
            data = json.loads(body)
        except json.JSONDecodeError as exc:
            parse_error = f"json: {exc}"
            continue
        if not isinstance(data, dict) or "verdict" not in data:
            parse_error = "fence parsed but carries no 'verdict' key"
            continue
        try:
            from core.governance.qg_verdict import QGVerdict

            return QGVerdict.model_validate(data).model_dump(), None
        except Exception as exc:  # pydantic missing or schema mismatch
            # The block names a verdict but fails the schema — record the
            # raw dict AND the error so nothing disappears silently.
            return data, f"schema: {exc}"
    if not candidates:
        return None, None  # no fence at all — raw text is still the record
    return None, parse_error


def _sanitize(raw_output: str) -> tuple[str, bool]:
    try:
        from core.evals.sanitizer import SanitizerConfigMissing, sanitize_text

        try:
            clean, _counts = sanitize_text(raw_output)
            return clean, True
        except SanitizerConfigMissing:
            return raw_output, False
    except Exception:
        return raw_output, False


def _session_dir(session_id: str) -> Path | None:
    if not session_id or not _SAFE_ID_RE.match(session_id):
        return None
    path = ledger_root() / session_id
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(path, 0o700)
    return path


def record_reviewer_output(
    session_id: str,
    reviewer_id: str,
    raw_output: str,
    source: str,
) -> dict | None:
    """Persist one reviewer dispatch verbatim. Returns the record or None.

    Never raises — this runs inside hooks that promise not to break.
    Deduplicates on raw_sha256 so the PostToolUse and SubagentStop
    writers do not double-record the same output.
    """
    try:
        if not raw_output or not is_reviewer(reviewer_id):
            return None
        if not _SAFE_ID_RE.match(reviewer_id):
            return None
        session_dir = _session_dir(session_id)
        if session_dir is None:
            return None

        digest = hashlib.sha256(raw_output.encode("utf-8")).hexdigest()
        existing = sorted(session_dir.glob(f"{reviewer_id}-*.json"))
        for path in existing:
            try:
                prior = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if prior.get("raw_sha256") == digest:
                prior["path"] = str(path)
                return prior  # already captured (other source, same text)

        verdict, parse_error = _extract_verdict(raw_output)
        stored, sanitized = _sanitize(raw_output)
        record = {
            "ts": datetime.now(UTC).isoformat(),
            "session_id": session_id,
            "reviewer_id": reviewer_id,
            "seq": len(existing) + 1,
            "raw_output": stored,
            "raw_sha256": digest,
            "verdict": verdict,
            "parse_error": parse_error,
            "evidence_digest": (verdict or {}).get("evidence_digest"),
            "tree_digest": (verdict or {}).get("tree_digest"),
            "source": source,
            "sanitized": sanitized,
        }
        path = session_dir / f"{reviewer_id}-{record['seq']}.json"
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
        record["path"] = str(path)
        return record
    except Exception:
        return None


def latest_verdicts(session_id: str) -> dict[str, dict]:
    """Most recent record per reviewer for a session ({} on any failure)."""
    try:
        if not session_id or not _SAFE_ID_RE.match(session_id):
            return {}
        session_dir = ledger_root() / session_id
        if not session_dir.is_dir():
            return {}
        result: dict[str, dict] = {}
        for path in sorted(session_dir.glob("*.json")):
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            reviewer = record.get("reviewer_id")
            if reviewer:
                record["path"] = str(path)
                result[reviewer] = record
        return result
    except Exception:
        return {}


def sweep_expired(days: int = 90) -> int:
    """Remove session dirs older than ``days``. Returns dirs removed."""
    removed = 0
    try:
        root = ledger_root()
        if not root.is_dir():
            return 0
        cutoff = datetime.now(UTC) - timedelta(days=days)
        for session_dir in root.iterdir():
            if not session_dir.is_dir():
                continue
            try:
                mtime = datetime.fromtimestamp(
                    session_dir.stat().st_mtime, tz=UTC
                )
                if mtime >= cutoff:
                    continue
                for item in session_dir.iterdir():
                    item.unlink()
                session_dir.rmdir()
                removed += 1
            except OSError:
                continue
    except Exception:
        return removed
    return removed
