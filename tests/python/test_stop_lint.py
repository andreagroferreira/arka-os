"""Stop-lint detached worker + telemetry summarizer.

All projects are tmp_path fixtures; the evidence engine is
monkeypatched (no real linters run). Never touches ~/.arkaos or this
repo's own tree: config/telemetry/state paths are injected or
redirected per test.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from core.governance import stop_lint, stop_lint_telemetry
from core.governance.evidence_checks import CheckResult, EvidenceReport

# ─── fixtures ───────────────────────────────────────────────────────────


@pytest.fixture()
def git_repo(tmp_path: Path) -> Path:
    """Real git repo on master with one committed file."""
    repo = tmp_path / "proj"
    repo.mkdir()
    _git(repo, "init", "-b", "master")
    _git(repo, "config", "user.email", "t@t.local")
    _git(repo, "config", "user.name", "t")
    (repo / "clean.py").write_text("x = 1\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base", "--no-gpg-sign")
    return repo


@pytest.fixture()
def isolated_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect the /tmp coordination dirs into tmp_path."""
    state_base = tmp_path / "arka-tmp"
    monkeypatch.setattr(
        stop_lint, "arkaos_temp_dir",
        lambda *parts: state_base.joinpath(*parts),
    )
    monkeypatch.delenv("ARKA_STOP_LINT", raising=False)
    return state_base


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True,
    )


def _fake_report(overall: str = "pass", *, passed: bool = True) -> EvidenceReport:
    return EvidenceReport(
        project_dir="x",
        overall=overall,
        results=[
            CheckResult(
                check="lint", ran=True, passed=passed,
                command="lint(scoped: 1 file(s)) ruff check clean.py",
                exit_code=0 if passed else 1, summary="ok" if passed else "E501",
            )
        ],
    )


# ─── mode / flags ───────────────────────────────────────────────────────


def test_mode_defaults_to_warn_without_config(tmp_path, monkeypatch):
    monkeypatch.delenv("ARKA_STOP_LINT", raising=False)
    assert stop_lint.mode(tmp_path / "missing.json") == "warn"


@pytest.mark.parametrize("value", [False, "off", "OFF"])
def test_mode_off_via_config(tmp_path, monkeypatch, value):
    monkeypatch.delenv("ARKA_STOP_LINT", raising=False)
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"hooks": {"stopLint": value}}), encoding="utf-8")
    assert stop_lint.mode(cfg) == "off"


