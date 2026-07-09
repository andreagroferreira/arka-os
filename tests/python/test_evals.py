"""Tests for core/evals — task schema, seed set integrity, verdict labels."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from core.evals import (
    EvalTask,
    load_eval_tasks,
    load_verdict_labels,
    record_verdict_label,
)
from core.evals.schema import DEFAULT_EVALS_DIR
from core.governance.qg_verdict import QGEvidenceSummary, QGVerdict

REPO_DEPARTMENTS = Path(__file__).parent.parent.parent / "departments"


class TestSchema:
    def test_valid_task(self):
        task = EvalTask(
            id="dev-sample",
            department="dev",
            prompt="Implementa uma feature qualquer com testes.",
            expected_properties=["testes correm com exit 0"],
        )
        assert task.rubric == ""

    def test_rejects_bad_id(self):
        with pytest.raises(ValidationError):
            EvalTask(
                id="Bad_ID",
                department="dev",
                prompt="Prompt suficientemente longo.",
                expected_properties=["x"],
            )

    def test_rejects_empty_properties(self):
        with pytest.raises(ValidationError):
            EvalTask(
                id="dev-x",
                department="dev",
                prompt="Prompt suficientemente longo.",
                expected_properties=[],
            )


class TestSeedSet:
    def test_seed_set_loads_and_validates(self):
        tasks = load_eval_tasks()
        assert len(tasks) >= 10, "seed set shrank below 2 tasks x 5 departments"

    def test_seed_departments_are_real(self):
        real = {p.name for p in REPO_DEPARTMENTS.iterdir() if p.is_dir()}
        for task in load_eval_tasks():
            assert task.department in real, (
                f"{task.id}: unknown department {task.department!r}"
            )

    def test_duplicate_ids_fail_loudly(self, tmp_path):
        dup = (
            "- id: dev-dup\n  department: dev\n"
            "  prompt: Prompt suficientemente longo.\n"
            "  expected_properties: [x]\n"
        )
        (tmp_path / "a.yaml").write_text(dup, encoding="utf-8")
        (tmp_path / "b.yaml").write_text(dup, encoding="utf-8")
        with pytest.raises(ValueError, match="duplicate eval task id"):
            load_eval_tasks(tmp_path)

    def test_default_dir_is_config_evals(self):
        assert DEFAULT_EVALS_DIR.name == "evals"
        assert DEFAULT_EVALS_DIR.parent.name == "config"


def _verdict(v: str = "REJECTED") -> QGVerdict:
    return QGVerdict(
        verdict=v,
        evidence_report=QGEvidenceSummary(
            overall="fail" if v == "REJECTED" else "pass"
        ),
        reviewer="cqo-marta",
        model_used="opus",
    )


class TestVerdictLabels:
    @pytest.fixture(autouse=True)
    def _tmp_labels(self, tmp_path, monkeypatch):
        self.path = tmp_path / "qg-verdicts.jsonl"
        monkeypatch.setenv("ARKA_QG_LABELS_PATH", str(self.path))

    def test_record_and_load_roundtrip(self):
        record_verdict_label(
            _verdict(),
            deliverable="feature X",
            department="dev",
            eval_task_id="dev-feature-auth-endpoint",
            session_id="sess-1",
        )
        labels = load_verdict_labels()
        assert len(labels) == 1
        assert labels[0]["verdict"] == "REJECTED"
        assert labels[0]["eval_task_id"] == "dev-feature-auth-endpoint"
        assert labels[0]["evidence_report"]["overall"] == "fail"

    def test_never_raises_on_bad_path(self, monkeypatch):
        monkeypatch.setenv(
            "ARKA_QG_LABELS_PATH", "/proc/1/forbidden/labels.jsonl"
        )
        record_verdict_label(_verdict())  # must not raise

    def test_load_skips_malformed_lines(self):
        record_verdict_label(_verdict())
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write("not json\n")
        record_verdict_label(_verdict("APPROVED"))
        labels = load_verdict_labels()
        assert [entry["verdict"] for entry in labels] == [
            "REJECTED",
            "APPROVED",
        ]
