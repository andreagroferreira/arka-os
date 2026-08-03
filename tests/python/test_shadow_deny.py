"""PR-A5a shadow-deny: with the enforcement flags off, the three
PreToolUse gates evaluate anyway and record what they WOULD have
decided (would_block / shadow_reason / shadow_ms) while always
allowing and staying silent. Spec: .arkaos/specs/shadow-deny.yaml."""

import itertools
import json
import time
from pathlib import Path

import pytest
import yaml

from core.workflow import (
    flow_authorization,
    flow_enforcer,
    frontend_gate,
    marker_cache,
    specialist_enforcer,
)
from core.workflow.flow_enforcer import shadow_deny_on

# ─── Fixtures ───────────────────────────────────────────────────────────


@pytest.fixture
def shadow_home(tmp_path, monkeypatch):
    """Full isolation for the three gates + their persistence dirs."""
    home = tmp_path / "home"
    home.mkdir()
    cfg = home / "config.json"
    monkeypatch.setattr(flow_enforcer, "CONFIG_PATH", cfg)
    monkeypatch.setattr(frontend_gate, "CONFIG_PATH", cfg)
    monkeypatch.setattr(specialist_enforcer, "CONFIG_PATH", cfg)
    monkeypatch.setattr(
        flow_enforcer, "BYPASS_AUDIT_PATH", home / "audit" / "bypass.log"
    )
    monkeypatch.setattr(
        flow_enforcer, "TELEMETRY_PATH", home / "telemetry" / "enforcement.jsonl"
    )
    monkeypatch.setattr(
        frontend_gate, "TELEMETRY_PATH", home / "telemetry" / "fg.jsonl"
    )
    monkeypatch.setattr(
        specialist_enforcer, "TELEMETRY_PATH", home / "telemetry" / "sd.jsonl"
    )
    monkeypatch.setattr(
        specialist_enforcer, "OWNERSHIP_YAML_PATH",
        tmp_path / "agent-ownership.yaml",
    )
    specialist_enforcer._load_ownership.cache_clear()
    monkeypatch.setattr(
        flow_enforcer, "FLOW_REQUIRED_DIR", tmp_path / "wf-required"
    )
    monkeypatch.setattr(marker_cache, "MARKER_CACHE_DIR", tmp_path / "marker-cache")
    monkeypatch.setenv("ARKA_FLOW_AUTH_DIR", str(tmp_path / "flow-auth"))
    monkeypatch.setenv("ARKA_DESIGN_AUTH_DIR", str(tmp_path / "design-auth"))
    monkeypatch.setenv("ARKA_SPECIALIST_AUTH_DIR", str(tmp_path / "spec-auth"))
    monkeypatch.delenv("ARKA_BYPASS_FLOW", raising=False)
    monkeypatch.delenv("ARKA_BYPASS_DESIGN", raising=False)
    flow_enforcer.shadow_deny_on.cache_clear()
    yield home
    flow_enforcer.shadow_deny_on.cache_clear()


def _config(home: Path, **hooks) -> None:
    (home / "config.json").write_text(
        json.dumps({"hooks": hooks}), encoding="utf-8"
    )
    flow_enforcer.shadow_deny_on.cache_clear()


def _transcript(path: Path, assistant_messages: list[str]) -> Path:
    lines = [{"role": "user", "content": "implement a feature"}]
    for msg in assistant_messages:
        lines.append({"role": "assistant", "content": msg})
    path.write_text(
        "\n".join(json.dumps(line) for line in lines), encoding="utf-8"
    )
    return path


def _ownership(path: Path) -> None:
    path.write_text(
        yaml.safe_dump({
            "version": 1,
            "leads": ["paulo"],
            "c_suite": [],
            "ownership": [
                {"pattern": "**/*.vue", "owners": ["frontend-dev"]},
            ],
            "lead_allowed": [],
        }),
        encoding="utf-8",
    )


# ─── shadow_deny_on coercion ────────────────────────────────────────────


def test_shadow_flag_default_on_missing_file(shadow_home):
    assert shadow_deny_on() is True


