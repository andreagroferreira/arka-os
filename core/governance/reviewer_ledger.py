"""Reviewer verdict ledger — the direct channel from QG reviewers to disk.

Before this module, a reviewer's QGVerdict existed only as subagent final
text inside the aggregator's context: of 81 corpus records, 80 were
authored by the aggregator, one was malformed, and none by a reviewer.
This ledger captures each reviewer dispatch at the HOOK boundary — a
surface the reviewer cannot fail to use and the aggregator cannot
distort — so the operator can read each verdict verbatim, with a digest
that makes any tampering evident:

    ~/.arkaos/quality-gate/<session_id>/<reviewer_id>-<seq>-<sha8>.json

Each record carries the reviewer's COMPLETE returned text (untruncated),
its sha256, the parsed QGVerdict when a fenced block is present (parse
failures are recorded, never silent), and the capture source. The digest
is part of the filename, so two captures that disagree can never
overwrite each other: divergent text always lands as a second record.

ATTRIBUTION IS FAIL-CLOSED. A record here is signed evidence carrying a
reviewer's name, so it is written only from a source that provably
belongs to that reviewer (the SubagentStop payload's
``last_assistant_message`` / ``agent_transcript_path``). Missing a
verdict is recoverable; a hashed record of words the reviewer never
wrote is not — that failure produced three identical-hash artifacts
under three reviewer names before this rule existed.

Sanitization boundary, on purpose: the ledger is a LOCAL-ONLY surface
(files 0600, directory 0700, never shipped, no reader outside this
module). When the redaction config is missing the raw text is stored
with ``sanitized: false`` instead of being erased — erasing the
reviewer's words is the relay failure this module exists to end. The
fail-closed contract of ``core.evals.sanitizer`` is unchanged for the
writers that honour it (``core.knowledge.recipes``); anything that later
promotes these artifacts into a shared corpus must redact at that edge.
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
# "." and ".." match the character class above and would resolve the
# ledger onto ~/.arkaos itself.
_DOT_IDS = frozenset({".", ".."})
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


def _validated(data: dict) -> tuple[dict, str | None]:
    """Validate against QGVerdict; keep the raw dict on any failure."""
    try:
        from core.governance.qg_verdict import QGVerdict
    except Exception as exc:  # pydantic absent on a stripped install
        return data, f"validator-unavailable: {exc}"
    try:
        return QGVerdict.model_validate(data).model_dump(), None
    except Exception as exc:
        return data, f"schema: {exc}"


def _qualifying_fences(bodies: list[str]) -> tuple[list[dict], str | None]:
    """Fence bodies that parse to a dict carrying a ``verdict`` key."""
    qualifying: list[dict] = []
    parse_error: str | None = None
    for body in bodies:
        try:
            data = json.loads(body)
        except json.JSONDecodeError as exc:
            parse_error = f"json: {exc}"
            continue
        if not isinstance(data, dict) or "verdict" not in data:
            parse_error = "fence parsed but carries no 'verdict' key"
            continue
        qualifying.append(data)
    return qualifying, parse_error


def _extract_verdict(raw_output: str) -> tuple[dict | None, str | None]:
    """Parse the verdict block. Returns (verdict, parse_error).

    The LAST qualifying fence wins: reviewers state their verdict at the
    end of a reply and routinely quote the schema, a template, or a
    prior round's verdict earlier on. Taking the first fence filed a
    REJECTED review as APPROVED with no error recorded.
    """
    candidates = (
        _VERDICT_FENCE_RE.findall(raw_output)
        or _JSON_FENCE_RE.findall(raw_output)
    )
    qualifying, parse_error = _qualifying_fences(candidates)
    if not qualifying:
        if not candidates:
            return None, None  # no fence at all — raw text is the record
        return None, parse_error

    verdict, error = _validated(qualifying[-1])
    if len(qualifying) > 1:
        ambiguity = f"ambiguous: {len(qualifying)} verdict fences (last used)"
        error = f"{ambiguity}; {error}" if error else ambiguity
    return verdict, error


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


def _safe_id(value: str) -> bool:
    return bool(value) and value not in _DOT_IDS and bool(_SAFE_ID_RE.match(value))


def _session_dir(session_id: str) -> Path | None:
    if not _safe_id(session_id):
        return None
    path = ledger_root() / session_id
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(path, 0o700)
    return path


def _records_for(session_dir: Path, reviewer_id: str) -> list[Path]:
    """Existing records for one reviewer, anchored so ``copy-director``
    never matches ``copy-director-eduardo``'s files."""
    prefix = f"{reviewer_id}-"
    return sorted(
        path for path in session_dir.glob(f"{prefix}*.json")
        if path.name[len(prefix):].split("-", 1)[0].isdigit()
    )


