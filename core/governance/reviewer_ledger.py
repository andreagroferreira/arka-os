"""Reviewer verdict ledger — the direct channel from QG reviewers to disk.

Before this module, a reviewer's QGVerdict existed only as subagent final
text inside the aggregator's context: of 81 corpus records, 80 were
authored by the aggregator and none by a reviewer (the remaining record
is a hand-written verdict-invalidation, not a verdict).
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
(In the field every record has come from SubagentStop — the PostToolUse
writer only sees synchronous dispatches — so treat that as collision
safety, not as a delivered two-source cross-check.)

ATTRIBUTION IS FAIL-CLOSED. A record here is signed evidence carrying a
reviewer's name, so it is written only from a subagent-scoped source.
Two writers qualify, and ``CAPTURE_SOURCES`` is enforced here rather
than trusted to either of them:

- ``subagent-stop`` — the SubagentStop payload's
  ``last_assistant_message`` or ``agent_transcript_path``, gated by
  ``core.hooks.subagent_stop._attributable`` on where the text actually
  came from (never the parent transcript);
- ``post-tool-use`` — ``tool_response.content`` of a SYNCHRONOUS Task
  dispatch, which is the subagent's own returned text. Async dispatches
  carry no output at that point and are skipped.

Missing a verdict is recoverable; a hashed record of words the reviewer
never wrote is not — that failure produced three identical-hash
artifacts under three reviewer names before this rule existed.

Sanitization boundary, on purpose: the ledger is a LOCAL-ONLY surface
(files 0600, session directories 0700, never shipped, no reader outside
this module). When the redaction config is missing the raw text is stored
with ``sanitized: false`` instead of being erased — erasing the
reviewer's words is the relay failure this module exists to end. The
fail-closed contract of ``core.evals.sanitizer`` is unchanged for the
writers that honour it (``core.knowledge.recipes``); anything that later
promotes these artifacts into a shared corpus must redact at that edge.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

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

# The only provenances that may produce a signed record. Both are
# subagent-scoped by construction: PostToolUse reads the Task result,
# SubagentStop reads the subagent's own final message.
CAPTURE_SOURCES = frozenset({"post-tool-use", "subagent-stop"})

_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
# "." and ".." match the character class above: "." would scatter
# records across the ledger root, ".." onto ~/.arkaos itself.
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
    """Publish the record atomically: complete body, then the name.

    The filename carries the digest, so two DIFFERENT texts never
    collide even at the same seq — a collision therefore means another
    writer captured this exact text first, and the answer is to adopt
    its file, not to bump the seq (bumping filed the same verdict twice).

    Body first, name second, via a temp file and ``os.link``. Creating
    the final name with O_EXCL and writing afterwards published an empty
    file the instant the name existed: a hook killed on its timeout
    budget in that window left a 0-byte record that shadowed the real
    verdict forever, and the operator was told the reviewer had filed
    none. A name in this directory now always implies complete content.
    """
    digest8 = record["raw_sha256"][:8]
    path = session_dir / f"{record['reviewer_id']}-{record['seq']}-{digest8}.json"
    tmp = _write_temp(session_dir, path.name, record)
    if tmp is None:
        return None
    try:
        os.link(tmp, path)
    except FileExistsError:
        pass  # same reviewer, seq and text: another writer got there first
    except OSError:
        return None
    finally:
        with contextlib.suppress(OSError):
            tmp.unlink(missing_ok=True)
    return path


def _write_temp(session_dir: Path, name: str, record: dict) -> Path | None:
    """The complete body under a private name, fsynced."""
    # pid AND a random suffix: two threads of one process share the pid,
    # so a pid-only name had them clobber each other's temp file and both
    # writers returned empty-handed.
    tmp = session_dir / f".{name}.tmp-{os.getpid()}-{uuid4().hex[:8]}"
    try:
        fd = os.open(tmp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, indent=2))
            fh.flush()
            os.fsync(fh.fileno())
    except OSError:
        with contextlib.suppress(OSError):
            tmp.unlink(missing_ok=True)
        return None
    return tmp


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
        # The fail-closed attribution rule is enforced HERE, not only in
        # the hook that calls this: a record carries a reviewer's name,
        # so an unknown provenance must never produce one.
        if source not in CAPTURE_SOURCES:
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
    """Prior capture of this exact text, matched on the FILENAME digest.

    Reading the body to compare hashes raced the writer: a file created
    with O_EXCL is visible before its content is flushed, so a
    concurrent capture parsed nothing, believed the text was new, and
    filed a duplicate under the next seq. The digest is in the name, so
    the check needs no content at all.
    """
    suffix = f"-{digest[:8]}.json"
    for path in paths:
        if not path.name.endswith(suffix):
            continue
        try:
            prior = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            # Unreadable despite the atomic publish (truncated on disk,
            # or written by an older build). Treat it as absent so the
            # verdict is captured again rather than lost behind a name.
            continue
        prior["path"] = str(path)
        return prior
    return None


def _expired(session_dir: Path, cutoff: datetime) -> bool:
    try:
        mtime = datetime.fromtimestamp(session_dir.stat().st_mtime, tz=UTC)
    except OSError:
        return False
    return mtime < cutoff


def _purge(session_dir: Path) -> bool:
    """Remove a session's records. Only own files; never recursive.

    The glob covers ``NOTICES.jsonl`` too: matching ``*.json`` alone
    deleted every verdict, then failed the rmdir on the leftover notices
    file and reported zero removed — destruction with a clean receipt.
    """
    try:
        for item in session_dir.iterdir():
            if item.is_symlink() or item.is_dir():
                return False  # foreign content: leave the whole dir alone
        for item in session_dir.iterdir():
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


def _notice_path(session_id: str) -> Path | None:
    session_dir = ledger_root() / session_id
    return session_dir / "NOTICES.jsonl" if _safe_id(session_id) else None


def _notice_entry(record: dict | None, nudge: str) -> dict | None:
    entry: dict = {"ts": datetime.now(UTC).isoformat()}
    if record is not None:
        verdict = record.get("verdict") or {}
        entry.update({
            "kind": "reviewer-verdict",
            "reviewer_id": record.get("reviewer_id"),
            "verdict": verdict.get("verdict"),
            # Only claims the reviewer stands behind: a REFUTED entry is
            # one they considered and dismissed, so counting it would
            # inflate the headline the orchestrator reads.
            "blockers": sum(
                1 for blocker in (verdict.get("blockers") or [])
                if (blocker or {}).get("verdict") != "REFUTED"
            ),
            "parse_error": record.get("parse_error"),
            "artifact": record.get("path"),
        })
        return entry
    if nudge:
        entry.update({"kind": "subagent-qa", "message": nudge})
        return entry
    return None


def queue_notice(session_id: str, record: dict | None, nudge: str) -> None:
    """Queue a subagent notice for the ORCHESTRATOR's next turn end.

    SubagentStop cannot tell the orchestrator anything: its
    additionalContext is "delivered to the subagent" (2.1.220), so
    emitting there wakes the agent that just stopped. The Stop hook's
    context IS delivered to the model, so notices are parked here and
    drained at the orchestrator's own turn end.
    """
    try:
        path = _notice_path(session_id)
        if path is None:
            return
        entry = _notice_entry(record, nudge)
        if entry is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        # mkdir honours the umask (0o755 in practice); the session dir
        # holds verdict records, so it is tightened here as well as in
        # _session_dir — whichever writer creates it first.
        os.chmod(path.parent, 0o700)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        os.chmod(path, 0o600)
    except Exception:
        return


def read_notices(session_id: str) -> list[dict]:
    """Queued notices for a session, WITHOUT clearing them ([] when none)."""
    try:
        path = _notice_path(session_id)
        if path is None or not path.is_file():
            return []
        entries = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # a torn append must not swallow the rest
        return entries
    except Exception:
        return []


def clear_notices(session_id: str) -> None:
    """Drop the queue — call only AFTER the notices have been delivered.

    Split from the read so a failed delivery cannot lose a verdict: the
    queue used to be unlinked before the caller emitted, and the emit
    sits outside that call's try/except.
    """
    try:
        path = _notice_path(session_id)
        if path is not None:
            path.unlink(missing_ok=True)
    except Exception:
        return


def notices_context(session_id: str) -> str:
    """The orchestrator-facing block for the Stop hook ("" when empty).

    Does NOT clear the queue — the caller clears it once the context has
    actually been emitted (see ``clear_notices``).
    """
    lines = []
    for entry in read_notices(session_id):
        if entry.get("kind") == "reviewer-verdict":
            verdict = entry.get("verdict")
            if verdict:
                head = (
                    f"{entry.get('reviewer_id')} {verdict}"
                    f" blockers={entry.get('blockers', 0)}"
                )
            else:
                # A reviewer who filed no parsable verdict is exactly who
                # this line exists to surface — printing a Python None
                # here tells the operator nothing.
                reason = entry.get("parse_error") or "no verdict block in the reply"
                head = f"{entry.get('reviewer_id')} verdict-unparsed ({reason})"
            lines.append(
                f"[arka:qg:reviewer-verdict] {head}"
                f" artifact={entry.get('artifact')} — read the artifact and"
                f" quote the verdict verbatim to the operator; do not"
                f" summarise or paraphrase it."
            )
        elif entry.get("message"):
            lines.append(entry["message"])
    return "\n".join(lines)
