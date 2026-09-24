"""core.egress.credentials — context-marked credentials the prefix list misses.

Fixture values are built at runtime from synthetic fragments, so no
literal credential lives in the repo and the evidence engine's own
security-grep never fires on this file.
"""

from __future__ import annotations

import functools
import json
import re
from datetime import UTC, datetime

import pytest

from core.egress import credentials as _cred
from core.egress.credentials import credential_labels, egress_secret_labels
from core.egress.policy import evaluate

OPAQUE = "Zq9" + "k7" * 14  # 31 chars, digits, no vendor prefix
PASSWORD = "Hunter" + "2" + "Secret!"  # arka:sec-ok(hardcoded-password): synthetic fixture
BARE_PASSWORD = f"PASSWORD={PASSWORD} ./run"
DB_ASSIGN = f"export DB_PASSWORD='{PASSWORD}'"  # arka:sec-ok(hardcoded-password): synthetic fixture
NOW = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)

POSITIVE = [
    (f"export API_TOKEN={OPAQUE}", "credential assignment"),
    (f"PGPASSWORD={OPAQUE} psql -h db", "credential assignment"),
    (DB_ASSIGN, "credential assignment"),
    (f"deploy --api-key {OPAQUE}", "credential flag"),
    (f"login --password={PASSWORD}", "credential flag"),
    (f"curl -H 'Authorization: Bearer {OPAQUE}' https://api.example.org", "auth header"),
    (f'curl -H "X-Api-Key: {OPAQUE}" https://api.example.org', "auth header"),
    (f"curl -u bob:{PASSWORD} https://api.example.org", "basic-auth flag"),
    (f"mysql -u root -p{PASSWORD} app", "password flag"),
    (f"sshpass -p {PASSWORD} ssh host", "password flag"),
    (f"git clone https://bob:{OPAQUE}@git.example.org/r.git", "url userinfo"),
    (f"psql postgres://app:{PASSWORD}@db:5432/app", "url userinfo"),
    # QG PR2 r1 B2a: no prefix before the secret word.
    (f"TOKEN={OPAQUE} ./run", "credential assignment"),
    (BARE_PASSWORD, "credential assignment"),
    (f"KEY={OPAQUE} ./run", "credential assignment"),
    (f"SECRET={OPAQUE} ./run", "credential assignment"),
    (f"export token={OPAQUE}", "credential assignment"),
    # B2d: PASS / PWD words.
    (f"DB_PASS={PASSWORD} ./run", "credential assignment"),
    (f"PASS={PASSWORD} ./run", "credential assignment"),
    (f"MYSQL_PWD={PASSWORD} mysql app", "credential assignment"),
    # B2b: credentials in a query string.
    (f"curl 'https://api.example.org/v1?token={OPAQUE}'", "url query credential"),
    (f"curl 'https://x.example.org/?access_token={OPAQUE}&a=1'", "url query credential"),
    (f"curl 'https://x.example.org/m?api_key={OPAQUE}'", "url query credential"),
    (f"curl 'https://x.example.org/m?key={OPAQUE}'", "url query credential"),
    (f"curl 'https://x.example.org/f?password={PASSWORD}'", "url query credential"),
    (f"curl 'https://x.example.org/m?secret={OPAQUE}'", "url query credential"),
    (f"curl 'https://b.example.org/c?sv=1&sig={OPAQUE}'", "url query credential"),
    # B2c: quoted password flags.
    (f"mysql -u root -p'{PASSWORD}' app", "password flag"),
    (f'mysql -u root -p"{PASSWORD}" app', "password flag"),
    # B2d: other positional password arguments.
    (f"docker login -u bob -p {PASSWORD} registry.example.org", "password flag"),
    (f"redis-cli -h cache -a {PASSWORD} ping", "password flag"),
    (f"aws configure set aws_secret_access_key {OPAQUE}", "cli secret setting"),
    (f"aws configure set default.aws_session_token {OPAQUE}", "cli secret setting"),
    # QG PR2 r2 B3: a value glued to ; ) or , (the separator used to be
    # swallowed into the value, which the reference rule then discarded).
    (f"export API_TOKEN={OPAQUE}; ./deploy", "credential assignment"),
    (f"(export API_TOKEN={OPAQUE})", "credential assignment"),
    (f"PGPASSWORD={OPAQUE},psql", "credential assignment"),
    (f"mysql -uroot -p{PASSWORD};", "password flag"),
    (f"sshpass -p {PASSWORD};ssh h", "password flag"),
    (f"docker login -p {PASSWORD})", "password flag"),
    (f"echo Authorization: Bearer {OPAQUE};", "auth header"),
    (f"echo X-Api-Key: {OPAQUE})", "auth header"),
    (f"curl https://x.example.org -u bob:{PASSWORD},", "basic-auth flag"),
    (f"curl https://x.example.org/?token={OPAQUE};", "url query credential"),
    (f"$(curl https://x.example.org/?token={OPAQUE})", "url query credential"),
    (f"curl https://bob:ab;cd{OPAQUE}@x.example.org", "url userinfo"),
    (f"export TOKEN='ab;cd,{OPAQUE})'", "credential assignment"),
    (f'export TOKEN="ab cd {OPAQUE}"', "credential assignment"),
    # QG PR2 r2 M1: httpie / xh basic auth.
    (f"http --auth bob:{PASSWORD} GET https://api.example.org", "basic-auth flag"),
    (f"http -a bob:{PASSWORD} GET https://api.example.org", "basic-auth flag"),
    (f"xh --auth=bob:{PASSWORD} https://api.example.org", "basic-auth flag"),
    # QG PR2 r3 M2: brackets and braces are data, even when a sub-token
    # detector starts inside a single-quoted word.
    (f"curl -u 'admin:Xk9]{OPAQUE}' https://api.example.org", "basic-auth flag"),
    (f"curl -H 'Authorization: Basic Xk9{{{OPAQUE}}}' https://api.example.org", "auth header"),
    (f"curl 'https://api.example.org/v1?api_key=Xk9]{OPAQUE}'", "url query credential"),
    (f"git clone 'https://bob:Xk9]{OPAQUE}@git.example.org/r.git'", "url userinfo"),
    (f"http -a 'bob:Xk9]{OPAQUE}' api.example.org", "basic-auth flag"),
    (f"API_TOKEN={OPAQUE}}}", "credential assignment"),
    ("export API_TOKEN=abc[123]" + OPAQUE, "credential assignment"),
    # r3: inside single quotes $ and the separators are data.
    ("curl -u 'admin:Pa$$w0rd" + OPAQUE + "' https://h.example.org", "basic-auth flag"),
    (f"curl -u 'admin:ab;cd{OPAQUE}' https://h.example.org", "basic-auth flag"),
    ("curl 'https://bob:Pa$$" + OPAQUE + "@h.example.org'", "url userinfo"),
]

NEGATIVE = [
    "export API_TOKEN=$API_TOKEN",
    'export API_TOKEN="${API_TOKEN}"',
    "export API_TOKEN=$(cat .token)",
    "export OPENAI_API_KEY=your-key-here",
    "export API_KEY=<token>",
    "export API_TOKEN=xxxxxxxx",
    "GOOGLE_APPLICATION_CREDENTIALS=/etc/sa.json gcloud auth",
    "export TOKEN_FILE=/run/secrets/token",
    "export SSH_KEY_PATH=~/.ssh/id_ed25519",
    "export SECRET_NAME=prod-db-2026",
    "export API_TOKEN_CMD=vault-read-v2",
    "SORT_KEY=created_at make report",
    "password = request.form['password']",
    "token = get_token(user)",
    "api_key = settings.API_KEY",
    "curl -H 'Authorization: Bearer $TOKEN' https://api.example.org",
    "curl -H \"Authorization: Bearer ${TOKEN}\" https://api.example.org",
    "mkdir -p build/out && ssh -p 2222 host",
    "mysql -u root -p app",
    "mysql -h db -P3306 -u root app",
    "git clone https://github.com/org/repo.git",
    "git clone git@github.com:org/repo.git",
    "psql postgres://app:$DB_PASS@db/app",
    "psql postgres://app:password@localhost/app",
    # Rows guarding the widened B2 patterns against ordinary commands.
    "export COMPASS_URL=http://intranet.example.org",
    "export TOKEN_URL=https://auth.example.org/token",
    "export API_KEY_DOCS=https://docs.example.org/keys",  # URL value, not a pointer name
    "export TOKEN_URL=auth-v2.example.org",  # pointer name, not a URL value
    "export PASSWORD_STORE_DIR=~/.password-store",
    "export BYPASS=1",
    "export PASSTHROUGH=enabled",
    "KEYBOARD=us make",
    "cd $PWD && OLDPWD=/tmp cd -",
    "docker run -e TOKEN=$TOKEN image",
    "docker login registry.example.org",
    "redis-cli -h cache ping",
    "aws configure set region eu-west-1",
    'curl "https://x.example.org/?page=2&sort=key"',
    'curl "https://x.example.org/?key=$KEY"',
    "curl 'https://x.example.org/?token=<token>'",
    'git commit -m "rotate key=value parsing"',
    "kubectl get secret my-secret -o yaml",
    "grep -rn password src/",
    # r2: the terminator class and the call guard must not flag code or prose.
    "api_key = compute_key2(x)",
    "token = tokens2[0]",
    'export SORT_KEY="created at"',
    "export API_TOKEN=$API_TOKEN; ./deploy",
    "(export API_TOKEN=$(cat .token))",
    # M1 negatives: -a on other tools, httpie without a literal password.
    "ls -a /tmp",
    "git commit -a -m 'wip: fix 2 tests'",
    "http GET https://api.example.org/items",
    "http -a $USER:$PASS GET https://api.example.org",
    "http --auth-type=bearer GET https://api.example.org",
    # r3: a value that is only a reference stays a reference in single
    # quotes; code shapes stay code.
    "curl -u 'bob:$PASS' https://api.example.org",
    "cfg_key = cfg[k1]",
    "key = f(x)",
    "TOKEN=${TOK}",
    "export API_TOKEN=$(vault read x)",
    # r3: header NAMES in a search are prose, not credentials.
    'grep "Authorization: Bearer" logs/',
    "grep -rn 'Authorization: Bearer' src/",
    'grep -n "X-Api-Key: missing header" app.log',
    # r3: a sub-token inside double quotes stops at whitespace, or the
    # JSON-serialised layer (the whole command in double quotes) would run
    # a short value into the rest of the command.
    "docker run -u 1000:1000 image && echo done",
]


@pytest.mark.parametrize(("text", "label"), POSITIVE)
def test_context_marked_credentials_are_labelled(text, label):
    # Kills: removing any single detector (its rows lose their label).
    assert label in credential_labels(text)


@pytest.mark.parametrize("text", NEGATIVE)
def test_references_placeholders_and_pointers_pass(text):
    # Kills: dropping _REFERENCE / _PLACEHOLDER / _POINTER_SUFFIX / _PATHLIKE.
    assert credential_labels(text) == []


