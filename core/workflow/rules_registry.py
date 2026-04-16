"""Workflow enforcement rules registry.

Defines all 14 NON-NEGOTIABLE Constitution rules with their
violation triggers, auto-recovery suggestions, and severity classification.

Each rule has:
  - id: Unique identifier
  - name: Human-readable name
  - trigger: What causes a violation
  - check: Function to evaluate violation
  - recovery: Function to attempt auto-fix
  - severity: BLOCK | ESCALATE
  - description: What the rule enforces
"""

from dataclasses import dataclass
from typing import Callable, Optional, Any


@dataclass
class RuleDefinition:
    """Definition of a single enforcement rule."""

    id: str
    name: str
    description: str
    trigger_patterns: list[str]
    check_fn: Callable[[dict], tuple[bool, str]]
    recovery_fn: Optional[Callable[[dict], str]] = None
    severity: str = "BLOCK"
    auto_recoverable: bool = True


def _check_branch_isolation(context: dict) -> tuple[bool, str]:
    """Check if commit was made on protected branch while workflow active."""
    tool = context.get("tool_name", "")
    output = context.get("tool_output", "")
    command = context.get("command", "")

    if tool == "Bash" and "git commit" in command:
        branch = context.get("git_branch", "")
        if branch in ("main", "master", "dev", ""):
            return (
                True,
                f"VIOLATION [branch-isolation]: Commit on {branch} while workflow active. Use feature branch.",
            )
    return False, ""


def _check_obsidian_output(context: dict) -> tuple[bool, str]:
    """Check if code was modified without vault save step."""
    tool = context.get("tool_name", "")
    if tool in ("Write", "Edit"):
        file_path = context.get("file_path", "")
        if any(
            file_path.endswith(ext) for ext in [".py", ".js", ".ts", ".vue", ".php", ".jsx", ".tsx"]
        ):
            if not context.get("vault_saved", False):
                return (
                    True,
                    f"VIOLATION [obsidian-output]: {file_path} modified without vault save.",
                )
    return False, ""


def _check_authority_boundaries(context: dict) -> tuple[bool, str]:
    """Check if Tier 2 agent attempted privileged operation."""
    agent_tier = context.get("agent_tier", 2)
    tool = context.get("tool_name", "")
    command = context.get("command", "")

    privileged_tools = {"sudo", "chmod", "chown", "delete_branch", "force_push"}
    privileged_commands = {"DROP TABLE", "TRUNCATE", "rm -rf /", "git push --force"}

    if agent_tier > 0:
        if tool in privileged_tools:
            return (
                True,
                f"VIOLATION [authority-boundaries]: Tier {agent_tier} agent attempted privileged operation: {tool}",
            )
        if any(cmd in command.upper() for cmd in privileged_commands):
            return (
                True,
                f"VIOLATION [authority-boundaries]: Tier {agent_tier} agent attempted privileged command",
            )

    if agent_tier > 0 and "Bash" in tool and ("sudo" in command or "chmod 777" in command):
        return True, f"VIOLATION [authority-boundaries]: Privileged shell command attempted"

    return False, ""


def _check_security_gate(context: dict) -> tuple[bool, str]:
    """Check if code shipped without security audit."""
    tool = context.get("tool_name", "")
    output = context.get("tool_output", "")
    phase = context.get("workflow_phase", "")

    if phase == "delivery" and tool in ("Write", "Edit"):
        if not context.get("security_reviewed", False):
            return True, "VIOLATION [security-gate]: Code shipping without OWASP security audit"
    return False, ""


def _check_context_first(context: dict) -> tuple[bool, str]:
    """Check if project context was read before code modification."""
    tool = context.get("tool_name", "")
    if tool in ("Write", "Edit"):
        file_path = context.get("file_path", "")
        if any(
            file_path.endswith(ext) for ext in [".py", ".js", ".ts", ".vue", ".php", ".jsx", ".tsx"]
        ):
            if not context.get("claude_md_read", False):
                return (
                    True,
                    f"VIOLATION [context-first]: {file_path} modified without reading CLAUDE.md first",
                )
    return False, ""


