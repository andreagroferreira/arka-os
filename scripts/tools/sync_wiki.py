#!/usr/bin/env python3
"""Sync wiki/ -> GitHub Wiki format.

The in-repo `wiki/` is the single source of truth. The GitHub Wiki is flat
(no subdirectories) and references pages by name without the .md extension.
This transformer flattens `wiki/04-Departments/*` into prefixed page names,
rewrites every internal link, turns `../docs/` links into absolute repository
URLs, and generates a `_Sidebar.md` navigation from the page set so the sidebar
itself stays in sync. It writes the result to an output directory that a CI job
pushes to the `<repo>.wiki` Git remote.

Links inside fenced or inline code are left untouched. Link titles
(`[x](y.md "title")`) and one level of balanced parentheses in targets are
handled.

Usage:
    python scripts/tools/sync_wiki.py --out /tmp/wiki-out
    python scripts/tools/sync_wiki.py --out /tmp/wiki-out --repo https://github.com/o/n --branch master
"""
from __future__ import annotations

import argparse
import os.path
import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_REPO = "https://github.com/andreagroferreira/arka-os"
_DEFAULT_BRANCH = "master"
# Target group allows one level of balanced parentheses, e.g. Foo_(bar).
_LINK_RE = re.compile(r"\[([^\]]+)\]\(((?:[^()]|\([^()]*\))*)\)")
_TITLE_RE = re.compile(r'^(\S+)(\s+"[^"]*"|\s+\'[^\']*\')?$')
_CODE_RE = re.compile(r"```.*?```|~~~.*?~~~|`[^`\n]+`", re.DOTALL)
_SENTINEL = "\x00CODE{}\x00"


def page_name(rel_path: str) -> str:
    """Map a wiki-relative .md path to a flat GitHub Wiki page name.

    Home.md -> Home; 01-Getting-Started.md -> 01-Getting-Started;
    04-Departments/README.md -> 04-Departments;
    04-Departments/dev.md -> 04-Departments-dev.
    """
    p = rel_path[:-3] if rel_path.endswith(".md") else rel_path
    parts = p.split("/")
    if parts[-1] == "README":
        parts = parts[:-1]
    return "-".join(parts)


def _mask_code(text: str) -> tuple[str, list[str]]:
    """Replace fenced/inline code spans with sentinels so links inside are safe."""
    spans: list[str] = []

    def stash(m: re.Match[str]) -> str:
        spans.append(m.group(0))
        return _SENTINEL.format(len(spans) - 1)

    return _CODE_RE.sub(stash, text), spans


def _unmask_code(text: str, spans: list[str]) -> str:
    """Restore code spans masked by _mask_code."""
    for i, span in enumerate(spans):
        text = text.replace(_SENTINEL.format(i), span)
    return text


def _resolve(base: str, source_rel: str, name_map: dict[str, str],
             repo: str, branch: str) -> str:
    """Resolve a bare target (no title) to a GitHub Wiki page or absolute URL."""
    src_dir = str(Path(source_rel).parent)
    joined = base if src_dir in ("", ".") else f"{src_dir}/{base}"
    norm = os.path.normpath(joined).replace("\\", "/") if base else base
    if base.endswith("/"):
        readme = f"{norm}/README.md"
        if readme in name_map:
            return name_map[readme]
    if norm in name_map:
        return name_map[norm]
    if base.startswith("../"):
        return f"{repo}/blob/{branch}/{norm.lstrip('./')}"
    return base


def _rewrite_target(target: str, source_rel: str, name_map: dict[str, str],
                    repo: str, branch: str) -> str:
    """Rewrite one link target, preserving any trailing title and anchor."""
    if "://" in target or target.startswith(("#", "mailto:")):
        return target
    m = _TITLE_RE.match(target)
    url, title = (m.group(1), m.group(2) or "") if m else (target, "")
    base, _, anchor = url.partition("#")
    anchor = f"#{anchor}" if anchor else ""
    resolved = _resolve(base, source_rel, name_map, repo, branch)
    return f"{resolved}{anchor}{title}"


def rewrite_links(content: str, source_rel: str, name_map: dict[str, str],
                  repo: str = _DEFAULT_REPO, branch: str = _DEFAULT_BRANCH) -> str:
    """Rewrite every markdown link, leaving code spans untouched."""
    masked, spans = _mask_code(content)

    def repl(m: re.Match[str]) -> str:
        text, target = m.group(1), m.group(2).strip()
        return f"[{text}]({_rewrite_target(target, source_rel, name_map, repo, branch)})"

    return _unmask_code(_LINK_RE.sub(repl, masked), spans)


def _build_sidebar(name_map: dict[str, str]) -> str:
    """Generate a _Sidebar.md navigation from the page set (kept in sync)."""
    # top-level pages plus subdirectory index pages (e.g. 04-Departments)
    roots = sorted(n for rel, n in name_map.items()
                   if "/" not in rel or rel.endswith("/README.md"))
    depts = sorted(n for rel, n in name_map.items()
                   if rel.startswith("04-Departments/") and not rel.endswith("README.md"))
    lines = ["## ArkaOS Wiki", ""]
    lines += [f"- [[{n}]]" for n in roots]
    if depts:
        lines += ["", "### Departments", ""]
        lines += [f"- [[{n}]]" for n in depts]
    return "\n".join(lines) + "\n"


def build_wiki(src_dir: Path, out_dir: Path, repo: str = _DEFAULT_REPO,
               branch: str = _DEFAULT_BRANCH) -> int:
    """Transform all of src_dir into flat GitHub Wiki pages in out_dir.

    Also writes a generated `_Sidebar.md`. Returns the number of content
    pages written (excluding the sidebar).
    """
    md_files = sorted(str(p.relative_to(src_dir)) for p in src_dir.rglob("*.md"))
    name_map = {rel: page_name(rel) for rel in md_files}
    out_dir.mkdir(parents=True, exist_ok=True)
    for rel in md_files:
        content = (src_dir / rel).read_text(encoding="utf-8")
        rewritten = rewrite_links(content, rel, name_map, repo, branch)
        (out_dir / f"{name_map[rel]}.md").write_text(rewritten, encoding="utf-8")
    (out_dir / "_Sidebar.md").write_text(_build_sidebar(name_map), encoding="utf-8")
    return len(md_files)


def main() -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(description="Sync wiki/ to GitHub Wiki format")
    parser.add_argument("--src", default=str(_REPO_ROOT / "wiki"), help="Source wiki dir")
    parser.add_argument("--out", required=True, help="Output dir for flat wiki pages")
    parser.add_argument("--repo", default=_DEFAULT_REPO, help="Repo URL for absolute links")
    parser.add_argument("--branch", default=_DEFAULT_BRANCH, help="Default branch for absolute links")
    args = parser.parse_args()
    src = Path(args.src)
    if not src.is_dir():
        print(f"Error: source '{src}' is not a directory", file=sys.stderr)
        return 2
    n = build_wiki(src, Path(args.out), args.repo, args.branch)
    print(f"Wrote {n} wiki pages (+ _Sidebar.md) to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
