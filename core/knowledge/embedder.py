"""Embedding wrapper — local embeddings via fastembed.

Graceful degradation: if fastembed is not installed, returns None
and the vector store falls back to keyword matching (which the store
now labels as ``retrieval: "keyword-degraded"`` — see vector_store.py).

Model selection (PR-3 v4.1 — RAG honesty):
    1. ``ARKA_EMBED_MODEL`` env var
    2. ``knowledge.embedModel`` in ``~/.arkaos/config.json``
    3. default ``BAAI/bge-small-en-v1.5`` (backward compatible, 384 dims)

Recommendation for PT-heavy corpora:
    ``sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2``
    (384 dims — same dimension as the default, so switching does NOT
    require re-creating the vec0 table). ``intfloat/multilingual-e5-small``
    is NOT in fastembed's supported model list (fastembed only ships the
    ``intfloat/multilingual-e5-large`` variant, 1024 dims, which WOULD
    force a re-index); the MiniLM multilingual model is the supported
    drop-in. Verify with ``TextEmbedding.list_supported_models()``.

Dimensions are derived from the model (``embedding_dims()``), never
hardcoded at call sites. The vector store guards against a stored vec0
table whose dimension differs from the configured model — it logs and
keeps the stored dimension instead of corrupting the table.
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"  # 384 dims, fast, good quality
RECOMMENDED_MULTILINGUAL_MODEL = (
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)

# Known dims for models we document — used when fastembed is missing so
# dimension resolution stays deterministic in degraded environments.
_KNOWN_DIMS: dict[str, int] = {
    "BAAI/bge-small-en-v1.5": 384,
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2": 384,
    "sentence-transformers/paraphrase-multilingual-mpnet-base-v2": 768,
    "intfloat/multilingual-e5-large": 1024,
}

# Legacy constant (dims of the default model). Prefer embedding_dims().
EMBEDDING_DIMS = 384

# Lazy singletons — fastembed is optional.
_model = None
_loaded_model_name: Optional[str] = None


def get_model_name() -> str:
    """Resolve the configured embedding model name (env > config > default)."""
    env_name = os.environ.get("ARKA_EMBED_MODEL", "").strip()
    if env_name:
        return env_name
    config_path = Path.home() / ".arkaos" / "config.json"
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
        name = (data.get("knowledge") or {}).get("embedModel", "")
        if isinstance(name, str) and name.strip():
            return name.strip()
    except (OSError, json.JSONDecodeError, AttributeError):
        pass
    return DEFAULT_MODEL


def embedding_dims(model_name: Optional[str] = None) -> int:
    """Dimension of the active embedding model — derived, not hardcoded.

    Prefers the actually-loaded model (which may have fallen back to the
    default when a configured name failed to load), then fastembed's own
    supported-models metadata, then the documented known-dims map.
    """
    name = model_name or _loaded_model_name or get_model_name()
    dim = _dims_from_fastembed(name)
    if dim is not None:
        return dim
    return _KNOWN_DIMS.get(name, EMBEDDING_DIMS)


def _dims_from_fastembed(name: str) -> Optional[int]:
    try:
        from fastembed import TextEmbedding
        for entry in TextEmbedding.list_supported_models():
            info = entry if isinstance(entry, dict) else vars(entry)
            if info.get("model") == name and info.get("dim"):
                return int(info["dim"])
    except Exception:  # noqa: BLE001 — degraded envs must never raise here
        pass
    return None


def get_model():
    """Get or create the embedding model (lazy singleton, config-aware)."""
    global _model, _loaded_model_name
    name = get_model_name()
    if _model is not None and _loaded_model_name == name:
        return _model
    try:
        from fastembed import TextEmbedding
    except ImportError:
        return None
    try:
        _model = TextEmbedding(name)
        _loaded_model_name = name
    except Exception as exc:  # noqa: BLE001 — unsupported model name, etc.
        logger.warning(
            "embed model %r failed to load (%s) — falling back to %s",
            name, exc, DEFAULT_MODEL,
        )
        if name == DEFAULT_MODEL:
            return None
        try:
            _model = TextEmbedding(DEFAULT_MODEL)
            _loaded_model_name = DEFAULT_MODEL
        except Exception:  # noqa: BLE001
            return None
    return _model


def reset_model_cache() -> None:
    """Drop the cached model so the next call re-resolves configuration."""
    global _model, _loaded_model_name
    _model = None
    _loaded_model_name = None


def embed(text: str) -> Optional[list[float]]:
    """Embed a single text. Returns None if fastembed unavailable."""
    model = get_model()
    if model is None:
        return None
    results = list(model.embed([text]))
    return results[0].tolist() if results else None


def embed_batch(texts: list[str]) -> Optional[list[list[float]]]:
    """Embed multiple texts. Returns None if fastembed unavailable."""
    if not texts:
        return []
    model = get_model()
    if model is None:
        return None
    return [emb.tolist() for emb in model.embed(texts)]


def is_available() -> bool:
    """Check if embedding model is available."""
    try:
        from fastembed import TextEmbedding  # noqa: F401
        return True
    except ImportError:
        return False
