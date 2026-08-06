"""Markdown chunker — split documents into embeddable chunks.

Splits on paragraph boundaries, respects heading structure,
and maintains overlap for context continuity.

Token accounting is REAL, not estimated, whenever the embedding stack is
present: the previous implementation counted whitespace words and called
them tokens (``len(block.split())``), but the measured token/word factor
on a live vault is 1.87 median and 2.63 at p90 — so with the default
``max_tokens=512``, 69.5% of produced chunks exceeded the 512-token hard
limit of every fastembed-served model and 38.2% of the corpus was
silently truncated at embed time. No error, no log, no metric. When
fastembed is unavailable the word estimate remains as the fallback —
harmless there, because without fastembed nothing gets embedded and
retrieval is keyword-only anyway.
"""

import re
from dataclasses import dataclass
from typing import Callable, Optional

# Lazy singleton token counter. IMPORTANT: this loads its OWN
# TextEmbedding instance rather than sharing the embedder's — calling
# ``no_truncation()`` on the tokenizer of the instance that also embeds
# breaks its ``embed()`` (the ONNX session receives irregular sequences).
# Measured trap, not a guess. Chunking only happens at index time, so the
# extra model load never touches the per-prompt Synapse budget.
_TOKEN_COUNTER: Optional[Callable[[str], int]] = None
_TOKEN_COUNTER_FAILED = False


def _token_counter() -> Optional[Callable[[str], int]]:
    """A real token counter from the active embed model, or None."""
    global _TOKEN_COUNTER, _TOKEN_COUNTER_FAILED
    if _TOKEN_COUNTER is not None or _TOKEN_COUNTER_FAILED:
        return _TOKEN_COUNTER
    try:
        from fastembed import TextEmbedding

        from core.knowledge.embedder import get_model_name

        tokenizer = TextEmbedding(get_model_name()).model.tokenizer
        tokenizer.no_truncation()
        tokenizer.no_padding()
        _TOKEN_COUNTER = lambda text: len(tokenizer.encode(text).ids)  # noqa: E731
    except Exception:
        _TOKEN_COUNTER_FAILED = True
    return _TOKEN_COUNTER


def _count_tokens(text: str) -> int:
    counter = _token_counter()
    if counter is not None:
        try:
            return counter(text)
        except Exception:
            pass
    return len(text.split())


@dataclass
class Chunk:
    """A text chunk ready for embedding."""
    text: str
    heading: str = ""       # Current heading context
    index: int = 0          # Position in document
    source: str = ""        # Source file path

    @property
    def token_estimate(self) -> int:
        return _count_tokens(self.text)


def chunk_markdown(
    content: str,
    max_tokens: int = 512,
    overlap_tokens: int = 50,
    source: str = "",
) -> list[Chunk]:
    """Split markdown content into chunks at paragraph boundaries.

    Args:
        content: Markdown text to chunk.
        max_tokens: Maximum tokens per chunk.
        overlap_tokens: Token overlap between consecutive chunks.
        source: Source file path for metadata.

    Returns:
        List of Chunk objects.
    """
    # Strip frontmatter
    body = content
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            body = content[end + 3:].strip()

    # Split into paragraphs (double newline) preserving headings
    blocks = re.split(r'\n\n+', body)
    blocks = [b.strip() for b in blocks if b.strip()]

    chunks: list[Chunk] = []
    current_heading = ""
    current_text = ""
    current_tokens = 0

    for block in blocks:
        # Track headings
        heading_match = re.match(r'^(#{1,6})\s+(.+)', block)
        if heading_match:
            current_heading = heading_match.group(2)

        block_tokens = _count_tokens(block)

        # If single block exceeds max, split it
        if block_tokens > max_tokens:
            if current_text:
                chunks.append(Chunk(
                    text=current_text.strip(),
                    heading=current_heading,
                    index=len(chunks),
                    source=source,
                ))
                current_text = ""
                current_tokens = 0

            # Split large block by sentences
            sentences = re.split(r'(?<=[.!?])\s+', block)
            for sentence in sentences:
                sent_tokens = _count_tokens(sentence)
                if current_tokens + sent_tokens > max_tokens and current_text:
                    chunks.append(Chunk(
                        text=current_text.strip(),
                        heading=current_heading,
                        index=len(chunks),
                        source=source,
                    ))
                    # Overlap: keep last few words
                    words = current_text.split()
                    current_text = " ".join(words[-overlap_tokens:]) + " " if len(words) > overlap_tokens else ""
                    current_tokens = _count_tokens(current_text)
                current_text += sentence + " "
                current_tokens += sent_tokens
            continue

        # Check if adding this block exceeds limit
        if current_tokens + block_tokens > max_tokens and current_text:
            chunks.append(Chunk(
                text=current_text.strip(),
                heading=current_heading,
                index=len(chunks),
                source=source,
            ))
            # Overlap
            words = current_text.split()
            current_text = " ".join(words[-overlap_tokens:]) + " " if len(words) > overlap_tokens else ""
            current_tokens = _count_tokens(current_text)

        current_text += block + "\n\n"
        current_tokens += block_tokens

    # Final chunk
    if current_text.strip():
        chunks.append(Chunk(
            text=current_text.strip(),
            heading=current_heading,
            index=len(chunks),
            source=source,
        ))

    return _enforce_token_invariant(chunks, max_tokens)


