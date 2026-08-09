"""Suite-wide guard: no test may write to real state (issue #497/#510).

The constitution's destructive-tests rule says cross-cutting tests stub
destructive primitives via monkeypatch/tmp_path. Two tests did not, and
nothing noticed for months because the bytes they wrote back were
identical: ``pytest tests/python/`` rewrote all 85 generated
``config/claude-agents/*.md`` and ``departments/brand/workflows/audit.yaml``
on every run, so ``git status`` stayed clean while the inode churn masked
real changes — one behavioural drift away from silently dirtying commits.
A third read the operator's REAL ``~/.arkaos/projects`` and handed all 20
registered project directories to five sync writers.

This module holds ONLY the fixture. Every helper lives in
``_real_state_guard.py``, because pytest imports conftests under the bare
name ``conftest`` and the sibling ``diagram/`` and ``watch/`` conftests
claim that name first — a test importing helpers from ``conftest`` aborts
collection.
"""

from __future__ import annotations

import os

import pytest
from _real_state_guard import (
    BYPASS_ENV,
    collect_violations,
    fingerprints,
    format_failure,
)


@pytest.fixture(scope="session", autouse=True)
def real_state_write_guard():
    """Fail the session when a test wrote to a guarded real-state file."""
    if os.environ.get(BYPASS_ENV):
        yield
        return

    before = fingerprints()
    yield
    report = format_failure(collect_violations(before, fingerprints()))
    if report:
        pytest.fail(report, pytrace=False)