def test_labels_never_carry_the_value():
    labels = credential_labels(f"export API_TOKEN={OPAQUE}")
    assert all(OPAQUE not in label for label in labels)


def test_egress_vocabulary_keeps_the_vendor_prefixes():
    slack = "xoxb-" + "1234567890" + "-abcdef"
    assert "Slack token" in egress_secret_labels(slack)
    assert egress_secret_labels("plain text") == []


@pytest.mark.parametrize("levels", [0, 1, 2, 3])
def test_every_escape_layer_is_scanned(levels):
    # Kills: scanning fewer escape layers than the nesting (r4 note). Each
    # level of shell nesting adds 2**n backslashes before the quote.
    quote = "\\" * (2**levels - 1) + '"'
    # curl -u, not an assignment: a bare run of 2**n - 1 backslashes is itself
    # token-like, so an assignment row would be caught on layer 0 by chance.
    text = f"curl -u {quote}bob:{PASSWORD}{quote} x"
    assert "basic-auth flag" in credential_labels(text)


def test_non_text_is_empty():
    assert credential_labels(None) == []  # type: ignore[arg-type]


def test_policy_denies_a_bearer_header_and_audits_no_value(tmp_path):
    # Kills: policy still calling secret_labels (the header leaves).
    cfg = tmp_path / "redaction-clients.json"
    cfg.write_text(json.dumps({"clients": ["acme-alpha"]}), encoding="utf-8")
    audit_path = tmp_path / "audit.jsonl"
    decision = evaluate(
        f"curl -H 'Authorization: Bearer {OPAQUE}' https://api.example.org",
        "decisions:jev", config_path=cfg, home=tmp_path / "home",
        allowlist_path=tmp_path / "allow.json", audit_path=audit_path, now=NOW,
    )
    assert not decision.allowed
    assert [(f.kind, f.token) for f in decision.findings] == [("secret", "auth header")]
    assert OPAQUE not in audit_path.read_text(encoding="utf-8")


# --- Probe: forms x suffixes x paths (QG PR2 r2, r3) -----------------------
# Every leak form x every suffix x every egress path must be REFUSED; every
# benign form x every path must be SENT. The QG artefacts record only the
# counts of the reviewers' probes (23 leak and 19 false-positive shapes), not
# the shapes, so this set is the union of the round-1 probe, the shapes the
# round-2 reviewers named, and every POSITIVE and NEGATIVE row above. The
# id prefix names the detector a form exercises (mutation table).

LEAK_FORMS: dict[str, str] = {
    "assign-export": f"export API_TOKEN={OPAQUE}",
    "assign-bare-token": f"TOKEN={OPAQUE}",
    "assign-lower": f"export token={OPAQUE}",
    "assign-bare-password": f"PASSWORD={PASSWORD}",
    "assign-bare-key": f"KEY={OPAQUE}",
    "assign-bare-secret": f"SECRET={OPAQUE}",
    "assign-pgpassword": f"PGPASSWORD={OPAQUE}",
    "assign-db-pass": f"DB_PASS={PASSWORD}",
    "assign-pass": f"PASS={PASSWORD}",
    "assign-mysql-pwd": f"MYSQL_PWD={PASSWORD}",
    "assign-single-quoted": DB_ASSIGN,
    "assign-double-quoted": f'export API_TOKEN="{OPAQUE}"',
    "assign-quoted-space": f"export TOKEN='ab cd {OPAQUE}'",
    "assign-quoted-separators": f'export TOKEN="ab;cd,ef){OPAQUE}"',
    "assign-subshell": f"(export API_TOKEN={OPAQUE}",
    "flag-api-key": f"deploy --api-key {OPAQUE}",
    "flag-password-eq": f"login --password={PASSWORD}",
    "flag-password-quoted": f'tool --password "{PASSWORD}"',
    "authhdr-bare": f"echo Authorization: Bearer {OPAQUE}",
    "authhdr-quoted": f"curl -H 'Authorization: Bearer {OPAQUE}'",
    "keyhdr-bare": f"echo X-Api-Key: {OPAQUE}",
    "basic-curl-tail": f"curl https://api.example.org -u bob:{PASSWORD}",
    "basic-curl-quoted": f'curl -s -u "bob:{PASSWORD}"',
    "httpie-auth": f"http --auth bob:{PASSWORD}",
    "httpie-a": f"http -a bob:{PASSWORD}",
    "httpie-xh": f"xh -a bob:{PASSWORD}",
    "pwflag-mysql": f"mysql -u root -p{PASSWORD}",
    "pwflag-mysql-single": f"mysql -uroot -p'{PASSWORD}'",
    "pwflag-mysql-double": f'mysql -u root -p"{PASSWORD}"',
    "pwflag-sshpass": f"sshpass -p {PASSWORD}",
    "pwflag-docker": f"docker login -u bob -p {PASSWORD}",
    "pwflag-redis": f"redis-cli -h cache -a {PASSWORD}",
    "aws-secret": f"aws configure set aws_secret_access_key {OPAQUE}",
    "aws-session": f"aws configure set default.aws_session_token {OPAQUE}",
    "userinfo-git": f"git clone https://bob:{OPAQUE}@git.example.org/r.git",
    "userinfo-separators": f"curl https://bob:ab;cd,ef){OPAQUE}@x.example.org",
    "query-token": f"curl https://api.example.org/v1?token={OPAQUE}",
    "query-access-token": f"curl https://x.example.org/?a=1&access_token={OPAQUE}",
    "query-api-key": f"curl https://x.example.org/m?api_key={OPAQUE}",
    "query-key": f"curl https://x.example.org/m?key={OPAQUE}",
    "query-password": f"curl https://x.example.org/f?password={PASSWORD}",
    "query-secret": f"curl https://x.example.org/m?secret={OPAQUE}",
    "query-sig": f"curl https://b.example.org/c?sv=1&sig={OPAQUE}",
    "vendor-slack": "xoxb-" + "1234567890" + "-abcdefghijklmnop",
    # QG PR2 r3 M2 and Marta's bare shapes.
    "basic-single-bracket": f"curl -u 'admin:Xk9]{OPAQUE}'",
    "authhdr-single-brace": f"curl -H 'Authorization: Basic Xk9{{{OPAQUE}}}'",
    "query-single-bracket": f"curl 'https://api.example.org/v1?api_key=Xk9]{OPAQUE}'",
    "userinfo-single-bracket": f"git clone 'https://bob:Xk9]{OPAQUE}@git.example.org/r.git'",
    "httpie-single-bracket": f"http -a 'bob:Xk9]{OPAQUE}'",
    "assign-trailing-brace": f"API_TOKEN={OPAQUE}}}",
    "assign-inner-brackets": "export API_TOKEN=abc[123]" + OPAQUE,
    "assign-braces-word": f"export DB_PASS=Pa{{ss}}{OPAQUE}",
    "pwflag-mysql-bracket": f"mysql -uroot -pPa]{OPAQUE}",
    # r3: $ and separators inside single quotes are data.
    "basic-single-dollar": "curl -u 'admin:Pa$$w0rd" + OPAQUE + "'",
    "basic-single-separator": f"curl -u 'admin:ab;cd{OPAQUE}'",
    "userinfo-single-dollar": "curl 'https://bob:Pa$$" + OPAQUE + "@h.example.org'",
    "pwflag-mysql-single-dollar": "mysql -p'Pa$$w0rd" + OPAQUE + "'",
}
# The reviewers' own shapes, verbatim (QG PR2 r2/r3 scratchpad probes
# probe3.py, probe4.py, probe_r2.py), each on the three paths. They carry
# their own separators, so they are not crossed with SUFFIXES.
REVIEWER_LEAKS: list[str] = [
    "export API_TOKEN=abc123XYZ99; curl x", "TOKEN=s3cr3tV4lue&& ls", "DB_PASS=hunter2x|cat",
    "API_KEY=abc123def456) ", "PGPASSWORD=Zq9w8e7r6t,psql",
    "curl -H 'Authorization: Bearer abc123def456;' x", "curl -H X-Api-Key:abc123def456; ls",
    "curl 'https://h/x?token=abc123def456;x'", "curl -u bob:hunter2pw; ls",
    "http -a bob:hunter2pw example.com", "http --auth=bob:hunter2pw example.com",
    "xh --auth bob:hunter2pw x.io", "https POST x.io -a bob:s3cretpw",
    "API_TOKEN=abc123XYZ99}", "export API_TOKEN=abc[123]XYZ", "export DB_PASSWORD=Pa{ss}w0rd99",
    "MYSQL_PWD=a[b]c1234 mysql", "curl -H 'Authorization: Bearer abc{123}def' x",
    "curl -u bob:pa[ss]w0rd x", "mysql -uroot -pPa]ss99", "curl 'https://h/x?token=ab{c}123456'",
    "https://bob:pa[ss]99@h.com", "export API_TOKEN='abc[123]XYZ'",
    'export API_TOKEN="abc[123]XYZ"',
    "curl -u 'admin:Xk9]pL2vQ' https://api.example.com",
    "curl -u 'admin:Xk9]pL2vQ!' https://api.example.com",
    "curl -H 'Authorization: Basic Xk9{pL2vQ}' https://api.example.com",
    "curl 'https://api.example.com/v1?api_key=Xk9]pL2vQ'",
    "git clone 'https://bob:Xk9]pL2vQ@git.example.com/r.git'",
    "http -a 'bob:Xk9]pL2vQ' api.example.com", "curl -u 'admin:Xk9pL2vQ' https://api.example.com",
    "export API_TOKEN=abc123XYZ99; ./deploy", "export API_TOKEN=abc123XYZ99;./deploy",
    "mysql -uroot -phunter22;", 'curl -H "Authorization: Bearer abcdef123456;" x',
    "(export API_TOKEN=abc123XYZ99)", "PGPASSWORD=abc123xyz,psql",
    'curl "https://h/v1?token=Zq8vLm2pXr7tN4wK;"', "export TOKEN=s3cr3tValue99; ./d",
    "export TOKEN=s3cr3tValue99 && ./d", "export TOKEN=s3cr3tValue99 ; ./d",
    "export TOKEN=s3cr3tValue99|cat", "export TOKEN=s3cr3tValue99&&./d",
    "http --auth bob:S3cretPw9 GET https://h", "http -a bob:S3cretPw9 GET https://h",
    "sshpass -p hunter22;ssh h", "docker login -u bob -p S3cretPw9;",
    # QG PR2 r4 N1 (Paulo's reproduction, verbatim): an apostrophe in the
    # prose before the command flipped the whole-text quote reading.
    "I can't log in with curl -u 'admin:Summer$2026x' https://api.example.com, why?",
    "it's: http -a 'bob:Pa$$w0rd9' x.io",
    "can't auth: curl -H 'Authorization: Bearer ab$c9Zq9k7k7' x",
    # r4 m2: quoted code-shaped values are data (kills the guard on wrapped
    # values). 'x9[a]' is 5 chars, under _MIN_VALUE; 'x9[ab]' is the row.
    "export API_TOKEN='x9[ab]'", '--token "Qx9{abc}"',
    # r4 m3: an unencoded @ inside the userinfo password.
    "git clone 'https://bob:p@ss{w0}rd@g.io/r'", "git clone https://bob:p@ssw0rd9@g.io/r",
    # r4 note: escaped quotes (nested shell quoting, JSON-escaped text).
    'ssh host "export API_TOKEN=\\"abc123XYZ99\\" && ./run"',
    'bash -c "curl -u \\"bob:hunter2pw\\" x"', 'bash -c "mysql -p\\"hunter22\\" app"',
    'export API_TOKEN=\\"abc123XYZ99\\"',
    # r4 N1, either reading refuses: here the shell really opens the quote at
    # the apostrophe, so the $ is data and the local "..." reading is wrong.
    "echo don't -H \"Authorization: Bearer ab$c9Zq9k7k7\" x'",
]
REVIEWER_BENIGN: list[str] = [
    "ls -a", "git commit -a -m fix", "http -a $USER:$PASS x.io", "http --auth-type=bearer x.io",
    "export API_TOKEN=$(vault read x)", "TOKEN=${TOK}", "key = f(x)", 'SORT_KEY="created at"',
    "api_key = compute_key2(x)", "cfg_key = cfg[k1]",
    # r4 N1: the local reading must not turn a quoted reference into a secret.
    "it's fine: curl -u 'bob:$PASS' x", "don't: curl -H 'Authorization: Bearer $TOKEN' x",
    "curl 'https://bob:$PASS@h.io/x'", "it's Bob's: curl -u bob:$PASS 'x'",
    "echo x'y 'curl -u bob:$PASS z", 'ssh h "export API_TOKEN=\\"\\$API_TOKEN\\""',
]
# Suffixes glued to the form, no space (the B3 shape), plus one spaced
# control. The "-expansion" variants put a $ right after the separator: a
# value class that swallows the separator then captures an expansion
# marker too and discards a real secret, so they pin the terminator class
# of each pattern, while the plain separators pin the expansion rule.
SUFFIXES: dict[str, str] = {
    "plain": "",
    "semicolon": ";next",
    "paren": ")next",
    "comma": ",next",
    "and": "&&next",
    "pipe": "|next",
    "redirect": ">out.txt",
    "spaced-semicolon": " ; next",
    "semicolon-expansion": ";$next",
    "paren-expansion": ")$(next)",
    "comma-expansion": ",${next}",
    "and-expansion": "&&$next",
    "pipe-expansion": "|$next",
    "redirect-expansion": ">$out",
}
BENIGN_FORMS: list[str] = [
    *NEGATIVE,
    "ssh -i ~/.ssh/key host",
    "git log --pretty=format:%H",
    "git config user.signingkey ABCD1234EF",
    "npm run build -- --token-file .t",
    'python -c "print(key)"',
    "git status && make test",
    *REVIEWER_BENIGN,
]
PATHS = ("redacted", "redaction-disabled", "config-missing")


