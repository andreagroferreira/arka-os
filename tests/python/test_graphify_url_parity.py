"""One corpus, both implementations of the graphify URL guard.

The Bearer token is validated twice — `isPrivateHost` in
`installer/graphify.js` (registration) and `_is_private_host` in
`core/synapse/layers_kb.py` (the side that resolves the host before opening
a socket — not the only sender; see RESOLVE_DEPENDENT below). QG review
found the two had silently drifted: Python used `ip.is_private`, a
strict superset admitting 0.0.0.0/8, TEST-NET-1/2/3, 240/4 and
255.255.255.255, and judged names by string shape so `http://134744072/`
(8.8.8.8 in decimal) shipped the credential to a public host.

Reviewing for drift does not scale. This drives ONE fixture through both and
fails on any disagreement, so the next divergence breaks CI instead.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from core.synapse.layers_kb import _valid_graphify_url

REPO_ROOT = str(Path(__file__).resolve().parents[2])

# (url, expected_accept). Anything not private must never receive a token.
CORPUS: tuple[tuple[str, bool], ...] = (
    # --- legitimate operator endpoints ---------------------------------
    ("https://graph.example.com/mcp", True),   # TLS anywhere
    ("https://10.0.0.5/mcp", True),
    ("http://localhost:8080/mcp", True),
    ("http://127.0.0.1:8080/mcp", True),
    ("http://192.168.1.13:8080/mcp", True),    # the home AI lab
    ("http://10.0.0.5/mcp", True),
    ("http://172.16.0.1/mcp", True),
    ("http://172.31.255.254/mcp", True),
    ("http://169.254.1.1/mcp", True),
    ("http://[::1]:8080/mcp", True),
    ("http://[fc00::1]/mcp", True),
    ("http://[fe80::1]/mcp", True),
    # --- public / hostile ----------------------------------------------
    ("http://evil.example.com/mcp", False),
    ("http://8.8.8.8/mcp", False),
    ("http://10.evil.example/mcp", False),      # prefix-regex bypass
    ("http://127.evil.example/mcp", False),
    ("http://192.168.evil.example/mcp", False),
    ("http://172.16.evil.example/mcp", False),
    ("http://169.254.evil.example/mcp", False),
    ("http://evil.local.example/mcp", False),
    ("http://134744072/mcp", False),            # 8.8.8.8, decimal
    ("http://0x08080808/mcp", False),           # 8.8.8.8, hex
    ("http://0177.0.0.1/mcp", False),           # octal
    ("http://[2001:db8::1]/mcp", False),        # RFC 3849 documentation
    ("http://172.32.0.1/mcp", False),           # just past 172.16/12
    ("http://192.0.2.5/mcp", False),            # TEST-NET-1
    ("http://198.51.100.4/mcp", False),         # TEST-NET-2
    ("http://203.0.113.9/mcp", False),          # TEST-NET-3
    ("http://0.0.0.0/mcp", False),
    ("http://255.255.255.255/mcp", False),
    ("http://240.0.0.1/mcp", False),
    # --- malformed / degenerate ----------------------------------------
    ("ftp://host/mcp", False),
    ("not-a-url", False),
    ("http:///mcp", False),                     # empty host
    ("", False),
)

_JS_RUNNER = """
import {{ resolveGraphifyHttpConfig }} from '{root}/installer/graphify.js';
import {{ mkdtempSync, mkdirSync, writeFileSync }} from 'node:fs';
import {{ tmpdir }} from 'node:os';
import {{ join }} from 'node:path';
const home = mkdtempSync(join(tmpdir(), 'parity-'));
mkdirSync(join(home, '.arkaos'), {{ recursive: true }});
writeFileSync(join(home, '.arkaos', 'keys.json'),
  JSON.stringify({{ GRAPHIFY_TOKEN: 'tok' }}));
const urls = {urls};
const out = {{}};
for (const u of urls) {{
  out[u] = Boolean(resolveGraphifyHttpConfig({{ home, env: {{ GRAPHIFY_URL: u }} }}).url);
}}
console.log(JSON.stringify(out));
"""


# Names that only exist on the operator's LAN. The two sides answer these
# DIFFERENTLY by design, so they are excluded from the parity corpus above:
#
#   JS  (registration) judges the string — it must not block `npx arkaos
#       update` on a laptop that is away from the LAN at install time.
#   Python (send time) RESOLVES and requires every answer to be private, so
#       an unresolvable name yields no endpoint. That is the fail-open path:
#       no graph context this turn, and — critically — no credential sent to
#       whatever a hijacked DNS search domain would have returned.
#
# The asymmetry is deliberate, but NOT because "only Python sends": QG review
# corrected that. `registerGraphifyHttpMcp` hands a live Bearer token to
# `claude mcp add --scope user`, so Claude Code becomes a SECOND sender aimed
# at a name the JS side never resolved. Open debt (M1): resolve at
# registration time too, accepting by form only when the name does not resolve
# at all — an off-LAN laptop keeps working, a publicly-resolving name is
# refused. Until then the residual vector is a bare single-label name on a
# hostile DNS search domain.
RESOLVE_DEPENDENT = ("http://nas.local/mcp", "http://lab:8080/mcp")

# Also outside the corpus, for a different reason: Node's `new URL()` throws
# on an IPv6 zone-id, so `http://[fe80::1%25eth0]/` is JS-reject /
# Python-accept. Direction is safe (fe80::1 IS link-local — Python is right
# and JS is fail-closed); it is a usability nit, not a hole.
ZONE_ID_DEPENDENT = ("http://[fe80::1%25eth0]/mcp",)


@pytest.mark.parametrize("url,expected", CORPUS)
def test_python_guard_matches_corpus(url: str, expected: bool):
    assert bool(_valid_graphify_url(url)) is expected


@pytest.mark.parametrize("url", RESOLVE_DEPENDENT)
def test_unresolvable_lan_name_never_receives_a_credential(url: str):
    """An unresolvable LAN name must degrade to "not configured", not to trust."""
    import socket

    try:
        socket.getaddrinfo(url.split("//")[1].split(":")[0].split("/")[0], None)
    except OSError:
        assert _valid_graphify_url(url) == "", (
            "an unresolvable name must never be treated as private"
        )


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
def test_js_and_python_guards_agree():
    """Both sides must reach the same verdict on every corpus entry."""
    urls = [u for u, _ in CORPUS]
    script = _JS_RUNNER.format(root=REPO_ROOT, urls=json.dumps(urls))
    proc = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        capture_output=True, text=True, timeout=60, cwd=REPO_ROOT,
    )
    assert proc.returncode == 0, f"node runner failed: {proc.stderr[-500:]}"
    js = json.loads(proc.stdout.strip().splitlines()[-1])

    divergent = {
        url: {"js": js[url], "python": bool(_valid_graphify_url(url))}
        for url, _ in CORPUS
        if js[url] != bool(_valid_graphify_url(url))
    }
    assert not divergent, f"JS/Python guards disagree: {divergent}"

    wrong = {url: js[url] for url, expected in CORPUS if js[url] is not expected}
    assert not wrong, f"JS guard disagrees with the corpus: {wrong}"
