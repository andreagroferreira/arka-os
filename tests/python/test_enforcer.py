"""Tests for the workflow enforcement engine (enforcer.py).

Tests all 14 NON-NEGOTIABLE Constitution rules.
"""

import pytest

from core.workflow.enforcer import enforce, enforce_tool, Violation, EnforcementResult
from core.workflow.rules_registry import RULES_REGISTRY


class TestEnforcerRegistry:
    """Tests that all rules are registered."""

    def test_all_rules_registered(self):
        assert len(RULES_REGISTRY) >= 14  # At least 14 NON-NEGOTIABLE

    def test_all_rules_have_check_fn(self):
        for rule_id, rule_def in RULES_REGISTRY.items():
            assert rule_def.check_fn is not None, f"Rule {rule_id} missing check_fn"

    def test_all_rules_have_valid_severity(self):
        valid_severities = {"BLOCK", "ESCALATE", "WARN"}
        for rule_id, rule_def in RULES_REGISTRY.items():
            assert rule_def.severity in valid_severities, f"Rule {rule_id} has invalid severity"


class TestBranchIsolation:
    """Tests for branch-isolation rule."""

    def test_violation_when_commit_on_main(self):
        context = {
            "tool_name": "Bash",
            "command": "git commit -m 'fix: something'",
            "git_branch": "main",
        }
        result = enforce("Bash", context)
        assert result.blocked
        assert any(v.rule_id == "branch-isolation" for v in result.violations)

    def test_violation_when_commit_on_master(self):
        context = {
            "tool_name": "Bash",
            "command": "git commit -m 'fix: something'",
            "git_branch": "master",
        }
        result = enforce("Bash", context)
        assert result.blocked
        assert any(v.rule_id == "branch-isolation" for v in result.violations)

    def test_no_violation_on_feature_branch(self):
        context = {
            "tool_name": "Bash",
            "command": "git commit -m 'fix: something'",
            "git_branch": "feature/my-feature",
        }
        result = enforce("Bash", context)
        assert not result.blocked
        assert not any(v.rule_id == "branch-isolation" for v in result.violations)

    def test_no_violation_for_non_commit_commands(self):
        context = {
            "tool_name": "Bash",
            "command": "git status",
            "git_branch": "main",
        }
        result = enforce("Bash", context)
        assert not any(v.rule_id == "branch-isolation" for v in result.violations)


class TestObsidianOutput:
    """Tests for obsidian-output rule."""

    def test_violation_when_code_modified_without_vault_save(self):
        context = {
            "tool_name": "Write",
            "file_path": "/path/to/file.py",
            "vault_saved": False,
        }
        result = enforce("Write", context)
        assert result.blocked
        assert any(v.rule_id == "obsidian-output" for v in result.violations)

    def test_no_violation_when_vault_saved(self):
        context = {
            "tool_name": "Write",
            "file_path": "/path/to/file.py",
            "vault_saved": True,
        }
        result = enforce("Write", context)
        assert not any(v.rule_id == "obsidian-output" for v in result.violations)

    def test_no_violation_for_non_code_files(self):
        context = {
            "tool_name": "Write",
            "file_path": "/path/to/file.txt",
            "vault_saved": False,
        }
        result = enforce("Write", context)
        assert not any(v.rule_id == "obsidian-output" for v in result.violations)


class TestAuthorityBoundaries:
    """Tests for authority-boundaries rule."""

    def test_violation_when_tier2_uses_sudo(self):
        context = {
            "tool_name": "Bash",
            "command": "sudo rm /some/file",
            "agent_tier": 2,
        }
        result = enforce("Bash", context)
        assert result.escalated
        assert any(v.rule_id == "authority-boundaries" for v in result.violations)

    def test_violation_when_tier2_drops_table(self):
        context = {
            "tool_name": "Bash",
            "command": "mysql -e 'DROP TABLE users'",
            "agent_tier": 2,
        }
        result = enforce("Bash", context)
        assert result.escalated
        assert any(v.rule_id == "authority-boundaries" for v in result.violations)

    def test_no_violation_when_tier0_privileged(self):
        context = {
            "tool_name": "Bash",
            "command": "sudo rm /some/file",
            "agent_tier": 0,
        }
        result = enforce("Bash", context)
        assert not any(v.rule_id == "authority-boundaries" for v in result.violations)


class TestSecurityGate:
    """Tests for security-gate rule."""

    def test_violation_when_delivery_without_security_review(self):
        context = {
            "tool_name": "Write",
            "file_path": "/path/to/file.py",
            "workflow_phase": "delivery",
            "security_reviewed": False,
        }
        result = enforce("Write", context)
        assert result.blocked
        assert any(v.rule_id == "security-gate" for v in result.violations)

    def test_no_violation_when_security_reviewed(self):
        context = {
            "tool_name": "Write",
            "file_path": "/path/to/file.py",
            "workflow_phase": "delivery",
            "security_reviewed": True,
        }
        result = enforce("Write", context)
        assert not any(v.rule_id == "security-gate" for v in result.violations)

    def test_no_violation_outside_delivery_phase(self):
        context = {
            "tool_name": "Write",
            "file_path": "/path/to/file.py",
            "workflow_phase": "implementation",
            "security_reviewed": False,
        }
        result = enforce("Write", context)
        assert not any(v.rule_id == "security-gate" for v in result.violations)


