#!/usr/bin/env python3
"""Knowledge Indexer — index markdown files into vector store.

Usage:
    python scripts/knowledge-index.py --vault /path/to/vault
    python scripts/knowledge-index.py --dir departments/ --db /tmp/test.db
    python scripts/knowledge-index.py --force
    python scripts/knowledge-index.py --stats
    python scripts/knowledge-index.py --search "security vulnerability"

With no --vault/--dir the vault is resolved in order: ``knowledge.vaultPath``
/ ``ARKAOS_VAULT`` (canonical), then the deprecated ``knowledge/
obsidian-config.json``, then the deprecated ``~/.arkaos/profile.json``. Each
source announces itself on stderr. If none answers, the run exits 2 rather
than indexing some other corpus.
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Windows consoles default to cp1252; progress lines with non-ASCII vault
# names would raise UnicodeEncodeError and kill the index run silently.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ARKAOS_ROOT = Path(os.environ.get("ARKAOS_ROOT", Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(ARKAOS_ROOT))

DEFAULT_DB = Path.home() / ".arkaos" / "knowledge.db"


def _note(message: str) -> None:
    """Diagnostics go to stderr unconditionally.

    Never gated on --json: stdout is the JSON channel, stderr is not, so
    suppressing these under --json only ever hid which corpus was chosen
    from the operator most likely to be automating against it.
    """
    print(message, file=sys.stderr)


_DEPRECATION = (
    "  DEPRECATED source — set `knowledge.vaultPath` in "
    "~/.arkaos/config.json; this file will stop being consulted."
)


def _legacy_obsidian_config() -> str:
    """``knowledge/obsidian-config.json``. May hold a ``${VAULT_PATH}``
    template, resolved through the canonical path resolver."""
    config_path = ARKAOS_ROOT / "knowledge" / "obsidian-config.json"
    if not config_path.exists():
        return ""
    try:
        vault = json.loads(config_path.read_text(encoding="utf-8")).get("vault_path", "")
    except (json.JSONDecodeError, OSError):
        return ""
    if vault and "${" in vault:
        try:
            from core.runtime.path_resolver import resolve

            vault = resolve(vault)
        except Exception:
            vault = ""
    return vault if vault and Path(vault).exists() else ""


def _legacy_profile_vault() -> str:
    """``~/.arkaos/profile.json::vaultPath``, written by `npx arkaos install`."""
    profile_path = Path.home() / ".arkaos" / "profile.json"
    if not profile_path.exists():
        return ""
    try:
        vault = json.loads(profile_path.read_text(encoding="utf-8")).get("vaultPath", "")
    except (json.JSONDecodeError, OSError):
        return ""
    return vault if vault and Path(vault).exists() else ""


def resolve_index_directory() -> str:
    """The vault to index, or '' — canonical configuration first.

    The order changed and the change is the point. ``knowledge.vaultPath``,
    resolved by :mod:`core.knowledge.vault` (the same resolver
    ``research_gate`` uses, so the gate and the indexer cannot disagree),
    used to be consulted THIRD — behind two legacy files. An operator who
    set the documented key could still be indexed from a stale legacy
    value and never be told. Now the documented key wins, and the legacy
    files still work but announce that they are deprecated.
    """
    from core.knowledge.vault import resolve_vault_with_source

    configured, source = resolve_vault_with_source()
    if configured:
        # The source is reported by the resolver, not assumed here: it
        # answers from the config file OR from ARKAOS_VAULT, and naming
        # the wrong one is the exact ambiguity these lines exist to end.
        _note(f"Vault from {source}: {configured}")
        return str(configured)

    legacy = _legacy_obsidian_config()
    if legacy:
        _note(f"Vault from knowledge/obsidian-config.json: {legacy}")
        _note(_DEPRECATION)
        return legacy

    legacy = _legacy_profile_vault()
    if legacy:
        _note(f"Vault from ~/.arkaos/profile.json: {legacy}")
        _note(_DEPRECATION)
        return legacy

    return ""


def clear_index(store, db_path: Path) -> None:
    """Wipe the chunk index AND the lexical sidecar built from it.

    The sidecar is a separate file, so clearing only the chunk table
    leaves the wiped corpus sitting on disk in readable form.
    ``lexical.search`` would reject it as stale rather than serve it, so
    this is hygiene rather than a correctness fix — but "cleared" should
    mean cleared. Fail-open: an install without the lexical module has no
    sidecar to remove.
    """
    store.clear()
    try:
        from core.knowledge import lexical

        lexical.index_path(db_path).unlink(missing_ok=True)
    except Exception:
        pass


def main() -> int:
    parser = argparse.ArgumentParser(description="ArkaOS Knowledge Indexer")
    parser.add_argument("--vault", type=str, help="Obsidian vault path to index")
    parser.add_argument("--dir", type=str, help="Directory to index")
    parser.add_argument("--db", type=str, default=str(DEFAULT_DB), help="Vector DB path")
    parser.add_argument("--search", type=str, help="Search query")
    parser.add_argument("--stats", action="store_true", help="Show DB statistics")
    parser.add_argument("--clear", action="store_true", help="Clear all indexed data")
    parser.add_argument(
        "--force",
        "--reindex",
        action="store_true",
        dest="force",
        help=(
            "Wipe the index and rebuild it from scratch in one invocation "
            "(--clear + reindex). Use after a chunker, embedder or doctrine "
            "rule change, where incremental indexing would keep serving "
            "chunks produced by the old rules."
        ),
    )
    parser.add_argument("--json", action="store_true", dest="json_output", help="JSON output")
    args = parser.parse_args()

    from core.knowledge.vector_store import VectorStore

    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    store = VectorStore(db_path)

    if args.clear:
        clear_index(store, db_path)
        print("Knowledge base cleared." if not args.json_output else json.dumps({"cleared": True}))
        return 0

    if args.stats:
        stats = store.get_stats()
        if args.json_output:
            print(json.dumps(stats, indent=2))
        else:
            print(f"Chunks:     {stats['total_chunks']}")
            print(f"Files:      {stats['total_files']}")
            print(f"Retrieval:  {stats.get('retrieval_mode', 'unknown')}")
            vec = "enabled" if stats.get("vec_available") else "disabled (keyword fallback)"
            print(f"Vec:        {vec}")
            print(f"DB:         {stats['db_path']}")
        return 0

    if args.search:
        results = store.search(args.search, top_k=5)
        if args.json_output:
            print(json.dumps(results, indent=2))
        else:
            if not results:
                print("No results found.")
            for i, r in enumerate(results, 1):
                src = Path(r.get("source", "")).name if r.get("source") else "unknown"
                # RAG honesty: degraded keyword matches have NO similarity
                # score — never print one.
                if r.get("score") is None:
                    print(f"\n[{i}] Match: keyword-degraded (no similarity) | {src}")
                else:
                    print(f"\n[{i}] Score: {r['score']:.3f} | {src}")
                if r.get("heading"):
                    print(f"    Heading: {r['heading']}")
                print(f"    {r['text'][:200]}...")
        return 0

    # Index mode
    directory = args.vault or args.dir or resolve_index_directory()

    if not directory:
        # No guessed corpus. Indexing ArkaOS's own departments/ tree as if
        # it were the operator's knowledge base and exiting 0 is exactly
        # the silent substitution core/knowledge/vault.py exists to end:
        # the run looks successful and the KB answers from the wrong body
        # of text. Say what is missing and fail.
        print(
            "No vault configured. Set `knowledge.vaultPath` in "
            "~/.arkaos/config.json (or export ARKAOS_VAULT), or pass "
            "--vault <path> / --dir <path>.",
            file=sys.stderr,
        )
        return 2

    if not Path(directory).exists():
        print(f"Directory not found: {directory}", file=sys.stderr)
        return 2

    from core.knowledge.indexer import index_directory

    def progress(current, total, name):
        if not args.json_output:
            print(f"\r  [{current}/{total}] {name[:50]}...", end="", flush=True)

    if args.force:
        # Two independent guarantees, deliberately both: the wipe makes this
        # a --clear + rebuild in one invocation, and skip_indexed=False below
        # means the rebuild does not depend on the wipe having emptied the
        # hash table. Either alone would reindex today; keeping both means a
        # future change to clear() cannot quietly turn --force into a no-op.
        # index_directory then rebuilds both sidecars off the fresh chunks:
        # the doctrine vocabulary and the lexical FTS5 index.
        clear_index(store, db_path)
        if not args.json_output:
            print("Index cleared — rebuilding from scratch.", file=sys.stderr)

    print(f"Indexing: {directory}" if not args.json_output else "", file=sys.stderr)
    result = index_directory(
        directory, store, on_progress=progress, skip_indexed=not args.force
    )

    if not args.json_output:
        print()  # newline after progress
        print(f"\nFiles scanned:  {result['files_scanned']}")
        print(f"Files indexed:  {result['files_indexed']}")
        print(f"Files skipped:  {result['files_skipped']}")
        print(f"Chunks created: {result['chunks_created']}")
        # The two sidecars report themselves: a rebuild that silently failed
        # to refresh them looks identical to one that worked without this.
        print(f"Doctrine notes: {result.get('doctrine_notes', 0)}")
        print(f"Lexical index:  {'rebuilt' if result.get('lexical_rebuilt') else 'not rebuilt'}")
    else:
        print(json.dumps(result, indent=2))

    store.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
