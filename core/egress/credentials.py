"""Credentials by CONTEXT, not by vendor prefix — the command-line shapes.

``harness_scanner.secret_labels`` knows vendor-prefixed keys (``sk-ant-``,
``AKIA``, ``xoxb-`` ...). A shell command carries credentials that have no
prefix at all, and the PR2 security probe sent every one of these in
clear through ``prepare_state``: ``export API_TOKEN=<opaque>``,
``curl -H 'Authorization: Bearer <opaque>'``, ``mysql -p<password>``,
``https://user:<password>@host``, ``PGPASSWORD=<opaque> psql``.

What marks them is the SURROUNDING syntax: a secret-named variable, an
auth header, a password flag or positional CLI password (mysql -p,
docker login -p, redis-cli -a, aws configure set), URL userinfo, a
credential in a query string, httpie ``-a``/``--auth``. Quality Gate
PR2 r1 (B2), r2 (B3, M1) and r3 (M2) shaped the rules below.

Each detector requires that context AND a value that is literal: not a
shell expansion, not a placeholder (``<token>``, ``xxx``, ``your-key``)
and, for assignments and flags, not a path, a URL or code. Assignment,
flag and header values must also look like a token (a digit, a symbol
other than a space, or 20+ characters): ``SORT_KEY=created_at`` and
``grep "X-Api-Key: missing header"`` are prose.

Quote context decides both where a value ends and what counts as an
expansion (QG PR2 r3 M2). ``_quote_context`` walks the text once, the
way a POSIX shell reads quotes. A value that starts inside quotes runs
to the closing quote, so a ``;`` or ``]`` inside ``'admin:ab;c]d'`` is
part of the password. A bare value ends at the first whitespace, quote
or shell metacharacter (``; & | ( ) < > ,`` and backtick), so
``TOKEN=v; next`` yields ``v`` (QG PR2 r2 B3). An unmatched apostrophe
in prose (``can't``) flips that whole-text reading, so the sub-token
detectors also read the value under the quote that opens its own word,
and refuse when EITHER reading is literal (QG PR2 r4 N1). Escaped quotes
(``ssh h "T=\\"v\\""``) are read on every un-escaped layer. What we reject as
"not the literal secret", and why:

* ``$`` or a backtick in a bare or double-quoted value: parameter or
  command substitution, the text is a reference to the secret, not the
  secret. Inside single quotes nothing is substituted, so a ``$`` there
  is data (``'admin:Pa$$w0rd'``); only a value that is NOTHING but a
  reference (``'Bearer $TOKEN'``) is still rejected, since what ships is
  the name, not a secret.
* ``[ ] { }`` are NOT rejected: a lone ``}`` is not brace expansion and
  an unmatched glob stays literal. The only bracket rule is the code
  guard of assignments and flags: a bare value shaped like
  ``name[...]`` or ``name{...}`` running to its end (``cfg[k1]``,
  ``request.form[``) is code in a diff, not a credential.

URL userinfo is bounded by ``:`` and ``@``, not by shell syntax, so a
``;`` inside a password there is part of it.

Source code carries the same credentials in its own syntax (security
review PR3, finding 33): the ``diff`` states of the Quality Gate and the
``ui-in-ts`` payload are code, not shell. So the assignment detector also
reads a type annotation (``API_KEY: str = "v"``, ``const apiKey: string =
"v"``), a key/value detector reads ``apiKey: "v"`` (JS/TS/YAML/Ruby/Go),
``"api_key": "v"`` (JSON) and ``'api_key' => 'v'`` (PHP), and the auth
header accepts a quoted key and value (``{"Authorization": "Bearer v"}``,
``Authorization: `Bearer v```). A key/value value holding whitespace is
prose (an i18n label, a hint), not a token, once an auth scheme prefix is
set aside. A PEM private key is refused on its END line too: a diff cut
into chunks can put the key body and ``-----END ... PRIVATE KEY-----`` in
a chunk that has no BEGIN line (finding 34).

A string literal of source code is not a shell word (finding 38): JSON,
JS, YAML and Python substitute nothing inside ``'...'`` or ``"..."``, so
a ``$`` there is data (``{"password": "Tr0ub4dor$3xYz"}``). Such values
are read as ``_CODE``: only a value that is nothing but a reference
(``"${DB_PASSWORD}"``, ``"$TOKEN"``) is exempt, a backtick template
drops its ``${...}`` slots and is judged on the rest, and a bare value
that starts with ``$`` is a variable (``'password' => $pw``). That holds
for key/value values, for the auth header in its code forms (a quoted
key, a quoted value, or a call argument ``set("Authorization", "...")``,
finding 39) and for an assignment written as code: a type annotation or
spaces around ``=`` (``password = "..."``); ``TOKEN="a$b"`` with no
spaces is still read as shell. A quoted ``"Bearer <opaque>"`` string is
refused on its own, whatever the header key looks like (finding 39).

Code also writes a literal with a prefix and binds it in other ways
(finding 41): ``b"..."``, ``r'...'``, ``rb"..."``, ``f"..."`` (whose
``{...}`` slots are dropped, as a template's are), a keyword argument
(``connect(host=h, password="...")``), Go's ``password := "..."`` and
``var password string = "..."``. Each is read as ``_CODE``. A template
is judged on its literal runs joined (QG PR3 r3 m10: ``f"q8Z{a}r2m{b}Xv7"``
hides no secret in slots), and a run ending in ``=`` or ``:`` labels the
slot after it (``f"TOKEN={tok}"``), it is not a value.
``${NAME:-}``, ``${NAME:?msg}`` and ``${NAME:-$OTHER}`` are references;
a literal default (``${PW:-<opaque>}``) is a hardcoded password.

Code also NAMES a secret inside a quoted string (finding 42): a subscript
(``os.environ["API_TOKEN"] = "v"``, ``$config['encryption_key'] = 'v'``),
a positional argument (WordPress ``define('AUTH_KEY', 'v')``,
``os.environ.setdefault("DB_PASSWORD", "v")``, ``os.getenv("PW", "v")``),
a .NET ``<add key="ApiKey" value="v" />``, a setter whose name is the
secret (``ds.setPassword("v")``, ``builder.password("v")``) and a user and
password pair (``auth=("admin", "v")``, ``HTTPBasicAuth(user, "v")``).
Each value is a string literal, judged as a key/value value.

A quoted name may hold dots (``Config::set("services.stripe.secret",
"v")``, ``"db.password": "v"``), and Ruby binds a name with ``||=``, a
symbol subscript (``config[:api_key] = "v"``) and a fetch block
(``ENV.fetch("NAME") { "v" }``) (QG PR3 r4 B1, M1).

Config files hold credentials outside any string literal (QG PR3 r5,
finding 47): XML element text (``<password>v</password>``, a key in a
``name=``/``key=`` attribute, CDATA, a namespace, and since r6 the
``<value>`` child of such a tag) and ``.netrc`` (``machine h login u
password v``, or a ``password v`` line; ``account`` too). Both are judged
as key/value values. Since QG PR3 r7 a config file never reaches these
detectors as a ``diff`` state: ``decisions.privacy`` sends a diff only for
an allowlisted source suffix, and the detectors are defence in depth.

Behind the precise detectors sits a catch-all layer (QG PR3 r4, finding
46): a line holding a secret word and a secret-looking literal, quoted or
(r5) a bare token, is refused, whatever syntax binds them. It fires only
when no precise detector did; see the comment above ``CATCH_ALL_LABEL``.

A false positive denies one egress (the caller falls back to its
heuristic); a false negative ships a password to a third party — the
patterns lean to the deny side on purpose. Regex detection cannot prove
absence: the residual is bounded by the probe set in
``tests/python/test_egress_credentials.py``.

Labels, never values, leave this module: the policy hashes the label
into the audit, exactly as it does for ``secret_labels``.
"""

from __future__ import annotations

import json
import re
from bisect import bisect_left
from collections.abc import Callable, Iterable
from functools import lru_cache
from typing import NamedTuple

from core.governance.harness_scanner import secret_labels