def test_shadow_flag_default_on_corrupt(shadow_home):
    (shadow_home / "config.json").write_text("{not json", encoding="utf-8")
    shadow_deny_on.cache_clear()
    assert shadow_deny_on() is True


def test_shadow_flag_undecodable_bytes_mean_on(shadow_home):
    """Invalid UTF-8 raises UnicodeDecodeError (a ValueError) out of
    read_text — 'corrupt means ON' must hold for that input too (QG r1,
    Francisca error-handling advisory)."""
    (shadow_home / "config.json").write_bytes(b"\xff\xfe{broken")
    shadow_deny_on.cache_clear()
    assert shadow_deny_on() is True


def test_shadow_flag_missing_key_means_on(shadow_home):
    _config(shadow_home, hardEnforcement=False)
    assert shadow_deny_on() is True


def test_shadow_flag_explicit_false_off(shadow_home):
    _config(shadow_home, shadowDeny=False)
    assert shadow_deny_on() is False


def test_shadow_flag_python_truthy(shadow_home):
    _config(shadow_home, shadowDeny="false")  # non-empty string → ON
    assert shadow_deny_on() is True
    _config(shadow_home, shadowDeny=[])  # bool([]) → OFF
    assert shadow_deny_on() is False


# ─── flow_enforcer shadow ───────────────────────────────────────────────


def test_flow_shadow_marker_found(shadow_home, tmp_path):
    flow_enforcer.mark_flow_required("s-shadow")
    transcript = _transcript(
        tmp_path / "t.jsonl", ["[arka:routing] dev -> Paulo\nworking"]
    )
    d = flow_enforcer.evaluate("Write", str(transcript), "s-shadow", "/tmp")
    assert d.allow is True
    assert d.reason == "feature-flag-off"
    assert d.would_block is False
    assert d.shadow_reason == "marker-found:routing"
    assert d.marker_found == "routing"
    assert d.warning == ""


def test_flow_shadow_grace_ladder_then_would_block(shadow_home, tmp_path):
    """The shadow grace ladder mirrors enforcement exactly: graced turns
    report would_block=False; past GRACE_CAP the shadow records the
    block enforcement would have issued — while STILL allowing."""
    flow_enforcer.mark_flow_required("s-nomarker")
    transcript = _transcript(tmp_path / "t.jsonl", ["no markers here"])
    decisions = []
    for _ in range(flow_authorization.GRACE_CAP + 1):
        decisions.append(
            flow_enforcer.evaluate("Write", str(transcript), "s-nomarker", "/tmp")
        )
        flow_authorization.reset_turn("s-nomarker")
    for d in decisions:
        assert d.allow is True, "shadow must never deny"
        assert d.warning == "", "shadow must never surface a warning"
        assert d.reason == "feature-flag-off"
    for d in decisions[:-1]:
        assert d.would_block is False
        assert d.shadow_reason.startswith("first-tool-grace")
    last = decisions[-1]
    assert last.would_block is True
    assert "grace-exhausted" in last.shadow_reason


def test_flow_shadow_env_bypass_writes_no_audit(shadow_home, tmp_path, monkeypatch):
    """An env bypass of an INACTIVE gate is not a bypass — the shadow
    path must not pollute the accountability log."""
    monkeypatch.setenv("ARKA_BYPASS_FLOW", "1")
    flow_enforcer.mark_flow_required("s-bypass")
    d = flow_enforcer.evaluate("Write", "/nonexistent", "s-bypass", "/tmp")
    assert d.allow is True
    assert d.shadow_reason == "env-bypass"
    assert d.would_block is False
    assert d.bypass_used is False
    assert not flow_enforcer.BYPASS_AUDIT_PATH.exists()


def test_flow_enforced_env_bypass_still_audited(shadow_home, tmp_path, monkeypatch):
    _config(shadow_home, hardEnforcement=True)
    monkeypatch.setenv("ARKA_BYPASS_FLOW", "1")
    flow_enforcer.mark_flow_required("s-real-bypass")
    d = flow_enforcer.evaluate("Write", "/nonexistent", "s-real-bypass", "/tmp")
    assert d.reason == "env-bypass"
    assert d.bypass_used is True
    assert flow_enforcer.BYPASS_AUDIT_PATH.exists()


