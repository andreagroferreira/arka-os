"""ObsidianWriter — persists KnowledgeEntry objects as Obsidian markdown notes."""

import re
from pathlib import Path

from core.cognition.memory.schemas import KnowledgeEntry


CATEGORY_FOLDERS = {
    "pattern": "Patterns",
    "anti_pattern": "Anti-Patterns",
    "solution": "Solutions",
    "architecture": "Architecture",
    "config": "Config",
    "lesson": "Lessons",
    "improvement": "Improvements",
}


def _slugify(title: str, max_len: int = 80) -> str:
    """Convert title to a safe filename slug."""
    slug = title.lower()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s]+", "-", slug.strip())
    slug = re.sub(r"-+", "-", slug)
    return slug[:max_len].rstrip("-")


def _format_frontmatter(entry: KnowledgeEntry) -> str:
    """Build YAML frontmatter string from a KnowledgeEntry."""
    tags_inline = "[" + ", ".join(entry.tags) + "]"
    stacks_inline = "[" + ", ".join(entry.stacks) + "]"
    created = entry.created_at.isoformat()
    updated = entry.updated_at.isoformat()

    lines = [
        "---",
        f"title: {entry.title}",
        f"id: {entry.id}",
        f"category: {entry.category}",
        f"tags: {tags_inline}",
        f"stacks: {stacks_inline}",
        f"source_project: {entry.source_project}",
        f"applicable_to: {entry.applicable_to}",
        f"confidence: {entry.confidence}",
        f"times_used: {entry.times_used}",
        f"created_at: {created}",
        f"updated_at: {updated}",
        "---",
    ]
    return "\n".join(lines)


class ObsidianWriter:
    """Writes KnowledgeEntry objects as Obsidian-compatible markdown notes."""

    def __init__(self, vault_base_path: str) -> None:
        self._vault = Path(vault_base_path)

    def write(self, entry: KnowledgeEntry) -> str:
        """Persist a KnowledgeEntry as a markdown note. Returns the file path."""
        folder_name = CATEGORY_FOLDERS.get(entry.category, "Knowledge")
        folder = self._vault / folder_name
        folder.mkdir(parents=True, exist_ok=True)

        slug = _slugify(entry.title)
        file_path = folder / f"{slug}.md"

        frontmatter = _format_frontmatter(entry)
        note = f"{frontmatter}\n\n{entry.content}\n"

        file_path.write_text(note, encoding="utf-8")
        return str(file_path)
