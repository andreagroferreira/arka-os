"""Named feature-block merger for ecosystem skill files.

An ecosystem ``SKILL.md`` carries several ArkaOS-owned sections at once, so
the single-region algorithm in :mod:`core.sync.content_merger` does not
apply. Here each feature owns its own delimited block, stamped with the
sync version and a content hash, and is rewritten from the canonical
registry on every sync. Everything outside those blocks belongs to the
project and is never touched.

Sections written before the stamped-marker format exist in the wild as
*legacy* sections — a bare ``## <section_title>`` heading, sometimes with a
project-specific suffix such as ``(NON-NEGOTIABLE)``. A legacy section is
adopted into a managed block only when its text already matches the
canonical body once surrounding whitespace is trimmed. When it diverges,
the project has customised it, and this module refuses to overwrite: the
divergence is reported for review instead (the Terraform
``plan``-before-``apply`` contract). This is what stops an "always align"
sync from silently deleting the operator's work.

Markers are validated before any splice. A file whose markers are
unbalanced, duplicated or inverted yields ``malformed_markers`` and is left
exactly as it is — guessing at the pairing is what turns a repair into a
deletion.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from core.sync.content_merger import compute_managed_hash
from core.sync.schema import FeatureSpec

FeatureStatus = Literal[
    "updated",
    "restamped",
    "unchanged",
    "adopted",
    "injected",
    "removed",
    "pending_adoption",
    "pending_removal",
    "malformed_markers",
]

_WRITE_STATUSES: frozenset[str] = frozenset(
    {"updated", "restamped", "adopted", "injected", "removed"}
)


@dataclass
class FeatureMergeResult:
    """Outcome of merging one feature into one skill file."""

    feature: str
    status: FeatureStatus
    new_text: str
    canonical_body: str = ""
    legacy_body: str = ""
    error: str | None = None

    @property
    def wrote(self) -> bool:
        """True when new_text differs from the input and should be persisted."""
        return self.status in _WRITE_STATUSES


@dataclass
class SkillMergeReport:
    """Aggregated result of merging every feature into one skill file."""

    skill_name: str
    new_text: str
    results: list[FeatureMergeResult] = field(default_factory=list)

    def by_status(self, *statuses: str) -> list[str]:
        """Feature names whose status is one of ``statuses``."""
        return [r.feature for r in self.results if r.status in statuses]

    @property
    def changed(self) -> bool:
        return any(r.wrote for r in self.results)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def canonical_body(feature: FeatureSpec) -> str:
    """Return the feature content with any legacy marker lines stripped."""
    lines = [
        line
        for line in feature.content.splitlines()
        if not _MARKER_LINE_RE.match(line.strip())
    ]
    return "\n".join(lines).strip()


def merge_feature(text: str, feature: FeatureSpec, version: str) -> FeatureMergeResult:
    """Merge one feature into ``text``, honouring project customisation."""
    body = canonical_body(feature)
    lookup = _find_block(text, feature.name)
    if lookup.error is not None:
        return _malformed(text, feature, body, lookup.error)

    if feature.deprecated_in is not None:
        return _remove_feature(text, feature, body, lookup)

    if lookup.pair is not None:
        return _merge_existing_block(text, feature, body, version, lookup.pair)

    legacy = _find_legacy_section(text, feature.section_title)
    if legacy is not None:
        return _adopt_legacy(text, feature, body, version, legacy)

    return FeatureMergeResult(
        feature=feature.name,
        status="injected",
        new_text=_append_block(text, _render(feature.name, body, version)),
        canonical_body=body,
    )


def merge_skill(
    text: str, skill_name: str, features: list[FeatureSpec], version: str
) -> SkillMergeReport:
    """Merge every feature into one skill file, sequentially."""
    report = SkillMergeReport(skill_name=skill_name, new_text=text)
    for feature in features:
        result = merge_feature(report.new_text, feature, version)
        report.new_text = result.new_text
        report.results.append(result)
    return report


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

_MARKER_LINE_RE = re.compile(r"^<!--\s*arka:feature:[\w-]+:(?:start|end).*-->$")


def _start_re(name: str) -> re.Pattern[str]:
    return re.compile(
        rf"<!--\s*arka:feature:{re.escape(name)}:start"
        rf"(?:\s+version=(?P<version>\S+))?"
        rf"(?:\s+hash=(?P<hash>[0-9a-f]{{12}}))?\s*-->"
    )


def _end_re(name: str) -> re.Pattern[str]:
    return re.compile(rf"<!--\s*arka:feature:{re.escape(name)}:end\s*-->")


@dataclass
class _BlockLookup:
    """Outcome of locating one feature's markers: a pair, nothing, or a fault."""

    pair: tuple[re.Match[str], re.Match[str]] | None = None
    error: str | None = None


