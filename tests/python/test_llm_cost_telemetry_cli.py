"""Tests for the `/arka costs` CLI wrapper."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from core.runtime import llm_cost_telemetry_cli as cli


@pytest.fixture()
def populated_telemetry(tmp_path, monkeypatch) -> Path:
    """Build a 5-entry JSONL the CLI can aggregate."""
    path = tmp_path / "llm-cost.jsonl"
    monkeypatch.setenv("ARKA_LLM_COST_PATH", str(path))
    now = datetime.now(timezone.utc)
    rows = [
        {
            "ts": now.isoformat(),
            "session_id": "sess-a",
            "provider": "anthropic",
            "model": "claude-opus-4-7",
            "tokens_in": 2000,
            "tokens_out": 400,
            "cached_tokens": 500,
            "estimated_cost_usd": 0.075,
        },
        {
            "ts": (now - timedelta(hours=1)).isoformat(),
            "session_id": "sess-a",
            "provider": "anthropic",
            "model": "claude-sonnet-4-6",
            "tokens_in": 1500,
            "tokens_out": 300,
            "cached_tokens": 0,
            "estimated_cost_usd": 0.009,
        },
        {
            "ts": (now - timedelta(days=2)).isoformat(),
            "session_id": "sess-b",
            "provider": "openai",
            "model": "gpt-4",
            "tokens_in": 800,
            "tokens_out": 200,
            "cached_tokens": 0,
            "estimated_cost_usd": 0.036,
        },
        {
            "ts": (now - timedelta(days=10)).isoformat(),
            "session_id": "sess-c",
            "provider": "google",
            "model": "gemini-2.5-pro",
            "tokens_in": 5000,
            "tokens_out": 1000,
            "cached_tokens": 0,
            "estimated_cost_usd": 0.011,
        },
        {
            "ts": (now - timedelta(days=45)).isoformat(),
            "session_id": "sess-d",
            "provider": "anthropic",
            "model": "claude-opus-4-7",
            "tokens_in": 10000,
            "tokens_out": 2000,
            "cached_tokens": 1000,
            "estimated_cost_usd": 7.50,  # triggers advisory
        },
    ]
    path.write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8"
    )
    return path


def _run(args: list[str]) -> tuple[int, str, str]:
    stdout, stderr = io.StringIO(), io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = cli.main(["llm-cost-cli", *args])
    return code, stdout.getvalue(), stderr.getvalue()


def test_cli_default_is_today(populated_telemetry: Path):
    code, out, err = _run([])
    assert code == 0
    assert err == ""
    assert "LLM costs — today" in out
    # Only the two entries from today make it in.
    assert "Calls: **2**" in out


def test_cli_week_period(populated_telemetry: Path):
    code, out, _ = _run(["week"])
    assert code == 0
    assert "LLM costs — week" in out
    # 3 entries fall inside the rolling 7-day window.
    assert "Calls: **3**" in out


def test_cli_month_period(populated_telemetry: Path):
    code, out, _ = _run(["month"])
    assert code == 0
    assert "LLM costs — month" in out
    # 4 entries fall inside the rolling 30-day window.
    assert "Calls: **4**" in out


def test_cli_all_period(populated_telemetry: Path):
    code, out, _ = _run(["all"])
    assert code == 0
    assert "LLM costs — all" in out
    assert "Calls: **5**" in out
    # Spender over $5 must produce an advisory.
    assert "Advisories" in out
    assert "sess-d" in out


def test_cli_sessions_mode(populated_telemetry: Path):
    code, out, _ = _run(["sessions"])
    assert code == 0
    assert "top expensive sessions" in out
    # The most expensive session should appear first in the table.
    lines = out.splitlines()
    session_rows = [line for line in lines if line.startswith("| sess-")]
    assert session_rows
    assert "sess-d" in session_rows[0]


def test_cli_unknown_period_exits_nonzero(populated_telemetry: Path):
    code, out, err = _run(["yearly"])
    assert code == 1
    assert out == ""
    assert "Unknown period" in err


def test_cli_output_contains_markdown_table(populated_telemetry: Path):
    code, out, _ = _run(["all"])
    assert code == 0
    assert "| Key | Calls | Tokens in | Tokens out | Cache hit | Cost |" in out
    assert "| --- | ---: | ---: | ---: | ---: | ---: |" in out


def test_cli_handles_case_insensitive_period(populated_telemetry: Path):
    code, out, err = _run(["ALL"])
    assert code == 0, err
    assert "LLM costs — all" in out


def test_cli_empty_file_renders_gracefully(tmp_path, monkeypatch):
    path = tmp_path / "empty.jsonl"
    path.write_text("", encoding="utf-8")
    monkeypatch.setenv("ARKA_LLM_COST_PATH", str(path))
    code, out, _ = _run(["today"])
    assert code == 0
    assert "Calls: **0**" in out
    assert "Total cost: **n/a**" in out


def test_cli_unknown_models_bucketed(tmp_path, monkeypatch):
    path = tmp_path / "unknown.jsonl"
    now = datetime.now(timezone.utc)
    path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "ts": now.isoformat(),
                        "session_id": "s",
                        "provider": "stub",
                        "model": "",
                        "tokens_in": 100,
                        "tokens_out": 50,
                        "cached_tokens": 0,
                        "estimated_cost_usd": None,
                    }
                )
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("ARKA_LLM_COST_PATH", str(path))
    code, out, _ = _run(["today"])
    assert code == 0
    assert "<unknown>" in out
