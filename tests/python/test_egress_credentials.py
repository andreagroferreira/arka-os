"""core.egress.credentials — context-marked credentials the prefix list misses.

Fixture values are built at runtime from synthetic fragments, so no
literal credential lives in the repo and the evidence engine's own
security-grep never fires on this file.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

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
    'bash -c "ssh h \\"export API_TOKEN=\\\\\\"abc123XYZ99\\\\\\"\\""',
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


def _curl_paste(lines: int) -> str:
    return "".join(
        f'curl -sS -H "Authorization: Bearer $TOKEN" "https://api.example.com/v1/items/{i}'
        '?page=1" | jq .\n'
        for i in range(lines)
    )


def _timed(text: str) -> float:
    """Best of 3 runs of the detector; stops early once a run is clearly slow."""
    from time import perf_counter

    best = float("inf")
    for _ in range(3):
        began = perf_counter()
        credential_labels(text)
        best = min(best, perf_counter() - began)
        if best > 2 * _SLOW:
            break
    return best


def test_serialised_many_match_paste_scans_in_linear_time():
    # Kills: the round-5 ``_local`` (O(line) per match), 15x over the bound.
    small = _timed(json.dumps({"prompt": _curl_paste(1000)}))  # ~100 KB
    large = _timed(json.dumps({"prompt": _curl_paste(2000)}))  # ~200 KB
    assert large <= _SLOW, f"200 KB serialised paste took {large:.2f} s"
    assert large <= 3 * small + 0.05, f"not linear: {small:.3f} s -> {large:.3f} s"


@pytest.mark.parametrize(
    ("unit", "quote", "size"),
    [("'a' \"-u x:y\" ", "", 100_000), ("-u a:$(x) ", "'", 300_000), ("mysql x ", "", 100_000),
     ("http x ", "", 100_000), ("redis-cli x ", "", 100_000), ("docker login x ", "", 100_000),
     ("a.", "", 100_000), ("a-", "", 100_000)],
    ids=["quotes", "one-quoted-span", "mysql", "httpie", "redis", "docker", "dotted", "dashed"],
)
def test_adversarial_text_scans_under_a_second(unit, quote, size):
    # Kills: the round-5 ``_local`` (quotes), a value read without its cap
    # (one-quoted-span: every reference value runs to the far quote, so no
    # match short-circuits the scan), an unbounded tool-argument window
    # (mysql .. docker), an unbounded userinfo scheme (dotted, dashed).
    text = f"{quote} " + unit * (size // len(unit)) + quote
    for form in (text, json.dumps({"prompt": text})):
        took = _timed(form)
        assert took < _SLOW, f"{len(form)} chars took {took:.2f} s"


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
