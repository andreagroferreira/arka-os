"""Tests for the evals follow-up tooling: runner CLI, record CLI, sanitizer."""

from __future__ import annotations

import json

import pytest

from core.evals.record_cli import main as record_main
from core.evals.runner_cli import main as runner_main
from core.evals.sanitizer import (
    SanitizerConfigMissing,
    main as sanitizer_main,
    sanitize_text,
)
from core.evals.verdict_labels import load_verdict_labels


@pytest.fixture()
def tmp_labels(tmp_path, monkeypatch):
    path = tmp_path / "qg-verdicts.jsonl"
    monkeypatch.setenv("ARKA_QG_LABELS_PATH", str(path))
    yield path


def _verdict_json(verdict: str = "REJECTED") -> str:
    return json.dumps({
        "verdict": verdict,
        "evidence_report": {
            "overall": "fail" if verdict == "REJECTED" else "pass"
        },
        "reviewer": "cqo-marta",
        "model_used": "opus",
    })


class TestRecordCli:
    def test_records_valid_verdict(self, tmp_labels, tmp_path, capsys):
        verdict_file = tmp_path / "v.json"
        verdict_file.write_text(_verdict_json(), encoding="utf-8")
        rc = record_main([
            "--file", str(verdict_file),
            "--department", "dev",
            "--eval-task-id", "dev-feature-auth-endpoint",
        ])
        assert rc == 0
        out = json.loads(capsys.readouterr().out)
        assert out == {
            "recorded": True,
            "verdict": "REJECTED",
            "eval_task_id": "dev-feature-auth-endpoint",
        }
        labels = load_verdict_labels()
        assert labels[0]["department"] == "dev"

    def test_invalid_json_fails_loudly(self, tmp_labels, tmp_path, capsys):
        bad = tmp_path / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        rc = record_main(["--file", str(bad)])
        assert rc == 1
        assert "invalid QGVerdict" in capsys.readouterr().err
        assert load_verdict_labels() == []

    def test_approved_over_fail_rejected_at_validation(
        self, tmp_labels, tmp_path, capsys
    ):
        bad = tmp_path / "floor.json"
        bad.write_text(json.dumps({
            "verdict": "APPROVED",
            "evidence_report": {"overall": "fail"},
            "reviewer": "x", "model_used": "opus",
        }), encoding="utf-8")
        rc = record_main(["--file", str(bad)])
        assert rc == 1
        assert load_verdict_labels() == []

    def test_kind_judge_records_to_judge_corpus(
        self, tmp_path, monkeypatch, capsys
    ):
        judge_path = tmp_path / "judge-verdicts.jsonl"
        monkeypatch.setenv("ARKA_JUDGE_LABELS_PATH", str(judge_path))
        verdict_file = tmp_path / "j.json"
        verdict_file.write_text(json.dumps({
            "gate": "G2", "role": "plan-judge", "verdict": "PASS",
            "reviewer": "plan-judge-g2", "model_used": "opus",
        }), encoding="utf-8")
        rc = record_main([
            "--kind", "judge", "--file", str(verdict_file),
            "--department", "dev",
        ])
        assert rc == 0
        out = json.loads(capsys.readouterr().out)
        assert out == {"recorded": True, "verdict": "PASS", "gate": "G2"}
        assert judge_path.exists()

    def test_kind_judge_rejects_qg_shaped_payload(
        self, tmp_path, monkeypatch, capsys
    ):
        monkeypatch.setenv(
            "ARKA_JUDGE_LABELS_PATH", str(tmp_path / "j.jsonl")
        )
        verdict_file = tmp_path / "qg.json"
        verdict_file.write_text(_verdict_json(), encoding="utf-8")
        rc = record_main(["--kind", "judge", "--file", str(verdict_file)])
        assert rc == 1
        assert "invalid JudgeVerdict" in capsys.readouterr().err


