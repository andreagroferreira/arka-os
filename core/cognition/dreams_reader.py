"""Read Dreaming v2 insights from the Obsidian vault.

Surface used by the ``/arka dreams`` skill. Parses the plugin-compat
frontmatter shape written by ``core.cognition.dreaming`` and groups
results by date so the CLI can show today, since-N-days, or all.

Read-only; never modifies vault content.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path


@dataclass
class StoredInsight:
    """An insight surfaced by Dreaming v2 and parsed back from disk."""

    path: Path
    date: str  # YYYY-MM-DD
    title: str
    confidence: str
    sources: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    body: str = ""


_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)", re.DOTALL)


def list_insights(dreams_dir: Path, since_days: int = 1) -> list[StoredInsight]:
    """List insights from *dreams_dir* whose date is within *since_days*.

    ``since_days=1`` is "today only" (UTC-day boundary, generous tolerance
    of one calendar day so a late-night dream surfaced after midnight
    still counts). ``since_days=7`` returns last week, etc.
    """
    dreams_dir = Path(dreams_dir)
    if not dreams_dir.is_dir():
        return []
    cutoff = datetime.now(timezone.utc).date() - timedelta(days=max(since_days - 1, 0))
    out: list[StoredInsight] = []
    for md in sorted(dreams_dir.glob("*.md"), reverse=True):
        try:
            text = md.read_text(encoding="utf-8")
        except OSError:
            continue
        insight = parse_insight(md, text)
        if insight is None:
            continue
        try:
            insight_date = datetime.strptime(insight.date, "%Y-%m-%d").date()
        except ValueError:
            continue
        if insight_date >= cutoff:
            out.append(insight)
    return out


def parse_insight(path: Path, text: str) -> StoredInsight | None:
    """Parse one Dreaming v2 markdown file into a StoredInsight."""
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return None
    fm_block, body = match.group(1), match.group(2)
    fm = _parse_frontmatter(fm_block)
    if fm.get("type") != "arkaos-insight":
        return None
    title = _extract_h1(body) or path.stem
    return StoredInsight(
        path=path,
        date=str(fm.get("date", "")),
        title=title,
        confidence=str(fm.get("confidence", "medium")),
        sources=_parse_list(fm.get("sources")),
        tags=_parse_list(fm.get("tags")),
        body=_extract_body(body),
    )


def _parse_frontmatter(block: str) -> dict:
    """Tiny YAML-ish parser. Frontmatter shape is constrained by Dreaming v2
    output (`core/cognition/dreaming.py:_render_markdown`) so a full YAML
    dependency is not warranted here.
    """
    out: dict[str, object] = {}
    current_key: str | None = None
    current_list: list[str] = []
    for raw_line in block.splitlines():
        if not raw_line.strip():
            continue
        if raw_line.startswith("  - "):
            current_list.append(raw_line[4:].strip())
            continue
        if current_key is not None and current_list:
            out[current_key] = list(current_list)
            current_list = []
        current_key = None
        if ":" not in raw_line:
            continue
        key, _, value = raw_line.partition(":")
        key = key.strip()
        value = value.strip()
        if value == "":
            current_key = key
            continue
        out[key] = value
    if current_key is not None and current_list:
        out[current_key] = list(current_list)
    return out


def _parse_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value]
    if isinstance(value, str) and value:
        return [value]
    return []


def _extract_h1(body: str) -> str | None:
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None


def _extract_body(body: str) -> str:
    """Return the prose under '## What I noticed' if present, else the body."""
    marker = "## What I noticed"
    idx = body.find(marker)
    if idx < 0:
        return body.strip()
    after = body[idx + len(marker):]
    next_section = after.find("\n## ")
    if next_section < 0:
        return after.strip()
    return after[:next_section].strip()
