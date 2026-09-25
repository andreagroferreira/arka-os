"""#573: slop-score reads a whole file only when git said "untracked" (exit 1).

``evidence_checks._git_tracks`` used to read every non-zero exit of
``git ls-files --error-unmatch`` as "untracked", and ``slop_check.prose_text``
then read the allowlisted file whole: a git too old for
``--literal-pathspecs`` (exit 129 on every call) or a name git spells
differently (``x.md/``) widened the read past the diff. Each row names the
mutant it kills.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

from core.governance import evidence_checks, slop_check

LEGACY = "Legacy paragraph nobody touched in this change.\n"
ADDED = "A fresh sentence this change added.\n"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@example.invalid", "-c", "user.name=t", *args],
        cwd=repo, check=True, capture_output=True,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A committed ``x.md`` and ``a.py``, both changed, plus an untracked ``new.md``."""
    root = tmp_path / "repo"
    root.mkdir()
    (root / "x.md").write_text(LEGACY, encoding="utf-8")
    (root / "a.py").write_text("A = 1\n", encoding="utf-8")
    _git(root, "init", "-q", "-b", "master")
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "base")
    (root / "x.md").write_text(LEGACY + ADDED, encoding="utf-8")
    (root / "a.py").write_text("A = 1\nB: int = 'x'\n", encoding="utf-8")
    (root / "new.md").write_text("Untracked prose, all of it new.\n", encoding="utf-8")
    return root


@pytest.fixture
def old_git(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A ``git`` on PATH that exits 129 on ``--literal-pathspecs``, like a git before 1.8.

    Every other call reaches the real git, so ``_diff_base`` still finds
    the merge-base: only the literal calls fail, as on the old binary.
    """
    real = shutil.which("git")
    assert real is not None
    bindir = tmp_path / "oldgit"
    bindir.mkdir()
    shim = bindir / "git"
    shim.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "--literal-pathspecs" ]; then\n'
        '  echo "unknown option: --literal-pathspecs" >&2; exit 129\n'
        "fi\n"
        f'exec "{real}" "$@"\n',
        encoding="utf-8",
    )
    shim.chmod(shim.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("PATH", f"{bindir}{os.pathsep}{os.environ['PATH']}")


def _no_whole_read(monkeypatch: pytest.MonkeyPatch) -> None:
    """Any read of a file's text from here on fails the test (git's reads are subprocesses)."""
    def refuse(self: Path, *_args: object, **_kwargs: object) -> str:
        raise AssertionError(f"prose_text read {self.name} whole")

    monkeypatch.setattr(Path, "read_text", refuse)
    monkeypatch.setattr(Path, "open", refuse)


def _base(repo: Path) -> str:
    base = evidence_checks._diff_base(repo)
    assert base is not None
    return base


# --- the probe: only exit 1 is "untracked" ----------------------------------

def test_an_old_git_probe_is_no_answer(repo, old_git):
    # Kills: the probe rule reverted to ``returncode == 0`` (129 → False).
    assert evidence_checks._git_tracks(repo, "x.md") is None


def test_the_probe_keeps_exit_zero_and_one(repo):
    assert evidence_checks._git_tracks(repo, "x.md") is True
    assert evidence_checks._git_tracks(repo, "new.md") is False


def test_a_probe_that_cannot_run_is_no_answer(repo, monkeypatch):
    # Kills: ``except (OSError, TimeoutExpired)`` answering False again.
    def boom(*_args: object, **_kwargs: object) -> None:
        raise subprocess.TimeoutExpired("git", 10)

    monkeypatch.setattr(evidence_checks.literal_git, "run", boom)
    assert evidence_checks._git_tracks(repo, "x.md") is None


# --- slop-score: no whole-file read without a real "untracked" --------------

def test_an_old_git_never_reads_the_whole_file(repo, old_git, monkeypatch):
    # Kills: the probe rule reverted to ``!= 0``, or prose_text reading None as False.
    base = _base(repo)
    _no_whole_read(monkeypatch)
    assert slop_check.prose_text(repo, base, "x.md") == ("", "path-class")
    assert slop_check.prose_text(repo, base, "new.md") == ("", "path-class")


@pytest.mark.parametrize("name", ["x.md/", "./x.md", "x.md//", "new.md/"])
def test_a_name_not_in_gits_spelling_is_never_read(repo, monkeypatch, name):
    # Kills: the spelling guard removed (``x.md/`` is "untracked" to git
    # and resolves to the tracked x.md on disk, which was then read whole).
    _no_whole_read(monkeypatch)
    assert slop_check.prose_text(repo, _base(repo), name) == ("", "path-class")


def test_a_real_untracked_file_is_still_read_whole(repo):
    text, scope = slop_check.prose_text(repo, _base(repo), "new.md")
    assert (text, scope) == ("Untracked prose, all of it new.\n", "whole file")


def test_a_tracked_file_still_scores_only_its_added_lines(repo):
    text, scope = slop_check.prose_text(repo, _base(repo), "x.md")
    assert scope == "added lines" and text == ADDED.rstrip("\n")
    assert "Legacy" not in text


def test_without_a_merge_base_the_file_is_read_whole_as_before(repo):
    text, scope = slop_check.prose_text(repo, None, "x.md")
    assert scope == "whole file" and text == LEGACY + ADDED


# --- typecheck / spellcheck scoping under the old git -----------------------

MYPY_LINE = "a.py:2: error: Incompatible types in assignment"


def test_typecheck_scoping_fails_closed_under_an_old_git(repo, old_git, monkeypatch):
    # An unanswered probe is not "tracked": no diff is asked, the file is
    # unattributable and its finding gates (never filed as master's debt).
    calls: list[str] = []
    monkeypatch.setattr(evidence_checks, "_added_lines",
                        lambda *a: calls.append(a[2]) or [])
    base = _base(repo)
    assert evidence_checks._added_line_numbers(repo, base, "a.py") is None
    assert calls == []
    attribution = evidence_checks._attribute_hits(
        repo, MYPY_LINE, evidence_checks._MYPY_ERROR_RE)
    assert attribution == ([MYPY_LINE], [], ["a.py"])


def test_spellcheck_attribution_fails_closed_under_an_old_git(repo, old_git):
    hit = "x.md:2: fresh ==> afresh"
    attribution = evidence_checks._attribute_hits(
        repo, hit, evidence_checks._CODESPELL_HIT_RE)
    assert attribution == ([hit], [], ["x.md"])


def test_scoping_keeps_its_answers_for_exit_zero_and_one(repo):
    base = _base(repo)
    assert evidence_checks._added_line_numbers(repo, base, "a.py") == {2}
    assert evidence_checks._added_line_numbers(repo, base, "new.md") is None
    attribution = evidence_checks._attribute_hits(
        repo, "a.py:1: error: old\n" + MYPY_LINE, evidence_checks._MYPY_ERROR_RE)
    assert attribution == ([MYPY_LINE], ["a.py:1: error: old"], [])


def test_security_grep_scans_the_whole_file_under_an_old_git(repo, old_git):
    # The third scoping caller: no answer keeps the whole-file scan (#481's
    # fail-closed contract), and the file is listed as undescribable.
    result = evidence_checks._check_security_grep(repo, ["a.py"], None, 30)
    assert "a.py" in result.summary and "could not describe" in result.summary
