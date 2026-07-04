"""Tests for the workflow enforcement engine (enforcer.py).

Structural honesty PR-2: the registry only keeps disk-verifiable rules
(branch-isolation, spec-driven, mandatory-qa) and every test exercises
REAL state — tmp_path fixtures for disk evidence and a stubbed
subprocess for git branch reads. Behavioral rules were deleted from the
registry (enforced by hooks/telemetry) and their tests removed.
"""

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.workflow.enforcer import enforce, enforce_tool, Violation, EnforcementResult
from core.workflow.rules_registry import RULES_REGISTRY


def _stub_git_branch(
    monkeypatch: pytest.MonkeyPatch,
    branch: str | None,
    returncode: int = 0,
    calls: list | None = None,
) -> None:
    """Stub the read-only git branch subprocess in the rules registry."""

    def fake_run(cmd, **kwargs):
        if calls is not None:
            calls.append(cmd)
        if branch is None:
            raise OSError("git not available")
        return SimpleNamespace(returncode=returncode, stdout=f"{branch}\n", stderr="")

    monkeypatch.setattr("core.workflow.rules_registry.subprocess.run", fake_run)


def _write_spec(specs_dir: Path, name: str, status: str) -> None:
    specs_dir.mkdir(parents=True, exist_ok=True)
    (specs_dir / name).write_text(
        f"id: spec-001\ntitle: Test Spec\nstatus: {status}\n", encoding="utf-8"
    )


def _write_coverage_xml(cwd: Path, line_rate: float) -> None:
    (cwd / "coverage.xml").write_text(
        f'<?xml version="1.0"?>\n<coverage line-rate="{line_rate}" branch-rate="0.8">\n'
        "</coverage>\n",
        encoding="utf-8",
    )


class TestEnforcerRegistry:
    """The registry holds ONLY disk-verifiable rules."""

    def test_registry_contains_exactly_disk_verifiable_rules(self):
        assert set(RULES_REGISTRY) == {"branch-isolation", "spec-driven", "mandatory-qa"}

    def test_all_rules_have_check_fn(self):
        for rule_id, rule_def in RULES_REGISTRY.items():
            assert rule_def.check_fn is not None, f"Rule {rule_id} missing check_fn"

    def test_all_rules_have_valid_severity(self):
        valid_severities = {"BLOCK", "ESCALATE", "WARN"}
        for rule_id, rule_def in RULES_REGISTRY.items():
            assert rule_def.severity in valid_severities, f"Rule {rule_id} has invalid severity"

    def test_behavioral_rules_are_deleted_not_stubbed(self):
        for removed in (
            "human-writing",
            "squad-routing",
            "full-visibility",
            "context-verification",
            "arka-supremacy",
            "obsidian-output",
        ):
            assert removed not in RULES_REGISTRY


class TestBranchIsolation:
    """branch-isolation reads the REAL branch from git, never a caller string."""

    def test_violation_when_commit_on_main(self, tmp_path, monkeypatch):
        _stub_git_branch(monkeypatch, "main")
        context = {
            "tool_name": "Bash",
            "command": "git commit -m 'fix: something'",
            "cwd": str(tmp_path),
        }
        result = enforce("Bash", context)
        assert result.blocked
        assert any(v.rule_id == "branch-isolation" for v in result.violations)

    def test_violation_when_commit_on_master(self, tmp_path, monkeypatch):
        _stub_git_branch(monkeypatch, "master")
        context = {
            "tool_name": "Bash",
            "command": "git commit -m 'fix: something'",
            "cwd": str(tmp_path),
        }
        result = enforce("Bash", context)
        assert result.blocked

    def test_caller_supplied_branch_is_ignored(self, tmp_path, monkeypatch):
        """A caller claiming a feature branch cannot mask a real main commit."""
        _stub_git_branch(monkeypatch, "main")
        context = {
            "tool_name": "Bash",
            "command": "git commit -m 'fix'",
            "git_branch": "feature/lying-caller",
            "cwd": str(tmp_path),
        }
        result = enforce("Bash", context)
        assert any(v.rule_id == "branch-isolation" for v in result.violations)

    def test_no_violation_on_feature_branch(self, tmp_path, monkeypatch):
        _stub_git_branch(monkeypatch, "feature/my-feature")
        context = {
            "tool_name": "Bash",
            "command": "git commit -m 'fix: something'",
            "cwd": str(tmp_path),
        }
        result = enforce("Bash", context)
        assert not result.blocked

    def test_no_violation_for_non_commit_commands(self, tmp_path, monkeypatch):
        calls: list = []
        _stub_git_branch(monkeypatch, "main", calls=calls)
        context = {"tool_name": "Bash", "command": "git status", "cwd": str(tmp_path)}
        result = enforce("Bash", context)
        assert not any(v.rule_id == "branch-isolation" for v in result.violations)
        assert calls == []  # branch is not even read for non-commit commands

    def test_no_violation_when_git_unavailable(self, tmp_path, monkeypatch):
        _stub_git_branch(monkeypatch, None)
        context = {
            "tool_name": "Bash",
            "command": "git commit -m 'fix'",
            "cwd": str(tmp_path),
        }
        result = enforce("Bash", context)
        assert not any(v.rule_id == "branch-isolation" for v in result.violations)

    def test_no_violation_when_git_errors(self, tmp_path, monkeypatch):
        _stub_git_branch(monkeypatch, "fatal: not a git repo", returncode=128)
        context = {
            "tool_name": "Bash",
            "command": "git commit -m 'fix'",
            "cwd": str(tmp_path),
        }
        result = enforce("Bash", context)
        assert not any(v.rule_id == "branch-isolation" for v in result.violations)