@pytest.fixture(scope="module")
def probe_home(tmp_path_factory):
    from _decisions_helpers import isolate_decisions

    with pytest.MonkeyPatch.context() as mp:
        home = isolate_decisions(mp, tmp_path_factory.mktemp("probe"), clients=["acmecorp"])
        yield home


def _send(home, text: str, path: str) -> bool:
    """True when ``text`` would leave on ``path``; False when refused."""
    from core.decisions.client import DecisionUnavailable
    from core.decisions.privacy import prepare_state

    config = home / ".arkaos" / "redaction-clients.json"
    config.write_text(json.dumps({"clients": ["acmecorp"]}), encoding="utf-8")
    if path == "config-missing":
        config.unlink()
    try:
        prepare_state({"command": text}, redact=path != "redaction-disabled",
                      state_class="command", session_id="probe")
    except DecisionUnavailable as exc:
        assert "egress-denied:secret" in str(exc), str(exc)
        return False
    return True


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("suffix", list(SUFFIXES), ids=list(SUFFIXES))
@pytest.mark.parametrize("form", list(LEAK_FORMS), ids=list(LEAK_FORMS))
def test_probe_leak_form_is_refused(probe_home, form, suffix, path):
    assert not _send(probe_home, LEAK_FORMS[form] + SUFFIXES[suffix], path)


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("text", BENIGN_FORMS)
def test_probe_benign_form_is_sent(probe_home, text, path):
    assert _send(probe_home, text, path)


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("text", REVIEWER_LEAKS)
def test_probe_reviewer_leak_is_refused(probe_home, text, path):
    assert not _send(probe_home, text, path)


# QG PR2 r5 B1: the scan must stay linear in the text. ``privacy`` scans
# the JSON-serialised state, where newlines are ``\n`` and a whole paste
# is ONE line of up to 1,000,000 characters; any per-match work over the
# rest of the line (the round-5 local reading, an unbounded regex window)
# is quadratic there. Measured on the round-5 code: 100 KB 3.9 s, 200 KB
# 15.6 s; after the fix 0.05 s and 0.10 s.
_SLOW = 1.0
_CAP_SLOW = 4.0  # CPU seconds for one form at the 1 MB cap (up to 2 MB serialised)

# PR3 post-approval CI calibration. The absolute ceilings in this file measure
# the machine as well as the code: the ubuntu 3.12 coverage leg ran the same
# scans ~2.3x slower than the operator's machine (0.8 -> 1.64 s, 1.15 -> 2.64
# s) and failed four ceilings while every interleaved RATIO test passed. Each
# absolute ceiling is multiplied by ``_machine()``: a fixed regex workload
# independent of ``core.egress`` (so a slower scan cannot loosen its own
# bound), timed once per session, divided by its time on the operator's
# machine. The factor never goes below 1.0 and is capped at 4.0, so code 4x
# slower than today still fails on the slowest supported runner. The ratio
# tests stay unscaled: they are the linearity proof.
_REFERENCE_LOCAL = 0.083  # CPU s, best of 3, Apple M4 Max, CPython 3.13, 2026-09-24
_MACHINE_MAX = 4.0
_CALIBRATION_TEXT = "".join(f'"k{i % 97}": "v{i * 7919 % 10007}", ' for i in range(80_000))
_CALIBRATION_RE = re.compile(r'"([a-z]\w*)":\s*"([^"\\]*)"|\d{3,}')


def _reference_workload() -> float:
    """Best of 3 in process CPU time: six ``findall`` passes over ~1.26 MB."""
    from time import process_time

    best = float("inf")
    for _ in range(3):
        began = process_time()
        for _ in range(6):
            _CALIBRATION_RE.findall(_CALIBRATION_TEXT)
        best = min(best, process_time() - began)
    return best


@functools.cache
def _machine() -> float:
    """How much slower this machine is than the reference one, in ``[1.0, 4.0]``."""
    return min(_MACHINE_MAX, max(1.0, _reference_workload() / _REFERENCE_LOCAL))


def _ceiling(base: float) -> float:
    return base * _machine()


def _over(took: float, base: float) -> str:
    return (f"took {took:.2f} s CPU (ceiling {_ceiling(base):.2f} s, "
            f"machine factor {_machine():.2f})")


def _under_coverage() -> bool:
    """A tracer (``sys.settrace``), pytest-cov's env, or a live ``coverage.Coverage``."""
    import os
    import sys

    cov = sys.modules.get("coverage")
    current = getattr(getattr(cov, "Coverage", None), "current", None)
    return (sys.gettrace() is not None or bool(os.environ.get("COV_CORE_SOURCE"))
            or (callable(current) and current() is not None))


# QG PR3 r6 m3: the tracer makes the 1 MB cap step cost 9-22 s per unit. Under
# coverage the step runs at half the size (250 KB -> 500 KB, 1 MB serialised)
# with half the ceiling, so the bound per character is the same.
_CAP_SIZE, _CAP_CEILING = (500_000, _CAP_SLOW / 2) if _under_coverage() else (
    1_000_000, _CAP_SLOW)
# CPU seconds for one adversarial shape (``_timed``). Worst form measured on
# the PR3 round-5 tree, best of 3 in process CPU time: 0.31 s without
# coverage, 0.51 s under ``--cov=core`` (``kv-json`` and the finding-42
# ``positional`` row, ~420 KB serialised); 1.5 s is a 2.9x margin over the
# worst under coverage. The quadratic mutants these rows kill run for many
# seconds at these sizes. The test name keeps its review references.
_SHAPE_SLOW = 1.5


def _curl_paste(lines: int) -> str:
    return "".join(
        f'curl -sS -H "Authorization: Bearer $TOKEN" "https://api.example.com/v1/items/{i}'
        '?page=1" | jq .\n'
        for i in range(lines)
    )


def _timed(text: str) -> float:
    """Best of 3 runs of the detector in CPU time; stops once a run is clearly slow.

    Process CPU time, not wall time (PR3 round 5): the scheduler time a
    loaded runner takes away is not counted, and a quadratic scan is still
    quadratic in it. Same discipline as ``_interleaved``.
    """
    from time import process_time

    best = float("inf")
    for _ in range(3):
        began = process_time()
        credential_labels(text)
        best = min(best, process_time() - began)
        if best > 2 * _ceiling(_SHAPE_SLOW):
            break
    return best


def _interleaved(small_text: str, large_text: str, rounds: int = 5) -> tuple[float, float]:
    """Best of ``rounds`` for each size, ALTERNATING, in CPU time (PR2 round-6 m1).

    Wall time back to back let machine load land on one size only (the 3x
    ratio flaked 2/8 under 2x CPU load; interleaved wall time still 1/8 at
    4x). Process CPU time does not count the time the scheduler takes away,
    and a quadratic scan is still quadratic in it.
    """
    from time import process_time

    best = [float("inf"), float("inf")]
    for _ in range(rounds):
        for i, text in enumerate((small_text, large_text)):
            began = process_time()
            credential_labels(text)
            best[i] = min(best[i], process_time() - began)
    return best[0], best[1]


def test_serialised_many_match_paste_scans_in_linear_time():
    # Kills: the round-5 ``_local`` (O(line) per match), 15x over the bound.
    small, large = _interleaved(json.dumps({"prompt": _curl_paste(500)}),  # ~50 KB
                                json.dumps({"prompt": _curl_paste(2000)}))  # ~200 KB
    assert large <= _ceiling(_SLOW), f"200 KB serialised paste {_over(large, _SLOW)}"
    # 4x the text: linear is ~4x the time, quadratic ~16x (round 5: 0.97 s ->
    # 15.62 s). 8x sits halfway, with a 2x margin to either side.
    assert large <= 8 * small + 0.05, f"not linear: {small:.3f} s -> {large:.3f} s"


