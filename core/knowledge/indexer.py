"""Knowledge indexer — walk directories and index markdown files.

Supports incremental indexing (skips already-indexed files by hash).
"""

import hashlib
from pathlib import Path
from typing import Callable, Optional

from core.knowledge.chunker import chunk_markdown
from core.knowledge.doctrine import (
    note_domains,
    parse_frontmatter,
    rebuild_vocabulary_from_sources,
    resolve_knowledge_class,
    save_vocabulary,
)
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
    write_vocabulary: bool = True,
) -> dict:
    """Index all markdown files in a directory.

    Args:
        directory: Root directory to scan.
        store: VectorStore to index into.
        pattern: Glob pattern for files.
        on_progress: Callback(current, total, filename).
        max_tokens: Max tokens per chunk.
        skip_indexed: Skip files already indexed (by hash).
        write_vocabulary: Persist the doctrine domain vocabulary sidecar
            (``~/.arkaos/doctrine-domains.json``) when doctrine notes were
            indexed. The sidecar feeds the L2.5 doctrine retrieval pass.

    Returns:
        Dict with: files_scanned, files_indexed, files_skipped,
        chunks_created, doctrine_notes.
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
    doctrine_count = 0

    for i, filepath in enumerate(files):
        if on_progress:
            on_progress(i + 1, total, filepath.name)

        fhash = file_hash(filepath)

        if skip_indexed and store.is_file_indexed(str(filepath), fhash):
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

        # Doctrine classification rides in every chunk's metadata so the
        # retrieval side can filter without path heuristics. relative_path
        # is POSIX-normalized: the same index must behave identically on
        # Windows, macOS and Linux.
        relative = filepath.relative_to(root)
        frontmatter = parse_frontmatter(content)
        kclass = resolve_knowledge_class(frontmatter, relative)
        domains = note_domains(frontmatter) if kclass == "doctrine" else []
        if kclass == "doctrine":
            doctrine_count += 1

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
                metadata={
                    "relative_path": relative.as_posix(),
                    "knowledge_class": kclass,
                    "domains": domains,
                },
            )
            chunks_created += count
            indexed += 1

    # The vocabulary is rebuilt from the WHOLE index, never from this
    # run's files: with skip_indexed=True an incremental run touches only
    # new/changed notes, and a per-run vocabulary would overwrite the
    # sidecar with that fragment — blinding the doctrine pass to the rest
    # of the corpus.
    if write_vocabulary:
        vocabulary = rebuild_vocabulary_from_sources(
            store.distinct_source_metadata()
        )
        if vocabulary:
            save_vocabulary(vocabulary)

    # The lexical index is a sidecar built FROM the chunks table, so it is
    # stale the moment anything is indexed. `lexical.search` ignores a
    # stale index, which fails safe but also silently turns the lexical
    # signal off — so rebuild it here instead of leaving it to be
    # remembered. Fail-open: no FTS5 or a build error leaves the vector
    # path exactly as it was.
    lexical_rebuilt = False
    if indexed:
        try:
            from core.knowledge import lexical
            lexical_rebuilt = lexical.build(store._db_path)[0]
        except Exception:
            lexical_rebuilt = False

    return {
        "files_scanned": total,
        "files_indexed": indexed,
        "files_skipped": skipped,
        "chunks_created": chunks_created,
        "doctrine_notes": doctrine_count,
        "lexical_rebuilt": lexical_rebuilt,
    }