def test_flow_kill_switch_restores_early_return(shadow_home, monkeypatch):
    """shadowDeny=false is the pre-A5a behaviour: no evaluation at all."""
    _config(shadow_home, shadowDeny=False)
    flow_enforcer.mark_flow_required("s-kill")

    def _boom(*args, **kwargs):  # would only run if shadow evaluated
        raise AssertionError("kill-switch must prevent any transcript read")

    monkeypatch.setattr(flow_enforcer, "_load_last_assistant_messages", _boom)
    d = flow_enforcer.evaluate("Write", "/some/transcript", "s-kill", "/tmp")
    assert d.allow is True
    assert d.reason == "feature-flag-off"
    assert d.shadow_reason == ""
    assert d.would_block is False


def test_flow_enforced_deny_keeps_shadow_defaults(shadow_home, tmp_path):
    """Enforced paths never carry shadow fields — would_block is for
    what WOULD have happened, not what did."""
    _config(shadow_home, hardEnforcement=True)
    flow_enforcer.mark_flow_required("s-hard")
    transcript = _transcript(tmp_path / "t.jsonl", ["no markers"])
    last = None
    for _ in range(flow_authorization.GRACE_CAP + 1):
        last = flow_enforcer.evaluate("Write", str(transcript), "s-hard", "/tmp")
        flow_authorization.reset_turn("s-hard")
    assert last.allow is False
    assert last.would_block is False
    assert last.shadow_reason == ""
    assert last.shadow_ms == 0


def test_flow_shadow_telemetry_carries_fields(shadow_home, tmp_path):
    flow_enforcer.mark_flow_required("s-telemetry")
    transcript = _transcript(
        tmp_path / "t.jsonl", ["[arka:routing] dev -> Paulo"]
    )
    d = flow_enforcer.evaluate("Write", str(transcript), "s-telemetry", "/tmp")
    flow_enforcer.record_telemetry("s-telemetry", "Write", d, "/tmp")
    entry = json.loads(
        flow_enforcer.TELEMETRY_PATH.read_text(encoding="utf-8").splitlines()[-1]
    )
    assert entry["would_block"] is False
    assert entry["shadow_reason"] == "marker-found:routing"
    assert isinstance(entry["shadow_ms"], float)
    assert entry["shadow_ms"] >= 0


def test_flow_shadow_ms_not_hardcodable(shadow_home, tmp_path, monkeypatch):
    """shadow_ms must come from a real clock reading — a mutant that
    hard-codes 0 has to die (QG r1, Francisca B2 mutant M14). The clock
    is pinned so the assertion is exact, not >= 0."""
    ticks = [0.0, 0.5]  # start, end → 500.0 ms

    def fake_perf_counter():
        return ticks.pop(0) if ticks else 1.0

    monkeypatch.setattr(time, "perf_counter", fake_perf_counter)
    # Session NOT marked flow-required: the shadow chain early-outs at
    # the classifier, so the pinned clock is read exactly twice.
    d = flow_enforcer.evaluate("Write", "/nonexistent", "s-clock", "/tmp")
    assert d.shadow_reason == "classifier-did-not-match"
    assert d.shadow_ms == 500.0


# ─── frontend_gate shadow ───────────────────────────────────────────────


def _fg_evaluate(messages, file_path="app/Hero.vue"):
    return frontend_gate.evaluate(
        tool_name="Edit", transcript_path="", session_id="fg-shadow",
        cwd="/tmp", tool_input={"file_path": file_path}, messages=messages,
    )


def test_frontend_off_shadow_would_block(shadow_home):
    _config(shadow_home, frontendGate=False)
    d = _fg_evaluate([])
    assert d.allow is True
    assert d.reason == "flag-off"
    assert d.would_block is True
    assert d.shadow_reason == "no-design-marker"
    assert d.to_stderr_message() == ""


