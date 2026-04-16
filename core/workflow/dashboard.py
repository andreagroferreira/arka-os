"""Workflow dashboard — real-time CLI view of workflow state.

Reads ~/.arkaos/workflow-state.json and displays:
- Current phase and progress
- Elapsed time
- Violations accumulated
- Completed phases
"""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def _state_path() -> Path:
    return Path.home() / ".arkaos" / "workflow-state.json"


def read_state() -> dict | None:
    """Read current workflow state."""
    path = _state_path()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def format_duration(seconds: float) -> str:
    """Format seconds as human-readable duration."""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins}m {secs}s"
    else:
        hours = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        return f"{hours}h {mins}m"


def get_elapsed(started_at: str) -> float:
    """Calculate elapsed seconds since ISO timestamp."""
    try:
        start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        return (now - start).total_seconds()
    except (ValueError, OSError):
        return 0.0


class WorkflowDashboard:
    """Display workflow status in CLI."""

    def __init__(self, state: dict | None = None):
        self.state = state or read_state()

    def is_active(self) -> bool:
        """Check if there's an active workflow."""
        return self.state is not None

    def get_current_phase(self) -> str | None:
        """Get the currently executing phase."""
        if not self.state:
            return None
        for phase_id, phase_data in self.state.get("phases", {}).items():
            if phase_data.get("status") == "in_progress":
                return phase_id
        return None

    def get_violation_count(self) -> int:
        """Get number of violations recorded."""
        if not self.state:
            return 0
        return len(self.state.get("violations", []))

    def render(self, stream: list[str] | None = None) -> list[str]:
        """Render dashboard as lines.

        Args:
            stream: Optional list to append lines to (for testing)

        Returns:
            List of formatted lines
        """
        output = stream or []

        if not self.state:
            output.append("No active workflow")
            return output

        workflow_name = self.state.get("workflow", "Unknown")
        project = self.state.get("project", "Unknown")
        started_at = self.state.get("started_at", "")
        elapsed = get_elapsed(started_at)

        output.append("─" * 50)
        output.append(f"  ARKAOS WORKFLOW DASHBOARD")
        output.append("─" * 50)
        output.append(f"  Workflow: {workflow_name}")
        output.append(f"  Project:  {project}")
        output.append(f"  Started:  {started_at}")
        output.append(f"  Elapsed:  {format_duration(elapsed)}")
        output.append("─" * 50)
        output.append("  PHASES")

        phases = self.state.get("phases", {})
        status_icons = {
            "pending": "○",
            "in_progress": "◐",
            "completed": "●",
            "skipped": "◌",
            "failed": "✗",
            "blocked": "⊘",
        }

        for phase_id, phase_data in phases.items():
            status = phase_data.get("status", "pending")
            icon = status_icons.get(status, "?")
            at = phase_data.get("at", "")
            artifact = phase_data.get("artifact", "")

            line = f"  {icon} {phase_id}: {status}"
            if at:
                line += f" ({at[-8:]})"
            if artifact:
                line += f" → {artifact[:30]}"
            output.append(line)

        violations = self.state.get("violations", [])
        if violations:
            output.append("─" * 50)
            output.append(f"  VIOLATIONS ({len(violations)})")
            for v in violations[-5:]:  # Show last 5
                rule = v.get("rule", "unknown")
                detail = v.get("detail", "")[:50]
                severity = v.get("severity", "")
                sev_marker = (
                    "🔴" if severity == "BLOCK" else "🟠" if severity == "ESCALATE" else "🟡"
                )
                output.append(f"  {sev_marker} [{rule}] {detail}")

        output.append("─" * 50)
        return output

    def print(self) -> None:
        """Print dashboard to stdout."""
        for line in self.render():
            print(line)


def cmd_status() -> int:
    """CLI entry point: show workflow status."""
    dashboard = WorkflowDashboard()
    if not dashboard.is_active():
        print("No active workflow")
        return 1
    dashboard.print()
    return 0


def cmd_violations() -> int:
    """CLI entry point: show violations."""
    state = read_state()
    if not state:
        print("No active workflow")
        return 1

    violations = state.get("violations", [])
    if not violations:
        print("No violations")
        return 0

    print(f"Total violations: {len(violations)}")
    for v in violations:
        print(f"  [{v.get('rule', '?')}] {v.get('detail', '')}")
    return 0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ArkaOS Workflow Dashboard")
    parser.add_argument("command", choices=["status", "violations"], help="Command to run")
    args = parser.parse_args()

    if args.command == "status":
        sys.exit(cmd_status())
    elif args.command == "violations":
        sys.exit(cmd_violations())
