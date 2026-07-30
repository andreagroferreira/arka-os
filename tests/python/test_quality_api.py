"""Minimal pins for core/governance/quality_api.py (PR-B5, QG r1 M1).

The module is deprecated in favour of the guarded record_cli path, but
this PR's diff touches executable lines in it (the datetime.UTC import
and clear_resolved), and no other test in the repo imports the module —
these pins put it on the coverage record instead of leaving it excluded
on a false premise.
"""

from __future__ import annotations

import json

import pytest


@pytest.fixture()
def api_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    # _STATE_DIR is computed at import time from Path.home(); repoint it
    # so the module under test never touches the real ~/.arkaos.
    from core.governance import quality_api

    state = tmp_path / "quality-gate"
    monkeypatch.setattr(quality_api, "_STATE_DIR", state)
    monkeypatch.setattr(quality_api, "_QUEUE_FILE", state / "queue.json")
    monkeypatch.setattr(
        quality_api, "_WORKFLOWS_FILE", state / "workflows.json"
    )
    return quality_api


def _seed_queue(quality_api, items):
    quality_api._ensure_state_dir()
    quality_api._QUEUE_FILE.write_text(json.dumps(items), encoding="utf-8")


def test_record_verdict_marks_item_reviewed(api_home):
    _seed_queue(api_home, [{"id": "sub-1", "status": "pending"}])
    assert api_home.record_verdict("sub-1", "francisca-tech", "APPROVED")
    queue = json.loads(api_home._QUEUE_FILE.read_text(encoding="utf-8"))
    assert queue[0]["status"] == "reviewed"
    assert queue[0]["verdict"] == "APPROVED"


def test_record_verdict_unknown_submission_is_false(api_home):
    _seed_queue(api_home, [])
    assert api_home.record_verdict("ghost", "eduardo-copy", "REJECTED") is False


def test_record_verdict_docstring_names_the_guarded_path(api_home):
    """The deprecation must point somewhere that exists: the module is
    core.evals.record_cli (QG r1 blockers E1-E3 shipped a phantom
    core.governance path — this pin keeps the correction honest)."""
    import importlib

    doc = api_home.record_verdict.__doc__ or ""
    assert "core.evals.record_cli" in doc
    assert "core.governance.record_cli" not in doc
    importlib.import_module("core.evals.record_cli")


def test_clear_resolved_keeps_recent_and_pending(api_home):
    from datetime import UTC, datetime, timedelta

    old = (datetime.now(UTC) - timedelta(days=30)).isoformat()
    _seed_queue(api_home, [
        {"id": "p", "status": "pending"},
        {"id": "old", "status": "reviewed", "verdict_at": old},
        {
            "id": "new", "status": "reviewed",
            "verdict_at": datetime.now(UTC).isoformat(),
        },
    ])
    removed = api_home.clear_resolved(older_than_days=7)
    assert removed == 1
    ids = [i["id"] for i in json.loads(
        api_home._QUEUE_FILE.read_text(encoding="utf-8")
    )]
    assert ids == ["p", "new"]