class TestRunnerCli:
    def test_list_shows_seed_tasks(self, capsys):
        assert runner_main(["list"]) == 0
        out = capsys.readouterr().out
        assert "dev-feature-auth-endpoint" in out

    def test_list_filters_by_department(self, capsys):
        # Eval tasks key on department DIRECTORY names (finance), unlike
        # the commands registry which keys on prefixes (fin) — locked by
        # test_evals.py::test_seed_departments_are_real.
        assert runner_main(["list", "--department", "finance"]) == 0
        out = capsys.readouterr().out
        assert "fin-unit-economics-saas" in out
        assert "dev-feature-auth-endpoint" not in out

    def test_status_reports_gate_progress(self, tmp_labels, capsys):
        assert runner_main(["status"]) == 0
        out = capsys.readouterr().out
        assert "labels: 0 (gate: 500" in out

    def test_prompt_emits_dispatchable_run(self, capsys):
        assert runner_main(["prompt", "kb-moc-reorganize"]) == 0
        out = capsys.readouterr().out
        assert "[EVAL RUN — task kb-moc-reorganize]" in out
        assert "core.evals.record_cli" in out
        assert "--eval-task-id kb-moc-reorganize" in out

    def test_prompt_unknown_task_fails(self, capsys):
        assert runner_main(["prompt", "nope-nope"]) == 1
        assert "unknown eval task" in capsys.readouterr().err


class TestSanitizer:
    @pytest.fixture()
    def redaction_config(self, tmp_path):
        config = tmp_path / "redaction-clients.json"
        config.write_text(
            json.dumps({"clients": ["acme corp", "globex"]}),
            encoding="utf-8",
        )
        return config

    def test_redacts_with_stable_placeholders(self, redaction_config):
        clean, counts = sanitize_text(
            "O deploy da Acme Corp falhou; a Globex e a acme corp aprovaram.",
            config_path=redaction_config,
        )
        assert "Acme" not in clean and "Globex" not in clean
        assert clean.count("[CLIENT-1]") == 2
        assert clean.count("[CLIENT-2]") == 1
        assert counts == {"[CLIENT-1]": 2, "[CLIENT-2]": 1}

    def test_word_boundaries_respected(self, redaction_config):
        clean, counts = sanitize_text(
            "globexpert is not a client name.", config_path=redaction_config
        )
        assert clean == "globexpert is not a client name."
        assert counts == {}

    # QG blocker pack (2026-07-09): the positional subn loop leaked on
    # these exact shapes — locked as regressions.
    def _config(self, tmp_path, clients):
        config = tmp_path / "clients.json"
        config.write_text(json.dumps({"clients": clients}), encoding="utf-8")
        return config

    def test_prefix_pattern_first_never_leaks_the_suffix(self, tmp_path):
        config = self._config(tmp_path, ["data", "data dynamics corp"])
        clean, counts = sanitize_text(
            "incident at data dynamics corp escalated",
            config_path=config,
        )
        assert clean == "incident at [CLIENT-2] escalated"
        assert "dynamics" not in clean
        assert counts == {"[CLIENT-2]": 1}

    def test_placeholder_text_never_rematched(self, tmp_path):
        config = self._config(tmp_path, ["acme", "client"])
        clean, _ = sanitize_text("acme is here", config_path=config)
        assert clean == "[CLIENT-1] is here"

    def test_overlapping_patterns_take_the_longest(self, tmp_path):
        config = self._config(tmp_path, ["acme", "acme corp"])
        clean, counts = sanitize_text(
            "acme corp hired acme", config_path=config
        )
        assert clean == "[CLIENT-2] hired [CLIENT-1]"
        assert counts == {"[CLIENT-1]": 1, "[CLIENT-2]": 1}

    def test_placeholders_keyed_to_config_position_survive_appends(
        self, tmp_path
    ):
        before = self._config(tmp_path, ["globex"])
        clean_before, _ = sanitize_text("globex ok", config_path=before)
        after = self._config(tmp_path, ["globex", "initech"])
        clean_after, _ = sanitize_text("globex ok", config_path=after)
        assert clean_before == clean_after == "[CLIENT-1] ok"

    def test_missing_config_fails_closed(self, tmp_path):
        with pytest.raises(SanitizerConfigMissing):
            sanitize_text("anything", config_path=tmp_path / "absent.json")

    def test_cli_exit_2_without_config(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(
            "core.governance.leak_scanner._DEFAULT_CONFIG_PATH",
            tmp_path / "absent.json",
        )
        monkeypatch.setattr("sys.stdin", type("S", (), {
            "read": staticmethod(lambda: "text")
        })())
        assert sanitizer_main([]) == 2
        assert "refusing to sanitize" in capsys.readouterr().err
