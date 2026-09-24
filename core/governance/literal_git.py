"""git calls that read a changed-file name as a NAME, never as a pathspec.

A changed-file name is an input (``--changed-files``, or a file an
attacker named in the tree), and git reads what follows ``--`` as a
pathspec: ``:!zz.py`` means "every file but zz.py" and ``*.py`` every
Python file, so ``git diff base -- ':!zz.py'`` returned the diff of a
config file the allowlist had skipped (security review PR3, finding 52).
Every git call that carries a changed-file name in the Quality Gate's
diff readers (``qg_prescreen``, ``slop_check`` and the ``evidence_checks``
helpers they share) goes through :func:`run`, which passes
``--literal-pathspecs`` AND sets ``GIT_LITERAL_PATHSPECS=1``. The calls
that take no changed-file name (``evidence_checks._diff_base`` and
``_derive_changed_files``) run outside it.

A git too old to know the option exits 129 on every call. That alone
does not make a caller read "no diff": ``qg_prescreen.file_diff`` treats
only exit 1 of its ``ls-files --error-unmatch`` probe as "untracked" and
returns '' on any other code, and :func:`names_exactly` answers False on
any non-zero exit, so the prescreen sends nothing. ``slop_check`` reads
such a name as untracked and scores the whole file, which is still the
one allowlisted regular file the name resolves to.

A literal pathspec still matches a directory's contents (``big.md``
names ``big.md/inner.yaml``), so the name is not enough on its own:
:func:`names_exactly` asks git which files a diff covers and a caller
refuses anything but exactly the one name it asked for.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

LITERAL_ENV = {"GIT_LITERAL_PATHSPECS": "1"}
LITERAL_FLAG = "--literal-pathspecs"


def env() -> dict[str, str]:
    """The process environment with literal pathspecs forced on."""
    return {**os.environ, **LITERAL_ENV}


def run(project_dir: Path, *args: str, timeout: float) -> subprocess.CompletedProcess[str]:
    """``git --literal-pathspecs <args>`` in ``project_dir``; raises like ``subprocess.run``."""
    return subprocess.run(
        ["git", LITERAL_FLAG, *args], cwd=project_dir, capture_output=True, text=True,
        timeout=timeout, env=env(),
    )


def names_exactly(project_dir: Path, base: str, name: str, timeout: float) -> bool:
    """True when ``git diff base -- name`` covers exactly the one file ``name``.

    ``-z`` keeps git from quoting the names, so the comparison is on the
    raw name; ``--relative`` prints them relative to ``project_dir``, so a
    repo subdirectory compares like the root (QG PR3 r9, m5). A directory,
    a pattern git still expands, or a failed call answers False.
    """
    try:
        proc = run(project_dir, "diff", "--relative", "--name-only", "-z", base, "--", name,
                   timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0 and proc.stdout.split("\0") == [name, ""]
