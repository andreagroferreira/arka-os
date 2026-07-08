#!/usr/bin/env python3
"""Knowledge Indexer — index markdown files into vector store.

Usage:
    python scripts/knowledge-index.py --vault ~/Documents/Personal
    python scripts/knowledge-index.py --dir departments/ --db /tmp/test.db
    python scripts/knowledge-index.py --stats
    python scripts/knowledge-index.py --search "security vulnerability"
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


def main() -> int:
    parser = argparse.ArgumentParser(description="ArkaOS Knowledge Indexer")
    parser.add_argument("--vault", type=str, help="Obsidian vault path to index")
    parser.add_argument("--dir", type=str, help="Directory to index")
    parser.add_argument("--db", type=str, default=str(DEFAULT_DB), help="Vector DB path")
    parser.add_argument("--search", type=str, help="Search query")
    parser.add_argument("--stats", action="store_true", help="Show DB statistics")
    parser.add_argument("--clear", action="store_true", help="Clear all indexed data")
    parser.add_argument("--json", action="store_true", dest="json_output", help="JSON output")
    args = parser.parse_args()

    from core.knowledge.vector_store import VectorStore

    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    store = VectorStore(db_path)

    if args.clear:
        store.clear()
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
            print(f"Vec:        {'enabled' if stats.get('vec_available') else 'disabled (keyword fallback)'}")
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
    directory = args.vault or args.dir
    if not directory:
        # Auto-detect vault from config. vault_path may be a template like
        # "${VAULT_PATH}" — resolve it through the canonical path resolver
        # (ARKAOS_VAULT_PATH env / profile.json vaultPath) before testing.
        config_path = ARKAOS_ROOT / "knowledge" / "obsidian-config.json"
        if config_path.exists():
            config = json.loads(config_path.read_text(encoding="utf-8"))
            vault = config.get("vault_path", "")
            if vault and "${" in vault:
                try:
                    from core.runtime.path_resolver import resolve

                    vault = resolve(vault)
                except Exception:
                    vault = ""
            if vault and Path(vault).exists():
                directory = vault
                if not args.json_output:
                    print(f"Vault from config: {directory}", file=sys.stderr)

    if not directory:
        # profile.json vaultPath — set by `npx arkaos install` and the
        # authoritative answer to "where is the user's vault".
        profile_path = Path.home() / ".arkaos" / "profile.json"
        if profile_path.exists():
            try:
                vault = json.loads(
                    profile_path.read_text(encoding="utf-8")
                ).get("vaultPath", "")
            except (json.JSONDecodeError, OSError):
                vault = ""
            if vault and Path(vault).exists():
                directory = vault
                if not args.json_output:
                    print(f"Vault from profile: {directory}", file=sys.stderr)

    if not directory:
        # Try common vault locations
        common_vaults = [
            Path.home() / "Documents" / "Personal",
            Path.home() / "Documents" / "Obsidian",
            Path.home() / "Obsidian",
            Path.home() / "vault",
        ]
        for vault_path in common_vaults:
            if vault_path.exists() and (vault_path / ".obsidian").exists():
                directory = str(vault_path)
                print(f"Auto-detected vault: {directory}" if not args.json_output else "", file=sys.stderr)
                break

    if not directory:
        # Fall back to indexing ArkaOS departments (always available)
        departments_dir = ARKAOS_ROOT / "departments"
        if departments_dir.exists():
            directory = str(departments_dir)
            print(f"No vault found. Indexing ArkaOS skills: {directory}" if not args.json_output else "", file=sys.stderr)

    if not directory:
        print("No directory specified. Use --vault <path> or --dir <path>.", file=sys.stderr)
        return 2

    if not Path(directory).exists():
        print(f"Directory not found: {directory}", file=sys.stderr)
        return 2

    from core.knowledge.indexer import index_directory

    def progress(current, total, name):
        if not args.json_output:
            print(f"\r  [{current}/{total}] {name[:50]}...", end="", flush=True)

    print(f"Indexing: {directory}" if not args.json_output else "", file=sys.stderr)
    result = index_directory(directory, store, on_progress=progress)

    if not args.json_output:
        print()  # newline after progress
        print(f"\nFiles scanned:  {result['files_scanned']}")
        print(f"Files indexed:  {result['files_indexed']}")
        print(f"Files skipped:  {result['files_skipped']}")
        print(f"Chunks created: {result['chunks_created']}")
    else:
        print(json.dumps(result, indent=2))

    store.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