# PASS covers PASSWORD/PASSWD/PASSPHRASE and the bare DB_PASS/PASS (QG PR2
# r1 B2d); PWD covers MYSQL_PWD. A path value (PWD=/x) is ruled out below.
_SECRET_WORD = r"(?:KEY|TOKEN|SECRET|PASS|PWD|CREDENTIAL)"
# Suffixes naming a pointer TO a secret (same idea as harness_scanner).
_POINTER_SUFFIX = re.compile(
    r"(?:_FILE|_PATH|_HELPER|_CMD|_COMMAND|_DIR|_ID|_NAME|_URL|_URI|_HOST|_ENDPOINT"
    r"|_POLICY|_RESET|_RULES?|_HINT|_EXPIRY|_MIN|_MAX)$",
    re.I,
)
_PLACEHOLDER = re.compile(
    r"^(?:<[^>]*>|x{3,}|\*{3,}|\.{3}|your[-_ ]|changeme|example|redacted|placeholder"
    r"|(?:password|secret|token|pass)$)",
    re.I,
)
# Substitution markers outside single quotes (see the module docstring).
_EXPANSION = re.compile(r"[$`]")
# Code guard for BARE assignment/flag values: one identifier followed by a
# single bracket group that runs to the end of the value.
_CODE_SHAPE = re.compile(r"^[A-Za-z_][\w.]*(?:\[[^\]]*\]?|\{[^}]*\}?)$")
# Inside single quotes nothing is substituted, but a value that is ONLY a
# reference ('Bearer $TOKEN') ships the name, not a secret.
# ``${NAME:-}``, ``${NAME:?msg}`` and ``${NAME:-$OTHER}`` are references too
# (QG PR3 r2 m7): the default is empty, a message or another name. A literal
# default (``${PW:-<opaque>}``) is a hardcoded password and stays refused.
_PARAM_DEFAULT = r"(?::?(?:\?[^{}]*|[-=+](?:\$[A-Za-z_]\w*|\$\{[A-Za-z_]\w*\})?))"
_WHOLE_REFERENCE = re.compile(
    r"^(?:\$\{?[A-Za-z_]\w*\}?|\$\{[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+\}"
    rf"|\$\{{[A-Za-z_]\w*{_PARAM_DEFAULT}\}}|\$\(.*\)?|`.*`?)$"
)
# _CODE: a source-code string literal (finding 38). Like single quotes,
# nothing is substituted in it; only a whole reference is exempt.
_NONE, _SINGLE, _DOUBLE, _CODE = 0, 1, 2, 3
_NO_SUBSTITUTION = (_SINGLE, _CODE)
# A ``${...}`` slot of a JS template literal, a ``{...}`` slot of an f-string.
_TEMPLATE_SLOT = re.compile(r"\$\{[^{}\n]*\}")
_FSTRING_SLOT = re.compile(r"\{[^{}\n]*\}")
# A string-literal prefix (``b"..."``, ``r'...'``, ``f"..."``, ``rb"..."``,
# QG PR3 r2 B1). Outside the ``value`` group, so ``_value`` still unwraps
# the quotes; a prefixed literal is source code, never a shell word.
_STR_PREFIX = r"""(?:(?P<pfx>[rRbBuUfF]{1,2})(?=['"]))?"""


class _Val(NamedTuple):
    text: str
    quoting: int  # _NONE | _SINGLE | _DOUBLE | _CODE
    wrapped: bool  # written as '...' or "..." (the value is the whole word)
    capped: bool = False  # read stopped at _VALUE_CAP, not at its own end
# A path, or a URL: credentials INSIDE a URL are the userinfo and query
# detectors' job, so a URL value alone does not make an assignment secret.
_PATHLIKE = re.compile(r"^(?:[~/.]|[A-Za-z]:[\\/]|[a-z][a-z0-9+.\-]*://)", re.I)
# A bare value stops at whitespace, quotes and shell metacharacters. The
# group is atomic so the regex cannot back off a character to dodge the
# call guard below.
_STOP = r"""\s'"`;&|()<>,"""
_BARE = rf"(?>[^{_STOP}]+)"
# Quoted values may hold spaces and separators: inside quotes they are data.
# ``(?![(\[])`` after a bare value: ``fn(x)`` / ``cfg[k]`` is code, not a
# literal (``api_key = compute_key2(x)`` in a diff).
_VALUE = rf"""(?P<value>'[^'\n]*'|"[^"\n]*"|{_BARE}(?![(\[]))"""

