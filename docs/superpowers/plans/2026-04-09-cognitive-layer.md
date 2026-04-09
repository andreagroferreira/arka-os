# Cognitive Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add three cognitive capabilities to ArkaOS — Institutional Memory (dual-write), Dreaming (nightly self-critique), and Research (adaptive daily intelligence) — connected by a cross-platform scheduler.

**Architecture:** New `core/cognition/` module with 5 subpackages (memory, capture, dreaming, research, scheduler). The dual-write engine (`memory/writer.py`) is the shared interface — all subsystems persist knowledge through it. Raw captures accumulate during the day in SQLite; Dreaming curates them at night; Research adds external intelligence. Insights are delivered to the user via hook injection on project entry.

**Tech Stack:** Python 3.11+, Pydantic 2.x, SQLite, sqlite-vss (existing), PyYAML, `schedule` lib (new), platform-specific service adapters (launchd/systemd/schtasks)

**Spec:** `docs/superpowers/specs/2026-04-09-cognitive-layer-design.md`

---

## File Structure

### New Files

```
core/cognition/
├── __init__.py                    # Exports: DualWriter, CaptureStore, InsightStore
├── memory/
│   ├── __init__.py
│   ├── schemas.py                 # Pydantic models: RawCapture, KnowledgeEntry, ActionableInsight
│   ├── writer.py                  # DualWriter class: write() → Obsidian + Vector DB
│   ├── obsidian.py                # ObsidianWriter: markdown + frontmatter + backlinks
│   └── vector.py                  # VectorWriter: wraps core/knowledge/vector_store.py
├── capture/
│   ├── __init__.py
│   ├── store.py                   # CaptureStore: SQLite CRUD for ~/.arkaos/captures.db
│   └── collector.py               # collect_session_data(): parses session for raw captures
├── insights/
│   ├── __init__.py
│   └── store.py                   # InsightStore: SQLite CRUD for ~/.arkaos/insights.db
├── research/
│   ├── __init__.py
│   └── profiler.py                # ResearchProfiler: infer profile from projects + memories
└── scheduler/
    ├── __init__.py
    ├── daemon.py                  # ArkaScheduler: main loop, schedule execution
    ├── platform.py                # PlatformAdapter ABC + MacOS/Linux/Windows adapters
    └── cli.py                     # CLI entry points: status, start, stop, run, logs

config/cognition/
├── schedules.yaml                 # Default schedule config (dreaming 02:00, research 05:00)
└── prompts/
    ├── dreaming.md                # Complete Dreaming prompt for headless Claude session
    └── research.md                # Complete Research prompt for headless Claude session

tests/python/
├── test_cognition_schemas.py      # Schema validation tests
├── test_dual_writer.py            # DualWriter tests (obsidian + vector)
├── test_capture_store.py          # CaptureStore CRUD tests
├── test_insight_store.py          # InsightStore CRUD tests
├── test_research_profiler.py      # Profile inference tests
├── test_scheduler_daemon.py       # Scheduler logic tests
└── test_scheduler_platform.py     # Platform adapter tests
```

### Modified Files

```
config/hooks/pre-compact.sh        # Add raw capture collection call
config/hooks/cwd-changed.sh        # Add insight presentation
config/hooks/session-start.sh      # Add overnight insight/research alerts
installer/index.js                 # Add scheduler installation step
installer/cli.js                   # Add 'scheduler' subcommand routing
pyproject.toml                     # Add 'schedule' dependency
```

---

## Phase 1: Foundation — Schemas + Databases

### Task 1: Pydantic Schemas

**Files:**
- Create: `core/cognition/__init__.py`
- Create: `core/cognition/memory/__init__.py`
- Create: `core/cognition/memory/schemas.py`
- Test: `tests/python/test_cognition_schemas.py`

- [ ] **Step 1: Write failing tests for all schema models**

```python
# tests/python/test_cognition_schemas.py
import pytest
from datetime import datetime, timezone


class TestRawCapture:
    def test_create_valid_capture(self):
        from core.cognition.memory.schemas import RawCapture

        capture = RawCapture(
            session_id="sess-001",
            project_path="/Users/dev/projects/client_commerce",
            project_name="client_commerce",
            category="decision",
            content="Used Sanctum for API authentication",
            context={"stack": "laravel", "files": ["config/auth.php"]},
        )
        assert capture.id is not None
        assert capture.timestamp is not None
        assert capture.category == "decision"
        assert capture.context["stack"] == "laravel"

    def test_invalid_category_rejected(self):
        from core.cognition.memory.schemas import RawCapture

        with pytest.raises(ValueError):
            RawCapture(
                session_id="sess-001",
                project_path="/tmp",
                project_name="test",
                category="invalid_category",
                content="test",
                context={},
            )


class TestKnowledgeEntry:
    def test_create_valid_entry(self):
        from core.cognition.memory.schemas import KnowledgeEntry

        entry = KnowledgeEntry(
            title="Laravel Sanctum Auth Setup",
            category="pattern",
            tags=["laravel", "auth", "sanctum"],
            stacks=["laravel", "php"],
            content="# Sanctum Auth\nUse Sanctum for SPA + API auth...",
            source_project="client_commerce",
            applicable_to="laravel",
        )
        assert entry.id is not None
        assert entry.confidence == 0.5
        assert entry.times_used == 0
        assert entry.created_at is not None

    def test_invalid_category_rejected(self):
        from core.cognition.memory.schemas import KnowledgeEntry

        with pytest.raises(ValueError):
            KnowledgeEntry(
                title="Test",
                category="bogus",
                tags=[],
                stacks=[],
                content="test",
                source_project="test",
                applicable_to="any",
            )

    def test_confidence_clamped(self):
        from core.cognition.memory.schemas import KnowledgeEntry

        entry = KnowledgeEntry(
            title="Test",
            category="pattern",
            tags=[],
            stacks=[],
            content="test",
            source_project="test",
            applicable_to="any",
            confidence=1.5,
        )
        assert entry.confidence == 1.0


class TestActionableInsight:
    def test_create_valid_insight(self):
        from core.cognition.memory.schemas import ActionableInsight

        insight = ActionableInsight(
            project="client_commerce",
            trigger="dreaming",
            category="business",
            severity="rethink",
            title="Offer model missing key conversion fields",
            description="The offer model does not consider min qty per SKU...",
            recommendation="Add min_qty, tier_price, volume_discount fields",
            context="Implemented basic offer model in migration 2026_04_08",
        )
        assert insight.id is not None
        assert insight.status == "pending"
        assert insight.presented_at is None

    def test_invalid_status_rejected(self):
        from core.cognition.memory.schemas import ActionableInsight

        with pytest.raises(ValueError):
            ActionableInsight(
                project="test",
                trigger="dreaming",
                category="business",
                severity="rethink",
                title="Test",
                description="test",
                recommendation="test",
                context="test",
                status="invalid_status",
            )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/andreagroferreira/AIProjects/arka-os && python -m pytest tests/python/test_cognition_schemas.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.cognition'`

- [ ] **Step 3: Implement schemas**

```python
# core/cognition/__init__.py
"""ArkaOS Cognitive Layer — Memory, Dreaming, Research."""

# core/cognition/memory/__init__.py
from .schemas import RawCapture, KnowledgeEntry, ActionableInsight

__all__ = ["RawCapture", "KnowledgeEntry", "ActionableInsight"]
```

```python
# core/cognition/memory/schemas.py
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator

CAPTURE_CATEGORIES = ("decision", "solution", "pattern", "error", "config")

KNOWLEDGE_CATEGORIES = (
    "pattern",
    "anti_pattern",
    "solution",
    "architecture",
    "config",
    "lesson",
    "improvement",
)

INSIGHT_CATEGORIES = ("business", "technical", "ux", "strategy")
INSIGHT_SEVERITIES = ("rethink", "improve", "consider")
INSIGHT_STATUSES = ("pending", "presented", "accepted", "dismissed")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class RawCapture(BaseModel):
    id: str = Field(default_factory=_uuid)
    timestamp: datetime = Field(default_factory=_utcnow)
    session_id: str
    project_path: str
    project_name: str
    category: str
    content: str
    context: dict = Field(default_factory=dict)

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        if v not in CAPTURE_CATEGORIES:
            raise ValueError(f"category must be one of {CAPTURE_CATEGORIES}, got '{v}'")
        return v


class KnowledgeEntry(BaseModel):
    id: str = Field(default_factory=_uuid)
    title: str
    category: str
    tags: list[str] = Field(default_factory=list)
    stacks: list[str] = Field(default_factory=list)
    content: str
    source_project: str
    applicable_to: str = "any"
    confidence: float = 0.5
    times_used: int = 0
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        if v not in KNOWLEDGE_CATEGORIES:
            raise ValueError(
                f"category must be one of {KNOWLEDGE_CATEGORIES}, got '{v}'"
            )
        return v

    @field_validator("confidence")
    @classmethod
    def clamp_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, v))


class ActionableInsight(BaseModel):
    id: str = Field(default_factory=_uuid)
    project: str
    trigger: str
    date_generated: datetime = Field(default_factory=_utcnow)
    category: str
    severity: str
    title: str
    description: str
    recommendation: str
    context: str
    status: str = "pending"
    presented_at: datetime | None = None

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        if v not in INSIGHT_CATEGORIES:
            raise ValueError(
                f"category must be one of {INSIGHT_CATEGORIES}, got '{v}'"
            )
        return v

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v: str) -> str:
        if v not in INSIGHT_SEVERITIES:
            raise ValueError(
                f"severity must be one of {INSIGHT_SEVERITIES}, got '{v}'"
            )
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in INSIGHT_STATUSES:
            raise ValueError(
                f"status must be one of {INSIGHT_STATUSES}, got '{v}'"
            )
        return v
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/andreagroferreira/AIProjects/arka-os && python -m pytest tests/python/test_cognition_schemas.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add core/cognition/__init__.py core/cognition/memory/__init__.py core/cognition/memory/schemas.py tests/python/test_cognition_schemas.py
git commit -m "feat(cognition): add Pydantic schemas for RawCapture, KnowledgeEntry, ActionableInsight"
```

---

### Task 2: Capture Store (SQLite CRUD)

**Files:**
- Create: `core/cognition/capture/__init__.py`
- Create: `core/cognition/capture/store.py`
- Test: `tests/python/test_capture_store.py`

- [ ] **Step 1: Write failing tests for CaptureStore**

```python
# tests/python/test_capture_store.py
import pytest
from datetime import datetime, timezone, timedelta


class TestCaptureStore:
    @pytest.fixture
    def store(self, tmp_path):
        from core.cognition.capture.store import CaptureStore

        db_path = str(tmp_path / "captures.db")
        s = CaptureStore(db_path)
        yield s
        s.close()

    @pytest.fixture
    def sample_capture(self):
        from core.cognition.memory.schemas import RawCapture

        return RawCapture(
            session_id="sess-001",
            project_path="/Users/dev/projects/client_commerce",
            project_name="client_commerce",
            category="decision",
            content="Used Sanctum for API authentication",
            context={"stack": "laravel", "files": ["config/auth.php"]},
        )

    def test_save_and_retrieve(self, store, sample_capture):
        store.save(sample_capture)
        results = store.get_by_date(sample_capture.timestamp.date())
        assert len(results) == 1
        assert results[0].content == "Used Sanctum for API authentication"
        assert results[0].id == sample_capture.id

    def test_get_by_date_filters_correctly(self, store):
        from core.cognition.memory.schemas import RawCapture
        from datetime import date

        today = RawCapture(
            session_id="s1",
            project_path="/tmp",
            project_name="a",
            category="decision",
            content="today",
            context={},
        )
        store.save(today)

        yesterday = RawCapture(
            session_id="s2",
            project_path="/tmp",
            project_name="b",
            category="error",
            content="yesterday",
            context={},
            timestamp=datetime.now(timezone.utc) - timedelta(days=1),
        )
        store.save(yesterday)

        results = store.get_by_date(date.today())
        assert len(results) == 1
        assert results[0].content == "today"

    def test_get_by_project(self, store, sample_capture):
        store.save(sample_capture)
        results = store.get_by_project("client_commerce")
        assert len(results) == 1

        results = store.get_by_project("nonexistent")
        assert len(results) == 0

    def test_get_unprocessed(self, store, sample_capture):
        store.save(sample_capture)
        unprocessed = store.get_unprocessed()
        assert len(unprocessed) == 1

        store.mark_processed([sample_capture.id])
        unprocessed = store.get_unprocessed()
        assert len(unprocessed) == 0

    def test_archive_processed(self, store, sample_capture):
        store.save(sample_capture)
        store.mark_processed([sample_capture.id])
        archived = store.archive_processed()
        assert archived == 1

        # Archived captures no longer returned
        results = store.get_by_date(sample_capture.timestamp.date())
        assert len(results) == 0

    def test_stats(self, store, sample_capture):
        store.save(sample_capture)
        stats = store.stats()
        assert stats["total"] == 1
        assert stats["unprocessed"] == 1
        assert stats["by_category"]["decision"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/andreagroferreira/AIProjects/arka-os && python -m pytest tests/python/test_capture_store.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement CaptureStore**

```python
# core/cognition/capture/__init__.py
from .store import CaptureStore

