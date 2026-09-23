"""prepare_state for the ``command`` class — secrets refused, home and clients cleaned.

The command site (PR2) ships ``{"command": <text up to 4000 chars>}``.
A shell command carries credentials with no vendor prefix; these tests
prove none of them leaves, on every egress path. Client names are
synthetic; secret values are built at runtime.

The ``redact=False`` and missing-config paths refuse secrets through
``privacy._refuse_secrets``, which calls ``core.egress.credentials.
egress_secret_labels`` (security review PR2, R-P1); ``command_state``
caps between tokens, never inside one (R-C1). Both landed in the
``core/decisions`` lane and their strict-xfail markers went with them.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from _decisions_helpers import isolate_decisions

from core.decisions.client import DecisionUnavailable
from core.decisions.privacy import prepare_state

OPAQUE = "Zq9" + "k7" * 14
PASSWORD = "Hunter" + "2" + "Secret!"  # arka:sec-ok(hardcoded-password): synthetic fixture
CLIENTS = ["acmecorp", "betacorp"]
QUOTED_TOKEN = f'export API_TOKEN="{OPAQUE}"'
QUOTED_PG = f'PGPASSWORD="{OPAQUE}" psql'  # arka:sec-ok(hardcoded-password): synthetic fixture

SECRET_COMMANDS = [
    f"export API_TOKEN={OPAQUE} && ./deploy.sh",
    f"curl -H 'Authorization: Bearer {OPAQUE}' https://api.example.org/v1",
    f"mysql -u root -p{PASSWORD} app < dump.sql",
    f"git clone https://bob:{OPAQUE}@git.example.org/app.git",
    f"PGPASSWORD={OPAQUE} psql -h db app",
    # QG PR2 r1 B1: double quotes become \" under json.dumps, and a scan of
    # the serialised text alone captured only the backslash.
    QUOTED_TOKEN,
    QUOTED_PG,
    f'curl -s -u "bob:{PASSWORD}" https://api.example.org/v1',
    f'tool --password "{PASSWORD}"',
    # QG PR2 r2 B3, the reported shapes: a value glued to ; ) or ,.
    f"export API_TOKEN={OPAQUE}; ./deploy",
    f"export TOKEN={OPAQUE}; ./d",
    f"mysql -uroot -p{PASSWORD};",
    f"(export API_TOKEN={OPAQUE})",
    f"PGPASSWORD={OPAQUE},psql",
    f"curl https://api.example.org/?token={OPAQUE};",
    f"sshpass -p {PASSWORD};ssh h",
    f"docker login -p {PASSWORD};",
    f"echo Authorization: Bearer {OPAQUE};",
    f"export API_TOKEN={OPAQUE};$SHELL",
    # QG PR2 r2 M1: httpie basic auth.
    f"http --auth bob:{PASSWORD} GET https://api.example.org",
    f"http -a bob:{PASSWORD} GET https://api.example.org",
    # QG PR2 r4 N1: an apostrophe in the prose before a single-quoted value.
    f"I can't log in with curl -u 'admin:Pa$${PASSWORD}' https://api.example.org",
    # r4: nested quoting escapes the quotes; every escape layer is scanned.
    f'ssh host "export API_TOKEN=\\"{OPAQUE}\\" && ./run"',
]

@pytest.fixture
def home(monkeypatch, tmp_path) -> Path:
    return isolate_decisions(monkeypatch, tmp_path, clients=CLIENTS)


def _cmd(text: str) -> dict[str, str]:
    return {"command": text}


def _audit_text(home: Path) -> str:
    path = home / ".arkaos" / "egress" / "audit.jsonl"
    return path.read_text(encoding="utf-8") if path.exists() else ""


@pytest.mark.parametrize("text", SECRET_COMMANDS)
def test_redacted_path_refuses_command_secrets(home, text):
    # Kills: policy reverting to secret_labels (every row leaves in clear).
    with pytest.raises(DecisionUnavailable, match="egress-denied:secret"):
        prepare_state(_cmd(text), redact=True, state_class="command")
    assert OPAQUE not in _audit_text(home) and PASSWORD not in _audit_text(home)


@pytest.mark.parametrize("text", SECRET_COMMANDS)
def test_redaction_disabled_refuses_command_secrets(home, text):
    with pytest.raises(DecisionUnavailable, match="egress-denied:secret"):
        prepare_state(_cmd(text), redact=False, state_class="command")


@pytest.mark.parametrize("text", SECRET_COMMANDS)
def test_missing_config_refuses_command_secrets(home, text):
    (home / ".arkaos" / "redaction-clients.json").unlink()
    with pytest.raises(DecisionUnavailable, match="egress-denied:secret"):
        prepare_state(_cmd(text), redact=True, state_class="command", session_id="s")


def test_secret_at_the_end_of_a_long_command_is_still_refused(home):
    # The cap runs after the checks: a 4000-char command whose secret
    # sits at the tail must not be cut into a harmless-looking prefix.
    text = "echo " + "a" * 3900 + f" && export API_TOKEN={OPAQUE}"
    assert len(text) <= 4000
    with pytest.raises(DecisionUnavailable, match="egress-denied:secret"):
        prepare_state(_cmd(text), redact=True, state_class="command")


def test_home_paths_in_a_command_are_normalised(home):
    text = f"cd {home}/Work/app && cat ~/notes.md && ls {str(home).upper()}/tmp"
    out = prepare_state(_cmd(text), redact=True, state_class="command")
    assert out == {"command": "cd <home>/Work/app && cat <home>/notes.md && ls <home>/tmp"}


def test_client_names_in_a_command_are_redacted(home):
    text = f"cd {home}/Work/acmecorp-api && scp build.tgz deploy@BetaCorp.example.org:/srv"
    out = prepare_state(_cmd(text), redact=True, state_class="command")
    flat = json.dumps(out).lower()
    assert "acmecorp" not in flat and "betacorp" not in flat
    assert "<home>/work/" in flat


def test_compound_client_token_never_leaves_in_clear(home):
    # The sanitizer matches on word boundaries; the residual check is a
    # substring match, so a compound token is denied rather than shipped.
    try:
        out = prepare_state(_cmd("git checkout release/acmecorp2026"), redact=True,
                            state_class="command")
    except DecisionUnavailable as exc:
        assert "egress-denied" in str(exc)
    else:
        assert "acmecorp" not in json.dumps(out).lower()


def test_plain_command_leaves_unchanged(home):
    out = prepare_state(_cmd("git status && make test"), redact=True, state_class="command")
    assert out == {"command": "git status && make test"}


def _straddling(tail: str) -> str:
    from core.decisions.sites.command import MAX_COMMAND_CHARS

    # "echo " + filler + " " puts the first 3 chars of ``tail`` before the cut.
    return "echo " + "a" * (MAX_COMMAND_CHARS - 9) + " " + tail


def test_command_cap_never_ships_a_split_client_name(home):
    # PR1 M2 again, one layer up: the cut leaves "acm", which no longer
    # matches the redaction list, and the fragment ships in clear.
    from core.decisions.sites.command import command_state

    out = prepare_state(command_state(_straddling("acmecorp")), redact=True,
                        state_class="command")
    assert "acm" not in out["command"]


def test_command_cap_never_ships_a_secret_prefix(home):
    from core.decisions.sites.command import command_state

    slack = "xoxb-" + "1234567890" + "-abcdefghijklmnop"
    try:
        out = prepare_state(command_state(_straddling(slack)), redact=True,
                            state_class="command")
    except DecisionUnavailable:
        return
    assert "xox" not in out["command"]


def test_raw_leaves_are_scanned_before_serialisation(home, monkeypatch):
    # Kills: scanning only the serialised text again (B1). The refusal
    # must come from the raw strings, before json.dumps ever runs.
    from core.decisions import privacy

    def serialised_first(_state):
        raise AssertionError("serialised before the raw scan")

    monkeypatch.setattr(privacy, "_serialise", serialised_first)
    with pytest.raises(DecisionUnavailable, match="egress-denied:secret"):
        prepare_state(_cmd(QUOTED_TOKEN), redact=True, state_class="command")


@pytest.mark.parametrize("state", [
    {"recent": [{"command": QUOTED_TOKEN}]},
    [["git status"], {"nested": {"deeper": QUOTED_PG}}],
    {QUOTED_TOKEN: "key holds it"},
])
def test_nested_leaves_and_keys_are_scanned(home, state):
    with pytest.raises(DecisionUnavailable, match="egress-denied:secret"):
        prepare_state(state, redact=False, state_class="command")


def test_deep_state_does_not_blow_the_stack(home):
    state: object = QUOTED_TOKEN
    for _ in range(5000):
        state = [state]
    with pytest.raises(DecisionUnavailable):
        prepare_state(state, redact=True, state_class="command")
