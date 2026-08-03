"""Deny-by-default egress policy — the guard every upload passes.

Check order, each one sufficient to deny:

1. **Redaction, fail-closed** — no redaction config on disk means the
   payload cannot be proven clean, so it does not leave (operator
   directive 2026-07-26). What leaves is always the REDACTED text.
2. **Residual client identifiers** — the redacted text is re-scanned
   with the same pattern source; any hit means redaction failed.
   Never allowlistable.
3. **Secrets** — ``secret_labels`` vocabulary; allowlistable per exact
   label, with expiry.
4. **Operator home paths** — absolute paths under the operator's home
   AND their tilde form, matched case-insensitively; both expose
   local project structure; allowlistable per exact path.
5. **Audit** — every decision is recorded; an ALLOW that cannot be
   audited flips to denied (``audit-unavailable``).

``evaluate`` never raises. ``enforce`` is the raising convenience for
call sites that want the guard inline: redacted text back, or
:class:`EgressDeniedError`.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from core.egress import allowlist, audit, redact
from core.governance.harness_scanner import secret_labels


@dataclass(frozen=True)
class Finding:
    """One reason a payload may not leave."""

    kind: str  # redaction-config-missing | redaction-failed
    #          # | client-identifier | secret | home-path
    #          # | audit-unavailable | payload-not-text | guard-failure
    token: str

    def to_audit(self, salt: bytes = b"") -> dict[str, Any]:
        return {
            "kind": self.kind,
            "token_sha16": (
                audit.hash_token(self.token, salt) if self.token else ""
            ),
        }


@dataclass
class EgressDecision:
    """Outcome of one egress evaluation."""

    allowed: bool
    destination: str
    payload_sha256: str
    findings: list[Finding] = field(default_factory=list)
    allowlisted: list[Finding] = field(default_factory=list)
    redacted_text: str | None = None
    redacted_sha256: str = ""
    audited: bool = False

    def to_audit(self, salt: bytes = b"") -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "destination": self.destination,
            "payload_sha256": self.payload_sha256,
            "redacted_sha256": self.redacted_sha256,
            "findings": [f.to_audit(salt) for f in self.findings],
            "allowlisted": [f.to_audit(salt) for f in self.allowlisted],
        }


class EgressDeniedError(RuntimeError):
    """Raised by ``enforce`` when the payload may not leave."""

    def __init__(self, decision: EgressDecision):
        reasons = ", ".join(f.kind for f in decision.findings) or "denied"
        super().__init__(
            f"egress to {decision.destination} denied: {reasons} "
            f"(audit: {'recorded' if decision.audited else 'FAILED'})"
        )
        self.decision = decision


def evaluate(
    text: object,
    destination: str,
    *,
    config_path: Path | None = None,
    home: Path | None = None,
    allowlist_path: Path | None = None,
    audit_path: Path | None = None,
    now: datetime | None = None,
) -> EgressDecision:
    """Judge one payload against the policy. Never raises.

    ``home`` scopes the home-path check, the redaction config and the
    default allowlist / audit locations; ``now`` pins allowlist expiry
    for tests.
    """
    destination = _safe_str(destination)
    # ONCE, before any failure path, so no handler re-runs what
    # failed. Named `digest`: `payload_digest` shadowed the public
    # function here (QG D2 r12, Francisca M2).
    digest = payload_digest(text) if isinstance(text, str) else ""
    try:
        decision = _judge(
            text, destination, config_path, home, allowlist_path, now
        )
    except Exception as exc:  # never-raises boundary — deny, not crash
        decision = _guard_failure(destination, digest, exc)
    return _audited(decision, home, audit_path, now)


def _guard_failure(
    destination: str, digest: str, exc: BaseException
) -> EgressDecision:
    return EgressDecision(
        allowed=False, destination=destination, payload_sha256=digest,
        findings=[Finding("guard-failure", type(exc).__name__)],
    )


def default_redaction_config_path(home: Path | None = None) -> Path:
    """The identifier list *home* implies.

    Mirrors ``leak_scanner._DEFAULT_CONFIG_PATH`` for the real home, so
    scoping by ``home`` never changes production behaviour — pinned by
    ``test_egress_policy.py`` rather than by this comment.
    """
    return (home or Path.home()) / ".arkaos" / "redaction-clients.json"


def _safe_str(value: object) -> str:
    try:
        return str(value)
    except Exception:
        return f"<unprintable {type(value).__name__}>"


def _audited(
    decision: EgressDecision,
    home: Path | None,
    audit_path: Path | None,
    now: datetime | None,
) -> EgressDecision:
    try:
        target = audit_path or audit.default_audit_path(home)
        salt = audit.load_or_create_salt(audit.default_salt_path(home))
    except Exception:  # a home that cannot even form paths (M5)
        target, salt = None, b""
    decision.audited = target is not None and audit.record(
        decision.to_audit(salt), target, now
    )
    if decision.allowed and not decision.audited:
        # No audit trail, no egress — record the flip best-effort.
        decision.allowed = False
        decision.redacted_text = None
        decision.findings.append(Finding("audit-unavailable", ""))
        if target is not None:
            audit.record(decision.to_audit(salt), target, now)
    return decision


def enforce(text: object, destination: str, **kwargs: Any) -> str:
    """The redacted text cleared to leave, or :class:`EgressDeniedError`."""
    decision = evaluate(text, destination, **kwargs)
    if not decision.allowed or decision.redacted_text is None:
        raise EgressDeniedError(decision)
    return decision.redacted_text


def _judge(
    text: object,
    destination: str,
    config_path: Path | None,
    home: Path | None,
    allowlist_path: Path | None,
    now: datetime | None,
) -> EgressDecision:
    if not isinstance(text, str):
        return _not_text(destination, text)
    decision = EgressDecision(
        allowed=False, destination=destination,
        payload_sha256=payload_digest(text),
    )
    # One scoped path for both layers: scoping only the redaction call
    # left residual_identifiers reading the real machine's list
    # (QG D2 r3, Francisca B1).
    scoped = _scoped_config(config_path, home)
    clean = _redacted(text, scoped)
    if isinstance(clean, Finding):
        decision.findings.append(clean)
        return decision
    _collect_findings(
        decision, clean, destination, scoped, home, allowlist_path, now
    )
    if not decision.findings:
        decision.allowed = True
        decision.redacted_text = clean
        decision.redacted_sha256 = payload_digest(clean)
    return decision


def _not_text(destination: str, text: object) -> EgressDecision:
    return EgressDecision(
        allowed=False, destination=destination, payload_sha256="",
        findings=[Finding("payload-not-text", type(text).__name__)],
    )


def payload_digest(text: str) -> str:
    """Total over any str — surrogatepass, because a payload holding a
    lone surrogate (routine from errors="surrogateescape" decoding or
    json.loads of an escape) must be DIGESTIBLE to be denied with an
    audit line (QG D1 r2 E-B1).

    Public because callers outside this package need the same digest
    the audit trail records; reaching for a private symbol made a D1
    rename a silent runtime break downstream (QG D2 r1, Francisca M6).
    """
    payload = text.encode("utf-8", errors="surrogatepass")
    return hashlib.sha256(payload).hexdigest()


def _scoped_config(config_path: Path | None, home: Path | None) -> Path | None:
    """The redaction config *home* implies, unless one was named.

    ``home`` scoped ``allowlist_path`` and ``audit_path`` but NOT the
    redaction config, so a caller passing ``home=`` and forgetting
    ``config_path`` judged paths against one home while redacting
    against another (QG D2 r1, Francisca M7).

    Called from inside ``_judge``, i.e. inside ``evaluate``'s try: the
    same defaulting one frame up sat OUTSIDE it, and a non-Path home
    turned the never-raises boundary into a TypeError — the very shape
    QG D1 r2 F-M5 already closed once.
    """
    if config_path is not None or home is None:
        return config_path
    return default_redaction_config_path(home)


def _redacted(text: str, config_path: Path | None) -> str | Finding:
    """The clean text, or the finding that denies it.

    A redaction that CRASHES proves nothing about the payload — same
    posture as a missing config: denied, never allowlistable (QG D1
    r1 B1: U+017F KeyError, non-list clients config, latin-1 file).
    """
    try:
        clean, _counts = redact.redact(text, config_path)
        # Annotated: redact() is untyped, so `clean` arrives as Any and
        # the union return silently degrades to Any (mypy no-any-return,
        # surfaced only with --follow-imports=skip —
        # QG D2 r3, Francisca M3).
        clean_text: str = clean
        return clean_text
    except redact.SanitizerConfigMissing:
        return Finding("redaction-config-missing", "")
    except Exception as exc:
        return Finding("redaction-failed", type(exc).__name__)


def _collect_findings(
    decision: EgressDecision,
    clean: str,
    destination: str,
    config_path: Path | None,
    home: Path | None,
    allowlist_path: Path | None,
    now: datetime | None,
) -> None:
    for token in redact.residual_identifiers(clean, config_path):
        # Never allowlistable — a residual identifier is a redaction
        # failure, not an operator choice.
        decision.findings.append(Finding("client-identifier", token))
    entries = allowlist.active_entries(
        allowlist_path or allowlist.default_allowlist_path(home), now
    )
    candidates = [
        Finding("secret", label) for label in secret_labels(clean)
    ] + [Finding("home-path", p) for p in _home_paths(clean, home)]
    for finding in candidates:
        cleared = allowlist.permits(
            entries, finding.kind, finding.token, destination
        )
        (decision.allowlisted if cleared else decision.findings).append(
            finding
        )


def _home_paths(text: str, home: Path | None) -> list[str]:
    """Distinct operator-home paths found in *text*.

    Matches the absolute form AND the ``~/`` tilde form, case-
    insensitively — macOS filesystems resolve case variants to the
    same file, and a tilde path names the home just as precisely
    (QG D1 r1 M3). Over-capture of trailing punctuation is accepted:
    it is the deny direction.
    """
    root = re.escape(str(home or Path.home()))
    pattern = re.compile(
        rf"(?:{root}(?:/[^\s'\"`)\]]*)?|~/[^\s'\"`)\]]*)",
        re.IGNORECASE,
    )
    return sorted({m.group(0) for m in pattern.finditer(text)})
