"""Synapse layer L7.5 — Pattern Library injection.

When the user's prompt has substantive keywords overlapping a recorded
`PatternCard`, this layer surfaces the top-3 matching cards as context
so the orchestrator (and the dispatched specialists) start from the
"we have already built this" prior art rather than reinventing.

Matching is keyword-substring + tag overlap for v1. Semantic similarity
via vector embeddings lands in v3.75.x.

PR4 of the Squad Intelligence Upgrade.
"""

from __future__ import annotations

import re
import time

from core.knowledge.pattern_cards import PatternCard, query_patterns
from core.synapse.layers import Layer, LayerResult, PromptContext


# Cheap keyword extractor — letter-led runs of ≥4 chars, lowercased,
# stopword-filtered. The character class includes Latin-1 Supplement
# (À-ÿ, U+00C0–U+00FF) so pt-PT input like "autenticação", "paginação",
# "implementação" is captured whole instead of truncated at the
# accented character. Latin Extended-A (U+0100+) is intentionally
# excluded — extend the class when adding CS/PL/HU/TR corpora
# (š, ý, ě, ą, ł, ő, ı, etc.). Vector-DB embedder lands in v3.75.x.
_WORD_RE = re.compile(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9_-]{3,}")

_STOPWORDS: frozenset[str] = frozenset({
    # EN
    "this", "that", "with", "from", "into", "have", "want", "need",
    "should", "would", "could", "make", "made", "thing", "things",
    "there", "their", "about", "what", "when", "where", "which",
    "while", "also", "just", "like",
    # PT
    "para", "como", "isto", "esta", "este", "isso", "essa", "esse",
    "depois", "antes", "pode", "deve", "muito", "pelo", "pela",
    "desde", "ainda", "assim", "porque", "mais", "menos", "sobre",
})


def _extract_keywords(text: str, max_n: int = 10) -> list[str]:
    """Return the first `max_n` distinct meaningful words from `text`."""
    seen: list[str] = []
    seen_set: set[str] = set()
    for word in _WORD_RE.findall(text or ""):
        low = word.lower()
        if low in _STOPWORDS or low in seen_set:
            continue
        seen.append(low)
        seen_set.add(low)
        if len(seen) >= max_n:
            break
    return seen


class PatternLibraryLayer(Layer):
    """L7.5 — surface prior implementations matching the user prompt."""

    def __init__(self, limit: int = 3) -> None:
        self._limit = limit

    @property
    def id(self) -> str:
        return "L7.5"

    @property
    def name(self) -> str:
        return "PatternLibrary"

    @property
    def input_sensitive(self) -> bool:
        return True

    @property
    def cache_ttl(self) -> int:
        return 60

    @property
    def priority(self) -> int:
        # 75 — runs after L7 Time (70) and BEFORE L8 ForgeContext (80) so
        # the prior-art context is available to Forge's plan synthesis.
        return 75

    def compute(self, ctx: PromptContext) -> LayerResult:
        start = time.time()
        keywords = _extract_keywords(ctx.user_input)
        if not keywords:
            return self._empty_result(start)

        cards = query_patterns(keywords=keywords, limit=self._limit)
        if not cards:
            return self._empty_result(start, tag="[patterns:none]")

        content = format_patterns(cards)
        ms = int((time.time() - start) * 1000)
        return LayerResult(
            layer_id=self.id,
            tag=f"[patterns:{len(cards)}]",
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


def format_patterns(cards: list[PatternCard]) -> str:
    """Render a compact, model-readable summary of prior implementations."""
    lines = [
        "Prior implementations found in the Pattern Library "
        "(consult before designing — reuse or document divergence):"
    ]
    for i, c in enumerate(cards, start=1):
        head = f"  {i}. {c.name} ({c.id})"
        if c.stack:
            head += f" — stack: {', '.join(c.stack[:4])}"
        lines.append(head)
        if c.description:
            lines.append(f"     {c.description}")
        if c.files:
            lines.append(f"     files: {', '.join(c.files[:3])}")
        if c.acceptance_criteria:
            lines.append(
                f"     AC: {'; '.join(c.acceptance_criteria[:2])}"
            )
        if c.references:
            lines.append(f"     refs: {', '.join(c.references[:2])}")
    return "\n".join(lines)
