"""Guard for issue #228: file I/O in core/sync MUST declare encoding.

Windows defaults Path.read_text/write_text to the locale codec (cp1252),
which corrupts every non-ASCII character the sync engine round-trips
(SKILL.md content, YAML descriptors, pt-PT copy). AST-based on purpose —
a line-oriented grep misses multiline calls in both directions.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SYNC_DIR = Path(__file__).resolve().parents[2] / "core" / "sync"
SYNC_FILES = sorted(SYNC_DIR.rglob("*.py"))


def _is_binary_mode(node: ast.Call) -> bool:
    mode = None
    if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
        mode = node.args[1].value
    for kw in node.keywords:
        if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
            mode = kw.value.value
    return isinstance(mode, str) and "b" in mode


def _offending_calls(source: str) -> list[tuple[int, str]]:
    tree = ast.parse(source)
    offenders: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else (
            func.id if isinstance(func, ast.Name) else ""
        )
        if name not in ("read_text", "write_text", "open"):
            continue
        if any(kw.arg == "encoding" for kw in node.keywords):
            continue
        # read_text("utf-8") positional also counts as declared.
        if name == "read_text" and len(node.args) >= 1:
            continue
        if name == "write_text" and len(node.args) >= 2:
            continue
        # Binary opens carry no text encoding by definition.
        if name == "open" and _is_binary_mode(node):
            continue
        offenders.append((node.lineno, name))
    return offenders


@pytest.mark.parametrize("path", SYNC_FILES, ids=lambda p: p.name)
def test_sync_file_io_declares_encoding(path: Path) -> None:
    offenders = _offending_calls(path.read_text(encoding="utf-8"))
    assert not offenders, (
        f"{path.relative_to(SYNC_DIR.parent.parent)} has read_text/write_text "
        f"without encoding= (cp1252 corruption on Windows): {offenders}"
    )


def test_guard_actually_sees_sync_files() -> None:
    assert len(SYNC_FILES) >= 10, "core/sync moved? guard is scanning nothing"
