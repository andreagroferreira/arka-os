"""Post-task skill proposer (PR44 v2.63.0).

Constitution rule (NON-NEGOTIABLE): after every completed substantive
task, the system MUST evaluate whether the work just done represents a
repeatable capability that should be promoted to a permanent skill.

Mirror of the PR20 reorganizer pattern but focused on capability-capture.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

_COMPLETION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\[arka:gate:4\]", re.IGNORECASE),
    re.compile(r"\[arka:phase:13\]", re.IGNORECASE),  # legacy, v4.1 window
    re.compile(r"\barc complete\b", re.IGNORECASE),
)

_BYPASS_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\[arka:trivial\]", re.IGNORECASE),
    re.compile(r"\[arka:skill-skip\]", re.IGNORECASE),
)

_SKILL_WORTHY_HINTS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b\d+-phase\b", re.IGNORECASE),
    re.compile(r"\bworkflow\b", re.IGNORECASE),
    re.compile(r"\bskill\b", re.IGNORECASE),
    re.compile(r"\btemplate\b", re.IGNORECASE),
    re.compile(r"\bprocedure\b", re.IGNORECASE),
    re.compile(r"\bplaybook\b", re.IGNORECASE),
    re.compile(r"\bchecklist\b", re.IGNORECASE),
)

_TRIVIAL_WORD_THRESHOLD: int = 15
_DEFAULT_OUTPUT_DIR: Path = Path.home() / ".arkaos" / "skill-proposals"


@dataclass(frozen=True)
class SkillProposal:
    """Outcome of a skill-evaluation pass.

    ``proposal_path`` is set only when a file was actually written. It is
    ``None`` both when no proposal was warranted and when one was
    rendered but had nowhere safe to go (reason ``no-safe-filename``) —
    in that second case ``proposal_markdown`` still carries the capture,
    so a caller can route it somewhere else.
    """
    should_propose: bool
    reason: str
    suggested_slug: str | None
    proposal_path: Path | None
    proposal_markdown: str | None


def evaluate(
    transcript_tail: str,
    *,
    output_dir: Path | None = None,
    today: str | None = None,
) -> SkillProposal:
    """Classify the closing transcript tail; propose a skill if warranted."""
    text = transcript_tail or ""

    if _has_bypass(text):
        return SkillProposal(False, "bypass-marker", None, None, None)

    if not _has_completion_signal(text):
        return SkillProposal(False, "no-completion-signal", None, None, None)

    if _is_trivial_length(text):
        return SkillProposal(False, "trivial-length", None, None, None)

    hint_count = sum(1 for pat in _SKILL_WORTHY_HINTS if pat.search(text))
    if hint_count < 2:
        return SkillProposal(False, "below-skill-hint-floor", None, None, None)

    slug = _suggest_slug(text)
    markdown = _render_proposal(text, slug, today=today)
    out_dir = output_dir or _DEFAULT_OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    iso_today = today or datetime.now(UTC).strftime("%Y-%m-%d")
    path = _collision_free_path(out_dir, iso_today, slug, markdown)
    if path is None:
        return SkillProposal(False, "no-safe-filename", slug, None, markdown)
    path.write_text(markdown, encoding="utf-8")
    return SkillProposal(True, "proposed", slug, path, markdown)


def _collision_free_path(
    out_dir: Path, iso_today: str, slug: str, markdown: str
) -> Path | None:
    """Return a path for today's proposal, or ``None`` if none is safe.

    ``_suggest_slug`` anchors on the first matching skill-worthy hint, so
    same-day slug collisions are the norm: the six word hints plus the
    fallback yield seven fixed names, and the numeric ``N-phase`` hint
    mints a fresh one per number it matches (until ``_slugify``'s 60-char
    cap truncates the extremes back together). The space is small in
    practice, but it is not the fixed handful this docstring once
    claimed. Every proposal after the first with the same slug used to
    overwrite its predecessor, silently: distinct captured capabilities
    were lost with no error and no trace.

    Disambiguates by content digest rather than a counter, so re-running
    the hook over the same closing message stays idempotent (same content
    -> same path -> one file) while genuinely different proposals get
    their own. One invariant holds every branch honest: never return a
    path unless it is free or provably holds this exact proposal.

    A name built from our digest proves nothing about the bytes inside
    the file — any file can carry any name, no hash collision required.
    So when the plain name and both digest names are all occupied by
    content we cannot account for, this returns ``None`` and the caller
    writes nothing: losing one capture is honest, overwriting somebody
    else's is not.

    The digest names are checked before the plain one, so a re-fire after
    the operator deleted the plain twin lands back on the file it already
    wrote instead of duplicating it.
    """
    digest = hashlib.sha256(markdown.encode("utf-8")).hexdigest()
    plain = out_dir / f"{iso_today}-{slug}.md"
    # 8 hex chars keep the filename readable; the full digest is the
    # tie-breaker for the day those 32 bits meet a different proposal.
    digest_paths = (
        out_dir / f"{iso_today}-{slug}-{digest[:8]}.md",
        out_dir / f"{iso_today}-{slug}-{digest}.md",
    )
    for candidate in digest_paths:
        if _already_holds(candidate, markdown):
            return candidate
    if not plain.exists() or _already_holds(plain, markdown):
        return plain
    for candidate in digest_paths:
        if not candidate.exists():
            return candidate
    return None


def _already_holds(path: Path, markdown: str) -> bool:
    """True only when ``path`` provably contains exactly ``markdown``.

    Content we cannot read back is not "equal": a missing, unreadable, or
    non-UTF-8 file is unknown content, and the caller must treat unknown
    as another proposal rather than write over it. ``UnicodeDecodeError``
    is a ``ValueError``, not an ``OSError`` — both belong in the same
    branch, or the exception escapes ``evaluate`` into the Stop hook's
    blanket ``except Exception: pass`` and the proposal is lost silently.
    """
    try:
        return path.read_text(encoding="utf-8") == markdown
    except (OSError, ValueError):
        return False


def _has_completion_signal(text: str) -> bool:
    return any(p.search(text) for p in _COMPLETION_PATTERNS)


def _has_bypass(text: str) -> bool:
    return any(p.search(text) for p in _BYPASS_PATTERNS)


def _is_trivial_length(text: str) -> bool:
    return len(text.split()) < _TRIVIAL_WORD_THRESHOLD


def _suggest_slug(text: str) -> str:
    for pat in _SKILL_WORTHY_HINTS:
        m = pat.search(text)
        if m:
            anchor = m.group(0).lower()
            return _slugify(f"capability-{anchor}")
    return "capability-task"


def _slugify(value: str) -> str:
    out = re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-")
    return out[:60] if out else "capability"


def _render_proposal(text: str, slug: str, *, today: str | None) -> str:
    iso = today or datetime.now(UTC).strftime("%Y-%m-%d")
    excerpt = text.strip()
    if len(excerpt) > 1000:
        excerpt = excerpt[:1000].rstrip() + "..."
    return (
        f"# Skill Proposal — {slug}\n\n"
        f"> Auto-generated by skill_proposer.evaluate on {iso}. "
        "Review before promoting.\n\n"
        "## Why this proposal exists\n\n"
        "The constitution rule mandatory-skill-evaluation (NON-NEGOTIABLE) "
        "fires after every completed substantive task. This proposal "
        "represents a candidate capability the system thinks could be "
        "captured as a permanent skill in a department.\n\n"
        "## Transcript excerpt (last 1000 chars)\n\n"
        f"```\n{excerpt}\n```\n\n"
        "## Suggested next steps\n\n"
        "1. Decide if this capability deserves its own skill.\n"
        "2. Pick the target department (/dev, /brand, /saas, ...).\n"
        "3. Manually scaffold departments/<dept>/skills/<slug>/SKILL.md.\n"
        "4. Delete this proposal file once acted on.\n\n"
        "## Status\n\n"
        "- Reviewed by operator: NO\n"
        "- Promoted to skill: NO\n"
    )