def test_frontend_off_shadow_structured_marker(shadow_home):
    _config(shadow_home, frontendGate=False)
    d = _fg_evaluate(
        ["[arka:design] benchmark=Linear skills=frontend-design tokens=none"]
    )
    assert d.would_block is False
    assert d.shadow_reason == "design-evidence"
    assert d.marker_kind == "structured"


def test_frontend_off_kill_switch(shadow_home):
    _config(shadow_home, frontendGate=False, shadowDeny=False)
    d = _fg_evaluate([])
    assert d.allow is True
    assert d.reason == "flag-off"
    assert d.shadow_reason == ""
    assert d.would_block is False


def test_frontend_off_shadow_env_bypass(shadow_home, monkeypatch):
    _config(shadow_home, frontendGate=False)
    monkeypatch.setenv("ARKA_BYPASS_DESIGN", "1")
    d = _fg_evaluate([])
    assert d.would_block is False
    assert d.shadow_reason == "env-bypass"


def test_frontend_warn_annotates_would_block(shadow_home):
    # warn is the default mode; annotation adds zero transcript reads
    # → shadow_ms stays 0
    d = _fg_evaluate([])
    assert d.allow is True
    assert d.mode == "warn"
    assert d.would_block is True
    assert d.shadow_reason == "no-design-marker"
    assert d.shadow_ms == 0


def test_frontend_warn_heuristic_never_would_block(shadow_home):
    d = frontend_gate.evaluate(
        tool_name="Write", transcript_path="", session_id="fg-shadow",
        cwd="/tmp",
        tool_input={"file_path": "app/Button.styles.ts", "content": "x"},
        messages=[],
    )
    assert d.ui_scope == "heuristic"
    assert d.would_block is False, "heuristic scope never denies in hard"


def test_frontend_warn_kill_switch_no_annotation(shadow_home):
    _config(shadow_home, frontendGate="warn", shadowDeny=False)
    d = _fg_evaluate([])
    assert d.would_block is False
    assert d.shadow_reason == ""


def test_frontend_hard_deny_keeps_shadow_defaults(shadow_home):
    _config(shadow_home, frontendGate="hard")
    d = _fg_evaluate([])
    assert d.allow is False
    assert d.would_block is False
    assert d.shadow_reason == ""


def test_frontend_off_shadow_loads_transcript(shadow_home, tmp_path):
    """Off-mode shadow with messages=None reads the transcript itself —
    the only load on this path (QG r1, Francisca coverage advisory)."""
    _config(shadow_home, frontendGate=False)
    transcript = _transcript(
        tmp_path / "t.jsonl",
        ["[arka:design] benchmark=Linear skills=frontend-design tokens=none"],
    )
    d = frontend_gate.evaluate(
        tool_name="Edit", transcript_path=str(transcript),
        session_id="fg-load", cwd="/tmp",
        tool_input={"file_path": "app/Hero.vue"}, messages=None,
    )
    assert d.reason == "flag-off"
    assert d.would_block is False
    assert d.shadow_reason == "design-evidence"
    assert d.marker_kind == "structured"


# ─── specialist_enforcer shadow ─────────────────────────────────────────


def test_specialist_shadow_lead_blocked(shadow_home, tmp_path):
    _ownership(specialist_enforcer.OWNERSHIP_YAML_PATH)
    transcript = _transcript(
        tmp_path / "tx.jsonl", ["[arka:routing] dev -> Paulo\nworking"]
    )
    d = specialist_enforcer.evaluate(
        tool_name="Write", transcript_path=str(transcript),
        session_id="sp-shadow",
        tool_input={"file_path": "/Users/me/proj/src/App.vue"},
    )
    assert d.allow is True
    assert d.reason == "feature-flag-off"
    assert d.would_block is True
    assert d.shadow_reason.startswith("lead-blocked:paulo")
    assert d.current_persona == "paulo"
    assert "frontend-dev" in d.required_owners
    assert d.to_stderr_message() == ""