__all__ = ["CaptureStore"]
```

```python
# core/cognition/capture/store.py
from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

from core.cognition.memory.schemas import RawCapture


class CaptureStore:
    """SQLite store for raw session captures."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS captures (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                session_id TEXT NOT NULL,
                project_path TEXT NOT NULL,
                project_name TEXT NOT NULL,
                category TEXT NOT NULL,
                content TEXT NOT NULL,
                context TEXT NOT NULL DEFAULT '{}',
                processed INTEGER NOT NULL DEFAULT 0,
                archived INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_captures_date
                ON captures(timestamp);
            CREATE INDEX IF NOT EXISTS idx_captures_project
                ON captures(project_name);
            CREATE INDEX IF NOT EXISTS idx_captures_processed
                ON captures(processed);
            """
        )
        self._conn.commit()

    def save(self, capture: RawCapture) -> None:
        self._conn.execute(
            """
            INSERT OR REPLACE INTO captures
                (id, timestamp, session_id, project_path, project_name,
                 category, content, context)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                capture.id,
                capture.timestamp.isoformat(),
                capture.session_id,
                capture.project_path,
                capture.project_name,
                capture.category,
                capture.content,
                json.dumps(capture.context),
            ),
        )
        self._conn.commit()

    def _row_to_capture(self, row: sqlite3.Row) -> RawCapture:
        return RawCapture(
            id=row["id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            session_id=row["session_id"],
            project_path=row["project_path"],
            project_name=row["project_name"],
            category=row["category"],
            content=row["content"],
            context=json.loads(row["context"]),
        )

    def get_by_date(self, target_date: date) -> list[RawCapture]:
        start = datetime(target_date.year, target_date.month, target_date.day,
                         tzinfo=timezone.utc).isoformat()
        end = datetime(target_date.year, target_date.month, target_date.day,
                       23, 59, 59, tzinfo=timezone.utc).isoformat()
        rows = self._conn.execute(
            "SELECT * FROM captures WHERE timestamp >= ? AND timestamp <= ? AND archived = 0",
            (start, end),
        ).fetchall()
        return [self._row_to_capture(r) for r in rows]

    def get_by_project(self, project_name: str) -> list[RawCapture]:
        rows = self._conn.execute(
            "SELECT * FROM captures WHERE project_name = ? AND archived = 0",
            (project_name,),
        ).fetchall()
        return [self._row_to_capture(r) for r in rows]

    def get_unprocessed(self) -> list[RawCapture]:
        rows = self._conn.execute(
            "SELECT * FROM captures WHERE processed = 0 AND archived = 0"
        ).fetchall()
        return [self._row_to_capture(r) for r in rows]

    def mark_processed(self, ids: list[str]) -> None:
        if not ids:
            return
        placeholders = ",".join("?" for _ in ids)
        self._conn.execute(
            f"UPDATE captures SET processed = 1 WHERE id IN ({placeholders})",
            ids,
        )
        self._conn.commit()

    def archive_processed(self) -> int:
        cursor = self._conn.execute(
            "UPDATE captures SET archived = 1 WHERE processed = 1 AND archived = 0"
        )
        self._conn.commit()
        return cursor.rowcount

    def stats(self) -> dict:
        total = self._conn.execute(
            "SELECT COUNT(*) FROM captures WHERE archived = 0"
        ).fetchone()[0]
        unprocessed = self._conn.execute(
            "SELECT COUNT(*) FROM captures WHERE processed = 0 AND archived = 0"
        ).fetchone()[0]
        rows = self._conn.execute(
            "SELECT category, COUNT(*) as cnt FROM captures WHERE archived = 0 GROUP BY category"
        ).fetchall()
        by_category = {r["category"]: r["cnt"] for r in rows}
        return {"total": total, "unprocessed": unprocessed, "by_category": by_category}

    def close(self) -> None:
        self._conn.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/andreagroferreira/AIProjects/arka-os && python -m pytest tests/python/test_capture_store.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add core/cognition/capture/ tests/python/test_capture_store.py
git commit -m "feat(cognition): add CaptureStore for raw session captures"
```

---

### Task 3: Insight Store (SQLite CRUD)

**Files:**
- Create: `core/cognition/insights/__init__.py`
- Create: `core/cognition/insights/store.py`
- Test: `tests/python/test_insight_store.py`

- [ ] **Step 1: Write failing tests for InsightStore**

```python
# tests/python/test_insight_store.py
import pytest
from datetime import datetime, timezone


class TestInsightStore:
    @pytest.fixture
    def store(self, tmp_path):
        from core.cognition.insights.store import InsightStore

        db_path = str(tmp_path / "insights.db")
        s = InsightStore(db_path)
        yield s
        s.close()

    @pytest.fixture
    def sample_insight(self):
        from core.cognition.memory.schemas import ActionableInsight

        return ActionableInsight(
            project="client_commerce",
            trigger="dreaming",
            category="business",
            severity="rethink",
            title="Offer model missing key conversion fields",
            description="The offer model does not consider min qty per SKU",
            recommendation="Add min_qty, tier_price, volume_discount fields",
            context="Implemented basic offer model in migration 2026_04_08",
        )

    def test_save_and_retrieve(self, store, sample_insight):
        store.save(sample_insight)
        results = store.get_pending("client_commerce")
        assert len(results) == 1
        assert results[0].title == "Offer model missing key conversion fields"

    def test_get_pending_filters_by_project(self, store, sample_insight):
        store.save(sample_insight)
        assert len(store.get_pending("client_commerce")) == 1
        assert len(store.get_pending("client_retail")) == 0

    def test_get_pending_excludes_non_pending(self, store, sample_insight):
        store.save(sample_insight)
        store.update_status(sample_insight.id, "presented")
        assert len(store.get_pending("client_commerce")) == 0

    def test_update_status(self, store, sample_insight):
        store.save(sample_insight)
        store.update_status(sample_insight.id, "accepted")
        results = store.get_by_project("client_commerce")
        assert results[0].status == "accepted"

    def test_mark_presented(self, store, sample_insight):
        store.save(sample_insight)
        store.mark_presented([sample_insight.id])
        results = store.get_by_project("client_commerce")
        assert results[0].status == "presented"
        assert results[0].presented_at is not None

    def test_get_all_pending(self, store):
        from core.cognition.memory.schemas import ActionableInsight

        for project in ["client_commerce", "client_retail", "client_fashion"]:
            store.save(
                ActionableInsight(
                    project=project,
                    trigger="dreaming",
                    category="technical",
                    severity="improve",
                    title=f"Insight for {project}",
                    description="desc",
                    recommendation="rec",
                    context="ctx",
                )
            )
        all_pending = store.get_all_pending()
        assert len(all_pending) == 3

    def test_dismissed_count_by_category(self, store):
        from core.cognition.memory.schemas import ActionableInsight

        for i in range(3):
            insight = ActionableInsight(
                project="client_commerce",
                trigger="dreaming",
                category="business",
                severity="consider",
                title=f"Insight {i}",
                description="desc",
                recommendation="rec",
                context="ctx",
            )
            store.save(insight)
            store.update_status(insight.id, "dismissed")

        counts = store.dismissed_counts("client_commerce")
        assert counts.get("business", 0) == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/andreagroferreira/AIProjects/arka-os && python -m pytest tests/python/test_insight_store.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement InsightStore**

```python
# core/cognition/insights/__init__.py
from .store import InsightStore

__all__ = ["InsightStore"]
```

```python
# core/cognition/insights/store.py
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from core.cognition.memory.schemas import ActionableInsight


class InsightStore:
    """SQLite store for actionable insights."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS insights (
                id TEXT PRIMARY KEY,
                project TEXT NOT NULL,
                trigger_source TEXT NOT NULL,
                date_generated TEXT NOT NULL,
                category TEXT NOT NULL,
                severity TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                recommendation TEXT NOT NULL,
                context TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                presented_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_insights_project
                ON insights(project);
            CREATE INDEX IF NOT EXISTS idx_insights_status
                ON insights(status);
            """
        )
        self._conn.commit()

    def save(self, insight: ActionableInsight) -> None:
        self._conn.execute(
            """
            INSERT OR REPLACE INTO insights
                (id, project, trigger_source, date_generated, category,
                 severity, title, description, recommendation, context,
                 status, presented_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                insight.id,
                insight.project,
                insight.trigger,
                insight.date_generated.isoformat(),
                insight.category,
                insight.severity,
                insight.title,
                insight.description,
                insight.recommendation,
                insight.context,
                insight.status,
                insight.presented_at.isoformat() if insight.presented_at else None,
            ),
        )
        self._conn.commit()

    def _row_to_insight(self, row: sqlite3.Row) -> ActionableInsight:
        presented = row["presented_at"]
        return ActionableInsight(
            id=row["id"],
            project=row["project"],
            trigger=row["trigger_source"],
            date_generated=datetime.fromisoformat(row["date_generated"]),
            category=row["category"],
            severity=row["severity"],
            title=row["title"],
            description=row["description"],
            recommendation=row["recommendation"],
            context=row["context"],
            status=row["status"],
            presented_at=datetime.fromisoformat(presented) if presented else None,
        )

    def get_pending(self, project: str) -> list[ActionableInsight]:
        rows = self._conn.execute(
            "SELECT * FROM insights WHERE project = ? AND status = 'pending'",
            (project,),
        ).fetchall()
        return [self._row_to_insight(r) for r in rows]

    def get_all_pending(self) -> list[ActionableInsight]:
        rows = self._conn.execute(
            "SELECT * FROM insights WHERE status = 'pending'"
        ).fetchall()
        return [self._row_to_insight(r) for r in rows]

    def get_by_project(self, project: str) -> list[ActionableInsight]:
        rows = self._conn.execute(
            "SELECT * FROM insights WHERE project = ?",
            (project,),
        ).fetchall()
        return [self._row_to_insight(r) for r in rows]

    def update_status(self, insight_id: str, status: str) -> None:
        self._conn.execute(
            "UPDATE insights SET status = ? WHERE id = ?",
            (status, insight_id),
        )
        self._conn.commit()

    def mark_presented(self, ids: list[str]) -> None:
        if not ids:
            return
        now = datetime.now(timezone.utc).isoformat()
        placeholders = ",".join("?" for _ in ids)
        self._conn.execute(
            f"UPDATE insights SET status = 'presented', presented_at = ? WHERE id IN ({placeholders})",
            [now] + ids,
        )
        self._conn.commit()

    def dismissed_counts(self, project: str) -> dict[str, int]:
        rows = self._conn.execute(
            "SELECT category, COUNT(*) as cnt FROM insights WHERE project = ? AND status = 'dismissed' GROUP BY category",
            (project,),
        ).fetchall()
        return {r["category"]: r["cnt"] for r in rows}

    def close(self) -> None:
        self._conn.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/andreagroferreira/AIProjects/arka-os && python -m pytest tests/python/test_insight_store.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add core/cognition/insights/ tests/python/test_insight_store.py
git commit -m "feat(cognition): add InsightStore for actionable insights"
```

---

## Phase 2: Dual-Write Engine

### Task 4: Obsidian Writer

**Files:**
- Create: `core/cognition/memory/obsidian.py`
- Test: `tests/python/test_dual_writer.py` (obsidian section)

- [ ] **Step 1: Write failing tests for ObsidianWriter**

```python
# tests/python/test_dual_writer.py
import pytest
from pathlib import Path


