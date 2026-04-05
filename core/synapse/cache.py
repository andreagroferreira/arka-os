"""TTL-based cache for Synapse layers.

Each layer can have its own cache TTL. The cache stores computed
layer results to avoid re-computation on every prompt.
"""

import time
from dataclasses import dataclass, field


@dataclass
class CacheEntry:
    """A single cached value with TTL."""
    value: str
    created_at: float
    ttl_seconds: int

    @property
    def is_expired(self) -> bool:
        if self.ttl_seconds <= 0:
            return False  # TTL 0 = never expires
        return (time.time() - self.created_at) > self.ttl_seconds


class LayerCache:
    """TTL-based cache for layer results.

    Each layer key maps to a cached value with its own TTL.
    Expired entries are evicted on access.
    """

    def __init__(self) -> None:
        self._store: dict[str, CacheEntry] = {}
        self._hits: int = 0
        self._misses: int = 0

    def get(self, key: str) -> str | None:
        """Get a cached value, or None if missing/expired."""
        entry = self._store.get(key)
        if entry is None:
            self._misses += 1
            return None
        if entry.is_expired:
            del self._store[key]
            self._misses += 1
            return None
        self._hits += 1
        return entry.value

    def set(self, key: str, value: str, ttl_seconds: int = 300) -> None:
        """Cache a value with TTL."""
        self._store[key] = CacheEntry(
            value=value,
            created_at=time.time(),
            ttl_seconds=ttl_seconds,
        )

    def invalidate(self, key: str) -> None:
        """Remove a specific key from cache."""
        self._store.pop(key, None)

    def clear(self) -> None:
        """Clear all cached entries."""
        self._store.clear()

    def evict_expired(self) -> int:
        """Remove all expired entries. Returns count of evicted entries."""
        expired = [k for k, v in self._store.items() if v.is_expired]
        for k in expired:
            del self._store[k]
        return len(expired)

    @property
    def stats(self) -> dict[str, int]:
        """Cache hit/miss statistics."""
        total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self._hits / total * 100) if total > 0 else 0,
            "size": len(self._store),
        }