def _check_solid_clean_code(context: dict) -> tuple[bool, str]:
    """Check for SOLID/Clean Code violations."""
    tool = context.get("tool_name", "")
    output = context.get("tool_output", "")

    code_smells = [
        ("God Class", r"class \w{50,}"),
        ("Long Method", r"def \w+\([^)]{100,}\)"),
        ("Magic Number", r"[0-9]{5,}"),
        ("Nested Ifs", r"if .+:\s+if .+:\s+if .+:"),
    ]

    if tool in ("Write", "Edit"):
        for smell_name, pattern in code_smells:
            import re

            if re.search(pattern, output):
                return True, f"VIOLATION [solid-clean-code]: Code smell detected: {smell_name}"

    return False, ""


def _check_spec_driven(context: dict) -> tuple[bool, str]:
    """Check if code modified without completed spec."""
    tool = context.get("tool_name", "")
    if tool in ("Write", "Edit"):
        file_path = context.get("file_path", "")
        if any(
            file_path.endswith(ext) for ext in [".py", ".js", ".ts", ".vue", ".php", ".jsx", ".tsx"]
        ):
            spec_status = context.get("spec_status", "missing")
            if spec_status != "completed":
                return (
                    True,
                    f"VIOLATION [spec-driven]: {file_path} modified without completed spec (status: {spec_status})",
                )
    return False, ""


def _check_human_writing(context: dict) -> tuple[bool, str]:
    """Check for AI patterns in text output."""
    tool = context.get("tool_name", "")

    if tool in ("Write", "Edit"):
        file_path = context.get("file_path", "")
        if file_path.endswith((".md", ".txt", ".json")):
            content = context.get("tool_output", "")
            ai_patterns = [
                "As an AI language model",
                "I'm sorry, but I cannot",
                "Please note that",
                "It is important to note",
                "Additionally,",
                "In conclusion,",
                "Furthermore,",
                "Moreover,",
            ]
            for pattern in ai_patterns:
                if pattern.lower() in content.lower():
                    return True, f"VIOLATION [human-writing]: AI pattern detected: '{pattern}'"

    return False, ""


def _check_squad_routing(context: dict) -> tuple[bool, str]:
    """Check if non-department command was executed without routing."""
    command = context.get("command", "")
    user_input = context.get("user_input", "")

    explicit_prefixes = {
        "/dev",
        "/mkt",
        "/fin",
        "/strat",
        "/ops",
        "/ecom",
        "/kb",
        "/brand",
        "/saas",
        "/landing",
        "/content",
        "/community",
        "/sales",
        "/lead",
        "/org",
        "/do",
        "/arka",
        "/qa",
    }

    if user_input.startswith("/"):
        prefix = user_input.split()[0] if " " in user_input else user_input
        if prefix not in explicit_prefixes and not any(
            user_input.startswith(p) for p in explicit_prefixes
        ):
            return (
                True,
                f"VIOLATION [squad-routing]: Command '{prefix}' executed without squad routing",
            )

    return False, ""


def _check_full_visibility(context: dict) -> tuple[bool, str]:
    """Check if phase announcements were made."""
    phase = context.get("workflow_phase", "")
    announcements = context.get("announcements_made", [])

    required_announcements = ["starting", "completing"]
    if phase and not all(ann in announcements for ann in required_announcements):
        return True, f"VIOLATION [full-visibility]: Phase '{phase}' missing required announcements"

    return False, ""


def _check_sequential_validation(context: dict) -> tuple[bool, str]:
    """Check if tasks executed in correct order."""
    current_phase = context.get("workflow_phase", "")
    completed_phases = context.get("completed_phases", [])

    phase_order = ["spec", "planning", "implementation", "review", "qa", "delivery"]

    if current_phase:
        current_idx = phase_order.index(current_phase) if current_phase in phase_order else -1
        for completed in completed_phases:
            if completed in phase_order:
                completed_idx = phase_order.index(completed)
                if completed_idx > current_idx:
                    return (
                        True,
                        f"VIOLATION [sequential-validation]: Phase '{current_phase}' started before '{completed}' completed",
                    )

    return False, ""


