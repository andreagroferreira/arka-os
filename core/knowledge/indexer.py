"""Knowledge indexer — walk directories and index markdown files.

Supports incremental indexing (skips already-indexed files by hash).
"""

import hashlib
from pathlib import Path
from typing import Callable, Optional

from core.knowledge.chunker import chunk_markdown
from core.knowledge.vector_store import VectorStore


def file_hash(path: Path) -> str:
    """Compute SHA-256 hash of file content."""
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def index_directory(
    directory: str | Path,
    store: VectorStore,
    pattern: str = "**/*.md",
    on_progress: Optional[Callable[[int, int, str], None]] = None,
    max_tokens: int = 512,
    skip_indexed: bool = True,
) -> dict:
    """Index all markdown files in a directory.

    Args:
        directory: Root directory to scan.
        store: VectorStore to index into.
        pattern: Glob pattern for files.
        on_progress: Callback(current, total, filename).
        max_tokens: Max tokens per chunk.
        skip_indexed: Skip files already indexed (by hash).

    Returns:
        Dict with: files_scanned, files_indexed, files_skipped, chunks_created.
    """
    root = Path(directory)
    if not root.exists():
        return {"files_scanned": 0, "files_indexed": 0, "files_skipped": 0, "chunks_created": 0}

    files = sorted(root.glob(pattern))
    # Skip hidden dirs (.obsidian, .git)
    files = [f for f in files if not any(part.startswith(".") for part in f.relative_to(root).parts)]

    total = len(files)
    indexed = 0
    skipped = 0
    chunks_created = 0

    for i, filepath in enumerate(files):
        if on_progress:
            on_progress(i + 1, total, filepath.name)

        fhash = file_hash(filepath)

        if skip_indexed and store.is_file_indexed(fhash):
            skipped += 1
            continue

        try:
            content = filepath.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            skipped += 1
            continue

        # Skip very small files
        if len(content.split()) < 20:
            skipped += 1
            continue

        # Remove old chunks for this file (re-index)
        store.remove_file(str(filepath))

        # Chunk and index
        chunks = chunk_markdown(content, max_tokens=max_tokens, source=str(filepath))
        if chunks:
            texts = [c.text for c in chunks]
            headings = [c.heading for c in chunks]
            count = store.index_chunks(
                texts=texts,
                headings=headings,
                source=str(filepath),
                file_hash=fhash,
                metadata={"relative_path": str(filepath.relative_to(root))},
            )
            chunks_created += count
            indexed += 1

    return {
        "files_scanned": total,
        "files_indexed": indexed,
        "files_skipped": skipped,
        "chunks_created": chunks_created,
    }