# An optional type annotation between the name and ``=`` (PR3 finding 33):
# ``API_KEY: str = "v"``, ``apiKey: string = "v"``. Bounded and lazy, so a
# long run after a colon costs at most 48 steps per name.
# Go and Swift put the type after the name, behind ``var``/``const`` (QG
# PR3 r2 B1): ``var password string = "v"``; that form needs the keyword,
# so prose ("the api key value = x") stays out.
_ANNOTATION = (
    r"(?P<ann>\s*:\s*[A-Za-z_][\w.\[\], |]{0,48}?"
    r"|(?(var)\s+[A-Za-z_*\[][\w.\[\]*]{0,48}?|(?!)))?"
)
_ASSIGNMENT = re.compile(
    # Zero or more chars before the word: a bare TOKEN= / KEY= / export
    # token= is a credential too (QG PR2 r1 B2a); the lookbehind keeps the
    # match at the start of the identifier. ``:=`` is Go's (QG PR3 r2 B1).
    rf"(?:\b(?P<var>var|const)\s+)?"
    # The name is read atomically, and a lazy lookahead finds the secret word
    # in it (finding 43): ``[A-Za-z0-9_]*WORD[A-Za-z0-9_]*`` backtracked over
    # every occurrence of the word, quadratic on ``tokentoken...``.
    rf"(?<![\w-])(?P<name>(?=[A-Za-z0-9_]*?{_SECRET_WORD})(?>[A-Za-z0-9_]+)){_ANNOTATION}"
    rf"\s*:?=\s*{_STR_PREFIX}{_VALUE}",
    re.I,
)
# A keyword argument (``connect(host=h, password="v")``, QG PR3 r2 B1): the
# name follows ``(`` or ``,`` on its line, or the value is followed by one.
_CALL_BEFORE = re.compile(r"[(,][ \t]*\Z")
_CALL_AFTER = re.compile(r"""['"][ \t]*[,)]""")
# Source-code key/value (PR3 finding 33). The key is read atomically and
# judged by its words afterwards (``_secret_key_name``), so a long
# identifier costs one pass. A bare value also stops at brackets and
# braces: ``{api_key}`` is a template, ``x[:4]`` and ``{..., k: v}`` code.
_KV_BARE = rf"(?>[^{_STOP}\[\]{{}}]+)"
_KV_VALUE = rf"""(?P<value>'[^'\n]*'|"[^"\n]*"|`[^`\n]*`|{_KV_BARE}(?![(\[]))"""
# A quoted key may hold dots (``"db.password": "v"``, ``'stripe.secret' =>
# 'v'``, QG PR3 r4 B1); a bare one may not, so ``cfg.token: v`` stays the
# ``token: v`` it was. The quote group is optional, not empty-matching: an
# empty match still counts as matched for ``(?(q)...)``, and a bare dotted
# name read to its end at every ``.`` is quadratic (``a.a.a...``).
_KEY_VALUE = re.compile(
    rf"""(?<![\w-])(?P<q>["'`])?(?P<name>(?(q)(?>[A-Za-z0-9_.-]+)|(?>[A-Za-z0-9_-]+)))"""
    rf"""(?(q)(?P=q))\s*(?::|=>)\s*{_STR_PREFIX}{_KV_VALUE}"""
)
# A secret NAMED inside a quoted string (finding 42): ``"NAME"`` then ``] =``
# (a subscript; also ``==``/``!=`` and Ruby's ``||=``), ``,`` (a positional
# argument), ``value=`` (.NET appSettings) or ``) {`` (Ruby's
# ``ENV.fetch("NAME") { "v" }``), then a string literal. The name may hold
# dots: a Laravel config key, a Java system property (QG PR3 r4 B1). The
# value's quote may open the next name (``f("a", "API_TOKEN", "v")``): the
# scan resumes there (``_quoted_name_hit``).
_LITERAL = r"""(?P<value>'[^'\n]*'|"[^"\n]*"|`[^`\n]*`)"""
_QUOTED_NAME = re.compile(
    r"""(?P<q>["'])(?P<name>(?>[A-Za-z0-9_.-]+))(?P=q)\s*"""
    r"(?:\]\s*(?:\|\||[!=])?={1,2}|,|\s+value\s*=|\)\s*\{)"
    rf"\s*{_STR_PREFIX}{_LITERAL}"
)
# A Ruby symbol subscript (``config[:api_key] = "v"``, ``||=``; QG PR3 r4 M1).
_SYMBOL_SUBSCRIPT = re.compile(
    rf"\[\s*:(?P<name>[A-Za-z_](?>\w*))\s*\]\s*(?:\|\||[!=])?={{1,2}}\s*{_STR_PREFIX}{_LITERAL}"
)
# A setter or builder call whose first argument is a literal
# (``ds.setPassword("v")``, ``builder.password("v")``, ``withApiKey("v")``).
# Only a setter verb, or the secret word alone, names a value being SET:
# ``get_secret("prod/db-2")`` looks one up by its name. The lookbehind starts
# the name at the start of an identifier, so the scan stays linear.
_SETTER_CALL = re.compile(rf"(?<![\w$])(?P<name>[A-Za-z_](?>\w*))\(\s*{_STR_PREFIX}{_LITERAL}")
_SETTER_VERBS = frozenset({"set", "with", "use", "put"})
# A user and password pair: ``auth=("admin", "v")``, ``auth = [user, "v"]``,
# ``HTTPBasicAuth(user, "v")``, ``HTTPDigestAuth("u", "v")``. The user may be
# a name; the password is a literal.
_AUTH_PAIR = re.compile(
    r"""(?:\bauth\s*=\s*(?:\w{0,32}Auth\s*)?|\b\w{0,32}(?:Basic|Digest)Auth\s*)[(\[]\s*"""
    r"""(?:'[^'\n]*'|"[^"\n]*"|[A-Za-z_][\w.]{0,64})\s*,\s*"""
    rf"{_STR_PREFIX}{_LITERAL}\s*[)\]]"
)
# The words of an identifier: ``apiKey`` → api, key; ``DB_PASSWORD`` → db,
# password; ``APIKey`` → api, key.
_WORDS = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+")
_SECRET_WORDS = frozenset({
    "token", "secret", "password", "passwd", "passphrase", "pass", "pwd",
    "credential", "credentials", "apikey", "secretkey", "privatekey", "accesskey",
    "pw",  # os.getenv("PW", "v"), finding 42
})
# ``key`` alone is a map key, a sort key, a React key: it names a secret
# only after one of these words (``api_key``, ``privateKey``, ``MASTER_KEY``).
_KEY_QUALIFIERS = frozenset({
    "api", "access", "secret", "private", "master", "signing", "encryption", "client",
    "app", "auth", "session", "jwt", "hmac", "webhook", "license", "service", "account",
    "admin", "deploy", "subscription",
    "priv",  # ``privKey`` (QG PR3 r5); ``pub`` is not here: a public key is no secret
})
_POINTER_WORDS = frozenset({
    "id", "ids", "name", "url", "uri", "path", "file", "dir", "host", "endpoint",
    "helper", "cmd", "command", "type", "length", "count", "field", "label",
    # A rule ABOUT a secret (QG PR3 r6 m1): ``passwordPolicy``, ``token_expiry``.
    "policy", "reset", "rule", "rules", "hint", "expiry", "min", "max",
})
# Bare key/value values that are code or data, not a credential:
# ``process.env.DB_PASSWORD``, ``this.token``, ``max_tokens: 128000``,
# ``os.environ/GATEWAY_KEY`` and ``API_TOKEN_REF`` (a name, not a value).
_MEMBER = re.compile(r"^[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)+(?:\\[nrt])*$")
# A trailing JSON escape (``\n`` of a serialised line) is not part of it.
_NUMBER = re.compile(r"^[+-]?\d[\d_]*(?:\.\d+)?(?:\\[nrt])*$")
_ENV_NAME = re.compile(r"^(?:os\.environ/|env:)?_?[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+(?:\\[nrt])*$")
# A value made of placeholder words and nothing else (``your_token_here``,
# ``sk-example-key``, ``token_here_placeholder``). The WHOLE value must be
# such words (QG PR3 r3 m12): ``<opaque>-example-<opaque>`` is a token that
# holds a word, not documentation. A letters-only prefix of up to five
# (``sk-``) and trailing digits per word (``here1``) carry no secret; each
# word is atomic, so the run is linear.
_PLACEHOLDER_WORDS = (
    r"^(?:[A-Za-z]{1,5}[-_])?(?:(?>placeholder|example|sample|dummy|fake|redacted|changeme"
    r"|your|here|goes|my|the|user|app|client|live|test|prod|dev|private|public|service"
    r"|account|token|secret|password|key|api|access|auth|bearer|jwt|value"
    r"|x{3,})\d*[-_.]?)+$"
)
# Documentation placeholders: ``"{api_key}"``, ``"{{ token }}"``, a
# ``%(SECRET)s`` format slot (QG PR3 r2 m8), placeholder words, an address
# at a domain reserved for documentation (RFC 2606: ``user@example.com``).
_KV_PLACEHOLDER = re.compile(
    r"^\{\{?[^{}]*\}\}?$|^%\([\w.-]+\)[sdr]$"
    r"|^[^\s@]+@(?:[\w-]+\.)*(?:example(?:\.(?:com|org|net))?|invalid|test)$|"
    + _PLACEHOLDER_WORDS,
    re.I,
)
# The same words as a quoted bearer string: ``"Bearer token_here_placeholder"``
# is documentation, not a token (QG PR3 r2 m8).
_BEARER_PLACEHOLDER = re.compile(_PLACEHOLDER_WORDS, re.I)
# A bare value that is a variable, or the ``-$OTHER`` default of a
# ``${NAME:-$OTHER}`` the scan resumed inside (QG PR3 r2 m7).
_BARE_VARIABLE = re.compile(r"[-=+?]?\$")
_AUTH_SCHEME = re.compile(r"^(?:bearer|basic|token|digest|apikey)\s+", re.I)
_PEM_TAIL = re.compile(r"-----END [A-Z ]*PRIVATE KEY-----")
_FLAG = re.compile(
    rf"(?<![\w-])--(?:[a-z0-9]+-)*(?:password|passwd|token|secret|api-?key|access-key)"
    rf"(?:=|\s+){_VALUE}",
    re.I,
)
_AUTH_HEADER = re.compile(
    # A quoted key and an opening quote or backtick before the value are
    # source code (``{"Authorization": "Bearer v"}``, PR3 finding 33); so
    # is a quoted key followed by a comma, a call argument
    # (``headers.set("Authorization", "Bearer v")``, finding 39).
    r"""\b(?:proxy-)?authorization(?P<kq>["'`])?"""
    r"""(?:\s*(?::|=>)|(?(kq)\s*,|(?!)))\s*(?P<vq>["'`]?)"""
    r"(?:(?:bearer|basic|token|digest|apikey)\s+)?"
    # The scheme word alone is never the value: ``"Bearer " + token`` has
    # none (``Token token=v`` still reads ``token=v``).
    rf"(?!(?:bearer|basic|token|digest|apikey)(?:[{_STOP}]|$))"
    rf"(?P<value>{_BARE})",
    re.I,
)
# A quoted ``"Bearer <opaque>"`` string, whatever names its header
# (``headers[AUTH] = "Bearer v"``, finding 39). The token alphabet has no
# ``$``, so ``"Bearer $TOKEN"`` never matches; the run is atomic, linear.
_QUOTED_BEARER = re.compile(
    r"""["'`](?:bearer|token|basic)\s+(?P<value>(?>[A-Za-z0-9._~+/=-]{16,}))["'`]""", re.I
)
_KEY_HEADER = re.compile(
    r"\b(?:x-api-key|api-key|x-auth-token|x-access-token|private-token)\s*:\s*"
    rf"(?P<value>{_BARE})",
    re.I,
)
# The arguments between a tool's name and its password flag, on one command.
# Bounded (QG PR2 r5 B1): unbounded, every "mysql" in a JSON-serialised
# state (one line) scanned the rest of the text, quadratic in its length.
_ARGS = r"[^\n|;&]{0,512}?"
_USER_PASS = rf"""['"]?[^\s:'"]+:(?P<value>{_BARE})"""
_BASIC_FLAGS: tuple[re.Pattern[str], ...] = (
    re.compile(rf"(?<![\w-])(?:-u|--user)\s+{_USER_PASS}"),
    # httpie / xh (QG PR2 r2 M1): -a / --auth only after the tool's name,
    # so ls -a and git commit -a stay out.
    re.compile(rf"\b(?:http|https|xh|xhs)\s+(?:{_ARGS}\s)?(?:-a|--auth)(?:=|\s+){_USER_PASS}"),
)
# CLI arguments that carry a password positionally, each with one
# ``value`` group; quoted values (-p'pw', -p"pw") count (QG PR2 r1 B2c).
_PASSWORD_FLAGS: tuple[re.Pattern[str], ...] = (
    re.compile(rf"\b(?:mysql|mysqldump|mysqladmin|mariadb(?:-dump)?)\b{_ARGS}\s-p{_VALUE}"),
    re.compile(rf"\bsshpass\s+-p\s*{_VALUE}"),
    re.compile(rf"\b(?:docker|podman|nerdctl)\s+login\b{_ARGS}\s-p\s+{_VALUE}"),
    re.compile(rf"\bredis-cli\b{_ARGS}\s-a\s*{_VALUE}"),
)
_CLI_SETTING = re.compile(
    r"\baws\s+configure\s+set\s+(?:[\w.-]*\.)?(?:aws_secret_access_key|aws_session_token)"
    rf"\s+{_VALUE}",
    re.I,
)
_QUERY = re.compile(
    r"[?&](?:access_token|refresh_token|id_token|client_secret|api_?key|token|key"
    r"|password|passwd|pwd|secret|sig|signature|auth)="
    rf"(?P<value>(?>[^{_STOP}#]+))",
    re.I,
)
# The password runs to the LAST ``@`` of the authority (it ends at ``/ ? #``):
# RFC 3986 wants a literal ``@`` in userinfo percent-encoded, but a typed
# ``p@ss`` is the password all the same (QG PR2 r4 m3). The scheme is
# bounded and needs no word boundary (QG PR2 r5 B1): ``\b[a-z][...]*``
# started at every letter after a ``.`` or ``-`` and scanned the rest of
# the run, quadratic on a url-safe base64 blob; a longer scheme still
# matches on its last 63 characters.
_USERINFO = re.compile(
    r"[a-z][a-z0-9+.\-]{0,62}://[^\s/:@'\"]+:(?P<value>[^\s/?#'\"]+)@",
    re.I,
)
_MIN_VALUE = 6
# How far past the regex match a quoted value is read (QG PR2 r5 B1): the
# read stops at ``start + floor + _VALUE_CAP`` (PR2 round-6 m2).
_VALUE_CAP = 256
# Where a value inside double quotes stops (see ``_extend``).
_DOUBLE_STOPS = " \t\n'\"\\"
# One level of shell/JSON quote escaping: \" \' \\ -> " ' \.
_UNESCAPE = re.compile(r"\\([\"'\\])")