def test_mode_env_killswitch_wins(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKA_STOP_LINT", "0")
    assert stop_lint.mode(tmp_path / "missing.json") == "off"


def test_mode_corrupt_config_defaults_warn(tmp_path, monkeypatch):
    monkeypatch.delenv("ARKA_STOP_LINT", raising=False)
    cfg = tmp_path / "config.json"
    cfg.write_text("{not json", encoding="utf-8")
    assert stop_lint.mode(cfg) == "warn"


# ─── changed_files ──────────────────────────────────────────────────────


def test_changed_files_modified_and_untracked(git_repo):
    (git_repo / "clean.py").write_text("x = 2\n", encoding="utf-8")
    (git_repo / "new.py").write_text("y = 1\n", encoding="utf-8")
    files = stop_lint.changed_files(git_repo)
    assert "clean.py" in files
    assert "new.py" in files


def test_changed_files_clean_tree_empty(git_repo):
    assert stop_lint.changed_files(git_repo) == []


def test_changed_files_outside_repo_empty(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    assert stop_lint.changed_files(plain) == []


# ─── run() ──────────────────────────────────────────────────────────────


def test_run_appends_entry_and_result_state(
    git_repo, tmp_path, monkeypatch, isolated_state,
):
    (git_repo / "clean.py").write_text("x = 2\n", encoding="utf-8")
    captured: dict = {}

    def fake_checks(project_dir, changed_files=None, checks=None, **kw):
        captured["checks"] = checks
        captured["changed"] = changed_files
        return _fake_report("pass")

    monkeypatch.setattr(stop_lint, "run_evidence_checks", fake_checks)
    telemetry = tmp_path / "stop-lint.jsonl"
    rc = stop_lint.run(
        git_repo, "sess-abc123",
        config_path=tmp_path / "missing.json", telemetry_path=telemetry,
    )
    assert rc == 0
    assert captured["checks"] == ["lint"]
    assert "clean.py" in captured["changed"]
    lines = telemetry.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["event"] == "stop-lint"
    assert entry["mode"] == "warn"
    assert entry["overall"] == "pass"
    assert entry["would_block"] is False
    assert entry["lint_passed"] is True
    assert entry["changed_count"] >= 1
    result_state = isolated_state / "arkaos-stop-lint-result" / "sess-abc123.json"
    assert result_state.is_file()
    assert json.loads(result_state.read_text(encoding="utf-8"))["overall"] == "pass"


def test_run_would_block_on_fail(git_repo, tmp_path, monkeypatch, isolated_state):
    (git_repo / "clean.py").write_text("x = 2\n", encoding="utf-8")
    monkeypatch.setattr(
        stop_lint, "run_evidence_checks",
        lambda *a, **k: _fake_report("fail", passed=False),
    )
    telemetry = tmp_path / "stop-lint.jsonl"
    stop_lint.run(
        git_repo, "sess-abc123",
        config_path=tmp_path / "missing.json", telemetry_path=telemetry,
    )
    entry = json.loads(telemetry.read_text(encoding="utf-8").strip())
    assert entry["overall"] == "fail"
    assert entry["would_block"] is True


def test_run_skips_engine_on_clean_tree(
    git_repo, tmp_path, monkeypatch, isolated_state,
):
    def boom(*a, **k):  # engine must never run without changed files
        raise AssertionError("engine ran on a clean tree")

    monkeypatch.setattr(stop_lint, "run_evidence_checks", boom)
    telemetry = tmp_path / "stop-lint.jsonl"
    stop_lint.run(
        git_repo, "sess-abc123",
        config_path=tmp_path / "missing.json", telemetry_path=telemetry,
    )
    entry = json.loads(telemetry.read_text(encoding="utf-8").strip())
    assert entry["overall"] == "skipped"
    assert entry["skip_reason"] == "no-changed-files"
    assert entry["would_block"] is False


def test_run_coalesces_unchanged_fingerprint(
    git_repo, tmp_path, monkeypatch, isolated_state,
):
    (git_repo / "clean.py").write_text("x = 2\n", encoding="utf-8")
    monkeypatch.setattr(
        stop_lint, "run_evidence_checks", lambda *a, **k: _fake_report("pass"),
    )
    telemetry = tmp_path / "stop-lint.jsonl"
    kwargs = {
        "config_path": tmp_path / "missing.json", "telemetry_path": telemetry,
    }
    stop_lint.run(git_repo, "sess-abc123", **kwargs)
    stop_lint.run(git_repo, "sess-abc123", **kwargs)
    lines = telemetry.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    # A new tree change re-arms the worker.
    (git_repo / "clean.py").write_text("x = 3\n", encoding="utf-8")
    stop_lint.run(git_repo, "sess-abc123", **kwargs)
    lines = telemetry.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2


def test_run_mode_off_is_noop(git_repo, tmp_path, monkeypatch, isolated_state):
    monkeypatch.setattr(
        stop_lint, "run_evidence_checks",
        lambda *a, **k: pytest.fail("engine ran with stopLint off"),
    )
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"hooks": {"stopLint": False}}), encoding="utf-8")
    telemetry = tmp_path / "stop-lint.jsonl"
    stop_lint.run(
        git_repo, "sess-abc123", config_path=cfg, telemetry_path=telemetry,
    )
    assert not telemetry.exists()


def test_run_typecheck_opt_in(git_repo, tmp_path, monkeypatch, isolated_state):
    (git_repo / "clean.py").write_text("x = 2\n", encoding="utf-8")
    captured: dict = {}

    def fake_checks(project_dir, changed_files=None, checks=None, **kw):
        captured["checks"] = checks
        return _fake_report("pass")

    monkeypatch.setattr(stop_lint, "run_evidence_checks", fake_checks)
    cfg = tmp_path / "config.json"
    cfg.write_text(
        json.dumps({"hooks": {"stopLintTypecheck": True}}), encoding="utf-8",
    )
    stop_lint.run(
        git_repo, "sess-abc123",
        config_path=cfg, telemetry_path=tmp_path / "t.jsonl",
    )
    assert captured["checks"] == ["lint", "typecheck"]


def test_run_unsafe_session_id_still_logs_telemetry(
    git_repo, tmp_path, monkeypatch, isolated_state,
):
    (git_repo / "clean.py").write_text("x = 2\n", encoding="utf-8")
    monkeypatch.setattr(
        stop_lint, "run_evidence_checks", lambda *a, **k: _fake_report("pass"),
    )
    telemetry = tmp_path / "stop-lint.jsonl"
    stop_lint.run(
        git_repo, "../../etc/passwd",
        config_path=tmp_path / "missing.json", telemetry_path=telemetry,
    )
    assert telemetry.exists()
    assert not (isolated_state / "arkaos-stop-lint-result").exists()


def test_changed_files_non_ascii_and_spaced_names(git_repo):
    # core.quotePath octal-escapes non-ASCII in line-based porcelain/diff
    # output; -z returns raw paths. Regression for the quoted-path bug.
    (git_repo / "café.py").write_text("y = 1\n", encoding="utf-8")
    (git_repo / "sp ace.py").write_text("z = 1\n", encoding="utf-8")
    files = stop_lint.changed_files(git_repo)
    assert "café.py" in files
    assert "sp ace.py" in files


def test_porcelain_entries_skip_rename_origin():
    stdout = "R  new.py\0old.py\0?? plain.py\0 M dirty.py\0"
    entries = stop_lint._porcelain_entries(stdout)
    assert ("R ", "new.py") in entries
    assert ("??", "plain.py") in entries
    assert (" M", "dirty.py") in entries
    assert all(path != "old.py" for _, path in entries)