def test_specialist_shadow_owner_match(shadow_home, tmp_path):
    _ownership(specialist_enforcer.OWNERSHIP_YAML_PATH)
    transcript = _transcript(
        tmp_path / "tx.jsonl", ["[arka:dispatch] paulo -> frontend-dev"]
    )
    d = specialist_enforcer.evaluate(
        tool_name="Write", transcript_path=str(transcript),
        session_id="sp-owner",
        tool_input={"file_path": "/Users/me/proj/src/App.vue"},
    )
    assert d.allow is True
    assert d.would_block is False
    assert d.shadow_reason == "owner-match:frontend-dev"


def test_specialist_shadow_bypass_not_counted(shadow_home, tmp_path):
    """Mirror of test_flow_shadow_env_bypass_writes_no_audit for the
    specialist gate (QG r1, Francisca B1): a bypass marker seen by an
    INACTIVE gate must not inflate the 'Bypasses used' accountability
    counter — shadow_reason still records it, so nothing is lost."""
    _ownership(specialist_enforcer.OWNERSHIP_YAML_PATH)
    transcript = _transcript(
        tmp_path / "tx.jsonl",
        [
            "[arka:routing] dev -> Paulo",
            "[arka:specialist-bypass owner=frontend-dev reason=the "
            "specialist is unavailable right now and this is urgent]",
        ],
    )
    d = specialist_enforcer.evaluate(
        tool_name="Write", transcript_path=str(transcript),
        session_id="sp-bypass",
        tool_input={"file_path": "/Users/me/proj/src/App.vue"},
    )
    assert d.allow is True
    assert d.reason == "feature-flag-off"
    assert d.shadow_reason == "bypass-with-reason"
    assert d.bypass_used is False
    assert d.bypass_reason is None
    assert d.would_block is False
    specialist_enforcer.record_telemetry("sp-bypass", "Write", d)
    entry = json.loads(
        specialist_enforcer.TELEMETRY_PATH.read_text(
            encoding="utf-8"
        ).splitlines()[-1]
    )
    assert entry["bypass_used"] is False
    assert entry["bypass_reason"] is None


def test_pre_tool_use_attributes_parse_to_shadow(shadow_home, tmp_path, monkeypatch):
    """The parse a shadow evaluation forces happens in _MessagesOnce.load,
    outside every gate's timer — the first shadow decision claims it into
    shadow_ms and the claim is one-shot (QG r1, Francisca B2). The pin is
    EXACT (QG r2, Francisca B2): the claimed parse cost is captured and
    the final shadow_ms must equal the gate's own elapsed plus that
    claim — a disabled timing mechanism (claimed 0) fails here, where a
    bare `> 0` would still pass on the gate's inner timer alone."""
    from core.hooks import pre_tool_use

    counter = itertools.count()
    monkeypatch.setattr(
        time, "perf_counter", lambda: next(counter) * 0.001
    )
    _ownership(specialist_enforcer.OWNERSHIP_YAML_PATH)
    transcript = _transcript(
        tmp_path / "t.jsonl", ["[arka:routing] dev -> Paulo"]
    )
    captured = {}
    real_evaluate = specialist_enforcer.evaluate

    def spy(**kwargs):
        decision = real_evaluate(**kwargs)
        captured["decision"] = decision
        captured["pre_ms"] = decision.shadow_ms
        return decision

    monkeypatch.setattr(specialist_enforcer, "evaluate", spy)
    real_consume = pre_tool_use._MessagesOnce.consume_load_ms

    def consume_spy(self):
        value = real_consume(self)
        captured.setdefault("claimed", value)
        return value

    monkeypatch.setattr(
        pre_tool_use._MessagesOnce, "consume_load_ms", consume_spy
    )
    root = str(Path(specialist_enforcer.__file__).resolve().parents[2])
    shared = pre_tool_use._MessagesOnce(str(transcript))
    code = pre_tool_use._specialist_gate(
        root, "Write", str(transcript), "pt-attr", "/tmp",
        {"file_path": "/x/App.vue"}, shared,
    )
    assert code is None
    decision = captured["decision"]
    assert decision.shadow_reason != ""
    assert captured["claimed"] > 0, (
        "the forced parse must cost > 0 under the tick clock — a "
        "disabled load timer shows up here"
    )
    assert decision.shadow_ms == round(
        captured["pre_ms"] + captured["claimed"], 3
    ), "shadow_ms must equal the gate's own elapsed plus the parse claim"
    assert shared.consume_load_ms() == 0.0, "the claim must be one-shot"


