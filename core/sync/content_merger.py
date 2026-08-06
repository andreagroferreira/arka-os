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

    status: Literal["updated", "restamped", "drifted", "unchanged", "error"]
    new_text: str
    error: str | None = None


def compute_managed_hash(content: str) -> str:
    """Return the first 12 hex chars of sha256 over managed content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]


def merge_managed_content(
    target_text: str, managed_content: str, version: str
) -> MergeResult:
    """Merge managed_content into target_text inside the managed region.

    Returns "updated" when the managed content itself changes, "restamped"
    when the verified-current content carries a stale stamp, "drifted" when
    the block was edited in place (nothing is written), "unchanged" when
    everything already matches, or "error" when markers are malformed.
    """
    starts = list(_START_RE.finditer(target_text))
    ends = list(_END_RE.finditer(target_text))

    malformed = _validate_markers(starts, ends, target_text)
    if malformed is not None:
        return malformed

    new_hash = compute_managed_hash(managed_content)
    new_block = _render_block(managed_content, version, new_hash)

    if not starts:
        return _prepend_block(target_text, new_block)

    start_match, end_match = starts[0], ends[0]
    rewritten = (
        target_text[: start_match.start()]
        + new_block
        + target_text[end_match.end() :]
    )

    body = target_text[start_match.end() : end_match.start()].strip()
    return _decide(
        stamped_hash=start_match.group("hash"),
        stamped_version=start_match.group("version"),
        body=body,
        new_hash=new_hash,
        version=version,
        target_text=target_text,
        rewritten=rewritten,
    )


def _decide(
    *,
    stamped_hash: str | None,
    stamped_version: str | None,
    body: str,
    new_hash: str,
    version: str,
    target_text: str,
    rewritten: str,
) -> MergeResult:
    """Choose the outcome for a well-formed block."""
    if stamped_hash != new_hash:
        return MergeResult(status="updated", new_text=rewritten)
    # The stamp says the content matches canonical — but the stamp is a
    # claim, not a measurement. Hash what is ACTUALLY between the markers
    # before rewriting: an operator who edited inside the block leaves the
    # stamp untouched, and a rewrite would delete their work to correct a
    # version number.
    if compute_managed_hash(body) != new_hash:
        return MergeResult(
            status="drifted",
            new_text=target_text,
            error="managed block was edited in place; left untouched",
        )
    if stamped_version == version:
        return MergeResult(status="unchanged", new_text=target_text)
    # Content verified current; only the stamp lags. Rewriting it keeps
    # `version=` an honest record of the last sync that verified this file.
    return MergeResult(status="restamped", new_text=rewritten)


def _validate_markers(
    starts: list[re.Match[str]],
    ends: list[re.Match[str]],
    target_text: str,
) -> MergeResult | None:
    """Return an error MergeResult when the marker pair is malformed."""
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
    if starts and ends[0].start() < starts[0].end():
        return MergeResult(
            status="error",
            new_text=target_text,
            error="end marker appears before start marker",
        )
    return None


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