def _check_mandatory_qa(context: dict) -> tuple[bool, str]:
    """Check if full test suite was run before delivery."""
    phase = context.get("workflow_phase", "")
    if phase == "delivery":
        if not context.get("tests_run", False):
            return (
                True,
                "VIOLATION [mandatory-qa]: Delivery attempted without running full test suite",
            )
        if context.get("test_coverage", 0) < 80:
            return (
                True,
                f"VIOLATION [mandatory-qa]: Test coverage {context.get('test_coverage')}% below 80% threshold",
            )
    return False, ""


def _check_arka_supremacy(context: dict) -> tuple[bool, str]:
    """Check if ArkaOS context was used over runtime defaults."""
    context_injected = context.get("arkos_context_injected", True)
    if not context_injected:
        return True, "VIOLATION [arka-supremacy]: Operation without ArkaOS context override"
    return False, ""


def _check_context_verification(context: dict) -> tuple[bool, str]:
    """Check if clarifying questions were asked before execution."""
    user_input = context.get("user_input", "")
    clarifying_asked = context.get("clarifying_questions_asked", False)

    complex_commands = {"implement", "create", "build", "design", "architect", "develop"}
    if any(cmd in user_input.lower() for cmd in complex_commands):
        if not clarifying_asked:
            return (
                True,
                "VIOLATION [context-verification]: Complex task executed without clarifying questions",
            )
    return False, ""


def _check_forge_governance(context: dict) -> tuple[bool, str]:
    """Check if Forge plan violations occurred."""
    forge_active = context.get("forge_active", False)
    tool = context.get("tool_name", "")
    file_path = context.get("file_path", "")

    if forge_active and tool in ("Write", "Edit"):
        forge_deliverables = context.get("forge_deliverables", [])
        if forge_deliverables:
            is_deliverable = any(
                file_path.endswith(d) or d in file_path for d in forge_deliverables
            )
            if not is_deliverable:
                return (
                    True,
                    f"VIOLATION [forge-governance]: {file_path} outside Forge plan deliverables",
                )

    return False, ""


