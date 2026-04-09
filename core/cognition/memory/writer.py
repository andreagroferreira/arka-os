"""DualWriter — unified interface that writes KnowledgeEntry to Obsidian and Vector DB."""

from dataclasses import dataclass, field

from core.cognition.memory.obsidian import ObsidianWriter
from core.cognition.memory.schemas import KnowledgeEntry
from core.cognition.memory.vector import VectorWriter


@dataclass
class WriteResult:
    """Result of a dual-write operation, with independent success/error per backend."""

    obsidian_path: str | None = None
    obsidian_error: str | None = None
    vector_indexed: bool = False
    vector_error: str | None = None


class DualWriter:
    """Writes KnowledgeEntry objects to both Obsidian and Vector DB in one call.

    Each backend fails independently — if Obsidian fails, Vector still writes,
    and vice versa. All results are captured in WriteResult.
    """

    def __init__(self, obsidian_base: str, vector_db_path: str) -> None:
        self._obsidian = ObsidianWriter(vault_base_path=obsidian_base)
        self._vector = VectorWriter(db_path=vector_db_path)

    def write(self, entry: KnowledgeEntry) -> WriteResult:
        """Write a single entry to both backends. Returns a WriteResult."""
        result = WriteResult()

        try:
            result.obsidian_path = self._obsidian.write(entry)
        except Exception as exc:  # noqa: BLE001
            result.obsidian_error = str(exc)

        try:
            result.vector_indexed = self._vector.write(entry)
        except Exception as exc:  # noqa: BLE001
            result.vector_error = str(exc)

        return result

    def write_batch(self, entries: list[KnowledgeEntry]) -> list[WriteResult]:
        """Write a list of entries. Returns one WriteResult per entry."""
        return [self.write(entry) for entry in entries]

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """Search the vector store. Delegates directly to VectorWriter."""
        return self._vector.search(query, top_k=top_k)

    def close(self) -> None:
        """Close the vector DB connection."""
        self._vector.close()
