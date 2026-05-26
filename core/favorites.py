"""Favorites store for agents and personas (PR86a v3.15.0).

Single JSON file at ``~/.arkaos/favorites.json`` shaped as
``{"agents": ["<id>", ...], "personas": ["<id>", ...]}``.

Survives across sessions, mutated by the dashboard. No tier-0 protection
needed — favouriting is read-only intent.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

FavoriteKind = Literal["agents", "personas"]
_VALID_KINDS: tuple[str, ...] = ("agents", "personas")


def _store_path() -> Path:
    return Path.home() / ".arkaos" / "favorites.json"


def _load() -> dict[str, list[str]]:
    path = _store_path()
    if not path.exists():
        return {"agents": [], "personas": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"agents": [], "personas": []}
    if not isinstance(data, dict):
        return {"agents": [], "personas": []}
    return {
        "agents": [str(x) for x in (data.get("agents") or []) if isinstance(x, str)],
        "personas": [str(x) for x in (data.get("personas") or []) if isinstance(x, str)],
    }


def _save(state: dict[str, list[str]]) -> None:
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp.replace(path)


def list_favorites() -> dict[str, list[str]]:
    """Return the current favourites payload."""
    return _load()


def is_favorite(kind: str, item_id: str) -> bool:
    if kind not in _VALID_KINDS:
        return False
    state = _load()
    return item_id in state.get(kind, [])


def toggle(kind: str, item_id: str) -> dict:
    """Flip the favourite state. Returns ``{kind, id, favorited}``."""
    if kind not in _VALID_KINDS:
        return {"error": f"unknown kind: {kind!r}"}
    if not item_id:
        return {"error": "id is required"}
    state = _load()
    bucket = state.setdefault(kind, [])
    if item_id in bucket:
        bucket.remove(item_id)
        favorited = False
    else:
        bucket.append(item_id)
        favorited = True
    state[kind] = bucket
    _save(state)
    return {"kind": kind, "id": item_id, "favorited": favorited}


def set_favorite(kind: str, item_id: str, favorited: bool) -> dict:
    """Force a specific state. Useful for tests / bulk operations."""
    if kind not in _VALID_KINDS:
        return {"error": f"unknown kind: {kind!r}"}
    state = _load()
    bucket = state.setdefault(kind, [])
    if favorited and item_id not in bucket:
        bucket.append(item_id)
    elif not favorited and item_id in bucket:
        bucket.remove(item_id)
    state[kind] = bucket
    _save(state)
    return {"kind": kind, "id": item_id, "favorited": favorited}


def set_many(kind: str, ids: list[str], favorited: bool) -> dict:
    """PR97c v3.61.0 — bulk-set favourite state for many ids.

    Returns ``{kind, favorited, applied: N, total: N}`` where applied
    counts how many ids actually changed state.
    """
    if kind not in _VALID_KINDS:
        return {"error": f"unknown kind: {kind!r}", "applied": 0, "total": 0}
    if not isinstance(ids, list):
        return {"error": "ids must be a list", "applied": 0, "total": 0}
    state = _load()
    bucket = state.setdefault(kind, [])
    existing = set(bucket)
    applied = 0
    for item_id in ids:
        if not isinstance(item_id, str) or not item_id:
            continue
        if favorited and item_id not in existing:
            existing.add(item_id)
            applied += 1
        elif not favorited and item_id in existing:
            existing.discard(item_id)
            applied += 1
    state[kind] = list(existing)
    _save(state)
    return {
        "kind": kind,
        "favorited": favorited,
        "applied": applied,
        "total": len([i for i in ids if isinstance(i, str) and i]),
    }
