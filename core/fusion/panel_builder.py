"""Build a fusion panel from what the machine can actually run.

Fusion needs a diverse panel + a judge. The user's ``models.yaml`` may
have an explicit ``fusion.panel`` (configured via ``/arka-fusion``); when
it is empty, this builds a sensible default from discovered models so
``npx arkaos fusion "question"`` does something out of the box instead of
failing with FusionUnavailable.

Diversity is the point (OpenRouter's result: a diverse panel beats a
single model): pair the runtime model with up to two large, distinct
local Ollama models. The judge stays the configured frontier model.
"""

from __future__ import annotations

from core.runtime.model_router import ModelsConfig, RoleChoice, load_config


def default_panel(
    config: ModelsConfig | None = None,
) -> tuple[list[RoleChoice], RoleChoice]:
    """Return (panel, judge). Respects an explicit panel; else builds one.

    An empty return panel means the machine offers nothing to fuse (no
    local models and no explicit config) — the caller reports that rather
    than fanning out to a single seat.
    """
    if config is None:
        config, _ = load_config()
    judge = config.fusion.judge
    if config.fusion.panel:
        return list(config.fusion.panel), judge

    panel: list[RoleChoice] = [
        RoleChoice(provider="runtime", model="default", effort="high"),
    ]
    try:
        from core.runtime.ollama_discovery import discover
        status = discover()
    except Exception:
        status = None
    if status and status.running:
        # Panel-grade locals: >= 4GB, or cloud-proxied (size 0). Sort by
        # size desc so the strongest come first; take two distinct ones.
        candidates = sorted(
            (m for m in status.models if m.size_gb >= 4 or m.size_gb == 0),
            key=lambda m: m.size_gb,
            reverse=True,
        )
        for m in candidates[:2]:
            panel.append(RoleChoice(provider="ollama", model=m.name, effort="high"))
    return panel, judge


def describe_panel(panel: list[RoleChoice], judge: RoleChoice) -> str:
    """Human summary of a panel for CLI output."""
    seats = ", ".join(f"{c.provider}/{c.model}" for c in panel)
    return f"judge {judge.provider}/{judge.model} | panel: {seats}"
