"""The ``slop-score`` evidence section (JEV PR3, site #11).

Jev is mocked at ``urlopen``. The contract under test: minor severity,
never flips the overall, never counts as evidence on its own, auto-skips
without prose, fail-closed without the redaction list, silent under the
bypass.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from _decisions_helpers import fake_ok, isolate_decisions, sent_payload

from core.decisions.sites.quality import MAX_PROSE_CHARS, SLOP_DIMENSIONS
from core.governance import evidence_checks as ec
from core.governance import slop_check as sc

URLOPEN = "core.decisions.client.urllib.request.urlopen"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@example.invalid", "-c", "user.name=t", *args],
        cwd=repo, check=True, capture_output=True,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "docs").mkdir(parents=True)
    (root / "docs" / "guide.md").write_text("# Guide\n\nOld line.\n", encoding="utf-8")
    _git(root, "init", "-q", "-b", "master")
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "base")
    (root / "docs" / "guide.md").write_text(
        "# Guide\n\nOld line.\nA new sentence the change added.\n", encoding="utf-8")
    (root / "README.txt").write_text("A brand new untracked note.\n", encoding="utf-8")
    return root


@pytest.fixture
def jev(monkeypatch, tmp_path):
    return isolate_decisions(monkeypatch, tmp_path)


def _scores(level: int, conf: float = 0.9) -> object:
    """Every dimension at 0-based ``level`` (1-10 score = level + 1)."""
    return fake_ok({f"slop_score__{d}": {"type": "score", "score": level, "confidence": conf}
                    for d in SLOP_DIMENSIONS})


PROSE = ["docs/guide.md", "README.txt"]


# --- registration -------------------------------------------------------------

def test_section_is_registered_minor_and_advisory_only():
    assert "slop-score" in ec.ALL_CHECKS
    assert set(ec.CHECK_SEVERITY) == set(ec.ALL_CHECKS)
    assert ec.CHECK_SEVERITY["slop-score"] == "minor"
    assert ec._CHECK_DISPATCH["slop-score"] is ec._check_slop_score
    assert frozenset({"slop-score"}) == ec.ADVISORY_ONLY_CHECKS


def test_auto_skip_follows_the_spellcheck_prose_predicate():
    assert "slop-score" in ec._auto_skips(["core/x.py"])
    assert ec._auto_skips(["core/x.py"])["slop-score"] == ec._auto_skips(["core/x.py"])[
        "spellcheck"]
    for name in ("docs/a.md", "docs/a.mdx", "notes.txt"):
        assert "slop-score" not in ec._auto_skips([name])


def test_no_prose_file_is_a_skip_row(jev):
    with patch(URLOPEN) as net:
        result = sc.check_slop_score(Path("."), ["core/x.py"], None, 60)
    net.assert_not_called()
    assert (result.ran, result.summary) == (False, sc.NO_PROSE)


# --- scoring ------------------------------------------------------------------

def test_below_35_fails_the_section_but_never_the_overall(jev, repo):
    with patch(URLOPEN, return_value=_scores(4)):  # 5/10 each → 25/50
        report = ec.run_evidence_checks(repo, PROSE, checks=["slop-score"])
    result = report.results[0]
    assert (result.ran, result.passed, result.severity) == (True, False, "minor")
    assert result.findings_count == 2 and "total=25/50" in result.findings[0]
    assert report.overall != "fail"


def test_at_or_above_35_passes_with_the_five_scores(jev, repo):
    with patch(URLOPEN, return_value=_scores(6)) as net:  # 7/10 each → 35/50
        result = ec.run_evidence_checks(repo, PROSE, checks=["slop-score"]).results[0]
    assert result.passed is True and result.findings == []
    assert "total=35/50 directness=7 rhythm=7 trust=7 authenticity=7 density=7" in result.summary
    sent = {sent_payload(net, i)["state"]["prose"] for i in range(net.call_count)}
    assert sent == {"A new sentence the change added.", "A brand new untracked note.\n"}


def test_tracked_file_scores_added_lines_untracked_the_whole_file(repo):
    base = ec._diff_base(repo)
    assert sc.prose_text(repo, base, "docs/guide.md") == (
        "A new sentence the change added.", "added lines")
    assert sc.prose_text(repo, base, "README.txt")[1] == "whole file"


def test_long_prose_scores_the_first_12k_with_a_note(jev, repo):
    (repo / "long.md").write_text("word " * 5000 + "\n", encoding="utf-8")
    with patch(URLOPEN, return_value=_scores(8)) as net:
        result = sc.check_slop_score(repo, ["long.md"], None, 60)
    assert len(sent_payload(net)["state"]["prose"]) <= MAX_PROSE_CHARS
    assert f"(first {MAX_PROSE_CHARS} chars scored)" in result.summary


# --- the overall ----------------------------------------------------------------

def _row(check: str, passed: bool, severity: str) -> ec.CheckResult:
    return ec.CheckResult(check=check, ran=True, passed=passed, command="c", exit_code=0,
                          summary="", severity=severity)


def test_a_failing_slop_score_never_flips_a_passing_report():
    rows = [_row("lint", True, "major"), _row("slop-score", False, "minor")]
    assert ec._derive_overall(rows) == "pass"


def test_slop_score_alone_never_concludes_the_evidence():
    assert ec._derive_overall([_row("slop-score", True, "minor")]) == "insufficient-evidence"
    assert ec._derive_overall([_row("slop-score", False, "minor")]) == "insufficient-evidence"
    # Kills the exemption leaking to other minor checks.
    assert ec._derive_overall([_row("spellcheck", True, "minor")]) == "pass"


def test_a_real_failure_still_fails_beside_a_passing_slop_score():
    rows = [_row("tests", False, "blocker"), _row("slop-score", True, "minor")]
    assert ec._derive_overall(rows) == "fail"


# --- skips and privacy ----------------------------------------------------------

def test_without_the_redaction_list_the_section_skips_and_sends_nothing(jev, repo):
    (jev / ".arkaos" / "redaction-clients.json").unlink()
    with patch(URLOPEN) as net:
        result = sc.check_slop_score(repo, PROSE, None, 60)
    net.assert_not_called()
    assert result.ran is False and "reason=redaction-config-missing" in result.summary


def test_bypass_never_reaches_the_network(repo, monkeypatch):
    monkeypatch.setenv("ARKA_BYPASS_DECISIONS", "1")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    with patch(URLOPEN) as net:
        report = ec.run_evidence_checks(repo, PROSE, checks=["slop-score"])
    net.assert_not_called()
    row = next(r for r in report.results if r.check == "slop-score")
    assert row.ran is False and "reason=bypass" in row.summary


def test_unavailable_jev_is_a_skip_with_the_reason(jev, repo):
    with patch(URLOPEN, side_effect=OSError("down")):
        result = sc.check_slop_score(repo, PROSE, None, 60)
    assert result.ran is False and "reason=unavailable:" in result.summary


def test_abstaining_jev_scores_nothing(jev, repo):
    with patch(URLOPEN, return_value=_scores(4, conf=0.2)):
        result = sc.check_slop_score(repo, PROSE, None, 60)
    assert result.ran is False and "unavailable:abstain" in result.summary
