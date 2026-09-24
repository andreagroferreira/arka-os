"""frontend_gate x the ui-in-ts JEV site (JEV Decisions Layer PR3, site #17).

Jev is consulted only for a .ts/.js/.mjs/.cjs payload the regex heuristic
called "not UI"; it can add a WARN (ui_scope=heuristic), never a deny,
never remove a gate. Network is mocked at ``urlopen``.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from _decisions_helpers import fake_ok, isolate_decisions, read_jsonl, sent_payload

from core.workflow import frontend_gate as fg

URLOPEN = "core.decisions.client.urllib.request.urlopen"
# UI in truth, invisible to the regex (no className=/styled/@apply/tailwind/cva).
SNEAKY = "export function banner(el) {\n  el.innerHTML = '<h1>Hi</h1>';\n}\n"
UI_REGEX = "export const Button = () => <b className='x' />;\n"


@pytest.fixture
def jev(monkeypatch, tmp_path):
    home = isolate_decisions(monkeypatch, tmp_path)
    monkeypatch.setenv("ARKA_DESIGN_AUTH_DIR", str(tmp_path / "design-auth"))
    monkeypatch.setattr(fg, "TELEMETRY_PATH", tmp_path / "frontend-gate.jsonl")
    monkeypatch.setattr(fg, "shadow_deny_on", lambda: False)
    monkeypatch.delenv("ARKA_BYPASS_DESIGN", raising=False)
    _gate_mode(monkeypatch, tmp_path, "warn")
    return home


def _gate_mode(monkeypatch, tmp_path: Path, mode: str) -> None:
    path = tmp_path / "gate-config.json"
    path.write_text(json.dumps({"hooks": {"frontendGate": mode}}), encoding="utf-8")
    monkeypatch.setattr(fg, "CONFIG_PATH", path)


def _is_ui(noul: float) -> object:
    return fake_ok({"ui_in_ts__is_ui_code": {"type": "noul", "noul": noul}})


def _write(path: str, content: str, tool: str = "Write") -> fg.Decision:
    key = "content" if tool == "Write" else "new_string"
    return fg.evaluate(tool, "/nonexistent", "s-ui", "/tmp", {"file_path": path, key: content},
                       messages=[])


def test_regex_miss_is_what_jev_sees():
    assert fg.is_heuristic_ui_file("src/banner.ts", "Write", {"content": SNEAKY}) is False


def test_jev_yes_escalates_to_a_warn(jev, tmp_path):
    with patch(URLOPEN, return_value=_is_ui(0.95)) as net:
        decision = _write("src/banner.ts", SNEAKY)
    assert net.call_count == 1
    assert sent_payload(net)["state"] == {"path": "src/banner.ts", "content": SNEAKY}
    assert (decision.allow, decision.reason, decision.ui_scope) == (
        True, "no-design-marker", "heuristic")
    row = read_jsonl(tmp_path / "decisions.jsonl")[0]
    assert (row["site"], row["acted_on"]) == ("ui-in-ts", "jev")


def test_jev_yes_never_denies_even_in_hard_mode(jev, tmp_path, monkeypatch):
    _gate_mode(monkeypatch, tmp_path, "hard")
    with patch(URLOPEN, return_value=_is_ui(0.99)):
        decision = _write("src/banner.mjs", SNEAKY, tool="Edit")
    assert decision.allow is True and decision.ui_scope == "heuristic"
    assert decision.mode == "hard"


def test_jev_no_or_unsure_keeps_the_heuristic(jev):
    for noul in (0.02, 0.6):  # write threshold 0.75: 0.6 abstains
        with patch(URLOPEN, return_value=_is_ui(noul)):
            assert _write(f"src/store-{noul}.ts", SNEAKY).reason == "not-ui-scope"


@pytest.mark.parametrize(("path", "content"), [
    ("src/button.ts", UI_REGEX),        # the regex already said UI
    ("tailwind.config.ts", "export default {}\n"),  # filename heuristic
    ("src/App.vue", "<template/>"),      # suffix scope
    ("core/x.py", SNEAKY),               # not a .ts/.js payload
    ("src/empty.ts", "   "),             # nothing to judge
])
def test_jev_is_never_asked_outside_its_escalation(jev, path, content):
    with patch(URLOPEN) as net:
        _write(path, content)
    net.assert_not_called()


def test_regex_ui_is_never_downgraded_by_a_hostile_jev(jev):
    with patch(URLOPEN, return_value=_is_ui(0.0)) as net:
        decision = _write("src/button.ts", UI_REGEX)
    net.assert_not_called()
    assert decision.ui_scope == "heuristic" and decision.reason == "no-design-marker"


def test_bypass_never_reaches_the_network(jev, monkeypatch):
    monkeypatch.setenv("ARKA_BYPASS_DECISIONS", "1")
    with patch(URLOPEN) as net:
        assert _write("src/banner.ts", SNEAKY).reason == "not-ui-scope"
    net.assert_not_called()


def test_gate_off_or_design_bypass_never_reaches_the_network(jev, tmp_path, monkeypatch):
    _gate_mode(monkeypatch, tmp_path, "off")
    with patch(URLOPEN) as net:
        assert _write("src/banner.ts", SNEAKY).reason == "not-ui-scope"
        _gate_mode(monkeypatch, tmp_path, "warn")
        monkeypatch.setenv("ARKA_BYPASS_DESIGN", "1")
        assert _write("src/banner.ts", SNEAKY).reason == "not-ui-scope"
    net.assert_not_called()


def test_no_key_never_reaches_the_network(jev, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY")
    with patch(URLOPEN) as net:
        assert _write("src/banner.ts", SNEAKY).reason == "not-ui-scope"
    net.assert_not_called()


def test_jev_failure_keeps_the_heuristic(jev):
    with patch(URLOPEN, side_effect=OSError("down")):
        assert _write("src/banner.ts", SNEAKY).reason == "not-ui-scope"


def test_ceiling_is_600_ms():
    assert fg.UI_JEV_TIMEOUT_MS == 600
    from core.decisions.sites.governance import UI_IN_TS, UI_TS_SUFFIXES

    assert UI_IN_TS.timeout_ms == 600 and UI_IN_TS.direction == "escalate_only"
    assert UI_TS_SUFFIXES == fg._HEURISTIC_SUFFIXES


# Source code is content, so ui-in-ts is `diff` class (ADR Decision 2): with
# no redaction list it is refused before the network, as a diff would be.
CLIENT_CODE = "export const TENANT = 'acmebank';\nexport function tag(el) { el.innerHTML = 'x'; }\n"


def test_ui_in_ts_is_diff_class():
    from core.decisions.sites.governance import UI_IN_TS

    assert UI_IN_TS.state_class == "diff"


@pytest.mark.parametrize("scaffold", [None, {"clients": []}])
def test_no_redaction_list_never_reaches_the_network(jev, tmp_path, scaffold):
    config = jev / ".arkaos" / "redaction-clients.json"
    if scaffold is None:
        config.unlink()
    else:  # the default install's scaffold (installer/user-data-scaffold.js)
        config.write_text(json.dumps(scaffold), encoding="utf-8")
    with patch(URLOPEN, return_value=_is_ui(0.99)) as net:
        decision = _write("src/billing/acme.ts", CLIENT_CODE)
    net.assert_not_called()
    assert (decision.allow, decision.reason) == (True, "not-ui-scope")
    row = read_jsonl(tmp_path / "decisions.jsonl")[0]  # the fallback is counted
    assert (row["site"], row["reason"]) == ("ui-in-ts", "egress-denied:redaction-config-missing")


def test_client_names_are_redacted_in_the_sent_code(monkeypatch, tmp_path):
    isolate_decisions(monkeypatch, tmp_path, clients=["acmebank"])
    monkeypatch.setenv("ARKA_DESIGN_AUTH_DIR", str(tmp_path / "design-auth"))
    monkeypatch.setattr(fg, "TELEMETRY_PATH", tmp_path / "frontend-gate.jsonl")
    monkeypatch.setattr(fg, "shadow_deny_on", lambda: False)
    _gate_mode(monkeypatch, tmp_path, "warn")
    with patch(URLOPEN, return_value=_is_ui(0.99)) as net:
        decision = _write("src/billing/tenant.ts", CLIENT_CODE)
    assert net.call_count == 1 and decision.ui_scope == "heuristic"
    body = json.dumps(sent_payload(net))
    assert "acmebank" not in body.lower() and "innerHTML" in body
