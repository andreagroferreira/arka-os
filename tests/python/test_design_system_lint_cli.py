"""Tests for core.governance.design_system_lint_cli (PR6 v3.77.0).

Covers Marta QG-PR6 backlog #1: the senior-dev's smoke test ran 4/4 with
no violations rendered, leaving `_print_text` and `_print_json` without
automated coverage when violations DO exist. These tests close that gap.
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import pytest
import yaml

from core.governance import design_system_lint_cli


def _write_yaml(root: Path, spec: dict) -> None:
    (root / "design-system.yaml").write_text(
        yaml.safe_dump(spec), encoding="utf-8"
    )


def _write_file(root: Path, rel_path: str, content: str) -> None:
    path = root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _violating_project(tmp_path) -> Path:
    _write_yaml(
        tmp_path,
        {
            "version": 1,
            "file_globs": ["**/*.vue"],
            "forbidden_patterns": [
                {
                    "pattern": r"#[a-fA-F0-9]{6}\b",
                    "suggestion": "Use bg-primary token instead",
                }
            ],
        },
    )
    _write_file(tmp_path, "App.vue", "color: #ff0000")
    _write_file(tmp_path, "src/Card.vue", "border: #abcdef")
    return tmp_path


# ─── Empty-project paths ────────────────────────────────────────────────


def test_clean_project_text_prints_no_violations(tmp_path, capsys):
    exit_code = design_system_lint_cli.main([str(tmp_path)])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "No design-system violations" in captured.out


def test_clean_project_json_prints_empty(tmp_path, capsys):
    exit_code = design_system_lint_cli.main(
        [str(tmp_path), "--format", "json"]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    # The clean-project JSON path emits a single object; parse it.
    payload = json.loads(captured.out.strip().splitlines()[-1])
    assert payload.get("count") == 0


# ─── Violating-project paths ────────────────────────────────────────────


def test_violations_text_shows_file_line_and_suggestion(tmp_path, capsys):
    _violating_project(tmp_path)
    exit_code = design_system_lint_cli.main([str(tmp_path)])
    captured = capsys.readouterr()
    # Without --exit-on-violations, exit is 0 even with violations
    assert exit_code == 0
    # Both files surface
    assert "App.vue" in captured.out
    assert "src/Card.vue" in captured.out
    # The suggestion is rendered
    assert "Use bg-primary token instead" in captured.out


def test_violations_json_emits_per_violation_records(tmp_path, capsys):
    _violating_project(tmp_path)
    exit_code = design_system_lint_cli.main(
        [str(tmp_path), "--format", "json"]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    lines = [
        line for line in captured.out.strip().splitlines() if line.strip()
    ]
    # Expect at least one violation record + one summary line
    records = [json.loads(line) for line in lines]
    summary = [r for r in records if r.get("summary")]
    violations = [r for r in records if not r.get("summary")]
    assert len(violations) == 2
    assert summary and summary[0].get("count") == 2


# ─── Exit-on-violations flag ────────────────────────────────────────────


def test_exit_on_violations_returns_1_when_violations(tmp_path):
    _violating_project(tmp_path)
    exit_code = design_system_lint_cli.main(
        [str(tmp_path), "--exit-on-violations"]
    )
    assert exit_code == 1


def test_exit_on_violations_returns_0_when_clean(tmp_path):
    exit_code = design_system_lint_cli.main(
        [str(tmp_path), "--exit-on-violations"]
    )
    assert exit_code == 0
