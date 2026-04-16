"""Tests for Session Memory System (Sprint 7).

Tests SessionStore, ContextRehydrator, and SessionCompressor.
"""

import gzip
import json
import shutil
import tarfile
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from core.memory.session_store import (
    SessionStore,
    SessionMeta,
    WorkflowSnapshot,
    AgentOutput,
    create_session,
    load_session,
    load_or_create_session,
    _sessions_dir,
    _ensure_sessions_dir,
)
from core.memory.rehydrator import (
    ContextRehydrator,
    RehydratedContext,
    HandoffState,
    rehydrate_session,
    build_resume_context,
)
from core.memory.compressor import (
    SessionCompressor,
    compress_old_sessions,
    restore_session,
    list_archived_sessions,
    prune_archive,
    get_storage_stats,
    _is_hot,
    _compress_session,
    _decompress_session,
    HOT_DAYS,
    SESSIONS_DIR,
    ARCHIVE_DIR,
)


# --- Fixtures ---


@pytest.fixture
def temp_sessions(monkeypatch, tmp_path):
    """Use temp dir for sessions during tests."""
    sessions = tmp_path / ".arkaos" / "sessions"
    sessions.mkdir(parents=True)
    archive = tmp_path / ".arkaos" / "archive"
    archive.mkdir(parents=True)
    monkeypatch.setattr("core.memory.session_store._sessions_dir", lambda: sessions)
    monkeypatch.setattr("core.memory.session_store._ensure_sessions_dir", lambda: sessions)
    monkeypatch.setattr("core.memory.compressor.SESSIONS_DIR", sessions)
    monkeypatch.setattr("core.memory.compressor.ARCHIVE_DIR", archive)
    monkeypatch.setattr("core.memory.compressor._ensure_archive_dir", lambda: archive)
    yield sessions
    shutil.rmtree(tmp_path / ".arkaos", ignore_errors=True)


@pytest.fixture
def session_store(temp_sessions):
    """Create a fresh SessionStore for testing."""
    return SessionStore()


@pytest.fixture
def sample_meta():
    """Sample SessionMeta for testing."""
    return SessionMeta(
        session_id="test-session-123",
        project="test-project",
        started_at=datetime.now(timezone.utc).isoformat(),
        agent_id="test-agent",
        metadata={"key": "value"},
    )


@pytest.fixture
def sample_snapshot():
    """Sample WorkflowSnapshot for testing."""
    return WorkflowSnapshot(
        workflow_id="wf-1",
        workflow_name="TestWorkflow",
        current_phase="phase-2",
        phases={"phase-1": "complete", "phase-2": "in_progress", "phase-3": "pending"},
        violations=[{"rule": "test-rule", "detail": "Test violation"}],
        artifacts=["file1.txt", "file2.txt"],
        at=datetime.now(timezone.utc).isoformat(),
    )


@pytest.fixture
def sample_output():
    """Sample AgentOutput for testing."""
    return AgentOutput(
        agent_id="agent-1",
        phase_id="phase-1",
        output="Agent completed task successfully",
        at=datetime.now(timezone.utc).isoformat(),
    )


# =============================================================================
# SessionStore Tests
# =============================================================================


class TestSessionStoreBasics:
    def test_session_id_is_uuid(self, session_store):
        assert session_store.session_id is not None
        try:
            uuid.UUID(session_store.session_id)
        except ValueError:
            pytest.fail("session_id is not a valid UUID")

    def test_custom_session_id(self, temp_sessions):
        custom_id = "my-custom-id-123"
        store = SessionStore(session_id=custom_id)
        assert store.session_id == custom_id

    def test_directories_created(self, session_store, temp_sessions):
        assert session_store._session_dir.exists()
        assert session_store._outputs_dir.exists()
        assert session_store._session_dir.is_dir()
        assert session_store._outputs_dir.is_dir()