class TestContextFirst:
    """Tests for context-first rule."""

    def test_violation_when_code_modified_without_reading_claude_md(self):
        context = {
            "tool_name": "Edit",
            "file_path": "/path/to/file.py",
            "claude_md_read": False,
        }
        result = enforce("Edit", context)
        assert result.blocked
        assert any(v.rule_id == "context-first" for v in result.violations)

    def test_no_violation_when_claude_md_read(self):
        context = {
            "tool_name": "Edit",
            "file_path": "/path/to/file.py",
            "claude_md_read": True,
        }
        result = enforce("Edit", context)
        assert not any(v.rule_id == "context-first" for v in result.violations)


class TestSolidCleanCode:
    """Tests for solid-clean-code rule."""

    def test_violation_when_god_class_detected(self):
        context = {
            "tool_name": "Write",
            "file_path": "/path/to/file.py",
            "tool_output": "class ThisIsAVeryLongClassNameThatExceedsFiftyCharactersFixItNow",
        }
        result = enforce("Write", context)
        assert result.violations
        assert any(v.rule_id == "solid-clean-code" for v in result.violations)

    def test_no_violation_for_clean_code(self):
        context = {
            "tool_name": "Write",
            "file_path": "/path/to/file.py",
            "tool_output": "class MyClass:\n    def do_something(self):\n        pass",
        }
        result = enforce("Write", context)
        assert not any(v.rule_id == "solid-clean-code" for v in result.violations)


class TestSpecDriven:
    """Tests for spec-driven rule."""

    def test_violation_when_code_modified_without_spec(self):
        context = {
            "tool_name": "Write",
            "file_path": "/path/to/file.py",
            "spec_status": "missing",
        }
        result = enforce("Write", context)
        assert result.blocked
        assert any(v.rule_id == "spec-driven" for v in result.violations)

    def test_no_violation_when_spec_completed(self):
        context = {
            "tool_name": "Write",
            "file_path": "/path/to/file.py",
            "spec_status": "completed",
        }
        result = enforce("Write", context)
        assert not any(v.rule_id == "spec-driven" for v in result.violations)


class TestHumanWriting:
    """Tests for human-writing rule."""

    def test_violation_when_ai_pattern_detected(self):
        context = {
            "tool_name": "Write",
            "file_path": "/path/to/file.md",
            "tool_output": "As an AI language model, I cannot help with this request.",
        }
        result = enforce("Write", context)
        assert result.violations
        assert any(v.rule_id == "human-writing" for v in result.violations)

    def test_no_violation_for_natural_writing(self):
        context = {
            "tool_name": "Write",
            "file_path": "/path/to/file.md",
            "tool_output": "We need to fix the bug in the authentication module. The issue is that...",
        }
        result = enforce("Write", context)
        assert not any(v.rule_id == "human-writing" for v in result.violations)

    def test_no_violation_for_code_files(self):
        context = {
            "tool_name": "Write",
            "file_path": "/path/to/file.py",
            "tool_output": "As an AI language model, I cannot help with this request.",
        }
        result = enforce("Write", context)
        assert not any(v.rule_id == "human-writing" for v in result.violations)


class TestSquadRouting:
    """Tests for squad-routing rule."""

    def test_violation_when_unknown_command_executed(self):
        context = {
            "tool_name": "Bash",
            "user_input": "/unknown-cmd arg1 arg2",
            "command": "/unknown-cmd arg1 arg2",
        }
        result = enforce("Bash", context)
        assert result.blocked
        assert any(v.rule_id == "squad-routing" for v in result.violations)

    def test_no_violation_for_department_command(self):
        for prefix in ["/dev", "/mkt", "/fin", "/strat", "/ops"]:
            context = {
                "tool_name": "Bash",
                "user_input": f"{prefix} something",
                "command": f"{prefix} something",
            }
            result = enforce("Bash", context)
            assert not any(v.rule_id == "squad-routing" for v in result.violations), (
                f"Failed for {prefix}"
            )

    def test_no_violation_for_regular_input(self):
        context = {
            "tool_name": "Bash",
            "user_input": "show me the current directory",
            "command": "pwd",
        }
        result = enforce("Bash", context)
        assert not any(v.rule_id == "squad-routing" for v in result.violations)


class TestFullVisibility:
    """Tests for full-visibility rule."""

    def test_violation_when_phase_announcements_missing(self):
        context = {
            "workflow_phase": "implementation",
            "announcements_made": [],  # missing both starting and completing
        }
        result = enforce("Bash", context)
        assert result.violations
        assert any(v.rule_id == "full-visibility" for v in result.violations)

    def test_no_violation_when_announcements_complete(self):
        context = {
            "workflow_phase": "implementation",
            "announcements_made": ["starting", "completing"],
        }
        result = enforce("Bash", context)
        assert not any(v.rule_id == "full-visibility" for v in result.violations)


