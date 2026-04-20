"""Idempotent migration: inject KB-first prefix into SKILL.md files.

Targets SKILL.md files in arka/ and departments/ that reference external
research tools (Context7, WebSearch, WebFetch, Firecrawl). Each file gets
a standard KB-first block prepended after its frontmatter or H1, wrapped
in HTML-comment delimiters so re-runs are no-ops.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

SCAN_ROOTS = [REPO_ROOT / "arka", REPO_ROOT / "departments"]
SKIP_ROOTS = [REPO_ROOT / "docs", REPO_ROOT / "config" / "cognition"]

EXTERNAL_TOOL_RE = re.compile(
    r"mcp__context7|WebSearch|WebFetch|firecrawl",
    re.IGNORECASE,
)

BEGIN_DELIM = "<!-- arka:kb-first-prefix begin -->"
END_DELIM = "<!-- arka:kb-first-prefix end -->"

PREFIX_BLOCK = f"""{BEGIN_DELIM}
## KB-First Research (non-negotiable)

Before any external research (Context7, WebSearch, WebFetch, Firecrawl):

1. Call `mcp__obsidian__search_notes` on the query first.
2. Cite relevant hits with `[[wikilinks]]` or explicitly declare a KB gap.
3. Only after (1) and (2) may external tools run.

The Synapse L2.5 layer pre-injects top KB matches on every user prompt;
treat them as your default source. External research supplements, it
does not replace the vault.
{END_DELIM}
"""


@dataclass
class FileResult:
    path: Path
    status: str
    detail: str = ""


def _discover_skill_files() -> list[Path]:
    files: list[Path] = []
    for root in SCAN_ROOTS:
        if not root.exists():
            continue
        files.extend(root.rglob("SKILL.md"))
    return sorted(set(files))


def _references_external_tool(text: str) -> bool:
    return bool(EXTERNAL_TOOL_RE.search(text))


def _already_migrated(text: str) -> bool:
    return BEGIN_DELIM in text and END_DELIM in text


def _inject(text: str) -> str:
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            head = text[: end + len("\n---\n")]
            body = text[end + len("\n---\n") :]
            return head + "\n" + PREFIX_BLOCK + body
    h1_match = re.search(r"^# .+$", text, flags=re.MULTILINE)
    if h1_match:
        insertion = h1_match.end()
        return text[:insertion] + "\n\n" + PREFIX_BLOCK + text[insertion:]
    return PREFIX_BLOCK + "\n" + text


def _process_one(path: Path) -> FileResult:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return FileResult(path, "error", str(exc))

    if not _references_external_tool(text):
        return FileResult(path, "skipped-no-external-ref")
    if _already_migrated(text):
        return FileResult(path, "skipped-already-migrated")

    new_text = _inject(text)
    try:
        path.write_text(new_text, encoding="utf-8")
    except OSError as exc:
        return FileResult(path, "error", str(exc))
    return FileResult(path, "migrated")


def run(dry_run: bool = False) -> list[FileResult]:
    files = _discover_skill_files()
    results: list[FileResult] = []
    for path in files:
        if dry_run:
            text = path.read_text(encoding="utf-8", errors="replace")
            if not _references_external_tool(text):
                results.append(FileResult(path, "skipped-no-external-ref"))
            elif _already_migrated(text):
                results.append(FileResult(path, "skipped-already-migrated"))
            else:
                results.append(FileResult(path, "would-migrate"))
        else:
            results.append(_process_one(path))
    return results


def _summarise(results: list[FileResult]) -> None:
    counts: dict[str, int] = {}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1
    total = len(results)
    print(f"\nScanned {total} SKILL.md files.\n")
    for status, count in sorted(counts.items()):
        print(f"  {status:32s} {count}")
    errors = [r for r in results if r.status == "error"]
    if errors:
        print("\nErrors:")
        for r in errors:
            print(f"  {r.path}: {r.detail}")


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    results = run(dry_run=dry)
    _summarise(results)
