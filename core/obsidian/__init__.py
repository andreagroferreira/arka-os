"""Obsidian vault integration — write workflow outputs to knowledge base."""

from core.obsidian.writer import ObsidianWriter
from core.obsidian.templates import build_frontmatter

__all__ = ["ObsidianWriter", "build_frontmatter"]
