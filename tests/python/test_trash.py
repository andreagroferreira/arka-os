"""Tests for the trash + undo subsystem (PR85b v3.12.0)."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest


@pytest.fixture
def trash(tmp_path, monkeypatch):
    """Isolated trash dir per test."""
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    import core.trash as t
    importlib.reload(t)
    return t


def test_record_deletion_writes_payload_and_meta(trash):
    trash_id = trash.record_deletion(
        kind="agent-delete",
        item_id="some-agent",
        original_path="/tmp/some-agent.yaml",
        content="id: some-agent\nname: Test\n",
    )
    assert trash_id
    entries = trash.list_trash()
    assert len(entries) == 1
    assert entries[0]["kind"] == "agent-delete"
    assert entries[0]["item_id"] == "some-agent"
    assert entries[0]["has_payload"] is True


def test_record_move_has_no_payload(trash):
    trash_id = trash.record_move(
        item_id="some-agent",
        from_path="/tmp/a.yaml",
        to_path="/tmp/b.yaml",
    )
    entries = trash.list_trash()
    assert entries[0]["has_payload"] is False
    assert entries[0]["kind"] == "agent-move"
    assert entries[0]["new_path"] == "/tmp/b.yaml"


def test_list_trash_sorts_desc_by_timestamp(trash):
    a = trash.record_deletion("agent-delete", "a", "/tmp/a.yaml", "a")
    b = trash.record_deletion("agent-delete", "b", "/tmp/b.yaml", "b")
    entries = trash.list_trash()
    assert [e["id"] for e in entries[:2]] == [b, a]


def test_list_trash_respects_limit(trash):
    for i in range(5):
        trash.record_deletion("agent-delete", f"a{i}", f"/tmp/a{i}.yaml", "x")
    entries = trash.list_trash(limit=2)
    assert len(entries) == 2


def test_restore_unknown_returns_error(trash):
    res = trash.restore("nonexistent-id")
    assert "error" in res


def test_restore_recreates_deleted_file(trash, tmp_path):
    target = tmp_path / "agent-restore-test.yaml"
    target.write_text("id: x\n", encoding="utf-8")
    content = target.read_text(encoding="utf-8")
    target.unlink()
    trash_id = trash.record_deletion(
        "agent-delete", "x", str(target), content,
    )
    res = trash.restore(trash_id)
    assert res.get("restored") is True
    assert target.exists()
    assert "id: x" in target.read_text(encoding="utf-8")


def test_restore_refuses_to_overwrite(trash, tmp_path):
    target = tmp_path / "occupied.yaml"
    target.write_text("existing", encoding="utf-8")
    trash_id = trash.record_deletion(
        "agent-delete", "x", str(target), "new",
    )
    res = trash.restore(trash_id)
    assert "error" in res
    assert "exists" in res["error"]


def test_restore_move_undoes_the_move(trash, tmp_path):
    src = tmp_path / "src.yaml"
    dst = tmp_path / "dst.yaml"
    dst.write_text("hello", encoding="utf-8")  # Simulate post-move state
    trash_id = trash.record_move("agent-id", str(src), str(dst))
    res = trash.restore(trash_id)
    assert res.get("restored") is True
    assert src.exists()
    assert not dst.exists()


def test_purge_drops_entry_without_restoring(trash, tmp_path):
    target = tmp_path / "p.yaml"
    trash_id = trash.record_deletion("agent-delete", "x", str(target), "x")
    res = trash.purge(trash_id)
    assert res.get("purged") is True
    assert trash.list_trash() == []
    assert not target.exists()


def test_prune_keeps_only_max_entries(trash):
    for i in range(trash.MAX_ENTRIES + 5):
        trash.record_deletion("agent-delete", f"a{i}", f"/tmp/a{i}.yaml", "x")
    entries = trash.list_trash(limit=999)
    assert len(entries) == trash.MAX_ENTRIES
