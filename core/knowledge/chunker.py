"""Markdown chunker — split documents into embeddable chunks.

Splits on paragraph boundaries, respects heading structure,
and maintains overlap for context continuity.
"""

import re
from dataclasses import dataclass


@dataclass
class Chunk:
    """A text chunk ready for embedding."""
    text: str
    heading: str = ""       # Current heading context
    index: int = 0          # Position in document
    source: str = ""        # Source file path

    @property
    def token_estimate(self) -> int:
        return len(self.text.split())


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

        block_tokens = len(block.split())

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
                sent_tokens = len(sentence.split())
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
                    current_tokens = len(current_text.split())
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
            current_tokens = len(current_text.split())

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

    return chunks