class TestSpecDriven:
    """spec-driven checks an approved spec YAML actually exists on disk."""

    def test_violation_when_no_spec_dir(self, tmp_path):
        context = {
            "tool_name": "Write",
            "file_path": "/path/to/file.py",
            "cwd": str(tmp_path),
        }
        result = enforce("Write", context)
        assert result.blocked
        assert any(v.rule_id == "spec-driven" for v in result.violations)

    def test_no_violation_with_approved_spec_on_disk(self, tmp_path):
        _write_spec(tmp_path / ".arkaos" / "specs", "feature.yaml", "approved")
        context = {
            "tool_name": "Write",
            "file_path": "/path/to/file.py",
            "cwd": str(tmp_path),
        }
        result = enforce("Write", context)
        assert not any(v.rule_id == "spec-driven" for v in result.violations)

    def test_no_violation_with_in_progress_spec(self, tmp_path):
        _write_spec(tmp_path / ".arkaos" / "specs", "feature.yml", "in_progress")
        context = {
            "tool_name": "Edit",
            "file_path": "/path/to/file.ts",
            "cwd": str(tmp_path),
        }
        result = enforce("Edit", context)
        assert not any(v.rule_id == "spec-driven" for v in result.violations)

    def test_violation_when_only_draft_spec(self, tmp_path):
        _write_spec(tmp_path / ".arkaos" / "specs", "feature.yaml", "draft")
        context = {
            "tool_name": "Write",
            "file_path": "/path/to/file.py",
            "cwd": str(tmp_path),
        }
        result = enforce("Write", context)
        assert any(v.rule_id == "spec-driven" for v in result.violations)

    def test_no_violation_for_non_code_files(self, tmp_path):
        context = {
            "tool_name": "Write",
            "file_path": "/path/to/notes.md",
            "cwd": str(tmp_path),
        }
        result = enforce("Write", context)
        assert not any(v.rule_id == "spec-driven" for v in result.violations)

    def test_specs_dir_override_honored(self, tmp_path):
        custom = tmp_path / "custom-specs"
        _write_spec(custom, "feature.yaml", "approved")
        context = {
            "tool_name": "Write",
            "file_path": "/path/to/file.py",
            "cwd": str(tmp_path),
            "specs_dir": str(custom),
        }
        result = enforce("Write", context)
        assert not any(v.rule_id == "spec-driven" for v in result.violations)


