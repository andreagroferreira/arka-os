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

A false positive denies one egress (the caller falls back to its
heuristic); a false negative ships a password to a third party — the
patterns lean to the deny side on purpose. Regex detection cannot prove
absence: the residual is bounded by the probe set in
``tests/python/test_egress_credentials.py``.

Labels, never values, leave this module: the policy hashes the label
into the audit, exactly as it does for ``secret_labels``.
"""

from __future__ import annotations

import re
from bisect import bisect_left
from functools import lru_cache
from typing import NamedTuple

from core.governance.harness_scanner import secret_labels

# PASS covers PASSWORD/PASSWD/PASSPHRASE and the bare DB_PASS/PASS (QG PR2
# r1 B2d); PWD covers MYSQL_PWD. A path value (PWD=/x) is ruled out below.
_SECRET_WORD = r"(?:KEY|TOKEN|SECRET|PASS|PWD|CREDENTIAL)"
# Suffixes naming a pointer TO a secret (same idea as harness_scanner).
_POINTER_SUFFIX = re.compile(
    r"(?:_FILE|_PATH|_HELPER|_CMD|_COMMAND|_DIR|_ID|_NAME|_URL|_URI|_HOST|_ENDPOINT)$", re.I
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
_WHOLE_REFERENCE = re.compile(r"^(?:\$\{?[A-Za-z_]\w*\}?|\$\(.*\)?|`.*`?)$")
_NONE, _SINGLE, _DOUBLE = 0, 1, 2


class _Val(NamedTuple):
    text: str
    quoting: int  # _NONE | _SINGLE | _DOUBLE
    wrapped: bool  # written as '...' or "..." (the value is the whole word)
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

_ASSIGNMENT = re.compile(
    # Zero or more chars before the word: a bare TOKEN= / KEY= / export
    # token= is a credential too (QG PR2 r1 B2a); the lookbehind keeps the
    # match at the start of the identifier.
    rf"(?<![\w-])(?P<name>[A-Za-z0-9_]*{_SECRET_WORD}[A-Za-z0-9_]*)\s*=\s*{_VALUE}",
    re.I,
)
_FLAG = re.compile(
    rf"(?<![\w-])--(?:[a-z0-9]+-)*(?:password|passwd|token|secret|api-?key|access-key)"
    rf"(?:=|\s+){_VALUE}",
    re.I,
)
_AUTH_HEADER = re.compile(
    r"\b(?:proxy-)?authorization\s*:\s*(?:(?:bearer|basic|token|digest|apikey)\s+)?"
    rf"(?P<value>{_BARE})",
    re.I,
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
# How far past the regex match a quoted value is read (QG PR2 r5 B1).
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
    the floor: every test on it (length, placeholder, reference) is
    decided by its head, and the bound keeps a scan linear.
    """
    hard = "'" if quoting == _SINGLE else _DOUBLE_STOPS
    limit = min(len(text), start + max(floor, _VALUE_CAP))
    end = _first(text, hard, start, limit)
    if extend and start + floor < end:
        end = _first(text, extend, start + floor, end)
    return _Val(text[start:end], quoting, False)


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
    double-quoted value (substitution: the text names the secret), and a
    single-quoted value that is nothing but ``$NAME``/``${NAME}``/``$(...)``
    (shipped literally, it is still a name, not a secret).
    """
    if val.quoting != _SINGLE and _EXPANSION.search(val.text):
        return False
    if _WHOLE_REFERENCE.match(val.text):
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

    Bearer/API tokens are hex, base64 or JWT, never a plain word.
    """
    vals = (
        v for p in (_AUTH_HEADER, _KEY_HEADER) for m in p.finditer(scan.text)
        for v in _readings(scan, m, "")
    )
    return any(_literal(v) and _token_like(v.text) for v in vals)


def _assignment_hit(scan: _Scan) -> bool:
    return any(
        not _POINTER_SUFFIX.search(m.group("name")) and _opaque(_value(scan, m))
        for m in _ASSIGNMENT.finditer(scan.text)
    )


def credential_labels(text: str) -> list[str]:
    """Context-marked credential shapes present in ``text`` (labels only).

    Every escape layer is scanned: ``ssh h "export T=\\"<secret>\\""``
    holds its quotes escaped, and read as written the value is a lone
    backslash (QG PR2 r4, Francisca's note).
    """
    if not isinstance(text, str):
        return []
    found: list[str] = []
    for layer in _escape_layers(text):
        found += [label for label in _labels(layer) if label not in found]
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


def _labels(text: str) -> list[str]:
    scan = _scan(text)
    checks: tuple[tuple[str, bool], ...] = (
        ("credential assignment", _assignment_hit(scan)),
        ("credential flag", any(_opaque(_value(scan, m)) for m in _FLAG.finditer(text))),
        # Sub-token detectors: the value may start inside a quoted word.
        ("auth header", _header_hit(scan)),
        ("basic-auth flag", _any(scan, _BASIC_FLAGS, extend="")),
        ("password flag", _any(scan, _PASSWORD_FLAGS)),
        ("cli secret setting", _any(scan, (_CLI_SETTING,))),
        ("url userinfo", _any(scan, (_USERINFO,), extend="@/")),
        ("url query credential", _any(scan, (_QUERY,), extend="&#")),
    )
    return [label for label, hit in checks if hit]


def egress_secret_labels(text: str) -> list[str]:
    """Vendor-prefixed secrets plus context-marked credentials.

    The single secret vocabulary for everything leaving the machine:
    ``policy.evaluate`` uses it, and so must every path that refuses
    secrets without calling the policy (``decisions.privacy``).
    """
    return secret_labels(text) + credential_labels(text)
