"""Governance engine — Constitution, quality gates, audit trails."""

from core.governance.constitution import Constitution, load_constitution
from core.governance.kb_cite_check import CitationResult, check_citation

__all__ = [
    "CitationResult",
    "Constitution",
    "check_citation",
    "load_constitution",
]
