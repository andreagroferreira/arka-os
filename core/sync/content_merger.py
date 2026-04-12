"""Managed-region content merger for the ArkaOS Sync Engine.

Merges core-owned content into project files while preserving any
project-authored content outside the managed region. Uses HTML comment
markers to delimit the managed block.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Literal

_START_RE = re.compile(
    r"<!--\s*arkaos:managed:start(?:\s+version=(?P<version>\S+))?"
    r"(?:\s+hash=(?P<hash>[0-9a-f]{12}))?\s*-->",
)
_END_RE = re.compile(r"<!--\s*arkaos:managed:end\s*-->")


@dataclass
class MergeResult:
    """Outcome of a managed-region merge operation."""

    status: Literal["updated", "unchanged", "error"]
    new_text: str
    error: str | None = None


def compute_managed_hash(content: str) -> str:
    """Return the first 12 hex chars of sha256 over managed content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]


def merge_managed_content(
    target_text: str, managed_content: str, version: str
) -> MergeResult:
    """Merge managed_content into target_text inside the managed region.

    Returns status "updated" when the file changes, "unchanged" when the
    new hash matches the existing one, or "error" when markers are
    unbalanced.
    """
    starts = list(_START_RE.finditer(target_text))
    ends = list(_END_RE.finditer(target_text))

    if len(starts) != len(ends):
        return MergeResult(
            status="error",
            new_text=target_text,
            error=f"unbalanced markers: {len(starts)} starts, {len(ends)} ends",
        )

    if len(starts) > 1:
        return MergeResult(
            status="error",
            new_text=target_text,
            error="multiple managed blocks are not supported",
        )

    new_hash = compute_managed_hash(managed_content)
    new_block = _render_block(managed_content, version, new_hash)

    if not starts:
        return _prepend_block(target_text, new_block)

    start_match = starts[0]
    end_match = ends[0]
    if end_match.start() < start_match.end():
        return MergeResult(
            status="error",
            new_text=target_text,
            error="end marker appears before start marker",
        )

    existing_hash = start_match.group("hash")
    if existing_hash == new_hash:
        return MergeResult(status="unchanged", new_text=target_text)

    new_text = (
        target_text[: start_match.start()]
        + new_block
        + target_text[end_match.end() :]
    )
    return MergeResult(status="updated", new_text=new_text)


def _render_block(content: str, version: str, content_hash: str) -> str:
    return (
        f"<!-- arkaos:managed:start version={version} hash={content_hash} -->\n"
        f"{content}\n"
        "<!-- arkaos:managed:end -->"
    )


def _prepend_block(target_text: str, new_block: str) -> MergeResult:
    separator = "\n\n" if target_text else "\n"
    new_text = f"{new_block}{separator}{target_text}" if target_text else f"{new_block}\n"
    return MergeResult(status="updated", new_text=new_text)
