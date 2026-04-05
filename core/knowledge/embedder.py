"""Embedding wrapper — local embeddings via fastembed.

Graceful degradation: if fastembed is not installed, returns None
and the vector store falls back to keyword matching.
"""

from typing import Optional

# Lazy import — fastembed is optional
_model = None
_model_name = "BAAI/bge-small-en-v1.5"  # 384 dims, fast, good quality
EMBEDDING_DIMS = 384


def get_model():
    """Get or create the embedding model (lazy singleton)."""
    global _model
    if _model is None:
        try:
            from fastembed import TextEmbedding
            _model = TextEmbedding(_model_name)
        except ImportError:
            return None
    return _model


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
        from fastembed import TextEmbedding
        return True
    except ImportError:
        return False
