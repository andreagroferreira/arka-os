"""Fail-closed redaction for egress payloads.

Thin, deliberate wrapper: the identifier list and the replacement
semantics belong to ``core.evals.sanitizer`` (one source of truth with
the release leak-scanner), and this module adds only the egress-side
contract — redaction that cannot be skipped, plus a residual check
that is DELIBERATELY looser than the sanitizer, so a payload the
sanitizer cannot fully redact is denied instead of leaking.
"""

from __future__ import annotations

from pathlib import Path

from core.evals.sanitizer import SanitizerConfigMissing, sanitize_text
from core.governance.leak_scanner import load_redaction_patterns

__all__ = ["SanitizerConfigMissing", "redact", "residual_identifiers"]


def redact(text: str, config_path: Path | None = None) -> tuple[str, dict[str, int]]:
    """Redact client identifiers; ``(clean_text, placeholder_counts)``.

    Raises :class:`SanitizerConfigMissing` when the redaction config is
    absent or empty — the caller (``policy.evaluate``) converts that
    into a denial, never into a pass-through.
    """
    return sanitize_text(text, config_path=config_path)


def residual_identifiers(text: str, config_path: Path | None = None) -> list[str]:
    """Configured identifiers still present in *text*, as substrings.

    Defence in depth only counts when the second layer differs from
    the first (QG D1 r1, Francisca B2): the sanitizer replaces
    word-boundary matches, so a compound token like ``<client>2026``
    survives redaction untouched. This check is therefore
    SUBSTRING-based — no boundaries, case-insensitive. Any hit on the
    redacted text denies; the false-positive cost of the looser match
    is a denial, never a leak.
    """
    patterns = load_redaction_patterns(config_path)
    if not patterns:
        return []
    lowered = text.lower()
    return [p for p in patterns if p in lowered]
