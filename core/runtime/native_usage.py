"""Close the native-usage cost blind spot in llm-cost.jsonl.

The bulk of real spend happens through Claude Code natively (the
interactive session itself) and never touches `core.runtime.llm_provider`,
so `~/.arkaos/telemetry/llm-cost.jsonl` under-reports. The Stop hook
(`config/hooks/stop.sh`) calls `record_native_usage` on every stop:

1. `extract_last_usage` parses the session transcript (JSONL) and
   returns the LAST assistant record carrying `message.usage`
   (input_tokens, output_tokens, cache_read_input_tokens,
   cache_creation_input_tokens, model).
2. A tiny per-session cursor file
   (`/tmp/arkaos-native-cost/<safe_sid>.txt`, last-recorded record id)
   ensures each turn is recorded exactly once.
3. The row is appended via `llm_cost_telemetry.record_cost` with
   category `native:session` and the real model id. Unknown model ids
   produce null-cost rows (tokens still recorded — fine per pricing.py).

Token accounting mirrors `llm_provider._response_from_anthropic`:
`tokens_in` = fresh input + cache reads + cache writes (every billable
input token); `cached_tokens` = cache reads only.

Never raises — cost capture must never break a Stop hook.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from core.runtime.llm_cost_telemetry import record_cost
from core.runtime.pricing import estimate_cost_usd
from core.shared.safe_session_id import safe_session_id
from core.shared.temp_paths import arkaos_temp_dir

DEFAULT_CURSOR_DIR = arkaos_temp_dir("arkaos-native-cost")

_USAGE_KEYS = (
    "input_tokens",
    "output_tokens",
    "cache_read_input_tokens",
    "cache_creation_input_tokens",
)


def _as_int(raw: Any) -> int:
    try:
        return max(0, int(raw or 0))
    except (TypeError, ValueError):
        return 0


def _usage_from_record(record: dict[str, Any]) -> dict[str, Any] | None:
    """Extract usage + model from one transcript record, or None."""
    message = record.get("message")
    message = message if isinstance(message, dict) else {}
    role = record.get("role") or message.get("role")
    if role != "assistant":
        return None
    usage = message.get("usage") or record.get("usage")
    if not isinstance(usage, dict) or not any(k in usage for k in _USAGE_KEYS):
        return None
    return {
        "model": str(message.get("model") or record.get("model") or ""),
        "input_tokens": _as_int(usage.get("input_tokens")),
        "output_tokens": _as_int(usage.get("output_tokens")),
        "cache_read_input_tokens": _as_int(usage.get("cache_read_input_tokens")),
        "cache_creation_input_tokens": _as_int(
            usage.get("cache_creation_input_tokens")
        ),
    }


def extract_usage_records(
    transcript_path: str, raw_text: str | None = None
) -> list[dict[str, Any]]:
    """Every assistant `message.usage` in the transcript, in order.

    Gate Economy PR-8: the last-record-only capture under-reported by
    38x on a measured session (one turn = many API calls; only the
    final one was recorded). Each dict carries `uuid` (record uuid, or
    `line:<n>` — the dedupe cursor key), `model`, and the four token
    counts. Malformed lines are skipped; empty list when nothing usable
    exists or the file is unreadable.

    ``raw_text`` (PR-6 hook consolidation): pre-read transcript
    contents; when None the file at ``transcript_path`` is read.
    """
    if raw_text is not None:
        lines = raw_text.splitlines()
    else:
        path = Path(transcript_path) if transcript_path else None
        if path is None or not path.exists():
            return []
        try:
            lines = path.read_text(
                encoding="utf-8", errors="replace"
            ).splitlines()
        except OSError:
            return []
    records: list[dict[str, Any]] = []
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict):
            continue
        usage = _usage_from_record(record)
        if usage is None:
            continue
        usage["uuid"] = str(record.get("uuid") or f"line:{index}")
        records.append(usage)
    return records


def extract_last_usage(
    transcript_path: str, raw_text: str | None = None
) -> dict[str, Any] | None:
    """The last assistant `message.usage` in the transcript, or None."""
    records = extract_usage_records(transcript_path, raw_text=raw_text)
    return records[-1] if records else None


def _new_since_cursor(
    records: list[dict[str, Any]], cursor_uuid: str | None
) -> list[dict[str, Any]]:
    """Records after the high-water uuid (fail-safe on every edge).

    No cursor → the whole session so far (first capture catches up).
    Cursor found → everything after it. Cursor set but absent from the
    transcript (rewritten/summarized file) → only the last record, the
    legacy behavior — under-counting once beats double-counting.
    """
    if cursor_uuid is None:
        return records
    for index in range(len(records) - 1, -1, -1):
        if records[index]["uuid"] == cursor_uuid:
            return records[index + 1:]
    return records[-1:]


def _cursor_matches(cursor: Path, uuid: str) -> bool:
    try:
        return cursor.exists() and cursor.read_text(
            encoding="utf-8"
        ).strip() == uuid
    except OSError:
        return False


def _write_cursor(cursor: Path, uuid: str) -> None:
    # /tmp is shared on multi-user systems — owner-only files, same
    # defence-in-depth as the other Stop-hook cursor writers.
    prev_umask = os.umask(0o077)
    try:
        cursor.parent.mkdir(parents=True, exist_ok=True)
        cursor.write_text(uuid, encoding="utf-8")
    finally:
        os.umask(prev_umask)


def record_native_usage(
    transcript_path: str,
    session_id: str,
    cursor_dir: Path | str | None = None,
    raw_text: str | None = None,
) -> bool:
    """Record the last native turn's usage once. Returns True if recorded.

    False on: no usage in transcript, unsafe session id, already
    recorded (cursor hit), or any internal error (never raises).

    ``raw_text`` (PR-6 hook consolidation): pre-read transcript contents.
    """
    try:
        records = extract_usage_records(transcript_path, raw_text=raw_text)
        if not records:
            return False
        sid = safe_session_id(session_id)
        if sid is None:
            return False
        cursor = (
            Path(cursor_dir) if cursor_dir else DEFAULT_CURSOR_DIR
        ) / f"{sid}.txt"
        cursor_uuid = None
        try:
            if cursor.exists():
                cursor_uuid = cursor.read_text(encoding="utf-8").strip()
        except OSError:
            cursor_uuid = None
        new = _new_since_cursor(records, cursor_uuid)
        if not new:
            return False
        _record_grouped(new, session_id, "native", "native:session")
        _write_cursor(cursor, records[-1]["uuid"])
        return True
    except Exception:
        return False


def _record_grouped(
    records: list[dict[str, Any]],
    session_id: str,
    provider: str,
    category: str,
) -> None:
    """One cost row per model over the given records (PR-8)."""
    by_model: dict[str, dict[str, int]] = {}
    for usage in records:
        totals = by_model.setdefault(
            usage["model"], {"in": 0, "out": 0, "cached": 0}
        )
        totals["in"] += (
            usage["input_tokens"]
            + usage["cache_read_input_tokens"]
            + usage["cache_creation_input_tokens"]
        )
        totals["out"] += usage["output_tokens"]
        totals["cached"] += usage["cache_read_input_tokens"]
    for model, totals in by_model.items():
        record_cost(
            session_id=session_id,
            provider=provider,
            model=model,
            tokens_in=totals["in"],
            tokens_out=totals["out"],
            cached_tokens=totals["cached"],
            estimated_cost_usd=estimate_cost_usd(
                model, totals["in"], totals["out"], totals["cached"]
            ),
            category=category,
        )


def record_subagent_usage(
    agent_transcript_path: str,
    session_id: str,
    agent_id: str,
    cursor_dir: Path | str | None = None,
) -> bool:
    """Record a subagent dispatch's full usage once (Gate Economy PR-8).

    Task-tool sidechains were 100% invisible to cost telemetry — QG
    reviewer dispatches left no usage record anywhere. The SubagentStop
    hook hands us the agent's own transcript; every assistant record in
    it is summed and attributed to ``subagent:<agent_id>`` under the
    PARENT session. Deduped per transcript via a path-keyed cursor.
    Never raises.
    """
    try:
        records = extract_usage_records(agent_transcript_path)
        if not records:
            return False
        sid = safe_session_id(session_id)
        if sid is None:
            return False
        path_key = hashlib.sha256(
            str(agent_transcript_path).encode("utf-8")
        ).hexdigest()[:16]
        cursor = (
            Path(cursor_dir) if cursor_dir else DEFAULT_CURSOR_DIR
        ) / f"{sid}-agent-{path_key}.txt"
        if _cursor_matches(cursor, records[-1]["uuid"]):
            return False
        _record_grouped(
            records, session_id, "native-subagent",
            f"subagent:{agent_id or 'unknown'}",
        )
        _write_cursor(cursor, records[-1]["uuid"])
        return True
    except Exception:
        return False