def _quote_context(text: str) -> bytearray:
    """Per character: 0 outside quotes, 1 inside '...', 2 inside "...".

    The quote characters themselves are 0. A backslash escapes the next
    character outside quotes and inside double quotes, never inside
    single quotes, as in a POSIX shell.
    """
    ctx = bytearray(len(text))
    state, i = _NONE, 0
    while i < len(text):
        ch = text[i]
        if state == _SINGLE:
            if ch == "'":
                state = _NONE
            else:
                ctx[i] = _SINGLE
        elif ch == "\\":
            ctx[i : i + 2] = bytes([state]) * len(ctx[i : i + 2])
            i += 1
        elif ch == '"':
            state = _NONE if state == _DOUBLE else _DOUBLE
        elif ch == "'" and state == _NONE:
            state = _SINGLE
        else:
            ctx[i] = state
        i += 1
    return ctx


class _Scan(NamedTuple):
    """One text layer, indexed once so each match costs O(log n + value)."""

    text: str
    ctx: bytearray
    marks: dict[str, list[int]]  # sorted positions of ' " and newline


def _scan(text: str) -> _Scan:
    marks = {c: [m.start() for m in re.finditer(re.escape(c), text)] for c in "'\"\n"}
    return _Scan(text, _quote_context(text), marks)


def _prev(marks: list[int], pos: int) -> int:
    """The last mark before ``pos``, or -1."""
    i = bisect_left(marks, pos)
    return marks[i - 1] if i else -1


def _next(marks: list[int], pos: int, default: int) -> int:
    """The first mark at or after ``pos``, or ``default``."""
    i = bisect_left(marks, pos)
    return marks[i] if i < len(marks) else default


@lru_cache(maxsize=16)
def _stops(chars: str) -> re.Pattern[str]:
    return re.compile("[" + re.escape(chars) + "]")


def _first(text: str, chars: str, pos: int, endpos: int) -> int:
    """Index of the first of ``chars`` in ``text[pos:endpos]``, else ``endpos``."""
    m = _stops(chars).search(text, pos, endpos)
    return m.start() if m else endpos


def _value(scan: _Scan, m: re.Match[str], extend: str | None = None) -> _Val:
    """The matched value, read with the whole-text quote context.

    A value written as '...' or "..." is unwrapped. For the sub-token
    detectors (``extend`` is not None), a value that STARTS inside quotes
    (``bob:pw`` in ``-u 'bob:pw'``) runs on to the closing quote, since
    inside quotes the shell separators are data. Inside double quotes it
    also stops at whitespace, quotes and backslashes: a JSON-serialised
    state wraps the whole command in double quotes, and the value must not
    swallow the rest.
    """
    raw, start = m.group("value") or "", m.start("value")
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "'\"":
        return _Val(raw[1:-1], _SINGLE if raw[0] == "'" else _DOUBLE, True)
    quoting = scan.ctx[start] if 0 <= start < len(scan.ctx) else _NONE
    if quoting == _NONE or extend is None:
        return _Val(raw, quoting, False)
    return _extend(scan.text, start, len(raw), quoting, extend)


def _extend(text: str, start: int, floor: int, quoting: int, extend: str) -> _Val:
    """Run a quoted value on to where its quote context ends (QG PR2 r5 B1).

    In single quotes only the closing ``'`` ends it; in double quotes the
    value stops at whitespace, quotes and backslashes (the JSON layer's
    escapes), which is also where the double-quoted run can end. So the
    end is a stop-character search, never a walk over the rest of the
    line. ``_extend`` skips the ``extend`` stops inside the span the regex
    already matched (the ``floor``), so a userinfo password keeps its
    ``@``. The value is read to at most ``_VALUE_CAP`` characters past
    the floor: the length and placeholder tests are decided by its head,
    and the bound keeps a scan linear. A read that hits the bound is
    ``capped``: its unread tail may turn a reference-looking head into a
    literal, so ``_literal`` gives a capped value no reference exemption.
    """
    hard = "'" if quoting == _SINGLE else _DOUBLE_STOPS
    limit = min(len(text), start + floor + _VALUE_CAP)
    end = _first(text, hard, start, limit)
    capped = end == limit < len(text)
    if extend and start + floor < end:
        end = _first(text, extend, start + floor, end)
    return _Val(text[start:end], quoting, False, capped)


def _local(scan: _Scan, m: re.Match[str], extend: str) -> _Val | None:
    """The value read under the quote that opens its own word (QG PR2 r4 N1).

    An unmatched apostrophe earlier in the text (``can't``) flips the
    whole-text reading, so ``-u 'admin:Pa$$w0rd'`` reads as unquoted and
    the ``$`` as an expansion. Locally: the nearest quote before the value
    on its line, if it opens a word (line start, whitespace or ``=``
    before it) and closes later on the same line, is re-read from there.
    Every lookup is a bisect on the marks of ``_scan`` (QG PR2 r5 B1).
    """
    text, marks, start = scan.text, scan.marks, m.start("value")
    q = max(_prev(marks["'"], start), _prev(marks['"'], start))
    line_start = _prev(marks["\n"], start) + 1
    if q < line_start or (q > line_start and text[q - 1] not in " \t="):
        return None
    line_end = _next(marks["\n"], start, len(text))
    if _next(marks[text[q]], start, line_end) >= line_end:
        return None
    # ``q`` is the nearest quote, it opens and it closes: the value is inside it.
    quoting = _SINGLE if text[q] == "'" else _DOUBLE
    return _extend(text, start, len(m.group("value") or ""), quoting, extend)


def _readings(scan: _Scan, m: re.Match[str], extend: str | None) -> list[_Val]:
    """Both quote readings of a sub-token value; a caller refuses if EITHER is literal."""
    vals = [_value(scan, m, extend)]
    if extend is not None and not vals[0].wrapped:
        local = _local(scan, m, extend)
        if local is not None:
            vals.append(local)
    return vals


def _literal(val: _Val) -> bool:
    """Long enough, not a reference, not a placeholder.

    Rejected as a reference: ``$`` or a backtick anywhere in a bare or
    double-quoted shell value (substitution: the text names the secret),
    and a single-quoted or source-code (``_CODE``) value that is nothing
    but ``$NAME``/``${NAME}``/``$(...)`` (shipped literally, it is still a
    name, not a secret) — unless the read was capped, since only the head
    was seen.
    """
    if val.quoting not in _NO_SUBSTITUTION and _EXPANSION.search(val.text):
        return False
    if not val.capped and _WHOLE_REFERENCE.match(val.text):
        return False
    return len(val.text) >= _MIN_VALUE and not _PLACEHOLDER.match(val.text)


def _opaque(val: _Val) -> bool:
    """Assignment/flag values also rule out paths, URLs, code and plain words.

    ``SORT_KEY=created_at`` names a column; an opaque value has a digit, a
    symbol other than a space, or is long enough that a word is unlikely.
    """
    value = val.text
    if not _literal(val) or _PATHLIKE.match(value):
        return False
    if not val.wrapped and _CODE_SHAPE.match(value):
        return False
    return _token_like(value)


def _token_like(value: str) -> bool:
    # Space is not a symbol here: a quoted phrase ("created at") is prose.
    return bool(re.search(r"[0-9]|[^\w.\-\s]", value)) or len(value) >= 20


def _any(scan: _Scan, patterns: tuple[re.Pattern[str], ...], extend: str | None = None) -> bool:
    return any(
        _literal(v)
        for p in patterns
        for m in p.finditer(scan.text)
        for v in _readings(scan, m, extend)
    )


