"""Inter-agent checkpoint primitives (PR15 v2.37.0).

Implements the `inter-agent-checkpoints` NON-NEGOTIABLE rule from PR10:
long-running multi-agent dispatches are fragmented into sub-dispatches
of 2-3min each, and the orchestrator emits a proactive checkpoint
prompt between each sub-dispatch announcing the next step and inviting
user context injection.

This module ships PRIMITIVES — message builders, an injection parser,
and a planner that splits a task list into checkpoint-sized chunks.
The actual orchestration (calling Agent tools in sequence, pausing
between them) is a pattern the orchestrator follows, not code this
module runs.

Conclave Phase 5 brainstorm (2026-05-13) decided:
  * Live interruption capability — user can add context mid-task
  * Proactive checkpoint prompts between sub-dispatches
  * Sub-dispatch budget: 2-3 minutes each
  * Reviewer conflicts: strategic -> escalate, technical -> Marta decides
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Literal

# Recommended sub-dispatch duration window (seconds).
SUB_DISPATCH_MIN_S = 60
SUB_DISPATCH_TARGET_S = 180  # 3 min sweet spot
SUB_DISPATCH_MAX_S = 300     # 5 min hard ceiling

# Threshold above which a task MUST be checkpointed.
CHECKPOINT_TRIGGER_S = 30

# Recognised user-injection cues (added context, not new turn / abort).
_INJECTION_CUES: tuple[re.Pattern, ...] = tuple(
    re.compile(p, re.IGNORECASE) for p in [
        r"\b(adiciona|considera tamb[eé]m|esquecia(-me)?|antes de|t[eê]m que|ainda|t[aâ]mbem)\b",
        r"\b(also|btw|by the way|forgot to mention|one more thing|consider also)\b",
        r"^[+]\s",            # leading + prefix common shorthand for "add"
        r"^\s*FYI[:\s]",
    ]
)

# Recognised abort / hard-stop cues (user wants to stop or redirect).
_ABORT_CUES: tuple[re.Pattern, ...] = tuple(
    re.compile(p, re.IGNORECASE) for p in [
        r"\b(stop|para|parar|abort|cancela|cancel|n[aã]o continues|wait)\b",
        r"\b(redirect|muda|altera|change direction)\b",
    ]
)

InjectionKind = Literal["new-turn", "context-injection", "abort"]


@dataclass
class CheckpointPlan:
    """A fragmented multi-step work plan."""

    task_name: str
    sub_dispatches: list[str] = field(default_factory=list)
    estimated_total_seconds: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class UserInjection:
    """Parsed verdict on a mid-checkpoint user message."""

    kind: InjectionKind
    matched_cues: list[str] = field(default_factory=list)
    raw_text: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def build_checkpoint_message(
    next_dispatch_name: str,
    estimated_seconds: int,
    step: int,
    total_steps: int,
    context_carried_forward: str = "",
) -> str:
    """Return the canonical [arka:checkpoint] message string.

    Format::

        [arka:checkpoint] Step S/T: next dispatch "<name>" — ~Xs.
        Tens contexto a acrescentar antes de eu arrancar? (Silêncio = procedo.)
    """
    s = max(1, int(step))
    t = max(s, int(total_steps))
    name = next_dispatch_name.strip() or "next sub-task"
    seconds = max(0, int(estimated_seconds))
    body = (
        f"[arka:checkpoint] Step {s}/{t}: next dispatch \"{name}\" — ~{seconds}s.\n"
        "Tens contexto a acrescentar antes de eu arrancar? (Silêncio = procedo.)"
    )
    if context_carried_forward:
        body += f"\n  (Carry-forward: {context_carried_forward.strip()})"
    return body


def parse_user_injection(text: str) -> UserInjection:
    """Classify a user message arriving between checkpoints.

    Returns an :class:`UserInjection` with kind in:
      * ``"abort"``              — user wants to stop or redirect
      * ``"context-injection"``  — user adds context to the current plan
      * ``"new-turn"``           — anything else (treat as fresh request)

    Abort detection wins over injection (cue order: abort first).
    """
    stripped = (text or "").strip()
    if not stripped:
        return UserInjection(kind="new-turn", raw_text=stripped)

    abort_hits = [p.pattern for p in _ABORT_CUES if p.search(stripped)]
    if abort_hits:
        return UserInjection(
            kind="abort", matched_cues=abort_hits, raw_text=stripped
        )

    injection_hits = [p.pattern for p in _INJECTION_CUES if p.search(stripped)]
    if injection_hits:
        return UserInjection(
            kind="context-injection",
            matched_cues=injection_hits,
            raw_text=stripped,
        )
    return UserInjection(kind="new-turn", raw_text=stripped)


def plan_fragmented_dispatches(
    task_name: str, sub_tasks: list[str], per_task_seconds: int = SUB_DISPATCH_TARGET_S
) -> CheckpointPlan:
    """Build a CheckpointPlan from a list of sub-task names.

    Each sub-task is one dispatch separated by a checkpoint prompt.
    Caller is responsible for executing the sub-dispatches in order.
    """
    cleaned: list[str] = [s.strip() for s in sub_tasks if s and s.strip()]
    per = max(SUB_DISPATCH_MIN_S, min(int(per_task_seconds), SUB_DISPATCH_MAX_S))
    return CheckpointPlan(
        task_name=task_name.strip() or "unnamed-task",
        sub_dispatches=cleaned,
        estimated_total_seconds=len(cleaned) * per,
    )


def should_checkpoint(estimated_seconds: int) -> bool:
    """Return True if the work is long enough to require a checkpoint."""
    return int(estimated_seconds) > CHECKPOINT_TRIGGER_S
