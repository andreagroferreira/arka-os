"""Knowledge session cache — project-scoped on-demand knowledge retrieval.

Provides session-scoped caching for L3.5 knowledge retrieval results.
Enables automatic knowledge injection when topics overlap across conversation turns
within the same project context.

Architecture:
    - Path: /tmp/arkaos-kb-{project_hash}/{session_id}.json
    - Max entries per session: 50
    - TTL: 30 minutes
    - Project-scoped via cwd hash (isolates knowledge by project)
    - Auto-inject when Jaccard topic overlap >= 0.3
"""

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Optional


STOP_WORDS = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "but",
    "in",
    "on",
    "at",
    "to",
    "for",
    "of",
    "with",
    "by",
    "from",
    "as",
    "is",
    "was",
    "are",
    "were",
    "been",
    "be",
    "have",
    "has",
    "had",
    "do",
    "does",
    "did",
    "will",
    "would",
    "could",
    "should",
    "may",
    "might",
    "must",
    "shall",
    "can",
    "need",
    "dare",
    "ought",
    "used",
    "it",
    "its",
    "this",
    "that",
    "these",
    "those",
    "i",
    "you",
    "he",
    "she",
    "we",
    "they",
    "what",
    "which",
    "who",
    "whom",
    "whose",
    "where",
    "when",
    "why",
    "how",
    "all",
    "each",
    "every",
    "both",
    "few",
    "more",
    "most",
    "other",
    "some",
    "such",
    "no",
    "nor",
    "not",
    "only",
    "own",
    "same",
    "so",
    "than",
    "too",
    "very",
    "just",
    "also",
    "now",
    "here",
    "there",
    "then",
}


