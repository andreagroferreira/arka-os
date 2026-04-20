"""Taxonomy — canonical mapping from NoteType to vault path, tags, and MOCs.

Central source of truth for how the Cataloger routes knowledge into the
vault. Tests assert every NoteType has an entry, every path is relative,
and template vars declared in `required_vars` match the `path_template`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class NoteType(str, Enum):
    CODE_PATTERN = "code_pattern"
    PERSONA = "persona"
    CLIENT_STRATEGY = "client_strategy"
    MARKETING_TEST = "marketing_test"
    ARCHITECTURE_DECISION = "architecture_decision"
    RESEARCH_FINDING = "research_finding"
    FRAMEWORK = "framework"
    SESSION_LEARNING = "session_learning"


@dataclass(frozen=True)
class TaxonomyEntry:
    path_template: str
    required_vars: tuple[str, ...] = ()
    default_tags: tuple[str, ...] = ()
    mocs: tuple[str, ...] = ()
    inline_moc: str | None = None


TAXONOMY: dict[NoteType, TaxonomyEntry] = {
    NoteType.CODE_PATTERN: TaxonomyEntry(
        path_template="🧠 Knowledge Base/{stack} Patterns/{title}.md",
        required_vars=("stack", "title"),
        default_tags=("code", "pattern"),
        mocs=("Topics MOC.md",),
    ),
    NoteType.PERSONA: TaxonomyEntry(
        path_template="Personas/{name}/{title}.md",
        required_vars=("name", "title"),
        default_tags=("persona",),
        mocs=("Personas MOC.md",),
    ),
    NoteType.CLIENT_STRATEGY: TaxonomyEntry(
        path_template="Projects/{client}/Strategies/{title}.md",
        required_vars=("client", "title"),
        default_tags=("strategy",),
        mocs=("Projects MOC.md",),
    ),
    NoteType.MARKETING_TEST: TaxonomyEntry(
        path_template="Projects/{client}/Campaigns/{campaign}/Tests/{title}.md",
        required_vars=("client", "campaign", "title"),
        default_tags=("marketing", "test"),
        mocs=("Projects MOC.md",),
    ),
    NoteType.ARCHITECTURE_DECISION: TaxonomyEntry(
        path_template="Projects/ArkaOS/ADRs/{number}-{slug}.md",
        required_vars=("number", "slug"),
        default_tags=("adr", "architecture"),
        mocs=("Projects MOC.md",),
        inline_moc="Projects/ArkaOS/ArkaOS v2 Architecture Decisions.md",
    ),
    NoteType.RESEARCH_FINDING: TaxonomyEntry(
        path_template="🧠 Knowledge Base/Research/{topic}/{title}.md",
        required_vars=("topic", "title"),
        default_tags=("research",),
        mocs=("Sources MOC.md", "Topics MOC.md"),
    ),
    NoteType.FRAMEWORK: TaxonomyEntry(
        path_template="Topics/{framework}/{title}.md",
        required_vars=("framework", "title"),
        default_tags=("framework",),
        mocs=("Topics MOC.md",),
    ),
    NoteType.SESSION_LEARNING: TaxonomyEntry(
        path_template="🧠 Knowledge Base/Sessions/{date}/{title}.md",
        required_vars=("date", "title"),
        default_tags=("learning", "session"),
        mocs=("WizardingCode MOC.md",),
    ),
}


_VAR_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def extract_template_vars(path_template: str) -> set[str]:
    return set(_VAR_RE.findall(path_template))


def get_entry(note_type: NoteType) -> TaxonomyEntry:
    return TAXONOMY[note_type]


def missing_vars(entry: TaxonomyEntry, provided: dict[str, str]) -> list[str]:
    return [v for v in entry.required_vars if not provided.get(v)]