def test_remember_fingerprint_is_atomic_and_leaves_no_tmp(tmp_path):
    state_file = tmp_path / "state" / "abc.json"
    stop_lint._remember_fingerprint(state_file, "deadbeef")
    assert state_file.is_file()
    assert stop_lint._seen_fingerprint(state_file) == "deadbeef"
    leftovers = [p for p in state_file.parent.iterdir() if p != state_file]
    assert leftovers == []



# ─── stop hook enqueue ──────────────────────────────────────────────────


def test_stop_hook_enqueues_detached_worker(tmp_path, monkeypatch):
    from core.hooks import stop as stop_hook

    spawned: dict = {}

    class FakePopen:
        def __init__(self, argv, **kwargs):
            spawned["argv"] = argv
            spawned["kwargs"] = kwargs

    monkeypatch.setattr(subprocess, "Popen", FakePopen)
    monkeypatch.setattr(
        "core.governance.stop_lint.mode", lambda config_path=None: "warn",
    )
    # repo_path() resolves ~/.arkaos on operator machines but not in CI —
    # pin it so the test is environment-independent (same as the
    # turn-capture enqueue tests in test_stop_hook.py).
    monkeypatch.setattr(stop_hook, "repo_path", lambda: str(tmp_path))
    stop_hook._enqueue_stop_lint("sess-abc123", str(tmp_path))
    assert "core.governance.stop_lint" in spawned["argv"]
    assert str(tmp_path) in spawned["argv"]
    assert "sess-abc123" in spawned["argv"]
    assert spawned["kwargs"].get("start_new_session") is True


def test_stop_hook_skips_enqueue_when_off(tmp_path, monkeypatch):
    from core.hooks import stop as stop_hook

    monkeypatch.setattr(
        subprocess, "Popen",
        lambda *a, **k: pytest.fail("spawned with stopLint off"),
    )
    monkeypatch.setattr(
        "core.governance.stop_lint.mode", lambda config_path=None: "off",
    )
    stop_hook._enqueue_stop_lint("sess-abc123", str(tmp_path))


def test_stop_hook_skips_enqueue_without_cwd(monkeypatch):
    from core.hooks import stop as stop_hook

    monkeypatch.setattr(
        subprocess, "Popen",
        lambda *a, **k: pytest.fail("spawned without a cwd"),
    )
    stop_hook._enqueue_stop_lint("sess-abc123", "")


# ─── CLI ────────────────────────────────────────────────────────────────


def test_main_without_args_is_noop():
    assert stop_lint.main([]) == 0


def test_main_swallows_worker_errors(tmp_path, monkeypatch):
    monkeypatch.setattr(
        stop_lint, "run", lambda *a, **k: (_ for _ in ()).throw(RuntimeError),
    )
    assert stop_lint.main([str(tmp_path), "sess-abc123"]) == 0


# ─── summariser ─────────────────────────────────────────────────────────


def _entry(**overrides) -> str:
    base = {
        "ts": "2099-01-01T00:00:00+00:00",
        "event": "stop-lint",
        "overall": "pass",
        "would_block": False,
        "lint_passed": True,
    }
    base.update(overrides)
    return json.dumps(base)


def test_summarise_rates(tmp_path):
    path = tmp_path / "stop-lint.jsonl"
    path.write_text(
        "\n".join(
            [
                _entry(),
                _entry(overall="fail", would_block=True, lint_passed=False),
                _entry(overall="skipped", would_block=False, lint_passed=None),
                "{corrupt",
                json.dumps({"event": "other"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    summary = stop_lint_telemetry.summarise("all", path=path)
    assert summary.runs == 3
    assert summary.skipped_runs == 1
    assert summary.lint_pass_rate == 0.5
    assert summary.would_block_rate == 0.5
    assert summary.corrupt_line_count == 1
    # typecheck never observed in these entries -> honest None, not 0.0
    assert summary.typecheck_pass_rate is None


def test_summarise_typecheck_rate_when_observed(tmp_path):
    path = tmp_path / "stop-lint.jsonl"
    path.write_text(
        _entry(typecheck_passed=True) + "\n"
        + _entry(typecheck_passed=False) + "\n",
        encoding="utf-8",
    )
    summary = stop_lint_telemetry.summarise("all", path=path)
    assert summary.typecheck_pass_rate == 0.5


def test_summarise_missing_file_zero(tmp_path):
    summary = stop_lint_telemetry.summarise("today", path=tmp_path / "n.jsonl")
    assert summary.runs == 0
    assert summary.lint_pass_rate == 0.0


def test_summarise_invalid_period_raises(tmp_path):
    with pytest.raises(ValueError):
        stop_lint_telemetry.summarise("fortnight", path=tmp_path / "n.jsonl")


def test_summarise_period_cutoff_excludes_old(tmp_path):
    path = tmp_path / "stop-lint.jsonl"
    path.write_text(
        _entry(ts="2000-01-01T00:00:00+00:00") + "\n" + _entry() + "\n",
        encoding="utf-8",
    )
    summary = stop_lint_telemetry.summarise("week", path=path)
    assert summary.runs == 1