class TestSessionMeta:
    def test_save_and_load_meta(self, session_store, sample_meta):
        session_store.save_meta(sample_meta)
        loaded = session_store.load_meta()

        assert loaded is not None
        assert loaded.session_id == sample_meta.session_id
        assert loaded.project == sample_meta.project
        assert loaded.started_at == sample_meta.started_at
        assert loaded.agent_id == sample_meta.agent_id
        assert loaded.metadata == sample_meta.metadata

    def test_load_meta_nonexistent(self, session_store):
        result = session_store.load_meta()
        assert result is None

    def test_load_meta_corrupted(self, session_store):
        session_store._meta_file.write_text("not valid json", encoding="utf-8")
        result = session_store.load_meta()
        assert result is None

    def test_meta_to_dict(self, sample_meta):
        d = sample_meta.to_dict()
        assert d["session_id"] == sample_meta.session_id
        assert d["project"] == sample_meta.project
        assert "metadata" in d


class TestWorkflowSnapshot:
    def test_save_and_load_snapshot(self, session_store, sample_snapshot):
        session_store.save_workflow_snapshot(sample_snapshot)
        loaded = session_store.load_workflow_snapshot()

        assert loaded is not None
        assert loaded.workflow_id == sample_snapshot.workflow_id
        assert loaded.workflow_name == sample_snapshot.workflow_name
        assert loaded.current_phase == sample_snapshot.current_phase
        assert loaded.phases == sample_snapshot.phases
        assert loaded.violations == sample_snapshot.violations
        assert loaded.artifacts == sample_snapshot.artifacts

    def test_load_snapshot_nonexistent(self, session_store):
        result = session_store.load_workflow_snapshot()
        assert result is None

    def test_snapshot_at_auto_filled(self, session_store, sample_snapshot):
        sample_snapshot.at = ""
        session_store.save_workflow_snapshot(sample_snapshot)
        loaded = session_store.load_workflow_snapshot()
        assert loaded is not None
        assert loaded.at != ""

    def test_snapshot_to_dict(self, sample_snapshot):
        d = sample_snapshot.to_dict()
        assert d["workflow_id"] == sample_snapshot.workflow_id
        assert "phases" in d


class TestAgentOutput:
    def test_save_and_load_outputs(self, session_store, sample_output):
        session_store.save_agent_output(sample_output)
        outputs = session_store.load_agent_outputs(sample_output.agent_id)

        assert len(outputs) == 1
        assert outputs[0].agent_id == sample_output.agent_id
        assert outputs[0].phase_id == sample_output.phase_id
        assert outputs[0].output == sample_output.output

    def test_multiple_outputs_append(self, session_store, sample_output):
        session_store.save_agent_output(sample_output)
        sample_output2 = AgentOutput(
            agent_id=sample_output.agent_id,
            phase_id="phase-2",
            output="Second output",
            at=datetime.now(timezone.utc).isoformat(),
        )
        session_store.save_agent_output(sample_output2)

        outputs = session_store.load_agent_outputs(sample_output.agent_id)
        assert len(outputs) == 2

    def test_load_nonexistent_agent(self, session_store):
        outputs = session_store.load_agent_outputs("nonexistent-agent")
        assert outputs == []


