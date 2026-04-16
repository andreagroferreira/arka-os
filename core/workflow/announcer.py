"""Phase announcement system for ArkaOS workflows.

Provides structured, visible announcements for workflow phases
enforcing the Constitution's "full visibility" rule.

Format: [PHASE] Starting: {name} | [PHASE] Completed: {name} ({duration}ms)
"""

import time
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class Announcement:
    """A single announcement record."""

    phase_id: str
    phase_name: str
    event: str  # "starting" | "completed" | "failed" | "blocked" | "skipped"
    duration_ms: int = 0
    metadata: dict = field(default_factory=dict)
    at: float = field(default_factory=time.time)


class PhaseAnnouncer:
    """Manages phase announcements with structured output.

    Integrates with WorkflowEngine via on_visibility callback.
    Tracks all announcements for session summary generation.
    """

    def __init__(self, on_announce: Callable[[str], None] | None = None):
        """Initialize announcer.

        Args:
            on_announce: Callback to output announcement. Defaults to print.
        """
        self._on_announce = on_announce or print
        self._announcements: list[Announcement] = []
        self._phase_start_times: dict[str, float] = {}

    def starting(self, phase_id: str, phase_name: str, **metadata: str) -> None:
        """Announce phase starting.

        Args:
            phase_id: Unique phase identifier
            phase_name: Human-readable phase name
            **metadata: Additional context (agents, department, etc.)
        """
        self._phase_start_times[phase_id] = time.time()
        announcement = Announcement(
            phase_id=phase_id,
            phase_name=phase_name,
            event="starting",
            metadata=metadata,
        )
        self._announcements.append(announcement)
        self._emit(announcement)

    def completed(self, phase_id: str, phase_name: str, output: str = "", **metadata: str) -> int:
        """Announce phase completed.

        Args:
            phase_id: Unique phase identifier
            phase_name: Human-readable phase name
            output: Phase result summary
            **metadata: Additional context

        Returns:
            Duration in milliseconds
        """
        start_time = self._phase_start_times.pop(phase_id, time.time())
        duration_ms = int((time.time() - start_time) * 1000)

        announcement = Announcement(
            phase_id=phase_id,
            phase_name=phase_name,
            event="completed",
            duration_ms=duration_ms,
            metadata=metadata,
        )
        self._announcements.append(announcement)
        self._emit(announcement)
        return duration_ms

    def failed(self, phase_id: str, phase_name: str, reason: str = "") -> None:
        """Announce phase failed.

        Args:
            phase_id: Unique phase identifier
            phase_name: Human-readable phase name
            reason: Failure reason
        """
        announcement = Announcement(
            phase_id=phase_id,
            phase_name=phase_name,
            event="failed",
            metadata={"reason": reason} if reason else {},
        )
        self._announcements.append(announcement)
        self._emit(announcement)

    def blocked(self, phase_id: str, phase_name: str, reason: str = "") -> None:
        """Announce phase blocked.

        Args:
            phase_id: Unique phase identifier
            phase_name: Human-readable phase name
            reason: Block reason
        """
        announcement = Announcement(
            phase_id=phase_id,
            phase_name=phase_name,
            event="blocked",
            metadata={"reason": reason} if reason else {},
        )
        self._announcements.append(announcement)
        self._emit(announcement)

    def skipped(self, phase_id: str, phase_name: str, reason: str = "") -> None:
        """Announce phase skipped.

        Args:
            phase_id: Unique phase identifier
            phase_name: Human-readable phase name
            reason: Skip reason
        """
        announcement = Announcement(
            phase_id=phase_id,
            phase_name=phase_name,
            event="skipped",
            metadata={"reason": reason} if reason else {},
        )
        self._announcements.append(announcement)
        self._emit(announcement)

    def workflow_start(self, workflow_name: str, phase_count: int, tier: str) -> None:
        """Announce workflow starting.

        Args:
            workflow_name: Name of the workflow
            phase_count: Number of phases
            tier: Workflow tier
        """
        msg = f"[WORKFLOW] Starting: {workflow_name} ({phase_count} phases, tier: {tier})"
        self._on_announce(msg)

    def workflow_complete(self, workflow_name: str, total_duration_ms: int) -> None:
        """Announce workflow completed.

        Args:
            workflow_name: Name of the workflow
            total_duration_ms: Total execution time
        """
        msg = f"[WORKFLOW] Completed: {workflow_name} (total: {total_duration_ms}ms)"
        self._on_announce(msg)

    def _emit(self, announcement: Announcement) -> None:
        """Format and emit an announcement."""
        if announcement.event == "starting":
            agents = announcement.metadata.get("agents", "")
            msg = f"[PHASE] Starting: {announcement.phase_name}"
            if agents:
                msg += f" (agents: {agents})"
        elif announcement.event == "completed":
            msg = f"[PHASE] Completed: {announcement.phase_name} ({announcement.duration_ms}ms)"
        elif announcement.event == "failed":
            reason = announcement.metadata.get("reason", "")
            msg = f"[PHASE] Failed: {announcement.phase_name}"
            if reason:
                msg += f" — {reason}"
        elif announcement.event == "blocked":
            reason = announcement.metadata.get("reason", "")
            msg = f"[PHASE] Blocked: {announcement.phase_name}"
            if reason:
                msg += f" (waiting for: {reason})"
        elif announcement.event == "skipped":
            reason = announcement.metadata.get("reason", "")
            msg = f"[PHASE] Skipped: {announcement.phase_name}"
            if reason:
                msg += f" ({reason})"
        else:
            msg = f"[PHASE] {announcement.phase_name} — {announcement.event.upper()}"

        self._on_announce(msg)

    @property
    def announcements(self) -> list[Announcement]:
        """Get all announcements for this session."""
        return self._announcements.copy()

    def get_phase_announcements(
        self, phase_id: str
    ) -> tuple[Announcement | None, Announcement | None]:
        """Get start and completion announcements for a phase.

        Args:
            phase_id: The phase identifier

        Returns:
            Tuple of (starting_announcement, completed_announcement) or (None, None)
        """
        start_ann = None
        complete_ann = None
        for ann in self._announcements:
            if ann.phase_id == phase_id:
                if ann.event == "starting":
                    start_ann = ann
                elif ann.event == "completed":
                    complete_ann = ann
        return start_ann, complete_ann

    def validate_phase_completion(self, phase_id: str) -> bool:
        """Check if a phase has both start and completion announcements.

        Args:
            phase_id: The phase to validate

        Returns:
            True if phase has both starting and completed announcements
        """
        start_ann, complete_ann = self.get_phase_announcements(phase_id)
        return start_ann is not None and complete_ann is not None

    def get_total_duration_ms(self) -> int:
        """Calculate total duration across all completed phases.

        Returns:
            Total milliseconds
        """
        return sum(ann.duration_ms for ann in self._announcements if ann.event == "completed")


def make_announcer(
    on_announce: Callable[[str], None] | None = None,
) -> PhaseAnnouncer:
    """Factory to create a PhaseAnnouncer.

    Args:
        on_announce: Optional output callback

    Returns:
        Configured PhaseAnnouncer instance
    """
    return PhaseAnnouncer(on_announce=on_announce)
