"""flow_enforcer x the bash-effect JEV site (JEV Decisions Layer PR2).

Decision 1 of the PR2 spec: the JEV is consulted only on the Python path
and only for a command the regex let through as discovery. Network is
mocked at ``urlopen``; no test reaches OpenRouter.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from _decisions_helpers import fake_ok, isolate_decisions, read_jsonl, sent_payload

from core.workflow import flow_enforcer as fe

URLOPEN = "core.decisions.client.urllib.request.urlopen"
# Discovery by the regex, a write in truth: `find -delete` is the canonical miss.
SNEAKY = "find . -name '*.pyc' -delete"
READ = "ls -la core/"


@pytest.fixture
def jev(monkeypatch, tmp_path):
    # Gated calls stop at "feature-flag-off": no transcript, no real config.
    monkeypatch.setattr(fe, "_feature_flag_on", lambda: False)
    monkeypatch.setattr(fe, "shadow_deny_on", lambda: False)
    return isolate_decisions(monkeypatch, tmp_path)


def _gating(noul: float) -> object:
    return fake_ok({"bash_effect__requires_gating": {"type": "noul", "noul": noul}})


def _flow(command: str, sid: str = "s-bash") -> fe.Decision:
    return fe._evaluate_flow("Bash", "/nonexistent", sid, "/tmp", {"command": command})


def test_regex_discovery_is_what_the_jev_sees():
    assert fe.bash_is_effect(SNEAKY) is False and fe.bash_is_effect(READ) is False


def test_discovery_plus_jev_yes_is_gated(jev, tmp_path):
    with patch(URLOPEN, return_value=_gating(0.97)) as net:
        assert fe._bash_effect_with_jev(SNEAKY, "s-bash") is True
    assert sent_payload(net)["state"] == {"command": SNEAKY}
    assert _flow_reason_after(SNEAKY, _gating(0.97)) == "feature-flag-off"
    row = read_jsonl(tmp_path / "decisions.jsonl")[0]
    assert (row["site"], row["acted_on"], row["jev_result"]) == ("bash-effect", "jev", True)


def _flow_reason_after(command: str, response: object) -> str:
    with patch(URLOPEN, return_value=response):
        return _flow(command).reason


def test_discovery_plus_jev_no_is_not_gated(jev):
    with patch(URLOPEN, return_value=_gating(0.02)) as net:
        decision = _flow(READ)
    assert net.call_count == 1
    assert decision.reason == "tool-not-gated" and decision.allow is True


def test_unsure_jev_keeps_the_regex(jev):
    # destructive threshold 0.90: p=0.8 abstains.
    with patch(URLOPEN, return_value=_gating(0.8)):
        assert fe._bash_effect_with_jev(SNEAKY, "s") is False


def test_effect_never_reaches_the_network(jev):
    with patch(URLOPEN) as net:
        assert fe._bash_effect_with_jev("git push origin master", "s") is True
        assert _flow("rm -rf build/").reason == "feature-flag-off"
    net.assert_not_called()


@pytest.mark.parametrize("command", ["", "   "])
def test_empty_command_never_reaches_the_network(jev, command):
    with patch(URLOPEN) as net:
        assert fe._bash_effect_with_jev(command, "s") is False
        assert _flow(command).reason == "tool-not-gated"
    net.assert_not_called()


def test_timeout_falls_back_to_the_regex(jev):
    with patch(URLOPEN, side_effect=TimeoutError("slow")):
        assert fe._bash_effect_with_jev(SNEAKY, "s") is False


def test_internal_error_falls_back_to_the_regex(jev, monkeypatch):
    from core.decisions import engine

    def _boom(*_a, **_k):
        raise RuntimeError("boom")

    monkeypatch.setattr(engine, "decide", _boom)
    assert fe._bash_effect_with_jev(SNEAKY, "s") is False


def test_the_call_is_capped_at_1000_ms(jev):
    """The hook ceiling reaches the wire (the hook default would be 1500)."""
    from core.decisions.sites.command import BASH_EFFECT

    with patch(URLOPEN, return_value=_gating(0.02)) as net:
        fe._bash_effect_with_jev(READ, "s")
    expected = min(fe.BASH_JEV_TIMEOUT_MS, BASH_EFFECT.timeout_ms) / 1000
    assert net.call_args.kwargs["timeout"] == pytest.approx(expected)
    assert fe.BASH_JEV_TIMEOUT_MS == 1000


def test_the_hook_cap_holds_over_an_operator_override(jev):
    """The PreToolUse hook keeps its own 1000 ms ceiling even when the
    config raises the site's ``timeoutMs`` (kills dropping ``timeout_ms``:
    the engine would take min(hookTimeoutMs 1500, 5000))."""
    from _decisions_helpers import write_config

    write_config(jev, {"sites": {"bash-effect": {"mode": "act", "timeoutMs": 5000}}})
    with patch(URLOPEN, return_value=_gating(0.02)) as net:
        fe._bash_effect_with_jev(READ, "s")
    assert net.call_args.kwargs["timeout"] == pytest.approx(1.0)


def test_bypass_touches_no_network(jev, monkeypatch):
    monkeypatch.setenv("ARKA_BYPASS_DECISIONS", "1")
    with patch(URLOPEN) as net:
        assert fe._bash_effect_with_jev(SNEAKY, "s") is False
    net.assert_not_called()


def test_bash_lines_carry_the_python_path(jev, tmp_path, monkeypatch):
    monkeypatch.setattr(fe, "TELEMETRY_PATH", tmp_path / "enforcement.jsonl")
    with patch(URLOPEN, return_value=_gating(0.02)):
        bash = _flow(READ)
    write = fe._evaluate_flow("Write", "/nonexistent", "s", "/tmp", {})
    assert (bash.bash_path, write.bash_path) == ("python", "")
    fe.record_telemetry("s", "Bash", bash, "/tmp")
    line = json.loads((tmp_path / "enforcement.jsonl").read_text())
    assert line["bash_path"] == "python"


def test_template_keeps_the_path_empty_for_the_node_fast_path():
    template = json.loads(fe.Path(__file__).resolve().parents[2].joinpath(
        "config", "hooks", "gate-manifest.json").read_text())["telemetry"]["enforcement_template"]
    assert template["bash_path"] == ""


def test_live_gate_matches_engine_active(jev, monkeypatch):
    from _decisions_helpers import write_config

    from core.decisions.config import load_decisions_config
    from core.decisions.engine import active

    for block, expected in (({}, True), ({"sites": {"bash-effect": "off"}}, False),
                            ({"sites": {"bash-effect": "shadow"}}, True),
                            ({"enabled": False}, False)):
        write_config(jev, block)
        assert fe._bash_jev_live() is active(
            load_decisions_config(), names=("bash-effect",)) is expected, block
    monkeypatch.delenv("OPENROUTER_API_KEY")
    write_config(jev, {})
    assert fe._bash_jev_live() is False


def test_keyless_discovery_never_imports_the_engine(tmp_path):
    import os
    import subprocess
    import sys

    env = {k: v for k, v in os.environ.items()
           if k not in ("ARKA_BYPASS_DECISIONS", "OPENROUTER_API_KEY")}
    env["HOME"] = str(tmp_path)
    code = (
        "import sys\n"
        "from core.workflow import flow_enforcer as fe\n"
        "assert fe._bash_effect_with_jev('ls -la', 's') is False\n"
        "print('core.decisions.engine' in sys.modules)\n"
    )
    root = fe.Path(__file__).resolve().parents[2]
    out = subprocess.run([sys.executable, "-c", code], cwd=root, env=env,
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "False"
