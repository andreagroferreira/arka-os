"""L2.5 KB Context layer (Obsidian) — extracted from layers.py.

Semantic + keyword retrieval over the operator's Obsidian vault with a
grounding policy that quarantines inferred (Dreaming-written) notes.
All names are re-exported by core.synapse.layers for backward
compatibility — import from there unless you need the module itself.
"""

import contextlib
import json
import os
import re
import time
import urllib.request
from pathlib import Path
from typing import Any

from core.synapse.layers_base import Layer, LayerResult, PromptContext

_WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:\|[^\]]+)?\]\]")
_FRONTMATTER_RE = re.compile(r"^---\n.*?\n---\n", re.DOTALL)
_KB_CONFIG_PATH = Path.home() / ".arkaos" / "config.json"
# Cap fallback-note scanning to avoid O(vault size) blow-ups on large
# Obsidian vaults. The cap is above any realistic top-N retrieval need
# (Jaccard ranks the top few notes; scanning 2000 sorted-by-name first
# is plenty — see `_load_fallback_notes`) while still bounding worst-case latency.
_MAX_FALLBACK_NOTES = 2000
# A config.json past this is not a config — refuse it rather than parse it
# inside the Synapse budget. 4 MiB is ~1000x the real file.
_MAX_CONFIG_BYTES = 4 * 1024 * 1024
_KB_STOPWORDS: frozenset[str] = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for", "of",
    "with", "by", "from", "as", "is", "was", "are", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "should", "could",
    "may", "might", "must", "can", "this", "that", "these", "those", "it", "its",
    "about", "into", "over", "under", "up", "down", "out", "than", "then", "so",
    "if", "because", "while", "where", "when", "what", "which", "who", "whom",
    "how", "why", "all", "some", "any", "no", "not", "very", "just", "also",
})


def _read_json_dict(path: Path) -> dict:
    """Parse ``path`` into a dict, or ``{}``. The single never-raises reader.

    Synapse does not wrap ``layer.compute``, so ANY exception escaping a
    config read breaks all 12 layers for the turn. Three failure modes are
    covered together, which is why this is one helper and not three
    try/excepts: OSError (unreadable), ValueError (bad JSON *and* the
    UnicodeDecodeError a non-UTF-8 file raises), and RecursionError (deeply
    nested JSON — neither of the other two, and it escaped in QG review).

    A fourth case needs no ``except`` at all: well-formed JSON whose root is
    not an object — ``[1,2,3]`` or ``"yes"`` — would raise AttributeError on
    the first ``.get``, so the return is isinstance-guarded instead.
    """
    try:
        # is_file() excludes a FIFO, whose read_text() blocks FOREVER with no
        # exception for the net below to catch (QG review). The size cap keeps
        # a huge file from stalling the ~87ms budget. Both are stat-only.
        if not path.is_file() or path.stat().st_size > _MAX_CONFIG_BYTES:
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError, RecursionError):
        return {}
    return data if isinstance(data, dict) else {}


def _section(data: dict, key: str) -> dict:
    """A dict-valued section of a config, or ``{}`` — never raises."""
    value = data.get(key)
    return value if isinstance(value, dict) else {}


def _l25_feature_flag_on() -> bool:
    if os.environ.get("ARKA_BYPASS_L25", "").strip() == "1":
        return False
    if not _KB_CONFIG_PATH.exists():
        return True
    synapse_cfg = _section(_read_json_dict(_KB_CONFIG_PATH), "synapse")
    return bool(synapse_cfg.get("l25KbContext", True))


# --- Graphify graph-context pre-injection (opt-in, default OFF) ------------
# The knowledge graph is a per-user HTTP endpoint. Pre-injecting it costs up
# to THREE bounded round-trips (initialize → initialized → tools/call), i.e.
# ~3x _GRAPHIFY_TIMEOUT_S worst case against a ~87ms Synapse budget. That is
# why it is OFF by default (synapse.l25Graphify) and always fail-open: any
# missing config, corrupt config, unreachable host, or slow response yields
# no block and never raises.
_KEYS_PATH = Path.home() / ".arkaos" / "keys.json"
_GRAPHIFY_TIMEOUT_S = 0.3


