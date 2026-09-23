"""core.decisions.privacy — home normalised, capped, redacted, secrets refused."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from _decisions_helpers import isolate_decisions

from core.decisions import privacy
from core.decisions.client import DecisionUnavailable
from core.decisions.privacy import MAX_STATE_CHARS, prepare_state

FAKE_AWS = "AKIA" + "Q" * 16  # built at runtime: no literal secret in the repo


@pytest.fixture
def home(monkeypatch, tmp_path) -> Path:
    return isolate_decisions(monkeypatch, tmp_path, clients=["acmecorp"])


def test_plain_text_passes(home):
    assert prepare_state("corrige o bug do login", redact=True) == "corrige o bug do login"


def test_home_paths_normalised(home):
    text = f"abre {home}/Work/app.py e ~/notes.md e {str(home).upper()}/x"
    out = prepare_state(text, redact=True)
    assert out == "abre <home>/Work/app.py e <home>/notes.md e <home>/x"


def test_dict_roundtrips_as_dict(home):
    out = prepare_state({"prompt": f"ver {home}/a", "recent": ["x"]}, redact=True)
    assert out == {"prompt": "ver <home>/a", "recent": ["x"]}


def test_client_names_redacted(home):
    out = prepare_state("envia a proposta à AcmeCorp hoje", redact=True)
    assert isinstance(out, str) and "acmecorp" not in out.lower()


def _drop_config(home: Path) -> None:
    (home / ".arkaos" / "redaction-clients.json").unlink()


def _audit_lines(home: Path) -> list[dict]:
    path = home / ".arkaos" / "egress" / "audit.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _telemetry(home: Path) -> list[dict]:
    path = home.parent / "decisions.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


@pytest.mark.parametrize("state_class", ["prompt", "command"])
def test_missing_config_prompt_and_command_still_leave(home, state_class):
    # Kills: dropping the DEGRADABLE branch (raises instead of returning).
    _drop_config(home)
    out = prepare_state(f"corrige {home}/app.py", redact=True, state_class=state_class,
                        session_id="s1")
    assert out == "corrige <home>/app.py"
    last = _audit_lines(home)[-1]
    # Kills: skipping _audit_override (the deny line would be the last one).
    assert last["allowed"] is True
    assert last["override"] == f"redaction-config-missing:{state_class}"


def test_empty_client_list_is_treated_as_missing(home):
    # The sanitizer raises on {"clients": []} too (verified by execution).
    (home / ".arkaos" / "redaction-clients.json").write_text('{"clients": []}', "utf-8")
    assert prepare_state("olá", redact=True, state_class="prompt") == "olá"


@pytest.mark.parametrize("state_class", ["diff", "transcript", "mystery"])
def test_missing_config_diff_transcript_unknown_fail_closed(home, state_class):
    # Kills: widening DEGRADABLE, or a default-allow for unknown classes.
    _drop_config(home)
    with pytest.raises(DecisionUnavailable) as info:
        prepare_state("olá", redact=True, state_class=state_class)
    assert info.value.reason == "egress-denied:redaction-config-missing"


def test_missing_config_still_refuses_secrets(home):
    # Kills: _degraded returning the text without _refuse_secrets.
    _drop_config(home)
    with pytest.raises(DecisionUnavailable) as info:
        prepare_state(f"usa {FAKE_AWS}", redact=True, state_class="prompt")
    assert info.value.reason == "egress-denied:secret"


@pytest.mark.parametrize("content", ["{nope", "[1]", '{"clients": [7]}', '{"other": 1}'])
def test_unreadable_config_is_not_degradable(home, content):
    # The loader reads all of these as "no clients"; an operator WITH a
    # list must not have it silently skipped. Kills: dropping _config_absent.
    (home / ".arkaos" / "redaction-clients.json").write_text(content, "utf-8")
    with pytest.raises(DecisionUnavailable) as info:
        prepare_state("olá", redact=True, state_class="prompt")
    assert info.value.reason == "egress-denied:redaction-config-missing"


def test_dangling_config_symlink_is_not_absent(home):
    cfg = home / ".arkaos" / "redaction-clients.json"
    cfg.unlink()
    cfg.symlink_to(home / "nowhere.json")
    with pytest.raises(DecisionUnavailable):
        prepare_state("olá", redact=True, state_class="prompt")


def test_config_dir_unreadable_is_not_absent(home):
    cfg = home / ".arkaos" / "redaction-clients.json"
    cfg.unlink()
    cfg.mkdir()  # exists, read_text raises IsADirectoryError (OSError)
    with pytest.raises(DecisionUnavailable):
        prepare_state("olá", redact=True, state_class="prompt")


def test_missing_config_without_audit_does_not_leave(home, monkeypatch):
    # Kills: ignoring the audit.record result ("no audit, no egress").
    _drop_config(home)
    monkeypatch.setattr(privacy.audit, "record", lambda *a, **k: False)
    with pytest.raises(DecisionUnavailable) as info:
        prepare_state("olá", redact=True, state_class="prompt")
    assert info.value.reason == "egress-denied:audit-unavailable"


def test_audit_path_failure_does_not_leave(home, monkeypatch):
    _drop_config(home)

    def _boom(*_a: object) -> Path:
        raise OSError("no home")

    monkeypatch.setattr(privacy.audit, "default_audit_path", _boom)
    with pytest.raises(DecisionUnavailable):
        prepare_state("olá", redact=True, state_class="prompt")


def test_missing_config_noted_once_per_session(home):
    # Kills: removing the O_EXCL marker (one line per turn instead of per session).
    _drop_config(home)
    for _ in range(3):
        prepare_state("olá", redact=True, session_id="sA")
    prepare_state("olá", redact=True, session_id="sB")
    notes = [r for r in _telemetry(home) if r["site"] == "egress-notice"]
    assert [(r["session_id"], r["reason"]) for r in notes] == [
        ("sA", "redaction-config-missing"), ("sB", "redaction-config-missing"),
    ]
    assert all(r["fallback_used"] is False for r in notes)


def test_client_list_present_writes_no_notice(home):
    prepare_state("olá", redact=True, session_id="sA")
    assert _telemetry(home) == []


def test_fictional_clients_redacted_in_structured_state(home):
    (home / ".arkaos" / "redaction-clients.json").write_text(
        json.dumps({"clients": ["zorblax industries", "quuxcorp"]}), "utf-8")
    out = prepare_state({"prompt": "proposta Zorblax Industries", "recent": ["QuuxCorp login"]},
                        redact=True)
    blob = json.dumps(out).lower()
    assert "zorblax" not in blob and "quuxcorp" not in blob
    assert "[CLIENT-1]" in out["prompt"] and "[CLIENT-2]" in out["recent"][0]


def test_cap_never_splits_a_client_name(home):
    # Kills: capping BEFORE redaction ("Zorblax" of "Zorblax Industries" left).
    (home / ".arkaos" / "redaction-clients.json").write_text(
        json.dumps({"clients": ["zorblax industries"]}), "utf-8")
    cut = MAX_STATE_CHARS - len("…[truncated]")
    text = "a" * (cut - 8) + " Zorblax Industries tail"
    out = prepare_state(text, redact=True)
    assert "zorblax" not in out.lower()


def test_cap_never_ships_a_secret_prefix(home):
    # Kills: capping BEFORE the secret check (a key prefix shipped).
    cut = MAX_STATE_CHARS - len("…[truncated]")
    with pytest.raises(DecisionUnavailable) as info:
        prepare_state("b" * (cut - 6) + " " + FAKE_AWS, redact=False)
    assert info.value.reason == "egress-denied:secret"


def test_scan_cut_drops_the_straddling_tail(home, monkeypatch):
    # Kills: removing the _TAIL_GUARD trim after a pre-scan cut.
    monkeypatch.setattr(privacy, "MAX_SCAN_CHARS", 20_000)
    text = "c" * (20_000 - 5) + FAKE_AWS
    out = prepare_state(text, redact=False)
    assert isinstance(out, str) and "AKIA" not in out
    assert len(out) == 20_000 - privacy._TAIL_GUARD


def test_strictest_state_class():
    assert privacy.strictest_state_class(["prompt", "diff", "command"]) == "diff"
    assert privacy.strictest_state_class(["transcript", "diff"]) == "transcript"
    assert privacy.strictest_state_class(["prompt", "weird"]) == "weird"
    assert privacy.strictest_state_class([]) == "prompt"


def test_secret_denied_with_redaction(home):
    with pytest.raises(DecisionUnavailable) as info:
        prepare_state(f"usa a chave {FAKE_AWS}", redact=True)
    assert info.value.reason == "egress-denied:secret"


def test_secret_refused_without_redaction(home, monkeypatch):
    monkeypatch.setattr(privacy, "evaluate", _must_not_run)
    with pytest.raises(DecisionUnavailable) as info:
        prepare_state({"k": FAKE_AWS}, redact=False)
    assert info.value.reason == "egress-denied:secret"
    assert prepare_state(f"{home}/x", redact=False) == "<home>/x"


def test_redaction_disabled_is_still_audited(home, monkeypatch):
    # Kills: _unredacted skipping _audit_override (an unaudited egress).
    monkeypatch.setattr(privacy, "evaluate", _must_not_run)
    prepare_state("olá", redact=False)
    assert _audit_lines(home)[-1]["override"] == "redact-disabled"
    monkeypatch.setattr(privacy.audit, "record", lambda *a, **k: False)
    with pytest.raises(DecisionUnavailable) as info:
        prepare_state("olá", redact=False)
    assert info.value.reason == "egress-denied:audit-unavailable"


def _must_not_run(*_a: object, **_k: object) -> None:
    raise AssertionError("egress evaluate must not run when redact=False")


def test_cap_marks_truncation(home):
    out = prepare_state("a" * (MAX_STATE_CHARS + 10), redact=False)
    assert isinstance(out, str) and len(out) == MAX_STATE_CHARS
    assert out.endswith("[truncated]")


def test_capped_dict_ships_as_text(home):
    out = prepare_state({"prompt": "a" * (MAX_STATE_CHARS + 10)}, redact=False)
    assert isinstance(out, str) and out.startswith('{"prompt"')


def test_unserialisable_state_is_invalid_shape(home):
    class Loop(dict):
        pass

    loop: dict = Loop()
    loop["self"] = loop
    with pytest.raises(DecisionUnavailable) as info:
        prepare_state(loop, redact=False)
    assert info.value.reason == "invalid-shape"


def test_denial_without_findings_is_generic(home, monkeypatch):
    class _Denied:
        allowed, redacted_text, findings = False, None, []

    monkeypatch.setattr(privacy, "evaluate", lambda *a, **k: _Denied())
    with pytest.raises(DecisionUnavailable) as info:
        prepare_state("x", redact=True)
    assert info.value.reason == "egress-denied:denied"


def test_egress_audit_stays_in_fake_home(home):
    prepare_state("olá", redact=True)
    audit = home / ".arkaos" / "egress" / "audit.jsonl"
    assert json.loads(audit.read_text(encoding="utf-8").splitlines()[-1])["destination"] == (
        "decisions:jev"
    )


@pytest.mark.parametrize("state_class", ["diff", "transcript"])
def test_redaction_disabled_never_applies_to_diff_or_transcript(home, state_class):
    # Kills: honouring redact=False for every class (QG r1 m1).
    out = prepare_state("patch for AcmeCorp", redact=False, state_class=state_class)
    assert isinstance(out, str) and "acmecorp" not in out.lower()