class TestObsidianWriter:
    @pytest.fixture
    def vault_path(self, tmp_path):
        return tmp_path / "vault" / "ArkaOS" / "Knowledge Base"

    @pytest.fixture
    def writer(self, vault_path):
        from core.cognition.memory.obsidian import ObsidianWriter

        return ObsidianWriter(str(vault_path))

    @pytest.fixture
    def sample_entry(self):
        from core.cognition.memory.schemas import KnowledgeEntry

        return KnowledgeEntry(
            title="Laravel Sanctum Auth Setup",
            category="pattern",
            tags=["laravel", "auth", "sanctum"],
            stacks=["laravel", "php"],
            content="# Sanctum Auth\n\nUse Sanctum for SPA + API authentication.\n\n## Steps\n1. Install Sanctum\n2. Run migration\n3. Add middleware",
            source_project="client_commerce",
            applicable_to="laravel",
            confidence=0.75,
            times_used=3,
        )

    def test_write_creates_file(self, writer, sample_entry, vault_path):
        path = writer.write(sample_entry)
        assert Path(path).exists()
        assert "Patterns" in path

    def test_write_has_frontmatter(self, writer, sample_entry, vault_path):
        path = writer.write(sample_entry)
        content = Path(path).read_text()
        assert content.startswith("---\n")
        assert "title: Laravel Sanctum Auth Setup" in content
        assert "category: pattern" in content
        assert "confidence: 0.75" in content
        assert "tags:" in content

    def test_write_has_content_body(self, writer, sample_entry, vault_path):
        path = writer.write(sample_entry)
        content = Path(path).read_text()
        assert "# Sanctum Auth" in content
        assert "Use Sanctum for SPA" in content

    def test_write_category_maps_to_folder(self, writer, vault_path):
        from core.cognition.memory.schemas import KnowledgeEntry

        for cat, folder in [
            ("pattern", "Patterns"),
            ("anti_pattern", "Anti-Patterns"),
            ("solution", "Solutions"),
            ("architecture", "Architecture"),
            ("lesson", "Lessons"),
            ("improvement", "Improvements"),
        ]:
            entry = KnowledgeEntry(
                title=f"Test {cat}",
                category=cat,
                tags=[],
                stacks=[],
                content="test",
                source_project="test",
                applicable_to="any",
            )
            path = writer.write(entry)
            assert folder in path

    def test_write_updates_existing(self, writer, sample_entry, vault_path):
        path1 = writer.write(sample_entry)
        sample_entry.confidence = 0.9
        sample_entry.times_used = 5
        path2 = writer.write(sample_entry)
        assert path1 == path2
        content = Path(path2).read_text()
        assert "confidence: 0.9" in content
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/andreagroferreira/AIProjects/arka-os && python -m pytest tests/python/test_dual_writer.py::TestObsidianWriter -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement ObsidianWriter**

```python
# core/cognition/memory/obsidian.py
from __future__ import annotations

import re
from pathlib import Path

from core.cognition.memory.schemas import KnowledgeEntry

CATEGORY_FOLDERS = {
    "pattern": "Patterns",
    "anti_pattern": "Anti-Patterns",
    "solution": "Solutions",
    "architecture": "Architecture",
    "config": "Config",
    "lesson": "Lessons",
    "improvement": "Improvements",
}


def _slugify(title: str) -> str:
    slug = title.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    return slug[:80]


class ObsidianWriter:
    """Writes KnowledgeEntry objects as Obsidian markdown notes."""

    def __init__(self, vault_base_path: str) -> None:
        self._base = Path(vault_base_path)

    def write(self, entry: KnowledgeEntry) -> str:
        folder = CATEGORY_FOLDERS.get(entry.category, "Uncategorized")
        dir_path = self._base / folder
        dir_path.mkdir(parents=True, exist_ok=True)

        filename = f"{_slugify(entry.title)}.md"
        file_path = dir_path / filename

        frontmatter = self._build_frontmatter(entry)
        content = f"---\n{frontmatter}---\n\n{entry.content}\n"

        file_path.write_text(content, encoding="utf-8")
        return str(file_path)

    def _build_frontmatter(self, entry: KnowledgeEntry) -> str:
        lines = [
            f"title: {entry.title}",
            f"id: {entry.id}",
            f"category: {entry.category}",
            f"tags: [{', '.join(entry.tags)}]",
            f"stacks: [{', '.join(entry.stacks)}]",
            f"source_project: {entry.source_project}",
            f"applicable_to: {entry.applicable_to}",
            f"confidence: {entry.confidence}",
            f"times_used: {entry.times_used}",
            f"created_at: {entry.created_at.isoformat()}",
            f"updated_at: {entry.updated_at.isoformat()}",
        ]
        return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/andreagroferreira/AIProjects/arka-os && python -m pytest tests/python/test_dual_writer.py::TestObsidianWriter -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add core/cognition/memory/obsidian.py tests/python/test_dual_writer.py
git commit -m "feat(cognition): add ObsidianWriter for knowledge entry markdown notes"
```

---

### Task 5: Vector Writer

**Files:**
- Create: `core/cognition/memory/vector.py`
- Test: `tests/python/test_dual_writer.py` (vector section — append)

- [ ] **Step 1: Write failing tests for VectorWriter**

Append to `tests/python/test_dual_writer.py`:

```python
class TestVectorWriter:
    @pytest.fixture
    def writer(self, tmp_path):
        from core.cognition.memory.vector import VectorWriter

        db_path = str(tmp_path / "knowledge.db")
        return VectorWriter(db_path)

    @pytest.fixture
    def sample_entry(self):
        from core.cognition.memory.schemas import KnowledgeEntry

        return KnowledgeEntry(
            title="Laravel Sanctum Auth Setup",
            category="pattern",
            tags=["laravel", "auth", "sanctum"],
            stacks=["laravel", "php"],
            content="Use Sanctum for SPA and API authentication in Laravel projects.",
            source_project="client_commerce",
            applicable_to="laravel",
        )

    def test_write_indexes_entry(self, writer, sample_entry):
        result = writer.write(sample_entry)
        assert result is True

    def test_search_finds_entry(self, writer, sample_entry):
        writer.write(sample_entry)
        results = writer.search("authentication Laravel API")
        assert len(results) >= 1
        assert results[0]["title"] == "Laravel Sanctum Auth Setup"

    def test_search_returns_metadata(self, writer, sample_entry):
        writer.write(sample_entry)
        results = writer.search("Sanctum auth")
        assert len(results) >= 1
        assert "entry_id" in results[0]
        assert "confidence" in results[0]
        assert "applicable_to" in results[0]

    def test_update_replaces_entry(self, writer, sample_entry):
        writer.write(sample_entry)
        sample_entry.confidence = 0.9
        sample_entry.content = "Updated: Use Sanctum v4 with new token rotation."
        writer.write(sample_entry)
        results = writer.search("Sanctum")
        # Should find exactly one, not duplicate
        matching = [r for r in results if r["entry_id"] == sample_entry.id]
        assert len(matching) == 1
        assert matching[0]["confidence"] == 0.9
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/andreagroferreira/AIProjects/arka-os && python -m pytest tests/python/test_dual_writer.py::TestVectorWriter -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement VectorWriter**

```python
# core/cognition/memory/vector.py
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from core.cognition.memory.schemas import KnowledgeEntry

try:
    from core.knowledge.embedder import embed, is_available as embedder_available
except ImportError:
    embedder_available = lambda: False
    embed = lambda t: None


class VectorWriter:
    """Writes KnowledgeEntry objects to SQLite with vector embeddings for semantic search."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._has_embedder = embedder_available()
        self._init_tables()

    def _init_tables(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS knowledge_entries (
                id TEXT PRIMARY KEY,
                entry_id TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                tags TEXT NOT NULL DEFAULT '[]',
                stacks TEXT NOT NULL DEFAULT '[]',
                content TEXT NOT NULL,
                source_project TEXT NOT NULL,
                applicable_to TEXT NOT NULL DEFAULT 'any',
                confidence REAL NOT NULL DEFAULT 0.5,
                times_used INTEGER NOT NULL DEFAULT 0,
                embedding BLOB,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_ke_entry_id ON knowledge_entries(entry_id);
            CREATE INDEX IF NOT EXISTS idx_ke_category ON knowledge_entries(category);
            CREATE INDEX IF NOT EXISTS idx_ke_applicable ON knowledge_entries(applicable_to);
            """
        )
        self._conn.commit()

    def write(self, entry: KnowledgeEntry) -> bool:
        search_text = f"{entry.title} {' '.join(entry.tags)} {entry.content}"
        embedding = None
        if self._has_embedder:
            embedding = embed(search_text)

        embedding_blob = None
        if embedding is not None:
            import struct
            embedding_blob = struct.pack(f"{len(embedding)}f", *embedding)

        self._conn.execute(
            """
            INSERT INTO knowledge_entries
                (id, entry_id, title, category, tags, stacks, content,
                 source_project, applicable_to, confidence, times_used,
                 embedding, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(entry_id) DO UPDATE SET
                title = excluded.title,
                category = excluded.category,
                tags = excluded.tags,
                stacks = excluded.stacks,
                content = excluded.content,
                confidence = excluded.confidence,
                times_used = excluded.times_used,
                embedding = excluded.embedding,
                updated_at = excluded.updated_at
            """,
            (
                entry.id,
                entry.id,
                entry.title,
                entry.category,
                json.dumps(entry.tags),
                json.dumps(entry.stacks),
                entry.content,
                entry.source_project,
                entry.applicable_to,
                entry.confidence,
                entry.times_used,
                embedding_blob,
                entry.created_at.isoformat(),
                entry.updated_at.isoformat(),
            ),
        )
        self._conn.commit()
        return True

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """Search knowledge entries. Uses embedding similarity if available, falls back to text search."""
        if self._has_embedder:
            return self._search_semantic(query, top_k)
        return self._search_text(query, top_k)

    def _search_semantic(self, query: str, top_k: int) -> list[dict]:
        import struct

        query_embedding = embed(query)
        if query_embedding is None:
            return self._search_text(query, top_k)

        rows = self._conn.execute(
            "SELECT * FROM knowledge_entries WHERE embedding IS NOT NULL"
        ).fetchall()

        scored = []
        for row in rows:
            stored = struct.unpack(f"{len(row['embedding']) // 4}f", row["embedding"])
            sim = sum(a * b for a, b in zip(query_embedding, stored))
            scored.append((sim, row))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [self._row_to_result(row) for _, row in scored[:top_k]]

    def _search_text(self, query: str, top_k: int) -> list[dict]:
        terms = query.lower().split()
        rows = self._conn.execute(
            "SELECT * FROM knowledge_entries"
        ).fetchall()

        scored = []
        for row in rows:
            text = f"{row['title']} {row['tags']} {row['content']}".lower()
            score = sum(1 for t in terms if t in text)
            if score > 0:
                scored.append((score, row))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [self._row_to_result(row) for _, row in scored[:top_k]]

    def _row_to_result(self, row: sqlite3.Row) -> dict:
        return {
            "entry_id": row["entry_id"],
            "title": row["title"],
            "category": row["category"],
            "tags": json.loads(row["tags"]),
            "stacks": json.loads(row["stacks"]),
            "content": row["content"],
            "source_project": row["source_project"],
            "applicable_to": row["applicable_to"],
            "confidence": row["confidence"],
            "times_used": row["times_used"],
        }

    def close(self) -> None:
        self._conn.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/andreagroferreira/AIProjects/arka-os && python -m pytest tests/python/test_dual_writer.py::TestVectorWriter -v`
Expected: 4 passed (using text fallback search since embedder may not be available in test)

- [ ] **Step 5: Commit**

```bash
git add core/cognition/memory/vector.py tests/python/test_dual_writer.py
git commit -m "feat(cognition): add VectorWriter with semantic search and text fallback"
```

---

### Task 6: DualWriter (Unified Interface)

**Files:**
- Create: `core/cognition/memory/writer.py`
- Test: `tests/python/test_dual_writer.py` (DualWriter section — append)

- [ ] **Step 1: Write failing tests for DualWriter**

Append to `tests/python/test_dual_writer.py`:

```python
class TestDualWriter:
    @pytest.fixture
    def writer(self, tmp_path):
        from core.cognition.memory.writer import DualWriter

        return DualWriter(
            obsidian_base=str(tmp_path / "vault" / "Knowledge Base"),
            vector_db_path=str(tmp_path / "knowledge.db"),
        )

    @pytest.fixture
    def sample_entry(self):
        from core.cognition.memory.schemas import KnowledgeEntry

        return KnowledgeEntry(
            title="Repository Pattern Laravel",
            category="pattern",
            tags=["laravel", "repository", "architecture"],
            stacks=["laravel", "php"],
            content="Use repositories to abstract Eloquent queries behind interfaces.",
            source_project="client_retail",
            applicable_to="laravel",
        )

    def test_write_persists_to_both(self, writer, sample_entry, tmp_path):
        result = writer.write(sample_entry)
        assert result.obsidian_path is not None
        assert result.vector_indexed is True
        assert Path(result.obsidian_path).exists()

    def test_write_survives_obsidian_failure(self, tmp_path):
        from core.cognition.memory.writer import DualWriter
        from core.cognition.memory.schemas import KnowledgeEntry

        writer = DualWriter(
            obsidian_base="/nonexistent/path/that/cannot/be/created",
            vector_db_path=str(tmp_path / "knowledge.db"),
        )
        entry = KnowledgeEntry(
            title="Test",
            category="pattern",
            tags=[],
            stacks=[],
            content="test",
            source_project="test",
            applicable_to="any",
        )
        result = writer.write(entry)
        assert result.obsidian_path is None
        assert result.obsidian_error is not None
        assert result.vector_indexed is True

    def test_search_delegates_to_vector(self, writer, sample_entry):
        writer.write(sample_entry)
        results = writer.search("repository pattern Eloquent")
        assert len(results) >= 1
        assert results[0]["title"] == "Repository Pattern Laravel"

    def test_write_returns_stats(self, writer, sample_entry):
        result = writer.write(sample_entry)
        assert hasattr(result, "obsidian_path")
        assert hasattr(result, "vector_indexed")
        assert hasattr(result, "obsidian_error")
        assert hasattr(result, "vector_error")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/andreagroferreira/AIProjects/arka-os && python -m pytest tests/python/test_dual_writer.py::TestDualWriter -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement DualWriter**

