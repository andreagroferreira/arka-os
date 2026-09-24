"""Egress review of the JEV PR3 ``diff``-class consumers (security review, PR3).

Each property is proven on the CAPTURED request body (``urlopen`` mocked),
never by reading the code: fail-closed without the redaction list, client
names and home paths redacted in the diff AND in the chunk header, secrets
in added lines refused before the POST, the Stop state limited to its three
fields, ``ui_state`` secrets refused (a ``diff``-class state since QG r1
M3), and every refusal on the egress audit trail. Findings 33-43 of
``docs/security/2026-09-23-jev-decisions-review.md`` (section "PR3 — diff
class consumers"); each finding's rows say which mutation they kill.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from _decisions_helpers import (
    fake_ok,
    isolate_decisions,
    read_jsonl,
    sent_payload,
    write_config,
)

from core.decisions import privacy
from core.decisions.client import DecisionUnavailable
from core.decisions.privacy import prepare_state
from core.decisions.sites import quality
from core.decisions.sites.governance import ui_state
from core.governance import evidence_checks, slop_check
from core.governance import qg_prescreen as qp

URLOPEN = "core.decisions.client.urllib.request.urlopen"
SOURCE_PATH = "core/app.py"  # an allowlisted suffix: the detectors are what these rows test
CLIENT = "zorblax"  # fictional; never a real client name
# Built at runtime so the literals never sit in the repo as secrets.
TOKEN_VALUE = "q8Zr" + "Vt3LmW9xK2pB7nJ4"
DOLLAR_VALUE = "Tr0ub4dor" + "$" + "3xYz"  # a literal password holding ``$``
SECRET_LINES: dict[str, str] = {
    "assignment": f"API_TOKEN={TOKEN_VALUE}",
    "quoted-assignment": f'API_TOKEN="{TOKEN_VALUE}"',
    "curl-userinfo": f"curl -u deploy:{TOKEN_VALUE} https://example.invalid/x",
    "bearer-header": f"Authorization: Bearer {TOKEN_VALUE}",
}


def diff_state(diff: str, path: str = SOURCE_PATH) -> dict[str, Any]:
    """The prescreen state of a source file (QG PR3 r7: a diff state names its file)."""
    return quality.diff_state(diff, path)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@example.invalid", "-c", "user.name=t", *args],
        cwd=repo, check=True, capture_output=True,
    )


@pytest.fixture
def jev(monkeypatch, tmp_path):
    home = isolate_decisions(monkeypatch, tmp_path, clients=[CLIENT])
    # qg-prescreen is shadow by default (PR3 replay gate): act, so the body
    # these tests capture is the one a live read would send.
    write_config(home, {"sites": {"qg-prescreen": "act"}})
    return home


def _repo(tmp_path: Path, files: dict[str, str]) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "base.txt").write_text("base\n", encoding="utf-8")
    _git(root, "init", "-q", "-b", "master")
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "base")
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text, encoding="utf-8")
    return root


def _approved() -> object:
    return fake_ok({
        "qg_prescreen__likely_verdict": {"type": "choice", "choice": "approved",
                                         "confidence": 0.9},
        "qg_prescreen__blocker_class": {"type": "choice", "choice": "none", "confidence": 0.9},
    })


def _audit(home: Path) -> list[dict[str, Any]]:
    return read_jsonl(home / ".arkaos" / "egress" / "audit.jsonl")


def _bodies(net: Any) -> list[str]:
    return [json.dumps(sent_payload(net, i)) for i in range(net.call_count)]


# --- 1. fail-closed without the list ------------------------------------------

def test_prescreen_cli_without_the_list_prints_the_skip_and_sends_nothing(
    jev, tmp_path, capsys
):
    (jev / ".arkaos" / "redaction-clients.json").unlink()
    repo = _repo(tmp_path, {"app.py": "X = 1\n"})
    with patch(URLOPEN) as net:
        assert qp.main([str(repo), "--changed-files", "app.py"]) == 0
    assert capsys.readouterr().out.splitlines()[0] == (
        "[arka:qg-prescreen] skipped reason=redaction-config-missing")
    net.assert_not_called()


def test_slop_section_without_the_list_skips_and_sends_nothing(jev, tmp_path):
    (jev / ".arkaos" / "redaction-clients.json").unlink()
    repo = _repo(tmp_path, {"NOTES.md": "Plain prose.\n"})
    with patch(URLOPEN) as net:
        result = slop_check.check_slop_score(repo, ["NOTES.md"], None, 30)
    assert "skipped reason=redaction-config-missing" in result.summary
    net.assert_not_called()


@pytest.mark.parametrize("state_class", ["diff", "transcript"])
def test_privacy_refuses_diff_and_transcript_without_the_list_and_audits_it(
    jev, state_class
):
    (jev / ".arkaos" / "redaction-clients.json").unlink()
    with pytest.raises(DecisionUnavailable) as info:
        prepare_state(diff_state("+x = 1\n"), redact=True, state_class=state_class)
    assert info.value.reason == "egress-denied:redaction-config-missing"
    last = _audit(jev)[-1]
    assert last["allowed"] is False
    assert [f["kind"] for f in last["findings"]] == ["redaction-config-missing"]


# --- 1. with the list: clients, secrets, home ------------------------------

def test_client_names_in_a_diff_are_redacted_in_the_body_and_the_header(jev, tmp_path):
    name = f"billing/{CLIENT}_invoices.py"
    repo = _repo(tmp_path, {name: f"CUSTOMER = '{CLIENT.title()} Ltd'\n"})
    with patch(URLOPEN, return_value=_approved()) as net:
        report = qp.run_prescreen(repo, [name], "s-redact")
    assert report["skipped"] is None and net.call_count == 1
    body = _bodies(net)[0]
    assert CLIENT not in body.lower()
    header = sent_payload(net)["state"]["diff"].splitlines()[0]
    assert header.startswith("# file: billing/") and CLIENT not in header.lower()


def test_home_paths_in_a_diff_and_a_header_are_normalised(jev, tmp_path):
    home = str(jev)
    chunk = qp.chunk_diff(f"{home}/proj/app.py", f"+CONFIG = '{home}/proj/.env'\n")[0]
    with patch(URLOPEN, return_value=_approved()) as net:
        prediction = qp.ask_chunk(chunk, "s-home", qp.jev_advisory.Deadline(5000),
                     path=SOURCE_PATH)
    assert prediction.jev is True
    diff = sent_payload(net)["state"]["diff"]
    assert home not in diff
    assert diff.splitlines()[0] == "# file: <home>/proj/app.py part 1/1"
    assert "'<home>/proj/.env'" in diff


def test_tilde_paths_in_a_diff_are_normalised(jev):
    with patch(URLOPEN, return_value=_approved()) as net:
        qp.ask_chunk("+p = '~/work/app'\n", "s-tilde", qp.jev_advisory.Deadline(5000),
                     path=SOURCE_PATH)
    assert "'<home>/work/app'" in sent_payload(net)["state"]["diff"]


@pytest.mark.parametrize("shape", sorted(SECRET_LINES))
def test_secrets_in_added_lines_never_reach_the_wire(jev, tmp_path, shape):
    repo = _repo(tmp_path, {"deploy.sh": f"#!/bin/sh\n{SECRET_LINES[shape]}\n"})
    with patch(URLOPEN, return_value=_approved()) as net:
        report = qp.run_prescreen(repo, ["deploy.sh"], "s-secret")
    net.assert_not_called()
    assert report["skipped"] == "unavailable:egress-denied:secret"


@pytest.mark.parametrize("shape", sorted(SECRET_LINES))
def test_secrets_in_changed_prose_never_reach_the_wire(jev, tmp_path, shape):
    repo = _repo(tmp_path, {"RUNBOOK.md": f"Run this:\n\n    {SECRET_LINES[shape]}\n"})
    with patch(URLOPEN) as net:
        result = slop_check.check_slop_score(repo, ["RUNBOOK.md"], None, 30)
    net.assert_not_called()
    assert "egress-denied:secret" in result.summary


@pytest.mark.parametrize("shape", sorted(SECRET_LINES))
def test_the_serialised_text_layer_refuses_on_its_own(jev, monkeypatch, shape):
    # Kills: the leaf scan removed — the second layer still refuses.
    monkeypatch.setattr("core.decisions.privacy._refuse_leaf_secrets", lambda _s: None)
    with pytest.raises(DecisionUnavailable) as info:
        prepare_state(diff_state(f"+{SECRET_LINES[shape]}\n"), redact=True,
                      state_class="diff")
    assert info.value.reason == "egress-denied:secret"


# --- 3. ui_state, a diff-class state (QG r1 M3) ---------------------------------

def _ui_write(fg: Any, path: str, content: str) -> Any:
    return fg.evaluate("Write", "/nonexistent", "s-ui", "/tmp",
                       {"file_path": path, "content": content}, messages=[])


@pytest.fixture
def gate(jev, monkeypatch, tmp_path):
    from core.workflow import frontend_gate as fg

    cfg = tmp_path / "gate-config.json"
    cfg.write_text(json.dumps({"hooks": {"frontendGate": "warn"}}), encoding="utf-8")
    monkeypatch.setattr(fg, "CONFIG_PATH", cfg)
    monkeypatch.setattr(fg, "TELEMETRY_PATH", tmp_path / "frontend-gate.jsonl")
    monkeypatch.setattr(fg, "shadow_deny_on", lambda: False)
    monkeypatch.setenv("ARKA_DESIGN_AUTH_DIR", str(tmp_path / "design-auth"))
    monkeypatch.delenv("ARKA_BYPASS_DESIGN", raising=False)
    return fg


@pytest.mark.parametrize("with_list", [True, False])
def test_a_ts_file_embedding_a_secret_is_refused_before_the_post(
    gate, jev, tmp_path, with_list
):
    if not with_list:  # diff class: refused without the list; the leaf secret scan answers first
        (jev / ".arkaos" / "redaction-clients.json").unlink()
    content = f'export const client = {{\n  apiToken: "{TOKEN_VALUE}",\n}};\n'
    content = content.replace("apiToken", "API_TOKEN")
    with patch(URLOPEN) as net:
        decision = _ui_write(gate, "src/api/client.ts", content)
    net.assert_not_called()
    assert decision.allow is True
    rows = read_jsonl(tmp_path / "decisions.jsonl")
    assert rows and rows[-1]["reason"] == "egress-denied:secret"


def test_ui_state_carries_only_path_and_capped_content():
    state = ui_state("src/x.ts", "a " * 5000)
    assert set(state) == {"path", "content"} and len(state["content"]) <= 6000


# --- 5. every refusal is on the audit trail -------------------------------

@pytest.mark.parametrize("shape", sorted(SECRET_LINES))
def test_a_leaf_secret_refusal_is_audited_without_the_value(jev, shape):
    # Finding 37. Kills: _audit_refusal removed from _refuse_leaf_secrets.
    before = len(_audit(jev))
    with pytest.raises(DecisionUnavailable):
        prepare_state(diff_state(f"+{SECRET_LINES[shape]}\n"), redact=True,
                      state_class="diff", session_id="s-audit")
    rows = _audit(jev)
    assert len(rows) == before + 1
    last = rows[-1]
    assert last["allowed"] is False and last["destination"] == "decisions:jev"
    assert last["layer"] == "privacy" and last["payload_sha256"] == ""
    assert {f["kind"] for f in last["findings"]} == {"secret"}
    raw = (jev / ".arkaos" / "egress" / "audit.jsonl").read_text(encoding="utf-8")
    assert TOKEN_VALUE not in raw and "deploy" not in raw


def test_a_client_residual_refusal_is_audited(jev):
    # A compound token the sanitizer's word boundary keeps: the residual
    # layer denies, and evaluate audits the denial.
    with pytest.raises(DecisionUnavailable) as info:
        prepare_state(diff_state(f"+x = '{CLIENT}2026'\n"), redact=True, state_class="diff")
    assert info.value.reason == "egress-denied:client-identifier"
    last = _audit(jev)[-1]
    assert last["allowed"] is False
    assert CLIENT not in json.dumps(last)


def test_a_text_layer_refusal_on_the_degraded_path_is_audited(jev):
    # Finding 37. Kills: _audit_refusal removed from _refuse_secrets. The leaf
    # scan is disabled so the serialised-text layer is the one refusing.
    (jev / ".arkaos" / "redaction-clients.json").unlink()
    with patch("core.decisions.privacy._refuse_leaf_secrets", lambda _s: None), \
            pytest.raises(DecisionUnavailable):
        prepare_state({"command": SECRET_LINES["assignment"]}, redact=True,
                      state_class="command", session_id="s-degraded")
    last = _audit(jev)[-1]
    assert last["allowed"] is False and last["layer"] == "privacy"
    assert len(last["payload_sha256"]) == 64
    assert TOKEN_VALUE not in json.dumps(last)


# --- finding 33: source-code credential shapes ------------------------------

CODE_LEAKS: dict[str, str] = {
    "ts-object": f'  API_TOKEN: "{TOKEN_VALUE}",',
    "ts-camel": f"  apiKey: '{TOKEN_VALUE}',",
    "ts-template": f"  clientSecret: `{TOKEN_VALUE}`,",
    "json": f'{{"api_key": "{TOKEN_VALUE}"}}',
    "json-hyphen": f'{{"x-api-key": "{TOKEN_VALUE}"}}',
    "yaml-bare": f"db_password: {TOKEN_VALUE}",
    "php": f"'api_key' => '{TOKEN_VALUE}',",
    "py-typed": f'API_KEY: str = "{TOKEN_VALUE}"',
    "ts-typed": f'const apiKey: string = "{TOKEN_VALUE}";',
    "headers-quoted": f"headers: {{ 'Authorization': 'Bearer {TOKEN_VALUE}' }}",
    "headers-json": f'{{"Authorization": "Bearer {TOKEN_VALUE}"}}',
    "headers-template": f"headers: {{ Authorization: `Bearer {TOKEN_VALUE}` }}",
    "docker-auth": f'{{"auths": {{"r.example.invalid": {{"auth": "{TOKEN_VALUE}"}}}}}}',
    # Finding 38: a ``$`` inside a source-code string is data, not a reference.
    "json-dollar": f'{{"password": "{DOLLAR_VALUE}"}}',
    "yaml-dollar": f'password: "{DOLLAR_VALUE}"',
    "js-dollar": f"  password: '{DOLLAR_VALUE}',",
    "py-dollar": f'password = "{DOLLAR_VALUE}"',  # arka:sec-ok(hardcoded-password): fixture
    # Finding 39: the auth header as a call argument.
    "js-headers-set": f'headers.set("Authorization", "Bearer {TOKEN_VALUE}");',
    "go-header-set": f'req.Header.Set("Authorization", "Bearer {TOKEN_VALUE}")',
    "java-request-property": f'c.setRequestProperty("Authorization", "Bearer {TOKEN_VALUE}");',
    "bearer-only": f'headers[AUTH] = "Bearer {TOKEN_VALUE}";',
}
CODE_BENIGN: list[str] = [
    "  apiKey: string;", "  password: process.env.DB_PASSWORD,", "  token: this.token,",
    "password: ${DB_PASSWORD}", 'api_key: "<your-api-key>"', "primary_key: id",
    'sortKey: "created_at"', 'passwordLabel: "Password"', "token: getToken(user),",
    "max_tokens: 128000", "max_context_tokens: int = 200_000", "keyword: [keyword]",
    '"api_key": "{api_key}"', "accessorKey: 'calls_30d'", "d3-sankey: 0.12.3",
    'passwordHint: "Use at least 12 characters"', "tokenUrl: 'https://a.example.invalid/t'",
    '"master_key": "os.environ/ARKA_GATEWAY_KEY"', "Regression tests pass: `test_x_2`",
    '"password": "${DB_PASSWORD}"', "'password' => $this->password,",
    'headers.set("Authorization", "Bearer " + token);', "h.Set(\"Authorization\", auth)",
]


@pytest.mark.parametrize("shape", sorted(CODE_LEAKS))
def test_source_code_credentials_never_reach_the_wire(jev, tmp_path, shape):
    # Kills: the key/value detector, the annotation group or the quoted
    # auth-header key removed (each shape loses its only label).
    repo = _repo(tmp_path, {"src/config.ts": f"export const c = {{\n{CODE_LEAKS[shape]}\n}};\n"})
    with patch(URLOPEN, return_value=_approved()) as net:
        report = qp.run_prescreen(repo, ["src/config.ts"], "s-code")
    net.assert_not_called()
    assert report["skipped"] == "unavailable:egress-denied:secret"


@pytest.mark.parametrize("line", CODE_BENIGN)
def test_ordinary_code_still_reaches_the_wire(jev, line):
    # Kills: the word-based key test, the member/number/env-name/placeholder
    # guards or the whitespace rule dropped (a benign row is refused).
    with patch(URLOPEN, return_value=_approved()) as net:
        prediction = qp.ask_chunk(f"+{line}\n", "s-benign", qp.jev_advisory.Deadline(5000),
                     path=SOURCE_PATH)
    assert prediction.jev is True and net.call_count == 1



# --- finding 41 (QG r2 B1): the diff state, not only the labels -------------

PLAIN_VALUE = "Tr0ub4dor" + "X3xYz"
STRING_FORM_LEAKS: dict[str, str] = {
    "kwarg-dollar": ("conn = psycopg2.connect(host=h, "
                     f'password="{DOLLAR_VALUE}")'),  # arka:sec-ok(hardcoded-password): fixture
    "kwarg-second": ('db.connect(user="u", '
                     f'password="{DOLLAR_VALUE}")'),  # arka:sec-ok(hardcoded-password): fixture
    "kwarg-api-key": f'client = Client(api_key="{DOLLAR_VALUE}")',
    "bytes": f'SECRET_KEY = b"{PLAIN_VALUE}9"',
    "raw-dollar": f'password = r"{DOLLAR_VALUE}"',
    "f-string": f'token = f"{TOKEN_VALUE}"',
    "go-walrus": f'password := "{PLAIN_VALUE}"',
    "go-var-typed": f'var password string = "{DOLLAR_VALUE}"',
    "dict-bytes": f'{{"password": b"{PLAIN_VALUE}"}}',
    "control": f'SECRET_KEY = "{PLAIN_VALUE}9"',
}
STRING_FORM_SENT: list[str] = [
    'POSTGRES_PASSWORD: "${POSTGRES_PASSWORD:-}"', '"password": "${X:?required}"',
    '"secret": "%(SECRET)s"', 'doc: "Bearer token_here_placeholder"',
    'token = f"{prefix}{suffix}"', 'connect(password=f"{pw}")',
]


@pytest.mark.parametrize("shape", sorted(STRING_FORM_LEAKS))
def test_string_forms_in_a_diff_are_refused_by_prepare_state(jev, shape):
    # Kills: any of the finding-41 readings removed; the refusal is captured
    # at the state the prescreen would send (QG r2 B1).
    with pytest.raises(DecisionUnavailable) as info:
        prepare_state(diff_state(f"+{STRING_FORM_LEAKS[shape]}\n"), redact=True,
                      state_class="diff")
    assert info.value.reason == "egress-denied:secret"


@pytest.mark.parametrize("line", STRING_FORM_SENT)
def test_string_form_references_in_a_diff_are_sent(jev, line):
    state = diff_state(f"+{line}\n")
    assert prepare_state(state, redact=True, state_class="diff") == state


# --- finding 42 (QG r3 B2): a secret named inside a quoted string -----------

WP_SALT = "x7#Qm!2@vL9p" + "$Kz&4Rt^8Yw*0Nb(3Hc)6Jd_1Fg+5Se="
QUOTED_NAME_LEAKS: dict[str, str] = {
    "wp-salt": f"define('AUTH_KEY',         '{WP_SALT}');",
    "wp-db-password": f"define( 'DB_PASSWORD', '{DOLLAR_VALUE}' );",
    "environ-subscript": f'os.environ["API_TOKEN"] = "{TOKEN_VALUE}"',
    "flask-config": f'app.config["SECRET_KEY"] = "{TOKEN_VALUE}"',
    "php-config": f"$config['encryption_key'] = '{TOKEN_VALUE}';",
    "setdefault": f'os.environ.setdefault("DB_PASSWORD", "{PLAIN_VALUE}")',
    "getenv-default": f'PASSWORD = os.getenv("PW", "{DOLLAR_VALUE}")',
    "setter": f'ds.setPassword("{PLAIN_VALUE}");',
    "auth-tuple": f'requests.get(url, auth=("admin", "{PLAIN_VALUE}"))',
    "dotnet-appsettings": f'<add key="ApiKey" value="{TOKEN_VALUE}" />',
    "kotlin-val": f'val password = "{DOLLAR_VALUE}"',  # arka:sec-ok(hardcoded-password): fixture
    "swift-let-typed": f'let password: String = "{DOLLAR_VALUE}"',
    "control": f'SECRET_KEY = "{TOKEN_VALUE}"',
    # QG r4 B1: a dot in a quoted name (Laravel config, Java properties, JSON).
    "laravel-config-set": f'Config::set("services.stripe.secret", "{TOKEN_VALUE}");',
    "laravel-helper-set": f"config()->set('services.stripe.secret', '{TOKEN_VALUE}');",
    "laravel-config-array": f"'stripe.secret' => '{TOKEN_VALUE}',",
    "json-dotted-key": f'"db.password": "{PLAIN_VALUE}"',
    "java-system-property": ('System.setProperty("javax.net.ssl.trustStorePassword", '
                             f'"{PLAIN_VALUE}")'),
    "spark-conf": f'conf.set("spark.hadoop.fs.s3a.secret.key", "{TOKEN_VALUE}")',
    # QG r4 M1: Ruby.
    "ruby-or-assign": f'ENV["API_TOKEN"] ||= "{TOKEN_VALUE}"',
    "ruby-symbol": f'config[:api_key] = "{TOKEN_VALUE}"',
    "ruby-fetch-block": f'ENV.fetch("API_TOKEN") {{ "{TOKEN_VALUE}" }}',
}
QUOTED_NAME_SENT: list[str] = [
    '"db.password.file": "/etc/x/pw"', '"spring.datasource.password": "${DB_PASSWORD}"',
    '"api.key.id": "k1a2b3c4d5"', "'services.stripe.key' => env('STRIPE_KEY'),",
    "'app.name' => 'Laravel',", 'ENV.fetch("API_TOKEN") { nil }',
    'home = os.environ["HOME"]', 'config["timeout"] = "30s"', "define('WP_DEBUG', 'false')",
    'os.environ["GIT_COMMIT"] = "a1b2c3d4e5f6"',
    'tok = os.environ.get("API_TOKEN")', "ds.setPassword(password)",
    "requests.get(url, auth=(user, pw))",
]


def _refused(state: dict[str, Any]) -> str:
    with pytest.raises(DecisionUnavailable) as info:
        prepare_state(state, redact=True, state_class="diff")
    return info.value.reason


@pytest.mark.parametrize("shape", sorted(QUOTED_NAME_LEAKS))
def test_a_secret_named_in_quotes_is_refused_by_prepare_state(jev, shape):
    # Kills: the quoted-name, setter or pair detector removed (finding 42).
    assert _refused(diff_state(f"+{QUOTED_NAME_LEAKS[shape]}\n")) == "egress-denied:secret"


@pytest.mark.parametrize("shape", sorted(QUOTED_NAME_LEAKS))
def test_a_secret_named_in_quotes_is_refused_on_the_serialised_layer(jev, monkeypatch, shape):
    # The leaf scan patched out: the serialised text layer refuses on its own.
    monkeypatch.setattr("core.decisions.privacy._refuse_leaf_secrets", lambda _s: None)
    assert _refused(diff_state(f"+{QUOTED_NAME_LEAKS[shape]}\n")) == "egress-denied:secret"


@pytest.mark.parametrize("line", QUOTED_NAME_SENT)
def test_a_quoted_name_without_a_literal_secret_is_sent(jev, line):
    state = diff_state(f"+{line}\n")
    assert prepare_state(state, redact=True, state_class="diff") == state


# --- QG r4: the catch-all layer, at the state the prescreen sends ----------

CATCH_ALL_LEAKS: dict[str, str] = {
    "reset-password": f'user.resetPassword("{PLAIN_VALUE}")',
    "runtime-name": f'env[f"{{prefix}}_TOKEN"] = "{TOKEN_VALUE}"',
    "triple-quoted": f'password = """{PLAIN_VALUE}"""',
    "keyring": f'keyring.set_password("svc", "bob", "{PLAIN_VALUE}")',
    "java-pw": f'String pw = "{PLAIN_VALUE}";',
    "priv-key-call": f'let privKey = decode("{TOKEN_VALUE}");',  # Marta r5: ``priv``
    "dockerfile-env": f"ENV API_TOKEN {TOKEN_VALUE}",  # finding 47: an unquoted literal
}
CATCH_ALL_SENT: list[str] = [
    'logger.info("token rotated", extra={"build": "a1b2c3d4"})',
    '_SECRET_NAME = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL)", re.I)',
    '"Read(.aws/credentials)",', '-H "Authorization: Bearer $API_KEY" \\',
    # QG r5 m1: a hash manifest, the file's words set aside with its path.
    "'/app/Http/Auth/LoginController.php' => 'cc77e6827498680eabf56e7d4c7dab22',",
    'let pubKey = decode("q8Zr2mXv7Lk");',
]


@pytest.mark.parametrize("shape", sorted(CATCH_ALL_LEAKS))
def test_the_catch_all_refuses_a_shape_no_detector_knows_by_prepare_state(jev, shape):
    # Kills: the catch-all layer off (no precise detector labels these).
    assert _refused(diff_state(f"+{CATCH_ALL_LEAKS[shape]}\n")) == "egress-denied:secret"


@pytest.mark.parametrize("shape", sorted(CATCH_ALL_LEAKS))
def test_the_catch_all_refuses_on_the_serialised_layer(jev, monkeypatch, shape):
    # The leaf scan patched out: the catch-all reads the JSON text by its leaves.
    monkeypatch.setattr("core.decisions.privacy._refuse_leaf_secrets", lambda _s: None)
    assert _refused(diff_state(f"+{CATCH_ALL_LEAKS[shape]}\n")) == "egress-denied:secret"


@pytest.mark.parametrize("line", CATCH_ALL_SENT)
def test_the_catch_all_sends_names_patterns_and_references(jev, line):
    state = diff_state(f"+{line}\n")
    assert prepare_state(state, redact=True, state_class="diff") == state


# --- QG r5 (finding 47): XML element text and .netrc, at the prescreen state -

XML_NETRC_LEAKS: dict[str, str] = {
    "xml-element": f"<password>{TOKEN_VALUE[:11]}</password>",
    "xml-case": f"<Password>{TOKEN_VALUE}</Password>",
    "xml-namespace": f"<db:password>{TOKEN_VALUE}</db:password>",
    "xml-secret": f"<secret>{TOKEN_VALUE}</secret>",
    "xml-api-key": f"<apiKey>{TOKEN_VALUE}</apiKey>",
    "xml-api-token": f"<ApiToken>{TOKEN_VALUE}</ApiToken>",
    "xml-property-name": f'<property name="hibernate.connection.password">{TOKEN_VALUE}</property>',
    "xml-entry-key": f'<entry key="db.password">{TOKEN_VALUE}</entry>',
    "xml-cdata": f"<password><![CDATA[{TOKEN_VALUE}]]></password>",
    "netrc-line": f"machine api.example.com login me password {TOKEN_VALUE}",
    "netrc-default": f"default login me password {TOKEN_VALUE}",
    "netrc-own-line": f"  password {TOKEN_VALUE}",
}
XML_NETRC_SENT: list[str] = [
    "<password></password>", "<password>${DB_PASSWORD}</password>",
    "<password>@db.password@</password>", "<passwordPolicy>strict</passwordPolicy>",
    '<entry key="timeout">30</entry>', "<name>password</name>",
    "machine api.example.com login me password $NETRC_PASSWORD",
]


@pytest.mark.parametrize("shape", sorted(XML_NETRC_LEAKS))
def test_xml_and_netrc_credentials_are_refused_by_prepare_state(jev, shape):
    # Kills: the element detector, its attribute key, CDATA, the netrc rule.
    assert _refused(diff_state(f"+{XML_NETRC_LEAKS[shape]}\n")) == "egress-denied:secret"


@pytest.mark.parametrize("shape", sorted(XML_NETRC_LEAKS))
def test_xml_and_netrc_credentials_are_refused_on_the_serialised_layer(jev, monkeypatch, shape):
    monkeypatch.setattr("core.decisions.privacy._refuse_leaf_secrets", lambda _s: None)
    assert _refused(diff_state(f"+{XML_NETRC_LEAKS[shape]}\n")) == "egress-denied:secret"


@pytest.mark.parametrize("line", XML_NETRC_SENT)
def test_xml_and_netrc_references_are_sent(jev, line):
    state = diff_state(f"+{line}\n")
    assert prepare_state(state, redact=True, state_class="diff") == state


@pytest.mark.parametrize("shape", sorted({**CODE_LEAKS, **STRING_FORM_LEAKS, **XML_NETRC_LEAKS}))
def test_with_no_precise_detector_the_catch_all_still_refuses_the_code_forms(
        jev, monkeypatch, shape):
    # Every precise detector off: the catch-all alone holds findings 33-41
    # and 47 at the state the prescreen sends; the bare YAML value and the
    # XML and netrc shapes through its unquoted reading (QG r5).
    monkeypatch.setattr("core.egress.credentials._DETECTORS", ())
    line = {**CODE_LEAKS, **STRING_FORM_LEAKS, **XML_NETRC_LEAKS}[shape]
    assert _refused(diff_state(f"+{line}\n")) == "egress-denied:secret"


def test_the_catch_all_alone_misses_a_pretty_printed_element_value(jev, monkeypatch):
    # Residual (g) of finding 46, pinned: the value on a line of its own has
    # no secret word on that line; the element detector refuses it.
    line = f"<password>\n+    {TOKEN_VALUE}\n+  </password>"
    assert _refused(diff_state(f"+{line}\n")) == "egress-denied:secret"
    monkeypatch.setattr("core.egress.credentials._DETECTORS", ())
    state = diff_state(f"+{line}\n")
    assert prepare_state(state, redact=True, state_class="diff") == state


def test_a_ts_payload_with_a_camel_case_key_is_refused_by_the_ui_site(gate, tmp_path):
    content = f"export const api = {{ apiKey: '{TOKEN_VALUE}' }};\n"
    with patch(URLOPEN) as net:
        _ui_write(gate, "src/api.ts", content)
    net.assert_not_called()
    assert read_jsonl(tmp_path / "decisions.jsonl")[-1]["reason"] == "egress-denied:secret"


# --- finding 34: a PEM body cut away from its BEGIN line --------------------

def _pem_diff() -> str:
    limit = qp.MAX_DIFF_CHARS - qp._HEADER_RESERVE
    filler = "".join(f"+f{i:05d}\n" for i in range(limit // 8 - 20))
    body = "".join("+MIIEowIBAAKCAQEA" + "A" * 48 + "\n" for _ in range(25))
    return (filler + "+-----BEGIN RSA PRIVATE KEY-----\n" + body
            + "+-----END RSA PRIVATE KEY-----\n")


def test_a_private_key_split_across_chunks_never_reaches_the_wire(jev):
    # Kills: the END-line detector (_PEM_TAIL) removed — chunk 2 left.
    chunks = qp.chunk_diff("deploy/key.pem", _pem_diff())
    assert len(chunks) == 2 and "BEGIN" not in chunks[1] and "MIIEow" in chunks[1]
    with patch(URLOPEN, return_value=_approved()) as net:
        for chunk in chunks:
            qp.ask_chunk(chunk, "s-pem", qp.jev_advisory.Deadline(5000),
                     path=SOURCE_PATH)
    net.assert_not_called()


# --- finding 35: long lines and long names never split a token --------------

def _straddle(token: str, offset: int) -> str:
    """A minified line whose ``token`` starts ``offset`` chars before a cut."""
    room = qp.MAX_DIFF_CHARS - qp._HEADER_RESERVE
    lead = "+" + "x " * ((room - offset - 1) // 2)
    return lead + token + " " + "y " * 11_700 + "\n"


@pytest.mark.parametrize(("token", "needle"), [
    (f"API_TOKEN={TOKEN_VALUE}", TOKEN_VALUE[1:]), (CLIENT, CLIENT[3:])])
def test_a_token_straddling_the_chunk_cut_never_leaves_in_halves(jev, token, needle):
    # Kills: the old hard cut in _split_lines (tail of the token in part 2).
    line = _straddle(token, 11)
    with patch(URLOPEN, return_value=_approved()) as net:
        for chunk in qp.chunk_diff("dist/app.min.js", line):
            qp.ask_chunk(chunk, "s-long", qp.jev_advisory.Deadline(5000),
                     path=SOURCE_PATH)
    bodies = "".join(_bodies(net))
    assert needle not in bodies and "[long line cut]" in bodies


def test_a_long_file_name_never_cuts_a_chunk_after_the_fact(jev):
    # Kills: chunk[:limit] restored with the fixed 512-char reserve.
    name = "a/" * 400 + f"{CLIENT}.py"
    diff = "".join(f"+v{i} = '{CLIENT}'\n" for i in range(3000))
    chunks = qp.chunk_diff(name, diff)
    assert all(len(c) <= qp.MAX_DIFF_CHARS for c in chunks)
    assert all(c.endswith(f"= '{CLIENT}'\n") for c in chunks)


# --- finding 36: nothing outside the project is read ------------------------

@pytest.fixture
def outside(tmp_path) -> Path:
    netrc = tmp_path / "netrc.txt"
    netrc.write_text("machine h.example.invalid login bob password CANARY-OUT-77\n",
                     encoding="utf-8")
    return netrc


@pytest.mark.parametrize("how", ["dotdot", "absolute", "symlink"])
def test_the_prescreen_never_sends_a_file_outside_the_project(jev, tmp_path, outside, how):
    # Kills: readable_inside removed from _untracked_diff.
    repo = _repo(tmp_path, {})
    name = {"dotdot": "../netrc.txt", "absolute": str(outside), "symlink": "notes.txt"}[how]
    if how == "symlink":
        (repo / "notes.txt").symlink_to(outside)
    with patch(URLOPEN, return_value=_approved()) as net:
        qp.run_prescreen(repo, [name], "s-out")
    assert "CANARY-OUT" not in "".join(_bodies(net))


def test_an_untracked_symlink_git_lists_is_not_followed(jev, tmp_path, outside):
    repo = _repo(tmp_path, {})
    (repo / "notes.txt").symlink_to(outside)
    with patch(URLOPEN, return_value=_approved()) as net:
        qp.run_prescreen(repo, None, "s-derived")  # changed files derived from git
    assert "CANARY-OUT" not in "".join(_bodies(net))


@pytest.mark.parametrize(
    "name", ["../netrc.txt", "notes.txt", ".git/config.txt", ".GIT/config.txt", ".Git/config.txt"]
)
def test_the_slop_section_never_scores_a_file_outside_the_project(jev, tmp_path, outside, name):
    # Kills: readable_inside removed from prose_text.
    repo = _repo(tmp_path, {})
    (repo / "notes.txt").symlink_to(outside)
    (repo / ".git" / "config.txt").write_text("url = CANARY-OUT-git\n", encoding="utf-8")
    with patch(URLOPEN) as net:
        slop_check.check_slop_score(repo, [name], None, 30)
    assert "CANARY-OUT" not in "".join(_bodies(net))


@pytest.mark.parametrize("name", [".GIT/config", ".Git/config", "src/../.GIT/hooks/x"])
def test_git_metadata_is_refused_in_any_case(tmp_path, name):
    # Kills: the case-sensitive ``".git" in parts`` test restored AND the
    # inode comparison removed (on APFS either one alone still refuses).
    repo = _repo(tmp_path, {})
    (repo / ".git" / "hooks" / "x").write_text("x\n", encoding="utf-8")
    assert qp.jev_advisory.readable_inside(repo, name) is None


def test_a_nested_git_dir_in_another_case_is_refused(tmp_path):
    # Kills: the case-sensitive part test restored. The inode check only
    # knows ``root/.git``, so a nested repository's ``.GIT`` rests on it.
    repo = _repo(tmp_path, {})
    (repo / "vendor" / ".git").mkdir(parents=True)
    (repo / "vendor" / ".git" / "config").write_text("[core]\n", encoding="utf-8")
    assert qp.jev_advisory.readable_inside(repo, "vendor/.GIT/config") is None


def test_the_root_git_dir_is_refused_by_identity_under_another_spelling(tmp_path):
    # Kills: the inode comparison removed. Only a case-insensitive file
    # system spells ``root/.git`` another way; elsewhere there is no alias.
    repo = _repo(tmp_path, {})
    if not (repo / ".GIT").exists():
        pytest.skip("case-sensitive file system: .GIT is not .git here")
    assert qp.jev_advisory._under_git_dir(repo.resolve(), (repo / ".GIT" / "config").resolve())


def test_an_ordinary_file_is_still_readable(tmp_path):
    repo = _repo(tmp_path, {"src/app.py": "x = 1\n", "docs/gitignore.md": "text\n"})
    for name in ("src/app.py", "docs/gitignore.md"):
        assert qp.jev_advisory.readable_inside(repo, name) == (repo / name).resolve()


# --- finding 51: the allowlist judges the file that is read, not the link --

LINK_CANARY = "CANARY-LINK-51"


@pytest.fixture
def linked(tmp_path) -> Path:
    """A committed config file, untracked links to it, and links to source."""
    root = tmp_path / "repo"
    root.mkdir()
    (root / "config.yaml").write_text(f"api_host: {LINK_CANARY}.example.invalid\n",
                                      encoding="utf-8")
    (root / "real.py").write_text("LINKED_OK = 1\n", encoding="utf-8")
    (root / "real.md").write_text("Plain linked prose that a person wrote.\n",
                                  encoding="utf-8")
    _git(root, "init", "-q", "-b", "master")
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "base")
    for link, target in (("util.py", "config.yaml"), ("notes.md", "config.yaml"),
                         ("ok.py", "real.py"), ("guide.md", "real.md")):
        (root / link).symlink_to(target)
    return root


@pytest.mark.parametrize("derived", [False, True], ids=["named", "derived-from-git"])
def test_the_prescreen_skips_a_link_to_a_config_file_on_record(jev, linked, derived):
    # Kills: partition_paths judging the name only; the reason string changed.
    changed = None if derived else ["util.py", "ok.py"]
    with patch(URLOPEN, return_value=_approved()) as net:
        report = qp.run_prescreen(linked, changed, "s-link")
    bodies = "".join(_bodies(net))
    assert LINK_CANARY not in bodies and "LINKED_OK = 1" in bodies
    assert {"path": "util.py", "reason": "path-class"} in report["skipped_paths"]
    assert "util.py" not in [r["file"] for r in report["files"]]
    assert "ok.py" in [r["file"] for r in report["files"]]


def test_file_diff_never_reads_through_a_link_to_a_config_file(linked):
    # Kills: the resolved check removed from _untracked_diff (the second layer).
    base = qp._diff_base(linked)
    assert qp.file_diff(linked, base, "util.py") == ""
    assert "+LINKED_OK = 1" in qp.file_diff(linked, base, "ok.py")


def test_the_slop_section_skips_a_link_to_a_config_file_on_record(jev, linked):
    # Kills: the resolved check removed from prose_text; its reason changed.
    base = qp._diff_base(linked)
    assert slop_check.prose_text(linked, base, "notes.md") == ("", "path-class")
    with patch(URLOPEN, return_value=fake_ok({})) as net:
        result = slop_check.check_slop_score(linked, ["notes.md", "guide.md"], None, 30)
    assert net.call_count == 1 and LINK_CANARY not in "".join(_bodies(net))
    assert sent_payload(net)["state"]["path"] == "guide.md"
    assert "path-class" in result.summary  # the skip row, or notes.md's own row


@pytest.mark.parametrize(("name", "target"), [
    ("util.py", "config.yaml"), ("gone.py", "missing.yaml"), ("up.py", "../outside.py"),
    ("hard.py", None), ("copy.py", None)])
def test_a_name_is_judged_by_the_file_it_resolves_to(linked, name, target):
    # Kills: the target's suffix not judged (util, gone), the outside check
    # dropped (up), the hard-link check removed (hard, copy).
    (linked.parent / "outside.py").write_text("OUT = 1\n", encoding="utf-8")
    if (linked / name).is_symlink():
        pass  # util.py: the fixture's own link
    elif target is not None:
        (linked / name).symlink_to(target)
    else:
        os.link(linked / ("config.yaml" if name == "hard.py" else "real.py"), linked / name)
    assert qp.jev_advisory.resolved_path_allowed(linked, name) is False


@pytest.mark.parametrize("name", ["ok.py", "guide.md", "real.py", "deleted.py"])
def test_a_link_to_source_and_a_plain_file_are_still_allowed(linked, name):
    assert qp.jev_advisory.resolved_path_allowed(linked, name) is True


def test_the_prescreen_records_a_hard_link_as_path_class(jev, linked):
    os.link(linked / "config.yaml", linked / "hard.py")
    with patch(URLOPEN, return_value=_approved()) as net:
        report = qp.run_prescreen(linked, ["hard.py"], "s-hard")
    assert net.call_count == 0 and LINK_CANARY not in "".join(_bodies(net))
    assert report["skipped_paths"] == [{"path": "hard.py", "reason": "path-class"}]


def test_a_directory_or_a_fifo_is_refused_on_the_resolved_side(linked):
    # Kills: the S_ISREG guard reverted to round 8 (directory passes) or
    # dropped (a FIFO has one link, so the link count alone passes it).
    (linked / "folder.md").mkdir()
    os.mkfifo(linked / "pipe.py")
    assert qp.jev_advisory.resolved_path_allowed(linked, "folder.md") is False
    assert qp.jev_advisory.resolved_path_allowed(linked, "pipe.py") is False


def test_a_target_whose_stat_fails_is_refused(linked, monkeypatch):
    # Kills: ``except OSError: return False`` flipped to True (r8 m2).
    class Unstattable:
        name = "a.py"

        def stat(self) -> os.stat_result:
            raise PermissionError("denied")

    monkeypatch.setattr(qp.jev_advisory, "readable_inside", lambda *_: Unstattable())
    assert qp.jev_advisory.resolved_path_allowed(linked, "a.py") is False


def test_a_tracked_hard_link_to_config_prose_is_refused_before_git(tmp_path):
    # Kills: the resolved guard in prose_text moved below the tracked branch (r8 m1).
    root = tmp_path / "repo"
    root.mkdir()
    (root / "config.yaml").write_text("k: 1\n", encoding="utf-8")
    os.link(root / "config.yaml", root / "hard.md")
    _git(root, "init", "-q", "-b", "master")
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "base")
    with (root / "config.yaml").open("a", encoding="utf-8") as fh:
        fh.write(f"api_host: {LINK_CANARY}.example.invalid\n")
    base = qp._diff_base(root)
    assert evidence_checks._git_tracks(root, "hard.md")  # the tracked branch is live
    assert slop_check.prose_text(root, base, "hard.md") == ("", "path-class")


# --- finding 52: a changed-file name is a name, never a pathspec ------------

SPEC_CANARY = "CANARY-SPEC-52"
PATHSPEC_NAMES = [":!x.py", ":!x.md", "big.md", "lib.py", "*.py", "b*.md", "old.md"]
PROSE_PATHSPEC_NAMES = [":!x.md", "big.md", "*.md", "b*.md", "old.md"]


@pytest.fixture
def specs(tmp_path) -> Path:
    """Committed config and directories named like source, then changed.

    ``big.md`` and ``lib.py`` are tracked directories holding YAML,
    ``old.md`` a tracked directory the change deleted, and ``:!x.py`` /
    ``:!x.md`` untracked files whose names are pathspec magic.
    """
    root = tmp_path / "repo"
    files = {"config.yaml": "k: 0\n", "app.py": "APP = 1\n", "big.md/inner.yaml": "k: 1\n",
             "lib.py/settings.yaml": "k: 1\n", "old.md/secret.yaml": f"k: {SPEC_CANARY}-old\n"}
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text, encoding="utf-8")
    _git(root, "init", "-q", "-b", "master")
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "base")
    config = "".join(f"line{i}: {SPEC_CANARY}-{i}\n" for i in range(3000))
    changes = {"config.yaml": config, "app.py": "APP = 2\n",
               "big.md/inner.yaml": f"k: {SPEC_CANARY}-dir\n",
               "lib.py/settings.yaml": f"k: {SPEC_CANARY}-lib\n",
               ":!x.py": "X_OK = 1\n", ":!x.md": "Plain prose a person wrote.\n"}
    for name, text in changes.items():
        (root / name).write_text(text, encoding="utf-8")
    shutil.rmtree(root / "old.md")
    return root


@pytest.mark.parametrize("name", PATHSPEC_NAMES)
def test_the_prescreen_reads_a_pathspec_name_as_one_file(jev, specs, name):
    # Kills, with the next rows: any one of the three layers removed.
    assert SPEC_CANARY not in qp.file_diff(specs, qp._diff_base(specs), name)
    with patch(URLOPEN, return_value=_approved()) as net:
        qp.run_prescreen(specs, [name, "app.py"], "s-spec")
    bodies = "".join(_bodies(net))
    assert SPEC_CANARY not in bodies and "+APP = 2" in bodies


@pytest.mark.parametrize("name", PROSE_PATHSPEC_NAMES)
def test_the_slop_section_reads_a_pathspec_name_as_one_file(jev, specs, name):
    text, _ = slop_check.prose_text(specs, qp._diff_base(specs), name)
    assert SPEC_CANARY not in text
    with patch(URLOPEN, return_value=fake_ok({})) as net:
        slop_check.check_slop_score(specs, [name, ":!x.md"], None, 30)
    bodies = "".join(_bodies(net))
    assert SPEC_CANARY not in bodies and "Plain prose a person wrote." in bodies


def test_a_directory_name_is_skipped_on_record(jev, specs):
    # Kills: the S_ISREG guard reverted (big.md then reached file_diff).
    with patch(URLOPEN, return_value=_approved()):
        report = qp.run_prescreen(specs, ["big.md", "lib.py"], "s-dir")
    assert report["skipped_paths"] == [{"path": "big.md", "reason": "path-class"},
                                       {"path": "lib.py", "reason": "path-class"}]


def test_magic_and_glob_names_reach_git_literally(specs):
    # Kills: the literal flag and env removed from literal_git.run (plain git
    # expands ``:!x.md`` to every other file and ``b*.md`` never matches).
    base = qp._diff_base(specs)
    assert evidence_checks._added_lines(specs, base, ":!x.md") == []
    assert evidence_checks._git_tracks(specs, ":!x.md") is False
    proc = qp._git(specs, "diff", base, "--", ":!x.py")
    assert proc is not None and proc.returncode == 0 and proc.stdout == ""


def test_every_git_call_of_both_readers_is_literal(jev, specs, monkeypatch):
    # Kills: the env or the flag dropped from literal_git.run, or a reader
    # calling git past it.
    calls: list[tuple[list[str], dict[str, str] | None]] = []
    real = subprocess.run

    def spy(cmd, *args, **kwargs):
        if cmd and cmd[0] == "git":
            calls.append((list(cmd), kwargs.get("env")))
        return real(cmd, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", spy)
    base = qp._diff_base(specs)
    calls.clear()
    for name in PATHSPEC_NAMES:
        qp.file_diff(specs, base, name)
        slop_check.prose_text(specs, base, name)
    assert calls and all(
        cmd[1] == "--literal-pathspecs" and (env or {}).get("GIT_LITERAL_PATHSPECS") == "1"
        for cmd, env in calls)


def test_no_reader_calls_subprocess_past_the_literal_helper():
    # Kills: a new ``subprocess.run(["git", ...])`` in either module, or
    # the shared evidence helpers calling git directly again.
    import ast
    import inspect

    for module in (qp, slop_check):
        assert "subprocess.run(" not in inspect.getsource(module)
    for fn in (evidence_checks._git_tracks, evidence_checks._added_lines):
        calls = {ast.unparse(n.func) for n in ast.walk(ast.parse(inspect.getsource(fn)))
                 if isinstance(n, ast.Call)}
        assert "literal_git.run" in calls and "subprocess.run" not in calls


def test_a_diff_covering_more_than_the_name_is_refused_whole(specs):
    # Kills: names_exactly removed from file_diff (the deleted directory
    # ``old.md`` is missing, so the names alone admit it).
    base = qp._diff_base(specs)
    assert qp.file_diff(specs, base, "old.md") == ""
    assert qp.file_diff(specs, base, "app.py").startswith("diff --git a/app.py b/app.py")


def test_the_names_check_alone_refuses_a_directory_in_prose(specs, monkeypatch):
    # Kills: names_exactly removed from prose_text, with the regular-file
    # guard bypassed to isolate it.
    monkeypatch.setattr(slop_check.jev_advisory, "resolved_path_allowed", lambda *_: True)
    assert slop_check.prose_text(specs, qp._diff_base(specs), "big.md") == ("", "path-class")


def test_every_chunk_carries_its_file_header_and_is_judged(jev, specs):
    # Kills: carry_git_headers removed (continuation chunks were SENT).
    config_diff = subprocess.run(
        ["git", "diff", qp._diff_base(specs), "--", "config.yaml"],
        cwd=specs, capture_output=True, text=True, check=True).stdout
    chunks = qp.chunk_diff("x.py", config_diff)
    assert len(chunks) > 1 and all(len(c) <= qp.MAX_DIFF_CHARS for c in chunks)
    assert all("\ndiff --git a/config.yaml b/config.yaml\n" in c for c in chunks)
    assert {_path_class(diff_state(c, "x.py")) for c in chunks} == {"egress-denied:path-class"}


# --- QG PR3 round 9: the fix-forward rows (m1-m5) ---------------------------

OK_HEADER = "diff --git a/ok.py b/ok.py"
FORGED = "diff --git a/config.yaml b/config.yaml"
# Every separator str.splitlines breaks on that privacy's newline split does not.
LINE_SEPARATORS = ["\x0b", "\x0c", "\x1c", "\x1d", "\x1e", "\x85", "\u2028", "\u2029", "\r"]


@pytest.mark.parametrize("sep", LINE_SEPARATORS, ids=lambda c: f"U+{ord(c):04X}")
def test_a_line_separator_inside_a_content_line_never_forges_a_carried_header(jev, sep):
    # Kills (m3): _split_lines or _git_header_lines back on str.splitlines
    # (the fragment after the separator became the header chunks 2+ carry,
    # or started a chunk of its own, and those chunks were refused).
    head = f"{OK_HEADER}\n--- a/ok.py\n+++ b/ok.py\n@@ -0,0 +1,3 @@\n"
    for filler in range(0, 160, 3):
        diff = head + "+x y\n" * filler + f"+a{sep}{FORGED}\n" + "+x y\n" * 300
        chunks = qp.chunk_diff("ok.py", diff, 1200)
        assert len(chunks) > 1
        for chunk in chunks:
            headers = [ln for ln in chunk.split("\n") if ln.startswith("diff --git ")]
            assert headers == [OK_HEADER], (filler, chunk[:200])
            prepare_state(diff_state(chunk, "ok.py"), redact=True, state_class="diff")


# (limit, depth): the header line is ~4 * depth chars, the largest each limit admits.
LONG_HEADER_CASES = [(qp.MAX_DIFF_CHARS, 2800), (qp.MAX_DIFF_CHARS, 1500), (5000, 450),
                     (2000, 100)]


@pytest.mark.parametrize(("limit", "depth"), LONG_HEADER_CASES)
def test_a_long_carried_header_keeps_every_chunk_within_the_limit(limit, depth):
    # Kills (m2): the carried-header reserve deleted from chunk_diff (each
    # continuation chunk then ran past ``limit`` by the header's length).
    name = "h/" * depth + "s.py"
    header = f"diff --git a/{name} b/{name}"
    diff = f"{header}\n--- a/{name}\n+++ b/{name}\n@@ -1 +1 @@\n" + "+w w w x\n" * 6000
    chunks = qp.chunk_diff("f.py", diff, limit)
    assert len(chunks) > 2 and len(header) > limit // 5
    assert all(len(c) <= limit for c in chunks)
    assert all(c.split("\n", 1)[1].startswith(header + "\n") for c in chunks)


def _replaced_dir_repo(tmp_path: Path) -> tuple[Path, str]:
    """``big.md`` committed as a directory, then staged as a regular file."""
    root = tmp_path / "replaced"
    (root / "big.md").mkdir(parents=True)
    (root / "big.md" / "inner.yaml").write_text(f"k: {SPEC_CANARY}-staged\n", encoding="utf-8")
    _git(root, "init", "-q", "-b", "master")
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "base")
    base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True,
                          text=True, check=True).stdout.strip()
    _git(root, "rm", "-r", "-q", "--cached", "big.md")
    shutil.rmtree(root / "big.md")
    (root / "big.md").write_text("New prose line.\n", encoding="utf-8")
    _git(root, "add", "big.md")
    return root, base


def test_a_staged_file_that_replaced_a_directory_is_refused_whole(tmp_path):
    # Kills (m1): names_exactly's ``== [name, ""]`` turned into a membership
    # check (git lists big.md AND big.md/inner.yaml for the name big.md).
    root, base = _replaced_dir_repo(tmp_path)
    names = subprocess.run(["git", "diff", "--name-only", base, "--", "big.md"], cwd=root,
                           capture_output=True, text=True, check=True).stdout.split()
    assert names == ["big.md", "big.md/inner.yaml"]
    assert qp.partition_paths(root, ["big.md"])[0] == ["big.md"]
    assert qp.literal_git.names_exactly(root, base, "big.md", 30) is False
    assert qp.file_diff(root, base, "big.md") == ""
    assert slop_check.prose_text(root, base, "big.md") == ("", "path-class")


@pytest.fixture
def old_git(tmp_path, monkeypatch) -> tuple[Path, str]:
    """A repo with tracked ``x.py`` changed, then a git that rejects ``--literal-pathspecs``."""
    root = _repo(tmp_path, {})
    (root / "x.py").write_text("X = 1\n", encoding="utf-8")
    _git(root, "add", "x.py")
    _git(root, "commit", "-q", "-m", "x")
    base = qp._diff_base(root)
    (root / "x.py").write_text(f"X = 2  # {SPEC_CANARY}-old-git\n", encoding="utf-8")
    shim = tmp_path / "old-git-bin"
    shim.mkdir()
    real = shutil.which("git")
    (shim / "git").write_text(
        "#!/bin/sh\ncase \"$1\" in --literal-pathspecs) "
        "echo 'unknown option: --literal-pathspecs' >&2; exit 129;; esac\n"
        f'exec "{real}" "$@"\n', encoding="utf-8")
    (shim / "git").chmod(0o755)
    monkeypatch.setenv("PATH", f"{shim}{os.pathsep}{os.environ['PATH']}")
    return root, base


def _no_whole_file_read(monkeypatch) -> None:
    def refuse(*_args: object) -> None:
        raise AssertionError("file_diff read the whole file")
    monkeypatch.setattr(qp.jev_advisory, "readable_inside", refuse)


def test_a_git_without_literal_pathspecs_reads_no_diff(old_git, monkeypatch):
    # Kills (m4): the tracking probe back on ``returncode != 0`` (exit 129
    # was read as "untracked" and x.py sent whole as a new file).
    root, base = old_git
    assert qp._git(root, "ls-files", "--error-unmatch", "--", "x.py").returncode == 129
    _no_whole_file_read(monkeypatch)
    assert qp.file_diff(root, base, "x.py") == ""


@pytest.mark.parametrize("name", ["x.py/", "./x.py", "x.py//", "./new.py", "new.py/"])
def test_a_name_git_would_not_print_is_never_read_whole(tmp_path, monkeypatch, name):
    # Kills (m4): the git-spelling guard removed from _untracked_diff
    # (``x.py/`` is "not tracked" to git and x.py on disk).
    root = _repo(tmp_path, {"x.py": "X = 1\n"})
    _git(root, "add", "x.py")
    _git(root, "commit", "-q", "-m", "x")
    (root / "x.py").write_text("X = 2\n", encoding="utf-8")
    (root / "new.py").write_text("NEW = 1\n", encoding="utf-8")
    base = qp._diff_base(root)
    assert qp.file_diff(root, base, "new.py").startswith("diff --git a/new.py b/new.py\nnew file")
    _no_whole_file_read(monkeypatch)
    assert qp.file_diff(root, base, name) == ""


def test_names_exactly_compares_relative_names_from_a_subdirectory(tmp_path):
    # Kills (m5): ``--relative`` dropped from names_exactly (git then printed
    # ``pkg/a.py`` for the name ``a.py`` and every tracked file read False).
    root = _repo(tmp_path, {"pkg/a.py": "A = 1\n"})
    _git(root, "add", "pkg/a.py")
    _git(root, "commit", "-q", "-m", "a")
    base = qp._diff_base(root)
    (root / "pkg" / "a.py").write_text("A = 2\n", encoding="utf-8")
    pkg = root / "pkg"
    assert qp.literal_git.names_exactly(root, base, "pkg/a.py", 30) is True
    assert qp.literal_git.names_exactly(pkg, base, "a.py", 30) is True
    assert "+A = 2" in qp.file_diff(pkg, base, "a.py")
    assert qp.literal_git.names_exactly(pkg, base, "../base.txt", 30) is False


def test_evidence_cli_prints_the_slop_skip_without_the_list(jev, tmp_path, capsys):
    (jev / ".arkaos" / "redaction-clients.json").unlink()
    repo = _repo(tmp_path, {"NOTES.md": "Plain prose.\n"})
    with patch(URLOPEN) as net:
        evidence_checks.main([str(repo), "--checks", "slop-score", "--changed-files", "NOTES.md"])
    assert "slop-score: skipped reason=redaction-config-missing" in capsys.readouterr().out
    net.assert_not_called()


# --- 2. the Stop state: three fields, never the transcript -------------------

@pytest.fixture
def stop_env(jev, tmp_path, monkeypatch):
    from core.hooks import stop as stop_hook
    from core.workflow import state as _st

    monkeypatch.chdir(tmp_path)
    _st.reset_root_cache()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: jev))
    for key, value in {"ARKA_STOP_LINT": "0", "ARKA_SESSION_MEMORY": "0",
                       "ARKA_AUTO_DOC_QUEUE": str(tmp_path / "queue"),
                       "ARKA_WF_REQUIRED_DIR": str(tmp_path / "wf"),
                       "ARKAOS_ROOT": str(Path(__file__).resolve().parents[2])}.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(stop_hook, "arkaos_temp_dir", lambda name: tmp_path / name)
    monkeypatch.setattr("core.workflow.flow_enforcer.TELEMETRY_PATH", tmp_path / "enf.jsonl")
    monkeypatch.setattr("core.governance.skill_proposer._DEFAULT_OUTPUT_DIR", tmp_path / "p")
    monkeypatch.setattr("core.decisions.shadow.spawn_shadow", lambda *a, **k: None)
    (tmp_path / "wf").mkdir()
    (tmp_path / "wf" / "s-stop").write_text("1", encoding="utf-8")
    return stop_hook


def _tool_turns(n: int) -> list[dict[str, Any]]:
    recs: list[dict[str, Any]] = []
    for i in range(n):
        recs.append({"role": "assistant", "content": [
            {"type": "tool_use", "id": f"t{i}", "name": "Bash", "input": {"command": "cat"}}]})
        result = f"CANARY-TOOL-{i} {CLIENT} {SECRET_LINES['assignment']}"
        content = result if i % 2 else [{"type": "text", "text": result}]
        recs.append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": f"t{i}", "content": content}]})
    return recs


def test_the_stop_body_carries_three_fields_and_nothing_of_the_transcript(stop_env, tmp_path):
    recs = [{"role": "user", "content": "migra a tabela"}, *_tool_turns(50),
            {"role": "assistant", "content": "Migrei a tabela e corri os testes."}]
    transcript = tmp_path / "t.jsonl"
    transcript.write_text("\n".join(json.dumps(r) for r in recs), encoding="utf-8")
    with patch(URLOPEN, return_value=fake_ok({})) as net:
        stop_env.main({"session_id": "s-stop", "transcript_path": str(transcript),
                       "stop_hook_active": "false", "cwd": str(tmp_path)})
    assert net.call_count == 1
    state = sent_payload(net)["state"]
    assert state == {"response": "Migrei a tabela e corri os testes.",
                     "user_message": "migra a tabela", "tool_uses": 50}
    body = json.dumps(sent_payload(net))
    assert "CANARY-TOOL" not in body and CLIENT not in body and TOKEN_VALUE not in body


def test_a_privacy_refusal_rotates_an_oversized_audit_like_any_line(jev):
    # PR2 finding 8 still applies to the new deny lines (they go through
    # audit.record): an audit over the cap moves to .1, the refusal lands fresh.
    from core.egress.audit import AUDIT_MAX_BYTES

    path = jev / ".arkaos" / "egress" / "audit.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as fh:
        fh.truncate(AUDIT_MAX_BYTES + 1)
    with pytest.raises(DecisionUnavailable):
        prepare_state(diff_state(f"+{SECRET_LINES['bearer-header']}\n"), redact=True,
                      state_class="diff")
    assert path.with_name("audit.jsonl.1").stat().st_size == AUDIT_MAX_BYTES + 1
    rows = _audit(jev)
    assert len(rows) == 1 and rows[0]["layer"] == "privacy"


# --- QG PR3 r7: the diff class is a suffix ALLOWLIST (the operator's decision) --
# Six rounds found one more syntax per round that binds a secret in a config
# file; the detectors stay as defence in depth and the boundary is the file.
# Each row carries NO secret: what refuses it is the path alone.
PATH_REFUSED: dict[str, str] = {
    "yaml": ".github/workflows/ci.yml", "yaml-long": "config/app.yaml",
    "json": "package.json", "toml": "pyproject.toml", "xml": "app/Web.config.xml",
    "properties": "src/main/resources/application.properties", "ini": "setup.ini",
    "conf": "nginx.conf", "cfg": "setup.cfg", "plist": "Info.plist",
    "config": "app/Web.config", "env-dotfile": ".env", "env-suffix": "deploy/prod.env",
    "netrc": ".netrc", "netrc-home": "home/u/.netrc", "dockerfile": "Dockerfile",
    "makefile": "Makefile", "pem": "certs/server.pem", "key": "certs/server.key",
    "crt": "certs/server.crt", "p12": "keystore.p12", "jks": "keystore.jks",
    "lock-poetry": "poetry.lock", "lock-yarn": "yarn.lock", "go-sum": "go.sum",
    "binary-png": "logo.png", "binary-so": "lib/native.so", "empty": "",
    "trailing-space": "app.py ", "windows-env": "C:\\app\\.env",
}
CLEAN_DIFF = "+x = 1\n"


def _path_class(state: object) -> str:
    with pytest.raises(DecisionUnavailable) as info:
        prepare_state(state, redact=True, state_class="diff")
    return info.value.reason


@pytest.mark.parametrize("shape", sorted(PATH_REFUSED))
def test_a_diff_of_a_file_outside_the_allowlist_never_leaves(jev, shape):
    # Kills: DIFF_SOURCE_SUFFIXES widened to the class, or the check skipped.
    state = {"path": PATH_REFUSED[shape], "diff": CLEAN_DIFF}
    assert _path_class(state) == "egress-denied:path-class"
    # Serialised: a JSON string names no file entry, so it is pathless.
    assert _path_class(json.dumps(state)) == "egress-denied:path-class"


@pytest.mark.parametrize("state", [
    {"diff": CLEAN_DIFF}, {"prose": "Plain prose."}, {"content": "export {}"},
    CLEAN_DIFF, json.dumps({"diff": CLEAN_DIFF}), [], {"path": None, "diff": CLEAN_DIFF},
    {"nested": {"path": "a.py", "diff": CLEAN_DIFF}},  # deeper than a file entry
], ids=["dict", "prose", "content", "raw", "serialised", "empty-list", "none", "nested"])
def test_a_diff_state_that_names_no_file_is_refused(jev, state):
    # Kills: a pathless diff state allowed (fail-open on the class).
    assert _path_class(state) == "egress-denied:path-class"


@pytest.mark.parametrize("suffix", sorted(privacy.DIFF_SOURCE_SUFFIXES))
def test_every_allowlisted_suffix_leaves(jev, suffix):
    # Kills: a suffix dropped from the list, or the list emptied.
    state = {"path": f"src/Module{suffix.upper() if suffix == '.py' else suffix}",
             "diff": CLEAN_DIFF}
    assert prepare_state(state, redact=True, state_class="diff") == state


def test_every_file_entry_of_a_list_must_be_allowlisted(jev):
    good = {"path": "core/a.py", "diff": CLEAN_DIFF}
    both = [good, {"path": "b.ts", "diff": CLEAN_DIFF}]
    assert prepare_state(both, redact=True, state_class="diff") == both
    assert prepare_state({"files": both}, redact=True, state_class="diff") == {"files": both}
    for bad in ({"path": ".env", "diff": CLEAN_DIFF}, {"diff": CLEAN_DIFF}):
        assert _path_class([good, bad]) == "egress-denied:path-class"
        assert _path_class({"files": [good, bad]}) == "egress-denied:path-class"


@pytest.mark.parametrize("header", [
    "diff --git a/.env b/.env", "diff --git a/core/a.py b/config/app.yaml",
    "diff --git a/config/app.yaml b/core/a.py",
    'diff --git "a/sec\\303\\251t.key" "b/sec\\303\\251t.key"', "diff --git garbage",
])
def test_a_git_header_inside_the_diff_names_its_file_too(jev, header):
    # Kills: only the declared path read (a multi-file diff under a .py path);
    # either side of a header dropped in _named_paths (QG r7 m1).
    state = {"path": "core/a.py", "diff": f"{header}\n+x = 1\n"}
    assert _path_class(state) == "egress-denied:path-class"


def test_a_git_header_of_source_files_leaves(jev):
    state = {"path": "core/a.py", "diff": "diff --git a/core/a b.py b/core/a b.py\n+x = 1\n"}
    assert prepare_state(state, redact=True, state_class="diff") == state


def test_a_path_class_refusal_is_audited_without_the_path(jev):
    before = len(_audit(jev))
    _path_class({"path": f"deploy/{CLIENT}.env", "diff": CLEAN_DIFF})
    rows = _audit(jev)
    assert len(rows) == before + 1
    last = rows[-1]
    assert last["allowed"] is False and last["layer"] == "privacy"
    assert [f["kind"] for f in last["findings"]] == ["path-class"]
    raw = (jev / ".arkaos" / "egress" / "audit.jsonl").read_text(encoding="utf-8")
    assert CLIENT not in raw


def test_other_classes_are_not_gated_by_the_path(jev):
    assert prepare_state({"prompt": "olá"}, redact=True, state_class="prompt") == {
        "prompt": "olá"}


def test_the_prescreen_skips_config_files_before_diffing_and_records_them(jev, tmp_path):
    # Kills: the prescreen filter off (the .yaml diff would reach the wire,
    # or privacy would refuse it and the row would say so).
    files = {"app.py": "X = 1\n", "config/app.yaml": "debug: true\n", ".env": "DEBUG=1\n"}
    repo = _repo(tmp_path, files)
    changed = list(files)
    with patch(URLOPEN, return_value=_approved()) as net:
        report = qp.run_prescreen(repo, changed, "s-skip")
    assert net.call_count == 1 and "app.py" in _bodies(net)[0]
    assert [r["file"] for r in report["files"]] == ["app.py"]
    assert report["skipped_paths"] == [
        {"path": "config/app.yaml", "reason": "path-class"},
        {"path": ".env", "reason": "path-class"}]
    tier = qp.compute_tier(repo, changed)
    assert report["reviewers"] == qp.dispatch_reviewers(tier)  # the list never moves
    path = qp.write_prescreen("s-skip", report)
    assert json.loads(path.read_text(encoding="utf-8"))["skipped_paths"] == report[
        "skipped_paths"]


def test_the_prescreen_filter_runs_before_git(jev, tmp_path, monkeypatch):
    repo = _repo(tmp_path, {"secrets.yaml": "a: b\n"})
    diffed: list[str] = []
    real = qp.file_diff
    monkeypatch.setattr(qp, "file_diff", lambda r, b, n: diffed.append(n) or real(r, b, n))
    with patch(URLOPEN) as net:
        report = qp.run_prescreen(repo, ["secrets.yaml"], "s-skip2")
    assert diffed == [] and net.call_count == 0
    assert report["skipped_paths"] == [{"path": "secrets.yaml", "reason": "path-class"}]


def test_slop_score_prose_files_carry_their_path_and_leave(jev, tmp_path):
    # ui-in-ts and slop-score are unchanged in behaviour: .md is allowlisted.
    repo = _repo(tmp_path, {"NOTES.md": "Plain prose that a person wrote.\n"})
    with patch(URLOPEN, return_value=fake_ok({})) as net:
        slop_check.check_slop_score(repo, ["NOTES.md"], None, 30)
    assert net.call_count == 1 and sent_payload(net)["state"]["path"] == "NOTES.md"


# --- QG PR3 r6 majors through prepare_state (defence in depth under the allowlist) --
# A .NET or Spring XML file never leaves as a diff state now (path-class);
# the same text inside an allowlisted file (an XML string in a .cs/.java
# test, a heredoc in a .sh) is what these rows send to the detectors.
R6_SECRET = "q8Zr" + "2mXv7LpT0wKd"
R6_LEAKS: dict[str, tuple[str, str]] = {
    "dotnet-nested-value": ("tests/SettingsTest.cs", '+<setting name="ApiSecret" '
                            'serializeAs="String">\n+    <value>' + R6_SECRET + "</value>\n"),
    "spring-nested-value": ("src/test/DataSourceTest.java", '+<property name="password">\n'
                            "+        <value>" + R6_SECRET + "</value>\n"),
    "netrc-account": ("scripts/setup.sh", "+machine h login u account " + R6_SECRET + "\n"),
    "path-keyed-json": ("src/keys.ts", '+  "auth/secret.key": "' + R6_SECRET + '",\n'),
    "path-keyed-php": ("config/keys.php", "+    '/etc/secrets/api.token' => '" + R6_SECRET
                       + "',\n"),
    "stripe-ts": ("src/lib/billing.ts", '+const stripe = new Stripe("sk_' + "live_"
                  + "51Hq8Zr2mXv7LpT0wKd9Qx" + '");\n'),
    "stripe-curl": ("scripts/charge.sh", "+curl https://api.stripe.com/v1/charges -u sk_"
                    + "live_51Hq8Zr2mXv7LpT0wKd9Qx:\n"),
}


@pytest.mark.parametrize("shape", sorted(R6_LEAKS))
def test_round_6_majors_are_refused_by_prepare_state(jev, shape):
    # Kills: the nested-value carry, netrc ``account``, the path-word pairing,
    # the Stripe vendor patterns (each removed).
    path, diff = R6_LEAKS[shape]
    assert _refused(diff_state(diff, path)) == "egress-denied:secret"


@pytest.mark.parametrize("shape", sorted(R6_LEAKS))
def test_round_6_majors_in_an_xml_or_config_file_stop_at_the_path(jev, shape):
    _, diff = R6_LEAKS[shape]
    assert _refused(diff_state(diff, "config/app.config")) == "egress-denied:path-class"