def _enforce_token_invariant(chunks: list[Chunk], max_tokens: int) -> list[Chunk]:
    """No chunk above ``max_tokens`` REAL tokens leaves the chunker.

    Two ways a chunk can still be oversized after accumulation: a single
    sentence that alone exceeds the budget (tables, JSON blobs, URLs —
    the sentence splitter cannot cut those), and joins whose merged text
    tokenizes to more than the sum of its parts. Both used to pass
    through silently and get truncated by the embedding model. Oversized
    chunks are split by character windows proportional to the overshoot
    — blunt, but bounded and loud in the data rather than lossy.

    With no real tokenizer available this is a no-op in practice (word
    counts are what the accumulator already enforced), which is fine:
    without fastembed nothing embeds, so nothing truncates.
    """
    final: list[Chunk] = []
    for chunk in chunks:
        # Pieces are RE-VERIFIED and re-split until they fit: a single
        # character-window pass left slightly-over pieces on token-dense
        # text (measured on a live corpus: 17 chunks at 513-522 tokens,
        # all diff/code-heavy notes). Windows shrink on every round, so
        # this terminates.
        pending: list[str] = [chunk.text]
        while pending:
            text = pending.pop(0)
            n = _count_tokens(text)
            if n <= max_tokens:
                final.append(Chunk(
                    text=text, heading=chunk.heading,
                    index=0, source=chunk.source,
                ))
                continue
            parts = max(2, (n // max_tokens) + 1)
            step = max(1, len(text) // parts)
            pieces = [
                text[i:i + step].strip()
                for i in range(0, len(text), step)
            ]
            pending = [p for p in pieces if p] + pending
    for i, chunk in enumerate(final):
        chunk.index = i
    return final


# Minimum contiguous token run treated as a real overlap. The chunker seeds
# each chunk with the previous chunk's last ``overlap_tokens`` words (default
# 50), so genuine seams are tens of tokens long. Requiring >= 5 avoids
# stripping on a 1-2 word coincidence (e.g. both chunks ending/starting "the").
_MIN_OVERLAP_TOKENS = 5


def _overlap_token_count(prev: list[str], cur: list[str], window: int) -> int:
    """Return length of the longest suffix of ``prev`` that prefixes ``cur``.

    Compares whitespace tokens (never mid-word). Searches the largest possible
    overlap first within ``window`` and returns the first match, so the result
    is the true chunker overlap window rather than a short coincidence. Returns
    0 when no run of at least ``_MIN_OVERLAP_TOKENS`` tokens matches.
    """
    max_len = min(len(prev), len(cur), window)
    for length in range(max_len, _MIN_OVERLAP_TOKENS - 1, -1):
        if prev[-length:] == cur[:length]:
            return length
    return 0


def stitch_chunks(texts: list[str], max_overlap_tokens: int = 200) -> str:
    """Re-join overlapping chunks into a clean transcript, deduping seams.

    ``chunk_markdown`` prepends each chunk with a token-overlap window copied
    from the previous chunk. Naively joining the chunks therefore repeats that
    window at every boundary. This detects the actual overlap per adjacent pair
    (longest suffix-of-prev == prefix-of-cur, on token boundaries, capped at
    ``max_overlap_tokens``) and strips it from the later chunk before joining
    with blank lines. No overlap detected -> plain join, so content is never
    lost. Single chunk returns as-is; empty list returns "".
    """
    parts = [t for t in texts if t]
    if not parts:
        return ""
    result = [parts[0]]
    for cur in parts[1:]:
        prev_tokens = result[-1].split()
        cur_tokens = cur.split()
        overlap = _overlap_token_count(prev_tokens, cur_tokens, max_overlap_tokens)
        result.append(" ".join(cur_tokens[overlap:]) if overlap else cur)
    return "\n\n".join(p for p in result if p)