def _header_hit(scan: _Scan) -> bool:
    """Header tokens must also be opaque: ``grep "X-Api-Key: missing"`` is prose.

    Bearer/API tokens are hex, base64 or JWT, never a plain word. An auth
    header in a code form is read as ``_CODE`` (finding 38).
    """
    vals = [
        v for p in (_AUTH_HEADER, _KEY_HEADER) for m in p.finditer(scan.text)
        for v in _header_readings(scan, m)
    ]
    vals += [
        _Val(m.group("value"), _CODE, True) for m in _QUOTED_BEARER.finditer(scan.text)
        if not _BEARER_PLACEHOLDER.match(m.group("value"))
    ]
    return any(_literal(v) and _token_like(v.text) for v in vals)


def _header_readings(scan: _Scan, m: re.Match[str]) -> list[_Val]:
    """A quoted key, or a value opened by a quote, is code, not a shell word;
    a backtick-opened value is a template, whose ``${...}`` stays a reference."""
    vals = _readings(scan, m, "")
    groups = m.groupdict()
    code = groups.get("vq") != "`" and bool(groups.get("kq") or groups.get("vq"))
    return [v._replace(quoting=_CODE) for v in vals] if code else vals


def _assignment_hit(scan: _Scan) -> bool:
    return any(
        not _POINTER_SUFFIX.search(m.group("name")) and _opaque(_assignment_value(scan, m))
        # ``max_context_tokens: int = 200_000``: a typed number is a setting.
        and not (m.group("ann") and _NUMBER.match(m.group("value") or ""))
        for m in _ASSIGNMENT.finditer(scan.text)
    )


def _assignment_value(scan: _Scan, m: re.Match[str]) -> _Val:
    """A quoted value of an assignment written as code is ``_CODE`` (finding 38).

    Code: a type annotation, a string prefix, a keyword argument, or
    anything but a bare ``=`` between the name and the value (``password =
    "v"``, ``password := "v"``). A shell assignment has no spaces around
    ``=``, so ``TOKEN="a$b"`` keeps the shell reading. An f-string drops its
    ``{...}`` slots and is judged on the rest (finding 41).
    """
    val = _value(scan, m)
    if not val.wrapped:
        return val
    # The separator runs from the name to the quote: an annotation or a
    # string prefix (``TOKEN=b"v"``) is in it, so neither is a bare ``=``.
    shell = scan.text[m.end("name") : m.start("value")] == "="
    if shell and not _call_argument(scan.text, m):
        return val
    if "f" in (m.group("pfx") or "").lower():
        val = val._replace(text=_template_literal(val.text, _FSTRING_SLOT))
    return val._replace(quoting=_CODE)


def _call_argument(text: str, m: re.Match[str]) -> bool:
    """``name="v"`` right after ``(`` or ``,``, or followed by ``,`` or ``)``."""
    start, end = m.start("name"), m.end("value")
    return bool(
        _CALL_BEFORE.search(text, max(0, start - 64), start) or _CALL_AFTER.match(text, end - 1)
    )


def _kv_value(m: re.Match[str]) -> _Val:
    """A key/value value, read as source code (``_CODE``, finding 38).

    Quotes are unwrapped and a ``$`` inside them is data; a backtick
    template drops its ``${...}`` slots and is judged on what is left.
    """
    raw = m.group("value") or ""
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "'\"`":
        inner = raw[1:-1]
        if raw[0] == "`":
            inner = _template_literal(inner, _TEMPLATE_SLOT)
        elif "f" in (m.group("pfx") or "").lower():
            inner = _template_literal(inner, _FSTRING_SLOT)
        return _Val(inner, _CODE, True)
    return _Val(raw, _CODE, False)


def _template_literal(inner: str, slot: re.Pattern[str]) -> str:
    """The literal runs of a template, joined: the text judged (finding 41).

    Joined, not the longest run (QG PR3 r3 m10): a secret split by slots
    (``f"q8Z{a}r2m{b}Xv7"``) is still judged whole. A run that ends in ``=``
    or ``:`` labels the slot after it (``f"TOKEN={tok}"``), it is not a
    value; ``f"{prefix}q8Zr..."`` keeps its literal tail. No slot: the text
    as written.
    """
    runs = slot.split(inner)
    if len(runs) == 1:
        return inner
    return "".join(r for r in runs if not r.rstrip().endswith(("=", ":")))


def _secret_key_name(name: str) -> bool:
    """True when a key names a credential by its WORDS, not by a substring.

    ``keyword``, ``passage``, ``bypass``, ``max_tokens``, ``sortKey`` and
    ``tokenType`` are not credentials; ``apiKey``, ``DB_PASSWORD``,
    ``x-api-key``, ``authToken`` and ``auth`` (docker's config.json) are.
    """
    words = [w.lower() for w in _WORDS.findall(name)]
    if not words or words[-1] in _POINTER_WORDS:
        return False
    if words in (["auth"], ["pass"]):
        return words == ["auth"]  # "tests pass: ..." is prose
    if _SECRET_WORDS.intersection(words):
        return True
    return any(w == "key" and i and words[i - 1] in _KEY_QUALIFIERS for i, w in enumerate(words))


def _kv_secret(name: str, val: _Val) -> bool:
    """A secret-named key holding an opaque, whitespace-free literal."""
    if not _secret_key_name(name):
        return False
    if _ENV_NAME.match(val.text) or _KV_PLACEHOLDER.match(val.text):
        return False
    if not val.wrapped and (_MEMBER.match(val.text) or _NUMBER.match(val.text)):
        return False
    if not val.wrapped and _BARE_VARIABLE.match(val.text):
        return False  # a variable: PHP ``$pw``, a shell or compose ``$PW``
    text = _AUTH_SCHEME.sub("", val.text)
    if re.search(r"\s", text):
        return False  # prose: a label, a hint, a sentence
    return _opaque(val._replace(text=text))


def _key_value_hit(text: str) -> bool:
    """Any secret key/value, including one INSIDE a quoted value.

    A serialised state is one big key/value (``{"diff": "+password: v"}``):
    after a quoted value the scan resumes inside it, not past it, or the
    text layer would never see the pair the leaf carries (finding 38).
    """
    pos = 0
    while (m := _KEY_VALUE.search(text, pos)) is not None:
        if _kv_secret(m.group("name"), _kv_value(m)):
            return True
        quoted = (m.group("value") or "")[:1] in "'\"`"
        pos = m.start("value") + 1 if quoted else m.end()
    return False


def _quoted_name_hit(text: str) -> bool:
    """A secret named in quotes, then its literal (finding 42).

    The scan resumes at the value's quote, which may open the next name.
    """
    pos = 0
    while (m := _QUOTED_NAME.search(text, pos)) is not None:
        if _kv_secret(m.group("name"), _kv_value(m)):
            return True
        pos = m.start("value")
    return False


def _symbol_subscript_hit(text: str) -> bool:
    return any(
        _kv_secret(m.group("name"), _kv_value(m)) for m in _SYMBOL_SUBSCRIPT.finditer(text)
    )


def _setter_hit(text: str) -> bool:
    return any(
        _setter_name(m.group("name")) and _kv_secret(m.group("name"), _kv_value(m))
        for m in _SETTER_CALL.finditer(text)
    )


def _setter_name(name: str) -> bool:
    """``setPassword``, ``with_api_key``, ``password``: a verb that sets, or the word alone."""
    words = [w.lower() for w in _WORDS.findall(name)]
    return len(words) == 1 or (len(words) > 1 and words[0] in _SETTER_VERBS)


def _auth_pair_hit(text: str) -> bool:
    return any(_kv_secret("password", _kv_value(m)) for m in _AUTH_PAIR.finditer(text))


# XML element text (finding 47): ``<password>v</password>``, ``<db:password>``,
# and a key held in an attribute (``<property name="x.password">v</property>``,
# ``<entry key="db.password">v</entry>``). Attributes, value and CDATA are
# atomic and bounded, and none crosses a ``<``: each ``<`` costs at most the
# distance to the next one, so the scan stays linear.
_XML_ELEMENT = re.compile(
    r"<(?P<tag>[A-Za-z_](?>[\w.:-]{0,128}))(?P<attrs>(?>[^<>\n]{0,512}))>"
    r"(?:<!\[CDATA\[(?P<cdata>(?>[^\]<>]{0,512}))\]\]>|(?P<value>(?>[^<>]{0,512})))"
    r"</(?P=tag)\s*>"
)
_XML_KEY_ATTR = re.compile(r"""(?<![\w-])(?:name|key)\s*=\s*(["'])([^"'\n]{1,256})\1""")
# Build-time and expression-language references: Maven/Ant ``@db.password@``,
# Spring ``#{...}``. ``${...}`` is ``_WHOLE_REFERENCE``'s.
_XML_REFERENCE = re.compile(r"^@[\w.-]+@$|^#\{[^{}]*\}$")
# A line break inside an element (real or serialised), with the sign a diff
# puts after it, and a serialised tab: whitespace around a pretty-printed value.
_XML_BREAK = re.compile(r"(?:\r?\n|\\[nr])[-+ ]?|\\t")


