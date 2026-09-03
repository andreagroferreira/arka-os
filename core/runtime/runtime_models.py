"""Known models per runtime, for the Model Fabric UI + advisor.

The Model Fabric ``runtime`` provider shells out to the active CLI. This
module lists the concrete models that CLI accepts, with human labels and
tier, so the dashboard dropdown and ``/arka-fusion`` can offer real
choices (Fable 5.1, Opus 5, Sonnet 5) instead of only the abstract
best/default/fast aliases. Haiku is deliberately absent: the weakest
lane ArkaOS routes to is Sonnet 5 (operator decision, Runtime Sync 2026-09-03).

Model IDs verified against the Claude Code changelog 2.1.257 (2026-09-01)
and the model-config reference (2026-09). This is
the single place they are hand-listed — update HERE when the runtime
ships new models; the dashboard and CLI read from this module. Codex /
Gemini / Cursor models are left empty on purpose: we do not hardcode
another vendor's catalogue, and the UI falls back to a free-text field
so the user types the exact id their runtime accepts.
"""

from __future__ import annotations

# Claude Code accepts the short aliases opus/sonnet/haiku and full model
# IDs. `value` is what gets written to models.yaml as the role's model.
CLAUDE_CODE_MODELS: list[dict[str, str]] = [
    {"value": "claude-fable-5-1", "label": "Fable 5.1", "tier": "frontier",
     "note": "most capable — 1M context, cache reads $0.25/MTok"},
    {"value": "opus", "label": "Opus 5", "tier": "frontier",
     "note": "frontier"},
    {"value": "sonnet", "label": "Sonnet 5", "tier": "balanced",
     "note": "balanced speed/quality — also the mechanical lane"},
]

_MODELS_BY_RUNTIME: dict[str, list[dict[str, str]]] = {
    "claude-code": CLAUDE_CODE_MODELS,
    # codex / gemini / cursor intentionally omitted — free-text in the UI.
}


def models_for_runtime(runtime_id: str) -> list[dict[str, str]]:
    """Return the known runtime models for the given runtime id."""
    return _MODELS_BY_RUNTIME.get(runtime_id, [])


def detect_runtime_models() -> tuple[str, list[dict[str, str]]]:
    """Best-effort (runtime_id, models) for the active runtime."""
    try:
        from core.runtime.registry import detect_runtime
        runtime_id = detect_runtime()
    except Exception:
        runtime_id = "claude-code"
    return runtime_id, models_for_runtime(runtime_id)
