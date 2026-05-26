"""Trash + undo for destructive dashboard actions (PR85b v3.12.0).

Captures agent/persona deletions and agent moves into
``~/.arkaos/trash/`` so the operator can undo recent mistakes.

Each trash entry is two files:
  - ``<timestamp>-<id>.payload``  — the file content (for deletes) or
    empty (for moves, which don't lose data)
  - ``<timestamp>-<id>.meta.json`` — metadata: kind, original_path,
    optional new_path, agent/persona id, timestamp

Trash is bounded by ``MAX_ENTRIES`` (newest 50 kept). Older entries
are pruned on every `record_*` call.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

TrashKind = Literal["agent-delete", "persona-delete", "agent-move"]

MAX_ENTRIES = 50
_TRASH_DIR_NAME = ".arkaos/trash"


def _trash_dir() -> Path:
    target = Path.home() / _TRASH_DIR_NAME
    target.mkdir(parents=True, exist_ok=True)
    return target


@dataclass(frozen=True)
class TrashEntry:
    id: str
    kind: TrashKind
    item_id: str
    timestamp: float
    original_path: str
    new_path: str | None
    has_payload: bool


def record_deletion(
    kind: TrashKind,
    item_id: str,
    original_path: str,
    content: str,
) -> str:
    """Record a destructive delete. Returns the new trash entry id."""
    return _record(
        kind=kind,
        item_id=item_id,
        original_path=original_path,
        new_path=None,
        payload=content,
    )


def record_move(item_id: str, from_path: str, to_path: str) -> str:
    """Record an agent department move. Payload is empty."""
    return _record(
        kind="agent-move",
        item_id=item_id,
        original_path=from_path,
        new_path=to_path,
        payload="",
    )


def list_trash(limit: int = 10) -> list[dict]:
    """Return the newest N trash entries (sorted desc by timestamp)."""
    entries = _scan()
    return [_entry_to_dict(e) for e in entries[: max(0, int(limit))]]


def restore(trash_id: str) -> dict:
    """Undo the action identified by trash_id. Returns a status dict."""
    entry = _find(trash_id)
    if entry is None:
        return {"error": "trash entry not found"}
    if entry.kind in ("agent-delete", "persona-delete"):
        return _restore_delete(entry)
    if entry.kind == "agent-move":
        return _restore_move(entry)
    return {"error": f"unknown trash kind: {entry.kind!r}"}


def purge(trash_id: str) -> dict:
    """Drop a trash entry without restoring it."""
    entry = _find(trash_id)
    if entry is None:
        return {"error": "trash entry not found"}
    _delete_entry(entry)
    return {"purged": True, "id": trash_id}


# --- Internal helpers ---


def _record(
    *,
    kind: TrashKind,
    item_id: str,
    original_path: str,
    new_path: str | None,
    payload: str,
) -> str:
    ts = time.time()
    trash_id = f"{int(ts)}-{uuid.uuid4().hex[:6]}"
    base = _trash_dir() / trash_id
    if payload:
        base.with_suffix(".payload").write_text(payload, encoding="utf-8")
    meta = {
        "id": trash_id,
        "kind": kind,
        "item_id": item_id,
        "timestamp": ts,
        "original_path": original_path,
        "new_path": new_path,
        "has_payload": bool(payload),
    }
    base.with_suffix(".meta.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8",
    )
    _prune()
    return trash_id


def _scan() -> list[TrashEntry]:
    entries: list[TrashEntry] = []
    for meta_file in _trash_dir().glob("*.meta.json"):
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        try:
            entries.append(TrashEntry(
                id=str(meta.get("id") or meta_file.stem.replace(".meta", "")),
                kind=meta.get("kind") or "agent-delete",
                item_id=str(meta.get("item_id") or ""),
                timestamp=float(meta.get("timestamp") or 0.0),
                original_path=str(meta.get("original_path") or ""),
                new_path=meta.get("new_path"),
                has_payload=bool(meta.get("has_payload")),
            ))
        except (TypeError, ValueError):
            continue
    entries.sort(key=lambda e: e.timestamp, reverse=True)
    return entries


def _find(trash_id: str) -> TrashEntry | None:
    for entry in _scan():
        if entry.id == trash_id:
            return entry
    return None


def _restore_delete(entry: TrashEntry) -> dict:
    payload_path = _trash_dir() / f"{entry.id}.payload"
    if not payload_path.exists():
        return {"error": "payload missing — cannot restore"}
    dest = Path(entry.original_path)
    if dest.exists():
        return {"error": f"target already exists: {dest}"}
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(payload_path.read_text(encoding="utf-8"), encoding="utf-8")
    except OSError as exc:
        return {"error": f"restore failed: {exc}"}
    _delete_entry(entry)
    return {"restored": True, "kind": entry.kind, "path": str(dest)}


def _restore_move(entry: TrashEntry) -> dict:
    if not entry.new_path:
        return {"error": "move record has no new_path"}
    current = Path(entry.new_path)
    if not current.exists():
        return {"error": f"file no longer at {current}"}
    target = Path(entry.original_path)
    if target.exists():
        return {"error": f"original path occupied: {target}"}
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        # Rewrite the `department:` field back if YAML
        if target.suffix in (".yaml", ".yml"):
            try:
                import yaml as _yaml
                raw = _yaml.safe_load(current.read_text(encoding="utf-8")) or {}
                if isinstance(raw, dict):
                    old_dept = target.parent.parent.name
                    raw["department"] = old_dept
                    current.write_text(
                        _yaml.safe_dump(
                            raw,
                            sort_keys=False,
                            allow_unicode=True,
                            default_flow_style=False,
                        ),
                        encoding="utf-8",
                    )
            except Exception:
                pass
        current.rename(target)
    except OSError as exc:
        return {"error": f"restore failed: {exc}"}
    _delete_entry(entry)
    return {"restored": True, "kind": entry.kind, "path": str(target)}


def _delete_entry(entry: TrashEntry) -> None:
    base = _trash_dir() / entry.id
    for suffix in (".payload", ".meta.json"):
        p = base.with_suffix(suffix)
        if p.exists():
            try:
                p.unlink()
            except OSError:
                pass


def _prune() -> None:
    entries = _scan()
    if len(entries) <= MAX_ENTRIES:
        return
    for entry in entries[MAX_ENTRIES:]:
        _delete_entry(entry)


def _entry_to_dict(entry: TrashEntry) -> dict:
    return {
        "id": entry.id,
        "kind": entry.kind,
        "item_id": entry.item_id,
        "timestamp": entry.timestamp,
        "original_path": entry.original_path,
        "new_path": entry.new_path,
        "has_payload": entry.has_payload,
    }