def test_specialist_kill_switch_no_read(shadow_home, monkeypatch):
    _config(shadow_home, shadowDeny=False)

    def _boom(*args, **kwargs):
        raise AssertionError("kill-switch must prevent any transcript read")

    from core.workflow import transcript_scope
    monkeypatch.setattr(transcript_scope, "split_from_path", _boom)
    d = specialist_enforcer.evaluate(
        tool_name="Write", transcript_path="/some/transcript",
        session_id="sp-kill", tool_input={"file_path": "/x/App.vue"},
    )
    assert d.allow is True
    assert d.reason == "feature-flag-off"
    assert d.shadow_reason == ""


def test_pre_tool_use_shares_parse_under_shadow(shadow_home, tmp_path, monkeypatch):
    """PR-A5a in _specialist_gate: with the flags off and shadow on, the
    hook loads and SHARES the transcript parse (one read across gates);
    with the kill-switch thrown it keeps the zero-read fast path."""
    from core.hooks import pre_tool_use

    _ownership(specialist_enforcer.OWNERSHIP_YAML_PATH)
    transcript = _transcript(
        tmp_path / "t.jsonl", ["[arka:routing] dev -> Paulo"]
    )
    captured = {}
    real_evaluate = specialist_enforcer.evaluate

    def spy(**kwargs):
        captured["messages"] = kwargs.get("messages")
        return real_evaluate(**kwargs)

    monkeypatch.setattr(specialist_enforcer, "evaluate", spy)
    root = str(Path(specialist_enforcer.__file__).resolve().parents[2])

    shared = pre_tool_use._MessagesOnce(str(transcript))
    code = pre_tool_use._specialist_gate(
        root, "Write", str(transcript), "pt-shadow", "/tmp",
        {"file_path": "/x/App.vue"}, shared,
    )
    assert code is None
    assert captured["messages"] is not None, "shadow must share ONE parse"
    assert shared.peek() is not None

    _config(shadow_home, shadowDeny=False)
    cold = pre_tool_use._MessagesOnce(str(transcript))
    code = pre_tool_use._specialist_gate(
        root, "Write", str(transcript), "pt-kill", "/tmp",
        {"file_path": "/x/App.vue"}, cold,
    )
    assert code is None
    assert captured["messages"] is None, "kill-switch keeps zero-read path"
    assert cold.peek() is None


def test_post_metrics_carry_shadow_attribution(shadow_home, tmp_path, monkeypatch):
    """hook-metrics entries must carry the flag labels (QG r2, Francisca
    B1 — she deleted _shadow_attribution's body and 7771 tests stayed
    green; this is the ~10-line test she prescribed and executed)."""
    from core.hooks import post_tool_use

    post_home = tmp_path / "post-home"
    post_home.mkdir()
    monkeypatch.setenv("HOME", str(post_home))
    _config(shadow_home, hardEnforcement=False)
    post_tool_use._log_metrics(5, post_tool_use._shadow_attribution())
    entries = json.loads(
        (post_home / ".arkaos" / "hook-metrics.json").read_text(encoding="utf-8")
    )
    assert entries[-1]["duration_ms"] == 5
    assert entries[-1]["enforcement"] is False
    assert entries[-1]["shadow"] is True

    _config(shadow_home, hardEnforcement=False, shadowDeny=False)
    post_tool_use._log_metrics(7, post_tool_use._shadow_attribution())
    entries = json.loads(
        (post_home / ".arkaos" / "hook-metrics.json").read_text(encoding="utf-8")
    )
    assert entries[-1]["duration_ms"] == 7
    assert entries[-1]["shadow"] is False


