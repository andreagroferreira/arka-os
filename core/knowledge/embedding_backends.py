"""Multi-backend embedding abstraction (F1-A1 — memory/learning reform).

Ordered auto-resolution, never a hardcoded single backend:
    1. ``fastembed`` — local, delegates to the existing embedder.py
    2. ``ollama``    — local ``/api/embed`` endpoint (stdlib urllib)
    3. ``none``      — no embedding available; consumers must label
                       retrieval as ``keyword-degraded`` (the exact
                       honesty contract of vector_store.py)

Outside the auto chain: ``api`` (OpenAI-compatible endpoint) is
EXPLICIT OPT-IN ONLY (cost/privacy) — never chosen by ``auto``, and
refused over plaintext http except to loopback hosts.

Backend selection (env > config > default):
    1. ``ARKA_EMBED_BACKEND`` env var
    2. ``memory.embedBackend`` in ``~/.arkaos/config.json``
    3. default ``auto``

Every result declares its ``backend`` — a vector is never presented
without saying where it came from.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel

from core.knowledge import embedder

logger = logging.getLogger(__name__)

BackendName = Literal["fastembed", "ollama", "api", "none"]

DEFAULT_OLLAMA_HOST = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "nomic-embed-text"
DEFAULT_API_BASE = "https://api.openai.com"
DEFAULT_API_MODEL = "text-embedding-3-small"
_OLLAMA_TIMEOUT_S = 2.0
_API_TIMEOUT_S = 10.0

# Probe results cached per process — resolution must stay cheap on hooks.
_resolved_backend: Optional[BackendName] = None
_ollama_available: Optional[bool] = None


class EmbeddingResult(BaseModel):
    """An embedding that declares its own provenance."""

    vector: Optional[list[float]] = None
    backend: BackendName = "none"
    model: str = ""
    dims: int = 0


def _memory_config() -> dict:
    config_path = Path.home() / ".arkaos" / "config.json"
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
        section = data.get("memory")
        return section if isinstance(section, dict) else {}
    except (OSError, json.JSONDecodeError, AttributeError):
        return {}


def get_backend_name() -> str:
    """Configured backend name (env > config > ``auto``) — unresolved."""
    env_name = os.environ.get("ARKA_EMBED_BACKEND", "").strip().lower()
    if env_name:
        return env_name
    configured = _memory_config().get("embedBackend", "")
    if isinstance(configured, str) and configured.strip():
        return configured.strip().lower()
    return "auto"


def _ollama_host() -> str:
    host = _memory_config().get("ollamaHost", "")
    if isinstance(host, str) and host.strip():
        return host.strip()
    return os.environ.get("OLLAMA_HOST", DEFAULT_OLLAMA_HOST)


def _ollama_model() -> str:
    model = _memory_config().get("embedModel", "")
    if isinstance(model, str) and model.strip():
        return model.strip()
    return DEFAULT_OLLAMA_MODEL


def _probe_ollama(host: str) -> bool:
    """One reachability probe per process — hooks must never pay twice."""
    global _ollama_available
    if _ollama_available is not None:
        return _ollama_available
    url = f"{host.rstrip('/')}/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=_OLLAMA_TIMEOUT_S) as resp:
            _ollama_available = resp.status == 200
    except (urllib.error.URLError, OSError, ValueError):
        _ollama_available = False
    return _ollama_available


def resolve_backend() -> BackendName:
    """Resolve the configured name to a concrete, usable backend.

    ``auto`` probes fastembed → ollama → none. ``api`` is honored only
    when explicitly configured AND a key exists; otherwise degrades to
    ``none`` (honestly, never silently to a paid default).
    """
    global _resolved_backend
    if _resolved_backend is not None:
        return _resolved_backend
    name = get_backend_name()
    if name == "fastembed":
        _resolved_backend = "fastembed" if embedder.is_available() else "none"
    elif name == "ollama":
        _resolved_backend = "ollama" if _probe_ollama(_ollama_host()) else "none"
    elif name == "api":
        _resolved_backend = "api" if _api_key() else "none"
    elif name == "none":
        _resolved_backend = "none"
    else:  # auto (and unknown names degrade to auto semantics)
        if embedder.is_available():
            _resolved_backend = "fastembed"
        elif _probe_ollama(_ollama_host()):
            _resolved_backend = "ollama"
        else:
            _resolved_backend = "none"
    return _resolved_backend


def reset_backend_cache() -> None:
    """Drop cached resolution so the next call re-probes (tests/config)."""
    global _resolved_backend, _ollama_available
    _resolved_backend = None
    _ollama_available = None


def _api_key() -> Optional[str]:
    try:
        from core.keys import get_key
        return get_key("openai")
    except Exception:  # noqa: BLE001 — degraded envs must never raise here
        return None


def _post_json(url: str, payload: dict, headers: dict, timeout: float) -> dict:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json", **headers}
    )
    with urllib.request.urlopen(request, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _embed_ollama(texts: list[str]) -> list[Optional[list[float]]]:
    model = _ollama_model()
    url = f"{_ollama_host().rstrip('/')}/api/embed"
    try:
        data = _post_json(url, {"model": model, "input": texts}, {}, _OLLAMA_TIMEOUT_S)
        embeddings = data.get("embeddings") if isinstance(data, dict) else None
        if not isinstance(embeddings, list) or len(embeddings) != len(texts):
            # Positional alignment is unknowable on a count mismatch —
            # degrading the whole batch beats misassociating vectors.
            logger.warning("ollama embed returned %s embeddings for %s texts",
                           len(embeddings) if isinstance(embeddings, list) else "no",
                           len(texts))
            return [None] * len(texts)
        return [list(map(float, vec)) for vec in embeddings]
    except (urllib.error.URLError, OSError, ValueError,
            TypeError, AttributeError) as exc:
        logger.warning("ollama embed failed (%s) — degrading to none", exc)
        return [None] * len(texts)


def _api_base_allowed(base: str) -> bool:
    """Bearer keys travel only over https, or http to loopback (local proxy)."""
    if base.startswith("https://"):
        return True
    if base.startswith("http://"):
        host = base[len("http://"):].split("/", 1)[0].split(":", 1)[0]
        return host in ("localhost", "127.0.0.1", "::1")
    return False


def _embed_api(texts: list[str]) -> list[Optional[list[float]]]:
    key = _api_key()
    if not key:
        return [None] * len(texts)
    cfg = _memory_config()
    base = str(cfg.get("embedApiBase") or DEFAULT_API_BASE).rstrip("/")
    model = str(cfg.get("embedApiModel") or DEFAULT_API_MODEL)
    if not _api_base_allowed(base):
        logger.warning("api embed refused: non-https base %r would leak the key", base)
        return [None] * len(texts)
    try:
        data = _post_json(
            f"{base}/v1/embeddings",
            {"model": model, "input": texts},
            {"Authorization": f"Bearer {key}"},
            _API_TIMEOUT_S,
        )
        rows = data.get("data") if isinstance(data, dict) else None
        # Rows are mapped by their declared index — precise per-item
        # alignment; absent indexes stay None.
        vectors: list[Optional[list[float]]] = [None] * len(texts)
        for row in rows if isinstance(rows, list) else []:
            if isinstance(row, dict):
                idx = row.get("index")
                if isinstance(idx, int) and 0 <= idx < len(texts):
                    vectors[idx] = list(map(float, row["embedding"]))
        return vectors
    except (urllib.error.URLError, OSError, ValueError,
            TypeError, KeyError, AttributeError) as exc:
        logger.warning("api embed failed (%s) — degrading to none", exc)
        return [None] * len(texts)


def _active_model_name(backend: BackendName) -> str:
    if backend == "fastembed":
        return embedder.get_model_name()
    if backend == "ollama":
        return _ollama_model()
    if backend == "api":
        cfg = _memory_config()
        return str(cfg.get("embedApiModel") or DEFAULT_API_MODEL)
    return ""


def _aligned(vectors: object, n: int) -> list[Optional[list[float]]]:
    """Every backend obeys one contract: exactly ``n`` positional items."""
    if not isinstance(vectors, list) or len(vectors) != n:
        return [None] * n
    return vectors


def embed_batch(texts: list[str]) -> list[EmbeddingResult]:
    """Embed texts via the resolved backend, declaring provenance per item."""
    if not texts:
        return []
    backend = resolve_backend()
    model = _active_model_name(backend)
    if backend == "fastembed":
        vectors = _aligned(embedder.embed_batch(texts), len(texts))
    elif backend == "ollama":
        vectors = _aligned(_embed_ollama(texts), len(texts))
    elif backend == "api":
        vectors = _aligned(_embed_api(texts), len(texts))
    else:
        vectors = [None] * len(texts)
    return [
        EmbeddingResult(
            vector=vec,
            backend=backend if vec is not None else "none",
            model=model if vec is not None else "",
            dims=len(vec) if vec is not None else 0,
        )
        for vec in vectors
    ]


def embed(text: str) -> EmbeddingResult:
    """Embed a single text (see ``embed_batch``)."""
    results = embed_batch([text])
    return results[0] if results else EmbeddingResult()