class KBSessionCache:
    """Project-scoped session cache for knowledge retrieval.

    Stores L3.5 search results per session with topic extraction for
    overlap-based auto-injection.

    Usage:
        cache = KBSessionCache(session_id="abc123", project_path="/path/to/project")
        cache.store("deploy arkaos on kubernetes", [{"text": "...", "source": "..."}])
        results = cache.retrieve(topics={"deploy", "kubernetes"})
    """

    def __init__(
        self,
        session_id: str,
        project_path: Optional[str] = None,
        cache_dir: Optional[str] = None,
        max_entries: int = 50,
        ttl_seconds: int = 1800,
    ) -> None:
        self._session_id = session_id
        self._max_entries = max_entries
        self._ttl_seconds = ttl_seconds

        if cache_dir:
            self._cache_dir = Path(cache_dir)
        else:
            project_hash = self._hash_project(project_path or "")
            self._cache_dir = Path("/tmp") / f"arkaos-kb-{project_hash}"

        self._cache_file = self._cache_dir / f"{session_id}.json"
        self._ensure_dir()

    @staticmethod
    def _hash_project(path: str) -> str:
        """Create short hash of project path for directory naming."""
        if not path:
            return "default"
        h = hashlib.md5(path.encode(), usedforsecurity=False)
        return h.hexdigest()[:12]

    def _ensure_dir(self) -> None:
        """Ensure cache directory exists."""
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict[str, Any]:
        """Load cache from disk."""
        if not self._cache_file.exists():
            return {}
        try:
            return json.loads(self._cache_file.read_text())
        except (json.JSONDecodeError, OSError):
            return {}

    def _save(self, data: dict[str, Any]) -> None:
        """Save cache to disk."""
        self._cache_file.write_text(json.dumps(data, indent=2))

    def extract_topics(self, query: str) -> set[str]:
        """Extract key topics from a query string.

        Removes stop words and extracts nouns, verbs, and key phrases.
        Used for Jaccard overlap calculation.

        Args:
            query: Raw query string

        Returns:
            Set of topic keywords
        """
        if not query:
            return set()

        words = query.lower().split()
        topics = {w.strip(".,!?;:()[]{}") for w in words if len(w) > 2 and w not in STOP_WORDS}
        return topics

    @staticmethod
    def jaccard(topics1: set[str], topics2: set[str]) -> float:
        """Calculate Jaccard similarity between two topic sets.

        Args:
            topics1: First set of topics
            topics2: Second set of topics

        Returns:
            Jaccard coefficient between 0.0 and 1.0
        """
        if not topics1 or not topics2:
            return 0.0
        intersection = len(topics1 & topics2)
        union = len(topics1 | topics2)
        return intersection / union if union > 0 else 0.0

    def store(self, query: str, results: list[dict]) -> set[str]:
        """Store knowledge retrieval results in session cache.

        Args:
            query: The original user query
            results: List of dicts with 'text', 'source', 'heading', 'score'

        Returns:
            Set of extracted topics for this query (for overlap detection)
        """
        if not results:
            return set()

        topics = self.extract_topics(query)
        now = time.time()

        cache = self._load()

        entry = {
            "query": query,
            "topics": list(topics),
            "normalized_topics": sorted(topics),
            "snippets": [
                {
                    "text": r.get("text", "")[:300],
                    "source": r.get("source", ""),
                    "heading": r.get("heading", ""),
                    "score": r.get("score", 0.0),
                }
                for r in results
            ],
            "timestamp": now,
        }

        query_hash = hashlib.sha256(query.lower().encode(), usedforsecurity=False).hexdigest()[:16]
        cache[query_hash] = entry

        cache["_meta"] = {
            "session_id": self._session_id,
            "updated_at": now,
            "entry_count": len(cache) - 1,
        }

        if len(cache) - 1 > self._max_entries:
            cache = self._evict_oldest(cache)

        self._save(cache)
        return topics

    def retrieve(
        self,
        query: Optional[str] = None,
        topics: Optional[set[str]] = None,
        threshold: float = 0.3,
    ) -> list[dict]:
        """Retrieve cached knowledge by query or topic overlap.

        Args:
            query: Optional exact query to retrieve
            topics: Optional topic set for Jaccard matching
            threshold: Minimum Jaccard similarity for auto-inject (default 0.3)

        Returns:
            List of snippet dicts from the best matching cached entry
        """
        cache = self._load()
        if not cache or "_meta" not in cache:
            return []

        now = time.time()
        candidates: list[tuple[float, dict]] = []

        for query_hash, entry in cache.items():
            if query_hash == "_meta":
                continue

            entry_age = now - entry.get("timestamp", 0)
            if entry_age > self._ttl_seconds:
                continue

            if query:
                entry_hash = hashlib.sha256(
                    query.lower().encode(), usedforsecurity=False
                ).hexdigest()[:16]
                if entry_hash == query_hash:
                    return entry.get("snippets", [])

            if topics:
                entry_topics = set(entry.get("normalized_topics", []))
                score = self.jaccard(topics, entry_topics)
                if score >= threshold:
                    candidates.append((score, entry))

        if not candidates:
            return []

        candidates.sort(key=lambda x: x[0], reverse=True)
        best = candidates[0][1]
        return best.get("snippets", [])

    def get_overlap(self, query: str, threshold: float = 0.3) -> list[dict]:
        """Get overlapping knowledge for a query using Jaccard similarity.

        Convenience method that extracts topics and retrieves.

        Args:
            query: Query string to match against cached entries
            threshold: Minimum Jaccard similarity (default 0.3)

        Returns:
            List of snippet dicts from matching entries
        """
        topics = self.extract_topics(query)
        return self.retrieve(topics=topics, threshold=threshold)

    def _evict_oldest(self, cache: dict[str, Any]) -> dict[str, Any]:
        """Evict oldest entries when cache exceeds max_entries."""
        entries = [(k, v) for k, v in cache.items() if k != "_meta"]
        entries.sort(key=lambda x: x[1].get("timestamp", 0))

        keep_count = self._max_entries - 1
        keep_entries = dict(entries[-keep_count:]) if len(entries) > keep_count else dict(entries)
        keep_entries["_meta"] = cache.get("_meta", {})

        return keep_entries

    def clear(self) -> None:
        """Clear all cached entries for this session."""
        if self._cache_file.exists():
            self._cache_file.unlink()

    def stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        cache = self._load()
        now = time.time()
        valid_entries = 0
        oldest = None
        newest = None

        for k, v in cache.items():
            if k == "_meta":
                continue
            age = now - v.get("timestamp", 0)
            if age <= self._ttl_seconds:
                valid_entries += 1
            if oldest is None or v.get("timestamp", 0) < oldest:
                oldest = v.get("timestamp", 0)
            if newest is None or v.get("timestamp", 0) > newest:
                newest = v.get("timestamp", 0)

        return {
            "session_id": self._session_id,
            "cache_dir": str(self._cache_dir),
            "total_entries": len(cache) - 1,
            "valid_entries": valid_entries,
            "oldest_entry": oldest,
            "newest_entry": newest,
            "ttl_seconds": self._ttl_seconds,
        }


def extract_topics(query: str) -> set[str]:
    """Standalone topic extraction function.

    Convenience wrapper for use in external contexts.
    """
    return KBSessionCache(session_id="", project_path="").extract_topics(query)


def jaccard_similarity(topics1: set[str], topics2: set[str]) -> float:
    """Standalone Jaccard similarity calculation.

    Convenience wrapper for use in external contexts.
    """
    return KBSessionCache.jaccard(topics1, topics2)
