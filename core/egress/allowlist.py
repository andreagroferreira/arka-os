"""Expiring egress exceptions — narrow, auditable, never for clients.

An allowlist entry permits ONE finding kind + token pair to leave,
until it expires. Two kinds are unallowlistable by construction:
``client-identifier`` (confidentiality is non-negotiable — the v2.18.0
npm leak precedent) and ``redaction-config-missing`` (an exception to
fail-closed would BE the open-by-default this package exists to
prevent). Malformed or expired entries permit nothing; a broken
allowlist degrades to deny, never to allow.

File: ``~/.arkaos/egress/allowlist.json`` —
``{"entries": [{"kind": "secret" | "home-path", "token": "<exact>",
"reason": "...", "expires": "<ISO-8601>",
"destinations": ["notebooklm"]}]}``. ``destinations`` is optional;
absent means any destination.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

ALLOWLISTABLE_KINDS: frozenset[str] = frozenset({"secret", "home-path"})


def default_allowlist_path(home: Path | None = None) -> Path:
    return (home or Path.home()) / ".arkaos" / "egress" / "allowlist.json"


@dataclass(frozen=True)
class AllowlistEntry:
    """One live exception, already validated and unexpired."""

    kind: str
    token: str
    reason: str
    expires: datetime
    destinations: tuple[str, ...]  # empty = any destination

    def permits(self, kind: str, token: str, destination: str) -> bool:
        return (
            self.kind == kind
            and self.token == token
            and (not self.destinations or destination in self.destinations)
        )


def active_entries(
    path: Path, now: datetime | None = None
) -> list[AllowlistEntry]:
    """Live entries in the allowlist file; never raises.

    Anything unparseable, incomplete, of an unallowlistable kind, or
    past its expiry is dropped — a defect in the file narrows what is
    permitted; it never widens it. The catch is deliberately broad
    (QG D1 r1: a latin-1 file raised UnicodeDecodeError through the
    original three-exception tuple; a naive ``now`` raised TypeError
    at the expiry comparison): any failure here means "no exceptions
    are in force", which is the deny direction.
    """
    moment = now or datetime.now(UTC)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        raw_entries = data.get("entries", [])
        if not isinstance(raw_entries, list):
            return []
        return [
            entry
            for raw in raw_entries
            if (entry := _parse_entry(raw)) is not None
            and entry.expires > moment
        ]
    except Exception:
        return []


def permits(
    entries: list[AllowlistEntry], kind: str, token: str, destination: str
) -> bool:
    """True when a live entry covers this exact finding."""
    if kind not in ALLOWLISTABLE_KINDS:
        return False
    return any(e.permits(kind, token, destination) for e in entries)


def _parse_entry(raw: object) -> AllowlistEntry | None:
    if not isinstance(raw, dict):
        return None
    kind = raw.get("kind")
    token = raw.get("token")
    reason = raw.get("reason")
    if kind not in ALLOWLISTABLE_KINDS or not token or not reason:
        return None
    expires = _parse_expiry(raw.get("expires"))
    if expires is None:
        return None
    destinations = raw.get("destinations", [])
    if not isinstance(destinations, list):
        return None
    return AllowlistEntry(
        kind=str(kind),
        token=str(token),
        reason=str(reason),
        expires=expires,
        destinations=tuple(str(d) for d in destinations),
    )


def _parse_expiry(value: object) -> datetime | None:
    """A usable, timezone-aware expiry — or None (entry dropped).

    An entry with no expiry, a malformed one, or a naive timestamp is
    invalid: an exception that cannot expire is a permanent hole.
    """
    if not isinstance(value, str):
        return None
    try:
        expires = datetime.fromisoformat(value)
    except ValueError:
        return None
    return expires if expires.tzinfo is not None else None
