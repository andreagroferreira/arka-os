"""Synapse L5.5 — routing feedback injection (F1-B2).

CLOSES the second learning loop: the F1-B1 aggregator turned QG/judge
verdicts into ``~/.arkaos/routing-scores.json``; this layer reads it at
prompt time and warns when the detected department has a poor recent
approval record, citing exact counts (evidence-flow: numbers the
orchestrator can verify, never vibes):

    [arka:redo-risk] frontend: 3/9 approved (90d, smoothed 0.36).
    Top blockers: function-length, missing-tests. Dispatch the
    specialist early; require evidence before the QG.

Silence rules (honesty over noise):
    - fewer than ``_MIN_SAMPLES`` QG verdicts → SILENT (no warnings
      from statistical noise)
    - smoothed approval >= ``_RISK_THRESHOLD`` → silent (no praise
      spam; the layer only warns)
    - no department detected in the prompt → silent

Flag: ``synapse.l55RoutingFeedback`` (default ON) + env ``ARKA_BYPASS_L55``.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from core.synapse.layers import Layer, LayerResult, PromptContext

_MIN_SAMPLES = 5
_RISK_THRESHOLD = 0.5
_CONFIG_PATH = Path.home() / ".arkaos" / "config.json"


def _l55_feature_flag_on() -> bool:
    if os.environ.get("ARKA_BYPASS_L55", "").strip() == "1":
        return False
    try:
        data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return True
    if not isinstance(data, dict):
        return True  # malformed-but-valid JSON (list/str) => documented default ON
    synapse_cfg = data.get("synapse") or {}
    return bool(synapse_cfg.get("l55RoutingFeedback", True))


def _detect_department(ctx: PromptContext) -> str:
    """Reuse L1's keyword detection — one source of routing truth."""
    try:
        from core.synapse.layers import DepartmentLayer

        result = DepartmentLayer().compute(ctx)
        # L1 tags as [dept:<slug>] — extract the slug.
        tag = result.tag or ""
        if tag.startswith("[dept:") and tag.endswith("]"):
            return tag[len("[dept:"):-1]
    except Exception:  # detection is best-effort
        pass
    return ""


class RoutingFeedbackLayer(Layer):
    """L5.5: cite the department's recent QG record when it warns."""

    @property
    def id(self) -> str:
        return "L5.5"

    @property
    def name(self) -> str:
        return "RoutingFeedback"

    @property
    def cache_ttl(self) -> int:
        return 300  # scores rebuild at most hourly — 5 min cache is safe

    @property
    def input_sensitive(self) -> bool:
        return True  # department detection depends on the prompt

    @property
    def priority(self) -> int:
        return 55  # after L5 CommandHints (50), before L6 QualityGate (60)

    def compute(self, ctx: PromptContext) -> LayerResult:
        start = time.time()
        content = ""
        try:
            if ctx.user_input and _l55_feature_flag_on():
                content = self._warn_if_risky(ctx)
        except Exception:  # layer must never break the prompt
            content = ""
        elapsed = int((time.time() - start) * 1000)
        if not content:
            return LayerResult(layer_id=self.id, tag="", content="",
                               tokens_est=0, compute_ms=elapsed, cached=False)
        return LayerResult(
            layer_id=self.id,
            tag=content,
            content=content,
            tokens_est=len(content.split()),
            compute_ms=elapsed,
            cached=False,
        )

    def _warn_if_risky(self, ctx: PromptContext) -> str:
        department = _detect_department(ctx)
        if not department:
            return ""
        from core.governance.routing_feedback import load_scores

        scores = load_scores()
        if scores is None:
            return ""
        score = next(
            (s for s in scores.scores if s.department == department), None
        )
        if score is None or score.samples < _MIN_SAMPLES:
            return ""  # silence below the sample floor — noise is not signal
        if score.smoothed_approval >= _RISK_THRESHOLD:
            return ""
        blockers = ", ".join(score.top_blocker_patterns) or "n/a"
        return (
            f"[arka:redo-risk] {department}: {score.approvals}/{score.samples}"
            f" approved ({scores.window_days}d,"
            f" smoothed {score.smoothed_approval:.2f})."
            f" Top blockers: {blockers}."
            f" Dispatch the specialist early; require evidence before the QG."
        )
