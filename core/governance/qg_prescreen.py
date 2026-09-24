"""Quality Gate prescreen — Jev's advisory read of the diff (JEV PR3, site #9).

Between the mechanical tier (``qg_tier``) and the reviewer dispatch,
Marta may ask the ``qg-prescreen`` site what a strict gate would likely
say about the diff and, when it would reject, on which blocker class.
The answer tells reviewers where to look FIRST. It is advisory, by
construction and by test:

* the reviewer list in the report is ``qg_tier.dispatch_reviewers`` of
  the tier, computed before and independently of any Jev answer — the
  prescreen never adds, removes or reorders a reviewer;
* an unavailable, abstaining, hostile or bypassed Jev yields the same
  reviewer list as no prescreen at all.

Mechanics: a changed file whose suffix is outside
``privacy.DIFF_SOURCE_SUFFIXES`` (config, dotfiles, key material, lock
files) is skipped BEFORE it is diffed and listed in ``skipped_paths``
(reason ``path-class``), so no request carries it; the reviewer list
does not change. The suffix is judged on the name and on the file the
name resolves to, so a link to a config file is skipped too (finding
51). git reads every name literally, a diff that covers anything but
the named file is refused whole, and every chunk carries the ``diff
--git`` line of the section it cuts into (finding 52). Every other file
gets one unified diff (vs the merge base; an untracked file is diffed
against ``/dev/null``), each cut on line boundaries into chunks of at
most ``MAX_DIFF_CHARS`` (one request per chunk, 5000 ms each, one
monotonic total budget). Chunks fold into a file verdict and files
into the session verdict the same way: any ``rejected`` wins with the
union of its blocker classes; ``approved`` needs every part approved;
anything else is ``unknown``.

The site is ``shadow`` by default (PR3 replay gate): the engine then
detaches each call to the shadow worker, which logs Jev's agreement, and
this read reports ``skipped reason=shadow`` — nothing reaches Marta. The
operator override ``decisions.sites.qg-prescreen: act`` makes it a live
read. ``p`` is always the verdict's own confidence, ``blocker_p`` the
blocker's.

The result lands in ``~/.arkaos/quality-gate/<session>/PRESCREEN.json``
(``reviewer_ledger.PRESCREEN_NAME``, covered by ledger retention) and the
QG verdict label copies it into its envelope. Usage::

    arka-py -m core.governance.qg_prescreen <project_dir> \\
        [--changed-files f1,f2] [--session-id <id>] [--json]
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from core.decisions.privacy import PATH_CLASS
from core.decisions.site import choice_confidence
from core.decisions.sites.quality import (
    MAX_DIFF_CHARS,
    NO_BLOCKER,
    QG_PRESCREEN,
    QUALITY_TIMEOUT_MS,
    diff_state,
    prescreen_heuristic,
)
from core.governance import jev_advisory, literal_git
from core.governance.evidence_checks import _derive_changed_files, _diff_base
from core.governance.qg_tier import compute_tier, dispatch_reviewers
from core.governance.reviewer_ledger import PRESCREEN_NAME, _safe_id, _write_temp, ledger_root

PRESCREEN_TOTAL_MS = 20_000
MARKER = "[arka:qg-prescreen]"
SESSION_FALLBACK = "qg-prescreen"
REASON_SHADOW = "shadow"
# Minimum room for the "# file: <name> part k/n" line each chunk carries.
_HEADER_RESERVE = 512
# What replaces the dropped tail of a line longer than a chunk.
LINE_CUT = " [long line cut]\n"
# The line that opens a file's section in a unified diff.
GIT_HEADER = "diff --git "
_GIT_TIMEOUT_S = 30
# ``git ls-files --error-unmatch`` exits 1 for a name it does not track;
# any other failure (129: a git without ``--literal-pathspecs``) is no answer.
_UNTRACKED_EXIT = 1


# --- diff and chunks ----------------------------------------------------------

def _git(project_dir: Path, *args: str) -> subprocess.CompletedProcess[str] | None:
    """Every git call of this module: names read literally (finding 52)."""
    try:
        return literal_git.run(project_dir, *args, timeout=_GIT_TIMEOUT_S)
    except (OSError, subprocess.TimeoutExpired):
        return None


def _untracked_diff(project_dir: Path, name: str) -> str:
    """An untracked file as an all-added diff ('' for a name git would not print).

    ``x.py/`` or ``./x.py`` resolve to the tracked ``x.py`` on disk while
    git answers "not tracked" for them, so only a name already in git's
    own spelling is read (QG PR3 r9, m4).
    """
    if PurePosixPath(name).as_posix() != name:
        return ""
    if not jev_advisory.resolved_path_allowed(project_dir, name):  # finding 51
        return ""
    path = jev_advisory.readable_inside(project_dir, name)
    if path is None:  # outside the project, a symlink out, or .git (finding 36)
        return ""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    lines = text.splitlines()
    head = f"diff --git a/{name} b/{name}\nnew file\n--- /dev/null\n+++ b/{name}\n"
    return head + f"@@ -0,0 +1,{len(lines)} @@\n" + "".join(f"+{ln}\n" for ln in lines)


def file_diff(project_dir: Path, base: str, name: str) -> str:
    """The unified diff of one changed file vs ``base`` ('' when none).

    A diff that covers any file but exactly ``name`` (a directory named
    like a source file, a name git still expands) is refused whole
    (finding 52): the allowlist judged ``name``, not what lies under it.
    Only exit 1 of the tracking probe means "untracked"; any other failure
    returns '' rather than reading the whole file (QG PR3 r9, m4).
    """
    proc = _git(project_dir, "diff", base, "--", name)
    if proc is not None and proc.returncode == 0 and proc.stdout.strip():
        exact = literal_git.names_exactly(project_dir, base, name, _GIT_TIMEOUT_S)
        return proc.stdout if exact else ""
    tracked = _git(project_dir, "ls-files", "--error-unmatch", "--", name)
    if tracked is not None and tracked.returncode == _UNTRACKED_EXIT:
        return _untracked_diff(project_dir, name)
    return ""


def _line_head(line: str, limit: int) -> str:
    """A line longer than a chunk: its head, cut on whitespace; the rest dropped.

    Cutting such a line into consecutive pieces split a secret or a client
    name across two requests, and neither half was recognisable to the
    privacy checks (security review PR3, finding 35). Dropping the tail
    loses advisory context only; a head without whitespace is dropped whole.
    """
    head = line[: max(0, limit - len(LINE_CUT))]
    cut = max(head.rfind(" "), head.rfind("\t"))
    return (head[:cut] if cut > 0 else "") + LINE_CUT


def _newline_lines(text: str) -> list[str]:
    """``text`` split after each ``\\n`` only, the newline kept.

    ``str.splitlines`` also breaks on form feed, NEL, U+2028 and the like,
    so a content line ``+a<FF>diff --git a/config.yaml ...`` became a
    carried header; ``privacy`` splits on newline only, and so does this
    (QG PR3 r9, m3).
    """
    lines = [line + "\n" for line in text.split("\n")]
    lines[-1] = lines[-1][:-1]
    return [line for line in lines if line]


def _split_lines(text: str, limit: int) -> list[str]:
    """``text`` in pieces of at most ``limit`` chars, cut between lines only."""
    pieces: list[str] = []
    current = ""
    for line in _newline_lines(text):
        if len(line) > limit:
            line = _line_head(line, limit)
        if current and len(current) + len(line) > limit:
            pieces.append(current)
            current = ""
        current += line
    if current:
        pieces.append(current)
    return pieces


def _header(name: str, part: int, total: int) -> str:
    return f"# file: {name} part {part}/{total}\n"


def _git_header_lines(text: str) -> list[str]:
    return [ln for ln in _newline_lines(text) if ln.startswith(GIT_HEADER)]


def carry_git_headers(bodies: list[str]) -> list[str]:
    """Every body that starts inside a file section, prefixed with its ``diff --git`` line.

    A continuation chunk had no header, so ``privacy.prepare_state``
    judged it by the state's ``path`` alone and sent it whatever file
    it came from (finding 52); with the header carried, every chunk
    names the file its lines belong to, and each one is judged.
    """
    carried: list[str] = []
    current = ""
    for body in bodies:
        if current and not body.startswith(GIT_HEADER):
            body = current + body
        current = next(reversed(_git_header_lines(body)), current)
        carried.append(body)
    return carried


def chunk_diff(name: str, diff: str, limit: int = MAX_DIFF_CHARS) -> list[str]:
    """One file's diff as chunks of at most ``limit`` chars each.

    The header room is measured on the real name (an upper bound on the
    part numbers) plus the longest ``diff --git`` line a chunk may carry
    (:func:`carry_git_headers`), so no chunk is ever cut after the fact:
    the old ``chunk[:limit]`` cut the tail of a chunk mid-token for a name
    past ~480 chars (finding 35). A name that leaves no room sends nothing.
    """
    widest = len(str(max(1, len(diff))))
    reserve = max(_HEADER_RESERVE, len(_header(name, 10**widest - 1, 10**widest - 1)))
    reserve += max(map(len, _git_header_lines(diff)), default=0)
    if reserve > limit // 2:
        return []
    bodies = carry_git_headers(_split_lines(diff, limit - reserve))
    total = len(bodies)
    return [_header(name, i, total) + body for i, body in enumerate(bodies, 1)]


# --- verdict algebra ----------------------------------------------------------

@dataclass
class Prediction:
    """A prescreen verdict for a chunk, a file or the whole diff."""

    verdict: str = "unknown"  # approved | rejected | unknown
    blockers: set[str] = field(default_factory=set)
    p: float | None = None  # the verdict's own confidence
    jev: bool = False  # at least one part was answered by Jev
    reasons: list[str] = field(default_factory=list)
    blocker_p: float | None = None  # the blocker answer's own confidence
    shadow: bool = False  # answered in shadow: logged, not acted on


def combine(a: Prediction, b: Prediction) -> Prediction:
    """Fold two predictions: rejected wins, approved needs both, else unknown."""
    jev, reasons = a.jev or b.jev, [*a.reasons, *b.reasons]
    shadow = a.shadow or b.shadow
    rejected = [x for x in (a, b) if x.verdict == "rejected"]
    if rejected:
        blockers = set().union(*(x.blockers for x in rejected))
        return Prediction("rejected", blockers, _max_p(x.p for x in rejected), jev,
                          reasons, _max_p(x.blocker_p for x in rejected), shadow)
    if a.verdict == b.verdict == "approved":
        ps = [x.p for x in (a, b) if x.p is not None]
        return Prediction("approved", set(), min(ps) if ps else None, jev, reasons,
                          None, shadow)
    return Prediction("unknown", set(), None, jev, reasons, None, shadow)


def _max_p(values: Any) -> float | None:
    known = [v for v in values if v is not None]
    return max(known) if known else None


def fold(parts: list[Prediction]) -> Prediction:
    """Every part folded with :func:`combine`; nothing → unknown."""
    if not parts:
        return Prediction(reasons=["no-diff"])
    result = parts[0]
    for part in parts[1:]:
        result = combine(result, part)
    return result


def _from_outcome(outcome: Any) -> Prediction:
    """The chunk's prediction from its ``Outcome``.

    ``p`` is the verdict answer's own confidence and ``blocker_p`` the
    blocker's (``value["blocker_p"]``) — never ``Outcome.confidence``, the
    engine's minimum across both answers, which let an unsure blocker
    pass for an unsure verdict. In shadow the engine detaches the call
    and returns the neutral baseline with reason ``shadow``: that is a
    skip. Only a shadow outcome that carries Jev's value (a call shared
    with an ``act`` site) is read, and it is marked as shadow.
    """
    shadow = outcome.reason == "shadow" and isinstance(outcome.jev, dict)
    value = outcome.jev if shadow else outcome.value
    if not shadow and (outcome.acted_on != "jev" or not isinstance(value, dict)):
        return Prediction(reasons=[str(outcome.reason)])
    verdict = str(value.get("verdict", "unknown"))
    blocker = str(value.get("blocker", NO_BLOCKER))
    blockers = {blocker} if verdict == "rejected" and blocker != NO_BLOCKER else set()
    return Prediction(verdict, blockers, _verdict_p(outcome), True,
                      ["shadow" if shadow else "jev"], _as_p(value.get("blocker_p")), shadow)


def _verdict_p(outcome: Any) -> float | None:
    answer = (outcome.answers or {}).get("likely_verdict")
    return None if answer is None else _as_p(choice_confidence(answer))


def _as_p(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def ask_chunk(
    chunk: str, session_id: str, deadline: jev_advisory.Deadline, *, path: str
) -> Prediction:
    """One request for one chunk of ``path``, inside the shared budget."""
    timeout = deadline.call_ms(QUALITY_TIMEOUT_MS)
    if timeout is None:
        return Prediction(reasons=["deadline"])
    outcome = jev_advisory.ask(
        QG_PRESCREEN, prescreen_heuristic(), diff_state(chunk, path), session_id, timeout)
    return _from_outcome(outcome)


def partition_paths(
    project_dir: Path, changed: list[str]
) -> tuple[list[str], list[dict[str, str]]]:
    """``(files a diff state may carry, skipped rows)``, decided before any diff.

    Judged on the name AND on the file it resolves to
    (:func:`jev_advisory.resolved_path_allowed`, finding 51): a symlink or
    a hard link to a config file is skipped with reason ``path-class``.
    """
    allowed = {name: jev_advisory.resolved_path_allowed(project_dir, name) for name in changed}
    sendable = [name for name in changed if allowed[name]]
    skipped = [{"path": name, "reason": PATH_CLASS} for name in changed if not allowed[name]]
    return sendable, skipped


# --- the run ------------------------------------------------------------------

def _prescreen_files(
    project_dir: Path, changed: list[str], session_id: str
) -> tuple[list[dict[str, Any]], list[Prediction], int]:
    base = _diff_base(project_dir)
    if base is None:
        return [], [Prediction(reasons=["no-diff-base"])], 0
    deadline = jev_advisory.Deadline(PRESCREEN_TOTAL_MS)
    rows: list[dict[str, Any]] = []
    folded: list[Prediction] = []
    requests = 0
    for name in changed:
        chunks = chunk_diff(name, file_diff(project_dir, base, name))
        if not chunks:
            continue
        verdict = fold([ask_chunk(c, session_id, deadline, path=name) for c in chunks])
        requests += len(chunks)
        rows.append({"file": name, "chunks": len(chunks), **_public(verdict)})
        folded.append(verdict)
    return rows, folded, requests


def _round(p: float | None) -> float | None:
    return None if p is None else round(p, 4)


def _public(pred: Prediction) -> dict[str, Any]:
    blocker = ",".join(sorted(pred.blockers)) or NO_BLOCKER
    source = "jev" if pred.jev and pred.verdict != "unknown" else "neutral"
    return {"verdict": pred.verdict, "blocker": blocker, "p": _round(pred.p),
            "blocker_p": _round(pred.blocker_p), "source": source, "shadow": pred.shadow}


def _skip_reason(pred: Prediction, blocked: str | None) -> str | None:
    if blocked is not None:
        return blocked
    if pred.jev:
        return None
    if REASON_SHADOW in pred.reasons:  # detached: nothing to read synchronously
        return REASON_SHADOW
    first = next((r for r in pred.reasons if r != "jev"), "no-diff")
    return f"unavailable:{first}"


def run_prescreen(
    project_dir: Path, changed: list[str] | None = None, session_id: str = ""
) -> dict[str, Any]:
    """The advisory prescreen report. Never raises on a Jev failure."""
    project_dir = Path(project_dir)
    if changed is None:
        changed = _derive_changed_files(project_dir) or []
    tier = compute_tier(project_dir, changed or None)
    blocked = jev_advisory.blocked_reason()
    sendable, skipped_paths = partition_paths(project_dir, changed)
    rows: list[dict[str, Any]] = []
    parts: list[Prediction] = []
    requests = 0
    if blocked is None:
        rows, parts, requests = _prescreen_files(
            project_dir, sendable, session_id or SESSION_FALLBACK)
    overall = fold(parts)
    report = _report(tier, overall, _skip_reason(overall, blocked), rows, requests)
    return {**report, "skipped_paths": skipped_paths}


def _report(
    tier: dict[str, Any], overall: Prediction, skipped: str | None,
    rows: list[dict[str, Any]], requests: int,
) -> dict[str, Any]:
    # The reviewer list is the tier's, full stop: nothing below reads it.
    public = _public(overall) if skipped is None else {
        "verdict": "unknown", "blocker": NO_BLOCKER, "p": None, "blocker_p": None,
        "source": "neutral", "shadow": False}
    report = {
        "advisory": True, **public, "skipped": skipped, "requests": requests,
        "files": rows, "tier": tier.get("tier"), "reviewers": dispatch_reviewers(tier),
    }
    report["marker"] = marker_line(report)
    return report


def _shown(p: object) -> str:
    return "-" if not isinstance(p, int | float) else f"{p:.2f}"


def marker_line(report: dict[str, Any]) -> str:
    """The one marker line of a prescreen run.

    ``[arka:qg-prescreen] [shadow ]verdict=… blocker=… p=… blocker_p=… source=…``
    (``p`` the verdict's confidence, ``blocker_p`` the blocker's, ``-``
    when unknown) or ``[arka:qg-prescreen] skipped reason=…``.
    """
    if report.get("skipped"):
        return f"{MARKER} skipped reason={report['skipped']}"
    head = f"{MARKER} shadow" if report.get("shadow") else MARKER
    return (f"{head} verdict={report['verdict']} blocker={report['blocker']} "
            f"p={_shown(report.get('p'))} blocker_p={_shown(report.get('blocker_p'))} "
            f"source={report['source']}")


# --- the ledger file ------------------------------------------------------------

ENVELOPE_KEYS: tuple[str, ...] = ("verdict", "blocker", "p", "source")


def write_prescreen(session_id: str, report: dict[str, Any]) -> Path | None:
    """``PRESCREEN.json`` in the session's ledger dir, atomically; None on failure."""
    if not _safe_id(session_id):
        return None
    session_dir = ledger_root() / session_id
    record = {"ts": datetime.now(UTC).isoformat(), "session_id": session_id,
              **{k: v for k, v in report.items() if k != "marker"}}
    try:
        session_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    except OSError:
        return None
    tmp = _write_temp(session_dir, PRESCREEN_NAME, record)
    if tmp is None:
        return None
    path = session_dir / PRESCREEN_NAME
    try:
        os.replace(tmp, path)  # a re-run replaces the prediction, never a gap
    except OSError:
        with contextlib.suppress(OSError):
            tmp.unlink(missing_ok=True)
        return None
    return path