def test_post_benign_run_logs_shadow_delegation(shadow_home, tmp_path, monkeypatch):
    """A BENIGN post run — exactly where the shadow-forced flow-auth
    delegations live — must write a labelled metrics entry with
    delegation="benign" (QG r2, Eduardo B1: the early exit previously
    returned before the only _log_metrics call, so the kill-switch
    population was never recorded)."""
    # Pre-import BEFORE faking HOME: main() lazy-imports this module and
    # its DEFAULT_PATH is derived from Path.home() at import time — a
    # first import under the faked HOME poisons sys.modules for every
    # later test in the process (it broke the manifest byte-parity test).
    import core.runtime.mcp_telemetry  # noqa: F401
    from core.hooks import post_tool_use

    post_home = tmp_path / "post-home-benign"
    post_home.mkdir()
    monkeypatch.setenv("HOME", str(post_home))
    code = post_tool_use.main(stdin_json={
        "tool_name": "Read", "session_id": "pm-benign",
        "tool_response": {"stdout": "3 lines", "stderr": ""},
        "transcript_path": "", "cwd": "/tmp",
    })
    assert code == 0
    entries = json.loads(
        (post_home / ".arkaos" / "hook-metrics.json").read_text(encoding="utf-8")
    )
    assert entries[-1]["delegation"] == "benign"
    assert entries[-1]["enforcement"] is False
    assert entries[-1]["shadow"] is True


def test_delegation_kind_mirrors_shim_precedence():
    """_delegation_kind derives the shim's own decision order (failure
    event, then the stateful set, then the error trigger, else benign)
    from the payload alone — pure function, no I/O."""
    from core.hooks.post_tool_use import _delegation_kind

    failure = {"hook_event_name": "PostToolUseFailure"}
    assert _delegation_kind(failure, "Task", benign=True) == "error"
    for tool in ("ExitPlanMode", "Task", "Agent"):
        assert _delegation_kind({}, tool, benign=True) == "stateful"
        assert _delegation_kind({}, tool, benign=False) == "stateful"
    assert _delegation_kind({}, "Read", benign=True) == "benign"
    assert _delegation_kind({}, "Bash", benign=False) == "error"


def test_shadow_ms_preserves_sub_ms_in_all_gates(shadow_home, monkeypatch):
    """A 0.4 ms shadow evaluation must record 0.4, not 0 — an int()
    truncation reintroduced in ANY of the three gates dies here (QG r2,
    Francisca M1; she proved 0.0 -> 0.0004 s gives 0.4 where int()
    gives 0). The clock returns 0.0 once, then 0.0004 forever, so
    intermediate perf_counter calls cannot skew the outer window."""
    _ownership(specialist_enforcer.OWNERSHIP_YAML_PATH)

    def pinned():
        vals = iter([0.0])
        return lambda: next(vals, 0.0004)

    monkeypatch.setattr(time, "perf_counter", pinned())
    d = flow_enforcer.evaluate("Write", "/nonexistent", "s-frac", "/tmp")
    assert d.shadow_ms == 0.4

    _config(shadow_home, frontendGate=False)
    monkeypatch.setattr(time, "perf_counter", pinned())
    df = _fg_evaluate([])
    assert df.shadow_ms == 0.4

    monkeypatch.setattr(time, "perf_counter", pinned())
    ds = specialist_enforcer.evaluate(
        tool_name="Write", transcript_path="/nonexistent",
        session_id="s-frac-sp", tool_input={"file_path": "/x/App.vue"},
    )
    assert ds.shadow_ms == 0.4


def test_specialist_enforced_block_keeps_shadow_defaults(shadow_home, tmp_path):
    _config(shadow_home, specialistEnforcement=True)
    _ownership(specialist_enforcer.OWNERSHIP_YAML_PATH)
    transcript = _transcript(
        tmp_path / "tx.jsonl", ["[arka:routing] dev -> Paulo"]
    )
    d = specialist_enforcer.evaluate(
        tool_name="Write", transcript_path=str(transcript),
        session_id="sp-hard",
        tool_input={"file_path": "/Users/me/proj/src/App.vue"},
    )
    assert d.allow is False
    assert d.would_block is False
    assert d.shadow_reason == ""