def _find_block(text: str, name: str) -> _BlockLookup:
    """Locate a well-formed start/end marker pair, or refuse to guess.

    Pairing a start marker with *any* later end marker is how a splice
    deletes text it does not own: an orphan start (an interrupted write, a
    hand-edit that dropped the end) would pair with the *next* block's end
    and take every project-authored byte in between with it. The same
    validation already guards ``.claude/CLAUDE.md`` in
    :func:`core.sync.content_merger._validate_markers`; a fault here is
    reported and never spliced.
    """
    starts = list(_start_re(name).finditer(text))
    ends = list(_end_re(name).finditer(text))

    if len(starts) != len(ends):
        return _BlockLookup(
            error=f"unbalanced markers: {len(starts)} start, {len(ends)} end"
        )
    if len(starts) > 1:
        return _BlockLookup(error=f"{len(starts)} blocks for one feature")
    if not starts:
        return _BlockLookup()
    if ends[0].start() < starts[0].end():
        return _BlockLookup(error="end marker appears before start marker")
    return _BlockLookup(pair=(starts[0], ends[0]))


def _malformed(
    text: str, feature: FeatureSpec, body: str, error: str
) -> FeatureMergeResult:
    """Refuse to touch a file whose markers cannot be trusted."""
    return FeatureMergeResult(
        feature=feature.name,
        status="malformed_markers",
        new_text=text,
        canonical_body=body,
        error=error,
    )


def _find_legacy_section(text: str, section_title: str) -> tuple[int, int] | None:
    """Locate an unmarked ``## <section_title>`` block, suffix tolerated.

    A project may harden the heading (``## Quality Gate (NON-NEGOTIABLE)``),
    so the title is matched as a prefix of the heading line.
    """
    heading = re.compile(rf"^## {re.escape(section_title)}\b.*$", re.M)
    match = heading.search(text)
    if match is None:
        return None
    following = re.compile(r"^## ", re.M).search(text, match.end())
    return match.start(), following.start() if following else len(text)


def _render(name: str, body: str, version: str) -> str:
    content_hash = compute_managed_hash(body)
    return (
        f"<!-- arka:feature:{name}:start version={version} hash={content_hash} -->\n"
        f"{body}\n"
        f"<!-- arka:feature:{name}:end -->"
    )


def _splice(text: str, start: int, end: int, replacement: str) -> str:
    return text[:start] + replacement + text[end:]


def _merge_existing_block(
    text: str,
    feature: FeatureSpec,
    body: str,
    version: str,
    block: tuple[re.Match[str], re.Match[str]],
) -> FeatureMergeResult:
    start, end = block
    rewritten = _splice(text, start.start(), end.end(), _render(feature.name, body, version))
    if start.group("hash") != compute_managed_hash(body):
        status: FeatureStatus = "updated"
    elif start.group("version") != version:
        status = "restamped"
    else:
        return FeatureMergeResult(
            feature=feature.name, status="unchanged", new_text=text, canonical_body=body
        )
    return FeatureMergeResult(
        feature=feature.name, status=status, new_text=rewritten, canonical_body=body
    )


def _adopt_legacy(
    text: str,
    feature: FeatureSpec,
    body: str,
    version: str,
    span: tuple[int, int],
) -> FeatureMergeResult:
    """Wrap an unmarked section in markers, but only if it has not diverged."""
    start, end = span
    legacy = text[start:end].strip()
    if legacy != body:
        return FeatureMergeResult(
            feature=feature.name,
            status="pending_adoption",
            new_text=text,
            canonical_body=body,
            legacy_body=legacy,
        )
    # The legacy span runs to the start of the next heading, blank line
    # included. Closing with a single newline would swallow that blank line —
    # harmless to rendering (a comment closes its HTML block on the `-->`
    # line, so the next heading still parses) but it silently reflows
    # project-authored spacing, which adoption has no business touching.
    return FeatureMergeResult(
        feature=feature.name,
        status="adopted",
        new_text=_splice(text, start, end, _render(feature.name, body, version) + "\n\n"),
        canonical_body=body,
        legacy_body=legacy,
    )


def _remove_feature(
    text: str, feature: FeatureSpec, body: str, lookup: _BlockLookup
) -> FeatureMergeResult:
    """Remove a deprecated feature; never guess at a customised section."""
    if lookup.pair is not None:
        start, end = lookup.pair
        return FeatureMergeResult(
            feature=feature.name,
            status="removed",
            new_text=_splice(text, start.start(), end.end(), "").lstrip("\n"),
            canonical_body=body,
        )

    legacy = _find_legacy_section(text, feature.section_title)
    if legacy is None:
        return FeatureMergeResult(
            feature=feature.name, status="unchanged", new_text=text, canonical_body=body
        )

    start, end = legacy
    legacy_text = text[start:end].strip()
    if legacy_text != body:
        # Deleting a section the project rewrote would destroy operator work.
        return FeatureMergeResult(
            feature=feature.name,
            status="pending_removal",
            new_text=text,
            canonical_body=body,
            legacy_body=legacy_text,
        )
    return FeatureMergeResult(
        feature=feature.name,
        status="removed",
        new_text=_splice(text, start, end, ""),
        canonical_body=body,
    )


def _append_block(text: str, block: str) -> str:
    """Append a new feature block after the last existing one, else at the end."""
    last_end = None
    for match in re.finditer(r"<!--\s*arka:feature:[\w-]+:end\s*-->", text):
        last_end = match
    if last_end is not None:
        return _splice(text, last_end.end(), last_end.end(), f"\n\n{block}")
    separator = "\n\n" if text.strip() else ""
    return f"{text.rstrip()}{separator}{block}\n" if text.strip() else f"{block}\n"
