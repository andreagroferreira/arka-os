"""Collect raw captures from session digests for Dreaming consolidation."""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone

from core.cognition.capture.store import CaptureStore
from core.cognition.memory.schemas import RawCapture


def _detect_project(digest: str) -> tuple[str, str]:
    """Try to detect project name and path from digest content."""
    path_match = re.search(
        r"(/Users/\S+/(?:Herd|Work|AIProjects)/([^\s/]+))", digest
    )
    if path_match:
        return path_match.group(2).rstrip("/"), path_match.group(1).rstrip("/")
    return "unknown", os.getcwd()


def _categorize_line(line: str) -> str | None:
    """Categorize a digest line. Returns None if not worth capturing."""
    lower = line.lower()
    if any(
        w in lower
        for w in ["decided", "chose", "using", "switched to", "went with"]
    ):
        return "decision"
    if any(
        w in lower
        for w in ["fixed", "resolved", "solved", "bug", "error", "issue"]
    ):
        return "error"
    if any(
        w in lower
        for w in ["created", "implemented", "added", "built", "wrote"]
    ):
        return "solution"
    if any(
        w in lower
        for w in ["pattern", "approach", "architecture", "structure"]
    ):
        return "pattern"
    if any(
        w in lower
        for w in ["config", "setup", "installed", "configured", "environment"]
    ):
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
