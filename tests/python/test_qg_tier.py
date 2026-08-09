"""Mechanical QG tier (Gate Economy PR-6) — the tier derives from the
real diff and every uncertainty fails closed to FULL; the same
primitives finally count [arka:trivial]'s one-file/10-line claim."""

from __future__ import annotations

import os
import subprocess

import pytest

from core.governance.qg_tier import (
    FILES_LIGHT_MAX,
    LINES_LIGHT_MAX,
    TRIVIAL_MAX_LINES,
    compute_tier,
    main,
    validate_trivial,
)


def _git(cwd, *args):
    subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
        },
    )


@pytest.fixture()
def repo(tmp_path):
    _git(tmp_path, "init", "-q", "-b", "master")
    (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# readme\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "base")
    _git(tmp_path, "checkout", "-qb", "feature")
    return tmp_path


class TestComputeTier:
    def test_small_code_diff_is_light_for_francisca(self, repo):
        (repo / "app.py").write_text("x = 2\n", encoding="utf-8")
        result = compute_tier(repo)
        assert result["tier"] == "LIGHT"
        assert result["reviewer"] == "francisca-tech"
        assert result["delta_kind"] == "code"

    def test_small_prose_diff_is_light_for_eduardo(self, repo):
        (repo / "README.md").write_text("# changed\n", encoding="utf-8")
        result = compute_tier(repo)
        assert result["tier"] == "LIGHT"
        assert result["reviewer"] == "eduardo-copy"

    def test_mixed_diff_is_full(self, repo):
        (repo / "app.py").write_text("x = 2\n", encoding="utf-8")
        (repo / "README.md").write_text("# changed\n", encoding="utf-8")
        result = compute_tier(repo)
        assert result["tier"] == "FULL"
        assert result["reviewer"] is None

    def test_sensitive_path_is_full(self, repo):
        target = repo / "core" / "governance" / "gate.py"
        target.parent.mkdir(parents=True)
        target.write_text("x = 1\n", encoding="utf-8")
        result = compute_tier(repo)
        assert result["tier"] == "FULL"
        assert "sensitive" in result["reasons"][0]

    def test_env_and_dockerfile_are_sensitive(self, repo):
        (repo / ".env.local").write_text("A=1\n", encoding="utf-8")
        assert compute_tier(repo)["tier"] == "FULL"

    def test_too_many_files_is_full(self, repo):
        for n in range(FILES_LIGHT_MAX + 1):
            (repo / f"mod{n}.py").write_text("x = 1\n", encoding="utf-8")
        result = compute_tier(repo)
        assert result["tier"] == "FULL"
        assert f"> {FILES_LIGHT_MAX}" in result["reasons"][0]

    def test_too_many_lines_is_full(self, repo):
        body = "\n".join(f"x{n} = {n}" for n in range(LINES_LIGHT_MAX + 1))
        (repo / "app.py").write_text(body + "\n", encoding="utf-8")
        result = compute_tier(repo)
        assert result["tier"] == "FULL"
        assert "changed lines" in result["reasons"][0]

    def test_no_repo_is_full(self, tmp_path):
        result = compute_tier(tmp_path)
        assert result["tier"] == "FULL"
        assert "fails closed" in result["reasons"][0]

    def test_untracked_new_file_counts_lines(self, repo):
        (repo / "new.py").write_text(
            "\n".join("y = 1" for _ in range(LINES_LIGHT_MAX + 1)) + "\n",
            encoding="utf-8",
        )
        assert compute_tier(repo)["tier"] == "FULL"


class TestValidateTrivial:
    def test_one_small_file_is_trivial(self, repo):
        (repo / "app.py").write_text("x = 2\n", encoding="utf-8")
        result = validate_trivial(repo)
        assert result["trivial"] is True
        assert result["file"] == "app.py"

    def test_two_files_are_not_trivial(self, repo):
        (repo / "app.py").write_text("x = 2\n", encoding="utf-8")
        (repo / "b.py").write_text("y = 1\n", encoding="utf-8")
        assert validate_trivial(repo)["trivial"] is False

    def test_eleven_lines_are_not_trivial(self, repo):
        body = "\n".join(
            f"x{n} = {n}" for n in range(TRIVIAL_MAX_LINES + 1)
        )
        (repo / "app.py").write_text(body + "\n", encoding="utf-8")
        result = validate_trivial(repo)
        assert result["trivial"] is False
        assert f"> {TRIVIAL_MAX_LINES}" in result["reason"]

    def test_no_diff_is_not_trivial(self, repo):
        assert validate_trivial(repo)["trivial"] is False

    def test_no_repo_is_not_trivial(self, tmp_path):
        assert validate_trivial(tmp_path)["trivial"] is False


class TestCli:
    def test_tier_json(self, repo, capsys):
        (repo / "app.py").write_text("x = 2\n", encoding="utf-8")
        import json

        assert main([str(repo)]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["tier"] == "LIGHT"

    def test_trivial_json(self, repo, capsys):
        (repo / "app.py").write_text("x = 2\n", encoding="utf-8")
        import json

        assert main([str(repo), "--trivial"]) == 0
        assert json.loads(capsys.readouterr().out)["trivial"] is True
