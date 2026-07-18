"""Evolve engine — ingestion, promotion candidates, propose-only render.

All paths (db, gotchas, output) point at tmp_path; the real
``~/.arkaos`` is never touched. Redaction uses the synthetic-clients
monkeypatch idiom from test_reorganizer.py — the production redaction
list is never loaded.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from core.cognition import evolve, reorganizer
from core.cognition.evolve import (
    build_proposal,
    derive_confidence,
    ingest_gotchas,
)
from core.cognition.evolve_cli import main as evolve_main
from core.cognition.insights.store import InsightStore


@pytest.fixture(autouse=True)
def synthetic_clients(monkeypatch: pytest.MonkeyPatch) -> None:
    patterns = ("acmecorp", "globexsa")
    monkeypatch.setattr(reorganizer, "_CLIENT_PATTERNS", patterns)
    monkeypatch.setattr(
        reorganizer,
        "_REDACT_RE",
        re.compile(
            r"(?<![A-Za-z0-9-])(" + "|".join(patterns) + r")(?![A-Za-z0-9-])",
            re.IGNORECASE,
        ),
    )


def _write_gotchas(path: Path, entries: list[dict]) -> Path:
    # Production shape: a bare JSON list (post_tool_use._store_gotcha).
    path.write_text(json.dumps(entries), encoding="utf-8")
    return path


def _gotcha(pattern: str, *, count: int, projects: list[str]) -> dict:
    return {
        "pattern": pattern,
        "full_pattern": f"{pattern}: full line",
        "category": "runtime-error",
        "tool": "Bash",
        "count": count,
        "projects": projects,
        "suggestion": "Pin the dependency version.",
    }


# ─── confidence derivation ──────────────────────────────────────────────


def test_confidence_floor_at_single_occurrence():
    assert derive_confidence(1) == pytest.approx(0.3)


def test_confidence_caps_at_band_max():
    assert derive_confidence(7) == pytest.approx(0.9)
    assert derive_confidence(50) == pytest.approx(0.9)


def test_confidence_monotonic():
    values = [derive_confidence(n) for n in range(1, 10)]
    assert values == sorted(values)


# ─── ingestion ──────────────────────────────────────────────────────────


def test_ingest_one_row_per_project(tmp_path: Path):
    store = InsightStore(tmp_path / "insights.db")
    gotchas = _write_gotchas(
        tmp_path / "gotchas.json",
        [_gotcha("ModuleNotFoundError: yaml", count=6, projects=["a", "b"])],
    )
    assert ingest_gotchas(store, gotchas) == 2
    pending = store.get_all_pending()
    assert len(pending) == 2
    assert {i.project for i in pending} == {"a", "b"}
    assert all(i.trigger == "evolve-ingest" for i in pending)
    assert all(i.evidence_count == 6 for i in pending)


def test_ingest_is_idempotent(tmp_path: Path):
    store = InsightStore(tmp_path / "insights.db")
    gotchas = _write_gotchas(
        tmp_path / "gotchas.json",
        [_gotcha("exit code 127", count=3, projects=["a"])],
    )
    ingest_gotchas(store, gotchas)
    ingest_gotchas(store, gotchas)
    assert len(store.get_all_pending()) == 1


def test_ingest_skips_blank_pattern_and_projects(tmp_path: Path):
    store = InsightStore(tmp_path / "insights.db")
    gotchas = _write_gotchas(
        tmp_path / "gotchas.json",
        [
            _gotcha("", count=2, projects=["a"]),
            _gotcha("real pattern", count=2, projects=["", "  "]),
        ],
    )
    assert ingest_gotchas(store, gotchas) == 0


def test_ingest_missing_file_is_noop(tmp_path: Path):
    store = InsightStore(tmp_path / "insights.db")
    assert ingest_gotchas(store, tmp_path / "absent.json") == 0


# ─── build_proposal ─────────────────────────────────────────────────────


def test_proposal_lists_cross_project_candidates(tmp_path: Path):
    gotchas = _write_gotchas(
        tmp_path / "gotchas.json",
        [_gotcha("npm ERR! peer dep", count=6, projects=["a", "b"])],
    )
    report = build_proposal(
        db_path=tmp_path / "insights.db",
        gotchas_path=gotchas,
        output_dir=tmp_path / "proposals",
    )
    assert report.ingested == 2
    assert len(report.candidates) == 1
    candidate = report.candidates[0]
    assert candidate.project_count == 2
    assert candidate.mean_confidence == pytest.approx(0.8)
    text = Path(report.proposal_path).read_text(encoding="utf-8")
    assert "npm ERR! peer dep" in text
    assert "Propose-only" in text


def test_single_project_signal_is_not_a_candidate(tmp_path: Path):
    gotchas = _write_gotchas(
        tmp_path / "gotchas.json",
        [_gotcha("solo pattern", count=9, projects=["a"])],
    )
    report = build_proposal(
        db_path=tmp_path / "insights.db",
        gotchas_path=gotchas,
        output_dir=tmp_path / "proposals",
    )
    assert report.candidates == []


def test_proposal_never_renders_project_names(tmp_path: Path):
    gotchas = _write_gotchas(
        tmp_path / "gotchas.json",
        [_gotcha("some pattern", count=6, projects=["secret-proj-x", "b"])],
    )
    report = build_proposal(
        db_path=tmp_path / "insights.db",
        gotchas_path=gotchas,
        output_dir=tmp_path / "proposals",
    )
    text = Path(report.proposal_path).read_text(encoding="utf-8")
    assert "secret-proj-x" not in text


def test_proposal_redacts_client_names(tmp_path: Path):
    gotchas = _write_gotchas(
        tmp_path / "gotchas.json",
        [_gotcha("acmecorp deploy failed", count=6, projects=["a", "b"])],
    )
    report = build_proposal(
        db_path=tmp_path / "insights.db",
        gotchas_path=gotchas,
        output_dir=tmp_path / "proposals",
    )
    text = Path(report.proposal_path).read_text(encoding="utf-8")
    assert "acmecorp" not in text
    assert "<redacted-client>" in text


def test_proposal_escapes_html_in_titles(tmp_path: Path):
    gotchas = _write_gotchas(
        tmp_path / "gotchas.json",
        [_gotcha("<script>alert(1)</script>", count=6, projects=["a", "b"])],
    )
    report = build_proposal(
        db_path=tmp_path / "insights.db",
        gotchas_path=gotchas,
        output_dir=tmp_path / "proposals",
    )
    text = Path(report.proposal_path).read_text(encoding="utf-8")
    assert "<script>" not in text
    assert "&lt;script&gt;" in text


def test_dry_run_writes_nothing(tmp_path: Path, capsys):
    gotchas = _write_gotchas(
        tmp_path / "gotchas.json",
        [_gotcha("dry pattern", count=2, projects=["a"])],
    )
    out_dir = tmp_path / "proposals"
    report = build_proposal(
        db_path=tmp_path / "insights.db",
        gotchas_path=gotchas,
        output_dir=out_dir,
        dry_run=True,
    )
    assert report.proposal_path is None
    assert not out_dir.exists()
    assert "dry pattern" in capsys.readouterr().out


def test_empty_store_renders_honest_empty_state(tmp_path: Path):
    report = build_proposal(
        db_path=tmp_path / "insights.db",
        gotchas_path=tmp_path / "absent.json",
        output_dir=tmp_path / "proposals",
    )
    text = Path(report.proposal_path).read_text(encoding="utf-8")
    assert "Store is empty" in text
    assert "None yet" in text


def test_output_dir_outside_allowlist_raises(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        evolve, "_validate_output_dir", evolve._validate_output_dir
    )
    with pytest.raises(ValueError):
        evolve._validate_output_dir(Path("/etc/evil"))


# ─── CLI ────────────────────────────────────────────────────────────────


def test_cli_dry_run_exit_zero(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setattr(
        evolve, "_DEFAULT_DB_PATH", tmp_path / "insights.db"
    )
    monkeypatch.setattr(
        evolve, "_DEFAULT_GOTCHAS_PATH", tmp_path / "absent.json"
    )
    monkeypatch.setattr(
        "core.cognition.evolve_cli.build_proposal",
        lambda **kw: build_proposal(
            db_path=tmp_path / "insights.db",
            gotchas_path=tmp_path / "absent.json",
            output_dir=tmp_path / "proposals",
            dry_run=kw.get("dry_run", False),
            min_projects=kw.get("min_projects", 2),
            min_confidence=kw.get("min_confidence", 0.8),
        ),
    )
    assert evolve_main(["--dry-run"]) == 0
    assert "Evolve proposal" in capsys.readouterr().out