```python
# core/cognition/memory/writer.py
from __future__ import annotations

from dataclasses import dataclass

from core.cognition.memory.obsidian import ObsidianWriter
from core.cognition.memory.schemas import KnowledgeEntry
from core.cognition.memory.vector import VectorWriter


@dataclass
class WriteResult:
    obsidian_path: str | None = None
    obsidian_error: str | None = None
    vector_indexed: bool = False
    vector_error: str | None = None


class DualWriter:
    """Unified interface for dual-writing KnowledgeEntries to Obsidian + Vector DB."""

    def __init__(self, obsidian_base: str, vector_db_path: str) -> None:
        self._obsidian = ObsidianWriter(obsidian_base)
        self._vector = VectorWriter(vector_db_path)

    def write(self, entry: KnowledgeEntry) -> WriteResult:
        result = WriteResult()

        # Write to Obsidian
        try:
            result.obsidian_path = self._obsidian.write(entry)
        except Exception as e:
            result.obsidian_error = str(e)

        # Write to Vector DB
        try:
            result.vector_indexed = self._vector.write(entry)
        except Exception as e:
            result.vector_error = str(e)
            result.vector_indexed = False

        return result

    def write_batch(self, entries: list[KnowledgeEntry]) -> list[WriteResult]:
        return [self.write(entry) for entry in entries]

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        return self._vector.search(query, top_k)

    def close(self) -> None:
        self._vector.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/andreagroferreira/AIProjects/arka-os && python -m pytest tests/python/test_dual_writer.py::TestDualWriter -v`
Expected: 4 passed

- [ ] **Step 5: Update core/cognition/__init__.py exports and commit**

Update `core/cognition/__init__.py`:

```python
"""ArkaOS Cognitive Layer — Memory, Dreaming, Research."""

from .memory.writer import DualWriter
from .capture.store import CaptureStore
from .insights.store import InsightStore

__all__ = ["DualWriter", "CaptureStore", "InsightStore"]
```

```bash
git add core/cognition/memory/writer.py core/cognition/__init__.py tests/python/test_dual_writer.py
git commit -m "feat(cognition): add DualWriter unified interface for Obsidian + Vector DB"
```

---

## Phase 3: Research Profiler

### Task 7: Research Profiler

**Files:**
- Create: `core/cognition/research/__init__.py`
- Create: `core/cognition/research/profiler.py`
- Test: `tests/python/test_research_profiler.py`

- [ ] **Step 1: Write failing tests for ResearchProfiler**

```python
# tests/python/test_research_profiler.py
import pytest
from pathlib import Path


class TestResearchProfiler:
    @pytest.fixture
    def ecosystems_path(self, tmp_path):
        import json

        eco_file = tmp_path / "ecosystems.json"
        eco_file.write_text(json.dumps({
            "ecosystems": {
                "client_commerce": {
                    "projects": [
                        {"name": "client_commerce-supplier-sync", "stack": "laravel", "path": "/Users/dev/Herd/client_commerce"},
                        {"name": "client_commerce-shopify-theme", "stack": "shopify-liquid", "path": "/Users/dev/Work/client_commerce-theme"},
                    ],
                    "domain": "ecommerce",
                },
                "client_video": {
                    "projects": [
                        {"name": "client_video-frontend", "stack": "nuxt", "path": "/Users/dev/Work/client_video"},
                    ],
                    "domain": "media",
                },
            }
        }))
        return str(eco_file)

    @pytest.fixture
    def profiler(self, ecosystems_path):
        from core.cognition.research.profiler import ResearchProfiler

        return ResearchProfiler(ecosystems_path)

    def test_infer_stacks(self, profiler):
        profile = profiler.build_profile()
        assert "laravel" in profile.stacks
        assert "nuxt" in profile.stacks
        assert "shopify-liquid" in profile.stacks

    def test_infer_domains(self, profiler):
        profile = profiler.build_profile()
        assert "ecommerce" in profile.domains
        assert "media" in profile.domains

    def test_generates_topics(self, profiler):
        profile = profiler.build_profile()
        assert len(profile.topics) > 0
        topic_names = [t.name for t in profile.topics]
        # Should generate stack-related topics
        assert any("laravel" in t.lower() for t in topic_names)

    def test_empty_ecosystems(self, tmp_path):
        import json
        from core.cognition.research.profiler import ResearchProfiler

        eco_file = tmp_path / "eco.json"
        eco_file.write_text(json.dumps({"ecosystems": {}}))
        profiler = ResearchProfiler(str(eco_file))
        profile = profiler.build_profile()
        assert len(profile.stacks) == 0
        assert len(profile.topics) == 0

    def test_profile_to_yaml(self, profiler):
        profile = profiler.build_profile()
        yaml_str = profile.to_yaml()
        assert "stacks:" in yaml_str
        assert "domains:" in yaml_str
        assert "topics:" in yaml_str
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/andreagroferreira/AIProjects/arka-os && python -m pytest tests/python/test_research_profiler.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement ResearchProfiler**

```python
# core/cognition/research/__init__.py
from .profiler import ResearchProfiler

__all__ = ["ResearchProfiler"]
```

```python
# core/cognition/research/profiler.py
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml


STACK_TOPICS = {
    "laravel": [
        "Laravel releases and security patches",
        "Laravel ecosystem packages (Livewire, Filament, Horizon)",
        "PHP security advisories",
    ],
    "nuxt": [
        "Nuxt 3/4 releases and migration guides",
        "Vue 3 ecosystem updates (Pinia, VueUse)",
        "Nitro server engine updates",
    ],
    "react": [
        "React and Next.js releases",
        "React Server Components updates",
        "Vercel platform changes",
    ],
    "python": [
        "Python releases and security patches",
        "Pydantic and FastAPI updates",
        "AI/ML library releases (transformers, langchain)",
    ],
    "shopify-liquid": [
        "Shopify API changes and new endpoints",
        "Shopify theme architecture updates",
        "Shopify app ecosystem trends",
    ],
}

DOMAIN_TOPICS = {
    "ecommerce": [
        "E-commerce conversion rate trends",
        "Marketplace integration updates",
        "Payment processing changes",
    ],
    "media": [
        "Streaming technology updates",
        "Content delivery network trends",
        "Video encoding best practices",
    ],
    "energy": [
        "Energy sector digital transformation",
        "Smart grid technology updates",
    ],
    "ai": [
        "LLM model releases and benchmarks",
        "AI agent framework updates (CrewAI, AutoGen, LangGraph)",
        "AI coding tool updates (Cursor, Windsurf, Claude Code)",
    ],
}


@dataclass
class ResearchTopic:
    name: str
    source: str  # "stack" | "domain" | "tool" | "business"
    search_queries: list[str] = field(default_factory=list)


@dataclass
class ResearchProfile:
    stacks: list[str] = field(default_factory=list)
    domains: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    business_interests: list[str] = field(default_factory=list)
    competitors: list[str] = field(default_factory=list)
    topics: list[ResearchTopic] = field(default_factory=list)

    def to_yaml(self) -> str:
        data = {
            "stacks": self.stacks,
            "domains": self.domains,
            "tools": self.tools,
            "business_interests": self.business_interests,
            "competitors": self.competitors,
            "topics": [
                {"name": t.name, "source": t.source, "search_queries": t.search_queries}
                for t in self.topics
            ],
        }
        return yaml.dump(data, default_flow_style=False, allow_unicode=True)


class ResearchProfiler:
    """Infers a research profile from the user's active projects and ecosystems."""

    def __init__(self, ecosystems_path: str) -> None:
        self._ecosystems_path = ecosystems_path

    def _load_ecosystems(self) -> dict:
        path = Path(self._ecosystems_path)
        if not path.exists():
            return {}
        with open(path) as f:
            data = json.load(f)
        return data.get("ecosystems", {})

    def build_profile(self) -> ResearchProfile:
        ecosystems = self._load_ecosystems()
        profile = ResearchProfile()

        # Extract stacks and domains from ecosystems
        for eco_name, eco_data in ecosystems.items():
            projects = eco_data.get("projects", [])
            for proj in projects:
                stack = proj.get("stack", "")
                if stack and stack not in profile.stacks:
                    profile.stacks.append(stack)

            domain = eco_data.get("domain", "")
            if domain and domain not in profile.domains:
                profile.domains.append(domain)

        # Generate topics from stacks
        for stack in profile.stacks:
            stack_key = stack.lower().split("-")[0] if "-" in stack else stack.lower()
            topic_names = STACK_TOPICS.get(stack_key, [])
            for name in topic_names:
                topic = ResearchTopic(
                    name=name,
                    source="stack",
                    search_queries=[name],
                )
                if not any(t.name == name for t in profile.topics):
                    profile.topics.append(topic)

        # Generate topics from domains
        for domain in profile.domains:
            topic_names = DOMAIN_TOPICS.get(domain.lower(), [])
            for name in topic_names:
                topic = ResearchTopic(
                    name=name,
                    source="domain",
                    search_queries=[name],
                )
                if not any(t.name == name for t in profile.topics):
                    profile.topics.append(topic)

        return profile
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/andreagroferreira/AIProjects/arka-os && python -m pytest tests/python/test_research_profiler.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add core/cognition/research/ tests/python/test_research_profiler.py
git commit -m "feat(cognition): add ResearchProfiler for adaptive topic inference"
```

---

## Phase 4: Scheduler

### Task 8: Scheduler Daemon

**Files:**
- Create: `core/cognition/scheduler/__init__.py`
- Create: `core/cognition/scheduler/daemon.py`
- Test: `tests/python/test_scheduler_daemon.py`

- [ ] **Step 1: Write failing tests for ArkaScheduler**

```python
# tests/python/test_scheduler_daemon.py
import pytest
from pathlib import Path
from datetime import time


class TestScheduleConfig:
    def test_load_from_yaml(self, tmp_path):
        from core.cognition.scheduler.daemon import ScheduleConfig

        yaml_content = """
schedules:
  dreaming:
    command: dreaming
    prompt_file: "~/.arkaos/cognition/prompts/dreaming.md"
    time: "02:00"
    timezone: auto
    enabled: true
    retry_on_fail: true
    max_retries: 2
    timeout_minutes: 60
  research:
    command: research
    prompt_file: "~/.arkaos/cognition/prompts/research.md"
    time: "05:00"
    timezone: auto
    enabled: true
    retry_on_fail: true
    max_retries: 2
    timeout_minutes: 90
"""
        config_file = tmp_path / "schedules.yaml"
        config_file.write_text(yaml_content)

        configs = ScheduleConfig.load(str(config_file))
        assert len(configs) == 2
        assert configs[0].command == "dreaming"
        assert configs[0].run_time == time(2, 0)
        assert configs[0].timeout_minutes == 60
        assert configs[1].command == "research"
        assert configs[1].run_time == time(5, 0)

    def test_disabled_schedule_excluded(self, tmp_path):
        from core.cognition.scheduler.daemon import ScheduleConfig

        yaml_content = """
schedules:
  dreaming:
    command: dreaming
    prompt_file: "~/.arkaos/prompts/dreaming.md"
    time: "02:00"
    enabled: false
"""
        config_file = tmp_path / "schedules.yaml"
        config_file.write_text(yaml_content)

        configs = ScheduleConfig.load(str(config_file))
        assert len(configs) == 0


