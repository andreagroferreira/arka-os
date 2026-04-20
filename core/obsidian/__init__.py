"""Obsidian vault integration — write, catalog, and relate workflow outputs."""

from core.obsidian.cataloger import CatalogPlan, classify, confidence, execute, plan
from core.obsidian.relator import (
    RelatedNote,
    ensure_tags,
    find_related,
    generate_wikilinks_block,
    update_back_references,
    update_mocs,
)
from core.obsidian.taxonomy import TAXONOMY, NoteType, TaxonomyEntry
from core.obsidian.templates import build_frontmatter
from core.obsidian.writer import ObsidianWriter

__all__ = [
    "CatalogPlan",
    "NoteType",
    "ObsidianWriter",
    "RelatedNote",
    "TAXONOMY",
    "TaxonomyEntry",
    "build_frontmatter",
    "classify",
    "confidence",
    "ensure_tags",
    "execute",
    "find_related",
    "generate_wikilinks_block",
    "plan",
    "update_back_references",
    "update_mocs",
]
