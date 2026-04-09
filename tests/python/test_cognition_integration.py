"""End-to-end integration tests for the ArkaOS Cognitive Layer.

Covers the full cognitive cycle: capture → store → dual-write → insight → query.
"""

from datetime import date, timezone
from pathlib import Path

import pytest

from core.cognition.capture.collector import collect_from_digest
from core.cognition.capture.store import CaptureStore
from core.cognition.insights.store import InsightStore
from core.cognition.memory.schemas import ActionableInsight, KnowledgeEntry, RawCapture
from core.cognition.memory.writer import DualWriter


# --- Helpers ---

def make_capture(**overrides) -> RawCapture:
    defaults = {
        "session_id": "session-20260409-120000",
        "project_path": "/Users/andre/Herd/client_retail",
        "project_name": "client_retail",
        "category": "solution",
        "content": "Implemented Laravel Sanctum token-based authentication for the API.",
        "context": {"source": "test-session"},
    }
    defaults.update(overrides)
    return RawCapture(**defaults)


def make_knowledge_entry(**overrides) -> KnowledgeEntry:
    defaults = {
        "title": "Laravel Sanctum Auth Setup",
        "category": "pattern",
        "tags": ["laravel", "auth", "sanctum"],
        "stacks": ["laravel", "php"],
        "content": "## Setup\n\nInstall Sanctum and publish config for token auth.",
        "source_project": "client_retail",
        "applicable_to": "laravel",
        "confidence": 0.85,
    }
    defaults.update(overrides)
    return KnowledgeEntry(**defaults)


def make_insight(**overrides) -> ActionableInsight:
    defaults = {
        "project": "client_retail",
        "trigger": "nightly-dreaming",
        "category": "technical",
        "severity": "improve",
        "title": "Auth layer should use token rotation",
        "description": "Sanctum tokens are not rotating on use, increasing exposure window.",
        "recommendation": "Enable token rotation with Sanctum's built-in expiry config.",
        "context": "Observed 3 sessions where auth tokens were reused without rotation.",
    }
    defaults.update(overrides)
    return ActionableInsight(**defaults)


# --- Test Classes ---

class TestCognitionIntegration:
    """End-to-end integration tests for the full cognitive cycle."""

    def test_full_cycle(self, tmp_path: Path) -> None:
        """Full cycle: capture → store → dual-write → insight → query → mark processed."""
        capture_db = str(tmp_path / "captures.db")
        insight_db = str(tmp_path / "insights.db")
        vault_base = str(tmp_path / "vault")
        vector_db = str(tmp_path / "vector.db")

        # a. Create and save a raw capture (simulating a session)
        capture_store = CaptureStore(capture_db)
        capture = make_capture()
        capture_store.save(capture)

        # b. Verify capture is stored by date
        today = date.today()
        captures_today = capture_store.get_by_date(today)
        assert len(captures_today) == 1
        assert captures_today[0].id == capture.id
        assert captures_today[0].content == capture.content

        # c. Create a KnowledgeEntry (simulating Dreaming curating the capture)
        entry = make_knowledge_entry()

        # d. Write it via DualWriter
        dual_writer = DualWriter(obsidian_base=vault_base, vector_db_path=vector_db)
        result = dual_writer.write(entry)

        # e. Verify Obsidian file exists
        assert result.obsidian_path is not None
        assert Path(result.obsidian_path).exists()
        assert result.obsidian_error is None

        # f. Verify Vector search finds the entry
        assert result.vector_indexed is True
        assert result.vector_error is None
        search_results = dual_writer.search("sanctum authentication laravel")
        assert len(search_results) >= 1
        found_titles = [r["title"] for r in search_results]
        assert entry.title in found_titles

        # g. Create an ActionableInsight (simulating Dreaming's strategic reflection)
        insight = make_insight()

        # h. Save to InsightStore
        insight_store = InsightStore(insight_db)
        insight_store.save(insight)

        # i. Verify insight is pending for the project
        pending = insight_store.get_pending("client_retail")
        assert len(pending) == 1
        assert pending[0].id == insight.id
        assert pending[0].title == insight.title
        assert pending[0].status == "pending"

        # j. Mark capture as processed
        capture_store.mark_processed([capture.id])

        # k. Verify no unprocessed captures remain
        unprocessed = capture_store.get_unprocessed()
        assert len(unprocessed) == 0

        # l. Cleanup
        capture_store.close()
        insight_store.close()
        dual_writer.close()

    def test_collector_parses_digest(self, tmp_path: Path) -> None:
        """Collector parses digest text and saves captures with correct categories."""
        capture_db = str(tmp_path / "collector_captures.db")

        digest = (
            "Created a new Laravel auth system with Sanctum for API tokens.\n"
            "Fixed CORS issue with trusted_proxies middleware configuration.\n"
            "Short line.\n"
            "Decided to use Redis for session storage instead of database.\n"
            "Configured environment variables for staging deployment pipeline.\n"
        )

        count = collect_from_digest(digest, capture_db)

        # At least the 4 qualifying lines should be captured
        assert count >= 4

        store = CaptureStore(capture_db)
        all_captures = store.get_unprocessed()
        assert len(all_captures) == count

        categories = {c.category for c in all_captures}
        # "Created" line → solution
        assert "solution" in categories
        # "Fixed" line → error
        assert "error" in categories
        # "Decided" line → decision
        assert "decision" in categories
        # "Configured" line → config
        assert "config" in categories

        store.close()

    def test_dual_write_search_cross_project(self, tmp_path: Path) -> None:
        """Knowledge from multiple projects is searchable via a shared topic."""
        vault_base = str(tmp_path / "vault")
        vector_db = str(tmp_path / "vector.db")

        dual_writer = DualWriter(obsidian_base=vault_base, vector_db_path=vector_db)

        # a. Write a KnowledgeEntry from project "client_retail" applicable to laravel
        entry_client_retail = make_knowledge_entry(
            title="ClientRetail: Sanctum Rate Limiting",
            source_project="client_retail",
            applicable_to="laravel",
            tags=["laravel", "sanctum", "rate-limiting"],
            content="Apply throttle middleware to Sanctum API routes to prevent abuse.",
        )
        result_client_retail = dual_writer.write(entry_client_retail)
        assert result_client_retail.vector_indexed is True

        # b. Write a KnowledgeEntry from project "client_commerce" applicable to laravel
        entry_client_commerce = make_knowledge_entry(
            title="ClientCommerce: Sanctum Token Scopes",
            source_project="client_commerce",
            applicable_to="laravel",
            tags=["laravel", "sanctum", "scopes"],
            content="Use Sanctum token abilities to restrict API access per client scope.",
        )
        result_client_commerce = dual_writer.write(entry_client_commerce)
        assert result_client_commerce.vector_indexed is True

        # c. Search for the common topic
        results = dual_writer.search("sanctum laravel", top_k=10)

        # d. Verify both entries are found
        found_titles = {r["title"] for r in results}
        assert entry_client_retail.title in found_titles
        assert entry_client_commerce.title in found_titles

        dual_writer.close()
