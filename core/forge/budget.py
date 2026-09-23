"""Deadline budget for the Forge's outbound decisions (JEV PR2, decision 3).

The Forge had no latency primitive; its two Jev sites (``forge-departments``
and ``forge-complexity``) run in sequence, so each call is capped at its
own ceiling AND at what is left of one monotonic deadline for the step.
Same contract as the UserPromptSubmit ``_Budget.remaining_ms``, without
the hook's 500 ms reserve: nothing follows the Forge's calls under a
runtime timeout.
"""

from __future__ import annotations

import time
from collections.abc import Callable

FORGE_TOTAL_MS = 5000
FORGE_CALL_MS = 3000


class ForgeBudget:
    """A monotonic deadline shared by the calls of one Forge step."""

    def __init__(
        self, total_ms: int = FORGE_TOTAL_MS, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._clock = clock
        self.deadline = clock() + total_ms / 1000.0

    def remaining_ms(self, cap: int = FORGE_CALL_MS) -> int:
        """Milliseconds the next call may spend: at most ``cap``, never below 0."""
        left = int((self.deadline - self._clock()) * 1000)
        return max(0, min(cap, left))
