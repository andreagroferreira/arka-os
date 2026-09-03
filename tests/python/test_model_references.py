"""Guard against stale model references (Runtime Sync 2026-09-03).

The operator's decision: Opus 4.x → Opus 5, Fable 5 → Fable 5.1, and the
weakest lane ArkaOS routes to is Sonnet 5 — never Haiku. Living code, config,
skills and docs must not name the old lanes. History (CHANGELOG, ADRs, dated
plans/specs) and the price table (old rows keep old sessions priced) are the
only places allowed to.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent

STALE = re.compile(
    r"(?<![\w-])opus-4-[5-8]\b|Opus 4\.[5-8]\b"
    r"|(?<![\w-])claude-fable-5(?![-.\w])|Fable 5(?![.\d\w])"
    r"|haiku-4-5|Haiku 4\.5|^model: haiku\b",
    re.M,
)
ALLOWED_FILES = {
    "CHANGELOG.md",
    "core/runtime/pricing.py",          # old rows keep old sessions priced
    "tests/python/test_pricing.py",     # pins those historical rows
    "core/runtime/model_router.py",     # LEGACY_MODEL_IDS map
    "tests/python/test_model_router.py",
    "tests/python/test_model_references.py",
}
ALLOWED_PREFIXES = ("docs/adr/", "docs/superpowers/", "docs/strategy/", "harness/")
TEXT_SUFFIXES = {".py", ".md", ".yaml", ".yml", ".json", ".js", ".cjs", ".mjs",
                 ".sh", ".bats", ".vue", ".ts", ".toml", ".txt"}


def _tracked_text_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    return [
        f for f in out
        if Path(f).suffix in TEXT_SUFFIXES
        and f not in ALLOWED_FILES
        and not f.startswith(ALLOWED_PREFIXES)
    ]


def test_no_stale_model_references_outside_history():
    hits: list[str] = []
    for rel in _tracked_text_files():
        try:
            text = (REPO / rel).read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for m in STALE.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            hits.append(f"{rel}:{line}: {m.group(0)}")
    assert not hits, "stale model references (Opus 4.x / Fable 5 / Haiku):\n" + "\n".join(hits[:40])
