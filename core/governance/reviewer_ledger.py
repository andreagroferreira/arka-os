"""Reviewer verdict ledger — the direct channel from QG reviewers to disk.

Before this module, a reviewer's QGVerdict existed only as subagent final
text inside the aggregator's context: of 81 corpus records, 80 were
authored by the aggregator and none by a reviewer (the remaining record
is a hand-written verdict-invalidation, not a verdict).
This ledger captures each reviewer dispatch at the HOOK boundary — a
surface the reviewer cannot fail to use and the aggregator cannot
distort — so the operator can read each verdict as the reviewer wrote
it, with digests that make any tampering evident:

    ~/.arkaos/quality-gate/<session_id>/<reviewer_id>-<seq>-<sha8>.json

Each record carries the reviewer's returned text UNTRUNCATED, the parsed
QGVerdict when a fenced block is present (parse failures are recorded,
never silent), the capture source, and two digests: ``stored_sha256``
over the ``raw_output`` field as stored, which is what the operator
verifies, and ``raw_sha256`` over the text as returned, which is the
dedup key. ``sanitized`` reports whether redaction RAN, not whether it
changed anything: the two digests differ only when it rewrote the text,
so a record with ``sanitized: true`` and equal digests was inspected and
left alone. The dedup digest is part of the filename, so two
captures that disagree can never overwrite each other: divergent text
always lands as a second record.
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

# One identity per person: a verdict's ``reviewer`` field and the id the
# dispatch carried are different spellings of the same reviewer. Used to
# tell a reviewer's OWN verdict from one they quoted.
IDENTITY_ALIASES: tuple[frozenset[str], ...] = (
    frozenset({"copy-director-eduardo", "eduardo-copy", "copy-director"}),
    frozenset({"tech-director-francisca", "francisca-tech", "tech-ux-director"}),
    AGGREGATOR_IDS,
)

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

# The only names this module writes into a session directory. Retention
# checks every entry against these before deleting anything.
_NOTICES_NAME = "NOTICES.jsonl"
_RECORD_NAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}-\d+-[0-9a-f]{8}\.json$")


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


def _same_identity(claimed: object, dispatched: str) -> bool:
    """True when a verdict's ``reviewer`` field names the dispatched agent."""
    if not isinstance(claimed, str) or not claimed:
        return True  # unclaimed: no evidence it belongs to someone else
    if claimed == dispatched:
        return True
    return any(
        claimed in group and dispatched in group for group in IDENTITY_ALIASES
    )


def _extract_verdict(
    raw_output: str, reviewer_id: str = ""
) -> tuple[dict | None, str | None]:
    """Parse the verdict block. Returns (verdict, parse_error).

    Two rules, both learned from misfiled verdicts. The LAST qualifying
    fence wins, because reviewers state their verdict at the end and
    quote the schema or a prior round earlier on (taking the first filed
    a REJECTED review as APPROVED). And a fence whose ``reviewer`` field
    names SOMEONE ELSE is a quotation, not this agent's verdict: the
    aggregator must reproduce each reviewer verbatim, so its own record
    took the last quoted reviewer as its own — filing a 7-blocker
    verdict under an agent whose own list held 12.
    """
    candidates = (
        _VERDICT_FENCE_RE.findall(raw_output)
        or _JSON_FENCE_RE.findall(raw_output)
    )
    qualifying, parse_error = _qualifying_fences(candidates)
    if not qualifying:
        # No fence at all: the raw text is still the record.
        return None, (parse_error if candidates else None)
    own = [
        data for data in qualifying
        if _same_identity(data.get("reviewer"), reviewer_id)
    ]
    if not own:
        return None, _foreign_fences_error(qualifying, reviewer_id)
    return _own_verdict(own)


def _own_verdict(own: list[dict]) -> tuple[dict | None, str | None]:
    verdict, error = _validated(own[-1])
    if len(own) > 1:
        ambiguity = f"ambiguous: {len(own)} own verdict fences (last used)"
        error = f"{ambiguity}; {error}" if error else ambiguity
    return verdict, error


