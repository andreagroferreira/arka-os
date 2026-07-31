"""Hashed egress audit trail — evidence of every decision, leak of none.

One JSONL line per ``evaluate`` outcome (allow AND deny) in
``~/.arkaos/egress/audit.jsonl`` (dir 0700, file 0600); a failed
write is reported to the caller rather than swallowed. The line
carries digests and finding KINDS with salted-hash tokens — never the
payload, never a client name, never a secret value, never a raw path.
The audit file itself must be safe to read aloud.

``record`` returns False instead of raising: the caller
(``policy.evaluate``) treats a failed audit as fail-closed — an ALLOW
that cannot be audited flips to denied, and the flip itself is
re-recorded best-effort.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path


def default_audit_path(home: Path | None = None) -> Path:
    return (home or Path.home()) / ".arkaos" / "egress" / "audit.jsonl"


def default_salt_path(home: Path | None = None) -> Path:
    return (home or Path.home()) / ".arkaos" / "egress" / ".audit-salt"


def load_or_create_salt(path: Path) -> bytes:
    """Per-install random salt for token hashing; created on first use.

    The finding tokens this package hashes are LOW-ENTROPY and
    enumerable — the client list, the fixed secret-label vocabulary,
    paths under a known home — so an unsalted digest is a
    confirm-a-guess lookup for anyone holding the candidate list (QG
    D1 r2, Francisca M1: reversed in microseconds). Keyed with a salt,
    the tokens confirm nothing to a reader who holds only the audit
    file. A salt that cannot be read or created degrades to ``b""`` —
    hashes stay raw-material-free; only the guess-confirmation
    resistance is lost. An EMPTY read is treated as not-yet-created (a
    concurrent creator's file exists before its bytes land — QG D1 r3
    F-M1), so the create path retries briefly before degrading.
    """
    data = _read_salt(path)
    if data:
        return data
    created = _create_salt(path)
    if created is not None:
        return created
    for _ in range(3):  # a concurrent creator may have won; its write
        time.sleep(0.005)  # may be in flight — bounded retry, degrade
        data = _read_salt(path)
        if data:
            return data
    return b""


def _create_salt(path: Path) -> bytes | None:
    """The new salt, or None when the file already exists (concurrent
    creator) or the filesystem refuses."""
    salt = os.urandom(16)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(path.parent, 0o700)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(salt)
        return salt
    except OSError:
        return None


def _read_salt(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError:
        return b""


def hash_token(token: str, salt: bytes = b"") -> str:
    """Keyed 16-hex digest for a finding token.

    Long enough to correlate entries across lines, and it carries no
    raw material. With the per-install salt it is also not a
    confirm-a-guess oracle: the tokens are low-entropy (client names,
    secret labels, home paths), so an UNSALTED truncated hash would
    confirm a candidate for anyone who already holds the list.
    """
    payload = token.encode("utf-8", errors="surrogatepass")
    return hmac.new(salt, payload, hashlib.sha256).hexdigest()[:16]


def record(entry: dict, path: Path, now: datetime | None = None) -> bool:
    """Append one audit line; True on durable success, False otherwise.

    The catch is broad by design: any failure — filesystem OR a
    payload that will not serialize — reads as "not audited", and the
    caller flips an unaudited ALLOW to denied. ``os.chmod(path, ...)``
    runs on every write, not only at creation, so a pre-existing file
    with looser permissions is repaired rather than trusted (QG D1 r1
    M2).
    """
    try:
        stamped = {
            "ts": (now or datetime.now(UTC)).isoformat(),
            **entry,
        }
        line = json.dumps(stamped, ensure_ascii=False, sort_keys=True)
        path.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(path.parent, 0o700)
        fd = os.open(
            path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600
        )
        with os.fdopen(fd, "a", encoding="utf-8") as handle:
            os.chmod(path, 0o600)
            handle.write(line + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return True
    except Exception:
        return False