class TestMandatoryQA:
    """mandatory-qa requires test evidence on disk — booleans are not trusted."""

    def test_violation_when_no_evidence_on_disk(self, tmp_path):
        context = {
            "tool_name": "Bash",
            "workflow_phase": "delivery",
            "cwd": str(tmp_path),
        }
        result = enforce("Bash", context)
        assert result.blocked
        violations = [v for v in result.violations if v.rule_id == "mandatory-qa"]
        assert violations and "no test evidence on disk" in violations[0].message

    def test_caller_boolean_cannot_fake_evidence(self, tmp_path):
        context = {
            "tool_name": "Bash",
            "workflow_phase": "delivery",
            "tests_run": True,
            "test_coverage": 95,
            "cwd": str(tmp_path),
        }
        result = enforce("Bash", context)
        assert any(v.rule_id == "mandatory-qa" for v in result.violations)

    def test_no_violation_outside_delivery_phase(self, tmp_path):
        context = {
            "tool_name": "Bash",
            "workflow_phase": "implementation",
            "cwd": str(tmp_path),
        }
        result = enforce("Bash", context)
        assert not any(v.rule_id == "mandatory-qa" for v in result.violations)

    def test_no_violation_with_good_coverage_xml(self, tmp_path):
        _write_coverage_xml(tmp_path, 0.92)
        context = {
            "tool_name": "Bash",
            "workflow_phase": "delivery",
            "cwd": str(tmp_path),
        }
        result = enforce("Bash", context)
        assert not any(v.rule_id == "mandatory-qa" for v in result.violations)

    def test_violation_with_low_coverage_xml(self, tmp_path):
        _write_coverage_xml(tmp_path, 0.55)
        context = {
            "tool_name": "Bash",
            "workflow_phase": "delivery",
            "cwd": str(tmp_path),
        }
        result = enforce("Bash", context)
        violations = [v for v in result.violations if v.rule_id == "mandatory-qa"]
        assert violations and "below 80%" in violations[0].message

    def test_pytest_cache_counts_as_evidence(self, tmp_path):
        (tmp_path / ".pytest_cache").mkdir()
        context = {
            "tool_name": "Bash",
            "workflow_phase": "delivery",
            "cwd": str(tmp_path),
        }
        result = enforce("Bash", context)
        assert not any(v.rule_id == "mandatory-qa" for v in result.violations)


class TestEnforcementResult:
    """Tests for EnforcementResult and Violation classes."""

    def test_violation_to_dict(self):
        v = Violation(
            rule_id="test-rule",
            rule_name="Test Rule",
            message="Test violation",
            severity="BLOCK",
            auto_recoverable=True,
            tool="Bash",
            file_path="/path/to/file.py",
        )
        d = v.to_dict()
        assert d["rule_id"] == "test-rule"
        assert d["severity"] == "BLOCK"
        assert d["auto_recoverable"] is True

    def test_enforcement_result_blocked_flag(self):
        result = EnforcementResult()
        result.add_violation(Violation("r1", "Rule 1", "msg", "BLOCK", False))
        assert result.blocked is True
        assert result.escalated is False

    def test_enforcement_result_escalated_flag(self):
        result = EnforcementResult()
        result.add_violation(Violation("r1", "Rule 1", "msg", "ESCALATE", False))
        assert result.blocked is False
        assert result.escalated is True

    def test_enforcement_result_messages(self):
        result = EnforcementResult()
        result.add_violation(Violation("r1", "Rule 1", "msg1", "WARN", False))
        result.add_violation(Violation("r2", "Rule 2", "msg2", "BLOCK", False))
        assert len(result.messages) == 2
        assert "msg1" in result.messages
        assert "msg2" in result.messages

    def test_enforcement_result_blocking_messages(self):
        result = EnforcementResult()
        result.add_violation(Violation("r1", "Rule 1", "msg1", "WARN", False))
        result.add_violation(Violation("r2", "Rule 2", "msg2", "BLOCK", False))
        assert len(result.blocking_messages) == 1
        assert "msg2" in result.blocking_messages


class TestEnforceTool:
    """Tests for the convenience wrapper enforce_tool()."""

    def test_enforce_tool_with_approved_spec(self, tmp_path):
        _write_spec(tmp_path / ".arkaos" / "specs", "feature.yaml", "approved")
        result = enforce_tool(
            tool_name="Write",
            file_path="/path/to/file.py",
            command="",
            user_input="/dev do something",
            cwd=str(tmp_path),
        )
        assert not result.blocked

    def test_enforce_tool_detects_branch_isolation(self, tmp_path, monkeypatch):
        _stub_git_branch(monkeypatch, "main")
        result = enforce_tool(
            tool_name="Bash",
            command="git commit -m 'fix'",
            cwd=str(tmp_path),
        )
        assert result.blocked
        assert any(v.rule_id == "branch-isolation" for v in result.violations)

    def test_enforce_swallows_check_exceptions(self, tmp_path, monkeypatch):
        def boom(context):
            raise RuntimeError("check exploded")

        monkeypatch.setattr(
            RULES_REGISTRY["branch-isolation"], "check_fn", boom
        )
        result = enforce_tool(tool_name="Bash", command="git commit -m x", cwd=str(tmp_path))
        assert not any(v.rule_id == "branch-isolation" for v in result.violations)
