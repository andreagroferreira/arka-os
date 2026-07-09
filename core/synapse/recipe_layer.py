"""Synapse layer L7.6 — validated Recipe injection (Interaction Reform PR8).

Sibling of L7.5 (Pattern Library): where a PatternCard is a short text
hint, a Recipe points at QG-approved reference files on disk that can be
adapted. When the prompt's keywords overlap a captured recipe, this
layer surfaces the top matches as `[recipes:N]` so the orchestrator
starts from "we have a validated build of this" — the `/arka refine` →
build loop reuses proven work instead of re-deriving it.

Keyword extraction is shared with L7.5 (imported, not duplicated).
Matching is keyword-overlap on the recipe's feature_keywords + stack for
v1; semantic ranking is a follow-up.
"""

from __future__ import annotations

import time

from core.knowledge.recipes import Recipe, list_recipes
from core.synapse.layers import Layer, LayerResult, PromptContext
from core.synapse.pattern_library_layer import extract_keywords


class RecipeLayer(Layer):
    """L7.6 — surface validated recipes matching the user prompt."""

    def __init__(self, limit: int = 3) -> None:
        self._limit = limit

    @property
    def id(self) -> str:
        return "L7.6"

    @property
    def name(self) -> str:
        return "Recipes"

    @property
    def input_sensitive(self) -> bool:
        return True

    @property
    def cache_ttl(self) -> int:
        return 60

    @property
    def priority(self) -> int:
        # 76 — right after L7.5 Pattern Library (75), before L8 Forge (80),
        # so both prior-art sources reach Forge's plan synthesis.
        return 76

    def compute(self, ctx: PromptContext) -> LayerResult:
        start = time.time()
        keywords = extract_keywords(ctx.user_input)
        if not keywords:
            return self._empty(start)
        matches = _match_recipes(keywords, self._limit)
        if not matches:
            return self._empty(start, tag="[recipes:none]")
        content = format_recipes(matches)
        return LayerResult(
            layer_id=self.id,
            tag=f"[recipes:{len(matches)}]",
            content=content,
            tokens_est=max(1, len(content) // 4),
            compute_ms=int((time.time() - start) * 1000),
            cached=False,
        )

    def _empty(self, start: float, tag: str = "") -> LayerResult:
        return LayerResult(
            layer_id=self.id,
            tag=tag,
            content="",
            tokens_est=0,
            compute_ms=int((time.time() - start) * 1000),
            cached=False,
        )


def _match_recipes(keywords: list[str], limit: int) -> list[Recipe]:
    """Rank recipes by keyword overlap with feature_keywords + stack."""
    kw = set(keywords)
    scored: list[tuple[int, Recipe]] = []
    for recipe in list_recipes():
        haystack = {
            w.lower()
            for w in (recipe.feature_keywords + recipe.stack)
        }
        overlap = len(kw & haystack)
        if overlap:
            scored.append((overlap, recipe))
    scored.sort(key=lambda pair: (-pair[0], pair[1].slug))
    return [recipe for _, recipe in scored[:limit]]


def format_recipes(recipes: list[Recipe]) -> str:
    """Compact, model-readable summary pointing at the on-disk files."""
    lines = [
        "Validated recipes found (QG-approved prior builds — read "
        "RECIPE.md + files/ and adapt via the normal flow, never "
        "copy-paste blind):"
    ]
    for i, r in enumerate(recipes, start=1):
        head = f"  {i}. {r.name} (~/.arkaos/recipes/{r.slug}/)"
        if r.stack:
            head += f" — stack: {', '.join(r.stack[:4])}"
        lines.append(head)
        lines.append(f"     {r.problem}")
        if r.files:
            lines.append(f"     files/: {', '.join(r.files[:4])}")
        if r.apply_notes:
            lines.append(f"     adapt: {r.apply_notes}")
    return "\n".join(lines)
