"""docs/WORKFLOWS-CATALOG.md is generated, never hand-edited.

The complete workflow surface (48 workflow YAMLs across 16 departments)
is compiled by ``scripts/workflows_catalog_gen.py``. This lock keeps the
committed file byte-identical to a fresh run, so the catalog can never
drift from the workflow YAML files it documents.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from workflows_catalog_gen import generate  # noqa: E402

CATALOG = REPO_ROOT / "docs" / "WORKFLOWS-CATALOG.md"


def test_committed_catalog_matches_fresh_regen():
    fresh = generate()
    committed = CATALOG.read_text(encoding="utf-8")
    assert fresh == committed, (
        "docs/WORKFLOWS-CATALOG.md drifted — regenerate with "
        "python scripts/workflows_catalog_gen.py"
    )


def test_catalog_counts_all_workflow_yamls():
    yamls = list((REPO_ROOT / "departments").rglob("workflows/*.yaml"))
    fresh = generate()
    total_line = [l for l in fresh.splitlines() if l.startswith("**48 workflows**")]
    assert total_line, "catalog must open with the 48-workflow headline"
    assert len(yamls) == 48, "workflow YAML count must match the catalog"
