"""The ``slop-score`` evidence section — Jev's Slop Score of changed prose (JEV PR3).

The human-writing standard's Slop Score (five 1-10 dimensions, revise
below 35/50) used to exist only as a rubric a writer applied to their own
draft. This section asks the ``slop-score`` Jev site to score each
changed prose file (the suffixes ``spellcheck`` auto-skips on,
``evidence_checks._PROSE_SUFFIXES``) and reports the five scores and the
total per file.

Severity is ``minor`` and stays advisory at every level:

* ``passed=False`` only when a scored file totals below 35 — a finding
  for the same-turn fix-forward pass, never a REJECTED on its own;
* the overall never becomes ``fail`` because of this section, and a
  model's score is not executable evidence, so it never lifts an
  ``insufficient-evidence`` report to ``pass`` either
  (``evidence_checks._derive_overall``);
* no redaction list, the bypass, or an unavailable Jev → a skip row with
  the reason; never a network call under ``ARKA_BYPASS_DECISIONS=1``.

What is scored: the lines the change ADDED to a tracked file (the
changed prose, not the whole legacy document), or the whole text of an
untracked file; over 12k chars, the first 12k with a note. A file whose
name or resolved target is outside the diff allowlist is not read; its
row says ``path-class`` (finding 51). git reads every name literally
(``literal_git``), and a tracked name whose diff covers more than that
one file is ``path-class`` too (finding 52).
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any

from core.decisions.privacy import PATH_CLASS
from core.decisions.sites.quality import (
    MAX_PROSE_CHARS,
    QUALITY_TIMEOUT_MS,
    SLOP_DIMENSIONS,
    SLOP_PASS_TOTAL,
    SLOP_SCORE,
    prose_state,
    slop_needs_revision,
)
from core.governance import jev_advisory, literal_git
from core.governance.evidence_checks import (
    _PROSE_SUFFIXES,
    CheckResult,
    _added_lines,
    _diff_base,
    _git_tracks,
    _skip,
)

CHECK = "slop-score"
COMMAND = "jev:slop-score"
SLOP_TOTAL_MS = 30_000
SESSION = "qg-slop-score"
NO_PROSE = "no changed prose files (.md/.mdx/.txt)"
GIT_TIMEOUT_S = 30


def prose_files(changed: list[str] | None) -> list[str]:
    """The changed files ``spellcheck``'s prose predicate would keep."""
    return [c for c in changed or [] if PurePosixPath(c.strip()).suffix.lower() in _PROSE_SUFFIXES]


def prose_text(project_dir: Path, base: str | None, name: str) -> tuple[str, str]:
    """``(text, scope)``: the added lines of a tracked file, else the whole file.

    A name whose resolved file is outside the diff allowlist (a link to a
    config file, a hard link, a directory) is read neither way:
    ``("", "path-class")``; so is a tracked name whose diff covers any
    file but exactly that one (finding 52). git reads the name literally.
    """
    if not jev_advisory.resolved_path_allowed(project_dir, name):  # finding 51
        return "", PATH_CLASS
    if base is not None and _git_tracks(project_dir, name):
        added = _added_lines(project_dir, base, name)
        if added and not literal_git.names_exactly(project_dir, base, name, GIT_TIMEOUT_S):
            return "", PATH_CLASS
        if added is not None:
            return "\n".join(text for _, text in added), "added lines"
    path = jev_advisory.readable_inside(project_dir, name)
    if path is None:  # outside the project, a symlink out, or .git (finding 36)
        return "", "outside the project"
    try:
        return path.read_text(encoding="utf-8", errors="replace"), "whole file"
    except OSError:
        return "", "unreadable"


def _score_file(
    project_dir: Path, base: str | None, name: str, deadline: jev_advisory.Deadline
) -> dict[str, Any]:
    text, scope = prose_text(project_dir, base, name)
    row: dict[str, Any] = {"file": name, "scope": scope, "score": None,
                           "truncated": len(text) > MAX_PROSE_CHARS, "reason": ""}
    if not text.strip():
        row["reason"] = PATH_CLASS if scope == PATH_CLASS else "no prose to score"
        return row
    timeout = deadline.call_ms(QUALITY_TIMEOUT_MS)
    if timeout is None:
        row["reason"] = "deadline"
        return row
    outcome = jev_advisory.ask(SLOP_SCORE, None, prose_state(text, name), SESSION, timeout)
    if outcome.acted_on == "jev" and isinstance(outcome.value, dict):
        row["score"] = dict(outcome.value)
    else:
        row["reason"] = str(outcome.reason)
    return row


def _row_line(row: dict[str, Any]) -> str:
    note = f" (first {MAX_PROSE_CHARS} chars scored)" if row["truncated"] else ""
    score = row["score"]
    if score is None:
        return f"{row['file']}: not scored — {row['reason']}"
    dims = " ".join(f"{d}={score[d]}" for d in SLOP_DIMENSIONS)
    flag = " REVISE" if slop_needs_revision(score) else ""
    return f"{row['file']}: total={score['total']}/50 {dims} [{row['scope']}]{note}{flag}"


def _result(rows: list[dict[str, Any]]) -> CheckResult:
    scored = [r for r in rows if r["score"] is not None]
    failing = [r for r in scored if slop_needs_revision(r["score"])]
    head = (f"{len(scored)} of {len(rows)} prose file(s) scored; revise below "
            f"{SLOP_PASS_TOTAL}/50 (advisory, minor)")
    findings = [_row_line(r) for r in failing]
    return CheckResult(
        check=CHECK, ran=True, passed=not failing, command=COMMAND,
        exit_code=1 if failing else 0,
        summary="\n".join([head, *(_row_line(r) for r in rows)]),
        findings=findings, findings_count=len(findings),
    )


def check_slop_score(
    project_dir: Path, changed: list[str] | None,
    test_command: str | None, timeout: int,
) -> CheckResult:
    """The ``slop-score`` section; a skip row whenever nothing could be scored."""
    files = prose_files(changed)
    if not files:
        return _skip(CHECK, NO_PROSE)
    blocked = jev_advisory.blocked_reason()
    if blocked is not None:
        return _skip(CHECK, f"skipped reason={blocked} (prose never leaves the machine)")
    project_dir = Path(project_dir)
    base, deadline = _diff_base(project_dir), jev_advisory.Deadline(SLOP_TOTAL_MS)
    rows = [_score_file(project_dir, base, name, deadline) for name in files]
    if not any(r["score"] is not None for r in rows):
        reason = next((r["reason"] for r in rows if r["reason"]), "unavailable")
        return _skip(CHECK, f"skipped reason=unavailable:{reason}")
    return _result(rows)