class TestArkaScheduler:
    @pytest.fixture
    def scheduler(self, tmp_path):
        from core.cognition.scheduler.daemon import ArkaScheduler

        config_file = tmp_path / "schedules.yaml"
        config_file.write_text("""
schedules:
  test_job:
    command: test
    prompt_file: "{prompt}"
    time: "02:00"
    enabled: true
    retry_on_fail: false
    max_retries: 0
    timeout_minutes: 5
""".format(prompt=str(tmp_path / "test.md")))

        prompt_file = tmp_path / "test.md"
        prompt_file.write_text("Test prompt")

        log_dir = tmp_path / "logs"
        lock_file = tmp_path / "scheduler.lock"

        return ArkaScheduler(
            config_path=str(config_file),
            log_dir=str(log_dir),
            lock_path=str(lock_file),
        )

    def test_loads_schedules(self, scheduler):
        assert len(scheduler.schedules) == 1
        assert scheduler.schedules[0].command == "test"

    def test_should_run_at_correct_time(self, scheduler):
        from datetime import time as dt_time

        schedule = scheduler.schedules[0]
        assert scheduler._should_run(schedule, dt_time(2, 0))
        assert not scheduler._should_run(schedule, dt_time(3, 0))

    def test_build_claude_command(self, scheduler):
        schedule = scheduler.schedules[0]
        cmd = scheduler._build_command(schedule)
        assert "claude" in cmd[0]
        assert "--dangerously-skip-permissions" in cmd

    def test_lock_prevents_duplicate(self, scheduler):
        assert scheduler.acquire_lock() is True
        # Second instance should fail
        from core.cognition.scheduler.daemon import ArkaScheduler
        scheduler2 = ArkaScheduler(
            config_path=scheduler._config_path,
            log_dir=scheduler._log_dir,
            lock_path=scheduler._lock_path,
        )
        assert scheduler2.acquire_lock() is False
        scheduler.release_lock()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/andreagroferreira/AIProjects/arka-os && python -m pytest tests/python/test_scheduler_daemon.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement ArkaScheduler**

```python
# core/cognition/scheduler/__init__.py
from .daemon import ArkaScheduler

__all__ = ["ArkaScheduler"]
```

```python
# core/cognition/scheduler/daemon.py
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, time
from pathlib import Path

import yaml

logger = logging.getLogger("arkaos.scheduler")


@dataclass
class ScheduleConfig:
    command: str
    prompt_file: str
    run_time: time
    enabled: bool = True
    retry_on_fail: bool = True
    max_retries: int = 2
    timeout_minutes: int = 60

    @classmethod
    def load(cls, config_path: str) -> list[ScheduleConfig]:
        with open(config_path) as f:
            data = yaml.safe_load(f)

        configs = []
        for name, sched in data.get("schedules", {}).items():
            if not sched.get("enabled", True):
                continue
            h, m = sched["time"].split(":")
            configs.append(
                cls(
                    command=sched["command"],
                    prompt_file=os.path.expanduser(sched.get("prompt_file", "")),
                    run_time=time(int(h), int(m)),
                    enabled=sched.get("enabled", True),
                    retry_on_fail=sched.get("retry_on_fail", True),
                    max_retries=sched.get("max_retries", 2),
                    timeout_minutes=sched.get("timeout_minutes", 60),
                )
            )
        return configs


class ArkaScheduler:
    """Cross-platform scheduler for ArkaOS cognitive tasks."""

    def __init__(
        self,
        config_path: str,
        log_dir: str,
        lock_path: str,
    ) -> None:
        self._config_path = config_path
        self._log_dir = log_dir
        self._lock_path = lock_path
        self._lock_fd = None
        self.schedules = ScheduleConfig.load(config_path)

    def acquire_lock(self) -> bool:
        try:
            Path(self._lock_path).parent.mkdir(parents=True, exist_ok=True)
            self._lock_fd = open(self._lock_path, "w")
            if sys.platform == "win32":
                import msvcrt
                try:
                    msvcrt.locking(self._lock_fd.fileno(), msvcrt.LK_NBLCK, 1)
                    return True
                except (IOError, OSError):
                    self._lock_fd.close()
                    self._lock_fd = None
                    return False
            else:
                import fcntl
                try:
                    fcntl.flock(self._lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    self._lock_fd.write(str(os.getpid()))
                    self._lock_fd.flush()
                    return True
                except (IOError, OSError):
                    self._lock_fd.close()
                    self._lock_fd = None
                    return False
        except Exception:
            return False

    def release_lock(self) -> None:
        if self._lock_fd:
            try:
                self._lock_fd.close()
            except Exception:
                pass
            try:
                os.unlink(self._lock_path)
            except Exception:
                pass
            self._lock_fd = None

    def _should_run(self, schedule: ScheduleConfig, current_time: time) -> bool:
        return (
            schedule.run_time.hour == current_time.hour
            and schedule.run_time.minute == current_time.minute
        )

    def _build_command(self, schedule: ScheduleConfig) -> list[str]:
        claude_bin = shutil.which("claude") or "claude"
        prompt_path = Path(schedule.prompt_file)

        if prompt_path.exists():
            prompt_arg = prompt_path.read_text(encoding="utf-8")
        else:
            prompt_arg = f"Run ArkaOS {schedule.command} cognitive task."

        return [
            claude_bin,
            "-p",
            prompt_arg,
            "--dangerously-skip-permissions",
        ]

    def execute(self, schedule: ScheduleConfig) -> bool:
        log_dir = Path(self._log_dir) / schedule.command
        log_dir.mkdir(parents=True, exist_ok=True)

        today = datetime.now().strftime("%Y-%m-%d")
        log_file = log_dir / f"{today}.log"

        cmd = self._build_command(schedule)
        timeout = schedule.timeout_minutes * 60

        logger.info(f"Starting {schedule.command} (timeout: {schedule.timeout_minutes}m)")

        try:
            with open(log_file, "a") as lf:
                lf.write(f"\n--- {datetime.now().isoformat()} ---\n")
                result = subprocess.run(
                    cmd,
                    stdout=lf,
                    stderr=subprocess.STDOUT,
                    timeout=timeout,
                    cwd=os.path.expanduser("~"),
                )
            success = result.returncode == 0
            logger.info(f"{schedule.command} completed (exit={result.returncode})")
            return success
        except subprocess.TimeoutExpired:
            logger.error(f"{schedule.command} timed out after {schedule.timeout_minutes}m")
            return False
        except Exception as e:
            logger.error(f"{schedule.command} failed: {e}")
            return False

    def run_once(self) -> None:
        current = datetime.now().time()
        for schedule in self.schedules:
            if self._should_run(schedule, current):
                retries = 0
                while True:
                    success = self.execute(schedule)
                    if success or not schedule.retry_on_fail:
                        break
                    retries += 1
                    if retries > schedule.max_retries:
                        logger.error(
                            f"{schedule.command} failed after {retries} retries"
                        )
                        break
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/andreagroferreira/AIProjects/arka-os && python -m pytest tests/python/test_scheduler_daemon.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add core/cognition/scheduler/ tests/python/test_scheduler_daemon.py
git commit -m "feat(cognition): add ArkaScheduler with cross-platform locking and schedule config"
```

---

### Task 9: Platform Adapters

**Files:**
- Create: `core/cognition/scheduler/platform.py`
- Test: `tests/python/test_scheduler_platform.py`

- [ ] **Step 1: Write failing tests for platform adapters**

```python
# tests/python/test_scheduler_platform.py
import pytest
import sys


class TestPlatformDetection:
    def test_detect_returns_adapter(self):
        from core.cognition.scheduler.platform import detect_platform

        adapter = detect_platform()
        assert adapter is not None
        assert hasattr(adapter, "install_service")
        assert hasattr(adapter, "uninstall_service")
        assert hasattr(adapter, "is_running")

    def test_detect_matches_current_os(self):
        from core.cognition.scheduler.platform import detect_platform

        adapter = detect_platform()
        if sys.platform == "darwin":
            assert adapter.platform_name == "macos"
        elif sys.platform == "linux":
            assert adapter.platform_name == "linux"
        elif sys.platform == "win32":
            assert adapter.platform_name == "windows"


class TestMacOSAdapter:
    @pytest.fixture
    def adapter(self, tmp_path):
        from core.cognition.scheduler.platform import MacOSAdapter

        return MacOSAdapter(
            daemon_script=str(tmp_path / "daemon.py"),
            plist_dir=str(tmp_path / "LaunchAgents"),
        )

    def test_generates_plist(self, adapter):
        plist = adapter._generate_plist()
        assert "com.arkaos.scheduler" in plist
        assert "<key>Label</key>" in plist
        assert "ProgramArguments" in plist

    def test_plist_path(self, adapter, tmp_path):
        expected = str(tmp_path / "LaunchAgents" / "com.arkaos.scheduler.plist")
        assert adapter._plist_path() == expected


class TestLinuxAdapter:
    @pytest.fixture
    def adapter(self, tmp_path):
        from core.cognition.scheduler.platform import LinuxAdapter

        return LinuxAdapter(
            daemon_script=str(tmp_path / "daemon.py"),
            service_dir=str(tmp_path / "systemd" / "user"),
        )

    def test_generates_unit_file(self, adapter):
        unit = adapter._generate_unit()
        assert "[Unit]" in unit
        assert "[Service]" in unit
        assert "arkaos-scheduler" in unit

    def test_service_path(self, adapter, tmp_path):
        expected = str(tmp_path / "systemd" / "user" / "arkaos-scheduler.service")
        assert adapter._service_path() == expected


class TestWindowsAdapter:
    @pytest.fixture
    def adapter(self, tmp_path):
        from core.cognition.scheduler.platform import WindowsAdapter

        return WindowsAdapter(
            daemon_script=str(tmp_path / "daemon.py"),
        )

    def test_generates_task_command(self, adapter):
        cmd = adapter._build_schtasks_command()
        assert "schtasks" in cmd[0] or "SCHTASKS" in cmd[0].upper()
        assert "ArkaOS-Scheduler" in " ".join(cmd)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/andreagroferreira/AIProjects/arka-os && python -m pytest tests/python/test_scheduler_platform.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement platform adapters**

```python
# core/cognition/scheduler/platform.py
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from abc import ABC, abstractmethod
from pathlib import Path


class PlatformAdapter(ABC):
    platform_name: str

    @abstractmethod
    def install_service(self) -> bool: ...

    @abstractmethod
    def uninstall_service(self) -> bool: ...

    @abstractmethod
    def is_running(self) -> bool: ...

    @abstractmethod
    def start(self) -> bool: ...

    @abstractmethod
    def stop(self) -> bool: ...


class MacOSAdapter(PlatformAdapter):
    platform_name = "macos"

    def __init__(self, daemon_script: str, plist_dir: str | None = None) -> None:
        self._daemon_script = daemon_script
        self._plist_dir = plist_dir or os.path.expanduser("~/Library/LaunchAgents")

    def _plist_path(self) -> str:
        return str(Path(self._plist_dir) / "com.arkaos.scheduler.plist")

    def _generate_plist(self) -> str:
        python = shutil.which("python3") or sys.executable
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.arkaos.scheduler</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python}</string>
        <string>{self._daemon_script}</string>
        <string>--run-loop</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{os.path.expanduser("~/.arkaos/logs/scheduler-stdout.log")}</string>
    <key>StandardErrorPath</key>
    <string>{os.path.expanduser("~/.arkaos/logs/scheduler-stderr.log")}</string>
