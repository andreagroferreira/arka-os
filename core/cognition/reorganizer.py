"""Dreaming → Agent reorganizer MVP (PR20 v2.42.0).

Propose-only. Scans the KB for pattern/anti-pattern/lesson artifacts
produced by Dreaming, sanitizes client identifiers, and renders a
markdown proposal report. Never modifies agent YAMLs — that step is
left for human review (and PR21 will wire optional auto-PR creation).

Reads only. The only write is the proposal markdown file under
``output_dir`` (default ``~/.arkaos/reorganize-proposals/``), and only
when ``dry_run=False``.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)", re.DOTALL)
_BODY_EXCERPT_LIMIT = 500
_PROPOSAL_FILENAME_FMT = "%Y-%m-%d.md"
_DEFAULT_OUTPUT_DIR = Path.home() / ".arkaos" / "reorganize-proposals"
_REDACT_TOKEN = "<redacted-client>"

# Client-name redaction patterns are loaded from a user-local JSON file —
# NEVER hard-coded in source. v2.18.0 shipped client names in source and
# leaked them to the npm registry (see feedback_npm_publish_safety in
# user memory); v2.42.0 fixes that class of mistake by design.
#
# File: ~/.arkaos/redaction-clients.json
# Shape: {"clients": ["client-a", "client-b", ...]}
# Missing file or malformed JSON → empty list (no redaction, tags-drop
# safety net at `_render` is the architectural backstop).
#
# Word boundary uses negative lookaround that allows hyphens so
# `client-a-billing-quirk` redacts the `client-a` segment correctly
# without false-positives on `client-axfoo`.
_REDACT_CONFIG_PATH = Path.home() / ".arkaos" / "redaction-clients.json"


def _load_client_patterns() -> tuple[str, ...]:
    """Read the user-local redaction list. Empty tuple on any error."""
    try:
        data = json.loads(_REDACT_CONFIG_PATH.read_text(encoding="utf-8"))
        raw = data.get("clients", [])
        return tuple(str(c).strip().lower() for c in raw if c and isinstance(c, str))
    except (OSError, json.JSONDecodeError, AttributeError):
        return ()


def _build_redact_re(patterns: tuple[str, ...]) -> re.Pattern[str] | None:
    if not patterns:
        return None
    escaped = [re.escape(p) for p in patterns]
    return re.compile(
        r"(?<![a-z0-9])(" + "|".join(escaped) + r")(?![a-z0-9])",
        re.IGNORECASE,
    )


_CLIENT_PATTERNS: tuple[str, ...] = _load_client_patterns()
_REDACT_RE: re.Pattern[str] | None = _build_redact_re(_CLIENT_PATTERNS)

_KNOWN_CATEGORIES = ("pattern", "anti-pattern", "lesson")


@dataclass(frozen=True)
class KbArtifact:
    """One pattern / anti-pattern / lesson surfaced from the KB."""
    path: Path
    category: str
    title: str
    confidence: str
    tags: list[str] = field(default_factory=list)
    first_seen: str = ""
    last_seen: str = ""
    times_used: int = 0
    body_excerpt: str = ""


@dataclass(frozen=True)
class ProposalReport:
    """Result of build_proposal — never contains client identifiers."""
    generated_at: str
    since_days: int
    kb_dir: str
    artifact_count: int
    by_category: dict[str, int] = field(default_factory=dict)
    report_markdown: str = ""
    report_path: Path | None = None


def build_proposal(
    kb_dir: Path,
    *,
    since_days: int = 7,
    output_dir: Path | None = None,
    dry_run: bool = False,
) -> ProposalReport:
    """Aggregate recent KB artifacts into a propose-only markdown report."""
    kb_dir = Path(kb_dir)
    cutoff = datetime.now(timezone.utc).date() - timedelta(days=max(since_days - 1, 0))
    artifacts = _scan_kb(kb_dir, cutoff)
    by_category = _aggregate_by_category(artifacts)
    generated_at = datetime.now(timezone.utc).isoformat()
    markdown = _render(artifacts, by_category, since_days, kb_dir, generated_at)
    report_path = None if dry_run else _write_report(markdown, output_dir)
    return ProposalReport(
        generated_at=generated_at,
        since_days=since_days,
        kb_dir=str(kb_dir),
        artifact_count=len(artifacts),
        by_category=by_category,
        report_markdown=markdown,
        report_path=report_path,
    )


def _aggregate_by_category(artifacts: list[KbArtifact]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for art in artifacts:
        counts[art.category] = counts.get(art.category, 0) + 1
    return counts


def _write_report(markdown: str, output_dir: Path | None) -> Path:
    """Atomic markdown write to a validated output directory."""
    out = _validate_output_dir(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    report_path = out / datetime.now(timezone.utc).strftime(_PROPOSAL_FILENAME_FMT)
    tmp_path = report_path.with_suffix(f".tmp-{os.getpid()}.md")
    tmp_path.write_text(markdown, encoding="utf-8")
    os.replace(tmp_path, report_path)
    return report_path


def _validate_output_dir(output_dir: Path | None) -> Path:
    """Allowlist the output directory to a safe parent.

    Without this guard, programmatic callers passing an attacker-controlled
    ``output_dir`` could write the proposal report anywhere the process has
    write access (e.g., ``~/.ssh/``). Even though the CLI does not expose
    ``--output-dir``, the public API does — defence in depth.

    Allowed roots:
      - ``~/.arkaos`` — the canonical production location
      - the system tempdir — for tests using pytest's ``tmp_path`` and any
        deliberate scratch use; still bounded by OS process privilege
    """
    if output_dir is None:
        return _DEFAULT_OUTPUT_DIR
    resolved = Path(output_dir).expanduser().resolve()
    allowed_roots = (
        (Path.home() / ".arkaos").resolve(),
        Path(tempfile.gettempdir()).resolve(),
    )
    for root in allowed_roots:
        try:
            resolved.relative_to(root)
            return resolved
        except ValueError:
            continue
    raise ValueError(
        "output_dir must be under one of "
        f"{[str(r) for r in allowed_roots]}; got {resolved}"
    )


def _scan_kb(kb_dir: Path, cutoff) -> list[KbArtifact]:
    if not kb_dir.is_dir():
        return []
    out: list[KbArtifact] = []
    for md in sorted(kb_dir.rglob("*.md")):
        category = _category_from_filename(md.name)
        if category is None:
            continue
        try:
            text = md.read_text(encoding="utf-8")
        except OSError:
            continue
        artifact = _parse_artifact(md, text, category)
        if artifact is None:
            continue
        if not _within_window(artifact, cutoff):
            continue
        out.append(artifact)
    return out


def _category_from_filename(name: str) -> str | None:
    lower = name.lower()
    if lower.startswith("anti-pattern-"):
        return "anti-pattern"
    if lower.startswith("pattern-"):
        return "pattern"
    if lower.startswith("lesson-"):
        return "lesson"
    return None


def _parse_artifact(path: Path, text: str, default_category: str) -> KbArtifact | None:
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return None
    fm = _parse_frontmatter(match.group(1))
    if not fm:
        return None
    body = match.group(2)
    category = str(fm.get("category", default_category))
    if category not in _KNOWN_CATEGORIES:
        category = default_category
    raw_title = str(fm.get("title", path.stem))
    excerpt = _redact(_body_excerpt(body))
    times_used = _safe_int(fm.get("times_used"))
    return KbArtifact(
        path=path,
        category=category,
        title=_redact(raw_title),
        confidence=str(fm.get("confidence", "")),
        tags=_parse_list(fm.get("tags")),
        first_seen=str(fm.get("first_seen", "")),
        last_seen=str(fm.get("last_seen", "")),
        times_used=times_used,
        body_excerpt=excerpt,
    )


def _within_window(artifact: KbArtifact, cutoff) -> bool:
    for raw in (artifact.last_seen, artifact.first_seen):
        try:
            seen = datetime.strptime(raw, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            continue
        if seen >= cutoff:
            return True
    return not artifact.first_seen and not artifact.last_seen


def _parse_frontmatter(block: str) -> dict:
    out: dict[str, object] = {}
    current_key: str | None = None
    current_list: list[str] = []
    for raw_line in block.splitlines():
        if not raw_line.strip():
            continue
        if raw_line.startswith("  - "):
            current_list.append(raw_line[4:].strip())
            continue
        if current_key is not None and current_list:
            out[current_key] = list(current_list)
            current_list = []
        current_key = None
        if ":" not in raw_line:
            continue
        key, _, value = raw_line.partition(":")
        key, value = key.strip(), value.strip()
        if value == "":
            current_key = key
            continue
        out[key] = _parse_inline_value(value)
    if current_key is not None and current_list:
        out[current_key] = list(current_list)
    return out


def _parse_inline_value(value: str) -> object:
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [item.strip() for item in inner.split(",")]
    return value


def _parse_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value]
    if isinstance(value, str) and value:
        return [value]
    return []


def _safe_int(value: object) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0


def _redact(text: str) -> str:
    if _REDACT_RE is None:
        return text
    return _REDACT_RE.sub(_REDACT_TOKEN, text)


def _md_escape(text: str) -> str:
    """Escape markdown control characters that would distort a table row.

    Titles and excerpts come from frontmatter the operator controls, but
    a `|` in a title silently shifts table columns and corrupts the raw-
    artifact table. Escape pipes, newlines, and stray backticks.
    """
    return (
        text.replace("\\", "\\\\")
            .replace("|", "\\|")
            .replace("\n", " ")
            .replace("\r", " ")
            .replace("`", "")
    )


def _body_excerpt(body: str) -> str:
    stripped = body.strip()
    if len(stripped) <= _BODY_EXCERPT_LIMIT:
        return stripped
    return stripped[:_BODY_EXCERPT_LIMIT].rstrip() + "..."


def _render(
    artifacts: list[KbArtifact],
    by_category: dict[str, int],
    since_days: int,
    kb_dir: Path,
    generated_at: str,
) -> str:
    today = generated_at.split("T", 1)[0]
    parts = [
        _render_header(today, len(artifacts), since_days),
        _render_summary(by_category, since_days, len(artifacts)),
    ]
    if not artifacts:
        parts.append("\n_(no artifacts in window — nothing to propose)_")
        return "\n".join(parts)
    parts.append(_render_suggested_actions(artifacts))
    parts.append("## Raw artifact list\n\n" + _render_table(artifacts))
    return "\n".join(parts)


def _render_header(today: str, count: int, since_days: int) -> str:
    return (
        f"# ArkaOS Reorganization Proposal — {today}\n"
        "\n"
        f"> Generated by `/arka reorganize` from {count} artifact(s) "
        f"learned in the last {since_days} days.\n"
        "> **Propose-only** — no agent YAML changes have been applied."
    )


def _render_summary(by_category: dict[str, int], since_days: int, count: int) -> str:
    lines = [
        "\n## Summary\n",
        f"- Window: last {since_days} days",
        f"- Artifacts: **{count}**",
    ]
    for cat in _KNOWN_CATEGORIES:
        if cat in by_category:
            lines.append(f"- {cat.capitalize()}s: {by_category[cat]}")
    return "\n".join(lines)


def _render_suggested_actions(artifacts: list[KbArtifact]) -> str:
    lines = ["\n## Suggested actions\n"]
    for cat in _KNOWN_CATEGORIES:
        cat_items = [a for a in artifacts if a.category == cat]
        if not cat_items:
            continue
        lines.append(f"### {cat.capitalize()}s\n")
        for art in cat_items:
            lines.append(_render_artifact_bullet(art, cat))
    return "\n".join(lines)


def _render_artifact_bullet(art: KbArtifact, category: str) -> str:
    # Tags intentionally NOT rendered — see _CLIENT_PATTERNS comment.
    line = (
        f"- **{art.title}** (confidence: {art.confidence or 'n/a'}, "
        f"times_used: {art.times_used})\n"
        f"  suggested: review for {_suggest_target(category)}"
    )
    if art.body_excerpt:
        line += f"\n  > {art.body_excerpt}"
    return line + "\n"


def _suggest_target(category: str) -> str:
    if category == "pattern":
        return "surfacing in the relevant department squad's context"
    if category == "anti-pattern":
        return "candidate detector in `core/governance/learning_detector.py`"
    if category == "lesson":
        return "Tier 0 review — potential constitution amendment"
    return "manual review"


def _render_table(artifacts: list[KbArtifact]) -> str:
    rows = [
        "| Category | Title | Confidence | first_seen | last_seen | times_used |",
        "|---|---|---|---|---|---|",
    ]
    for art in artifacts:
        rows.append(
            f"| {_md_escape(art.category)} | {_md_escape(art.title)} "
            f"| {_md_escape(art.confidence) or 'n/a'} "
            f"| {_md_escape(art.first_seen) or 'n/a'} "
            f"| {_md_escape(art.last_seen) or 'n/a'} "
            f"| {art.times_used} |"
        )
    return "\n".join(rows)
