"""Context Rehydrator — rebuild context from persisted session.

Restores:
- Workflow position (current phase, completed phases)
- Active violations
- Pending deliverables
- Agent handoff state
- Previous outputs for context

Called automatically on session start to restore state.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from core.memory.session_store import SessionStore, load_session, SessionMeta, WorkflowSnapshot


@dataclass
class RehydratedContext:
    """Context rebuilt from a persisted session."""

    session_id: str
    project: str
    workflow_snapshot: WorkflowSnapshot | None = None
    recent_outputs: list[dict] = field(default_factory=list)
    pending_items: list[str] = field(default_factory=list)
    violations: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class HandoffState:
    """Agent handoff state for rehydration."""

    from_agent: str
    to_agent: str
    task: str
    context_summary: str
    relevant_files: list[str] = field(default_factory=list)
    at: str = ""


class ContextRehydrator:
    """Reconstruct context from persisted session data."""

    def __init__(self, session_store: SessionStore):
        self.store = session_store

    def rehydrate(self) -> RehydratedContext:
        """Rebuild complete context from session.

        Returns:
            RehydratedContext with all restored state
        """
        meta = self.store.load_meta()
        workflow = self.store.load_workflow_snapshot()

        if meta is None:
            return RehydratedContext(
                session_id=self.store.session_id,
                project="unknown",
            )

        outputs = self._load_recent_outputs(limit=10)

        return RehydratedContext(
            session_id=meta.session_id,
            project=meta.project,
            workflow_snapshot=workflow,
            recent_outputs=outputs,
            pending_items=self._extract_pending_items(workflow),
            violations=workflow.violations if workflow else [],
            metadata=meta.metadata,
        )

    def _load_recent_outputs(self, limit: int = 10) -> list[dict]:
        """Load recent agent outputs."""
        outputs_dir = self.store._outputs_dir
        if not outputs_dir.exists():
            return []

        all_outputs = []
        for output_file in outputs_dir.glob("*.json"):
            try:
                data = json.loads(output_file.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    all_outputs.extend(data[-limit:])
                elif isinstance(data, dict):
                    all_outputs.append(data)
            except (json.JSONDecodeError, OSError):
                pass

        all_outputs.sort(key=lambda x: x.get("at", ""), reverse=True)
        return all_outputs[-limit:]

    def _extract_pending_items(self, workflow: WorkflowSnapshot | None) -> list[str]:
        """Extract pending items from workflow snapshot."""
        if workflow is None:
            return []

        pending = []
        for phase_id, status in workflow.phases.items():
            if status in ("pending", "in_progress"):
                pending.append(phase_id)
        return pending

    def build_context_string(self) -> str:
        """Build a context string for injection.

        Returns:
            Human-readable context summary
        """
        ctx = self.rehydrate()

        lines = [
            f"[SESSION] Resuming session: {ctx.session_id[:8]}",
            f"[SESSION] Project: {ctx.project}",
            "",
        ]

        if ctx.workflow_snapshot:
            wf = ctx.workflow_snapshot
            lines.append(f"[WORKFLOW] {wf.workflow_name}")
            lines.append(f"[WORKFLOW] Current phase: {wf.current_phase}")
            if ctx.pending_items:
                lines.append(f"[WORKFLOW] Pending: {', '.join(ctx.pending_items)}")

        if ctx.violations:
            lines.append(f"[WORKFLOW] Violations: {len(ctx.violations)}")
            for v in ctx.violations[-3:]:
                lines.append(f"  - [{v.get('rule', '?')}] {v.get('detail', '')[:50]}")

        if ctx.recent_outputs:
            lines.append(f"[CONTEXT] {len(ctx.recent_outputs)} recent outputs available")

        lines.append("")
        lines.append("[SESSION] Type /session resume to continue from last state.")

        return "\n".join(lines)

    def get_handoff_state(self, from_agent: str, to_agent: str) -> HandoffState | None:
        """Get handoff state between two agents.

        Args:
            from_agent: Source agent ID
            to_agent: Target agent ID

        Returns:
            HandoffState if found, None otherwise
        """
        outputs = self.store.load_agent_outputs(from_agent)
        if not outputs:
            return None

        last_output = outputs[-1]
        context_summary = last_output.output[:500] if last_output.output else ""

        return HandoffState(
            from_agent=from_agent,
            to_agent=to_agent,
            task="continued from previous session",
            context_summary=context_summary,
            relevant_files=[],
            at=last_output.at,
        )


def rehydrate_session(session_id: str) -> RehydratedContext | None:
    """Convenience function to rehydrate a session.

    Args:
        session_id: Session UUID to rehydrate

    Returns:
        RehydratedContext or None if session not found
    """
    store = load_session(session_id)
    if store is None:
        return None
    return ContextRehydrator(store).rehydrate()


def build_resume_context() -> str:
    """Build context string for session resume.

    Returns:
        Context string for injection
    """
    from core.memory.session_store import SessionStore

    store = SessionStore()
    active_id = store.get_active_session()
    if not active_id:
        return ""

    session_store = load_session(active_id)
    if session_store is None:
        return ""

    rehydrator = ContextRehydrator(session_store)
    return rehydrator.build_context_string()