</dict>
</plist>"""

    def install_service(self) -> bool:
        plist_path = self._plist_path()
        Path(plist_path).parent.mkdir(parents=True, exist_ok=True)
        Path(plist_path).write_text(self._generate_plist())
        return True

    def uninstall_service(self) -> bool:
        self.stop()
        plist_path = self._plist_path()
        if Path(plist_path).exists():
            Path(plist_path).unlink()
        return True

    def start(self) -> bool:
        try:
            subprocess.run(["launchctl", "load", self._plist_path()], check=True)
            return True
        except Exception:
            return False

    def stop(self) -> bool:
        try:
            subprocess.run(["launchctl", "unload", self._plist_path()],
                           check=False, capture_output=True)
            return True
        except Exception:
            return False

    def is_running(self) -> bool:
        try:
            result = subprocess.run(
                ["launchctl", "list", "com.arkaos.scheduler"],
                capture_output=True, text=True,
            )
            return result.returncode == 0
        except Exception:
            return False


class LinuxAdapter(PlatformAdapter):
    platform_name = "linux"

    def __init__(self, daemon_script: str, service_dir: str | None = None) -> None:
        self._daemon_script = daemon_script
        self._service_dir = service_dir or os.path.expanduser(
            "~/.config/systemd/user"
        )

    def _service_path(self) -> str:
        return str(Path(self._service_dir) / "arkaos-scheduler.service")

    def _generate_unit(self) -> str:
        python = shutil.which("python3") or sys.executable
        return f"""[Unit]
Description=ArkaOS Cognitive Scheduler
After=default.target

[Service]
Type=simple
ExecStart={python} {self._daemon_script} --run-loop
Restart=on-failure
RestartSec=60

[Install]
WantedBy=default.target
"""

    def install_service(self) -> bool:
        service_path = self._service_path()
        Path(service_path).parent.mkdir(parents=True, exist_ok=True)
        Path(service_path).write_text(self._generate_unit())
        return True

    def uninstall_service(self) -> bool:
        self.stop()
        service_path = self._service_path()
        if Path(service_path).exists():
            Path(service_path).unlink()
        return True

    def start(self) -> bool:
        try:
            subprocess.run(["systemctl", "--user", "enable", "--now", "arkaos-scheduler"],
                           check=True)
            return True
        except Exception:
            return False

    def stop(self) -> bool:
        try:
            subprocess.run(["systemctl", "--user", "stop", "arkaos-scheduler"],
                           check=False, capture_output=True)
            return True
        except Exception:
            return False

    def is_running(self) -> bool:
        try:
            result = subprocess.run(
                ["systemctl", "--user", "is-active", "arkaos-scheduler"],
                capture_output=True, text=True,
            )
            return result.stdout.strip() == "active"
        except Exception:
            return False


class WindowsAdapter(PlatformAdapter):
    platform_name = "windows"

    def __init__(self, daemon_script: str) -> None:
        self._daemon_script = daemon_script

    def _build_schtasks_command(self) -> list[str]:
        python = shutil.which("pythonw") or shutil.which("python") or sys.executable
        return [
            "schtasks", "/Create",
            "/TN", "ArkaOS-Scheduler",
            "/TR", f'"{python}" "{self._daemon_script}" --run-loop',
            "/SC", "ONLOGON",
            "/F",
        ]

    def install_service(self) -> bool:
        try:
            subprocess.run(self._build_schtasks_command(), check=True)
            return True
        except Exception:
            return False

    def uninstall_service(self) -> bool:
        try:
            subprocess.run(["schtasks", "/Delete", "/TN", "ArkaOS-Scheduler", "/F"],
                           check=True)
            return True
        except Exception:
            return False

    def start(self) -> bool:
        try:
            subprocess.run(["schtasks", "/Run", "/TN", "ArkaOS-Scheduler"], check=True)
            return True
        except Exception:
            return False

    def stop(self) -> bool:
        try:
            subprocess.run(["schtasks", "/End", "/TN", "ArkaOS-Scheduler"],
                           check=False, capture_output=True)
            return True
        except Exception:
            return False

    def is_running(self) -> bool:
        try:
            result = subprocess.run(
                ["schtasks", "/Query", "/TN", "ArkaOS-Scheduler"],
                capture_output=True, text=True,
            )
            return "Running" in result.stdout
        except Exception:
            return False


def detect_platform() -> PlatformAdapter:
    home = os.path.expanduser("~")
    daemon_script = os.path.join(home, ".arkaos", "bin", "scheduler-daemon.py")

    if sys.platform == "darwin":
        return MacOSAdapter(daemon_script)
    elif sys.platform == "linux":
        return LinuxAdapter(daemon_script)
    elif sys.platform == "win32":
        return WindowsAdapter(daemon_script)
    else:
        raise RuntimeError(f"Unsupported platform: {sys.platform}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/andreagroferreira/AIProjects/arka-os && python -m pytest tests/python/test_scheduler_platform.py -v`
Expected: All tests pass (platform-specific tests run on current OS)

- [ ] **Step 5: Commit**

```bash
git add core/cognition/scheduler/platform.py tests/python/test_scheduler_platform.py
git commit -m "feat(cognition): add cross-platform service adapters (macOS/Linux/Windows)"
```

---

### Task 10: Scheduler CLI

**Files:**
- Create: `core/cognition/scheduler/cli.py`
- Test: `tests/python/test_scheduler_daemon.py` (append CLI tests)

- [ ] **Step 1: Write failing tests for CLI**

Append to `tests/python/test_scheduler_daemon.py`:

```python
class TestSchedulerCLI:
    @pytest.fixture
    def cli_env(self, tmp_path):
        """Set up a minimal scheduler environment for CLI testing."""
        config_file = tmp_path / "schedules.yaml"
        config_file.write_text("""
schedules:
  dreaming:
    command: dreaming
    prompt_file: "{prompt}"
    time: "02:00"
    enabled: true
    retry_on_fail: false
    max_retries: 0
    timeout_minutes: 5
  research:
    command: research
    prompt_file: "{prompt}"
    time: "05:00"
    enabled: true
    retry_on_fail: false
    max_retries: 0
    timeout_minutes: 5