def _l25_graphify_flag_on() -> bool:
    if os.environ.get("ARKA_BYPASS_L25_GRAPHIFY", "").strip() == "1":
        return False
    if not _KB_CONFIG_PATH.exists():
        return False
    synapse_cfg = _section(_read_json_dict(_KB_CONFIG_PATH), "synapse")
    return bool(synapse_cfg.get("l25Graphify", False))


# The exact ranges ``isPrivateHost`` in installer/graphify.js accepts. Kept
# as literals rather than ``ip.is_private`` (a strict superset: 0.0.0.0/8,
# TEST-NET-1/2/3, 240/4, 255.255.255.255 …) so the two implementations cannot
# drift — tests/python/test_graphify_url_parity.py drives one shared corpus
# through both and fails on any divergence.
_PRIVATE_V4 = ("127.0.0.0/8", "10.0.0.0/8", "192.168.0.0/16",
               "172.16.0.0/12", "169.254.0.0/16")
_PRIVATE_V6 = ("::1/128", "fc00::/7", "fe80::/10")
# A whole-host label that is a bare number or 0x-hex, or any dotted form with
# a 0-prefixed (octal) octet: 134744072, 0x08080808, 0177.0.0.1.
_OBFUSCATED_IP_RE = re.compile(r"^(?:0[xX][0-9a-fA-F]+|\d+)$|(?:^|\.)0\d")


def _ip_is_private(ip: Any) -> bool:
    """Membership in the explicit private ranges — no is_private shortcut."""
    import ipaddress

    nets = _PRIVATE_V6 if ip.version == 6 else _PRIVATE_V4
    return any(ip in ipaddress.ip_network(n) for n in nets)


def _is_private_host(raw_host: str) -> bool:
    """True only for hosts that cannot reach a public endpoint.

    Python mirror of ``isPrivateHost`` in ``installer/graphify.js`` — and the
    side that resolves the name before opening the socket, so it validates
    independently of any registration-time check. It is NOT the only sender:
    ``registerGraphifyHttpMcp`` hands the same token to Claude Code, which
    then talks to the endpoint on every session (installer/graphify.js).

    A NAME is resolved rather than pattern-matched. Judging the string alone
    let ``http://134744072/`` through (8.8.8.8 in decimal is a single-label
    "name" with no dot) and the token went out over plaintext HTTP — captured
    in QG review. Resolving also closes hex literals and DNS rebinding, since
    every returned address must be private.
    """
    import ipaddress
    import socket

    host = raw_host.strip()
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]
    host = host.rstrip(".")  # trailing-dot FQDN is the same host
    if not host:
        return False
    if "%" in host:  # IPv6 zone-id: strip before parsing
        host = host.split("%", 1)[0]
    # Obfuscated IP encodings (decimal 134744072, hex 0x08080808, octal
    # 0177.0.0.1) have no legitimate use in a configured endpoint and are the
    # classic filter bypass. Rejected outright, matching the JS twin, rather
    # than resolved — even when they decode to a private address.
    if _OBFUSCATED_IP_RE.match(host):
        return False

    try:
        return _ip_is_private(ipaddress.ip_address(host))
    except ValueError:
        pass

    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except (OSError, UnicodeError):
        return False  # unresolvable → never send a credential to it
    if not infos:
        return False
    for info in infos:
        try:
            addr = ipaddress.ip_address(info[4][0].split("%", 1)[0])
        except ValueError:
            return False
        if not _ip_is_private(addr):
            return False  # ANY public answer disqualifies the name
    return True


def _valid_graphify_url(raw: str) -> str:
    """``raw`` when safe to send a credential to, else ''."""
    if not raw:
        return ""
    from urllib.parse import urlsplit

    try:
        parts = urlsplit(raw)
    except ValueError:
        return ""
    if parts.scheme == "https":
        return raw
    if parts.scheme != "http" or not parts.hostname:
        return ""
    return raw if _is_private_host(parts.hostname) else ""


