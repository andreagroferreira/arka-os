# Self-healing Sync (Sub-feature D) Implementation Plan

**Goal:** Transient sync errors retry with backoff; a consecutive `/arka update` re-run converges; errors are structured (code + context) for debuggability.

**Architecture:** New `core/sync/self_healing.py` module wraps individual phase functions with retry + backoff. Add a `SyncError` Pydantic model with typed codes. Engine uses the wrapper for each per-project phase invocation. Integration test asserts two consecutive runs produce "unchanged" statuses across all phases.

**Tech Stack:** Python 3.11, Pydantic, pytest.

---

## Task 1 — SyncError schema + retry helper tests

**Files:** `core/sync/schema.py`, create `tests/python/test_self_healing.py`

- [ ] **Step 1: Add `SyncError` to schema.py**

Append after existing models:
```python
class SyncError(BaseModel):
    """Structured sync error with grep-able code and context."""

    phase: str
    project_path: str
    code: str
    message: str
    context: dict = Field(default_factory=dict)
    retry_count: int = 0
```

- [ ] **Step 2: Write failing tests** in `tests/python/test_self_healing.py`:

```python
"""Tests for core.sync.self_healing — retry wrapper."""

from __future__ import annotations

import pytest

from core.sync.self_healing import RetryExhausted, run_with_retry


def test_success_on_first_try_returns_result() -> None:
    calls = {"n": 0}

    def fn() -> str:
        calls["n"] += 1
        return "ok"

    result = run_with_retry(fn, max_retries=3)
    assert result == "ok"
    assert calls["n"] == 1


def test_retries_until_success() -> None:
    calls = {"n": 0}

    def fn() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise ValueError("transient")
        return "ok"

    result = run_with_retry(fn, max_retries=3, base_delay=0.0)
    assert result == "ok"
    assert calls["n"] == 3


def test_raises_retry_exhausted_after_max() -> None:
    calls = {"n": 0}

    def fn() -> str:
        calls["n"] += 1
        raise ValueError("always fails")

    with pytest.raises(RetryExhausted) as exc_info:
        run_with_retry(fn, max_retries=2, base_delay=0.0)

    assert calls["n"] == 3  # initial + 2 retries
    assert "always fails" in str(exc_info.value)


def test_zero_retries_means_one_attempt() -> None:
    calls = {"n": 0}

    def fn() -> str:
        calls["n"] += 1
        raise ValueError("boom")

    with pytest.raises(RetryExhausted):
        run_with_retry(fn, max_retries=0, base_delay=0.0)

    assert calls["n"] == 1
```

Run: `cd /Users/andreagroferreira/AIProjects/arka-os && python -m pytest tests/python/test_self_healing.py -v`

Expected: ImportError, all fail.

- [ ] **Step 3: Commit**

```bash
git add core/sync/schema.py tests/python/test_self_healing.py
git commit -m "test(sync): self-healing retry wrapper + SyncError schema"
```

---

## Task 2 — Implement self_healing.py

**Files:** Create `core/sync/self_healing.py`

```python
"""Retry wrapper for sync engine phases.

Wraps phase callables with exponential backoff. Errors are surfaced as
RetryExhausted after max attempts so the orchestrator can convert them
into structured SyncError entries on the report.
"""

from __future__ import annotations

import time
from typing import Callable, TypeVar

T = TypeVar("T")


class RetryExhausted(RuntimeError):
    def __init__(self, message: str, last_exception: BaseException | None = None):
        super().__init__(message)
        self.last_exception = last_exception


def run_with_retry(
    fn: Callable[[], T],
    max_retries: int = 3,
    base_delay: float = 0.1,
    backoff: float = 2.0,
) -> T:
    """Call fn with exponential backoff; raise RetryExhausted after max_retries.

    max_retries=0 means a single attempt (no retries).
    """
    attempt = 0
    last_exc: BaseException | None = None
    while attempt <= max_retries:
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt == max_retries:
                break
            time.sleep(base_delay * (backoff ** attempt))
            attempt += 1

    raise RetryExhausted(
        f"exhausted {max_retries} retries: {last_exc}",
        last_exception=last_exc,
    )
```

Run tests: `python -m pytest tests/python/test_self_healing.py -v` — all 4 PASS.

Full suite: `python -m pytest tests/python/ -q` — 2287 + 4 = 2291 passing.

- [ ] **Commit**

```bash
git add core/sync/self_healing.py
git commit -m "feat(sync): retry wrapper with exponential backoff"
```

---

## Task 3 — Idempotence integration test

**Files:** Modify `tests/python/test_sync_integration.py`

- [ ] **Step 1: Add back-to-back idempotence test**

Add `test_full_sync_idempotent_across_two_runs`:

- Build a single fixture project with `stack=["python"]` using the existing `_build_content_sync_environment` helper (or equivalent).
- Run `run_sync` twice.
- Assert that on the SECOND run:
  - All `content_results[*].status == "unchanged"`
  - All `agent_results[*].status == "unchanged"`
  - All `mcp_results[*].mcps_added` are empty (list)
  - The overall `SyncReport.errors` list is empty.

If the existing fixture layout requires adaptation, do so minimally — don't build new infra.

Run: `python -m pytest tests/python/test_sync_integration.py -v -k idempotent`

PASS.

Full suite: `python -m pytest tests/python/ -q` — 2292 passing.

- [ ] **Commit**

```bash
git add tests/python/test_sync_integration.py
git commit -m "test(sync): full sync idempotence across two consecutive runs"
```

---

## Task 4 — Quality Gate + merge

- [ ] Dispatch Marta for Quality Gate review.
- [ ] On APPROVED, merge to master (no-ff).
- [ ] Do NOT release yet — release task is separate below.

---

## Release v2.17.0 (follows Sub-D merge)

- [ ] **Bump versions:** `VERSION`, `package.json`, `pyproject.toml` → `2.17.0`.
- [ ] **Update CHANGELOG** with a `## [2.17.0]` section documenting: Content Sync (A), MCP Optimizer (B), Agent Provisioning (C), Self-healing (D), plus the v2.17.0 follow-ups noted in prior QGs.
- [ ] **Commit:** `chore: bump to v2.17.0`
- [ ] **Push:** `git push origin master`
- [ ] **GitHub release:** `gh release create v2.17.0 --title "v2.17.0" --notes "..."` with detailed notes.
- [ ] **npm publish:** `npm publish --access public`
- [ ] **Verify:** `npm view arkaos version` = `2.17.0`.