class TestSequentialValidation:
    """Tests for sequential-validation rule."""

    def test_violation_when_phases_out_of_order(self):
        context = {
            "workflow_phase": "implementation",
            "completed_phases": ["implementation", "review"],  # impl completed before spec
        }
        result = enforce("Bash", context)
        assert result.blocked
        assert any(v.rule_id == "sequential-validation" for v in result.violations)

    def test_no_violation_when_phases_in_order(self):
        context = {
            "workflow_phase": "review",
            "completed_phases": ["spec", "planning", "implementation"],
        }
        result = enforce("Bash", context)
        assert not any(v.rule_id == "sequential-validation" for v in result.violations)


class TestMandatoryQA:
    """Tests for mandatory-qa rule."""

    def test_violation_when_delivery_without_tests(self):
        context = {
            "workflow_phase": "delivery",
            "tests_run": False,
        }
        result = enforce("Bash", context)
        assert result.blocked
        assert any(v.rule_id == "mandatory-qa" for v in result.violations)

    def test_violation_when_coverage_below_80(self):
        context = {
            "workflow_phase": "delivery",
            "tests_run": True,
            "test_coverage": 75,
        }
        result = enforce("Bash", context)
        assert result.blocked
        assert any(v.rule_id == "mandatory-qa" for v in result.violations)

    def test_no_violation_when_tests_pass_and_coverage_good(self):
        context = {
            "workflow_phase": "delivery",
            "tests_run": True,
            "test_coverage": 85,
        }
        result = enforce("Bash", context)
        assert not any(v.rule_id == "mandatory-qa" for v in result.violations)


class TestArkaSupremacy:
    """Tests for arka-supremacy rule."""

    def test_violation_when_context_not_injected(self):
        context = {
            "tool_name": "Bash",
            "arkos_context_injected": False,
        }
        result = enforce("Bash", context)
        assert result.blocked
        assert any(v.rule_id == "arka-supremacy" for v in result.violations)

    def test_no_violation_when_context_injected(self):
        context = {
            "tool_name": "Bash",
            "arkos_context_injected": True,
        }
        result = enforce("Bash", context)
        assert not any(v.rule_id == "arka-supremacy" for v in result.violations)


class TestContextVerification:
    """Tests for context-verification rule."""

    def test_violation_when_complex_task_without_clarifying(self):
        context = {
            "tool_name": "Bash",
            "user_input": "implement a new feature",
            "clarifying_questions_asked": False,
        }
        result = enforce("Bash", context)
        assert result.blocked
        assert any(v.rule_id == "context-verification" for v in result.violations)

    def test_no_violation_when_clarifying_asked(self):
        context = {
            "tool_name": "Bash",
            "user_input": "implement a new feature",
            "clarifying_questions_asked": True,
        }
        result = enforce("Bash", context)
        assert not any(v.rule_id == "context-verification" for v in result.violations)

    def test_no_violation_for_simple_commands(self):
        context = {
            "tool_name": "Bash",
            "user_input": "show me the weather",
            "clarifying_questions_asked": False,
        }
        result = enforce("Bash", context)
        assert not any(v.rule_id == "context-verification" for v in result.violations)


class TestForgeGovernance:
    """Tests for forge-governance rule."""

    def test_violation_when_editing_outside_forge_deliverables(self):
        context = {
            "tool_name": "Edit",
            "file_path": "/path/to/unrelated_file.py",
            "forge_active": True,
            "forge_deliverables": ["/path/to/deliverable1.py", "/path/to/deliverable2.py"],
        }
        result = enforce("Edit", context)
        assert result.blocked
        assert any(v.rule_id == "forge-governance" for v in result.violations)

    def test_no_violation_when_editing_deliverable(self):
        context = {
            "tool_name": "Edit",
            "file_path": "/path/to/deliverable1.py",
            "forge_active": True,
            "forge_deliverables": ["/path/to/deliverable1.py", "/path/to/deliverable2.py"],
        }
        result = enforce("Edit", context)
        assert not any(v.rule_id == "forge-governance" for v in result.violations)

    def test_no_violation_when_forge_not_active(self):
        context = {
            "tool_name": "Edit",
            "file_path": "/path/to/unrelated_file.py",
            "forge_active": False,
            "forge_deliverables": [],
        }
        result = enforce("Edit", context)
        assert not any(v.rule_id == "forge-governance" for v in result.violations)


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

    def test_enforce_tool_with_code_context(self):
        result = enforce_tool(
            tool_name="Write",
            file_path="/path/to/file.py",
            command="",
            user_input="/dev do something",
            claude_md_read=True,
            vault_saved=True,
            spec_status="completed",
        )
        # Should not trigger any violations with proper context
        assert not result.blocked

    def test_enforce_tool_detects_branch_isolation(self):
        result = enforce_tool(
            tool_name="Bash",
            command="git commit -m 'fix'",
            git_branch="main",
        )
        assert result.blocked
        assert any(v.rule_id == "branch-isolation" for v in result.violations)
