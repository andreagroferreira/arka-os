"""Tests for core.hooks.session_end (F2-4)."""

from __future__ import annotations

import json

import pytest

from core.hooks import session_end
from core.hooks.session_end import main, write_digest


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(session_end, "_DIGEST_DIR",
                        tmp_path / ".arkaos" / "session-digests")
    return tmp_path


@pytest.fixture
def sanitizer_present(tmp_path, monkeypatch):
    from core.governance import leak_scanner

    cfg = tmp_path / ".arkaos" / "redaction-clients.json"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(json.dumps({"clients": ["megacorp"]}), encoding="utf-8")
    monkeypatch.setattr(leak_scanner, "_DEFAULT_CONFIG_PATH", cfg)


def _transcript(tmp_path, *texts):
    lines = [
        {"type": "assistant", "message": {"role": "assistant",
         "content": [{"type": "text", "text": t}]}}
        for t in texts
    ]
    path = tmp_path / "t.jsonl"
    path.write_text("\n".join(json.dumps(x) for x in lines), encoding="utf-8")
    return str(path)


def _digests(tmp_path):
    d = tmp_path / ".arkaos" / "session-digests"
    return list(d.glob("*.md")) if d.exists() else []


def test_writes_digest_with_sanitized_excerpt(tmp_path, sanitizer_present):
    transcript = _transcript(
        tmp_path, "worked on megacorp payments", "shipped the megacorp feature"
    )
    path = write_digest("sess-abc12345", transcript)
    assert path is not None
    body = path.read_text(encoding="utf-8")
    assert "trigger: session-end" in body
    assert "session_id: sess-abc12345" in body
    assert "megacorp" not in body  # redacted
    assert "[CLIENT-1]" in body


def test_digest_deterministic_id(tmp_path, sanitizer_present):
    transcript = _transcript(tmp_path, "same content")
    p1 = write_digest("sess-x", transcript)
    p2 = write_digest("sess-x", transcript)
    assert p1 == p2  # content-hashed filename dedups


def test_digest_without_sanitizer_omits_excerpt(tmp_path, monkeypatch):
    from core.governance import leak_scanner

    monkeypatch.setattr(
        leak_scanner, "_DEFAULT_CONFIG_PATH",
        tmp_path / ".arkaos" / "nope.json",  # absent
    )
    transcript = _transcript(tmp_path, "some private work")
    body = write_digest("sess-y", transcript).read_text(encoding="utf-8")
    assert "some private work" not in body
    assert "no sanitizable transcript excerpt" in body


def test_main_ends_session_and_writes(tmp_path, sanitizer_present):
    from core.memory.session_store import create_session

    store = create_session("proj")
    sid = store.session_id
    transcript = _transcript(tmp_path, "final message")
    assert main({"session_id": sid, "transcript_path": transcript}) == 0
    assert _digests(tmp_path)  # digest written
    meta = store.load_meta()
    assert meta is not None and meta.ended_at  # session marked ended


def test_unsafe_session_id_bails(tmp_path):
    assert main({"session_id": "../evil", "transcript_path": "x"}) == 0
    assert _digests(tmp_path) == []


def test_empty_transcript_still_writes_metadata_digest(tmp_path, sanitizer_present):
    assert main({"session_id": "sess-empty", "transcript_path": ""}) == 0
    digests = _digests(tmp_path)
    assert len(digests) == 1
    assert "no sanitizable transcript excerpt" in digests[0].read_text(encoding="utf-8")


def test_invalid_utf8_transcript_never_raises(tmp_path, sanitizer_present):
    """QG B1: an invalid-UTF-8 transcript must not raise (write_digest must
    reach _end_session so the session is still marked ended)."""
    bad = tmp_path / "bad.jsonl"
    bad.write_bytes(b'\xff\xfe not utf-8')
    assert main({"session_id": "sess-bad", "transcript_path": str(bad)}) == 0
    assert _digests(tmp_path)  # digest still written


def test_null_byte_transcript_path_never_raises(tmp_path, sanitizer_present):
    """QG B1: a null-byte path (ValueError in read_text) is swallowed."""
    assert main({"session_id": "sess-nul", "transcript_path": "/x\x00y"}) == 0
    assert _digests(tmp_path)
