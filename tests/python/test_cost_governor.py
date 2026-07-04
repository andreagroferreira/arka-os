"""Tests for the CostGovernor (core/runtime/cost_governor.py)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from core.runtime import cost_governor
from core.runtime.cost_governor import GovernorDecision, check, main


# ─── Helpers ──────────────────────────────────────────────────────────


def _write_config(tmp_path, budget: dict | None):
    path = tmp_path / "config.json"
    data = {} if budget is None else {"budget": budget}
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _write_telemetry(tmp_path, rows: list[dict]):
    path = tmp_path / "llm-cost.jsonl"
    lines = []
    for row in rows:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "session_id": "s1",
            "provider": "native",
            "model": "m",
            "tokens_in": 10,
            "tokens_out": 5,
            "cached_tokens": 0,
            "estimated_cost_usd": 1.0,
            "category": "",
        }
        entry.update(row)
        lines.append(json.dumps(entry))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# ─── check() ──────────────────────────────────────────────────────────


class TestCheck:
    def test_no_budget_config_allows(self, tmp_path):
        config = _write_config(tmp_path, None)
        telemetry = _write_telemetry(tmp_path, [{"estimated_cost_usd": 999.0}])
        decision = check("s1", config_path=config, telemetry_path=telemetry)
        assert decision.allow and decision.reason == "no-cap"

    def test_config_file_missing_allows(self, tmp_path):
        decision = check(
            "s1",
            config_path=tmp_path / "nope.json",
            telemetry_path=tmp_path / "nope.jsonl",
        )
        assert decision.allow and decision.reason == "no-cap"

    def test_null_caps_mean_no_cap(self, tmp_path):
        config = _write_config(
            tmp_path, {"hardCapUsd": None, "dailyCapUsd": None}
        )
        decision = check("s1", config_path=config, telemetry_path=None)
        assert decision.allow and decision.reason == "no-cap"

    def test_under_cap_allows(self, tmp_path):
        config = _write_config(tmp_path, {"hardCapUsd": 10.0})
        telemetry = _write_telemetry(tmp_path, [{"estimated_cost_usd": 2.5}])
        decision = check("s1", config_path=config, telemetry_path=telemetry)
        assert decision.allow and decision.reason == "under-cap"
        assert decision.spent_usd == 2.5
        assert decision.cap_usd == 10.0
        assert decision.to_warning() == ""

    def test_telemetry_file_missing_never_blocks(self, tmp_path):
        config = _write_config(
            tmp_path, {"hardCapUsd": 0.01, "hardDeny": True}
        )
        decision = check(
            "s1", config_path=config, telemetry_path=tmp_path / "absent.jsonl"
        )
        assert decision.allow
        assert decision.spent_usd == 0.0

    def test_session_cap_exceeded_warn_default(self, tmp_path):
        config = _write_config(tmp_path, {"hardCapUsd": 3.0})
        telemetry = _write_telemetry(
            tmp_path,
            [{"estimated_cost_usd": 2.0}, {"estimated_cost_usd": 2.0}],
        )
        decision = check("s1", config_path=config, telemetry_path=telemetry)
        assert decision.allow  # warn-first: exceeded but not denied
        assert decision.reason == "session-cap-exceeded"
        assert decision.exceeded
        warning = decision.to_warning()
        assert "[arka:warn] budget cap exceeded" in warning
        assert "$4.00 of $3.00" in warning

    def test_session_cap_exceeded_hard_deny(self, tmp_path):
        config = _write_config(tmp_path, {"hardCapUsd": 3.0, "hardDeny": True})
        telemetry = _write_telemetry(tmp_path, [{"estimated_cost_usd": 5.0}])
        decision = check("s1", config_path=config, telemetry_path=telemetry)
        assert not decision.allow
        assert decision.hard_deny

    def test_other_sessions_do_not_count_toward_session_cap(self, tmp_path):
        config = _write_config(tmp_path, {"hardCapUsd": 3.0, "hardDeny": True})
        telemetry = _write_telemetry(
            tmp_path,
            [
                {"session_id": "other", "estimated_cost_usd": 50.0},
                {"session_id": "s1", "estimated_cost_usd": 1.0},
            ],
        )
        decision = check("s1", config_path=config, telemetry_path=telemetry)
        assert decision.allow and decision.reason == "under-cap"

    def test_daily_cap_aggregates_all_sessions(self, tmp_path):
        config = _write_config(tmp_path, {"dailyCapUsd": 5.0})
        telemetry = _write_telemetry(
            tmp_path,
            [
                {"session_id": "a", "estimated_cost_usd": 3.0},
                {"session_id": "b", "estimated_cost_usd": 4.0},
            ],
        )
        decision = check("s1", config_path=config, telemetry_path=telemetry)
        assert decision.allow  # warn-only by default
        assert decision.reason == "daily-cap-exceeded"
        assert decision.spent_usd == 7.0

    def test_daily_cap_ignores_yesterday(self, tmp_path):
        yesterday = (
            datetime.now(timezone.utc) - timedelta(days=2)
        ).isoformat()
        config = _write_config(tmp_path, {"dailyCapUsd": 5.0})
        telemetry = _write_telemetry(
            tmp_path,
            [{"session_id": "a", "estimated_cost_usd": 100.0, "ts": yesterday}],
        )
        decision = check("s1", config_path=config, telemetry_path=telemetry)
        assert decision.allow and decision.reason == "under-cap"

    def test_null_cost_rows_do_not_count(self, tmp_path):
        config = _write_config(tmp_path, {"hardCapUsd": 1.0, "hardDeny": True})
        telemetry = _write_telemetry(
            tmp_path, [{"estimated_cost_usd": None}] * 5
        )
        decision = check("s1", config_path=config, telemetry_path=telemetry)
        assert decision.allow and decision.reason == "under-cap"

    def test_invalid_cap_values_fail_open(self, tmp_path):
        config = _write_config(
            tmp_path, {"hardCapUsd": "lots", "dailyCapUsd": -3}
        )
        decision = check("s1", config_path=config, telemetry_path=None)
        assert decision.allow and decision.reason == "no-cap"


# ─── CLI ──────────────────────────────────────────────────────────────


class TestCli:
    @pytest.fixture()
    def cli_env(self, tmp_path, monkeypatch):
        """Point the CLI defaults (config + telemetry) at tmp paths."""
        config = tmp_path / "config.json"
        monkeypatch.setattr(cost_governor, "DEFAULT_CONFIG_PATH", config)
        telemetry = tmp_path / "llm-cost.jsonl"
        monkeypatch.setenv("ARKA_LLM_COST_PATH", str(telemetry))
        return config, telemetry

    def test_exit_0_when_allowed(self, cli_env, capsys):
        assert main(["session-x"]) == 0
        assert "ALLOW" in capsys.readouterr().out

    def test_exit_3_when_denied(self, cli_env, tmp_path, capsys):
        config, _ = cli_env
        config.write_text(
            json.dumps({"budget": {"hardCapUsd": 1.0, "hardDeny": True}}),
            encoding="utf-8",
        )
        _write_telemetry(tmp_path, [{"estimated_cost_usd": 9.0}])
        assert main(["s1"]) == 3
        assert "DENY" in capsys.readouterr().out

    def test_json_output(self, cli_env, capsys):
        assert main(["session-x", "--json"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["allow"] is True
        assert payload["reason"] == "no-cap"


# ─── GovernorDecision ─────────────────────────────────────────────────


class TestGovernorDecision:
    def test_warning_empty_when_under_cap(self):
        d = GovernorDecision(True, "under-cap", 1.0, 5.0)
        assert d.to_warning() == ""

    def test_warning_format_when_exceeded(self):
        d = GovernorDecision(True, "daily-cap-exceeded", 12.345, 10.0)
        assert d.to_warning() == (
            "[arka:warn] budget cap exceeded ($12.35 of $10.00) "
            "— daily-cap-exceeded"
        )
