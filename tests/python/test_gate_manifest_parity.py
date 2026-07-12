"""Gate-manifest parity — the committed manifest never drifts (F2-6).

Three layers of protection:
1. Byte parity: ``render()`` regenerated in memory must equal the
   committed ``config/hooks/gate-manifest.json`` exactly. A constant
   change in any source module fails here with the regeneration command.
2. Corpora vs the REAL functions: every embedded corpus expectation is
   executed against the actual Python implementation (``bash_is_effect``,
   ``safe_session_id``, ``_ERROR_TRIGGER_RE``, gate routing, cost
   governor, hardEnforcement flag) — the corpus cannot encode a wrong
   expectation. The node:test side runs the SAME corpora against
   engine.cjs, so drift on either side breaks the build.
3. Semantics pins: telemetry templates equal the real serializer
   output; flag/budget resolution matches the real functions on fixture
   configs; every exported regex compiles and carries no JS-incompatible
   construct.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from pathlib import Path

import pytest

from core.hooks import gate_manifest
from core.hooks.gate_manifest import build_manifest, manifest_path, render


@pytest.fixture(scope="module")
def committed() -> dict:
    return json.loads(manifest_path().read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def manifest() -> dict:
    return build_manifest()


def test_committed_manifest_is_byte_identical_to_generator():
    committed_text = manifest_path().read_text(encoding="utf-8")
    assert committed_text == render(), (
        "config/hooks/gate-manifest.json drifted from the source "
        "constants — run `python -m core.hooks.gate_manifest` and commit"
    )


def test_bash_corpus_matches_real_classifier(committed):
    from core.workflow.flow_enforcer import bash_is_effect

    for case in committed["corpora"]["bash"]:
        real = "effect" if bash_is_effect(case["cmd"]) else "discovery"
        assert real == case["expect"], (
            f"corpus expectation wrong for {case['cmd']!r}: real "
            f"bash_is_effect says {real}, corpus says {case['expect']}"
        )


def test_pre_tool_corpus_matches_gate_routing(committed):
    """fast_allow == provably never denied by any Python gate: outside
    the flow-gated set AND outside the research set (pre_tool_use.main
    order: research check happens inside the kb gate for every tool)."""
    flow_gated = set(committed["tools"]["flow_gated"])
    research = set(committed["tools"]["research_external"])
    for case in committed["corpora"]["pre_tools"]:
        tool = case["tool"]
        if tool in research:
            expected = "delegate"
        elif tool not in flow_gated:
            expected = "fast_allow"
        else:
            expected = "delegate"
        assert expected == case["expect"], f"corpus wrong for {tool!r}"


def test_session_id_corpus_matches_strict_validator(committed):
    from core.shared.safe_session_id import safe_session_id

    for case in committed["corpora"]["session_ids"]:
        real = safe_session_id(case["sid"]) is not None
        assert real == case["expect"], f"corpus wrong for {case['sid']!r}"


def test_error_trigger_corpus_matches_real_regex(committed):
    from core.hooks.post_tool_use import _ERROR_TRIGGER_RE

    for case in committed["corpora"]["error_trigger"]:
        real = bool(_ERROR_TRIGGER_RE.search(case["output"]))
        assert real == case["expect"], f"corpus wrong for {case['output']!r}"


def test_kb_first_template_equals_real_serializer(committed, tmp_path,
                                                  monkeypatch):
    from core.workflow import research_gate

    telemetry = tmp_path / "kb_first.jsonl"
    monkeypatch.setattr(research_gate, "TELEMETRY_PATH", telemetry)
    decision = research_gate.Decision(allow=True, reason="tool-not-gated")
    research_gate.record_telemetry(
        session_id="parity-sid", tool="Read", decision=decision
    )
    line = json.loads(telemetry.read_text(encoding="utf-8"))
    ts = line.pop("ts")
    _assert_py_isoformat(ts)
    assert line.pop("session_id") == "parity-sid"
    assert line.pop("tool") == "Read"
    assert line == committed["telemetry"]["kb_first_template"]


def test_enforcement_template_equals_real_serializer(committed, tmp_path,
                                                     monkeypatch):
    from core.workflow import flow_enforcer

    telemetry = tmp_path / "enforcement.jsonl"
    monkeypatch.setattr(flow_enforcer, "TELEMETRY_PATH", telemetry)
    decision = flow_enforcer.Decision(allow=True, reason="tool-not-gated")
    flow_enforcer.record_telemetry(
        session_id="parity-sid", tool="Bash", decision=decision, cwd="/w"
    )
    line = json.loads(telemetry.read_text(encoding="utf-8"))
    line.pop("ts")
    assert line.pop("session_id") == "parity-sid"
    assert line.pop("tool") == "Bash"
    assert line.pop("cwd") == "/w"
    assert line == committed["telemetry"]["enforcement_template"]


def test_mcp_record_matches_manifest_keys(committed, tmp_path):
    from core.runtime.mcp_telemetry import record

    dest = tmp_path / "mcp.jsonl"
    assert record("mcp__obsidian__search_notes", session_id="s1", path=dest)
    line = json.loads(dest.read_text(encoding="utf-8"))
    assert list(line.keys()) == committed["telemetry"]["mcp_keys"]
    assert line["server"] == "obsidian"
    assert line["tool"] == "search_notes"
    assert not record("Read", session_id="s1", path=dest)


def test_hard_enforcement_flag_semantics(committed, tmp_path, monkeypatch):
    """Pin the {missing, corrupt, python-truthy} trio the manifest
    declares against the real flow_enforcer resolution."""
    from core.workflow import flow_enforcer

    config = tmp_path / "config.json"
    monkeypatch.setattr(flow_enforcer, "CONFIG_PATH", config)
    flags = committed["flags"]["hardEnforcement"]

    assert flow_enforcer._feature_flag_on() is flags["on_missing_file"]
    config.write_text("{not json", encoding="utf-8")
    assert flow_enforcer._feature_flag_on() is flags["on_corrupt"]
    for raw, expected in [
        (True, True), (False, False), ("false", True),  # python-truthy!
        ("", False), (0, False), ([], False), ({}, False), (1, True),
    ]:
        config.write_text(
            json.dumps({"hooks": {"hardEnforcement": raw}}), encoding="utf-8"
        )
        assert flow_enforcer._feature_flag_on() is expected, (
            f"hardEnforcement={raw!r} must resolve {expected}"
        )


def test_budget_semantics_match_cost_governor(committed, tmp_path):
    """A budget is ACTIVE (shim must delegate Bash) iff cost_governor
    would do more than the immediate no-cap allow."""
    from core.runtime.cost_governor import check

    def active(config_body: str | None) -> bool:
        config = tmp_path / "config.json"
        if config_body is None:
            config.unlink(missing_ok=True)
        else:
            config.write_text(config_body, encoding="utf-8")
        return check("parity-sid", config_path=config).reason != "no-cap"

    assert active(None) is False                       # missing file
    assert active("{broken") is False                  # corrupt → {} → no-cap
    assert active("{}") is False
    assert active('{"budget": {}}') is False
    assert active('{"budget": {"hardCapUsd": null}}') is False
    assert active('{"budget": {"hardCapUsd": 0}}') is False
    assert active('{"budget": {"hardCapUsd": -5}}') is False
    assert active('{"budget": {"hardCapUsd": "lots"}}') is False
    assert active('{"budget": {"hardCapUsd": 8.5}}') is True
    assert active('{"budget": {"dailyCapUsd": 1}}') is True


def test_exported_regexes_compile_and_are_js_safe(committed):
    entries = list(committed["bash"]["effect_patterns"])
    entries.append(committed["post"]["error_trigger"])
    entries.append(
        {k: committed["session_id"][k] for k in ("py", "js", "flags")}
    )
    for entry in entries:
        re.compile(entry["py"])
        for construct in gate_manifest._JS_INCOMPATIBLE:
            assert construct not in entry["js"], (
                f"JS-incompatible {construct!r} in {entry['js']!r}"
            )


def test_numbers_pin_source_constants(committed):
    from core.hooks.pre_tool_use import _ASSISTANT_WINDOW
    from core.workflow.flow_authorization import (
        DEFAULT_TTL_SECONDS,
        GRACE_CAP,
    )

    numbers = committed["numbers"]
    assert numbers["assistant_window"] == _ASSISTANT_WINDOW
    assert numbers["grace_cap"] == GRACE_CAP
    assert numbers["auth_ttl_seconds"] == DEFAULT_TTL_SECONDS


def test_node_timestamp_shape_parses_as_python_isoformat():
    """The Node side emits ms padded to 6 digits — datetime.fromisoformat
    must accept it (telemetry summarisers parse with fromisoformat)."""
    from datetime import datetime

    parsed = datetime.fromisoformat("2026-07-12T13:49:27.902000+00:00")
    assert parsed.tzinfo is not None


def test_generator_refuses_js_incompatible_patterns():
    with pytest.raises(ValueError, match="not portable"):
        gate_manifest._js_pattern(re.compile(r"(?P<name>x)"))


def _assert_py_isoformat(ts: str) -> None:
    from datetime import datetime

    parsed = datetime.fromisoformat(ts)
    assert parsed.tzinfo is not None