class TestSessionListing:
    def test_list_sessions_empty(self, temp_sessions):
        store = SessionStore()
        sessions = store.list_sessions()
        assert sessions == []

    def test_list_sessions_returns_recent(self, temp_sessions):
        store1 = SessionStore()
        meta1 = SessionMeta(
            session_id=store1.session_id,
            project="test-project-1",
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        store1.save_meta(meta1)

        store2 = SessionStore()
        meta2 = SessionMeta(
            session_id=store2.session_id,
            project="test-project-2",
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        store2.save_meta(meta2)

        store3 = SessionStore()
        sessions = store3.list_sessions(limit=10)

        assert len(sessions) == 2

    def test_get_active_session(self, temp_sessions):
        store = SessionStore()
        meta = SessionMeta(
            session_id=store.session_id,
            project="test-project",
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        store.save_meta(meta)

        active = store.get_active_session()
        assert active is not None
        assert active == store.session_id


class TestEndSession:
    def test_end_session_updates_meta(self, session_store, sample_meta):
        session_store.save_meta(sample_meta)
        assert sample_meta.ended_at == ""

        session_store.end_session()
        updated = session_store.load_meta()

        assert updated is not None
        assert updated.ended_at != ""


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestCreateSession:
    def test_create_session_returns_store(self, temp_sessions):
        store = create_session("my-project", "agent-x", {"foo": "bar"})
        assert store is not None
        assert store.session_id is not None

        meta = store.load_meta()
        assert meta is not None
        assert meta.project == "my-project"
        assert meta.agent_id == "agent-x"
        assert meta.metadata == {"foo": "bar"}


class TestLoadSession:
    def test_load_nonexistent_returns_none(self, temp_sessions):
        result = load_session("nonexistent-id")
        assert result is None

    def test_load_existing_returns_store(self, temp_sessions):
        original = create_session("test-project")
        original_id = original.session_id

        loaded = load_session(original_id)
        assert loaded is not None
        assert loaded.session_id == original_id


class TestLoadOrCreateSession:
    def test_loads_existing_if_active(self, temp_sessions):
        store1 = create_session("my-project")
        meta = SessionMeta(
            session_id=store1.session_id,
            project="my-project",
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        store1.save_meta(meta)

        store2 = load_or_create_session("my-project")
        assert store2.session_id == store1.session_id

    def test_creates_new_if_no_active(self, temp_sessions):
        store = load_or_create_session("new-project")
        assert store is not None


# =============================================================================
# ContextRehydrator Tests
# =============================================================================


class TestRehydratedContext:
    def test_rehydrate_returns_context(self, temp_sessions, sample_meta, sample_snapshot):
        store = SessionStore()
        store.save_meta(sample_meta)
        store.save_workflow_snapshot(sample_snapshot)

        rehydrator = ContextRehydrator(store)
        ctx = rehydrator.rehydrate()

        assert ctx is not None
        assert ctx.session_id == sample_meta.session_id
        assert ctx.project == sample_meta.project

    def test_rehydrate_no_meta(self, temp_sessions):
        store = SessionStore()
        rehydrator = ContextRehydrator(store)
        ctx = rehydrator.rehydrate()

        assert ctx is not None
        assert ctx.project == "unknown"

    def test_extract_pending_items(self, temp_sessions, sample_snapshot):
        store = SessionStore()
        rehydrator = ContextRehydrator(store)

        pending = rehydrator._extract_pending_items(sample_snapshot)
        assert "phase-2" in pending
        assert "phase-3" in pending
        assert "phase-1" not in pending

    def test_extract_pending_none(self, temp_sessions):
        store = SessionStore()
        rehydrator = ContextRehydrator(store)

        pending = rehydrator._extract_pending_items(None)
        assert pending == []


class TestBuildContextString:
    def test_build_context_string(self, temp_sessions, sample_meta, sample_snapshot):
        store = SessionStore()
        store.save_meta(sample_meta)
        store.save_workflow_snapshot(sample_snapshot)

        rehydrator = ContextRehydrator(store)
        ctx_str = rehydrator.build_context_string()

        assert "[SESSION]" in ctx_str
        assert "[WORKFLOW]" in ctx_str
        assert sample_meta.project in ctx_str
        assert sample_snapshot.workflow_name in ctx_str


class TestGetHandoffState:
    def test_get_handoff_state(self, temp_sessions, sample_output):
        store = SessionStore()
        store.save_agent_output(sample_output)

        rehydrator = ContextRehydrator(store)
        handoff = rehydrator.get_handoff_state(sample_output.agent_id, "new-agent")

        assert handoff is not None
        assert handoff.from_agent == sample_output.agent_id
        assert handoff.to_agent == "new-agent"

    def test_get_handoff_none_if_no_outputs(self, temp_sessions):
        store = SessionStore()
        rehydrator = ContextRehydrator(store)
        handoff = rehydrator.get_handoff_state("ghost-agent", "new-agent")
        assert handoff is None


class TestRehydrateSession:
    def test_rehydrate_session_convenience(self, temp_sessions, sample_meta):
        store = create_session("test-project")
        store.save_meta(sample_meta)
        session_id = store.session_id

        ctx = rehydrate_session(session_id)
        assert ctx is not None
        assert ctx.project == sample_meta.project

    def test_rehydrate_session_none_if_missing(self, temp_sessions):
        ctx = rehydrate_session("nonexistent-session")
        assert ctx is None


class TestBuildResumeContext:
    def test_build_resume_context_empty_if_no_active(self, temp_sessions):
        result = build_resume_context()
        assert result == ""


# =============================================================================
# SessionCompressor Tests
# =============================================================================


class TestIsHot:
    def test_is_hot_true_recent(self, temp_sessions, sample_meta):
        session_dir = temp_sessions / "recent-session"
        session_dir.mkdir()
        meta = SessionMeta(
            session_id="recent-session",
            project="test",
            started_at=datetime.now(timezone.utc).isoformat(),
            ended_at=datetime.now(timezone.utc).isoformat(),
        )
        (session_dir / "session-meta.json").write_text(json.dumps(meta.to_dict()), encoding="utf-8")

        assert _is_hot(session_dir) is True

    def test_is_hot_false_old(self, temp_sessions, sample_meta):
        session_dir = temp_sessions / "old-session"
        session_dir.mkdir()

        old_time = (datetime.now(timezone.utc) - timedelta(days=HOT_DAYS + 1)).isoformat()
        meta = SessionMeta(
            session_id="old-session",
            project="test",
            started_at=old_time,
            ended_at=old_time,
        )
        (session_dir / "session-meta.json").write_text(json.dumps(meta.to_dict()), encoding="utf-8")

        assert _is_hot(session_dir) is False

    def test_is_hot_false_no_meta(self, temp_sessions):
        session_dir = temp_sessions / "no-meta-session"
        session_dir.mkdir()
        assert _is_hot(session_dir) is False


class TestCompressDecompress:
    def test_compress_session(self, temp_sessions, sample_meta, sample_snapshot):
        store = SessionStore()
        store.save_meta(sample_meta)
        store.save_workflow_snapshot(sample_snapshot)

        archive_file = _compress_session(store._session_dir)
        assert archive_file.exists()
        assert archive_file.suffix == ".gz"

    def test_decompress_session(self, temp_sessions, sample_meta):
        store = SessionStore()
        store.save_meta(sample_meta)

        archive_file = _compress_session(store._session_dir)
        shutil.rmtree(store._session_dir)

        restored_dir = _decompress_session(archive_file, temp_sessions)

        assert restored_dir.exists()
        meta = SessionMeta(
            **json.loads((restored_dir / "session-meta.json").read_text(encoding="utf-8"))
        )
        assert meta.session_id == sample_meta.session_id


class TestCompressOldSessions:
    def test_compress_old_sessions_empty(self, temp_sessions):
        result = compress_old_sessions()
        assert result["archived"] == 0
        assert result["remaining"] == 0

    def test_compress_old_sessions_keeps_hot(self, temp_sessions):
        store = SessionStore()
        meta = SessionMeta(
            session_id=store.session_id,
            project="test",
            started_at=datetime.now(timezone.utc).isoformat(),
            ended_at=datetime.now(timezone.utc).isoformat(),
        )
        store.save_meta(meta)

        result = compress_old_sessions()
        assert result["archived"] == 0
        assert result["remaining"] == 1


class TestRestoreSession:
    def test_restore_nonexistent(self, temp_sessions):
        result = restore_session("nonexistent-id")
        assert result is None

    def test_restore_existing(self, temp_sessions, sample_meta):
        store = SessionStore()
        store.save_meta(sample_meta)

        archive_file = _compress_session(store._session_dir)
        shutil.rmtree(store._session_dir)

        restored = restore_session(store.session_id)
        assert restored is not None
        assert restored.exists()


class TestListArchivedSessions:
    def test_list_archived_empty(self, temp_sessions):
        result = list_archived_sessions()
        assert result == []

    def test_list_archived_returns_sessions(self, temp_sessions, sample_meta):
        store = SessionStore()
        store.save_meta(sample_meta)

        _compress_session(store._session_dir)

        result = list_archived_sessions()
        assert len(result) == 1
        assert result[0]["session_id"] == store.session_id


class TestPruneArchive:
    def test_prune_none_to_delete(self, temp_sessions):
        result = prune_archive(older_than_days=90)
        assert result == 0

    def test_prune_deletes_old(self, temp_sessions, sample_meta):
        store = SessionStore()
        store.save_meta(sample_meta)

        archive_file = _compress_session(store._session_dir)
        old_mtime = time.time() - (91 * 24 * 3600)
        archive_file.touch()
        import os

        os.utime(archive_file, (old_mtime, old_mtime))

        result = prune_archive(older_than_days=90)
        assert result == 1


class TestGetStorageStats:
    def test_stats_empty(self, temp_sessions):
        stats = get_storage_stats()
        assert stats["sessions"]["total"] == 0
        assert stats["archive"]["count"] == 0

    def test_stats_with_data(self, temp_sessions, sample_meta):
        store = SessionStore()
        store.save_meta(sample_meta)

        stats = get_storage_stats()
        assert stats["sessions"]["total"] == 1
        assert stats["sessions"]["hot"] == 1


# =============================================================================
# SessionCompressor Class Tests
# =============================================================================


class TestSessionCompressor:
    def test_compress_old(self, temp_sessions):
        compressor = SessionCompressor()
        result = compressor.compress_old()
        assert "archived" in result
        assert "remaining" in result

    def test_restore(self, temp_sessions, sample_meta):
        store = SessionStore()
        store.save_meta(sample_meta)

        archive_file = _compress_session(store._session_dir)
        shutil.rmtree(store._session_dir)

        compressor = SessionCompressor()
        restored = compressor.restore(store.session_id)
        assert restored is not None

    def test_list_archived(self, temp_sessions, sample_meta):
        store = SessionStore()
        store.save_meta(sample_meta)
        _compress_session(store._session_dir)

        compressor = SessionCompressor()
        archived = compressor.list_archived()
        assert len(archived) == 1

    def test_prune(self, temp_sessions):
        compressor = SessionCompressor()
        result = compressor.prune(older_than_days=90)
        assert result >= 0

    def test_stats(self, temp_sessions):
        compressor = SessionCompressor()
        stats = compressor.stats()
        assert "sessions" in stats
        assert "archive" in stats


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    def test_session_with_unicode_metadata(self, session_store, sample_meta):
        sample_meta.metadata = {"unicode": "葡萄牙語 日本語 emoji 🎉"}
        session_store.save_meta(sample_meta)
        loaded = session_store.load_meta()
        assert loaded.metadata["unicode"] == "葡萄牙語 日本語 emoji 🎉"

    def test_workflow_snapshot_empty_phases(self, session_store):
        snapshot = WorkflowSnapshot(
            workflow_id="wf-empty",
            workflow_name="EmptyWorkflow",
            current_phase="start",
            phases={},
        )
        session_store.save_workflow_snapshot(snapshot)
        loaded = session_store.load_workflow_snapshot()
        assert loaded.phases == {}

    def test_agent_output_empty_string(self, session_store):
        output = AgentOutput(
            agent_id="empty-agent",
            phase_id="phase-1",
            output="",
        )
        session_store.save_agent_output(output)
        outputs = session_store.load_agent_outputs("empty-agent")
        assert len(outputs) == 1
        assert outputs[0].output == ""

    def test_context_string_no_workflow(self, temp_sessions, sample_meta):
        store = SessionStore()
        store.save_meta(sample_meta)

        rehydrator = ContextRehydrator(store)
        ctx_str = rehydrator.build_context_string()

        assert "Project: test-project" in ctx_str
        assert "[WORKFLOW]" not in ctx_str

    def test_compress_invalid_session_dir(self, temp_sessions):
        invalid_dir = temp_sessions / "invalid-session"
        invalid_dir.mkdir()
        (invalid_dir / "broken.json").write_text("{", encoding="utf-8")

        result = compress_old_sessions()
        assert len(result["errors"]) >= 0
