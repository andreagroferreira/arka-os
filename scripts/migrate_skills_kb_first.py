"""Idempotent migration: inject/compact the KB-first prefix in SKILL.md.

Targets SKILL.md files in arka/ and departments/ that reference external
research tools (Context7, WebSearch, WebFetch, Firecrawl). Each file gets
a standard KB-first block prepended after its frontmatter or H1, wrapped
in HTML-comment delimiters so re-runs are no-ops.

PR-3 of the prompt-surface plan (2026-07-08): the block is now a 2-line
POINTER instead of the full ~90-word doctrine — the doctrine lives once
in arka/SKILL.md (orchestrator) and is enforced by the Stop-hook kb-cite
check; cloning it into ~200 skills cost tokens on every co-loaded skill
and drifted on every edit. Re-running this script REPLACES any old-form
block with the compact one (delimiters preserved so marketplace_export
keeps stripping it).
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

SCAN_ROOTS = [REPO_ROOT / "arka", REPO_ROOT / "departments"]
SKIP_ROOTS = [REPO_ROOT / "docs", REPO_ROOT / "config" / "cognition"]
# The orchestrator SKILL.md is the canonical HOME of the KB-first
# doctrine (the compact pointers reference it) — never inject/compact it.
EXCLUDE_FILES = {REPO_ROOT / "arka" / "SKILL.md"}

EXTERNAL_TOOL_RE = re.compile(
    r"mcp__context7|WebSearch|WebFetch|firecrawl",
    re.IGNORECASE,
)

BEGIN_DELIM = "<!-- arka:kb-first-prefix begin -->"
END_DELIM = "<!-- arka:kb-first-prefix end -->"

# No "(non-negotiable)" marker in the pointer: the normative force lives
# once in the canonical doctrine; repeating the marker ~200x is exactly
# the instruction-strength inflation the prompt-lint ratchet blocks.
PREFIX_BLOCK = f"""{BEGIN_DELIM}
> **KB-first:** query `mcp__obsidian__search_notes` (and
> `mcp__graphify__query_graph` when configured) and cite `[[wikilinks]]`
> or graph nodes — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
{END_DELIM}
"""

_BLOCK_RE = re.compile(
    re.escape(BEGIN_DELIM) + r".*?" + re.escape(END_DELIM) + r"\n?",
    re.DOTALL,
)


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
    return sorted(set(files) - EXCLUDE_FILES)


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

    if _already_migrated(text):
        new_text = _BLOCK_RE.sub(PREFIX_BLOCK, text, count=1)
        if new_text == text:
            return FileResult(path, "skipped-already-compact")
        return _write(path, new_text, "compacted")

    if not _references_external_tool(text):
        return FileResult(path, "skipped-no-external-ref")
    return _write(path, _inject(text), "migrated")


def _write(path: Path, text: str, status: str) -> FileResult:
    try:
        path.write_text(text, encoding="utf-8")
    except OSError as exc:
        return FileResult(path, "error", str(exc))
    return FileResult(path, status)


def run(dry_run: bool = False) -> list[FileResult]:
    files = _discover_skill_files()
    results: list[FileResult] = []
    for path in files:
        if dry_run:
            text = path.read_text(encoding="utf-8", errors="replace")
            if _already_migrated(text):
                if _BLOCK_RE.sub(PREFIX_BLOCK, text, count=1) == text:
                    results.append(FileResult(path, "skipped-already-compact"))
                else:
                    results.append(FileResult(path, "would-compact"))
            elif not _references_external_tool(text):
                results.append(FileResult(path, "skipped-no-external-ref"))
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
