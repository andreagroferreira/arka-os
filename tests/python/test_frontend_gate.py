"""Tests for the frontend excellence gate (excellence-mandate, v4.2.0;
structured marker + scope hardening in Excellence Reform PR-D2)."""

import json

import pytest

from core.workflow import frontend_gate
from core.workflow.frontend_gate import (
    Decision,
    MARKER_TEMPLATE,
    evaluate,
    is_heuristic_ui_file,
    is_ui_file,
)

STRUCTURED = (
    "[arka:design] benchmark=Linear skills=frontend-design,ui-ux-pro-max "
    "tokens=design-system.yaml"
)


@pytest.fixture(autouse=True)
def _isolated_design_auth(tmp_path, monkeypatch):
    """Isolate persist-on-observe state — structured-marker tests would
    otherwise confirm 'test-session' in the real /tmp dir and leak an
    allow into the deny-path tests."""
    monkeypatch.setenv("ARKA_DESIGN_AUTH_DIR", str(tmp_path / "design-auth"))


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


def _evaluate(messages, file_path="app/components/Hero.vue", tool="Edit",
              tool_input=None):
    payload = {"file_path": file_path}
    if tool_input:
        payload.update(tool_input)
    return evaluate(
        tool_name=tool,
        transcript_path="",
        session_id="test-session",
        cwd="/tmp",
        tool_input=payload,
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
        assert is_ui_file("a/index.html")
        assert is_ui_file("a/legacy.HTM")
        assert not is_ui_file("a/store.ts")
        assert not is_ui_file("a/api.py")
        assert not is_ui_file("a/Hero")

    def test_plain_store_ts_stays_out_of_scope(self, config):
        decision = _evaluate(
            [], file_path="app/stores/cart.ts",
            tool="Write", tool_input={"content": "export const useCart = 1"},
        )
        assert decision.allow and decision.reason == "not-ui-scope"


class TestHeuristicScope:
    def test_styles_filename_is_heuristic_ui(self):
        assert is_heuristic_ui_file(
            "app/Button.styles.ts", "Write", {"content": "export {}"}
        )
        assert is_heuristic_ui_file(
            "tailwind.config.ts", "Write", {"content": "export default {}"}
        )
        assert is_heuristic_ui_file(
            "src/theme.ts", "Write", {"content": "export const t = {}"}
        )

    def test_ui_content_in_ts_is_heuristic_ui(self):
        assert is_heuristic_ui_file(
            "app/render.ts", "Edit",
            {"new_string": 'el.className="btn btn-primary"'},
        )
        assert is_heuristic_ui_file(
            "app/card.js", "Write",
            {"content": "const Card = styled.div`padding: 4px`"},
        )

    def test_multiedit_payloads_are_scanned(self):
        assert is_heuristic_ui_file(
            "app/render.ts", "MultiEdit",
            {"edits": [{"new_string": "const x = 1"},
                       {"new_string": "cva('btn')"}]},
        )

    def test_heuristic_gates_in_warn_with_own_scope(self, config):
        decision = _evaluate(
            [], file_path="app/Button.styles.ts",
            tool="Write", tool_input={"content": "export const s = {}"},
        )
        assert decision.allow
        assert decision.reason == "no-design-marker"
        assert decision.ui_scope == "heuristic"

    def test_heuristic_never_denies_even_in_hard_mode(self, config):
        config("hard")
        decision = _evaluate(
            [], file_path="app/Button.styles.ts",
            tool="Write", tool_input={"content": "export const s = {}"},
        )
        assert decision.allow, "heuristic scope is WARN-only by design"
        assert decision.ui_scope == "heuristic"


class TestModes:
    def test_missing_config_defaults_to_warn(self, config):
        decision = _evaluate([])
        assert decision.allow
        assert decision.mode == "warn"
        assert decision.reason == "no-design-marker"
        message = decision.to_stderr_message()
        assert "[arka:suggest]" in message
        assert MARKER_TEMPLATE in message

    def test_hard_mode_denies_without_marker(self, config):
        config("hard")
        decision = _evaluate([])
        assert not decision.allow
        message = decision.to_stderr_message()
        assert "[ARKA:DESIGN]" in message
        assert "excellence-mandate" in message
        assert MARKER_TEMPLATE in message

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


class TestStructuredMarker:
    def test_structured_marker_allows_in_hard_mode(self, config):
        config("hard")
        decision = _evaluate([STRUCTURED])
        assert decision.allow
        assert decision.reason == "design-evidence"
        assert decision.marker_kind == "structured"
        assert decision.marker_found.startswith("[arka:design]")

    def test_key_order_is_irrelevant(self, config):
        config("hard")
        reordered = "[arka:design] skills=frontend-design benchmark=Stripe"
        decision = _evaluate([reordered])
        assert decision.allow and decision.marker_kind == "structured"

    def test_degraded_skills_value_is_accepted(self, config):
        config("hard")
        degraded = "[arka:design] benchmark=Vercel skills=degraded:ui-ux-pro-max"
        decision = _evaluate([degraded])
        assert decision.allow and decision.marker_kind == "structured"

    def test_tokens_key_is_optional_for_passage(self, config):
        config("hard")
        minimal = "[arka:design] benchmark=Notion skills=frontend-design"
        assert _evaluate([minimal]).allow

    def test_structured_anywhere_in_window_wins_over_legacy(self, config):
        config("hard")
        messages = ["[arka:design] old-style-token", STRUCTURED, "done"]
        decision = _evaluate(messages)
        assert decision.allow and decision.marker_kind == "structured"

    def test_trivial_marker_allows_in_hard_mode(self, config):
        config("hard")
        decision = _evaluate(["[arka:trivial] one-line color fix"])
        assert decision.allow
        assert decision.reason == "design-evidence"
        assert decision.marker_kind == "trivial"


class TestLegacyMarker:
    def test_legacy_allows_in_warn_with_nudge(self, config):
        decision = _evaluate(["[arka:design] valentina-approved"])
        assert decision.allow
        assert decision.reason == "legacy-marker"
        assert decision.marker_kind == "legacy"
        message = decision.to_stderr_message()
        assert "Legacy design marker" in message
        assert MARKER_TEMPLATE in message

    def test_benchmark_without_skills_is_legacy(self, config):
        decision = _evaluate(
            ["[arka:design] frontend-design+ui-ux-pro-max benchmark=Linear"]
        )
        assert decision.reason == "legacy-marker", (
            "missing skills= key must not count as structured"
        )

    def test_legacy_denies_in_hard_mode(self, config):
        config("hard")
        decision = _evaluate(["[arka:design] valentina-approved"])
        assert not decision.allow
        assert decision.reason == "legacy-marker"


class TestBypasses:
    def test_env_bypass_allows_and_is_labelled(self, config, monkeypatch):
        config("hard")
        monkeypatch.setenv("ARKA_BYPASS_DESIGN", "1")
        decision = _evaluate([])
        assert decision.allow and decision.reason == "env-bypass"

    def test_marker_in_older_message_still_counts(self, config):
        config("hard")
        messages = [STRUCTURED, "working on it", "done"]
        assert _evaluate(messages).allow


class TestTelemetry:
    def test_records_jsonl_entry_with_marker_kind(self, config):
        decision = Decision(allow=False, reason="legacy-marker",
                            mode="hard", target_file="Hero.vue",
                            marker_kind="legacy", ui_scope="suffix")
        frontend_gate.record_telemetry("sess-1", "Edit", decision)
        lines = frontend_gate.TELEMETRY_PATH.read_text().splitlines()
        entry = json.loads(lines[0])
        assert entry["reason"] == "legacy-marker"
        assert entry["marker_kind"] == "legacy"
        assert entry["ui_scope"] == "suffix"
        assert entry["session_id"] == "sess-1"

    def test_unsafe_session_id_drops_record(self, config):
        decision = Decision(allow=True, reason="not-ui-scope")
        frontend_gate.record_telemetry("../../etc", "Edit", decision)
        assert not frontend_gate.TELEMETRY_PATH.exists()