def _foreign_fences_error(qualifying: list[dict], reviewer_id: str) -> str:
    quoted = sorted({
        str(data.get("reviewer")) for data in qualifying
        if isinstance(data.get("reviewer"), str)
    })
    return (
        f"{len(qualifying)} verdict fences, none authored by "
        f"{reviewer_id or 'this agent'} (quoted: {', '.join(quoted)})"
    )


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
    verdict, parse_error = _extract_verdict(raw_output, reviewer_id)
    stored, sanitized = _sanitize(raw_output)
    return {
        "ts": datetime.now(UTC).isoformat(),
        "session_id": session_id,
        "reviewer_id": reviewer_id,
        "seq": seq,
        # ``stored_sha256`` is the digest OF WHAT IS ON DISK, so the
        # operator can verify the file they are reading. ``raw_sha256``
        # is the digest of the text as returned, which is the dedup key
        # across writers; the two differ only when redaction rewrote the
        # text, and ``sanitized`` says which case this is.
        "stored_sha256": hashlib.sha256(stored.encode("utf-8")).hexdigest(),
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

    Never raises. Deduplicates by finding the 8-hex digest prefix in a
    filename and then confirming the full 256-bit ``raw_sha256`` in the
    body, so the two writers do not double-record the same output and a
    32-bit filename collision cannot adopt a different text.
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
        if prior.get("raw_sha256") != digest:
            continue  # 32-bit filename match, 256-bit body disagrees
        prior["path"] = str(path)
        return prior
    return None


def _expired(session_dir: Path, cutoff: datetime) -> bool:
    try:
        mtime = datetime.fromtimestamp(session_dir.stat().st_mtime, tz=UTC)
    except OSError:
        return False
    return mtime < cutoff


def _is_own_file(item: Path) -> bool:
    """True only for names this module writes."""
    if item.is_symlink() or not item.is_file():
        return False
    name = item.name
    if name == _NOTICES_NAME or name.startswith(f"{_NOTICES_NAME}.claim-"):
        return True
    if name.startswith(".") and ".tmp-" in name:
        return True  # an interrupted atomic publish
    return bool(_RECORD_NAME_RE.fullmatch(name))


def _purge(session_dir: Path) -> bool:
    """Remove a session's records. Only own files; never recursive.

    Every entry is checked against the ledger's own naming before
    anything is deleted: unlinking whatever happened to be a regular
    file destroyed an operator's notes that this module never wrote.
    A directory holding anything else is refused whole — and refused
    BEFORE the first unlink, so a refusal never leaves the verdicts
    already gone (destruction with a clean receipt).
    """
    try:
        items = list(session_dir.iterdir())
        if not all(_is_own_file(item) for item in items):
            return False  # foreign content: leave the whole dir alone
        for item in items:
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
            # A dot-directory is not a session: `.quarantine/` holds
            # invalidated verdicts kept deliberately as evidence, and
            # retention must never age those out.
            if session_dir.name.startswith(".") or not _safe_id(session_dir.name):
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
    return session_dir / _NOTICES_NAME if _safe_id(session_id) else None


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


def _read_lines(path: Path) -> list[dict]:
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # a torn append must not swallow the rest
    return entries


def take_notices(session_id: str) -> tuple[list[dict], list[Path]]:
    """Claim the queued notices. Returns (entries, tokens).

    The live queue is RENAMED aside before it is read, so a SubagentStop
    that appends while the orchestrator is being told creates a fresh
    queue and is delivered next turn. Deleting the whole file after the
    read destroyed anything that arrived in that window — a reviewer's
    verdict lost between the read and the unlink.

    Leftover claim files from an interrupted drain are picked up too, so
    a crash re-delivers rather than loses.
    """
    entries: list[dict] = []
    tokens: list[Path] = []
    try:
        path = _notice_path(session_id)
        if path is None:
            return [], []
        for stale in sorted(path.parent.glob(f"{path.name}.claim-*")):
            tokens.append(stale)
            entries.extend(_read_lines(stale))
        claim = _claim_queue(path)
        if claim is not None:
            tokens.append(claim)
            entries.extend(_read_lines(claim))
    except Exception:
        return entries, tokens
    return entries, tokens


def _claim_queue(path: Path) -> Path | None:
    """Rename the live queue aside; None when there is nothing to claim."""
    if not path.is_file():
        return None
    claim = path.with_name(f"{path.name}.claim-{os.getpid()}-{uuid4().hex[:8]}")
    try:
        os.replace(path, claim)
    except OSError:
        return None
    return claim


def read_notices(session_id: str) -> list[dict]:
    """Queued notices for a session, WITHOUT claiming them ([] when none)."""
    try:
        path = _notice_path(session_id)
        if path is None:
            return []
        entries: list[dict] = []
        for claimed in sorted(path.parent.glob(f"{path.name}.claim-*")):
            entries.extend(_read_lines(claimed))
        if path.is_file():
            entries.extend(_read_lines(path))
        return entries
    except Exception:
        return []


def clear_notices(session_id: str, tokens: list[Path] | None = None) -> None:
    """Drop the CLAIMED notices — call only AFTER they were delivered.

    Only the claim files handed out by ``take_notices`` are removed, so
    anything queued since the claim survives untouched.
    """
    try:
        if tokens is None:
            path = _notice_path(session_id)
            tokens = sorted(path.parent.glob(f"{path.name}.claim-*")) if path else []
        for token in tokens:
            with contextlib.suppress(OSError):
                token.unlink(missing_ok=True)
    except Exception:
        return


def notices_context(session_id: str) -> str:
    """The orchestrator-facing block, read WITHOUT claiming ("" if none)."""
    return _render(read_notices(session_id))


def claim_notices_context(session_id: str) -> tuple[str, list[Path]]:
    """The block plus the claim tokens to clear once it is delivered."""
    entries, tokens = take_notices(session_id)
    return _render(entries), tokens


def _render(entries: list[dict]) -> str:
    lines = []
    for entry in entries:
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