# A key held by an opening tag carried to its next ``<value>`` child (QG PR3
# r6 B1): .NET ``<setting name="ApiSecret" serializeAs="String">`` then
# ``<value>v</value>``, Spring ``<property name="password">`` then
# ``<value>v</value>``, pretty-printed. The gap is whitespace, a diff sign or
# a serialised ``\n``/``\t``, atomic and bounded like the attributes, so each
# ``<`` costs a constant and the scan stays linear.
_XML_CARRY = re.compile(
    r"<(?P<tag>[A-Za-z_](?>[\w.:-]{0,128}))(?P<attrs>(?>[^<>\n]{0,512}))(?<!/)>"
    r"(?>(?:[ \t\r\n+-]|\\[nrt]){0,64})(?=<value\b)"
)


def _xml_hit(text: str) -> bool:
    """A secret-named element, an element keyed by a secret-named attribute,
    or the ``<value>`` child of either."""
    if any(_xml_secret(_xml_names(m), _xml_text(m)) for m in _XML_ELEMENT.finditer(text)):
        return True
    return _xml_carry_hit(text)


def _xml_carry_hit(text: str) -> bool:
    for m in _XML_CARRY.finditer(text):
        child = _XML_ELEMENT.match(text, m.end())
        if child is not None and _xml_secret(_xml_names(m), _xml_text(child)):
            return True
    return False


def _xml_names(m: re.Match[str]) -> list[str]:
    return [m.group("tag"), *(a.group(2) for a in _XML_KEY_ATTR.finditer(m.group("attrs")))]


def _xml_text(m: re.Match[str]) -> str:
    return m.group("cdata") if m.group("cdata") is not None else m.group("value")


def _xml_secret(names: list[str], raw: str) -> bool:
    value = _XML_BREAK.sub(" ", raw).strip()
    if not value or _XML_REFERENCE.match(value):
        return False
    return any(_kv_secret(name, _Val(value, _CODE, True)) for name in names)


# ``.netrc`` (finding 47): ``machine h login u password p`` on one line, or
# a ``password p`` line of its own; ``account`` too, which netrc(5) defines
# as an additional password (QG PR3 r6 B2) (the multi-line form; a diff's ``+`` and a
# serialised line's start, ``\\n`` or the opening quote, kept). Tokens are
# printable ASCII bar quotes and the backslash, where a serialised line or
# a string literal ends, and judged as a key/value value is (``{PW}`` and
# ``$PW`` are no password). The window after ``machine``/``default`` is bounded.
_NETRC_TOKEN = r"(?P<value>(?>[!#-&(-\[\]-_a-~]+))"
_NETRC: tuple[re.Pattern[str], ...] = (
    re.compile(
        rf"\b(?:machine|default)\b[^\n\\]{{0,256}}?(?<![\w.-])(?:password|account)[ \t]+"
        rf"{_NETRC_TOKEN}"
    ),
    re.compile(
        rf"(?:(?m:^)|(?<=\\n)|(?<=[\"']))[ \t+-]*(?:password|account)[ \t]+{_NETRC_TOKEN}"
        r"""(?=[ \t]*(?:\r|\n|\\[nr]|["']|$))"""
    ),
)


# A usage string's option list (``'account [info]'``), not a netrc token.
_NETRC_USAGE = re.compile(r"^\[[^\]]*\]$")


def _netrc_hit(text: str) -> bool:
    return any(
        not _NETRC_USAGE.match(m.group("value"))
        and _kv_secret("password", _Val(m.group("value"), _NONE, False))
        for p in _NETRC
        for m in p.finditer(text)
    )


def credential_labels(text: str) -> list[str]:
    """Context-marked credential shapes present in ``text`` (labels only).

    Every escape layer is scanned: ``ssh h "export T=\\"<secret>\\""``
    holds its quotes escaped, and read as written the value is a lone
    backslash (QG PR2 r4, Francisca's note). When no precise detector
    fires on any layer, the catch-all layer reads them all once more.
    """
    if not isinstance(text, str):
        return []
    layers = _escape_layers(text)
    found: list[str] = []
    for layer in layers:
        found += [label for label in _labels(layer) if label not in found]
    if not found and any(
        _catch_all_hit(layer) for unit in _catch_units(text) for layer in _escape_layers(unit)
    ):
        found.append(CATCH_ALL_LABEL)
    return found


def _escape_layers(text: str, depth: int = 8) -> list[str]:
    """``text`` and its successive un-escapes of ``\\" \\' \\\\``, to a fixed point.

    ``depth`` bounds the work: a layer halves a run of backslashes, so 8
    layers cover 8 levels of nesting (255 backslashes before a quote).
    """
    layers = [text]
    for _ in range(depth):
        nxt = _UNESCAPE.sub(r"\1", layers[-1])
        if nxt == layers[-1]:
            break
        layers.append(nxt)
    return layers


def _flag_hit(scan: _Scan) -> bool:
    return any(_opaque(_value(scan, m)) for m in _FLAG.finditer(scan.text))


# The precise detectors, in the order their labels are reported. A test
# empties this tuple to prove what the catch-all layer catches on its own.
_DETECTORS: tuple[tuple[str, Callable[[_Scan], bool]], ...] = (
    ("credential assignment", _assignment_hit),
    ("credential key-value", lambda s: _key_value_hit(s.text)),
    ("credential quoted name", lambda s: _quoted_name_hit(s.text) or _symbol_subscript_hit(s.text)),
    ("credential setter", lambda s: _setter_hit(s.text)),
    ("basic-auth pair", lambda s: _auth_pair_hit(s.text)),
    ("credential xml element", lambda s: _xml_hit(s.text)),
    ("netrc password", lambda s: _netrc_hit(s.text)),
    ("credential flag", _flag_hit),
    ("private key block", lambda s: bool(_PEM_TAIL.search(s.text))),
    # Sub-token detectors: the value may start inside a quoted word.
    ("auth header", _header_hit),
    ("basic-auth flag", lambda s: _any(s, _BASIC_FLAGS, extend="")),
    ("password flag", lambda s: _any(s, _PASSWORD_FLAGS)),
    ("cli secret setting", lambda s: _any(s, (_CLI_SETTING,))),
    ("url userinfo", lambda s: _any(s, (_USERINFO,), extend="@/")),
    ("url query credential", lambda s: _any(s, (_QUERY,), extend="&#")),
)


def _labels(text: str) -> list[str]:
    scan = _scan(text)
    return [label for label, hit in _DETECTORS if hit(scan)]


