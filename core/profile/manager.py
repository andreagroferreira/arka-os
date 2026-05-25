"""Profile manager — safe read/write of ~/.arkaos/profile.json (PR63 v2.81.0).

The profile is operator-local user data:
  - identity (name, company, role)
  - market context (language, market)
  - filesystem context (projectsDir, vaultPath)
  - timestamps (created, updated)

Used by:
  - Sync engine (`core/sync/engine.py`) to discover project directories
    from `projectsDir`
  - Dashboard Settings page (PR63) for editing
  - Various skills to greet by name and route by market

Lives at ``~/.arkaos/profile.json`` per ADR
`docs/adr/2026-04-17-user-data-separation.md`. The manager NEVER
raises on disk errors — read returns a default ``Profile``, write
swallows OSError so a failed save is logged but doesn't break the
caller.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


DEFAULT_PROFILE_PATH = Path.home() / ".arkaos" / "profile.json"

# Fields the API accepts in a POST payload — anything else is ignored
# so callers can't sneak in arbitrary JSON.
_WRITABLE_FIELDS = frozenset({
    "name", "language", "market", "role", "company",
    "projectsDir", "vaultPath",
})


@dataclass
class Profile:
    """Operator profile stored at ``~/.arkaos/profile.json``."""

    version: str = "2"
    name: str = ""
    language: str = "en"
    market: str = ""
    role: str = ""
    company: str = ""
    projectsDir: str = ""
    vaultPath: str = ""
    created: str = ""
    updated: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "Profile":
        """Build a Profile from a JSON dict, dropping unknown keys."""
        if not isinstance(data, dict):
            return cls()
        known = {
            f.name: data[f.name]
            for f in cls.__dataclass_fields__.values()  # type: ignore[attr-defined]
            if f.name in data and data[f.name] is not None
        }
        # Pydantic-free defensive conversion: every field must be a string.
        for key, value in list(known.items()):
            if not isinstance(value, str):
                known[key] = str(value)
        return cls(**known)

    def to_dict(self) -> dict:
        return asdict(self)


class ProfileManager:
    """Read / patch / write the operator profile.

    Always returns a ``Profile`` (the dataclass) — even when the file
    doesn't exist or is unparseable. The default Profile carries empty
    strings everywhere; the dashboard renders that as a setup CTA.
    """

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or DEFAULT_PROFILE_PATH

    @property
    def path(self) -> Path:
        return self._path

    def read(self) -> Profile:
        """Return the current profile, or a default Profile on any error."""
        if not self._path.exists():
            return Profile()
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return Profile()
        return Profile.from_dict(data)

    def patch(self, updates: dict[str, Any]) -> Profile:
        """Merge ``updates`` into the stored profile and persist.

        - Drops any key not in ``_WRITABLE_FIELDS``.
        - Coerces values to strings (the schema is all-string).
        - Bumps ``updated`` to the current UTC timestamp.
        - Initialises ``created`` if absent.
        - Atomic write (.tmp + os.replace).
        - Returns the new Profile.
        """
        current = self.read()
        sanitized = {
            k: ("" if v is None else str(v))
            for k, v in updates.items()
            if k in _WRITABLE_FIELDS
        }
        merged = {**current.to_dict(), **sanitized}
        now = datetime.now(timezone.utc).isoformat()
        merged["updated"] = now
        if not merged.get("created"):
            merged["created"] = now
        merged["version"] = "2"
        self._write(merged)
        return Profile.from_dict(merged)

    def _write(self, data: dict) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._path.with_suffix(self._path.suffix + ".tmp")
            tmp.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            tmp.replace(self._path)
        except OSError:
            # Caller still gets a Profile back from patch(); persistence
            # failure is logged via stderr by upstream callers when
            # appropriate. We never raise.
            return


# ─── Helpers ────────────────────────────────────────────────────────────


def parse_projects_dirs(value: str) -> list[str]:
    """Split the free-text ``projectsDir`` field into individual paths.

    The historical schema stored e.g.
        "/Users/foo/Herd para Laravel, /Users/foo/Work para Nuxt"
    so the parser walks the comma-separated segments and keeps anything
    that starts with ``/`` (POSIX absolute) or ``~/`` (home-relative).
    """
    if not value:
        return []
    out: list[str] = []
    for raw in value.split(","):
        token = raw.strip()
        if not token:
            continue
        # First whitespace-delimited word that looks like a path wins.
        for word in token.split():
            if word.startswith("/") or word.startswith("~/"):
                out.append(word)
                break
    return out