def _resolve_graphify() -> tuple[str, str]:
    """(url, token) from config.json + keys.json + env. Empty when unset.

    The URL is validated here and not only in the installer: an unvalidated
    endpoint plus a token from keys.json is credential redirection, and this
    function reads ``GRAPHIFY_URL`` straight from the environment.
    """
    url = os.environ.get("GRAPHIFY_URL", "").strip()
    token = os.environ.get("GRAPHIFY_TOKEN", "").strip()
    gcfg = _section(_section(_read_json_dict(_KB_CONFIG_PATH), "knowledge"), "graphify")
    if gcfg.get("enabled") is False:
        return "", ""
    url = _valid_graphify_url(url or str(gcfg.get("url") or "").strip())
    if not url:
        return "", ""
    if not token and _KEYS_PATH.exists():
        token = str(_read_json_dict(_KEYS_PATH).get("GRAPHIFY_TOKEN") or "").strip()
    return url, token


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse every redirect.

    urllib copies non-content headers across a redirect, so a 302 from the
    graph server would forward ``Authorization: Bearer <token>`` to whatever
    host it names — reproduced end-to-end in QG review. An MCP endpoint has
    no legitimate reason to redirect, so the safe answer is to never follow.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _graphify_post(url: str, headers: dict, payload: dict, extra: dict | None = None):
    """One bounded MCP POST. Raises on transport failure — callers guard."""
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={**headers, **(extra or {})})
    opener = urllib.request.build_opener(_NoRedirect)
    return opener.open(req, timeout=_GRAPHIFY_TIMEOUT_S)


def _graphify_open_session(url: str, headers: dict) -> dict:
    """Initialize the MCP session; returns the session-id header dict."""
    init = {
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05", "capabilities": {},
            "clientInfo": {"name": "synapse-l25", "version": "1.0"},
        },
    }
    with _graphify_post(url, headers, init) as resp:
        session_id = resp.headers.get("Mcp-Session-Id", "")
    sid_header = {"Mcp-Session-Id": session_id} if session_id else {}
    # Some MCP servers require the initialized notification before a
    # tools/call; servers that do not need it ignore the extra request.
    with contextlib.suppress(Exception):
        _graphify_post(
            url, headers,
            {"jsonrpc": "2.0", "method": "notifications/initialized"}, sid_header,
        ).close()
    return sid_header


def _graphify_parse_sse(raw: str) -> dict | None:
    """First JSON object in an SSE or plain JSON-RPC response body."""
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped.startswith("data:"):
            stripped = stripped[5:].strip()
        if not stripped:
            continue
        try:
            return json.loads(stripped)
        except ValueError:
            continue
    return None


