"""Tests for Synapse L2.5 — KB context injection.

Covers:
- Vector-store path (mocked) with similarity threshold
- Jaccard fallback when vector store is empty / missing
- Block formatting: title, path, excerpt, wikilinks
- record_obsidian_query side-effect
- Feature flag + env bypass
- Engine sequencing (L2 < L2.5 < L3)
- Long-prompt graceful handling
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.synapse import kb_cache
from core.synapse.engine import create_default_engine
from core.synapse.layers import (
    KBContextLayer,
    PromptContext,
    _extract_excerpt,
    _extract_wikilinks,
    _format_kb_block,
    _jaccard,
    _tokenize_for_jaccard,
)

FIXTURE_VAULT = Path(__file__).parent / "fixtures" / "synapse_vault"


# --- Helpers ----------------------------------------------------------------


class _FakeStore:
    """Minimal vector store stand-in used by L2.5 tests."""

    def __init__(self, hits: list[dict] | None = None, *, raises: bool = False) -> None:
        self._hits = hits or []
        self._raises = raises

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        if self._raises:
            raise RuntimeError("embedder unavailable")
        return list(self._hits)[:top_k]


@pytest.fixture(autouse=True)
def _isolate_marker_dir(tmp_path, monkeypatch):
    """Isolate the turn-scoped marker so tests never touch /tmp/arkaos-kb-query."""
    monkeypatch.setenv("ARKA_KB_QUERY_DIR", str(tmp_path / "kb-query"))
    yield


@pytest.fixture(autouse=True)
def _clear_feature_flag_env(monkeypatch):
    monkeypatch.delenv("ARKA_BYPASS_L25", raising=False)
    yield


@pytest.fixture
def session_ctx():
    return PromptContext(
        user_input="como funciona o synapse L2.5 e kb architecture",
        cwd="/tmp/test",
        git_branch="feature/intelligence-v2",
        extra={"session_id": "test-session-001"},
    )


@pytest.fixture
def fixture_vault_path() -> str:
    return str(FIXTURE_VAULT)


# --- Core layer behaviour ---------------------------------------------------


def test_l25_empty_vault_returns_none():
    layer = KBContextLayer(vector_store=None, vault_path=None)
    assert layer.build("anything") is None


def test_l25_low_similarity_returns_none():
    hits = [
        {"source": "/vault/a.md", "heading": "Alpha", "text": "# Alpha\n\nNothing.", "score": 0.1},
        {"source": "/vault/b.md", "heading": "Beta", "text": "# Beta\n\nNothing.", "score": 0.2},
    ]
    layer = KBContextLayer(vector_store=_FakeStore(hits), min_similarity=0.5)
    assert layer.build("unrelated query") is None


def test_l25_high_similarity_formats_block_correctly():
    hits = [
        {
            "source": "/vault/KB Architecture.md",
            "heading": "KB Architecture",
            "text": (
                "---\ntags:\n  - synapse\n---\n# KB Architecture\n\n"
                "Synapse L2.5 injects Obsidian KB context.\n"
                "Relates: [[Vector Store]], [[Embedder Setup]]."
            ),
            "score": 0.92,
        }
    ]
    layer = KBContextLayer(vector_store=_FakeStore(hits), min_similarity=0.5)
    block = layer.build("synapse L2.5 and KB architecture")
    assert block is not None
    assert block.startswith("[arka:kb-context]")
    assert "[[KB Architecture]]" in block
    assert "/vault/KB Architecture.md" in block
    assert "Vector Store" in block
    assert "Embedder Setup" in block
    assert "Consulta-as antes de ir a Context7/Web" in block


def test_l25_respects_max_notes():
    hits = [
        {
            "source": f"/vault/n{i}.md",
            "heading": f"Note {i}",
            "text": f"# Note {i}\n\nBody about synapse.",
            "score": 0.8,
        }
        for i in range(10)
    ]
    layer = KBContextLayer(vector_store=_FakeStore(hits), max_notes=3, min_similarity=0.5)
    block = layer.build("synapse")
    assert block is not None
    titles = [line for line in block.splitlines() if line.startswith("- [[")]
    assert len(titles) == 3


def test_l25_extracts_wikilinks_from_body():
    raw = (
        "# Title\n\nBody with [[Link One]] and [[Link Two|alias]] "
        "and [[Link Three]] and [[Link Four]]."
    )
    links = _extract_wikilinks(raw, limit=3)
    assert links == ["Link One", "Link Two", "Link Three"]


def test_l25_excerpt_is_first_two_body_lines():
    raw = "---\ntags: [x]\n---\n# Title\n\nFirst body line.\nSecond body line.\nThird body line."
    excerpt = _extract_excerpt(raw, max_lines=2)
    assert "First body line." in excerpt
    assert "Second body line." in excerpt
    assert "Third body line." not in excerpt


def test_l25_fallback_to_jaccard_when_embedder_fails(fixture_vault_path):
    store = _FakeStore(raises=True)
    layer = KBContextLayer(
        vector_store=store, vault_path=fixture_vault_path, min_similarity=0.05
    )
    block = layer.build("synapse layers architecture")
    assert block is not None
    assert "[arka:kb-context]" in block
    assert "[[Synapse Layers]]" in block or "[[KB Architecture]]" in block


def test_l25_records_obsidian_query_on_call(session_ctx, fixture_vault_path):
    layer = KBContextLayer(
        vector_store=None, vault_path=fixture_vault_path, min_similarity=0.05
    )
    result = layer.compute(session_ctx)
    assert result.content  # something injected
    record = kb_cache.read_obsidian_query(session_ctx.extra["session_id"])
    assert record is not None
    assert record["last_hit_count"] >= 1
    assert record["queries"][-1]["query"] == session_ctx.user_input


def test_l25_records_query_even_when_zero_hits(session_ctx):
    layer = KBContextLayer(vector_store=_FakeStore([]), vault_path=None)
    result = layer.compute(session_ctx)
    assert result.content == ""
    record = kb_cache.read_obsidian_query(session_ctx.extra["session_id"])
    assert record is not None
    assert record["last_hit_count"] == 0


def test_l25_feature_flag_off_skips_injection(monkeypatch, fixture_vault_path, session_ctx):
    monkeypatch.setenv("ARKA_BYPASS_L25", "1")
    layer = KBContextLayer(vector_store=None, vault_path=fixture_vault_path)
    assert layer.build("synapse layers") is None
    result = layer.compute(session_ctx)
    assert result.content == ""
    # No query recorded because layer returned early
    assert kb_cache.read_obsidian_query(session_ctx.extra["session_id"]) is None


def test_l25_feature_flag_false_in_config(monkeypatch, tmp_path, fixture_vault_path):
    cfg_dir = tmp_path / ".arkaos"
    cfg_dir.mkdir()
    (cfg_dir / "config.json").write_text(json.dumps({"synapse": {"l25KbContext": False}}), encoding="utf-8")
    monkeypatch.setattr(
        "core.synapse.layers_kb._KB_CONFIG_PATH", cfg_dir / "config.json"
    )
    layer = KBContextLayer(vector_store=None, vault_path=fixture_vault_path)
    assert layer.build("synapse layers") is None


def test_l25_long_prompt_graceful(fixture_vault_path):
    long_prompt = "synapse layers " * 500  # ~7000 chars
    layer = KBContextLayer(
        vector_store=None, vault_path=fixture_vault_path, min_similarity=0.01
    )
    # Must not raise
    block = layer.build(long_prompt)
    # Either returns a block or None; never raises.
    assert block is None or block.startswith("[arka:kb-context]")


def test_l25_ignores_hits_below_similarity_floor():
    hits = [
        {"source": "/a.md", "heading": "A", "text": "# A\n\nbody", "score": 0.95},
        {"source": "/b.md", "heading": "B", "text": "# B\n\nbody", "score": 0.30},
        {"source": "/c.md", "heading": "C", "text": "# C\n\nbody", "score": 0.80},
    ]
    layer = KBContextLayer(vector_store=_FakeStore(hits), min_similarity=0.5)
    block = layer.build("query")
    assert block is not None
    assert "[[A]]" in block
    assert "[[C]]" in block
    assert "[[B]]" not in block


def test_l25_block_contains_pt_pt_phrasing():
    hits = [
        {
            "source": "/a.md",
            "heading": "A",
            "text": "# A\n\nBody text line.",
            "score": 0.9,
        }
    ]
    layer = KBContextLayer(vector_store=_FakeStore(hits), min_similarity=0.5)
    block = layer.build("q")
    assert "O teu cérebro (Obsidian)" in block
    assert "Consulta-as antes de ir a Context7/Web" in block


def test_l25_empty_prompt_returns_none():
    layer = KBContextLayer(vector_store=_FakeStore([{"score": 0.9}]), min_similarity=0.5)
    assert layer.build("") is None


# --- Graphify graph-context pre-injection (opt-in, default OFF) --------------


def _point_graphify_config(monkeypatch, tmp_path, config: dict, keys: dict | None = None):
    cfg_dir = tmp_path / ".arkaos"
    cfg_dir.mkdir(exist_ok=True)
    (cfg_dir / "config.json").write_text(json.dumps(config), encoding="utf-8")
    monkeypatch.setattr("core.synapse.layers_kb._KB_CONFIG_PATH", cfg_dir / "config.json")
    keys_path = cfg_dir / "keys.json"
    if keys is not None:
        keys_path.write_text(json.dumps(keys), encoding="utf-8")
    monkeypatch.setattr("core.synapse.layers_kb._KEYS_PATH", keys_path)


def test_graphify_flag_off_by_default(monkeypatch, tmp_path):
    from core.synapse import layers_kb

    monkeypatch.delenv("ARKA_BYPASS_L25_GRAPHIFY", raising=False)
    _point_graphify_config(monkeypatch, tmp_path, {"synapse": {"l25KbContext": True}})
    assert layers_kb._l25_graphify_flag_on() is False
    assert layers_kb._graphify_context("synapse layers") == ""


def test_graphify_flag_on_via_config(monkeypatch, tmp_path):
    from core.synapse import layers_kb

    monkeypatch.delenv("ARKA_BYPASS_L25_GRAPHIFY", raising=False)
    _point_graphify_config(monkeypatch, tmp_path, {"synapse": {"l25Graphify": True}})
    assert layers_kb._l25_graphify_flag_on() is True


def test_graphify_context_empty_without_url_or_token(monkeypatch, tmp_path):
    from core.synapse import layers_kb

    monkeypatch.delenv("ARKA_BYPASS_L25_GRAPHIFY", raising=False)
    monkeypatch.delenv("GRAPHIFY_URL", raising=False)
    monkeypatch.delenv("GRAPHIFY_TOKEN", raising=False)
    # Flag on but nothing configured → no block, no error.
    _point_graphify_config(monkeypatch, tmp_path, {"synapse": {"l25Graphify": True}})
    assert layers_kb._graphify_context("synapse layers") == ""


def test_graphify_disabled_flag_forces_empty(monkeypatch, tmp_path):
    from core.synapse import layers_kb

    _point_graphify_config(
        monkeypatch, tmp_path,
        {"synapse": {"l25Graphify": True},
         "knowledge": {"graphify": {"enabled": False, "url": "http://x/mcp"}}},
        keys={"GRAPHIFY_TOKEN": "t"},
    )
    # graphify.enabled == False → resolver returns empty, no block.
    assert layers_kb._resolve_graphify() == ("", "")
    assert layers_kb._graphify_context("q") == ""


def test_graphify_fail_open_on_corrupt_config(monkeypatch, tmp_path, session_ctx):
    """A non-UTF-8 config.json must NOT escape as UnicodeDecodeError.

    QG blocker: UnicodeDecodeError is a ValueError, not a JSONDecodeError, so
    the old `except (json.JSONDecodeError, OSError)` let it propagate out of
    layer.compute — which Synapse does not guard — breaking all 12 layers for
    that turn. Both flag readers and compute must stay silent and fail open.
    """
    from core.synapse import layers_kb

    cfg_dir = tmp_path / ".arkaos"
    cfg_dir.mkdir(exist_ok=True)
    cfg = cfg_dir / "config.json"
    cfg.write_bytes(b'{"synapse": {"l25Graphify": true, "l25KbContext": \xff\xfe}}')
    monkeypatch.setattr("core.synapse.layers_kb._KB_CONFIG_PATH", cfg)
    monkeypatch.setattr("core.synapse.layers_kb._KEYS_PATH", cfg_dir / "keys.json")

    # Neither flag reader raises; both degrade to their documented default.
    assert layers_kb._l25_feature_flag_on() is True
    assert layers_kb._l25_graphify_flag_on() is False
    assert layers_kb._resolve_graphify() == ("", "")
    assert layers_kb._graphify_context("synapse layers") == ""

    # And the whole layer stays alive for the turn.
    layer = KBContextLayer(vector_store=_FakeStore([]), vault_path=None)
    result = layer.compute(session_ctx)  # must not raise
    assert result.content == ""


@pytest.mark.parametrize("payload", [
    '{"synapse": "yes"}',          # section is a str — .get would AttributeError
    "[1, 2, 3]",                   # root is a list
    '"just a string"',             # root is a scalar
    "null",                        # root is None
    '{"knowledge": {"graphify": 7}}',  # nested section is an int
])
def test_graphify_fail_open_on_non_object_config(monkeypatch, tmp_path, session_ctx, payload):
    """Well-formed JSON whose root/section is not an object must not raise.

    QG blocker (redo 1): broadening to `(ValueError, OSError)` covered the
    parse but left `data.get(...)` outside the try, so `{"synapse": "yes"}`
    still escaped as AttributeError through compute() and broke all 12
    layers for the turn.
    """
    from core.synapse import layers_kb

    cfg_dir = tmp_path / ".arkaos"
    cfg_dir.mkdir(exist_ok=True)
    cfg = cfg_dir / "config.json"
    cfg.write_text(payload, encoding="utf-8")
    monkeypatch.setattr("core.synapse.layers_kb._KB_CONFIG_PATH", cfg)
    monkeypatch.setattr("core.synapse.layers_kb._KEYS_PATH", cfg_dir / "keys.json")

    assert layers_kb._l25_feature_flag_on() is True
    assert layers_kb._l25_graphify_flag_on() is False
    assert layers_kb._resolve_graphify() == ("", "")
    assert layers_kb._graphify_context("synapse layers") == ""

    layer = KBContextLayer(vector_store=_FakeStore([]), vault_path=None)
    assert layer.compute(session_ctx).content == ""  # must not raise


def test_graphify_fail_open_on_unreachable(monkeypatch, tmp_path):
    from core.synapse import layers_kb

    monkeypatch.delenv("ARKA_BYPASS_L25_GRAPHIFY", raising=False)
    # Flag on + configured to a dead port → fail-open to "" with no raise.
    _point_graphify_config(
        monkeypatch, tmp_path,
        {"synapse": {"l25Graphify": True},
         "knowledge": {"graphify": {"enabled": True, "url": "http://127.0.0.1:1/mcp"}}},
        keys={"GRAPHIFY_TOKEN": "tok"},
    )
    # Must not raise, must return "".
    assert layers_kb._graphify_context("synapse layers") == ""


# --- Engine sequencing ------------------------------------------------------


def test_engine_sequences_l25_between_l2_l3():
    engine = create_default_engine(
        vector_store=_FakeStore([]),  # enables L2.5 registration
    )
    ids = [layer.id for layer in sorted(engine._layers, key=lambda x: x.priority)]
    assert "L2" in ids
    assert "L2.5" in ids
    assert "L3" in ids
    assert ids.index("L2") < ids.index("L2.5") < ids.index("L3")


def test_engine_skips_l25_when_no_store_and_no_vault():
    engine = create_default_engine()
    ids = [layer.id for layer in engine._layers]
    assert "L2.5" not in ids


def test_engine_registers_l25_with_vault_only(fixture_vault_path):
    engine = create_default_engine(kb_vault_path=fixture_vault_path)
    ids = [layer.id for layer in engine._layers]
    assert "L2.5" in ids


# --- Pure helpers -----------------------------------------------------------


def test_jaccard_zero_for_disjoint_sets():
    assert _jaccard({"a", "b"}, {"c", "d"}) == 0.0


def test_jaccard_one_for_identical_sets():
    assert _jaccard({"a", "b"}, {"a", "b"}) == 1.0


def test_tokenize_for_jaccard_drops_stopwords():
    tokens = _tokenize_for_jaccard("The quick brown fox and the lazy dog")
    assert "the" not in tokens
    assert "and" not in tokens
    assert "quick" in tokens
    assert "brown" in tokens


def test_format_kb_block_handles_single_note():
    notes = [{"title": "N", "path": "/p.md", "excerpt": "E", "relates": []}]
    block = _format_kb_block(notes)
    assert "1 nota relevante" in block
    assert "[[N]]" in block


def test_format_kb_block_handles_multiple_notes():
    notes = [
        {"title": "A", "path": "/a.md", "excerpt": "e", "relates": ["B"]},
        {"title": "B", "path": "/b.md", "excerpt": "e", "relates": []},
    ]
    block = _format_kb_block(notes)
    assert "2 notas relevantes" in block
    assert "[[A]]" in block and "[[B]]" in block


def test_load_fallback_notes_respects_cap(tmp_path, monkeypatch):
    """Large vaults must not blow the fallback loader: cap at 2000 notes."""
    from core.synapse import layers_kb

    # Temporarily lower the cap to a manageable number for this test —
    # the behaviour under test is the break-on-cap, not the exact value.
    monkeypatch.setattr(layers_kb, "_MAX_FALLBACK_NOTES", 10)

    for i in range(25):
        (tmp_path / f"note-{i:03d}.md").write_text(
            f"# Note {i}\n\nBody {i}.", encoding="utf-8"
        )

    notes = layers_kb._load_fallback_notes(tmp_path)
    assert len(notes) == 10, (
        "loader must stop at _MAX_FALLBACK_NOTES — got "
        f"{len(notes)} notes from 25 files"
    )


# --- QG redo 4: security + fail-open regressions ----------------------------


def test_graphify_url_validation_rejects_public_hosts(monkeypatch, tmp_path):
    """The Python side sends the token, so it validates the URL itself.

    QG blocker: `_resolve_graphify` read GRAPHIFY_URL straight from the env
    with no validation, so a public host received the operator's Bearer
    token. Prefix regexes on the hostname string were not enough either —
    `10.evil.example` is a domain anyone can register.
    """
    from core.synapse import layers_kb

    cfg_dir = tmp_path / ".arkaos"
    cfg_dir.mkdir(exist_ok=True)
    (cfg_dir / "config.json").write_text(json.dumps({}), encoding="utf-8")
    (cfg_dir / "keys.json").write_text(json.dumps({"GRAPHIFY_TOKEN": "sk-secret"}), encoding="utf-8")
    monkeypatch.setattr("core.synapse.layers_kb._KB_CONFIG_PATH", cfg_dir / "config.json")
    monkeypatch.setattr("core.synapse.layers_kb._KEYS_PATH", cfg_dir / "keys.json")

    rejected = [
        "http://10.evil.example/mcp",
        "http://127.evil.example/mcp",
        "http://192.168.evil.example/mcp",
        "http://172.16.evil.example/mcp",
        "http://evil.example.com/mcp",
        "http://8.8.8.8/mcp",
        "http://[2001:db8::1]/mcp",
        "ftp://host/mcp",
    ]
    for url in rejected:
        monkeypatch.setenv("GRAPHIFY_URL", url)
        assert layers_kb._resolve_graphify() == ("", ""), f"{url} must not receive a token"

    accepted = [
        "https://graph.example.com/mcp",
        "http://localhost:8080/mcp",
        "http://127.0.0.1:8080/mcp",
        "http://192.168.1.13:8080/mcp",
        "http://10.0.0.5/mcp",
        "http://172.16.0.1/mcp",
        # NOTE: LAN names (nas.local, lab) are deliberately absent — the
        # Python guard RESOLVES names, so an unresolvable one yields no
        # endpoint. That asymmetry with the JS twin is covered, with its
        # rationale, in tests/python/test_graphify_url_parity.py.
        "http://[::1]:8080/mcp",
    ]
    for url in accepted:
        monkeypatch.setenv("GRAPHIFY_URL", url)
        got_url, got_token = layers_kb._resolve_graphify()
        assert got_url == url, f"{url} must resolve"
        assert got_token == "sk-secret"


def test_graphify_post_refuses_redirects():
    """urllib copies Authorization across a redirect — so refuse redirects.

    QG blocker: reproduced end-to-end, a 302 from the graph server forwarded
    `Bearer <token>` to the attacker host and its body came back as context.
    """
    from core.synapse import layers_kb

    opener_handlers = layers_kb.urllib.request.build_opener(
        layers_kb._NoRedirect
    ).handlers
    assert any(isinstance(h, layers_kb._NoRedirect) for h in opener_handlers)
    # The handler refuses every redirect by returning None.
    assert layers_kb._NoRedirect().redirect_request(
        None, None, 302, "Found", {}, "http://attacker.example/"
    ) is None


def test_read_json_dict_survives_deeply_nested_json(tmp_path, monkeypatch, session_ctx):
    """RecursionError is neither ValueError nor OSError — it escaped.

    QG blocker: a deeply nested config.json propagated RecursionError out of
    layer.compute, which Synapse does not wrap, killing all 12 layers.
    """
    from core.synapse import layers_kb

    cfg_dir = tmp_path / ".arkaos"
    cfg_dir.mkdir(exist_ok=True)
    cfg = cfg_dir / "config.json"
    cfg.write_text("[" * 60_000 + "]" * 60_000, encoding="utf-8")
    monkeypatch.setattr("core.synapse.layers_kb._KB_CONFIG_PATH", cfg)
    monkeypatch.setattr("core.synapse.layers_kb._KEYS_PATH", cfg_dir / "keys.json")

    assert layers_kb._read_json_dict(cfg) == {}
    assert layers_kb._l25_feature_flag_on() is True
    layer = KBContextLayer(vector_store=_FakeStore([]), vault_path=None)
    assert layer.compute(session_ctx).content == ""  # must not raise


# --- Graphify happy path against a real local MCP stub (QG M1) --------------


@pytest.fixture
def graphify_stub():
    """A loopback HTTP server speaking just enough MCP for query_graph."""
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    seen: list[dict] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", 0) or 0))
            try:
                req = json.loads(body or b"{}")
            except ValueError:
                req = {}
            seen.append({"method": req.get("method"),
                         "auth": self.headers.get("Authorization", "")})
            if req.get("method") == "initialize":
                self.send_response(200)
                self.send_header("Mcp-Session-Id", "sess-42")
                self.send_header("Content-Type", "application/json")
                payload = b'{"jsonrpc":"2.0","id":1,"result":{}}'
            elif req.get("method") == "tools/call":
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                payload = (
                    b'data: {"jsonrpc":"2.0","id":2,"result":{"content":'
                    b'[{"type":"text","text":"node: ArkaOS -> Synapse"}]}}\n\n'
                )
            else:  # notifications/initialized
                self.send_response(202)
                payload = b""
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            if payload:
                self.wfile.write(payload)

        def log_message(self, *args):  # silence the default stderr logging
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}/mcp", seen
    server.shutdown()
    server.server_close()


def test_graphify_query_parses_a_real_sse_response(graphify_stub):
    """The success path: handshake, tools/call, SSE parse. Previously untested."""
    from core.synapse import layers_kb

    url, seen = graphify_stub
    text = layers_kb._graphify_query("how does synapse work", url, "tok-123")

    assert text == "node: ArkaOS -> Synapse"
    assert [c["method"] for c in seen] == [
        "initialize", "notifications/initialized", "tools/call",
    ]
    assert all(c["auth"] == "Bearer tok-123" for c in seen)


def test_graphify_context_formats_the_remote_block(monkeypatch, tmp_path, graphify_stub):
    """End-to-end: flag on + configured endpoint -> a labelled remote block."""
    from core.synapse import layers_kb

    url, _ = graphify_stub
    cfg_dir = tmp_path / ".arkaos"
    cfg_dir.mkdir(exist_ok=True)
    (cfg_dir / "config.json").write_text(json.dumps({
        "synapse": {"l25Graphify": True},
        "knowledge": {"graphify": {"enabled": True, "url": url}},
    }), encoding="utf-8")
    (cfg_dir / "keys.json").write_text(json.dumps({"GRAPHIFY_TOKEN": "tok-123"}), encoding="utf-8")
    monkeypatch.setattr("core.synapse.layers_kb._KB_CONFIG_PATH", cfg_dir / "config.json")
    monkeypatch.setattr("core.synapse.layers_kb._KEYS_PATH", cfg_dir / "keys.json")
    monkeypatch.delenv("ARKA_BYPASS_L25_GRAPHIFY", raising=False)
    monkeypatch.delenv("GRAPHIFY_URL", raising=False)

    block = layers_kb._graphify_context("how does synapse work")
    assert block.startswith("[arka:graph-remote unverified]")
    assert "node: ArkaOS -> Synapse" in block


def test_graphify_layer_tags_and_delivers_the_block(
    monkeypatch, tmp_path, graphify_stub, session_ctx,
):
    """compute() must emit BOTH the +graph tag and the block it announces."""

    url, _ = graphify_stub
    cfg_dir = tmp_path / ".arkaos"
    cfg_dir.mkdir(exist_ok=True)
    (cfg_dir / "config.json").write_text(json.dumps({
        "synapse": {"l25Graphify": True},
        "knowledge": {"graphify": {"enabled": True, "url": url}},
    }), encoding="utf-8")
    (cfg_dir / "keys.json").write_text(json.dumps({"GRAPHIFY_TOKEN": "tok-123"}), encoding="utf-8")
    monkeypatch.setattr("core.synapse.layers_kb._KB_CONFIG_PATH", cfg_dir / "config.json")
    monkeypatch.setattr("core.synapse.layers_kb._KEYS_PATH", cfg_dir / "keys.json")
    monkeypatch.delenv("ARKA_BYPASS_L25_GRAPHIFY", raising=False)
    monkeypatch.delenv("GRAPHIFY_URL", raising=False)

    result = KBContextLayer(vector_store=_FakeStore([]), vault_path=None).compute(session_ctx)
    assert "+graph" in result.tag, "the tag must announce the injection"
    assert "node: ArkaOS -> Synapse" in result.content, "and the block must be there"