# --- The catch-all layer (QG PR3 r4, the operator's structural fix) --------
# Five rounds of review found a new SHAPE each time (a subscript, a setter, a
# dotted name, a Ruby block): a precise detector knows the syntax around a
# secret, and code has more syntax than any list. The last line of defence
# is a keyword rule in the manner of the gitleaks ``generic-api-key`` rule
# and GitHub's generic-secret patterns: it knows no syntax. A LINE (a real
# newline or a serialised ``\\n``) is refused when it holds a quoted literal
# that looks like a secret (``_catch_literal``) AND a secret word
# (``_CATCH_WORDS``, or ``key`` after a qualifier, read by words as
# ``_secret_key_name`` reads them, so ``.``, ``_``, ``-`` and case join
# them) outside that literal. Since QG r5 the literal may be unquoted: a
# bare token between whitespace, ``<`` and ``>`` outside every quoted
# literal, gated harder (``_catch_bare_literal``) because the sweep priced
# the ungated form at 111 newly refused code and doc lines against 5.
# It runs only when no precise detector fired on any layer: it adds
# refusals and never changes a label. A false positive
# costs one egress (the caller falls back to its heuristic), so the rule
# leans to refusing; the sweep in the security review prices it.
CATCH_ALL_LABEL = "credential catch-all"
_CATCH_MIN = 10
_CATCH_LINE = re.compile(r"\n|\\n|\r")
# A cheap pre-filter; the words themselves are judged by ``_catch_word``.
_CATCH_HINT = re.compile(r"pw|pass|secret|token|key|auth|credential", re.I)
# A quoted literal; a backslash escapes the next character, so ``"a\\"b"`` is
# one literal, and a serialised line does not pair its ``\\"`` wrongly. An
# escaped quote never opens one: from every ``\\"`` of ``\\"\\"\\"...`` the
# scan would run to the end of the line, quadratic.
_CATCH_LITERAL = re.compile(
    r"""(?<!\\)(?:'((?:[^'\\\n]|\\.)*)'|"((?:[^"\\\n]|\\.)*)"|`((?:[^`\\\n]|\\.)*)`)"""
)
_CATCH_IDENT = re.compile(r"[A-Za-z](?>[\w.-]*)")
# ``pass`` alone is not here: "tests pass", "pass the result" are prose.
_CATCH_WORDS = frozenset({
    "password", "passwd", "passphrase", "pwd", "pw", "secret", "secrets", "token",
    "auth", "authorization", "credential", "credentials", "apikey", "secretkey",
    "privatekey", "accesskey", "clientsecret",
})
# Template, format and documentation slots: ``${X}``, ``{x}``, ``{{ x }}``,
# ``%(x)s``, ``<x>``. A literal is judged on what is left once they go.
_CATCH_SLOT = re.compile(r"\$\{[^{}\n]*\}|\{\{?[^{}\n]*\}\}?|%\([\w.-]+\)[sdr]|<[^<>\n]*>")
# A literal default of a parameter slot is kept (``${PW:-<opaque>}``, as
# ``_PARAM_DEFAULT`` reads it); an empty one, a message or a name goes.
_CATCH_DEFAULT = re.compile(r"\$\{[A-Za-z_]\w*:?[-=]([^{}$\n]+)\}")
# A name, not a value: segments of letters with at most one run of digits,
# joined by separators (``services.stripe.secret``, ``OPENROUTER_API_KEY``,
# ``fs.s3a``, ``prod/db-password-2024``, ``SORT_KEY=created_at``,
# ``?sslmode=require``). A generated secret interleaves digits and letters
# (``q8Zr2mXv7…``) and fails the rule.
_NAME_SEGMENT = r"(?>[A-Za-z]*)(?>\d*)(?>[A-Za-z]*)"  # atomic: one reading, linear
_CATCH_NAME = re.compile(rf"^{_NAME_SEGMENT}(?:[_.\-/:@+=?&,*\[\]]{_NAME_SEGMENT})*$")
# A VALUE read as a name (QG PR3 r6 m2): from 20 characters on, ``/`` and
# ``+`` separate its segments only when it also holds a separator outside
# the base64 alphabet (``prod/db-password-2024``). A standard base64 key
# is letters, digits, ``/`` and ``+``: cut at them, a 40-character key read
# as a name 107 times in 2000 random keys.
_NAME_SEPARATORS = r"_.\-:@=?&,*\[\]"
_CATCH_NAME_VALUE = re.compile(
    rf"^(?:(?=.{{0,19}}$)|(?=[^\n]*[{_NAME_SEPARATORS}]))"
    rf"{_NAME_SEGMENT}(?:[{_NAME_SEPARATORS}/+]{_NAME_SEGMENT})*$"
    rf"|^{_NAME_SEGMENT}(?:[{_NAME_SEPARATORS}]{_NAME_SEGMENT})*$"
)
# A symbol for the character-class rule: ASCII punctuation that is not one of
# the separators a name or a path is made of.
_CATCH_SYMBOL = re.compile(r"[!-*,;<>?\[-\^`{-~]")
# A label at the head of a literal: a name, then ``=`` or ``:`` and a space.
_LITERAL_LABEL = re.compile(r"([A-Za-z_][\w.-]*)(?:=|:\s+)")
# A file path (not a URL: a URL's words may name what it carries).
_FILE_PATH = re.compile(r"^(?:[~/]|\.{1,2}[/\\]|[A-Za-z]:[\\/]|\$\{?[A-Za-z_]\w*\}?[/\\])")
# A relative file path (QG PR3 r6): directories that are names (letter runs
# with at most one digit run, as ``_CATCH_NAME`` reads them), then a file
# with an extension: ``resources/js/Pages/Auth/Login.vue``, a Vite asset
# ``assets/Login-Bk3x9Zq2.js``. A secret holding ``/`` fails it: a base64
# run interleaves digits inside a segment (``ab/Cd12Xy9Qw7/…``) and has no
# extension. No URL (``api/token/v1`` has no extension, its words count).
_PATH_DIR = rf"{_NAME_SEGMENT}(?:[_.-]{_NAME_SEGMENT})*"
_REL_PATH = re.compile(rf"^(?:{_PATH_DIR}/)+[\w-][\w.-]*\.[A-Za-z][A-Za-z0-9]{{0,5}}$")


def _file_path(value: str) -> bool:
    """An absolute, home, drive, ``$VAR/`` or relative file path (its words name a file)."""
    return bool(_FILE_PATH.match(value) or _REL_PATH.match(value))

# The bare reading (finding 47): tokens between whitespace, ``<`` and ``>``.
_BARE_TOKEN = re.compile(r"[^\s<>]+")
_BARE_TRIM = "\"'`,;.:()[]{}\\"
_BARE_LABEL = re.compile(r"([A-Za-z_][\w.-]*)[=:]")
# A hash declared as one: SRI ``sha512-…``, go.sum ``h1:…``, ``sha256:…``.
_DECLARED_HASH = re.compile(r"^(?:sha\d{1,3}|md5|h1)[-:=]", re.I)
# Code a bare token is, and a quoted literal is not: a call or subscript
# glued to a name (``tokens[0].map((line``), a bundler's ``name$1`` suffix.
_BARE_CODE = re.compile(r"\w[(\[]|^[A-Za-z_]\w*\$\d+(?:\.[\w$]+)*$")
# True: a bare token must also hold a digit and a symbol or both cases.
_BARE_GATE = True
_BARE_LONG = 20
_NOT_A_SECRET: tuple[re.Pattern[str], ...] = (
    # A regular expression: an escape class, a group, a character class
    # that opens on a range, a counted or dotted repeat, words joined by
    # ``|``. No run is scanned twice (a ``[a-`` repeat stays linear).
    re.compile(r"\\[sSwWdDbB]|\(\?[:=!<P]|\[\^?\w-\w|\{\d+,\d*\}|\.[*+]"),
    re.compile(r"^\(?\w+(?:\\?\|\w+)+\)?$"),
    # Code: a call (``create($request->all())``, ``var(--token-name)``) or an
    # attribute (``marker-end="url(#a)"``).
    re.compile(r"^(?>[\w$.:>-]*)(?<=\w)\(|=['\"]"),  # atomic: linear
    # A path from a variable (``$ARKA_OS/mcps/x.sh``), a URL without userinfo.
    re.compile(r"^\$\{?[A-Za-z_]\w*\}?[/\\]"),
    re.compile(r"^[a-z][a-z0-9+.\-]*://(?![^/@\s]*:[^/@\s]*@)", re.I),
    # A date or a timestamp (``2099-01-01T00:00:00+00:00``).
    re.compile(r"^\d{4}-\d\d-\d\d(?:[T ]\d\d:\d\d(?::\d\d(?:\.\d+)?)?(?:Z|[+-]\d\d:?\d\d)?)?$"),
    # Prose and documentation: whitespace, or a character outside ASCII (an ellipsis).
    re.compile(r"\s|[^\x00-\x7f]"),
    _KV_PLACEHOLDER, _PLACEHOLDER, _PATHLIKE, _REL_PATH, _CATCH_NAME_VALUE,
)


def _catch_units(text: str) -> list[str]:
    """The texts the catch-all reads; a serialised state is read by its leaves.

    A JSON state wraps each leaf in quotes, and a leaf with no space
    (``"+ds.setPassword(password)"``) would read as a literal on its own.
    So the string leaves are read as written, and each key with its plain
    string value (``api_key "v"``) and each array of plain strings
    (``"Authorization" "Token v"``) is read as a line of its own:
    the key or the sibling names the value. Text that is not a JSON object
    or array is read as it is.
    """
    try:
        data = json.loads(text)
    except (ValueError, RecursionError):
        return [text]
    if not isinstance(data, dict | list):
        return [text]
    units: list[str] = []
    stack: list[object] = [data]
    while stack:
        node = stack.pop()
        if isinstance(node, str):
            units.append(node)
        elif isinstance(node, dict):
            stack += [*node.keys(), *node.values()]
            units += [f'{k} "{v}"' for k, v in node.items() if _plain(v)]
        elif isinstance(node, list):
            stack += node
            units.append(" ".join(f'"{v}"' for v in node if _plain(v)))
    return units


def _plain(value: object) -> bool:
    """A one-line string with no quote or backslash: it reads back as one literal.

    Anything else is code, read as its own leaf.
    """
    return isinstance(value, str) and not any(c in value for c in "\n\"'`\\")


def _catch_all_hit(text: str) -> bool:
    """A line holding a secret-looking literal and a secret word outside it."""
    if not _CATCH_HINT.search(text):
        return False
    return any(
        _CATCH_HINT.search(line) and _catch_line(line) for line in _CATCH_LINE.split(text)
    )


