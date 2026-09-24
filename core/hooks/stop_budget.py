"""Monotonic deadline for the Stop hook (JEV Decisions Layer PR3).

The runtime kills Stop at its 5 s ceiling (``config/settings-template.json``)
and the hook ran ~7 detectors in sequence with no deadline. The one
network stage it now carries — the Jev call for the four Stop sites —
must never be what pushes it over. Same design as the UserPromptSubmit
``_Budget`` (PR-A3): a deadline fixed when the hook starts, a reserve
kept for the local stages that follow, and a network cap the caller
passes in.

Budget via ``ARKA_STOP_BUDGET_MS`` (default 3000 ms); 500 ms reserved.
"""

from __future__ import annotations

import os
import time

BUDGET_ENV = "ARKA_STOP_BUDGET_MS"
DEFAULT_BUDGET_MS = 3000
RESERVE_MS = 500


def _budget_ms() -> int:
    try:
        value = int(os.environ.get(BUDGET_ENV, str(DEFAULT_BUDGET_MS)))
    except ValueError:
        return DEFAULT_BUDGET_MS
    return value if value > 0 else DEFAULT_BUDGET_MS


class StopBudget:
    """Deadline fixed at construction; ``start`` defaults to now."""

    def __init__(self, start: float | None = None) -> None:
        origin = time.monotonic() if start is None else start
        self.deadline = origin + _budget_ms() / 1000.0

    def remaining_ms(self, cap: int) -> int:
        """Milliseconds a network stage may spend: at most ``cap``, and
        never the last ``RESERVE_MS`` kept for the stages that follow."""
        left = int((self.deadline - time.monotonic()) * 1000) - RESERVE_MS
        return max(0, min(cap, left))
