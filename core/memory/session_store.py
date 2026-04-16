"""Session Memory Store — persist session state across restarts.

Stores session data to ~/.arkaos/sessions/:
- workflow-state.json: Current workflow phase, violations
- agent-outputs/: Per-agent outputs from this session
- session-meta.json: Session metadata (start time, project, etc.)

Auto-saved on every state change. Loads automatically on session start.
"""

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _sessions_dir() -> Path:
    return Path.home() / ".arkaos" / "sessions"


def _ensure_sessions_dir() -> Path:
    sessions = _sessions_dir()
    sessions.mkdir(parents=True, exist_ok=True)
    return sessions


@dataclass
class SessionMeta:
    """Metadata about a session."""

    session_id: str
    project: str
    started_at: str
    ended_at: str = ""
    workflow_id: str = ""
    agent_id: str = ""
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WorkflowSnapshot:
    """Snapshot of workflow state at a point in time."""

    workflow_id: str
    workflow_name: str
    current_phase: str
    phases: dict[str, str]
    violations: list[dict] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AgentOutput:
    """Output from an agent during the session."""

    agent_id: str
    phase_id: str
    output: str
    at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SessionStore:
    """Persistent session memory store."""

    def __init__(self, session_id: str | None = None):
        self.session_id = session_id or str(uuid.uuid4())
        self._sessions_dir = _ensure_sessions_dir()
        self._session_dir = self._sessions_dir / self.session_id
        self._session_dir.mkdir(parents=True, exist_ok=True)

        self._meta_file = self._session_dir / "session-meta.json"
        self._workflow_file = self._session_dir / "workflow-state.json"
        self._outputs_dir = self._session_dir / "agent-outputs"
        self._outputs_dir.mkdir(exist_ok=True)

    def save_meta(self, meta: SessionMeta) -> None:
        """Save session metadata."""
        self._meta_file.write_text(json.dumps(meta.to_dict(), indent=2), encoding="utf-8")

    def load_meta(self) -> SessionMeta | None:
        """Load session metadata."""
        if not self._meta_file.exists():
            return None
        try:
            data = json.loads(self._meta_file.read_text(encoding="utf-8"))
            return SessionMeta(**data)
        except (json.JSONDecodeError, KeyError, OSError):
            return None

    def save_workflow_snapshot(self, snapshot: WorkflowSnapshot) -> None:
        """Save workflow state snapshot."""
        if not snapshot.at:
            snapshot.at = datetime.now(timezone.utc).isoformat()
        self._workflow_file.write_text(json.dumps(snapshot.to_dict(), indent=2), encoding="utf-8")

    def load_workflow_snapshot(self) -> WorkflowSnapshot | None:
        """Load workflow state snapshot."""
        if not self._workflow_file.exists():
            return None
        try:
            data = json.loads(self._workflow_file.read_text(encoding="utf-8"))
            return WorkflowSnapshot(**data)
        except (json.JSONDecodeError, KeyError, OSError):
            return None

    def save_agent_output(self, output: AgentOutput) -> None:
        """Save an agent's output."""
        if not output.at:
            output.at = datetime.now(timezone.utc).isoformat()

        file_path = self._outputs_dir / f"{output.agent_id}.json"
        outputs = []
        if file_path.exists():
            try:
                outputs = json.loads(file_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                outputs = []

        outputs.append(output.to_dict())
        file_path.write_text(json.dumps(outputs, indent=2), encoding="utf-8")

    def load_agent_outputs(self, agent_id: str) -> list[AgentOutput]:
        """Load all outputs for a specific agent."""
        file_path = self._outputs_dir / f"{agent_id}.json"
        if not file_path.exists():
            return []

        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            return [AgentOutput(**o) for o in data]
        except (json.JSONDecodeError, KeyError, OSError):
            return []

    def list_sessions(self, limit: int = 10) -> list[SessionMeta]:
        """List recent sessions."""
        sessions = []
        for session_dir in sorted(
            self._sessions_dir.iterdir(),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[:limit]:
            if session_dir.is_dir():
                meta_file = session_dir / "session-meta.json"
                if meta_file.exists():
                    try:
                        data = json.loads(meta_file.read_text(encoding="utf-8"))
                        sessions.append(SessionMeta(**data))
                    except (json.JSONDecodeError, KeyError):
                        pass
        return sessions

    def get_active_session(self) -> str | None:
        """Get the most recent active session ID."""
        sessions = self.list_sessions(limit=1)
        if sessions:
            return sessions[0].session_id
        return None

    def end_session(self) -> None:
        """Mark session as ended."""
        meta = self.load_meta()
        if meta:
            meta.ended_at = datetime.now(timezone.utc).isoformat()
            self.save_meta(meta)


def create_session(project: str, agent_id: str = "", metadata: dict | None = None) -> SessionStore:
    """Create a new session store.

    Args:
        project: Project name
        agent_id: Agent ID creating the session
        metadata: Additional metadata

    Returns:
        New SessionStore instance
    """
    store = SessionStore()
    meta = SessionMeta(
        session_id=store.session_id,
        project=project,
        started_at=datetime.now(timezone.utc).isoformat(),
        agent_id=agent_id,
        metadata=metadata or {},
    )
    store.save_meta(meta)
    return store


def load_session(session_id: str) -> SessionStore | None:
    """Load an existing session by ID.

    Args:
        session_id: The session UUID

    Returns:
        SessionStore instance or None if not found
    """
    session_dir = _sessions_dir() / session_id
    if not session_dir.exists():
        return None

    store = SessionStore(session_id=session_id)
    if store.load_meta() is None:
        return None
    return store


def load_or_create_session(project: str, agent_id: str = "") -> SessionStore:
    """Load the most recent session or create a new one.

    Args:
        project: Project name
        agent_id: Agent ID

    Returns:
        SessionStore for the session
    """
    sessions_dir = _sessions_dir()
    if not sessions_dir.exists():
        return create_session(project, agent_id)

    sessions = []
    for session_dir in sorted(
        sessions_dir.iterdir(),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    ):
        if session_dir.is_dir():
            meta_file = session_dir / "session-meta.json"
            if meta_file.exists():
                try:
                    data = json.loads(meta_file.read_text(encoding="utf-8"))
                    sessions.append(SessionMeta(**data))
                except (json.JSONDecodeError, KeyError):
                    pass

    for session in sessions:
        if not session.ended_at:
            existing = load_session(session.session_id)
            if existing:
                return existing

    return create_session(project, agent_id)
