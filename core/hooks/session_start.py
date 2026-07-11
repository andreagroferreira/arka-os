"""SessionStart memory recap (F1-A3).

Prints a compact plain-text recap of the most relevant prior turns for
the current project — importance+recency ranked, NO embedding at read
time (there is no prompt yet, so semantic ranking is impossible and is
not faked; mirrors ruflo's retrieveContextSmart where importance is the
primary signal). The session-start.sh shim appends this output to its
systemMessage.

Self-budgeted: any slow path bails to empty output — the banner must
stay snappy. F2-2 (hook consolidation) will grow this module into the
full session-start entrypoint; today it owns only the memory recap.

CLI: ``python3 -m core.hooks.session_start [cwd]``
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

_BUDGET_MS = 300
_RECAP_ITEMS = 3
_SUMMARY_CHARS = 130


def build_recap(cwd: str, budget_ms: int = _BUDGET_MS) -> str:
    start = time.monotonic()
    try:
        from core.memory.semantic_store import SessionMemoryStore, default_db_path
        if not default_db_path().is_file():
            return ""
        store = SessionMemoryStore()
        project = Path(cwd).name if cwd else ""
        records = store.recent(project_name=project or None, limit=_RECAP_ITEMS)
        if not records or (time.monotonic() - start) * 1000 > budget_ms:
            return ""
        from core.memory.semantic_store import neutralize_summary
        lines = ["[SESSION-MEMORY] Prior turns (importance+recency — not semantic):"]
        for record in records:
            summary = neutralize_summary(record.summary)[:_SUMMARY_CHARS]
            if not summary:
                continue
            day = record.ts[:10]
            lines.append(f"[SESSION-MEMORY] - {day}: {summary}")
        if len(lines) == 1:
            return ""
        stats = store.stats()
        backends = ",".join(sorted(stats.get("by_embedding_backend", {}))) or "none"
        lines.append(
            f"[SESSION-MEMORY] store: {stats.get('total_turns', 0)} turns,"
            f" backends={backends}"
        )
        return "\n".join(lines)
    except Exception:  # noqa: BLE001 — recap is best-effort, banner never breaks
        return ""


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    recap = build_recap(args[0] if args else "")
    if recap:
        print(recap)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
