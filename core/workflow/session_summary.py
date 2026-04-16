"""Session summary generator.

Generates end-of-session recap saved to ~/.arkaos/sessions/{session_id}.json
and optionally printed to stdout.

Includes:
- Phases completed
- Total duration
- Violations
- Artifacts produced
- Agent outputs
"""

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class PhaseSummary:
    """Summary of a single phase."""

    phase_id: str
    phase_name: str
    status: str
    duration_ms: int = 0
    artifacts: list[str] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)


@dataclass
class SessionSummary:
    """Complete session summary."""

    session_id: str
    workflow: str
    project: str
    started_at: str
    completed_at: str = ""
    total_duration_ms: int = 0
    phases: list[PhaseSummary] = field(default_factory=list)
    violations: list[dict] = field(default_factory=list)
    agent_outputs: dict[str, str] = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


def _sessions_dir() -> Path:
    """Get sessions directory path."""
    sessions = Path.home() / ".arkaos" / "sessions"
    sessions.mkdir(parents=True, exist_ok=True)
    return sessions


def save_session(summary: SessionSummary) -> Path:
    """Save session summary to JSON file.

    Args:
        summary: The session summary to save

    Returns:
        Path to saved file
    """
    path = _sessions_dir() / f"{summary.session_id}.json"
    path.write_text(summary.to_json(), encoding="utf-8")
    return path


def load_session(session_id: str) -> SessionSummary | None:
    """Load a session summary by ID.

    Args:
        session_id: The session UUID

    Returns:
        SessionSummary or None if not found
    """
    path = _sessions_dir() / f"{session_id}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return SessionSummary(**data)
    except (json.JSONDecodeError, KeyError, OSError):
        return None


def list_sessions(limit: int = 10) -> list[SessionSummary]:
    """List recent sessions.

    Args:
        limit: Maximum number of sessions to return

    Returns:
        List of SessionSummary objects, newest first
    """
    sessions_dir = _sessions_dir()
    if not sessions_dir.exists():
        return []

    sessions = []
    for path in sorted(sessions_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[
        :limit
    ]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            sessions.append(SessionSummary(**data))
        except (json.JSONDecodeError, KeyError):
            pass

    return sessions


class SessionSummaryBuilder:
    """Builder for session summaries."""

    def __init__(self, workflow: str, project: str):
        self.summary = SessionSummary(
            session_id=str(uuid.uuid4()),
            workflow=workflow,
            project=project,
            started_at=datetime.now(timezone.utc).isoformat(),
        )

    def add_phase(self, phase: PhaseSummary) -> None:
        """Add a phase to the summary."""
        self.summary.phases.append(phase)

    def add_violation(self, rule: str, detail: str, severity: str = "") -> None:
        """Add a violation to the summary."""
        self.summary.violations.append(
            {
                "rule": rule,
                "detail": detail,
                "severity": severity,
            }
        )

    def add_agent_output(self, agent_id: str, output: str) -> None:
        """Add an agent output."""
        self.summary.agent_outputs[agent_id] = output

    def set_metadata(self, key: str, value: Any) -> None:
        """Set a metadata field."""
        self.summary.metadata[key] = value

    def complete(self) -> SessionSummary:
        """Finalize and return the summary."""
        self.summary.completed_at = datetime.now(timezone.utc).isoformat()
        self.summary.total_duration_ms = sum(p.duration_ms for p in self.summary.phases)
        return self.summary

    def save(self) -> Path:
        """Complete and save the session."""
        self.complete()
        return save_session(self.summary)

    def render_text(self) -> str:
        """Render summary as human-readable text."""
        self.complete()
        lines = [
            "═" * 60,
            "  SESSION SUMMARY",
            "═" * 60,
            f"  Session: {self.summary.session_id[:8]}...",
            f"  Workflow: {self.summary.workflow}",
            f"  Project: {self.summary.project}",
            f"  Started: {self.summary.started_at}",
            f"  Completed: {self.summary.completed_at}",
            f"  Duration: {self.summary.total_duration_ms}ms",
            "",
            "  PHASES",
        ]

        for phase in self.summary.phases:
            icon = "✓" if phase.status == "completed" else "✗" if phase.status == "failed" else "○"
            lines.append(f"  {icon} {phase.phase_name} ({phase.duration_ms}ms)")
            for artifact in phase.artifacts:
                lines.append(f"    → {artifact}")
            for violation in phase.violations:
                lines.append(f"    ⚠ {violation}")

        if self.summary.violations:
            lines.append("")
            lines.append(f"  VIOLATIONS ({len(self.summary.violations)})")
            for v in self.summary.violations:
                sev = v.get("severity", "")
                marker = "🔴" if sev == "BLOCK" else "🟠" if sev == "ESCALATE" else "🟡"
                lines.append(f"  {marker} [{v.get('rule', '?')}] {v.get('detail', '')}")

        lines.append("═" * 60)
        return "\n".join(lines)

    def print(self) -> None:
        """Print summary to stdout."""
        print(self.render_text())