@pytest.mark.parametrize(
    ("unit", "quote", "size"),
    [("'a' \"-u x:y\" ", "", 100_000), ("-u a:$(x) ", "'", 300_000), ("mysql x ", "", 100_000),
     ("http x ", "", 100_000), ("redis-cli x ", "", 100_000), ("docker login x ", "", 100_000),
     ("a.", "", 100_000), ("a-", "", 100_000),
     # PR3 finding 33: the key/value and annotated-assignment detectors.
     ('"a": "b", ', "", 300_000), ("token: " + "x" * 47 + " ", "", 300_000),
     ("k", "", 300_000),
     # PR3 finding 43: one identifier holding the secret word again and again.
     ("token", "", 100_000),
     # QG r5 finding 47: element openers, unclosed elements, netrc windows.
     ("<password key='a' ", "", 300_000), ("<password>a", "", 300_000),
     ("machine login ", "", 300_000), ("\n password ", "", 300_000)],
    ids=["quotes", "one-quoted-span", "mysql", "httpie", "redis", "docker", "dotted", "dashed",
         "kv-json", "annotation", "one-identifier", "secret-word-run", "xml-attrs",
         "xml-unclosed", "netrc-machine", "netrc-lines"],
)
def test_adversarial_text_scans_under_a_second(unit, quote, size):
    # Kills: the round-5 ``_local`` (quotes), a value read without its cap
    # (one-quoted-span: every reference value runs to the far quote, so no
    # match short-circuits the scan), an unbounded tool-argument window
    # (mysql .. docker), an unbounded userinfo scheme (dotted, dashed).
    text = f"{quote} " + unit * (size // len(unit)) + quote
    for form in (text, json.dumps({"prompt": text})):
        took = _timed(form)
        assert took < _ceiling(_SHAPE_SLOW), f"{len(form)} chars {_over(took, _SHAPE_SLOW)}"


@pytest.mark.parametrize(
    ("text", "label"),
    [
        # A value longer than the read bound is still read (its head decides).
        ("can't: curl -H 'Authorization: Bearer ab$c" + "Zq9k7" * 200 + "' x", "auth header"),
        ('curl -H "Authorization: Bearer ' + "Zq9k7" * 200 + '" x', "auth header"),
        # A scheme longer than the bound matches on its tail.
        ("x" * 80 + f"://bob:{PASSWORD}@h.example.org", "url userinfo"),
        ("1.https://bob:" + PASSWORD + "@h.example.org", "url userinfo"),
    ],
)
def test_bounded_reads_keep_long_values(text, label):
    for form in (text, json.dumps({"prompt": text})):
        assert label in credential_labels(form)


# PR2 round-6 m3: the lower edges of the two bounds. ~490 characters of real
# arguments before the password flag stay inside ``_ARGS{0,512}`` (kills
# ``_ARGS{0,16}``); a quoted value is read ``_VALUE_CAP`` characters past
# its regex match (m2: ``start + floor + _VALUE_CAP``), and a read that hits
# the cap gets no reference exemption.
_ARG_RUNS = {
    "mysql": ("mysql ", "--host=db.example.org ", f"-p{PASSWORD} app"),
    "redis-cli": ("redis-cli ", "-h cache.example.org ", f"-a {PASSWORD} ping"),
    "docker": ("docker login ", "--username=bob-builder ", f"-p {PASSWORD} r.example.org"),
    "httpie": ("http ", "Accept:application/json ", f"-a bob:{PASSWORD} x.example.org"),
}


@pytest.mark.parametrize("tool", sorted(_ARG_RUNS))
def test_a_password_flag_after_490_chars_of_arguments_is_refused(tool):
    head, arg, tail = _ARG_RUNS[tool]
    args = arg * (490 // len(arg))
    assert 470 <= len(args) <= 500
    text = head + args + tail
    for form in (text, json.dumps({"command": text})):
        assert credential_labels(form), f"{tool}: {len(args)} chars of args"


def test_a_literal_tail_past_a_long_reference_head_is_refused():
    # Kills the round-5 read as it shipped: ``start + max(floor, _VALUE_CAP)``
    # AND no capped rule; the 301-char head then reads as a whole reference
    # and the tail is never seen. With the capped rule in place the formula
    # alone survives here (a capped read is refused anyway); the next row
    # separates the two formulas.
    text = "curl -u 'bob:$" + "A" * 300 + " tail9!' https://h.example.org"
    assert "basic-auth flag" in credential_labels(text)


def test_a_reference_of_exactly_the_cap_past_a_one_char_floor_is_read_to_its_end():
    # Kills ``limit = start + max(floor, _VALUE_CAP)`` on its own: the bare
    # run is ``$`` (floor 1, it stops at ``(``) and the value is 256 chars.
    # ``start + floor + 256`` reads it to its closing quote, a reference;
    # ``start + max(1, 256)`` stops one char short, capped, and refuses it.
    value = "$(" + "x" * 253 + ")"
    assert len(value) == 256
    assert credential_labels(f"curl -u 'bob:{value}' https://h.example.org") == []


def test_a_capped_value_gets_no_reference_exemption():
    # Kills: ``not val.capped`` dropped from ``_literal``: the first 257 chars
    # read as ``$(...`` although the single-quoted value is a literal.
    text = "curl -u 'bob:$(" + "x" * 400 + ") tail9!' https://h.example.org"
    assert "basic-auth flag" in credential_labels(text)


def test_a_long_reference_read_to_its_end_is_not_a_secret():
    # Kills: ``_VALUE_CAP = 8``: a 203-char reference read to its closing
    # quote is a name, not a secret; capped early it would be refused.
    text = "curl -u 'bob:$(" + "x" * 200 + ")' https://h.example.org"
    assert credential_labels(text) == []


# --- PR3 findings 38 and 39: source-code strings and header call forms -----

DOLLAR_PW = "Tr0ub4dor" + "$" + "3xYz"  # a literal password holding ``$``
DOLLAR_TOKEN = "q8Zr" + "$" + OPAQUE[:16]
BEARER = OPAQUE[:16]  # 16 opaque chars, the quoted-bearer floor

# Finding 38: ``$`` inside a source-code string literal is data.
CODE_DOLLAR_LEAKS = [
    ('{"password": "' + DOLLAR_PW + '"}', "credential key-value"),  # JSON
    ("const cfg = { password: \"" + DOLLAR_PW + "\" };", "credential key-value"),  # JS
    ('password: "' + DOLLAR_PW + '"', "credential key-value"),  # YAML, double
    ("password: '" + DOLLAR_PW + "'", "credential key-value"),  # YAML, single
    ("password: " + DOLLAR_PW, "credential key-value"),  # YAML, bare
    ("'password' => \"" + DOLLAR_PW + "\",", "credential key-value"),  # PHP
    ("  password: `" + DOLLAR_PW + "`,", "credential key-value"),  # template, no slot
    ("  apiKey: `${prefix}" + OPAQUE + "`,", "credential key-value"),  # slot + literal
    ('password = "' + DOLLAR_PW + '"', "credential assignment"),  # Python
    ('API_KEY: str = "' + DOLLAR_PW + '"', "credential assignment"),  # typed
    ('{"Authorization": "Bearer ' + DOLLAR_TOKEN + '"}', "auth header"),  # quoted key
]
CODE_DOLLAR_BENIGN = [
    '{"password": "${DB_PASSWORD}"}',
    '{"password": "$DB_PASSWORD"}',
    'password: "${env.DB_PASSWORD}"',
    '"password": "$(cat /run/secrets/pw)"',
    "  apiKey: `${API_KEY}`,",
    "  token: `${prefix}-${suffix}`,",  # a template of slots only
    "headers: { Authorization: `Bearer ${token}` }",
    "'password' => $password,",
    "'password' => $this->password,",
    "password: $DB_PASSWORD",
    "token: ${{ secrets.GITHUB_TOKEN }}",
    # Shell assignments keep the shell reading: no spaces around ``=``.
    'export TOKEN="a${B}c1234"',
    'TOKEN="$A$B" ./run',
]

# Finding 39: the auth header as a call argument, and a quoted bearer string.
HEADER_CALL_LEAKS = [
    'headers.set("Authorization", "Bearer ' + BEARER + '")',  # JS Headers
    'req.Header.Set("Authorization", "Bearer ' + BEARER + '")',  # Go
    'conn.setRequestProperty("Authorization", "Bearer ' + BEARER + '");',  # Java
    "fetch(url, { headers: { Authorization: 'Bearer " + BEARER + "' } })",  # JS fetch
    'new Headers([["Authorization", "Token ' + BEARER + '"]])',
    'requests.get(u, headers={"Authorization": "Bearer ' + BEARER + '"})',  # Python
    'headers.set("Authorization", "Bearer ' + DOLLAR_TOKEN + '")',  # ``$`` in code
    'req.Header.Set("Authorization", "' + OPAQUE + '")',  # no scheme word
    "curl -H 'Authorization: Token token=" + OPAQUE + "' https://api.example.org",  # G2
    # No header key the detector knows: only the quoted-bearer string.
    'headers["Authorization"] = "Bearer ' + BEARER + '"',
    'conn.setRequestProperty(AUTH_HEADER, "Bearer ' + BEARER + '");',
]
HEADER_CALL_BENIGN = [
    'headers.set("Authorization", "Bearer " + token)',
    "headers.set('Authorization', `Bearer ${token}`)",
    "headers: { Authorization: `Bearer ${scheme}${token}` }",  # a template stays shell-read
    'req.Header.Set("Authorization", auth)',
    'req.Header.Set("Authorization", "Bearer "+tok)',
    # The same rows as a quoted fixture line: the scheme word is not a value.
    "'headers.set(\"Authorization\", \"Bearer \" + token)',",
    'log.warn("Token expired")',
    'raise Unauthorized("Bearer authentication")',
    'curl -H "Authorization: Bearer $TOKEN" https://api.example.org',
    "curl -H 'Authorization: Bearer ${TOKEN}' https://api.example.org",
    'headers["Authorization"] = "Bearer xxxxxxxxxxxxxxxxxxxx"',
]


@pytest.mark.parametrize(("text", "label"), CODE_DOLLAR_LEAKS)
def test_a_dollar_inside_a_source_code_string_is_data(text, label):
    # Kills: ``_kv_value`` mapping ``"`` back to _DOUBLE, the assignment or
    # header code reading dropped (finding 38).
    assert label in credential_labels(text)
    assert label in credential_labels(json.dumps({"diff": "+" + text}))


@pytest.mark.parametrize("text", CODE_DOLLAR_BENIGN)
def test_a_whole_reference_in_source_code_is_still_a_reference(text):
    assert credential_labels(text) == []


@pytest.mark.parametrize("text", HEADER_CALL_LEAKS)
def test_an_auth_header_as_a_call_argument_is_refused(text):
    # Kills: the ``"key", "value"`` form or the quoted-bearer detector removed
    # (finding 39).
    assert "auth header" in credential_labels(text)
    assert "auth header" in credential_labels(json.dumps({"diff": "+" + text}))


@pytest.mark.parametrize("text", HEADER_CALL_BENIGN)
def test_a_header_built_from_a_variable_is_not_a_secret(text):
    assert credential_labels(text) == []


# --- PR3 finding 41 (QG r2 B1): prefixed strings, keyword args, Go forms ----

PLAIN_PW = "Tr0ub4dor" + "X3xYz"  # a literal password without ``$``
F_TOKEN = "q8Zr" + "2mXv7LpT0wKd"

# Each row: the text, the label, and what it proves.
STRING_FORM_LEAKS = [
    ('conn = psycopg2.connect(host=h, password="' + DOLLAR_PW + '")',
     "credential assignment"),  # keyword argument after ``,``
    ('db.connect(user="u", password="' + DOLLAR_PW + '")', "credential assignment"),
    ('client = Client(api_key="' + DOLLAR_PW + '")', "credential assignment"),  # after ``(``
    ('    password="' + DOLLAR_PW + '",', "credential assignment"),  # exploded call
    ('conn = connect(password="' + DOLLAR_PW + '" if prod else None)',
     "credential assignment"),  # after ``(`` only
    ('SECRET_KEY = b"' + PLAIN_PW + '9"', "credential assignment"),  # bytes
    ('SECRET_KEY = rb"' + PLAIN_PW + '9"', "credential assignment"),
    ('password = r"' + DOLLAR_PW + '"', "credential assignment"),  # raw
    ("password = u'" + PLAIN_PW + "'", "credential assignment"),
    ('token = f"' + F_TOKEN + '"', "credential assignment"),  # f-string, no slot
    ('token = f"{prefix}' + F_TOKEN + '"', "credential assignment"),  # slot + literal
    ('TOKEN=b"' + PLAIN_PW + '"', "credential assignment"),  # prefix, no spaces
    ('SECRET_KEY=b"' + DOLLAR_PW + '"', "credential assignment"),  # prefix alone is code
    ('password := "' + PLAIN_PW + '"', "credential assignment"),  # Go
    ('password := "' + DOLLAR_PW + '"', "credential assignment"),
    ('password:="' + DOLLAR_PW + '"', "credential assignment"),
    ('var password string = "' + DOLLAR_PW + '"', "credential assignment"),
    ('const apiKey string = "' + PLAIN_PW + '"', "credential assignment"),
    ('{"password": b"' + PLAIN_PW + '"}', "credential key-value"),
    ("password: f'{a}" + F_TOKEN + "'", "credential key-value"),
    ('password: "${DB_PASSWORD:-' + PLAIN_PW + '}"', "credential key-value"),  # literal default
    ('SECRET_KEY = "' + PLAIN_PW + '9"', "credential assignment"),  # the control
]
STRING_FORM_BENIGN = [
    'token = f"{prefix}{suffix}"',
    'connect(password=f"{pw}")',
    'token = f"TOKEN={tok}"',  # a run ending in ``=`` labels the slot
    '"api_token": f"TOKEN={tok}"',
    '"token": f"{head}{tail}"',
    '"api_token": f"Bearer {tok}"',
    "connect(password=password, token=self.token)",
    'connect(password="$DB_PASSWORD")',  # arka:sec-ok(hardcoded-password): a reference
    'connect(password="${DB_PASSWORD}")',  # arka:sec-ok(hardcoded-password): a reference
    'password := os.Getenv("DB_PASSWORD")',
    "var password string",
    'token = b""',
    "the api key value = abc123",  # typed form needs ``var``/``const``
    # QG r2 m7: an empty default, a message or another name is a reference.
    'POSTGRES_PASSWORD: "${POSTGRES_PASSWORD:-}"',
    '"password": "${X:?required}"',
    "password: '${DB_PASSWORD:?set DB_PASSWORD}'",
    'password: "${DB_PASSWORD:-$FALLBACK_PW}"',
    'password: "${DB_PASSWORD:-${FALLBACK_PW}}"',
    # QG r2 m8: a format slot and a documented bearer placeholder.
    '"secret": "%(SECRET)s"',
    'doc: "Bearer token_here_placeholder"',
    'example = "Bearer your_token_goes_here1"',
]


@pytest.mark.parametrize(("text", "label"), STRING_FORM_LEAKS)
def test_prefixed_keyword_and_go_string_forms_are_refused(text, label):
    # Kills: the string-prefix group, the keyword-argument reading, ``:=`` or
    # the ``var``/``const`` type form removed, the f-string slot drop kept
    # whole (finding 41).
    assert label in credential_labels(text)
    assert label in credential_labels(json.dumps({"diff": "+" + text}))


@pytest.mark.parametrize("text", STRING_FORM_BENIGN)
def test_templates_references_and_placeholders_in_string_forms_pass(text):
    # Kills: the label-run rule of ``_template_literal``, the ``${NAME:-}``
    # reference forms, the ``-$OTHER`` resume guard, ``%(...)s`` or the
    # bearer placeholder words dropped (QG r2 m7, m8).
    assert credential_labels(text) == []


# --- PR3 finding 42 (QG r3 B2): a secret named inside a quoted string -------

WP_SALT = "x7#Qm!2@vL9p" + "$Kz&4Rt^8Yw*0Nb(3Hc)6Jd_1Fg+5Se="  # a wp-config salt shape

# Each row: the text, the label, and the rule it pins.
QUOTED_NAME_LEAKS = [
    ("define('AUTH_KEY',         '" + WP_SALT + "');", "credential quoted name"),  # wp-config
    ("define( 'DB_PASSWORD', '" + DOLLAR_PW + "' );", "credential quoted name"),
    ('os.environ["API_TOKEN"] = "' + F_TOKEN + '"', "credential quoted name"),  # subscript
    ('app.config["SECRET_KEY"] = "' + F_TOKEN + '9Zx"', "credential quoted name"),  # Flask
    ("$config['encryption_key'] = '" + F_TOKEN + "';", "credential quoted name"),  # PHP
    ("ENV['API_TOKEN'] = '" + F_TOKEN + "'", "credential quoted name"),  # Ruby
    ('if request.headers["X-Api-Key"] == "' + F_TOKEN + '":', "credential quoted name"),
    ('os.environ.setdefault("DB_PASSWORD", "' + PLAIN_PW + '")', "credential quoted name"),
    ('PASSWORD = os.getenv("PW", "' + DOLLAR_PW + '")', "credential quoted name"),  # ``pw``
    ('cfg.get("a", "API_TOKEN", "' + F_TOKEN + '")', "credential quoted name"),  # resume
    ('<add key="ApiKey" value="' + F_TOKEN + '" />', "credential quoted name"),  # .NET
    ('ds.setPassword("' + PLAIN_PW + '");', "credential setter"),  # setter verb
    ('builder.password("' + PLAIN_PW + '")', "credential setter"),  # the word alone
    ('client.withApiKey("' + F_TOKEN + '")', "credential setter"),
    ('requests.get(url, auth=("admin", "' + PLAIN_PW + '"))', "basic-auth pair"),
    ('s.auth = HTTPBasicAuth(user, "' + PLAIN_PW + '")', "basic-auth pair"),  # user a name
    ('session.mount(a, HTTPDigestAuth("admin", "' + PLAIN_PW + '"))', "basic-auth pair"),
    ('requests.get(u, auth=HTTPProxyAuth("admin", "' + PLAIN_PW + '"))', "basic-auth pair"),
    ('t.set_token("' + F_TOKEN + '", ttl=60)', "credential setter"),  # first argument
    # QG r3 m11: Kotlin and Swift declarations, refused by the assignment reading.
    ('val password = "' + DOLLAR_PW + '"', "credential assignment"),
    ('val password: String = "' + DOLLAR_PW + '"', "credential assignment"),
    ('let password = "' + DOLLAR_PW + '"', "credential assignment"),
    ('let password: String = "' + DOLLAR_PW + '"', "credential assignment"),
    # QG r3 m10: a secret split into short runs by slots is judged joined.
    ('token = f"q8Z{a}r2m{b}Xv7"', "credential assignment"),
    # QG r3 m12: a placeholder word INSIDE a token does not make it one.
    ('headers[AUTH] = "Bearer ' + F_TOKEN + '-example-Zz91"', "auth header"),
    ('headers[AUTH] = "Bearer eyJhbGciOiJIUzI1NiJ9.dummyX' + F_TOKEN + '.abc"', "auth header"),
    ('token: "' + F_TOKEN + '-example"', "credential key-value"),
]
QUOTED_NAME_BENIGN = [
    'home = os.environ["HOME"]',
    'config["timeout"] = "30s"',
    'os.environ["GIT_COMMIT"] = "a1b2c3d4e5f6"',  # an opaque value under a plain name
    "define('WP_DEBUG', 'false')",
    'tok = os.environ.get("API_TOKEN")',
    'os.environ.get("API_TOKEN", "")',
    "define('AUTH_KEY', 'put your unique phrase here');",  # the wp-config sample
    '<add key="Timeout" value="30" />',
    'FIELDS = ("password", "token", "secret")',
    "ds.setPassword(password)",
    "requests.get(url, auth=(user, pw))",
    'secret = get_secret("prod/db-password-2024")',  # a lookup by name, not a setter
    '"token": "user@example.com"',  # an RFC 2606 documentation address
    'api_key: "sk-your-api-key-here"',  # a short prefix, then placeholder words
    '"SEQUENZY_API_KEY": "seq_user_your_key_here"',
    'headers[AUTH] = "Bearer access_token_here2"',  # a digit after a placeholder word
]


@pytest.mark.parametrize(("text", "label"), QUOTED_NAME_LEAKS)
def test_a_secret_named_in_quotes_is_refused(text, label):
    # Kills: each finding-42 separator, the resume at the value, ``pw``, the
    # setter and pair detectors, the joined template runs (m10) and the
    # whole-value placeholder anchor (m12).
    assert label in credential_labels(text)
    assert label in credential_labels(json.dumps({"diff": "+" + text}))


@pytest.mark.parametrize("text", QUOTED_NAME_BENIGN)
def test_a_quoted_name_without_a_literal_secret_passes(text):
    # Kills: the setter verb rule, the name judged by words, the RFC 2606
    # address and the short-prefix placeholder rules dropped.
    assert credential_labels(text) == []
    assert credential_labels(json.dumps({"diff": "+" + text})) == []


@pytest.mark.parametrize(
    "unit", ['"a", ', 'x["a"] = "b"; ', 'set("a") ', 'auth=("a", ', '"Bearer ' + "token" * 4],
    ids=["positional", "subscript", "setter", "auth-pair", "placeholder-words"],
)
def test_finding_42_detectors_scan_in_linear_time(unit):
    text = unit * (300_000 // len(unit))
    for form in (text, json.dumps({"diff": text})):
        took = _timed(form)
        assert took < _ceiling(_SHAPE_SLOW), f"{len(form)} chars {_over(took, _SHAPE_SLOW)}"


# --- PR3 QG r4: dotted quoted names (R4-B1), Ruby forms (R4-M1), m13 --------

# Each row: the text, the label. A dot is allowed in a QUOTED name only.
DOTTED_AND_RUBY_LEAKS = [
    ('Config::set("services.stripe.secret", "' + F_TOKEN + '");', "credential quoted name"),
    ("config()->set('services.stripe.secret', '" + F_TOKEN + "');", "credential quoted name"),
    ("'stripe.secret' => '" + F_TOKEN + "',", "credential key-value"),  # Laravel config array
    ('"db.password": "' + PLAIN_PW + '"', "credential key-value"),  # dotted JSON key
    ('"fs.s3a.secret.key": "' + F_TOKEN + '"', "credential key-value"),
    ('System.setProperty("javax.net.ssl.trustStorePassword", "' + PLAIN_PW + '")',
     "credential quoted name"),  # Java system property
    ('conf.set("spark.hadoop.fs.s3a.secret.key", "' + F_TOKEN + '")', "credential quoted name"),
    ('ENV["API_TOKEN"] ||= "' + F_TOKEN + '"', "credential quoted name"),  # Ruby ``||=``
    ('config[:api_key] = "' + F_TOKEN + '"', "credential quoted name"),  # symbol subscript
    ('config[:api_key] ||= "' + F_TOKEN + '"', "credential quoted name"),
    ('ENV.fetch("API_TOKEN") { "' + F_TOKEN + '" }', "credential quoted name"),  # fetch block
    # m13: the trailing ``$`` of _PLACEHOLDER_WORDS: a word HEAD is not a placeholder.
    ('password: "my-' + F_TOKEN + '"', "credential key-value"),
    ('token: "test_' + F_TOKEN + '"', "credential key-value"),
    ('os.environ["API_TOKEN"] = "live-' + F_TOKEN + '"', "credential quoted name"),
]
DOTTED_AND_RUBY_BENIGN = [
    '"db.password.file": "/etc/x/pw"',  # a pointer word ends the name
    '"spring.datasource.password": "${DB_PASSWORD}"',  # a reference
    '"api.key.id": "k1a2b3c4d5"',
    "'services.stripe.key' => env('STRIPE_KEY'),",  # a call, not a literal
    "'app.name' => 'Laravel',",
    'ENV.fetch("API_TOKEN") { nil }',
    'ENV["API_TOKEN"] ||= ENV["FALLBACK_TOKEN"]',
    "x[:5] = 'abc'",  # a slice, not a symbol
]


@pytest.mark.parametrize(("text", "label"), DOTTED_AND_RUBY_LEAKS)
def test_dotted_names_and_ruby_forms_are_refused(text, label):
    # Kills: the dot in the quoted-name alphabet of _QUOTED_NAME or
    # _KEY_VALUE, ``||=``, ``) {``, the symbol subscript (QG r4 B1, M1) and
    # the ``$`` anchor of the placeholder words (m13) removed.
    assert label in credential_labels(text)
    assert label in credential_labels(json.dumps({"diff": "+" + text}))


@pytest.mark.parametrize("text", DOTTED_AND_RUBY_BENIGN)
def test_dotted_names_and_ruby_forms_without_a_literal_pass(text):
    assert credential_labels(text) == []
    assert credential_labels(json.dumps({"diff": "+" + text})) == []


# --- PR3 QG r5 (finding 47): XML element text, .netrc, ``priv`` ------------

SHORT_TOKEN = F_TOKEN[:11]  # 11 chars: Paulo's reproduction length
# Each row: the text, the label. Every shape was SENT by every layer on the
# round-5 tree (R5-M1): the element text and the netrc token are unquoted.
XML_NETRC_LEAKS = [
    (f"<password>{SHORT_TOKEN}</password>", "credential xml element"),
    (f"<Password>{F_TOKEN}</Password>", "credential xml element"),  # case
    (f"<db:password>{F_TOKEN}</db:password>", "credential xml element"),  # namespace
    (f"<secret>{F_TOKEN}</secret>", "credential xml element"),
    (f"<apiKey>{F_TOKEN}</apiKey>", "credential xml element"),
    (f"<ApiToken>{F_TOKEN}</ApiToken>", "credential xml element"),
    (f'<property name="hibernate.connection.password">{F_TOKEN}</property>',
     "credential xml element"),  # the key in a name= attribute
    (f'<entry key="db.password">{F_TOKEN}</entry>', "credential xml element"),  # key=
    (f"<password><![CDATA[{F_TOKEN}]]></password>", "credential xml element"),
    (f"<password>\n    {F_TOKEN}\n  </password>", "credential xml element"),  # pretty-printed
    (f"<password>\n+    {F_TOKEN}\n+  </password>", "credential xml element"),  # in a diff
    (f"machine api.example.com login me password {F_TOKEN}", "netrc password"),
    (f"default login me password {F_TOKEN}", "netrc password"),
    (f"machine api.example.com\n  login me\n  password {F_TOKEN}\n", "netrc password"),
    (f"  password {F_TOKEN}", "netrc password"),  # the multi-line form's own line
    # Marta's r5 probe: ``priv`` qualifies ``key`` as ``private`` does.
    (f'privKey: "{F_TOKEN}"', "credential key-value"),
]
XML_NETRC_BENIGN = [
    "<password></password>",
    "<password>${DB_PASSWORD}</password>",
    "<password>@db.password@</password>",  # a Maven/Ant filter
    "<password>#{vault.dbPassword}</password>",  # Spring EL
    "<passwordPolicy>strict</passwordPolicy>",
    "<passwordPolicy><minLength>12</minLength></passwordPolicy>",
    '<entry key="timeout">30</entry>',
    "<name>password</name>",
    "<token_url>https://auth.example.invalid/t1</token_url>",  # a pointer word ends the name
    "machine api.example.com login me password $NETRC_PASSWORD",
    "machine api.example.com login me password {netrc_password}",  # a template slot
    'fmt = "  password {user_pw}"',  # a quote ends the token, the slot is left
    "the machine needs a password reset…",
    "Enter the password below",
    'let pubKey = decode("' + SHORT_TOKEN + '");',  # a public key is no secret
    'pubKey: "' + F_TOKEN + '"',
]


@pytest.mark.parametrize(("text", "label"), XML_NETRC_LEAKS)
def test_xml_element_text_and_netrc_passwords_are_refused(text, label):
    # Kills: the element detector, the attribute key, the namespace/case
    # reading, CDATA, the netrc rule (each form), ``priv`` removed (R5-M1).
    assert label in credential_labels(text)
    assert label in credential_labels(json.dumps({"diff": "+" + text + "\n"}))


@pytest.mark.parametrize("text", XML_NETRC_BENIGN)
def test_xml_and_netrc_references_and_prose_pass(text):
    # Kills: the reference skips (``@x@``, ``#{x}``), the netrc token alphabet
    # (the ellipsis), ``pub`` made a qualifier.
    assert credential_labels(text) == []
    assert credential_labels(json.dumps({"diff": "+" + text + "\n"})) == []


def test_marta_priv_key_call_is_refused():
    # Marta r5: ``let privKey = decode("…")`` was SENT; no precise detector
    # reads a call argument, the catch-all does once ``priv`` qualifies ``key``.
    text = 'let privKey = decode("' + SHORT_TOKEN + '");'
    assert credential_labels(text) == [_cred.CATCH_ALL_LABEL]
    assert credential_labels(json.dumps({"diff": "+" + text + "\n"})) == [_cred.CATCH_ALL_LABEL]


# --- PR3 QG r4: the catch-all layer -----------------------------------------

CATCH_ALL = _cred.CATCH_ALL_LABEL

# Shapes no precise detector knows; the catch-all alone refuses each.
CATCH_ALL_LEAKS = [
    'user.resetPassword("' + PLAIN_PW + '")',  # residual 42(a): a setter verb outside the four
    'login("admin", "' + PLAIN_PW + '")  # password',  # 42(a): not the first argument
    'keyring.set_password("svc", "bob", "' + PLAIN_PW + '")',
    'env[f"{prefix}_TOKEN"] = "' + F_TOKEN + '"',  # 42(c): a name built at run time
    'password = """' + PLAIN_PW + '"""',  # 42(f): a triple-quoted literal
    'ENV.fetch("API_TOKEN") do "' + F_TOKEN + '" end',
    'secrets.put(name, "' + F_TOKEN + '")',
    'set_secret(name="x", value="' + F_TOKEN + '")',
    'token ||= "' + F_TOKEN + '"',
    'auth_header = "Basic " + "' + F_TOKEN + '"',
    'String pw = "' + PLAIN_PW + '";',
    'run(env="${DB_DEFAULT:-' + PLAIN_PW + '}")  # the db password',  # a literal default
    # Finding 47: the literal unquoted, a bare token no precise detector reads.
    "ENV API_TOKEN " + F_TOKEN,  # a Dockerfile ENV without ``=``
    "<td>api token</td><td>" + F_TOKEN + "</td>",  # a table cell, ``<``/``>`` delimited
    "set the admin password to " + SHORT_TOKEN,  # prose around a bare value
    "ENV API_TOKEN " + "9f2f7db979a7d557" + "cfc92fa53aca95ba",  # lowercase hex, 20+ chars
]
# Each row kills one guard of the layer (named in the comment).
CATCH_ALL_BENIGN = [
    'logger.info("token rotated", extra={"build": "a1b2c3d4"})',  # 8 chars: _CATCH_MIN 10 -> 8
    'support.auth_phone = "(555)123-4567"',  # no letters: the two-class rule
    '"integrity": "sha512-RZPHBoxXuNnPQO9rvjh5jdkRmVizktkT7TCDkDmQ0W2SwHInKCAV95GRuvdSvA7w4VMwfCjU'
    'iPwDi0ZO6Nfe9A=="',  # ``Pw`` inside the hash: the word must be outside the literal
    'SECRET_WORDS = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL)", re.I)',  # alternation
    'GITHUB = re.compile(r"\\bghp_[A-Za-z0-9]{20,}")  # token',
    '"Read(~/.aws/credentials)",',  # a call-shaped rule, a path in it
    "Every design token must come through `var(--token-name)`.",  # a call
    '-H "Authorization: Bearer $OUTREACH_ACCESS_TOKEN" \\',  # a reference once the scheme goes
    'body: "grant_type=client_credentials",',  # a NAME=name setting
    'expires = self.secret_entry("2099-01-01T00:00:00+00:00")',  # a timestamp
    'bash "$ARKA_OS/mcps/scripts/apply-mcps.sh" --token-ttl 60',  # a path from a variable
    "- Payloads pass `core/egress/policy.evaluate()` first",  # ``pass`` is prose
    'passwordHint: "Use at least 12 characters"',  # whitespace
    'link("…/tokens/Zq9k7k7k7k7")  # token docs',  # outside ASCII: documentation
    'api_key: "sk-your-api-key-here"',
    'tokenUrl: "https://auth.example.invalid/oauth/token"',  # a URL without userinfo
    '"GRAPHIFY_TOKEN": "${GRAPHIFY_TOKEN:-}"',
    "hints = ['tokenHint: \"created_at\"']",  # a quoted value inside the literal
    # m1: the words of a file-path literal name the file (Laravel hash manifest).
    "'/app/Http/Auth/LoginController.php' => 'cc77e6827498680eabf56e7d4c7dab22',",
    # Finding 47, the bare reading: one row per guard.
    "if (!ACCESS_TOKEN && !process.env.ZOOMINFO_USERNAME) {",  # the gate: no digit
    "token rotated in commit 9f2f7db979",  # the gate: a digit alone, under 20 characters
    "pkg/auth v1.2.0 h1:Zq9k7K7k7k7k7k7k7k7k7k7A=",  # a declared hash (go.sum)
    "if (!token) cache[q8Zr2mX7] = 1",  # code: a subscript glued to a name
    "renderSlot({ token: o }, createElementVNode$1)",  # a bundler's ``$1`` suffix
    "the session token is now token_2024_Q3!",  # the value holds the secret word
    'ssh h "export API_TOKEN=\\"\\$UPSTREAM_2\\""',  # an escaped reference, backslash trimmed
    # A bare path next to a hex digest (QG r7, replacing the r5 base64 row
    # that M-B moved to the leak side): its words name the file.
    "./app/Auth/Guard.php  " + "9f2f7db979a7d557" + "cfc92fa53aca95ba",  # a manifest listing
    "9f2f7db979a7d557" + "cfc92fa53aca95ba" + "  ./app/Auth/Guard.php",  # ``sha256sum``
]


@pytest.mark.parametrize("text", CATCH_ALL_LEAKS)
def test_the_catch_all_refuses_a_shape_no_detector_knows(text):
    # Kills: the layer off, ``password`` or ``token`` dropped from its words,
    # the literal default of ``${X:-v}`` dropped with the slot.
    assert credential_labels(text) == [CATCH_ALL]
    assert credential_labels(json.dumps({"diff": "+" + text + "\n"})) == [CATCH_ALL]


@pytest.mark.parametrize("text", CATCH_ALL_BENIGN)
def test_the_catch_all_passes_names_patterns_and_references(text):
    # Kills: _CATCH_MIN 10 -> 8, the two-class rule off, the word read inside
    # the literal, each _NOT_A_SECRET guard dropped.
    assert credential_labels(text) == []
    assert credential_labels(json.dumps({"diff": "+" + text + "\n"})) == []


def test_the_catch_all_reads_a_serialised_state_by_its_leaves():
    # Kills: _catch_units off. As a JSON value a short code line is ONE quoted
    # literal (``"+ds.setPassword(password)"``) beside the ``diff`` key.
    for line in ("ds.setPassword(password)", 'os.environ.get("API_TOKEN", "")'):
        assert credential_labels(json.dumps({"diff": "+" + line})) == []
    pair = json.dumps({"auths": {"r.example.invalid": {"auth": F_TOKEN}}})
    assert credential_labels(pair) != []  # the key names the plain value


# QG PR3 r6: relative paths (a Vite/Laravel ``manifest.json``, a hash
# manifest keyed by a relative path) name files; their words and a hashed
# asset name are not a credential. Values built at runtime.
HEX56 = "cc77e6827498680e" + "abf56e7d4c7dab22" + "9303046e0994daf37f4fce84"
ASSET = "assets/Login-" + "Bk3x9Zq2.js"
SRI = "sha512-" + "RZPHBoxXuNnPQO9rvjh5jdkRmVizktkT7TCDkDmQ0W2S=="
RELATIVE_PATH_BENIGN = [
    '"resources/js/Pages/Auth/Login.vue": {"file": "' + ASSET + '", "src": '
    '"resources/js/Pages/Auth/Login.vue"},',
    '"resources/js/Pages/Auth/ForgotPassword.vue": {"file": "assets/ForgotPassword-'
    + "Dq8sZk2p.js" + '"},',
    '"resources/js/Auth/Login.vue": "' + HEX56 + '"',  # kills: relative path words kept
    "'app/Actions/Auth/AuthenticateCustomer.php' => '" + HEX56 + "',",
    # kills: the hashed asset read as a secret (``name`` is a word outside it)
    '"resources/js/Pages/Auth/Login.vue": {"file": "' + ASSET + '", "name": "auth"},',
    # Controls that were already sent.
    '"resources/js/Pages/Home.vue": "' + SRI + '"', '"file": "' + ASSET + '",',
    '<script integrity="sha384-' + "Ab9x" * 8 + '">',
    '"reference": "' + "9f2f7db979a7d557" + "cfc92fa53aca95ba12345678" + '"',
]
# With every precise detector off these stay refused: a secret holding ``/``
# is no path (a digit interleaved inside a segment, no extension), and a URL
# path without an extension keeps its words.
SLASHED_SECRETS = [
    'token = "ab/Cd12' + 'Xy9Qw7Lp3Zk"', 'auth_token = "q8Zr/2mXv7' + 'Lp/T0wKd9"',
    'token: "ab/Cd12Xy9Qw7/' + 'Lp3Zk.Mn"', 'fetch("api/token/v1", "' + F_TOKEN + '")',
    '"password": "' + DOLLAR_PW + '"',
]


@pytest.mark.parametrize("text", RELATIVE_PATH_BENIGN)
def test_relative_paths_and_hashed_assets_are_not_credentials(text):
    assert egress_secret_labels(text) == []
    assert egress_secret_labels(json.dumps({"diff": "+" + text + "\n"})) == []


@pytest.mark.parametrize("text", SLASHED_SECRETS)
def test_a_secret_holding_a_slash_is_not_read_as_a_path(catch_all_only, text):
    # Kills: a relative-path rule wide enough to swallow base64 or a URL path.
    assert credential_labels(text) == [CATCH_ALL]
    assert credential_labels(json.dumps({"diff": "+" + text + "\n"})) == [CATCH_ALL]


def test_below_the_gate_a_bare_value_is_sent():
    # Residual of finding 46 (round 5), pinned: one letter case with digits,
    # under 20 characters, is below the bare gate, and a Dockerfile ``ENV``
    # without ``=`` reaches no precise detector.
    assert credential_labels("ENV API_TOKEN abc123def456") == []


def test_the_catch_all_runs_only_when_no_detector_fired():
    labels = credential_labels('SECRET_KEY = "' + PLAIN_PW + '9"')
    assert labels == ["credential assignment"]


# The Quality Gate history, rounds 1 to 5, with every precise detector
# switched off: what the catch-all alone refuses. The misses are its
# residual (security review, finding 46), pinned so that a change moves
# the row and the review together; each is refused by a precise detector.
QUOTED_LEAK_FORMS = [v for v in LEAK_FORMS.values() if "'" in v or '"' in v]
N1_AND_30 = [r for r in REVIEWER_LEAKS if "'t " in r or "'s:" in r or '\\"' in r]
CATCH_ALL_HISTORY = [
    *QUOTED_LEAK_FORMS, *N1_AND_30, *(t for t, _ in CODE_DOLLAR_LEAKS), *HEADER_CALL_LEAKS,
    *(t for t, _ in STRING_FORM_LEAKS), *(t for t, _ in QUOTED_NAME_LEAKS),
    *(t for t, _ in DOTTED_AND_RUBY_LEAKS), *(t for t, _ in XML_NETRC_LEAKS),
]
CATCH_ALL_MISSES = {
    # (a) No secret word on the line: the shell auth flags, userinfo, a -p flag (14).
    *(v for v in QUOTED_LEAK_FORMS if not re.search(r"(?i)token|password|authoriz|api_key", v)),
    *(r for r in N1_AND_30 if not re.search(r"(?i)token|authoriz", r)),
    # (b) Whitespace inside the literal: a passphrase.
    LEAK_FORMS["assign-quoted-space"],
    # (c) Under 10 characters once the slots go.
    'token = f"q8Z{a}r2m{b}Xv7"',
    # (d) A quote paired across an apostrophe: the value is inside a literal
    # that holds whitespace, and no bare token is read inside a literal.
    "echo don't -H \"Authorization: Bearer ab$c9Zq9k7k7\" x'",
    # (e) A ``{…}`` run read as a template slot.
    LEAK_FORMS["authhdr-single-brace"],
    # (f) A query credential inside a URL literal (the URL guard).
    LEAK_FORMS["query-single-bracket"],
    # (g) An element value on a line of its own: no secret word on that line.
    f"<password>\n    {F_TOKEN}\n  </password>", f"<password>\n+    {F_TOKEN}\n+  </password>",
}

HISTORY_ROWS, HISTORY_REFUSED = 127, 106  # distinct rows; the misses are the 21 above


@pytest.fixture
def catch_all_only(monkeypatch):
    monkeypatch.setattr(_cred, "_DETECTORS", ())


@pytest.mark.parametrize("text", CATCH_ALL_HISTORY)
def test_the_catch_all_alone_refuses_the_review_history(catch_all_only, text):
    # Kills: the layer off, ``authorization`` or ``token`` dropped from its
    # words, the label split off (``'Authorization: Bearer v'``).
    want = [] if text in CATCH_ALL_MISSES else [CATCH_ALL]
    assert credential_labels(text) == want
    assert credential_labels(json.dumps({"diff": "+" + text + "\n"})) == want


def test_the_catch_all_alone_misses_only_the_documented_residual(catch_all_only):
    rows = set(CATCH_ALL_HISTORY)
    refused = {t for t in rows if credential_labels(t)}
    assert refused == rows - CATCH_ALL_MISSES
    assert (len(rows), len(refused)) == (HISTORY_ROWS, HISTORY_REFUSED)  # finding 46


# The cap step runs on three representative units (QG r5 m2): the worst one
# measured (``escapes``), a plain literal body (``digits``) and the bare
# reading (``bare-tokens``); every unit runs the 4x ratio step.
_AT_THE_CAP = frozenset({"escapes", "digits", "bare-tokens"})


@pytest.mark.parametrize(
    ("head", "body"),
    [('token "', "a1"), ('token "', "[a-"), ('token "', "a."), ('token "', "x("),
     ("token '", '\\"'), ("key ", '"q8Zr2mXv7Lp" '), ('password "', "${a:-"), ("token `", "Pw"),
     ("secret '", "a|"), ('auth "', "{1,"),
     # Finding 47: bare tokens, element tags, netrc windows.
     ("password ", "q8Zr2mX!7Lp "), ("<password>", "<a>"), ("machine ", "login ")],
    ids=["digits", "range", "dots", "call", "escapes", "no-word", "default", "backtick",
         "alternation", "repeat", "bare-tokens", "xml-tags", "netrc-window"],
)
def test_the_catch_all_alone_scans_a_megabyte_in_linear_time(catch_all_only, head, body, request):
    # Kills: the ``[a-`` class and the call guard written with a backtracking
    # run (the first draft took over 5 s on 100 KB), the escaped-quote
    # lookbehind removed. Each form is timed in CPU time, sizes interleaved
    # (``_interleaved``), because the coverage tracer roughly doubles
    # pure-Python time and CI runs under it: an absolute 1 s bound failed
    # there on the 2 MB serialised forms (1.47 s) while the scan stayed linear.
    def forms(size: int) -> list[str]:
        run = head + body * (size // len(body))
        texts = (run, run + head.strip()[-1])  # the literal left open, and closed
        return [form for text in texts for form in (text, json.dumps({"diff": text}))]

    # 4x the text on a small size first: linear ~4x, quadratic ~16x, and a
    # quadratic draft fails here in seconds instead of minutes at 1 MB.
    for small_text, large_text in zip(forms(25_000), forms(100_000), strict=True):
        small, large = _interleaved(small_text, large_text, rounds=3)
        assert large <= 8 * small + 0.05, f"not linear: {small:.3f} s -> {large:.3f} s"
    if request.node.callspec.id not in _AT_THE_CAP:
        return
    # Then at the 1 MB cap (``MAX_SCAN_CHARS``): 2x the text, linear ~2x,
    # quadratic ~4x; and a ceiling (``_CAP_SLOW``) with a margin over the
    # worst form measured under coverage (security review, finding 46).
    for half_text, full_text in zip(forms(_CAP_SIZE // 2), forms(_CAP_SIZE), strict=True):
        half, full = _interleaved(half_text, full_text, rounds=2)  # 3 MB of scan per round
        assert full <= 3 * half + 0.05, f"not linear: {half:.3f} s -> {full:.3f} s"
        assert full <= _ceiling(_CAP_CEILING), f"{len(full_text)} chars {_over(full, _CAP_CEILING)}"


# --- PR3 QG r6 -> round 7: nested <value>, netrc account, path-keyed secrets --

_DOTNET = ('<setting name="ApiSecret" serializeAs="String">\n'
           "    <value>" + F_TOKEN + "</value>\n</setting>")
_SPRING = ('<property name="password">\n        <value>' + F_TOKEN + "</value>\n"
           "    </property>")


def _as_diff(text: str) -> str:
    return "\n".join("+" + line for line in text.splitlines())


# B1: the key sits in the parent's ``name=``, the value in the next ``<value>``.
NESTED_VALUE_LEAKS = [
    _DOTNET, _SPRING, _as_diff(_DOTNET), _as_diff(_SPRING),
    '<property name="db.password"><value>' + F_TOKEN + "</value></property>",  # one line
    '<entry key="api.token">\r\n  <value type="string">' + F_TOKEN + "</value>",  # CRLF, attrs
    "<password>\n  <value><![CDATA[" + F_TOKEN + "]]></value>",  # the tag names it, CDATA
]
NESTED_VALUE_BENIGN = [
    '<property name="username">\n  <value>' + F_TOKEN + "</value>\n</property>",
    '<property name="password">\n  <value>${DB_PASSWORD}</value>\n</property>',
    '<property name="password"/>\n<value>' + F_TOKEN + "</value>",  # self-closed: no child
    '<property name="password">' + " " * 65 + "<value>" + F_TOKEN + "</value>",  # past the gap
    '<property name="passwordPolicy">\n  <value>strict-mode-v2</value>',
]


@pytest.mark.parametrize("text", NESTED_VALUE_LEAKS)
def test_a_nested_value_child_carries_its_parent_key(text):
    # Kills: the carry off (_xml_carry_hit), the diff sign or the serialised
    # ``\n`` out of the gap, the tag name left out of the carried names.
    assert "credential xml element" in credential_labels(text)
    assert "credential xml element" in credential_labels(json.dumps({"diff": text + "\n"}))


@pytest.mark.parametrize("text", NESTED_VALUE_BENIGN)
def test_a_nested_value_without_a_secret_key_or_literal_passes(text):
    assert "credential xml element" not in credential_labels(text)
    assert "credential xml element" not in credential_labels(json.dumps({"diff": text}))


def test_the_nested_value_carry_scans_in_linear_time():
    # Every ``<`` opens a tag whose gap never reaches a ``<value>``, or whose
    # ``<value>`` never closes: bounded per ``<``, 4x the text ~4x the time.
    for unit in ('<s name="password">' + "\\n+ " * 20, '<s key="token"> <value>',
                 '<s name="password"><value>x</value>'):
        small, large = _interleaved(unit * (25_000 // len(unit)), unit * (100_000 // len(unit)))
        assert large <= 8 * small + 0.05, f"not linear: {small:.3f} s -> {large:.3f} s"
        assert large < _ceiling(_SHAPE_SLOW), f"{unit[:20]!r} {_over(large, _SHAPE_SLOW)}"


# B2: netrc(5) defines ``account`` as an additional password.
NETRC_ACCOUNT_LEAKS = [
    "machine h login u account " + F_TOKEN,
    "default login u account " + F_TOKEN,
    "machine h.example.invalid\n  login u\n  account " + F_TOKEN + "\n",
    "+  account " + F_TOKEN,
]
NETRC_ACCOUNT_BENIGN = [
    "account: 'account [info]',",  # a CLI usage string, found by the round-7 sweep
    "account: 'account [credits|countries|currencies]',",
    "machine h login u account $NETRC_ACCOUNT",
    "Pick an account below",
]


@pytest.mark.parametrize("text", NETRC_ACCOUNT_LEAKS)
def test_a_netrc_account_is_refused_as_a_password(text):
    # Kills: ``account`` dropped from either _NETRC pattern.
    assert "netrc password" in credential_labels(text)
    assert "netrc password" in credential_labels(json.dumps({"diff": "+" + text + "\n"}))


@pytest.mark.parametrize("text", NETRC_ACCOUNT_BENIGN)
def test_a_netrc_account_reference_or_usage_passes(text):
    # Kills: the usage-list guard (_NETRC_USAGE) dropped.
    assert credential_labels(text) == []
    assert credential_labels(json.dumps({"diff": "+" + text + "\n"})) == []


# m1: a rule ABOUT a secret is no secret; the secret itself still is.
POLICY_BENIGN = [
    "<passwordPolicy>strict-mode-v2</passwordPolicy>", "passwordPolicy: strict-mode-v2",
    "PASSWORD_POLICY=strict-mode-v2", 'token_expiry: "2099-01-01T00:00:00Z"',
    "password_min_length: 12", "PASSWORD_MAX=64", "secret_rules: strict-v2",
    'password_reset: "enabled-v2"', 'passwordHint: "min-12-chars"',
]
POLICY_STILL_REFUSED = [
    ('password_reset_token = "' + F_TOKEN + '"', "credential assignment"),
    ("PASSWORD_RESET_TOKEN=" + F_TOKEN, "credential assignment"),
    ('resetPassword: "' + F_TOKEN + '"', "credential key-value"),
    ("<policyToken>" + F_TOKEN + "</policyToken>", "credential xml element"),
]


@pytest.mark.parametrize("text", POLICY_BENIGN)
def test_a_policy_about_a_secret_passes(text):
    # Kills: each pointer word (policy, expiry, min, max, rules, reset, hint)
    # and each pointer suffix dropped.
    assert credential_labels(text) == []
    assert credential_labels(json.dumps({"diff": "+" + text + "\n"})) == []


@pytest.mark.parametrize(("text", "label"), POLICY_STILL_REFUSED)
def test_a_secret_named_after_its_policy_is_still_refused(text, label):
    assert label in credential_labels(text)
    assert label in credential_labels(json.dumps({"diff": "+" + text + "\n"}))


# M-B: a secret keyed by a file path (fix-introduces-defect of the round-6
# path-word drop). The words name the value unless it is a hash or a path.
PATH_KEYED_LEAKS = [
    '"auth/secret.key": "' + F_TOKEN + '"',
    '"config/Auth/token.php": "' + F_TOKEN + '"',
    '"/etc/secrets/api.token": "' + F_TOKEN + '"',
    "'auth/secret.key' => '" + F_TOKEN + "',",
    "'config/Auth/token.php' => '" + F_TOKEN + "',",
    "'/etc/secrets/api.token' => '" + F_TOKEN + "',",
    "./app/Auth/Guard.php  Zq9k7K7k7k7k7k7k7k7k7k7A==",  # was benign in r5: base64 is no hash
]


@pytest.mark.parametrize("text", PATH_KEYED_LEAKS)
def test_a_secret_keyed_by_a_file_path_is_refused(text):
    # Kills: the path words dropped whatever the value (the round-6 rule).
    assert credential_labels(text) == [CATCH_ALL]
    assert credential_labels(json.dumps({"diff": "+" + text + "\n"})) == [CATCH_ALL]


@pytest.mark.parametrize("text", PATH_KEYED_LEAKS)
def test_a_path_keyed_secret_is_refused_by_the_catch_all_alone(catch_all_only, text):
    assert credential_labels(json.dumps({"path": "a.php", "diff": "+" + text})) == [CATCH_ALL]


def test_a_path_keyed_hex_digest_is_the_documented_residual():
    # Residual (i), pinned: a hex value of 32+ characters after a path is read
    # as a hash manifest, so a hex secret keyed by a path is sent.
    hex_secret = "9f2f7db979a7d557" + "cfc92fa53aca95ba"
    assert credential_labels('"auth/secret.key": "' + hex_secret + '"') == []


# m2: a standard base64 key cut at ``/`` and ``+`` is no name.
AWS_DOC_KEY = "wJalrXUtnFEMI/" + "K7MDENG/bPxRfiCY" + "EXAMPLEKEY"


def test_a_slashed_base64_key_is_not_read_as_a_name(catch_all_only):
    # Kills: _CATCH_NAME_VALUE replaced by _CATCH_NAME (Francisca r6 m2).
    assert credential_labels('Settings::SECRET << "' + AWS_DOC_KEY + '"') == [CATCH_ALL]
    assert credential_labels('secret = get_secret("prod/db-password-2024")') == []


def test_random_base64_keys_miss_only_the_documented_residual(catch_all_only):
    # Residual (h), pinned by category on a fixed seed: 34 of 2000 open on
    # ``/`` (read as a path), 3 hold no ``/`` or ``+`` and one digit run
    # (read as a name), 2 have no digit (the two-class rule).
    import random
    import string

    rng, alphabet = random.Random(7), string.ascii_letters + string.digits + "+/"
    misses: dict[str, int] = {}
    for _ in range(2000):
        key = "".join(rng.choice(alphabet) for _ in range(40))
        if not credential_labels('Settings::SECRET << "' + key + '"'):
            why = ("slash" if key[0] == "/" else "name" if _cred._CATCH_NAME_VALUE.match(key)
                   else "two-class")
            misses[why] = misses.get(why, 0) + 1
    assert misses == {"slash": 34, "name": 3, "two-class": 2}


# Stripe (QG PR3 r6 M-A, scoped into the PR by the operator).
STRIPE_LIVE = "sk_" + "live_" + "51Hq8Zr2mXv7LpT0wKd9Qx"
STRIPE_LEAKS = [
    'const stripe = new Stripe("' + STRIPE_LIVE + '");',
    "curl https://api.stripe.com/v1/charges -u " + STRIPE_LIVE + ":",
    "rk_" + "live_" + "51Hq8Zr2mXv7LpT0wKd9Qx", "sk_" + "test_" + "51Hq8Zr2mXv7LpT0wKd9Qx",
    "rk_" + "test_" + "51Hq8Zr2mXv7LpT0wKd9Qx", "whsec_" + "q8Zr2mXv7LpT0wKd9Qx4Nb",
]


@pytest.mark.parametrize("text", STRIPE_LEAKS)
def test_stripe_keys_are_refused_by_the_vendor_vocabulary(text):
    labels = egress_secret_labels(text)
    assert {"Stripe key", "Stripe webhook secret"} & set(labels)
    assert egress_secret_labels(json.dumps({"diff": "+" + text + "\n"})) == labels
