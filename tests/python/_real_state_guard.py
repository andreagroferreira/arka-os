"""Pure helpers for the suite-wide real-state write guard (issue #497/#510).

Deliberately NOT in ``conftest.py``. pytest imports every conftest under
the bare module name ``conftest``, and ``sys.modules["conftest"]`` is
claimed by whichever one loads first — this tree already ships
``tests/python/diagram/conftest.py`` and ``tests/python/watch/conftest.py``,
so a test importing helpers via ``from conftest import ...`` aborts
collection whenever a sibling conftest wins the name. The leading
underscore keeps pytest from collecting this module as tests.

``conftest.py`` imports from here and holds only the fixture.

Why a snapshot and not a global ``open()`` monkeypatch: patching the
process-wide file primitive is fragile in both directions — it misses
every write that goes through ``os.replace``/``pathlib``/C extensions,
and it breaks unrelated libraries that legitimately open files. A
snapshot cannot say WHICH test wrote, but it says WHAT was written with
zero false mechanism, and the file name is enough to find the test.

Reads stay legal on purpose: the agent-parity tests read these very paths
and must keep doing so. Only a changed fingerprint gates.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Real-state surfaces a test must never write to. Extend this tuple when a
#: new generated-and-committed artefact appears; the cost is one stat +
#: one hash per file, twice per session.
#:
#: Census at the time of writing: 89 tracked ``config/claude-agents/*.md``
#: + 48 tracked ``departments/*/workflows/*.yaml`` = 137 git-tracked, plus
#: the operator's real ``~/.arkaos/projects`` descriptors, which are in no
#: index. The fingerprint total is therefore larger than the tracked count
#: and the two must not be conflated.
_GUARDED_GLOBS: tuple[tuple[Path, str], ...] = (
    # QG round 1 (B1): the tracker writes in-project now — a test that
    # runs with the checkout as cwd and no chdir would write HERE.
    (REPO_ROOT / ".arka", "workflow-state.json"),
    (REPO_ROOT / "config" / "claude-agents", "*.md"),
    (REPO_ROOT / "departments", "*/workflows/*.yaml"),
    (Path.home() / ".arkaos" / "projects", "**/*.md"),
)

#: Escape hatch for the one false positive the snapshot cannot rule out:
#: something OUTSIDE pytest mutating a guarded path while the suite runs
#: (an `/arka update` writing ~/.arkaos/projects in another terminal).
#: Not for silencing a test that writes — fix the test.
BYPASS_ENV = "ARKA_ALLOW_REAL_WRITES"


def fingerprints() -> dict[Path, tuple[int, str]]:
    """(mtime_ns, sha256) for every guarded file that exists right now."""
    out: dict[Path, tuple[int, str]] = {}
    for base, pattern in _GUARDED_GLOBS:
        if not base.is_dir():
            continue
        for path in base.glob(pattern):
            if not path.is_file():
                continue
            try:
                out[path] = (
                    path.stat().st_mtime_ns,
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                )
            except OSError:
                continue
    return out


def describe(path: Path) -> str:
    """Repo-relative name when possible; absolute for paths outside it."""
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def collect_violations(
    before: dict[Path, tuple[int, str]], after: dict[Path, tuple[int, str]]
) -> dict[str, list[str]]:
    """Diff two fingerprint maps into rewritten / mutated / created / deleted.

    BOTH fields are load-bearing and both gate. ``rewritten`` (mtime) is
    what catches the #497 symptom, whose bytes were identical.
    ``mutated`` (sha256) is not decoration: timestamp-carrying writers
    (``shutil.copy2`` via ``copystat``, ``rsync -t``, ``tar -p``) stamp
    the source's mtime onto the destination, so a restore from a snapshot
    that shares the destination's timestamp changes the bytes at the old
    mtime and the mtime test alone goes blind.

    Pure, and separately tested in test_real_state_write_guard.py: a guard
    that compares the wrong field reports nothing and is
    indistinguishable from a clean run.
    """
    rewritten = sorted(
        describe(path)
        for path, fingerprint in before.items()
        if path in after and after[path][0] != fingerprint[0]
    )
    mutated = sorted(
        describe(path)
        for path, fingerprint in before.items()
        if path in after and after[path][1] != fingerprint[1]
    )
    return {
        "rewritten": rewritten,
        "mutated": mutated,
        "created": sorted(describe(path) for path in set(after) - set(before)),
        "deleted": sorted(describe(path) for path in set(before) - set(after)),
    }


def format_failure(found: dict[str, list[str]]) -> str:
    """Render a violation report, or "" when the session is clean."""
    rewritten = found["rewritten"]
    mutated = found["mutated"]
    created = found["created"]
    deleted = found["deleted"]

    # `mutated` is in the condition deliberately: a timestamp-carrying
    # write can change the bytes without moving mtime, and a guard that
    # recorded that in a field it never read would hold the truth and
    # stay silent.
    if not (rewritten or mutated or created or deleted):
        return ""

    changed = set(mutated)
    lines = [
        "A test wrote to real state instead of tmp_path "
        "(constitution: destructive-tests, issue #497).",
        "",
        "Point the offending test at tmp_path — or, for the projects "
        "directory, set ARKA_PROJECTS_DIR.",
        "",
    ]
    if rewritten:
        lines.append(f"rewritten ({len(rewritten)}):")
        lines += [
            f"  {name}{'  [CONTENT CHANGED]' if name in changed else ''}"
            for name in rewritten[:20]
        ]
        if len(rewritten) > 20:
            lines.append(f"  ... and {len(rewritten) - 20} more")
    mtime_preserved = [name for name in mutated if name not in set(rewritten)]
    if mtime_preserved:
        lines.append(
            f"content changed with mtime preserved ({len(mtime_preserved)}): "
            + ", ".join(mtime_preserved[:20])
        )
    if created:
        lines.append(f"created ({len(created)}): {', '.join(created[:20])}")
    if deleted:
        lines.append(f"deleted ({len(deleted)}): {', '.join(deleted[:20])}")
    return "\n".join(lines)