def read_prescreen(session_id: str) -> dict[str, Any] | None:
    """The ``{verdict, blocker, p, source}`` envelope of a session, or None."""
    if not session_id or not _safe_id(session_id):
        return None
    try:
        data = json.loads((ledger_root() / session_id / PRESCREEN_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    if data.get("skipped"):
        return {"verdict": "unknown", "blocker": NO_BLOCKER, "p": None,
                "source": f"skipped:{data['skipped']}"}
    envelope = {key: data.get(key) for key in ENVELOPE_KEYS}
    if data.get("shadow"):  # a logged prediction nobody acted on
        envelope["source"] = f"shadow:{envelope['source']}"
    return envelope


# --- CLI ------------------------------------------------------------------------

def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="arka-py -m core.governance.qg_prescreen",
        description="Advisory Jev prescreen of the diff; never changes the reviewer list.",
    )
    parser.add_argument("project_dir", type=Path)
    parser.add_argument("--changed-files", action="append", default=[],
                        help="comma-separated override (repeatable); derived from git when omitted")
    parser.add_argument("--session-id", default="",
                        help="writes PRESCREEN.json into that session's QG ledger")
    parser.add_argument("--json", action="store_true", help="emit the full JSON report")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    changed = [f.strip() for raw in args.changed_files for f in raw.split(",") if f.strip()]
    report = run_prescreen(args.project_dir, changed or None, args.session_id)
    path = write_prescreen(args.session_id, report) if args.session_id else None
    report["prescreen_path"] = str(path) if path else None
    if args.json:
        print(json.dumps(report, indent=2))
        return 0
    print(report["marker"])
    for row in report["files"]:
        print(f"  {row['file']}: verdict={row['verdict']} blocker={row['blocker']} "
              f"chunks={row['chunks']}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
