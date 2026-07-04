"""Tests for native usage extraction (core/runtime/native_usage.py)."""

from __future__ import annotations

import json

import pytest

from core.runtime.llm_cost_telemetry import read_entries
from core.runtime.native_usage import extract_last_usage, record_native_usage


# ─── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture()
def tmp_cost_file(tmp_path, monkeypatch):
    path = tmp_path / "llm-cost.jsonl"
    monkeypatch.setenv("ARKA_LLM_COST_PATH", str(path))
    yield path


@pytest.fixture()
def cursor_dir(tmp_path):
    return tmp_path / "native-cost"


def _assistant_record(uuid, model="claude-haiku-4-5", usage=None):
    return {
        "type": "assistant",
        "uuid": uuid,
        "message": {
            "role": "assistant",
            "model": model,
            "content": [{"type": "text", "text": "hi"}],
            "usage": usage
            if usage is not None
            else {
                "input_tokens": 10,
                "output_tokens": 7,
                "cache_read_input_tokens": 5,
                "cache_creation_input_tokens": 3,
            },
        },
    }


def _write_transcript(tmp_path, records, name="transcript.jsonl"):
    path = tmp_path / name
    path.write_text(
        "\n".join(json.dumps(r) if isinstance(r, dict) else r for r in records)
        + "\n",
        encoding="utf-8",
    )
    return str(path)


# ─── extract_last_usage ───────────────────────────────────────────────


class TestExtractLastUsage:
    def test_returns_last_assistant_with_usage(self, tmp_path):
        transcript = _write_transcript(
            tmp_path,
            [
                {"type": "user", "message": {"role": "user", "content": "q"}},
                _assistant_record("u1"),
                _assistant_record(
                    "u2",
                    usage={"input_tokens": 99, "output_tokens": 1},
                ),
            ],
        )
        usage = extract_last_usage(transcript)
        assert usage is not None
        assert usage["uuid"] == "u2"
        assert usage["input_tokens"] == 99
        assert usage["cache_read_input_tokens"] == 0  # missing key → 0

    def test_assistant_without_usage_skipped(self, tmp_path):
        no_usage = {
            "type": "assistant",
            "uuid": "u3",
            "message": {"role": "assistant", "content": "text only"},
        }
        transcript = _write_transcript(
            tmp_path, [_assistant_record("u1"), no_usage]
        )
        usage = extract_last_usage(transcript)
        assert usage is not None and usage["uuid"] == "u1"

    def test_model_extracted(self, tmp_path):
        transcript = _write_transcript(
            tmp_path, [_assistant_record("u1", model="claude-x")]
        )
        assert extract_last_usage(transcript)["model"] == "claude-x"

    def test_no_assistant_usage_returns_none(self, tmp_path):
        transcript = _write_transcript(
            tmp_path,
            [{"type": "user", "message": {"role": "user", "content": "q"}}],
        )
        assert extract_last_usage(transcript) is None

    def test_missing_file_returns_none(self, tmp_path):
        assert extract_last_usage(str(tmp_path / "absent.jsonl")) is None

    def test_empty_path_returns_none(self):
        assert extract_last_usage("") is None

    def test_malformed_lines_skipped(self, tmp_path):
        transcript = _write_transcript(
            tmp_path,
            ["{not json", "", _assistant_record("u1"), "[1,2,3]"],
        )
        usage = extract_last_usage(transcript)
        assert usage is not None and usage["uuid"] == "u1"

    def test_uuid_falls_back_to_line_index(self, tmp_path):
        record = _assistant_record("x")
        del record["uuid"]
        transcript = _write_transcript(tmp_path, [record])
        assert extract_last_usage(transcript)["uuid"] == "line:0"

    def test_non_numeric_tokens_clamped_to_zero(self, tmp_path):
        transcript = _write_transcript(
            tmp_path,
            [
                _assistant_record(
                    "u1",
                    usage={"input_tokens": "many", "output_tokens": 4},
                )
            ],
        )
        usage = extract_last_usage(transcript)
        assert usage["input_tokens"] == 0
        assert usage["output_tokens"] == 4


# ─── record_native_usage ──────────────────────────────────────────────


class TestRecordNativeUsage:
    def test_records_once_with_category_and_tokens(
        self, tmp_path, tmp_cost_file, cursor_dir
    ):
        transcript = _write_transcript(tmp_path, [_assistant_record("u1")])
        assert record_native_usage(transcript, "sess-1", cursor_dir) is True
        rows = read_entries(tmp_cost_file)
        assert len(rows) == 1
        row = rows[0]
        assert row["category"] == "native:session"
        assert row["provider"] == "native"
        assert row["model"] == "claude-haiku-4-5"
        # 10 fresh + 5 cache-read + 3 cache-write = 18 billable input
        assert row["tokens_in"] == 18
        assert row["tokens_out"] == 7
        assert row["cached_tokens"] == 5
        # claude-haiku-4-5 is a priced alias → real (non-null) cost
        assert row["estimated_cost_usd"] is not None

    def test_dedupe_cursor_blocks_second_record(
        self, tmp_path, tmp_cost_file, cursor_dir
    ):
        transcript = _write_transcript(tmp_path, [_assistant_record("u1")])
        assert record_native_usage(transcript, "sess-1", cursor_dir) is True
        assert record_native_usage(transcript, "sess-1", cursor_dir) is False
        assert len(read_entries(tmp_cost_file)) == 1

    def test_new_turn_records_again(self, tmp_path, tmp_cost_file, cursor_dir):
        records = [_assistant_record("u1")]
        transcript = _write_transcript(tmp_path, records)
        assert record_native_usage(transcript, "sess-1", cursor_dir) is True
        records.append(_assistant_record("u2"))
        transcript = _write_transcript(tmp_path, records)
        assert record_native_usage(transcript, "sess-1", cursor_dir) is True
        assert len(read_entries(tmp_cost_file)) == 2

    def test_unknown_model_records_null_cost(
        self, tmp_path, tmp_cost_file, cursor_dir
    ):
        transcript = _write_transcript(
            tmp_path, [_assistant_record("u1", model="claude-unknown-9")]
        )
        assert record_native_usage(transcript, "sess-1", cursor_dir) is True
        row = read_entries(tmp_cost_file)[0]
        assert row["estimated_cost_usd"] is None
        assert row["tokens_in"] == 18  # tokens still recorded

    def test_unsafe_session_id_rejected(
        self, tmp_path, tmp_cost_file, cursor_dir
    ):
        transcript = _write_transcript(tmp_path, [_assistant_record("u1")])
        assert record_native_usage(transcript, "../evil", cursor_dir) is False
        assert read_entries(tmp_cost_file) == []

    def test_missing_transcript_returns_false(
        self, tmp_path, tmp_cost_file, cursor_dir
    ):
        assert (
            record_native_usage(str(tmp_path / "gone.jsonl"), "s", cursor_dir)
            is False
        )

    def test_never_raises_on_unwritable_cursor_dir(
        self, tmp_path, tmp_cost_file
    ):
        transcript = _write_transcript(tmp_path, [_assistant_record("u1")])
        result = record_native_usage(
            transcript, "sess-1", "/dev/null/impossible"
        )
        assert result is False
