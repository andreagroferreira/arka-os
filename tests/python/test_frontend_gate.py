"""Tests for the frontend excellence gate (excellence-mandate, v4.2.0)."""

import json

import pytest

from core.workflow import frontend_gate
from core.workflow.frontend_gate import Decision, evaluate, is_ui_file


@pytest.fixture
def config(tmp_path, monkeypatch):
    """Point CONFIG_PATH/TELEMETRY_PATH at tmp; return a mode-setter."""
    config_path = tmp_path / "config.json"
    monkeypatch.setattr(frontend_gate, "CONFIG_PATH", config_path)
    monkeypatch.setattr(
        frontend_gate, "TELEMETRY_PATH", tmp_path / "telemetry" / "fg.jsonl"
    )
    monkeypatch.delenv("ARKA_BYPASS_DESIGN", raising=False)

    def set_mode(value):
        config_path.write_text(
            json.dumps({"hooks": {"frontendGate": value}}), encoding="utf-8"
        )

    return set_mode


def _evaluate(messages, file_path="app/components/Hero.vue", tool="Edit"):
    return evaluate(
        tool_name=tool,
        transcript_path="",
        session_id="test-session",
        cwd="/tmp",
        tool_input={"file_path": file_path},
        messages=messages,
    )


class TestScope:
    def test_non_gated_tool_allows(self, config):
        decision = _evaluate([], tool="Read")
        assert decision.allow and decision.reason == "not-ui-scope"

    def test_non_ui_file_allows(self, config):
        decision = _evaluate([], file_path="core/workflow/state.py")
        assert decision.allow and decision.reason == "not-ui-scope"

    def test_ui_suffixes(self):
        assert is_ui_file("a/Hero.vue")
        assert is_ui_file("a/Hero.tsx")
        assert is_ui_file("a/hero.CSS")
        assert is_ui_file("a/Hero.svelte")
        assert not is_ui_file("a/store.ts")
        assert not is_ui_file("a/api.py")
        assert not is_ui_file("a/Hero")


class TestModes:
    def test_missing_config_defaults_to_warn(self, config):
        decision = _evaluate([])
        assert decision.allow
        assert decision.mode == "warn"
        assert decision.reason == "no-design-marker"
        assert "[arka:suggest]" in decision.to_stderr_message()

    def test_hard_mode_denies_without_marker(self, config):
        config("hard")
        decision = _evaluate([])
        assert not decision.allow
        message = decision.to_stderr_message()
        assert "[ARKA:DESIGN]" in message
        assert "excellence-mandate" in message
        assert "[arka:design]" in message

    def test_true_means_hard(self, config):
        config(True)
        assert not _evaluate([]).allow

    def test_off_disables_gate(self, config):
        config(False)
        decision = _evaluate([])
        assert decision.allow and decision.reason == "flag-off"

    def test_corrupt_config_degrades_to_warn(self, config, monkeypatch):
        frontend_gate.CONFIG_PATH.write_text("{not json", encoding="utf-8")
        decision = _evaluate([])
        assert decision.allow and decision.mode == "warn"


class TestEvidence:
    def test_design_marker_allows_in_hard_mode(self, config):
        config("hard")
        messages = ["[arka:design] frontend-design+ui-ux-pro-max benchmark=Linear"]
        decision = _evaluate(messages)
        assert decision.allow
        assert decision.reason == "design-evidence"
        assert decision.marker_found.startswith("[arka:design]")

    def test_trivial_marker_allows_in_hard_mode(self, config):
        config("hard")
        decision = _evaluate(["[arka:trivial] one-line color fix"])
        assert decision.allow and decision.reason == "design-evidence"

    def test_env_bypass_allows_and_is_labelled(self, config, monkeypatch):
        config("hard")
        monkeypatch.setenv("ARKA_BYPASS_DESIGN", "1")
        decision = _evaluate([])
        assert decision.allow and decision.reason == "env-bypass"

    def test_marker_in_older_message_still_counts(self, config):
        config("hard")
        messages = ["[arka:design] valentina-approved", "working on it", "done"]
        assert _evaluate(messages).allow


class TestTelemetry:
    def test_records_jsonl_entry(self, config):
        decision = Decision(allow=False, reason="no-design-marker",
                            mode="hard", target_file="Hero.vue")
        frontend_gate.record_telemetry("sess-1", "Edit", decision)
        lines = frontend_gate.TELEMETRY_PATH.read_text().splitlines()
        entry = json.loads(lines[0])
        assert entry["reason"] == "no-design-marker"
        assert entry["session_id"] == "sess-1"

    def test_unsafe_session_id_drops_record(self, config):
        decision = Decision(allow=True, reason="not-ui-scope")
        frontend_gate.record_telemetry("../../etc", "Edit", decision)
        assert not frontend_gate.TELEMETRY_PATH.exists()
