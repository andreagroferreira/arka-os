"""Gotchas auto-recovery system.

Provides automatic recovery from common development errors by:
1. Loading known fix patterns from gotchas-fixes.json
2. Matching error output against patterns
3. Suggesting or automatically applying fixes

This is ALWAYS active (SIM) per Sprint 3 decision.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class FixPattern:
    """A known error pattern and its corresponding fix."""

    pattern_match: str
    category: str
    suggestion: str
    confidence: str


@dataclass
class RecoveryAction:
    """A recovery action to be taken."""

    pattern: FixPattern
    suggested_fix: str
    auto_apply: bool
    reason: str


class GotchasRecovery:
    """Auto-recovery from known error patterns."""

    def __init__(self, fixes_path: str | None = None):
        self.fixes: list[FixPattern] = []
        if fixes_path:
            self.load_fixes(fixes_path)

    def load_fixes(self, path: str) -> None:
        """Load fix patterns from JSON file."""
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            self.fixes = [
                FixPattern(
                    pattern_match=fix["pattern_match"],
                    category=fix["category"],
                    suggestion=fix["suggestion"],
                    confidence=fix.get("confidence", "medium"),
                )
                for fix in data.get("fixes", [])
            ]
        except (FileNotFoundError, json.JSONDecodeError):
            self.fixes = []

    @classmethod
    def from_config(cls, config_paths: list[str] | None = None) -> "GotchasRecovery":
        """Create from standard config locations."""
        if config_paths is None:
            config_paths = [
                str(Path.home() / ".claude" / "skills" / "arka" / "config" / "gotchas-fixes.json"),
                str(Path(__file__).parent.parent.parent / "config" / "gotchas-fixes.json"),
            ]

        for path in config_paths:
            if Path(path).exists():
                instance = cls(path)
                if instance.fixes:
                    return instance
        return cls()

    def match(self, error_output: str) -> list[FixPattern]:
        """Match error output against known patterns.

        Args:
            error_output: The error text to match

        Returns:
            List of matching FixPattern objects, sorted by confidence
        """
        matches = []
        for fix in self.fixes:
            try:
                if re.search(fix.pattern_match, error_output, re.IGNORECASE):
                    matches.append(fix)
            except re.error:
                pass

        matches.sort(key=lambda f: {"high": 0, "medium": 1, "low": 2}.get(f.confidence, 3))
        return matches

    def suggest(self, error_output: str) -> list[RecoveryAction]:
        """Suggest recovery actions for an error.

        Args:
            error_output: The error text to analyze

        Returns:
            List of RecoveryAction objects
        """
        matches = self.match(error_output)
        actions = []

        for pattern in matches:
            action = RecoveryAction(
                pattern=pattern,
                suggested_fix=pattern.suggestion,
                auto_apply=pattern.confidence == "high",
                reason=f"{pattern.category} error matched (confidence: {pattern.confidence})",
            )
            actions.append(action)

        return actions

    def get_suggestion(self, error_output: str) -> str | None:
        """Get the highest confidence suggestion for an error.

        Args:
            error_output: The error text to analyze

        Returns:
            The suggestion string, or None if no match
        """
        suggestions = self.suggest(error_output)
        return suggestions[0].suggested_fix if suggestions else None


_RECOVERY_INSTANCE: GotchasRecovery | None = None


def get_recovery() -> GotchasRecovery:
    """Get the global GotchasRecovery instance (singleton)."""
    global _RECOVERY_INSTANCE
    if _RECOVERY_INSTANCE is None:
        _RECOVERY_INSTANCE = GotchasRecovery.from_config()
    return _RECOVERY_INSTANCE


def suggest_fix(error_output: str) -> str | None:
    """Convenience function to get a fix suggestion for an error.

    Args:
        error_output: The error text to analyze

    Returns:
        The suggestion string, or None if no known fix
    """
    return get_recovery().get_suggestion(error_output)


def get_recovery_actions(error_output: str) -> list[RecoveryAction]:
    """Convenience function to get all recovery actions for an error.

    Args:
        error_output: The error text to analyze

    Returns:
        List of RecoveryAction objects
    """
    return get_recovery().suggest(error_output)


def extract_error_line(output: str) -> str | None:
    """Extract the first meaningful error line from output.

    Args:
        output: Raw command output

    Returns:
        First error line, or None if no error found
    """
    error_patterns = [
        r"(?i)(error|fatal|exception|failed|ENOENT|EACCES|EPERM|panic):?\s*(.+)",
        r"(?i)(cannot find|cannot open|not found|not defined|permission denied)[:\s]+(.+)",
    ]

    for pattern in error_patterns:
        match = re.search(pattern, output)
        if match:
            return match.group(0)

    lines = output.split("\n")
    for line in lines:
        line = line.strip()
        if line and not line.startswith("#") and not line.startswith("//"):
            if any(kw in line.lower() for kw in ["error", "fail", "exception", "denied"]):
                return line

    return None
