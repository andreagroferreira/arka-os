"""Workflow enforcement engine.

Central enforcement engine that evaluates all 14 NON-NEGOTIABLE
Constitution rules against tool operations. Returns violations
with severity classification (BLOCK, ESCALATE, WARN).

BLOCK severity = operation is halted until resolved
ESCALATE severity = operation continues but alerts Tier 0
WARN severity = non-blocking advisory
"""

import re
from typing import Any

from core.workflow.rules_registry import RULES_REGISTRY, RuleDefinition


class Violation:
    """Represents a detected rule violation."""

    def __init__(
        self,
        rule_id: str,
        rule_name: str,
        message: str,
        severity: str,
        auto_recoverable: bool,
        tool: str | None = None,
        file_path: str | None = None,
    ):
        self.rule_id = rule_id
        self.rule_name = rule_name
        self.message = message
        self.severity = severity
        self.auto_recoverable = auto_recoverable
        self.tool = tool
        self.file_path = file_path

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "message": self.message,
            "severity": self.severity,
            "auto_recoverable": self.auto_recoverable,
            "tool": self.tool,
            "file_path": self.file_path,
        }

    def __repr__(self) -> str:
        return f"Violation({self.rule_id}, {self.severity}, {self.message[:50]}...)"


class EnforcementResult:
    """Result of running enforcement checks."""

    def __init__(self):
        self.violations: list[Violation] = []
        self.blocked = False
        self.escalated = False

    def add_violation(self, violation: Violation) -> None:
        self.violations.append(violation)
        if violation.severity == "BLOCK":
            self.blocked = True
        elif violation.severity == "ESCALATE":
            self.escalated = True

    @property
    def messages(self) -> list[str]:
        return [v.message for v in self.violations]

    @property
    def blocking_messages(self) -> list[str]:
        return [v.message for v in self.violations if v.severity == "BLOCK"]


def _build_context(
    tool_name: str,
    tool_output: str = "",
    command: str = "",
    file_path: str = "",
    user_input: str = "",
    **extra: Any,
) -> dict[str, Any]:
    """Build standard context dict for rule checks."""
    return {
        "tool_name": tool_name,
        "tool_output": tool_output,
        "command": command,
        "file_path": file_path,
        "user_input": user_input,
        **extra,
    }


def _is_code_file(file_path: str) -> bool:
    """Check if file is a code file subject to enforcement."""
    code_extensions = {".py", ".js", ".ts", ".vue", ".php", ".jsx", ".tsx"}
    return any(file_path.endswith(ext) for ext in code_extensions)


def _is_text_file(file_path: str) -> bool:
    """Check if file is a text file subject to human-writing checks."""
    text_extensions = {".md", ".txt", ".json", ".yml", ".yaml"}
    return any(file_path.endswith(ext) for ext in text_extensions)


def enforce(tool_name: str, context: dict[str, Any]) -> EnforcementResult:
    """Evaluate all applicable rules against the given context.

    Args:
        tool_name: Name of the tool being executed
        context: Dict containing operation details (command, file_path, etc.)

    Returns:
        EnforcementResult with all violations found
    """
    result = EnforcementResult()

    for rule_id, rule_def in RULES_REGISTRY.items():
        try:
            violated, message = rule_def.check_fn(context)
            if violated:
                violation = Violation(
                    rule_id=rule_id,
                    rule_name=rule_def.name,
                    message=message,
                    severity=rule_def.severity,
                    auto_recoverable=rule_def.auto_recoverable,
                    tool=tool_name,
                    file_path=context.get("file_path"),
                )
                result.add_violation(violation)
        except Exception:
            pass

    return result


def enforce_tool(
    tool_name: str,
    tool_output: str = "",
    command: str = "",
    file_path: str = "",
    user_input: str = "",
    **extra: Any,
) -> EnforcementResult:
    """Convenience wrapper: build context and enforce all rules.

    Args:
        tool_name: Name of the tool (Bash, Write, Edit, etc.)
        tool_output: Output from the tool
        command: Full command executed
        file_path: File path if applicable
        user_input: Original user input
        **extra: Additional context fields

    Returns:
        EnforcementResult with all violations found
    """
    context = _build_context(
        tool_name=tool_name,
        tool_output=tool_output,
        command=command,
        file_path=file_path,
        user_input=user_input,
        **extra,
    )
    return enforce(tool_name, context)


def check_and_raise(tool_name: str, context: dict[str, Any]) -> None:
    """Enforce rules and raise if any BLOCK violation found.

    Args:
        tool_name: Name of the tool being executed
        context: Dict containing operation details

    Raises:
        ViolationError: If any BLOCK violation is detected
    """
    result = enforce(tool_name, context)
    if result.blocked:
        messages = "\n".join(result.blocking_messages)
        raise ViolationError(
            f"BLOCK violations detected:\n{messages}\n\n"
            "Operation halted. Resolve violations before proceeding."
        )


class ViolationError(Exception):
    """Raised when a BLOCK violation is detected."""

    pass


def format_violation_report(result: EnforcementResult) -> str:
    """Format violations as a human-readable report.

    Args:
        result: EnforcementResult from enforce()

    Returns:
        Formatted string with all violations grouped by severity
    """
    if not result.violations:
        return ""

    lines = ["═" * 60, "ARKAOS CONSTITUTION VIOLATIONS", "═" * 60, ""]

    blocks = [v for v in result.violations if v.severity == "BLOCK"]
    escalates = [v for v in result.violations if v.severity == "ESCALATE"]
    warns = [v for v in result.violations if v.severity == "WARN"]

    if blocks:
        lines.append("🔴 BLOCK — Operation Halted:")
        for v in blocks:
            lines.append(f"  [{v.rule_id}] {v.message}")

    if escalates:
        lines.append("🟠 ESCALATE — Tier 0 Alerted:")
        for v in escalates:
            lines.append(f"  [{v.rule_id}] {v.message}")

    if warns:
        lines.append("🟡 WARN — Advisory:")
        for v in warns:
            lines.append(f"  [{v.rule_id}] {v.message}")

    lines.append("")
    lines.append("═" * 60)

    return "\n".join(lines)
