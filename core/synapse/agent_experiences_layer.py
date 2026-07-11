"""Synapse layer L2.6 — Agent Experience injection.

When the user prompt contains `[arka:dispatch] <from> -> <target>`, this
layer queries `core.governance.agent_experiences` for the target agent's
recent experiences (REJECTED verdicts, lessons captured by the QG loop)
and injects them as context so the dispatched specialist inherits prior
failures across sessions.

Designed as a standalone `Layer` subclass — engine wiring happens in a
follow-up release (v3.74.1). For PR3 v1, callers (the UserPromptSubmit
hook, or a manual dispatch wrapper) invoke `compute()` directly.

Cache TTL: 30s. The experience file is appended-to, not rewritten, so a
short TTL keeps newly-recorded lessons visible to the immediately-next
dispatch.
"""

from __future__ import annotations

import re
import time

from core.governance.agent_experiences import Experience, query_experiences
from core.synapse.layers import Layer, LayerResult, PromptContext


# Mirror the parser in core.workflow.specialist_enforcer so we recognise
# the same marker the operator (and the constitution rule
# `dispatch-must-be-announced`) require for specialist dispatches.
_DISPATCH_RE = re.compile(
    r"\[arka:dispatch\]\s*[\w-]+\s*->\s*([\w-]+)", re.IGNORECASE
)


class AgentExperiencesLayer(Layer):
    """L2.6 — inject recent experiences for the dispatched specialist."""

    def __init__(self, limit: int = 5) -> None:
        self._limit = limit

    @property
    def id(self) -> str:
        return "L2.6"

    @property
    def name(self) -> str:
        return "AgentExperiences"

    @property
    def input_sensitive(self) -> bool:
        return True

    @property
    def cache_ttl(self) -> int:
        return 30

    @property
    def priority(self) -> int:
        return 25  # after AgentLayer (L2 prio 20), before KBContext (L2.5)

    def compute(self, ctx: PromptContext) -> LayerResult:
        start = time.time()
        target = _extract_dispatch_target(ctx.user_input)
        if target is None:
            return self._empty_result(start)

        experiences = query_experiences(target, limit=self._limit)
        if not experiences:
            return self._empty_result(start, tag=f"[agent-experiences:{target} none]")

        # F1-C2 decay: stale lessons collapse to a count line instead of
        # full injection — history is never lost (JSONL untouched), it
        # just stops paying context rent.
        fresh, faded_count = _split_by_decay(experiences)
        if not fresh:
            return self._empty_result(
                start, tag=f"[agent-experiences:{target} faded:{faded_count}]"
            )
        content = format_experiences(target, fresh, faded_count=faded_count)
        ms = int((time.time() - start) * 1000)
        return LayerResult(
            layer_id=self.id,
            tag=f"[agent-experiences:{target} count:{len(fresh)}]",
            content=content,
            tokens_est=max(1, len(content) // 4),
            compute_ms=ms,
            cached=False,
        )

    def _empty_result(self, start: float, tag: str = "") -> LayerResult:
        return LayerResult(
            layer_id=self.id,
            tag=tag,
            content="",
            tokens_est=0,
            compute_ms=int((time.time() - start) * 1000),
            cached=False,
        )


def _extract_dispatch_target(user_input: str) -> str | None:
    """Return the agent id from the most recent `[arka:dispatch]` marker."""
    if not user_input:
        return None
    matches = list(_DISPATCH_RE.finditer(user_input))
    if not matches:
        return None
    return matches[-1].group(1).lower()


def _split_by_decay(experiences: list[Experience]) -> tuple[list[Experience], int]:
    """Partition lessons into fresh (rendered) and faded (counted only).

    Read-time only: decay for an append-only experience JSONL needs no
    reinforcement field — a lesson's age IS its ``ts``. Config resolved
    ONCE per call (hot-path hoisting mandated by core/shared/decay.py).
    """
    from core.shared.decay import (
        INJECTION_FLOOR,
        decay_enabled,
        decayed_weight,
        half_life_days,
    )

    if not decay_enabled():
        return experiences, 0
    hl = half_life_days()
    fresh = [
        exp for exp in experiences
        if decayed_weight(exp.ts, half_life=hl, enabled=True) >= INJECTION_FLOOR
    ]
    return fresh, len(experiences) - len(fresh)


def format_experiences(
    target: str, experiences: list[Experience], faded_count: int = 0
) -> str:
    """Render a compact, model-readable summary of past lessons."""
    lines = [f"Past lessons for {target} (most recent first):"]
    for i, exp in enumerate(experiences, start=1):
        verdict = exp.verdict or "?"
        context = exp.context or "(no context)"
        head = f"  {i}. [{verdict}] {context}"
        if exp.patterns:
            head += f" — patterns: {', '.join(exp.patterns)}"
        lines.append(head)
        for blocker in (exp.blockers or [])[:3]:
            lines.append(f"     - {blocker}")
        if exp.fix_applied:
            lines.append(f"     fix: {exp.fix_applied}")
        if exp.references:
            refs = ", ".join(exp.references[:2])
            lines.append(f"     refs: {refs}")
    if faded_count > 0:
        lines.append(
            f"  +{faded_count} older lesson(s) faded from injection "
            f"(history kept on disk)"
        )
    lines.append("Apply these lessons proactively. Do not repeat the rejected patterns.")
    return "\n".join(lines)
