"""Shared plumbing for the Quality Gate's advisory Jev reads (JEV PR3).

The prescreen (``qg_prescreen``) and the ``slop-score`` evidence section
(``slop_check``) both send a diff-class state, so both share the same
two rules before any call leaves the machine:

* ``ARKA_BYPASS_DECISIONS=1`` skips the read outright — no config read,
  no transport lookup, no network;
* no operator redaction list (no ``~/.arkaos/redaction-clients.json``, or
  an explicit ``{"clients": []}``) skips it too: a diff is fail-closed in
  ``core.decisions.privacy`` and asking anyway would only record N
  denials. A corrupt or unreadable list is NOT missing — privacy denies
  that one itself, and the caller reports the denial reason.

Both reads are advisory: callers map an unavailable outcome to a skip,
never to a verdict.

Both also read changed files from disk, and a changed-file name is an
input (``--changed-files``, or an untracked symlink git lists): only a
file that resolves inside the project, outside ``.git``, may be read
(:func:`readable_inside`, security review PR3, finding 36). The diff
allowlist (Decision 2c) judges the file that is READ, not the name that
points at it: :func:`resolved_path_allowed` (finding 51).
"""

from __future__ import annotations

import os
import stat
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from core.decisions.site import Outcome, Site

REASON_BYPASS = "bypass"
REASON_CONFIG_MISSING = "redaction-config-missing"
MIN_CALL_MS = 50  # the engine's own floor (engine.MIN_CALL_MS)


def blocked_reason() -> str | None:
    """Why no diff state may be sent right now, or None when it may be."""
    from core.decisions.config import bypassed

    if bypassed():
        return REASON_BYPASS
    from core.decisions.privacy import _config_absent

    if _config_absent():
        return REASON_CONFIG_MISSING
    return None


def readable_inside(project_dir: Path, name: str) -> Path | None:
    """The file ``name`` names when it resolves inside ``project_dir``, else None.

    Symlinks are followed before the check, so ``notes.txt -> ~/.netrc``
    and ``../x`` / ``/abs/x`` are refused alike; so is anything under
    ``.git`` (remote URLs with tokens, hooks). ``resolve`` keeps the case
    as written, and APFS and NTFS match names without it, so ``.GIT/config``
    opens ``.git/config``: the part test ignores case, and every directory
    on the way is also compared to ``root/.git`` by inode (finding 40).
    """
    try:
        root = Path(project_dir).resolve()
        target = (root / name).resolve()
    except (OSError, RuntimeError, ValueError):
        return None
    if target == root or not target.is_relative_to(root):
        return None
    if any(part.casefold() == ".git" for part in target.relative_to(root).parts):
        return None
    return None if _under_git_dir(root, target) else target


def resolved_path_allowed(project_dir: Path, name: str) -> bool:
    """True when ``name`` and the file it resolves to both pass the diff allowlist.

    The name alone lied: an untracked ``util.py -> config.yaml`` passed as
    ``.py`` and the YAML was read (QG PR3 r7 B1, finding 51). A name that
    resolves outside the project or into ``.git`` is refused, and so is a
    regular file with more than one hard link: it is another file under
    this name, and neither the name nor ``resolve`` can tell which. An
    existing target that is not a regular file (a directory, a FIFO, a
    socket) is refused too: a directory named ``big.md`` holds files the
    name does not judge (finding 52). A missing file (a deletion, a
    dangling link) is judged by the names alone: nothing is read.
    """
    from core.decisions.privacy import diff_path_allowed

    target = readable_inside(project_dir, name) if diff_path_allowed(name) else None
    if target is None or not diff_path_allowed(target.name):
        return False
    try:
        info = target.stat()
    except FileNotFoundError:
        return True
    except OSError:
        return False
    if not stat.S_ISREG(info.st_mode):  # a directory, a FIFO, a socket (finding 52)
        return False
    return info.st_nlink == 1


def _under_git_dir(root: Path, target: Path) -> bool:
    """True when ``target`` or a directory above it (inside ``root``) IS ``root/.git``."""
    git_dir = root / ".git"
    if not git_dir.is_dir():
        return False
    try:
        return any(
            os.path.samefile(p, git_dir)
            for p in (target, *target.parents)
            if p != root and p.is_relative_to(root) and p.exists()
        )
    except OSError:
        return True  # cannot tell: refuse


@dataclass
class Deadline:
    """A monotonic total budget shared by every call of one read."""

    total_ms: int
    started: float = 0.0

    def __post_init__(self) -> None:
        self.started = time.monotonic()

    def remaining_ms(self) -> int:
        spent = (time.monotonic() - self.started) * 1000
        return max(0, int(self.total_ms - spent))

    def call_ms(self, ceiling_ms: int) -> int | None:
        """The ceiling for the next call, or None when the budget is spent."""
        budget = min(ceiling_ms, self.remaining_ms())
        return budget if budget >= MIN_CALL_MS else None


def ask(
    site: Site, heuristic: object, state: dict[str, Any], session_id: str, timeout_ms: int
) -> Outcome:
    """One ``decide`` call for one site; its ``Outcome``. Never raises."""
    from core.decisions.engine import decide
    from core.decisions.site import SiteCall
    from core.decisions.transport import configured_model

    outcomes = decide(
        [SiteCall(site, heuristic)], state, session_id=session_id,
        timeout_ms=timeout_ms, model=configured_model(),
    )
    return outcomes[site.name]