""".format(prompt=str(tmp_path / "test.md")))

        (tmp_path / "test.md").write_text("Test prompt")

        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        return {
            "config_path": str(config_file),
            "log_dir": str(log_dir),
            "lock_path": str(tmp_path / "scheduler.lock"),
        }

    def test_status_output(self, cli_env):
        from core.cognition.scheduler.cli import scheduler_status

        output = scheduler_status(**cli_env)
        assert "dreaming" in output.lower()
        assert "research" in output.lower()
        assert "02:00" in output
        assert "05:00" in output

    def test_list_schedules(self, cli_env):
        from core.cognition.scheduler.cli import list_schedules

        schedules = list_schedules(cli_env["config_path"])
        assert len(schedules) == 2
        assert schedules[0]["command"] == "dreaming"
        assert schedules[1]["command"] == "research"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/andreagroferreira/AIProjects/arka-os && python -m pytest tests/python/test_scheduler_daemon.py::TestSchedulerCLI -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement CLI functions**

```python
# core/cognition/scheduler/cli.py
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from core.cognition.scheduler.daemon import ArkaScheduler, ScheduleConfig
from core.cognition.scheduler.platform import detect_platform


def list_schedules(config_path: str) -> list[dict]:
    configs = ScheduleConfig.load(config_path)
    return [
        {
            "command": c.command,
            "time": c.run_time.strftime("%H:%M"),
            "timeout": c.timeout_minutes,
            "retry": c.retry_on_fail,
        }
        for c in configs
    ]


def scheduler_status(config_path: str, log_dir: str, lock_path: str) -> str:
    lines = ["=== ArkaOS Scheduler Status ===", ""]

    # Check if running
    if Path(lock_path).exists():
        lines.append("Status: RUNNING")
    else:
        lines.append("Status: STOPPED")
    lines.append("")

    # List schedules
    schedules = list_schedules(config_path)
    lines.append("Schedules:")
    for s in schedules:
        retry = "retry" if s["retry"] else "no-retry"
        lines.append(f"  {s['command']:12s} at {s['time']}  (timeout: {s['timeout']}m, {retry})")
    lines.append("")

    # Last run info
    lines.append("Last runs:")
    for s in schedules:
        log_path = Path(log_dir) / s["command"]
        if log_path.exists():
            logs = sorted(log_path.glob("*.log"), reverse=True)
            if logs:
                last = logs[0].stem
                lines.append(f"  {s['command']:12s} last: {last}")
            else:
                lines.append(f"  {s['command']:12s} last: never")
        else:
            lines.append(f"  {s['command']:12s} last: never")

    lines.append("")
    lines.append("=" * 31)
    return "\n".join(lines)


def run_now(command: str, config_path: str, log_dir: str, lock_path: str) -> bool:
    scheduler = ArkaScheduler(
        config_path=config_path,
        log_dir=log_dir,
        lock_path=lock_path,
    )
    for schedule in scheduler.schedules:
        if schedule.command == command:
            return scheduler.execute(schedule)
    raise ValueError(f"Unknown schedule command: {command}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/andreagroferreira/AIProjects/arka-os && python -m pytest tests/python/test_scheduler_daemon.py::TestSchedulerCLI -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add core/cognition/scheduler/cli.py tests/python/test_scheduler_daemon.py
git commit -m "feat(cognition): add scheduler CLI commands (status, list, run)"
```

---

## Phase 5: Default Config + Prompts

### Task 11: Default Schedule Config

**Files:**
- Create: `config/cognition/schedules.yaml`

- [ ] **Step 1: Create default schedule config**

```yaml
# config/cognition/schedules.yaml
# ArkaOS Cognitive Layer — Schedule Configuration
#
# This file is deployed to ~/.arkaos/schedules.yaml during installation.
# Edit the deployed copy to customize schedules.

schedules:
  dreaming:
    command: dreaming
    prompt_file: "~/.arkaos/cognition/prompts/dreaming.md"
    time: "02:00"
    timezone: auto
    enabled: true
    retry_on_fail: true
    max_retries: 2
    timeout_minutes: 60

  research:
    command: research
    prompt_file: "~/.arkaos/cognition/prompts/research.md"
    time: "05:00"
    timezone: auto
    enabled: true
    retry_on_fail: true
    max_retries: 2
    timeout_minutes: 90
```

- [ ] **Step 2: Commit**

```bash
git add config/cognition/schedules.yaml
git commit -m "feat(cognition): add default schedule configuration"
```

---

### Task 12: Dreaming Prompt

**Files:**
- Create: `config/cognition/prompts/dreaming.md`

- [ ] **Step 1: Create the Dreaming prompt**

```markdown
# config/cognition/prompts/dreaming.md
```

Content (this is the complete prompt that Claude will receive in the headless session):

````markdown
# ArkaOS Dreaming — Nightly Cognitive Consolidation

You are ArkaOS performing your nightly Dreaming session. Your job is to review everything that happened today, learn from it, critique it, and organize the knowledge for tomorrow.

## Execution Rules

### ALLOWED
- Read any file from any project
- Read git logs and diffs
- Search the web (WebSearch, Firecrawl)
- Write to Obsidian vault at ~/Documents/Personal/Projects/WizardingCode Internal/ArkaOS/
- Write to ~/.arkaos/ (captures, insights, logs, knowledge)
- Use browser for research
- Read online documentation

### PROHIBITED
- npm install, composer require, pip install (zero installations)
- git commit, git push (zero code changes)
- Create/modify code files in projects
- Execute migrations or destructive commands
- Send emails, messages, or communications
- Access production APIs

## Phase 1: Total Collection

1. Read raw captures from today: `~/.arkaos/captures.db`
   - Use Python: `from core.cognition.capture.store import CaptureStore`
   - `store = CaptureStore(os.path.expanduser("~/.arkaos/captures.db"))`
   - `captures = store.get_by_date(date.today())`

2. Read git logs from ALL active projects (check `~/.arkaos/ecosystems.json` for project paths):
   - `git -C <project_path> log --oneline --since="24 hours ago"`
   - `git -C <project_path> diff HEAD~5..HEAD --stat` (last 5 commits)

3. Read claude-mem timeline for today (if available)

4. Compile a complete list of everything that happened today.

If no activity found, write a brief "No Activity" report to Obsidian and exit.

## Phase 2: Critical Analysis

For each task/decision from today, evaluate:
- "Did I do this the best possible way?"
- "Was there a simpler approach?"
- "Did I repeat an error I should already know to avoid?"
- "Does the code follow the project's patterns?"

Classify each decision:
- GOOD — document as validated pattern
- ACCEPTABLE — document with better alternative noted
- ERROR — document what went wrong and why

## Phase 3: Recurring Pattern Detection

Search the existing knowledge base for similar past entries:
- `from core.cognition.memory.vector import VectorWriter`
- Compare today's errors with past errors
- If same error type appears > 2 times → create Anti-Pattern entry
- If same solution appears > 2 times → promote to Validated Pattern
- Detect inconsistencies between projects

## Phase 4: Curation and Consolidation

Group findings into KnowledgeEntry objects:
```python
from core.cognition.memory.schemas import KnowledgeEntry
from core.cognition.memory.writer import DualWriter

writer = DualWriter(
    obsidian_base=os.path.expanduser(
        "~/Documents/Personal/Projects/WizardingCode Internal/ArkaOS/Knowledge Base"
    ),
    vector_db_path=os.path.expanduser("~/.arkaos/knowledge.db"),
)

entry = KnowledgeEntry(
    title="...",
    category="pattern",  # or anti_pattern, solution, lesson, improvement, etc.
    tags=["..."],
    stacks=["..."],
    content="...",
    source_project="...",
    applicable_to="...",
)
writer.write(entry)
```

## Phase 5: Dual-Write

Use `DualWriter.write()` for each KnowledgeEntry. This automatically writes to both Obsidian and Vector DB.

## Phase 6: Report + Evolution Metrics

Write daily report to Obsidian:
`~/Documents/Personal/Projects/WizardingCode Internal/ArkaOS/Dreaming/YYYY-MM-DD.md`

Include:
- Quality Score (0-100) for the day
- Top 3 things learned
- Top 3 things done wrong and how to avoid
- Patterns validated or discovered
- Comparison trend with previous days (read past reports)

## Phase 7: Strategic Reflection — Actionable Insights

For each project worked on today:
1. Review ALL decisions with a business perspective
2. Question: "Does this serve the end user or just the developer?"
3. Question: "Did we consider all business edge cases?"
4. Question: "What do competitors do here?"
5. Cross-reference with any research briefings

Generate ActionableInsight objects:
```python
from core.cognition.memory.schemas import ActionableInsight
from core.cognition.insights.store import InsightStore

insight_store = InsightStore(os.path.expanduser("~/.arkaos/insights.db"))

insight = ActionableInsight(
    project="project_name",
    trigger="dreaming",
    category="business",  # or technical, ux, strategy
    severity="rethink",   # or improve, consider
    title="...",
    description="...",
    recommendation="...",
    context="...",
)
insight_store.save(insight)
```

## Phase 8: Cleanup

Mark processed captures as processed:
```python
store.mark_processed([c.id for c in captures])
```

Write structured metrics to `~/.arkaos/logs/dreaming/YYYY-MM-DD.json`:
```json
{
    "date": "YYYY-MM-DD",
    "quality_score": 75,
    "entries_created": 4,
    "entries_updated": 2,
    "insights_generated": 3,
    "captures_processed": 15,
    "projects_reviewed": ["client_commerce", "client_retail"]
}
```
````

- [ ] **Step 2: Commit**

```bash
git add config/cognition/prompts/dreaming.md
git commit -m "feat(cognition): add Dreaming prompt for nightly consolidation"
```

---

### Task 13: Research Prompt

**Files:**
- Create: `config/cognition/prompts/research.md`

- [ ] **Step 1: Create the Research prompt**

Content (complete prompt for headless Claude session):

````markdown
# ArkaOS Research — Daily Intelligence Gathering

You are ArkaOS performing your daily Research session. Your job is to stay current on everything relevant to the user's active projects, stacks, and business domains.

## Execution Rules

### ALLOWED
- Read any file from any project
- Read git logs
- Search the web extensively (WebSearch, Firecrawl)
- Write to Obsidian vault at ~/Documents/Personal/Projects/WizardingCode Internal/ArkaOS/
- Write to ~/.arkaos/ (insights, logs, knowledge, profiles)
- Use browser for research
- Read online documentation, blogs, changelogs, GitHub releases

### PROHIBITED
- npm install, composer require, pip install (zero installations)
- git commit, git push (zero code changes)
- Create/modify code files in projects
- Execute migrations or destructive commands
- Send emails, messages, or communications
- Access production APIs

## Phase 1: Profile Update

1. Load research profile: `~/.arkaos/cognition/profiles/research-profile.yaml`
2. If it doesn't exist, build it:
```python
from core.cognition.research.profiler import ResearchProfiler

profiler = ResearchProfiler(os.path.expanduser("~/.arkaos/ecosystems.json"))
profile = profiler.build_profile()

# Save profile
Path(os.path.expanduser("~/.arkaos/cognition/profiles")).mkdir(parents=True, exist_ok=True)
Path(os.path.expanduser("~/.arkaos/cognition/profiles/research-profile.yaml")).write_text(
    profile.to_yaml()
)
```
3. Check if any new projects were added since last profile generation
4. Regenerate if context changed

## Phase 2: Research by Topic

For each topic in the profile, search for recent updates:

- **Stack topics:** Search for latest releases, security patches, new features
  - GitHub releases pages for key frameworks
  - Official blogs (Laravel News, Vue blog, Nuxt blog, Python blog)
  - npm/composer/pip security advisories
- **Domain topics:** Search for industry trends, competitor moves, market changes
- **Tool topics:** Search for updates to tools the user relies on
- **Business topics:** Search for market opportunities, competitor funding, industry reports

Use WebSearch and Firecrawl to access content. Read and understand — do not just list headlines.

## Phase 3: Relevance Filtering

Classify each finding:
- URGENT — Security patch, breaking change, immediate action needed
- IMPORTANT — New feature relevant to active projects, market opportunity
- INFORMATIVE — Trend, interesting article, future consideration
- NOISE — Not relevant, already known, too generic

Discard NOISE. Keep the rest sorted by impact.

## Phase 4: Learning

For each relevant finding:
1. Read and understand the content fully
2. Relate to active projects: "How does this affect our work?"
3. Identify concrete actions: "What should we do about this?"
4. Create KnowledgeEntry with application context:

```python
from core.cognition.memory.schemas import KnowledgeEntry
from core.cognition.memory.writer import DualWriter

writer = DualWriter(
    obsidian_base=os.path.expanduser(
        "~/Documents/Personal/Projects/WizardingCode Internal/ArkaOS/Knowledge Base"
    ),
    vector_db_path=os.path.expanduser("~/.arkaos/knowledge.db"),
)

entry = KnowledgeEntry(
    title="...",
    category="...",
    tags=["..."],
    stacks=["..."],
    content="Full explanation of what was learned and how it applies",
    source_project="research",
    applicable_to="...",
)
writer.write(entry)
```

## Phase 5: Cross-Reference with Dreaming

1. Read tonight's Dreaming report (if it exists):
   `~/Documents/Personal/Projects/WizardingCode Internal/ArkaOS/Dreaming/YYYY-MM-DD.md`
2. Read pending insights: `~/.arkaos/insights.db`
3. If research findings reinforce a Dreaming insight, update the insight description
4. If research reveals something actionable for a project, create a new insight:

```python
from core.cognition.memory.schemas import ActionableInsight
from core.cognition.insights.store import InsightStore

store = InsightStore(os.path.expanduser("~/.arkaos/insights.db"))

insight = ActionableInsight(
    project="affected_project",
    trigger="research",
    category="technical",    # or business, ux, strategy
    severity="rethink",      # or improve, consider
    title="...",
    description="...",
    recommendation="...",
    context="Found during daily research: [source]",
)
store.save(insight)
```

## Phase 6: Intelligence Briefing

Write daily briefing to Obsidian:
`~/Documents/Personal/Projects/WizardingCode Internal/ArkaOS/Research/YYYY-MM-DD.md`

Structure:
```markdown
---
date: YYYY-MM-DD
topics_researched: N
findings: N
urgent: N
opportunities: N
---

# Intelligence Briefing — YYYY-MM-DD

## ACTION REQUIRED
[Security patches, breaking changes — with affected projects and fix commands]

## OPPORTUNITIES
[New features, market trends, competitive intelligence — with project impact]

## LEARNINGS
[New knowledge acquired, trends understood, techniques discovered]

## COMPETITOR WATCH
[Updates from competitive landscape]
```

Write structured metrics to `~/.arkaos/logs/research/YYYY-MM-DD.json`:
```json
{
    "date": "YYYY-MM-DD",
    "topics_researched": 14,
    "findings_total": 23,
    "findings_urgent": 2,
    "findings_important": 5,
    "findings_informative": 8,
    "findings_noise": 8,
    "insights_generated": 3,
    "knowledge_entries_created": 5,
    "profile_updated": false
}
```
````

- [ ] **Step 2: Commit**

```bash
git add config/cognition/prompts/research.md
git commit -m "feat(cognition): add Research prompt for daily intelligence gathering"
```

---

## Phase 6: Hook Integration

### Task 14: PreCompact Hook — Raw Capture

**Files:**
- Modify: `config/hooks/pre-compact.sh`

- [ ] **Step 1: Read current pre-compact hook**

Run: `cat ~/.arkaos/config/hooks/pre-compact.sh` (or the source in repo)
Understand the current structure before modifying.

- [ ] **Step 2: Add capture collection to pre-compact hook**

Append to the existing pre-compact hook a section that invokes the capture collector. The hook should:

1. Read the conversation summary from stdin (standard PreCompact behavior)
2. Extract key decisions, solutions, patterns, errors from the summary
3. Write them to `~/.arkaos/captures.db` via a Python one-liner

Add this block at the end of the existing hook:

```bash
# === Cognitive Layer: Raw Capture ===
# Capture session data for Dreaming consolidation
if command -v python3 &>/dev/null; then
    ARKAOS_ROOT="${ARKAOS_ROOT:-$(cat ~/.arkaos/.repo-path 2>/dev/null)}"
    if [ -n "$ARKAOS_ROOT" ] && [ -d "$ARKAOS_ROOT/core/cognition" ]; then
        # Pass the conversation digest to the capture collector
        echo "$input" | python3 -c "
import sys, os
sys.path.insert(0, os.environ.get('ARKAOS_ROOT', ''))
try:
    from core.cognition.capture.collector import collect_from_digest
    digest = sys.stdin.read()
    if digest.strip():
        collect_from_digest(digest, os.path.expanduser('~/.arkaos/captures.db'))
except Exception:
    pass  # Never block the hook
" 2>/dev/null &
    fi
fi
```

- [ ] **Step 3: Implement the collector function**

```python
# core/cognition/capture/collector.py
from __future__ import annotations

import os
import re
from datetime import datetime, timezone

from core.cognition.capture.store import CaptureStore
from core.cognition.memory.schemas import RawCapture


def _detect_project(digest: str) -> tuple[str, str]:
    """Try to detect project name and path from digest content."""
    # Look for common path patterns
    path_match = re.search(r"(/Users/\S+/(?:Herd|Work|AIProjects)/(\S+))", digest)
    if path_match:
        return path_match.group(2).rstrip("/"), path_match.group(1).rstrip("/")
    return "unknown", os.getcwd()


def _categorize_line(line: str) -> str | None:
    """Categorize a digest line. Returns None if not worth capturing."""
    lower = line.lower()
    if any(w in lower for w in ["decided", "chose", "using", "switched to", "went with"]):
        return "decision"
    if any(w in lower for w in ["fixed", "resolved", "solved", "bug", "error", "issue"]):
        return "error"
    if any(w in lower for w in ["created", "implemented", "added", "built", "wrote"]):
        return "solution"
    if any(w in lower for w in ["pattern", "approach", "architecture", "structure"]):
        return "pattern"
    if any(w in lower for w in ["config", "setup", "installed", "configured", "environment"]):
        return "config"
    return None


def collect_from_digest(digest: str, db_path: str) -> int:
    """Parse a session digest and save raw captures. Returns count saved."""
    store = CaptureStore(db_path)
    project_name, project_path = _detect_project(digest)
    session_id = f"session-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"

    count = 0
    for line in digest.split("\n"):
        line = line.strip()
        if len(line) < 20:
            continue
        category = _categorize_line(line)
        if category is None:
            continue

        capture = RawCapture(
            session_id=session_id,
            project_path=project_path,
            project_name=project_name,
            category=category,
            content=line,
            context={"source": "pre-compact-digest"},
        )
        store.save(capture)
        count += 1

    store.close()
    return count
```

- [ ] **Step 4: Run all cognition tests to verify nothing breaks**

Run: `cd /Users/andreagroferreira/AIProjects/arka-os && python -m pytest tests/python/test_cognition_schemas.py tests/python/test_capture_store.py tests/python/test_insight_store.py tests/python/test_dual_writer.py tests/python/test_research_profiler.py tests/python/test_scheduler_daemon.py tests/python/test_scheduler_platform.py -v`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add core/cognition/capture/collector.py config/hooks/pre-compact.sh
git commit -m "feat(cognition): add raw capture collection to PreCompact hook"
```

---

### Task 15: CwdChanged Hook — Insight Presentation

**Files:**
- Modify: `config/hooks/cwd-changed.sh`

- [ ] **Step 1: Read current cwd-changed hook**

Run: `cat ~/.arkaos/config/hooks/cwd-changed.sh` (or the source in repo)

- [ ] **Step 2: Add insight query to cwd-changed hook**

Add a block that queries `~/.arkaos/insights.db` for pending insights when entering a project directory. The hook output is JSON with a `systemMessage` field:

```bash
# === Cognitive Layer: Insight Presentation ===
# Check for pending insights when entering a project
INSIGHTS_MSG=""
if command -v python3 &>/dev/null; then
    ARKAOS_ROOT="${ARKAOS_ROOT:-$(cat ~/.arkaos/.repo-path 2>/dev/null)}"
    if [ -n "$ARKAOS_ROOT" ] && [ -d "$ARKAOS_ROOT/core/cognition" ]; then
        INSIGHTS_MSG=$(python3 -c "
import sys, os, json
sys.path.insert(0, os.environ.get('ARKAOS_ROOT', ''))
try:
    from core.cognition.insights.store import InsightStore
    store = InsightStore(os.path.expanduser('~/.arkaos/insights.db'))
    # Detect project from current directory
    cwd = os.environ.get('CWD', os.getcwd())
    project = os.path.basename(cwd).lower().split('-')[0]
    insights = store.get_pending(project)
    if insights:
        lines = ['Pending reflections from Dreaming:']
        for i, ins in enumerate(insights[:5], 1):
            lines.append(f'{i}. [{ins.category}] {ins.title} — {ins.severity}')
            lines.append(f'   {ins.description[:120]}')
        lines.append('')
        lines.append('Want me to elaborate on any of these?')
        print('\\n'.join(lines))
    store.close()
except Exception:
    pass
" 2>/dev/null)
    fi
fi
```

Then include `$INSIGHTS_MSG` in the hook's JSON output `systemMessage` field.

- [ ] **Step 3: Commit**

```bash
git add config/hooks/cwd-changed.sh
git commit -m "feat(cognition): add insight presentation to CwdChanged hook"
```

---

### Task 16: SessionStart Hook — Overnight Alerts

**Files:**
- Modify: `config/hooks/session-start.sh`

- [ ] **Step 1: Read current session-start hook**

Run: `cat ~/.arkaos/config/hooks/session-start.sh` (or the source in repo)

- [ ] **Step 2: Add overnight insight/research alert summary**

Add a block that checks for pending insights and recent research alerts:

```bash
# === Cognitive Layer: Overnight Alerts ===
COGNITIVE_MSG=""
if command -v python3 &>/dev/null; then
    ARKAOS_ROOT="${ARKAOS_ROOT:-$(cat ~/.arkaos/.repo-path 2>/dev/null)}"
    if [ -n "$ARKAOS_ROOT" ] && [ -d "$ARKAOS_ROOT/core/cognition" ]; then
        COGNITIVE_MSG=$(python3 -c "
import sys, os
sys.path.insert(0, os.environ.get('ARKAOS_ROOT', ''))
try:
    from core.cognition.insights.store import InsightStore
    store = InsightStore(os.path.expanduser('~/.arkaos/insights.db'))
    pending = store.get_all_pending()
    if pending:
        # Group by project
        projects = {}
        for ins in pending:
            projects.setdefault(ins.project, []).append(ins)
        lines = ['Cognitive Layer overnight results:']
        for proj, insights in projects.items():
            urgent = [i for i in insights if i.severity == 'rethink']
            lines.append(f'  {proj}: {len(insights)} insights ({len(urgent)} urgent)')
        print('\\n'.join(lines))
    store.close()
except Exception:
    pass
" 2>/dev/null)
    fi
fi
```

Include `$COGNITIVE_MSG` in the hook's systemMessage output.

- [ ] **Step 3: Commit**

```bash
git add config/hooks/session-start.sh
git commit -m "feat(cognition): add overnight cognitive alerts to SessionStart hook"
```

---

## Phase 7: Installer Integration

### Task 17: Add `schedule` Dependency to pyproject.toml

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Read current pyproject.toml**

Run: `cat /Users/andreagroferreira/AIProjects/arka-os/pyproject.toml`

- [ ] **Step 2: Add `schedule` to dependencies**

Add `schedule` to the `[project.dependencies]` or appropriate section. Also add `pyyaml` if not already present (it should be — verify).

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add schedule dependency for cognitive scheduler"
```

---

### Task 18: Installer — Deploy Cognitive Layer Files

**Files:**
- Modify: `installer/index.js`

- [ ] **Step 1: Read current installer/index.js**

Understand the installation flow, particularly `installHooks()` and `copyConfigFiles()`.

- [ ] **Step 2: Add cognitive layer deployment to installer**

Add a new function `installCognitiveLayer()` that:

1. Creates `~/.arkaos/cognition/prompts/` directory
2. Copies `config/cognition/prompts/dreaming.md` and `research.md` to `~/.arkaos/cognition/prompts/`
3. Copies `config/cognition/schedules.yaml` to `~/.arkaos/schedules.yaml` (if not exists — don't overwrite user edits)
4. Creates `~/.arkaos/logs/dreaming/` and `~/.arkaos/logs/research/` directories

Call this function from the main `install()` flow after `installHooks()`.

- [ ] **Step 3: Add scheduler service installation**

Add a function `installSchedulerService()` that:

1. Creates the scheduler daemon entry script at `~/.arkaos/bin/scheduler-daemon.py`:

```python
#!/usr/bin/env python3
"""ArkaOS Cognitive Scheduler — Daemon entry point."""
import os
import sys
import time
import logging

# Add ArkaOS core to path
repo_path_file = os.path.expanduser("~/.arkaos/.repo-path")
if os.path.exists(repo_path_file):
    repo_path = open(repo_path_file).read().strip()
    sys.path.insert(0, repo_path)

from core.cognition.scheduler.daemon import ArkaScheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.expanduser("~/.arkaos/logs/scheduler.log")),
        logging.StreamHandler(),
    ],
)

def main():
    scheduler = ArkaScheduler(
        config_path=os.path.expanduser("~/.arkaos/schedules.yaml"),
        log_dir=os.path.expanduser("~/.arkaos/logs"),
        lock_path=os.path.expanduser("~/.arkaos/scheduler.lock"),
    )

    if not scheduler.acquire_lock():
        logging.error("Another scheduler instance is already running")
        sys.exit(1)

    logging.info("ArkaOS Scheduler started")

    try:
        while True:
            scheduler.run_once()
            time.sleep(60)  # Check every minute
    except KeyboardInterrupt:
        logging.info("Scheduler stopped by user")
    finally:
        scheduler.release_lock()

if __name__ == "__main__":
    main()
```

2. Detects the platform and installs the appropriate service (via Python call to `platform.py`)

- [ ] **Step 4: Add scheduler subcommand to installer/cli.js**

Add routing for `arkaos scheduler` subcommands (status, start, stop, run, logs) that delegate to `core/cognition/scheduler/cli.py`.

- [ ] **Step 5: Test the installer locally**

Run: `node installer/cli.js --help` (verify scheduler subcommand appears)

- [ ] **Step 6: Commit**

```bash
git add installer/index.js installer/cli.js
git commit -m "feat(cognition): add cognitive layer deployment and scheduler to installer"
```

---

## Phase 8: Integration Test

### Task 19: End-to-End Smoke Test

**Files:**
- Create: `tests/python/test_cognition_integration.py`

- [ ] **Step 1: Write integration test**

```python
# tests/python/test_cognition_integration.py
"""Integration test: capture → store → dual-write → insight → query cycle."""
import pytest
from datetime import date
from pathlib import Path


class TestCognitionIntegration:
    @pytest.fixture
    def env(self, tmp_path):
        """Set up a complete cognitive layer environment."""
        from core.cognition.capture.store import CaptureStore
        from core.cognition.insights.store import InsightStore
        from core.cognition.memory.writer import DualWriter

        return {
            "capture_store": CaptureStore(str(tmp_path / "captures.db")),
            "insight_store": InsightStore(str(tmp_path / "insights.db")),
            "dual_writer": DualWriter(
                obsidian_base=str(tmp_path / "vault" / "Knowledge Base"),
                vector_db_path=str(tmp_path / "knowledge.db"),
            ),
            "tmp_path": tmp_path,
        }

    def test_full_cycle(self, env):
        from core.cognition.memory.schemas import (
            RawCapture,
            KnowledgeEntry,
            ActionableInsight,
        )

        # 1. Simulate raw capture during the day
        capture = RawCapture(
            session_id="sess-integration",
            project_path="/Users/dev/Herd/client_commerce",
            project_name="client_commerce",
            category="decision",
            content="Used Repository pattern for product sync in ClientCommerce",
            context={"stack": "laravel", "files": ["app/Repositories/ProductRepository.php"]},
        )
        env["capture_store"].save(capture)

        # 2. Verify capture stored
        captures = env["capture_store"].get_by_date(date.today())
        assert len(captures) == 1

        # 3. Simulate Dreaming: curate into KnowledgeEntry
        entry = KnowledgeEntry(
            title="Repository Pattern for Laravel Product Sync",
            category="pattern",
            tags=["laravel", "repository", "sync", "products"],
            stacks=["laravel", "php"],
            content="Use Repository pattern to abstract Eloquent queries for product synchronization. Separates business logic from data access. Validated across ClientCommerce and ClientRetail projects.",
            source_project="client_commerce",
            applicable_to="laravel",
        )
        result = env["dual_writer"].write(entry)
        assert result.obsidian_path is not None
        assert result.vector_indexed is True

        # 4. Verify Obsidian file exists
        assert Path(result.obsidian_path).exists()
        content = Path(result.obsidian_path).read_text()
        assert "Repository Pattern" in content

        # 5. Verify Vector search works
        results = env["dual_writer"].search("product sync repository")
        assert len(results) >= 1
        assert "Repository" in results[0]["title"]

        # 6. Simulate Dreaming: generate insight
        insight = ActionableInsight(
            project="client_commerce",
            trigger="dreaming",
            category="technical",
            severity="improve",
            title="Product sync should use batch upsert",
            description="Current sync processes products one by one. Batch upsert would be 10x faster.",
            recommendation="Use Eloquent upsert() with chunks of 100 records",
            context="Observed during ClientCommerce product sync implementation",
        )
        env["insight_store"].save(insight)

        # 7. Verify insight is pending for client_commerce
        pending = env["insight_store"].get_pending("client_commerce")
        assert len(pending) == 1
        assert pending[0].severity == "improve"

        # 8. Mark capture as processed
        env["capture_store"].mark_processed([capture.id])
        assert len(env["capture_store"].get_unprocessed()) == 0

        # Cleanup
        env["capture_store"].close()
        env["insight_store"].close()
        env["dual_writer"].close()
```

- [ ] **Step 2: Run integration test**

Run: `cd /Users/andreagroferreira/AIProjects/arka-os && python -m pytest tests/python/test_cognition_integration.py -v`
Expected: 1 passed

- [ ] **Step 3: Run full test suite**

Run: `cd /Users/andreagroferreira/AIProjects/arka-os && python -m pytest tests/python/test_cognition*.py tests/python/test_dual_writer.py tests/python/test_research_profiler.py tests/python/test_scheduler*.py -v`
Expected: ALL passed

- [ ] **Step 4: Commit**

```bash
git add tests/python/test_cognition_integration.py
git commit -m "test(cognition): add end-to-end integration test for full cognitive cycle"
```

---

## Summary

| Phase | Tasks | Description |
|-------|-------|-------------|
| 1 | 1-3 | Foundation: schemas, capture store, insight store |
| 2 | 4-6 | Dual-write engine: Obsidian writer, vector writer, unified interface |
| 3 | 7 | Research profiler |
| 4 | 8-10 | Scheduler: daemon, platform adapters, CLI |
| 5 | 11-13 | Config: default schedules, Dreaming prompt, Research prompt |
| 6 | 14-16 | Hook integration: PreCompact, CwdChanged, SessionStart |
| 7 | 17-18 | Installer: dependency, deployment, service registration |
| 8 | 19 | Integration test: full cycle smoke test |

**Total: 19 tasks, ~45 files created/modified**

Each phase produces independently testable, working code. Phases can be reviewed and committed separately.