class _Piece(NamedTuple):
    """One run of a line as the catch-all reads it."""

    text: str  # what the word check reads for this run
    value: str = ""  # a literal's or a bare token's value ('' for the text between)
    secret: bool = False  # a secret-looking literal or bare token
    path: bool = False  # a file path: its words may name the file, not a value


def _catch_line(line: str) -> bool:
    """A secret-looking literal, and a secret word OUTSIDE every such literal.

    The word must name the value, not sit inside it: a hash or a regex
    literal holds ``Pw`` or ``password`` among its own characters
    (``"sha512-…PwZG…"``). The label of a ``NAME=value`` or ``Name: value``
    literal names it (``putenv("API_TOKEN=…")``, ``'Authorization: Bearer
    …'``), so it counts as outside and the value alone is judged. The text
    between the quoted literals is read by its bare tokens too (finding
    47): the literal may be unquoted (``<password>v</password>``,
    ``password v``). A file path's words are dropped only when the value
    paired with it is a hash, a path or a hashed asset (``_hashed_pair``).
    """
    pieces = _line_pieces(line)
    if not any(p.secret for p in pieces):
        return False
    kept = ["" if p.path and _hashed_pair(pieces, i) else p.text for i, p in enumerate(pieces)]
    return _catch_word(" ".join(kept))


def _line_pieces(line: str) -> list[_Piece]:
    pieces, pos = [], 0
    for m in _CATCH_LITERAL.finditer(line):
        pieces += [*_gap_pieces(line[pos : m.start()]), _literal_piece(m)]
        pos = m.end()
    return [*pieces, *_gap_pieces(line[pos:])]


def _literal_piece(m: re.Match[str]) -> _Piece:
    """A quoted literal: a secret leaves its label, anything else stays as written."""
    label, value = _split_label(_literal_text(m))
    if _catch_literal(value):
        return _Piece(label, value, secret=True)
    return _Piece(m.group(), value, path=_file_path(value))


# A key/value separator between a path and its value: not the value itself.
_PAIR_SEPARATOR = re.compile(r"[=>:,;]+")
# A hex digest (``md5`` and up) and a bundler's hashed asset (``Login-Bk3x9Zq2.js``).
_HEX_DIGEST = re.compile(r"^[0-9a-fA-F]{32,}$")
_HASHED_ASSET = re.compile(r"^[\w.-]+-[A-Za-z0-9_]{6,}\.[A-Za-z][A-Za-z0-9]{0,5}$")


def _hashed_pair(pieces: list[_Piece], i: int) -> bool:
    """The value next to the path at ``i`` is a hash, a path or a hashed asset.

    ``'/app/Auth/X.php' => '<sha256>'`` (a hash manifest) and ``<sha256>
    ./app/Auth/X.php`` (``sha256sum``): the words name the file.
    ``"auth/secret.key": "<opaque>"`` keys a secret by its file (QG PR3 r6
    M-B), so an opaque neighbour, or none, keeps the words.
    """
    after = _neighbour(pieces[i + 1 :])
    before = _neighbour(reversed(pieces[:i]))
    return any(v is not None and _hash_like(v) for v in (after, before))


def _neighbour(pieces: Iterable[_Piece]) -> str | None:
    """The first value among ``pieces`` that is not a key/value separator."""
    return next((p.value for p in pieces
                 if p.value and not _PAIR_SEPARATOR.fullmatch(p.value)), None)


def _hash_like(value: str) -> bool:
    return bool(_HEX_DIGEST.match(value) or _DECLARED_HASH.match(value)
                or _file_path(value) or _HASHED_ASSET.match(value))


def _gap_pieces(text: str) -> list[_Piece]:
    """The text between quoted literals, by its bare tokens (finding 47).

    A token runs between whitespace, ``<`` and ``>``, with end punctuation
    trimmed; a secret-looking token leaves its ``NAME=`` or ``NAME:`` label.
    """
    if len(text) < _CATCH_MIN:
        return [_Piece(text)]
    pieces, pos = [], 0
    for m in _BARE_TOKEN.finditer(text):
        token = _bare_token(m.group())
        label, value = _split_bare_label(token)
        secret = len(value) >= _CATCH_MIN and _catch_bare_literal(token, value)
        piece = (_Piece(label, token, secret=True) if secret
                 else _Piece(m.group(), token, path=_file_path(token)))
        pieces += [_Piece(text[pos : m.start()]), piece]
        pos = m.end()
    return [*pieces, _Piece(text[pos:])]


def _bare_token(raw: str) -> str:
    """A diff line's sign and an XML CDATA opener are not part of the value."""
    return raw.strip(_BARE_TRIM).lstrip("+-").removeprefix("![CDATA[")


def _split_bare_label(token: str) -> tuple[str, str]:
    """``NAME=value`` or ``NAME:value`` inside one bare token → (label, value)."""
    m = _BARE_LABEL.match(token)
    if m is None or not _CATCH_NAME.match(m.group(1)):
        return "", token
    return m.group(1), token[m.end() :]


def _catch_bare_literal(token: str, value: str) -> bool:
    """A bare token's value judged as a quoted literal is, and more strictly.

    Not a declared hash (``sha512-…``, ``h1:…``, read on the whole token),
    not code (``_BARE_CODE``), not a value holding a secret word
    (``password))->`` is code naming one) and, with ``_BARE_GATE``, a digit
    and a symbol or both letter cases.
    """
    if _DECLARED_HASH.match(token) or _BARE_CODE.search(value) or _catch_word(value):
        return False
    return _catch_literal(value) and (not _BARE_GATE or _bare_strong(value))


def _bare_strong(value: str) -> bool:
    """A digit, and a symbol, both letter cases or 20+ characters (the gated
    bare rule: ``abc123def4`` is a name; a 32-char hex key is not)."""
    if not re.search(r"\d", value):
        return False
    if len(value) >= _BARE_LONG or _CATCH_SYMBOL.search(value):
        return True
    return bool(re.search(r"[a-z]", value) and re.search(r"[A-Z]", value))


def _literal_text(m: re.Match[str]) -> str:
    return next(g for g in m.groups() if g is not None)


def _split_label(raw: str) -> tuple[str, str]:
    """``NAME=value`` or ``Name: value`` → (the label, the value); else ("", raw)."""
    m = _LITERAL_LABEL.match(raw)
    if m is None or not _CATCH_NAME.match(m.group(1)):
        return "", raw  # ``q8Zr…Zw==`` is base64, not a label
    return m.group(1), raw[m.end() :]


def _catch_word(text: str) -> bool:
    """A secret word in a name of ``text``, read by words as ``_secret_key_name`` does.

    A name is joined by ``.``, ``_``, ``-`` or case (``api.key``,
    ``DB_PASSWORD``, ``trustStorePassword``). Inside one name a pointer
    word after the secret word names something else (``api.key.id``,
    ``token_url``, ``PASSWORD_FILE``).
    """
    return any(_secret_words(m.group()) for m in _CATCH_IDENT.finditer(text))


def _secret_words(name: str) -> bool:
    words = [w.lower() for w in _WORDS.findall(name)] + [""]
    return any(
        (w in _CATCH_WORDS or (w == "key" and i and words[i - 1] in _KEY_QUALIFIERS))
        and words[i + 1] not in _POINTER_WORDS
        for i, w in enumerate(words[:-1])
    )


def _catch_literal(raw: str) -> bool:
    """``_CATCH_MIN`` characters or more once slots and an auth scheme go,
    letters with a digit or a symbol, and none of ``_NOT_A_SECRET``."""
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "'\"`":
        raw = raw[1:-1]  # a quoted value inside the literal (``'k: "v"'``)
    unschemed = _AUTH_SCHEME.sub("", raw)
    if _WHOLE_REFERENCE.match(unschemed):
        return False  # ``Bearer $API_KEY`` names the token
    value = _CATCH_SLOT.sub("", _CATCH_DEFAULT.sub(r"\1", unschemed))
    if len(value) < _CATCH_MIN or any(p.search(value) for p in _NOT_A_SECRET):
        return False
    return _two_classes(value)


def _two_classes(value: str) -> bool:
    """Letters, and a digit or a symbol (``_CATCH_SYMBOL``)."""
    if not re.search(r"[A-Za-z]", value):
        return False
    return bool(re.search(r"\d", value) or _CATCH_SYMBOL.search(value))


def egress_secret_labels(text: str) -> list[str]:
    """Vendor-prefixed secrets plus context-marked credentials.

    The single secret vocabulary for everything leaving the machine:
    ``policy.evaluate`` uses it, and so must every path that refuses
    secrets without calling the policy (``decisions.privacy``).
    """
    return secret_labels(text) + credential_labels(text)
