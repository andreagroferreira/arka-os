"""Headless `claude -p --output-format json` parsing (Runtime Sync PR2).

The CLI payload has no top-level ``model`` key; before this the recorder
wrote an empty model id on every headless row (2,803 of 16,923 live rows on
2026-09-03), so nothing headless was ever priced.
"""

from __future__ import annotations

import json
from pathlib import Path

from core.runtime import claude_code

FIXTURE = Path(__file__).parent / "fixtures" / "claude_p_output_json_2_1_259.json"


def test_fixture_is_a_real_capture_without_a_model_key():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert "model" not in payload
    assert payload.get("modelUsage")


def test_parser_takes_the_model_id_from_model_usage():
    resp = claude_code._parse_claude_cli_output(FIXTURE.read_text(encoding="utf-8"))
    assert resp.model == "claude-sonnet-5"
    usage = json.loads(FIXTURE.read_text(encoding="utf-8"))["usage"]
    assert resp.tokens_in == (
        usage["input_tokens"]
        + usage["cache_read_input_tokens"]
        + usage["cache_creation_input_tokens"]
    )
    assert resp.cached_tokens == usage["cache_read_input_tokens"]


def test_model_from_payload_prefers_the_largest_entry_and_falls_back():
    multi = {
        "modelUsage": {
            "claude-sonnet-5": {
                "inputTokens": 5,
                "cacheReadInputTokens": 0,
                "cacheCreationInputTokens": 0,
            },
            "claude-opus-5": {
                "inputTokens": 500,
                "cacheReadInputTokens": 0,
                "cacheCreationInputTokens": 0,
            },
        }
    }
    assert claude_code._model_from_payload(multi) == "claude-opus-5"
    assert claude_code._model_from_payload({"model": "claude-opus-5"}) == "claude-opus-5"
    assert claude_code._model_from_payload({"modelUsage": {}, "model": ""}) == ""
    assert claude_code._model_from_payload({}) == ""
