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
canonical body byte-for-byte. When it diverges, the project has customised
it, and this module refuses to overwrite: the divergence is reported for
review instead (the Terraform ``plan``-before-``apply`` contract). This is
what stops an "always align" sync from silently deleting the operator's
work.
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
    if feature.deprecated_in is not None:
        return _remove_feature(text, feature, body)

    block = _find_block(text, feature.name)
    if block is not None:
        return _merge_existing_block(text, feature, body, version, block)

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


def _find_block(text: str, name: str) -> tuple[re.Match[str], re.Match[str]] | None:
    """Locate a well-formed start/end marker pair for ``name``."""
    start = _start_re(name).search(text)
    if start is None:
        return None
    end = _end_re(name).search(text, start.end())
    if end is None:
        return None
    return start, end


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
    text: str, feature: FeatureSpec, body: str
) -> FeatureMergeResult:
    """Remove a deprecated feature; never guess at a customised section."""
    block = _find_block(text, feature.name)
    if block is not None:
        start, end = block
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