def _write_record(session_dir: Path, record: dict) -> Path | None:
    """Create the record exclusively; retry the seq on collision."""
    digest8 = record["raw_sha256"][:8]
    for attempt in range(20):
        seq = record["seq"] + attempt
        path = session_dir / f"{record['reviewer_id']}-{seq}-{digest8}.json"
        if path.exists():
            return path  # same text, same seq — already captured
        record["seq"] = seq
        body = json.dumps(record, ensure_ascii=False, indent=2)
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            continue
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(body)
        except OSError:
            return None
        return path
    return None


def _build_record(
    session_id: str,
    reviewer_id: str,
    raw_output: str,
    source: str,
    digest: str,
    seq: int,
) -> dict:
    verdict, parse_error = _extract_verdict(raw_output)
    stored, sanitized = _sanitize(raw_output)
    return {
        "ts": datetime.now(UTC).isoformat(),
        "session_id": session_id,
        "reviewer_id": reviewer_id,
        "seq": seq,
        "raw_output": stored,
        "raw_sha256": digest,
        "verdict": verdict,
        "parse_error": parse_error,
        "evidence_digest": (verdict or {}).get("evidence_digest"),
        "tree_digest": (verdict or {}).get("tree_digest"),
        "source": source,
        "sanitized": sanitized,
    }


def record_reviewer_output(
    session_id: str,
    reviewer_id: str,
    raw_output: str,
    source: str,
) -> dict | None:
    """Persist one reviewer dispatch verbatim. Returns the record or None.

    Never raises. Deduplicates on raw_sha256 so the two writers do not
    double-record the same output.
    """
    try:
        if not raw_output or not is_reviewer(reviewer_id):
            return None
        if not _safe_id(reviewer_id):
            return None
        session_dir = _session_dir(session_id)
        if session_dir is None:
            return None
        return _capture(session_dir, session_id, reviewer_id, raw_output, source)
    except Exception:
        return None


def _capture(
    session_dir: Path,
    session_id: str,
    reviewer_id: str,
    raw_output: str,
    source: str,
) -> dict | None:
    digest = hashlib.sha256(raw_output.encode("utf-8")).hexdigest()
    existing = _records_for(session_dir, reviewer_id)
    prior = _find_by_digest(existing, digest)
    if prior is not None:
        return prior  # already captured (other source, same text)

    record = _build_record(
        session_id, reviewer_id, raw_output, source, digest, len(existing) + 1
    )
    path = _write_record(session_dir, record)
    if path is None:
        return None
    record["path"] = str(path)
    return record


def _find_by_digest(paths: list[Path], digest: str) -> dict | None:
    for path in paths:
        try:
            prior = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if prior.get("raw_sha256") == digest:
            prior["path"] = str(path)
            return prior
    return None


def latest_verdicts(session_id: str) -> dict[str, dict]:
    """Highest-seq record per reviewer for a session ({} on any failure).

    Ordered by the ``seq`` field, not by filename: lexical order puts
    ``-10`` before ``-2``, so a redo loop past nine rounds would return
    a stale verdict.
    """
    try:
        if not _safe_id(session_id):
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
            if not reviewer:
                continue
            record["path"] = str(path)
            current = result.get(reviewer)
            if current is None or record.get("seq", 0) >= current.get("seq", 0):
                result[reviewer] = record
        return result
    except Exception:
        return {}


def _expired(session_dir: Path, cutoff: datetime) -> bool:
    try:
        mtime = datetime.fromtimestamp(session_dir.stat().st_mtime, tz=UTC)
    except OSError:
        return False
    return mtime < cutoff


def _purge(session_dir: Path) -> bool:
    """Remove a session's records. Only ``*.json``; never recursive."""
    try:
        for item in session_dir.glob("*.json"):
            if not item.is_symlink():
                item.unlink()
        session_dir.rmdir()
        return True
    except OSError:
        return False


def sweep_expired(days: int = 90) -> int:
    """Remove session dirs older than ``days``. Returns dirs removed."""
    removed = 0
    try:
        root = ledger_root()
        if not root.is_dir():
            return 0
        cutoff = datetime.now(UTC) - timedelta(days=days)
        for session_dir in root.iterdir():
            # Never follow a symlink: this function deletes, and a linked
            # session dir would take its target's contents with it.
            if session_dir.is_symlink() or not session_dir.is_dir():
                continue
            if not _expired(session_dir, cutoff):
                continue
            if _purge(session_dir):
                removed += 1
    except Exception:
        return removed
    return removed