RULES_REGISTRY: dict[str, RuleDefinition] = {
    "branch-isolation": RuleDefinition(
        id="branch-isolation",
        name="Branch Isolation",
        description="All code-modifying work runs on dedicated feature branches",
        trigger_patterns=["git commit on main/master/dev"],
        check_fn=_check_branch_isolation,
        recovery_fn=None,
        severity="BLOCK",
        auto_recoverable=False,
    ),
    "obsidian-output": RuleDefinition(
        id="obsidian-output",
        name="Obsidian Output",
        description="All department output is saved to the Obsidian vault",
        trigger_patterns=["code modification without vault save"],
        check_fn=_check_obsidian_output,
        recovery_fn=None,
        severity="BLOCK",
        auto_recoverable=True,
    ),
    "authority-boundaries": RuleDefinition(
        id="authority-boundaries",
        name="Authority Boundaries",
        description="Agents operate within their tier authority",
        trigger_patterns=["privileged operations by Tier 2+"],
        check_fn=_check_authority_boundaries,
        recovery_fn=None,
        severity="ESCALATE",
        auto_recoverable=False,
    ),
    "security-gate": RuleDefinition(
        id="security-gate",
        name="Security Gate",
        description="No code ships without OWASP security audit",
        trigger_patterns=["delivery without security review"],
        check_fn=_check_security_gate,
        recovery_fn=None,
        severity="BLOCK",
        auto_recoverable=False,
    ),
    "context-first": RuleDefinition(
        id="context-first",
        name="Context First",
        description="Always read project context before modifying code",
        trigger_patterns=["code modification without reading CLAUDE.md"],
        check_fn=_check_context_first,
        recovery_fn=None,
        severity="BLOCK",
        auto_recoverable=True,
    ),
    "solid-clean-code": RuleDefinition(
        id="solid-clean-code",
        name="SOLID/Clean Code",
        description="SOLID principles and Clean Code enforced on all code",
        trigger_patterns=["code smells detected"],
        check_fn=_check_solid_clean_code,
        recovery_fn=None,
        severity="WARN",
        auto_recoverable=False,
    ),
    "spec-driven": RuleDefinition(
        id="spec-driven",
        name="Spec Driven",
        description="No code is written until a detailed spec exists",
        trigger_patterns=["code modification without completed spec"],
        check_fn=_check_spec_driven,
        recovery_fn=None,
        severity="BLOCK",
        auto_recoverable=False,
    ),
    "human-writing": RuleDefinition(
        id="human-writing",
        name="Human Writing",
        description="All text output reads as naturally human-written",
        trigger_patterns=["AI patterns detected in text"],
        check_fn=_check_human_writing,
        recovery_fn=None,
        severity="WARN",
        auto_recoverable=True,
    ),
    "squad-routing": RuleDefinition(
        id="squad-routing",
        name="Squad Routing",
        description="Every request routes through the appropriate department squad",
        trigger_patterns=["non-department command without routing"],
        check_fn=_check_squad_routing,
        recovery_fn=None,
        severity="BLOCK",
        auto_recoverable=False,
    ),
    "full-visibility": RuleDefinition(
        id="full-visibility",
        name="Full Visibility",
        description="Every phase announces what is starting and what resulted",
        trigger_patterns=["phase without announcements"],
        check_fn=_check_full_visibility,
        recovery_fn=None,
        severity="WARN",
        auto_recoverable=True,
    ),
    "sequential-validation": RuleDefinition(
        id="sequential-validation",
        name="Sequential Validation",
        description="Task N+1 only starts after Task N is complete",
        trigger_patterns=["task executed out of order"],
        check_fn=_check_sequential_validation,
        recovery_fn=None,
        severity="BLOCK",
        auto_recoverable=False,
    ),
    "mandatory-qa": RuleDefinition(
        id="mandatory-qa",
        name="Mandatory QA",
        description="QA runs ALL tests every time",
        trigger_patterns=["delivery without tests or coverage < 80%"],
        check_fn=_check_mandatory_qa,
        recovery_fn=None,
        severity="BLOCK",
        auto_recoverable=False,
    ),
    "arka-supremacy": RuleDefinition(
        id="arka-supremacy",
        name="ArkaOS Supremacy",
        description="ArkaOS instructions override runtime defaults",
        trigger_patterns=["operation without ArkaOS context"],
        check_fn=_check_arka_supremacy,
        recovery_fn=None,
        severity="BLOCK",
        auto_recoverable=True,
    ),
    "context-verification": RuleDefinition(
        id="context-verification",
        name="Context Verification",
        description="Orchestrators must confirm understanding before executing",
        trigger_patterns=["complex task without clarifying questions"],
        check_fn=_check_context_verification,
        recovery_fn=None,
        severity="BLOCK",
        auto_recoverable=True,
    ),
    "forge-governance": RuleDefinition(
        id="forge-governance",
        name="Forge Governance",
        description="Forge plans must pass critic validation before approval",
        trigger_patterns=["file edited outside Forge deliverables"],
        check_fn=_check_forge_governance,
        recovery_fn=None,
        severity="BLOCK",
        auto_recoverable=False,
    ),
}


def get_all_rules() -> dict[str, RuleDefinition]:
    """Get all registered rules."""
    return RULES_REGISTRY


def get_rule(rule_id: str) -> RuleDefinition | None:
    """Get a specific rule by ID."""
    return RULES_REGISTRY.get(rule_id)


def get_rules_by_severity(severity: str) -> list[RuleDefinition]:
    """Get all rules with a specific severity."""
    return [r for r in RULES_REGISTRY.values() if r.severity == severity]