def _graphify_query(prompt: str, url: str, token: str) -> str | None:
    """Best-effort MCP `query_graph` over streamable HTTP. Never raises.

    Returns the graph text-context, or None on any failure/timeout. Each of
    the up-to-three requests is bounded by ``_GRAPHIFY_TIMEOUT_S``, so a fully
    unresponsive endpoint costs ~3x that before this gives up and falls open.
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    try:
        sid_header = _graphify_open_session(url, headers)
        call = {
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "query_graph", "arguments": {"query": prompt[:200]}},
        }
        with _graphify_post(url, headers, call, sid_header) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        data = _graphify_parse_sse(raw)
        if not data:
            return None
        content = (data.get("result") or {}).get("content") or []
        texts = [c.get("text", "") for c in content if c.get("type") == "text"]
        return "\n".join(t for t in texts if t).strip() or None
    except Exception:
        return None


def _graphify_context(prompt: str) -> str:
    """Formatted ``[arka:graph-remote]`` block, or '' — fail-open.

    Deliberately NOT ``[arka:graph-context]``: L2.7 GraphContextLayer already
    owns that marker for the LOCAL graph, under a stricter contract (never
    truncates a source location, never injects AMBIGUOUS nodes). This block
    comes from a remote server, is not confidence-filtered, and is clipped to
    a byte budget — same marker, contradictory guarantees, so it gets its own.
    """
    if not prompt or not _l25_graphify_flag_on():
        return ""
    url, token = _resolve_graphify()
    if not url or not token:
        return ""
    text = _graphify_query(prompt, url, token)
    if not text:
        return ""
    excerpt = text[:600].rstrip()
    return f"[arka:graph-remote unverified]\n{excerpt}\n"


def _tokenize_for_jaccard(text: str) -> set[str]:
    if not text:
        return set()
    words = re.findall(r"[a-zA-Z0-9]{3,}", text.lower())
    return {w for w in words if w not in _KB_STOPWORDS}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _extract_note_body(raw: str) -> str:
    return _FRONTMATTER_RE.sub("", raw, count=1).lstrip()


def _extract_title(raw: str, fallback: str) -> str:
    body = _extract_note_body(raw)
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip() or fallback
        if stripped:
            return fallback
    return fallback


def _extract_excerpt(raw: str, max_lines: int = 2) -> str:
    body = _extract_note_body(raw)
    lines: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        lines.append(stripped)
        if len(lines) >= max_lines:
            break
    return " ".join(lines)[:240]


def _extract_wikilinks(raw: str, limit: int = 3) -> list[str]:
    body = _extract_note_body(raw)
    seen: list[str] = []
    for match in _WIKILINK_RE.finditer(body):
        target = match.group(1).strip()
        if target and target not in seen:
            seen.append(target)
        if len(seen) >= limit:
            break
    return seen


def _format_kb_block(notes: list[dict], degraded: bool = False) -> str:
    lines: list[str] = [
        f"[arka:kb-context] O teu cérebro (Obsidian) tem {len(notes)} "
        f"nota{'s' if len(notes) != 1 else ''} relevante{'s' if len(notes) != 1 else ''} "
        f"para este pedido:",
        "",
    ]
    if degraded:
        lines.insert(1, "")
        lines.insert(
            1,
            "Atenção: correspondência por palavras-chave (pesquisa semântica "
            "indisponível) — NÃO é similaridade semântica.",
        )
    for note in notes:
        title = note.get("title", "")
        path = note.get("path", "")
        excerpt = note.get("excerpt", "")
        relates = note.get("relates", []) or []
        # Deliberately pt-PT: this block is operator-facing and every other
        # string in it is pt-PT (header, Excerto, Relacionada, the degraded
        # warning). The label was the lone English fragment. The RAG-honesty
        # contract is unchanged — only the wording — and the two assertions
        # guarding it in test_rag_honesty.py were updated in the same change
        # for that reason, not to make a failing test pass.
        suffix = " (inferida — não autoritativa)" if note.get("inferred") else ""
        lines.append(f"- [[{title}]]{suffix} (path: `{path}`)")
        if excerpt:
            lines.append(f"  Excerto: {excerpt}")
        if relates:
            rel = ", ".join(f"[[{r}]]" for r in relates)
            lines.append(f"  Relacionada: {rel}")
        lines.append("")
    lines.append(
        "Consulta-as antes de ir a Context7/Web. Se preencherem o pedido, "
        "usa-as e cita. Se tiverem lacuna, investiga externamente e "
        "documenta de volta."
    )
    return "\n".join(lines).strip()


def _vector_search(store: Any, prompt: str, top_k: int) -> list[dict]:
    if store is None:
        return []
    try:
        return list(store.search(prompt, top_k=top_k)) or []
    except Exception:
        return []


def _jaccard_fallback(
    prompt: str, notes: list[dict], top_k: int, threshold: float
) -> list[dict]:
    prompt_tokens = _tokenize_for_jaccard(prompt)
    scored: list[tuple[float, dict]] = []
    for note in notes:
        title_tokens = _tokenize_for_jaccard(note.get("title", ""))
        score = _jaccard(prompt_tokens, title_tokens)
        if score >= threshold:
            scored.append((score, note))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [n for _, n in scored[:top_k]]


def _load_fallback_notes(vault_path: Path | None) -> list[dict]:
    if vault_path is None or not vault_path.exists() or not vault_path.is_dir():
        return []
    notes: list[dict] = []
    for md in sorted(vault_path.rglob("*.md")):
        if len(notes) >= _MAX_FALLBACK_NOTES:
            break
        try:
            raw = md.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        notes.append(
            {
                "title": _extract_title(raw, md.stem),
                "path": str(md),
                "raw": raw,
            }
        )
    return notes


_GROUNDING_INFERRED_RE = re.compile(r"^grounding:\s*inferred\s*$", re.MULTILINE)


def _frontmatter_marks_inferred(raw: str) -> bool:
    """Cheap check: does the YAML frontmatter carry `grounding: inferred`?

    Parses ONLY the frontmatter block (the note content is already in
    hand) — no YAML library, no full-document scan. Dreaming-written
    notes carry this marker (see core/cognition/dreaming.py, PR-3 v4.1).
    """
    match = _FRONTMATTER_RE.match(raw or "")
    if not match:
        return False
    return bool(_GROUNDING_INFERRED_RE.search(match.group(0)))


def _hit_is_inferred(hit: dict) -> bool:
    """Inferred check for a vector-store hit.

    Chunk text has frontmatter stripped by the chunker, so check the hit
    metadata first, then read just the head of the source file (cheap:
    frontmatter lives in the first bytes).
    """
    metadata = hit.get("metadata") or {}
    if isinstance(metadata, dict) and metadata.get("grounding") == "inferred":
        return True
    source = hit.get("source", "") or ""
    if not source:
        return False
    try:
        with open(source, encoding="utf-8", errors="ignore") as fh:
            head = fh.read(2048)
    except OSError:
        return False
    return _frontmatter_marks_inferred(head)


def _build_note_entry(
    raw: str, title: str, path: str, score: float, inferred: bool = False
) -> dict:
    return {
        "title": title,
        "path": path,
        "excerpt": _extract_excerpt(raw),
        "relates": _extract_wikilinks(raw),
        "score": float(score),
        "inferred": inferred,
    }


def _note_from_vector_hit(hit: dict) -> dict:
    source = hit.get("source", "") or ""
    raw = hit.get("text", "") or ""
    title = hit.get("heading") or Path(source).stem or "note"
    score_val = hit.get("score", 0.0) or 0.0
    return _build_note_entry(
        raw, str(title), str(source), float(score_val),
        inferred=_hit_is_inferred(hit),
    )


def _apply_grounding_policy(notes: list[dict], max_notes: int) -> list[dict]:
    """Quarantine inferred notes (Dreaming output) from grounded context.

    Policy (PR-3 v4.1): inferred notes are EXCLUDED by default; they are
    only included — explicitly suffixed `(inferida — não autoritativa)`
    by the formatter — when fewer than 2 grounded notes matched.
    """
    grounded = [n for n in notes if not n.get("inferred")]
    if len(grounded) >= 2:
        return grounded[:max_notes]
    inferred = [n for n in notes if n.get("inferred")]
    return (grounded + inferred)[:max_notes]


class KBContextLayer(Layer):
    """L2.5: Obsidian KB context injection before the model thinks.

    Design (see plan ``2026-04-20-intelligence-v2.md``):
      1. Semantic search the user prompt against the vector store.
      2. If store empty or embedder unavailable, fall back to Jaccard
         keyword similarity against cached note titles.
      3. Keep notes with similarity ≥ ``min_similarity`` (default 0.5),
         up to ``max_notes``.
      4. Format as ``[arka:kb-context]`` block with title, path, 2-line
         excerpt, and top 3 wikilinks per note.
      5. Call ``record_obsidian_query`` so research_gate (Task #6) can
         verify KB-first was respected this turn.

    Feature flag: ``synapse.l25KbContext`` in ``~/.arkaos/config.json``
    (default ``true``). ``ARKA_BYPASS_L25=1`` env disables for debugging.
    """

    def __init__(
        self,
        vector_store: Any = None,
        vault_path: str | None = None,
        max_notes: int = 5,
        min_similarity: float = 0.5,
    ) -> None:
        self._store = vector_store
        self._vault_path = Path(vault_path) if vault_path else None
        self._max_notes = max_notes
        self._min_similarity = min_similarity

    @property
    def id(self) -> str:
        return "L2.5"

    @property
    def name(self) -> str:
        return "KBContext"

    @property
    def input_sensitive(self) -> bool:
        return True

    @property
    def cache_ttl(self) -> int:
        return 0

    @property
    def emits_block(self) -> bool:
        """Content is the self-naming [arka:kb-context] / graph block."""
        return True

    @property
    def priority(self) -> int:
        return 25

    def _empty(self, start: float) -> LayerResult:
        ms = int((time.time() - start) * 1000)
        return LayerResult(
            layer_id=self.id, tag="", content="", tokens_est=0, compute_ms=ms, cached=False
        )

    def _session_id(self, ctx: PromptContext) -> str:
        return ctx.extra.get("session_id", "") if ctx.extra else ""

    def _record(self, ctx: PromptContext, hit_count: int) -> None:
        session_id = self._session_id(ctx)
        if not session_id:
            return
        try:
            from core.synapse.kb_cache import record_obsidian_query

            record_obsidian_query(session_id, ctx.user_input, hit_count)
        except Exception:
            pass

    def _retrieve(self, prompt: str) -> tuple[list[dict], bool]:
        """Return (notes, degraded). Degraded = keyword-only retrieval.

        Degraded hits carry no similarity score, so the min_similarity
        threshold does not apply to them — they are included but labeled
        (never presented as semantic matches).
        """
        hits = _vector_search(self._store, prompt, top_k=self._max_notes * 2)
        degraded = any(h.get("retrieval") == "keyword-degraded" for h in hits)
        notes: list[dict] = []
        for h in hits:
            if not degraded:
                score = float(h.get("score", 0.0) or 0.0)
                if score < self._min_similarity:
                    continue
            notes.append(_note_from_vector_hit(h))
        notes = _apply_grounding_policy(notes, self._max_notes)
        if notes:
            return notes, degraded
        candidates = _load_fallback_notes(self._vault_path)
        if not candidates:
            return [], False
        picked = _jaccard_fallback(
            prompt, candidates, self._max_notes * 2, self._min_similarity
        )
        fallback_notes = [
            _build_note_entry(
                n["raw"], n["title"], n["path"], 0.0,
                inferred=_frontmatter_marks_inferred(n["raw"]),
            )
            for n in picked
        ]
        return _apply_grounding_policy(fallback_notes, self._max_notes), False

    def build(self, prompt: str) -> str | None:
        """Public entrypoint — returns the formatted block or None."""
        if not prompt or not _l25_feature_flag_on():
            return None
        notes, degraded = self._retrieve(prompt[:2000])
        if not notes:
            return None
        return _format_kb_block(notes[: self._max_notes], degraded=degraded)

    def _safe_graph_block(self, prompt: str) -> str:
        """Graphify block, or ''. Guarded: Synapse does not wrap compute."""
        try:
            return _graphify_context(prompt)
        except Exception:
            return ""

    def _render(self, notes: list[dict], degraded: bool, graph_block: str) -> tuple[str, str]:
        """(content, tag) for the assembled KB + graph context."""
        parts = []
        if notes:
            parts.append(_format_kb_block(notes[: self._max_notes], degraded=degraded))
        if graph_block:
            parts.append(graph_block)
        tag = (
            f"[kb-context:{len(notes)} degraded=keyword]" if degraded
            else f"[kb-context:{len(notes)}]"
        )
        if graph_block:
            tag = f"{tag[:-1]} +graph]"
        return "\n".join(parts), tag

    def compute(self, ctx: PromptContext) -> LayerResult:
        start = time.time()
        if not ctx.user_input or not _l25_feature_flag_on():
            return self._empty(start)
        try:
            notes, degraded = self._retrieve(ctx.user_input[:2000])
        except Exception:
            return self._empty(start)
        self._record(ctx, len(notes))
        # Graphify graph-context is opt-in (default OFF) — a cheap no-op when
        # the flag is off, and always fail-open so it never blocks Obsidian.
        graph_block = self._safe_graph_block(ctx.user_input[:2000])
        if not notes and not graph_block:
            return self._empty(start)
        block, tag = self._render(notes, degraded, graph_block)
        return LayerResult(
            layer_id=self.id,
            tag=tag,
            content=block,
            tokens_est=len(block.split()),
            compute_ms=int((time.time() - start) * 1000),
            cached=False,
        )
