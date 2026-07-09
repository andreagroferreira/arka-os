"""Client-identifier sanitizer — distillation prerequisite (evals ADR).

Redacts every client identifier from transcript text BEFORE it can feed
a LoRA training run. Confidentiality is NON-NEGOTIABLE (v2.18.0 npm
leak precedent), so this module fails CLOSED: with no redaction config
on disk there is nothing to prove the text is clean, and sanitize()
refuses to run rather than pass text through unredacted.

The identifier list is the same one the release leak-scanner uses
(``~/.arkaos/redaction-clients.json`` via
``core.governance.leak_scanner.load_redaction_patterns``) — one source
of truth, never hardcoded in the repo.

Replacement is deterministic: the Nth pattern in the config maps to
``[CLIENT-N]`` in every run. Corpora stay diffable under the APPEND-ONLY
invariant — new clients go at the END of the config list; reordering or
deleting entries remaps the placeholders of everything sanitized before.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from core.governance.leak_scanner import load_redaction_patterns


class SanitizerConfigMissing(RuntimeError):
    """No redaction config — sanitization cannot be proven, so it refuses."""


def sanitize_text(
    text: str, config_path: Path | None = None
) -> tuple[str, dict[str, int]]:
    """Redact client identifiers; return (clean_text, per-placeholder counts).

    Raises SanitizerConfigMissing when the redaction config is absent or
    empty — fail closed, never pass text through unproven.
    """
    patterns = load_redaction_patterns(config_path)
    if not patterns:
        raise SanitizerConfigMissing(
            "redaction config missing or empty (~/.arkaos/redaction-"
            "clients.json) — refusing to sanitize without an identifier "
            "list; a silent pass-through would poison the training corpus"
        )
    # SINGLE pass over ONE longest-first alternation (QG blocker,
    # 2026-07-09): a positional per-pattern loop leaked the suffix of a
    # longer identifier whenever a shorter prefix pattern came first in
    # the config ("data" before "data dynamics corp"), and replacement
    # text could itself be re-matched. Placeholder numbers stay keyed to
    # CONFIG position, so appends never remap an existing corpus.
    index_by_pattern = {p: i for i, p in enumerate(patterns, start=1)}
    alternation = "|".join(
        re.escape(p) for p in sorted(patterns, key=len, reverse=True)
    )
    regex = re.compile(
        r"(?<![a-z0-9])(" + alternation + r")(?![a-z0-9])", re.IGNORECASE
    )
    counts: dict[str, int] = {}

    def _redact(match: re.Match[str]) -> str:
        placeholder = f"[CLIENT-{index_by_pattern[match.group(1).lower()]}]"
        counts[placeholder] = counts.get(placeholder, 0) + 1
        return placeholder

    return regex.sub(_redact, text), counts


def sanitize_file(
    path: Path, config_path: Path | None = None
) -> tuple[str, dict[str, int]]:
    return sanitize_text(
        path.read_text(encoding="utf-8"), config_path=config_path
    )


def main(argv: list[str] | None = None) -> int:
    """CLI: sanitize a file (or stdin) to stdout; counts on stderr."""
    args = argv if argv is not None else sys.argv[1:]
    try:
        if args:
            clean, counts = sanitize_file(Path(args[0]))
        else:
            clean, counts = sanitize_text(sys.stdin.read())
    except SanitizerConfigMissing as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    sys.stdout.write(clean)
    total = sum(counts.values())
    print(f"sanitized: {total} redaction(s) {counts}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
