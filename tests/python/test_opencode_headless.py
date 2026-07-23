"""OpenCode headless parsing — locked to the LIVE-verified JSONL shapes.

The fixtures below are (trimmed) captures from a real ``opencode run
--format json`` against opencode 1.18.4 on 2026-07-23 — the same
verification that flipped ``capabilities()["headless"]`` to True. If
OpenCode changes its event stream, these tests fail before users hit
a silent mis-parse.
"""

from __future__ import annotations

import pytest

from core.runtime.llm_provider import LLMUnavailable
from core.runtime.opencode import (
    OpenCodeAdapter,
    _first_error_message,
    _parse_opencode_output,
)

# Trimmed live capture: step_start -> text -> step_finish.
_LIVE_STREAM = "\n".join([
    '{"type":"step_start","timestamp":1,"sessionID":"s","part":{"type":"step-start"}}',
    '{"type":"text","timestamp":1,"sessionID":"s","part":{"type":"text","text":"ok"}}',
    '{"type":"step_finish","timestamp":1,"sessionID":"s","part":{"reason":"stop",'
    '"type":"step-finish","tokens":{"total":89793,"input":3,"output":4,'
    '"reasoning":0,"cache":{"write":89786,"read":12}},"cost":0.11}}',
])

# Live capture of the broken-default-model failure mode.
_LIVE_ERROR = (
    '{"type":"error","timestamp":1,"sessionID":"s","error":{"name":"UnknownError",'
    '"data":{"message":"Unexpected server error. Check server logs for details.",'
    '"ref":"err_x"}}}'
)


def test_parses_text_and_tokens_from_the_live_stream():
    response = _parse_opencode_output(_LIVE_STREAM)
    assert response.text == "ok"
    assert response.tokens_in == 3
    assert response.tokens_out == 4
    assert response.cached_tokens == 12
    assert response.model == ""


def test_multiple_text_parts_concatenate_in_order():
    stream = "\n".join([
        '{"type":"text","part":{"type":"text","text":"foo "}}',
        '{"type":"text","part":{"type":"text","text":"bar"}}',
    ])
    assert _parse_opencode_output(stream).text == "foo bar"


def test_error_event_raises_llm_unavailable_with_the_event_message():
    with pytest.raises(LLMUnavailable, match="Unexpected server error"):
        _parse_opencode_output(_LIVE_ERROR)
    assert "Unexpected server error" in _first_error_message(_LIVE_ERROR)


def test_no_jsonl_degrades_to_raw_text_with_estimate():
    response = _parse_opencode_output("plain text answer, no events")
    assert response.text == "plain text answer, no events"
    assert response.tokens_out >= 1
    assert response.tokens_in == 0


def test_garbage_lines_are_skipped_not_fatal():
    stream = "\n".join([
        "{not json",
        '{"type":"text","part":{"type":"text","text":"ok"}}',
        "trailing noise",
    ])
    assert _parse_opencode_output(stream).text == "ok"


def test_headless_supported_tracks_the_binary(monkeypatch):
    import core.runtime.opencode as mod

    monkeypatch.setattr(mod.shutil, "which", lambda _: "/usr/local/bin/opencode")
    assert OpenCodeAdapter().headless_supported() is True
    monkeypatch.setattr(mod.shutil, "which", lambda _: None)
    assert OpenCodeAdapter().headless_supported() is False


def test_headless_complete_without_binary_raises(monkeypatch):
    import core.runtime.opencode as mod

    monkeypatch.setattr(mod.shutil, "which", lambda _: None)
    with pytest.raises(NotImplementedError, match="not found on PATH"):
        OpenCodeAdapter().headless_complete("hi")
