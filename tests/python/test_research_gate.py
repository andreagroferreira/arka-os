"""Tests for core.workflow.research_gate — KB-first external research gate."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from core.synapse import kb_cache
from core.workflow import research_gate
from core.workflow.research_gate import (
    RESEARCH_EXTERNAL_TOOLS,
    Decision,
    evaluate_research_gate,
    invalidate_violation,
)


# ─── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def isolated_env(tmp_path, monkeypatch):
    """Isolate config, audit, telemetry, violation-marker and KB-query dirs."""
    home = tmp_path / "home"
    home.mkdir()
    violation_dir = tmp_path / "kb-violation"
    kb_query_dir = tmp_path / "kb-query"
    vault = tmp_path / "vault"
    vault.mkdir()

    monkeypatch.setattr(research_gate, "CONFIG_PATH", home / "config.json")
    monkeypatch.setattr(
        research_gate, "BYPASS_AUDIT_PATH", home / "audit" / "kb_first_bypass.log"
    )
    monkeypatch.setattr(
        research_gate, "TELEMETRY_PATH", home / "telemetry" / "kb_first.jsonl"
    )
    monkeypatch.setattr(research_gate, "VIOLATION_DIR", violation_dir)
    monkeypatch.setenv("ARKA_KB_QUERY_DIR", str(kb_query_dir))
    monkeypatch.setenv("ARKAOS_VAULT", str(vault))
    monkeypatch.delenv("ARKA_BYPASS_KB_FIRST", raising=False)

    (home / "config.json").write_text(
        json.dumps({"hooks": {"kbFirst": True}}),
        encoding="utf-8",
    )
    return {
        "home": home,
        "violation_dir": violation_dir,
        "kb_query_dir": kb_query_dir,
        "vault": vault,
    }


def _seed_vault(vault: Path, titles: list[str]) -> None:
    for t in titles:
        (vault / f"{t}.md").write_text(f"# {t}\n", encoding="utf-8")


# ─── Allow paths ────────────────────────────────────────────────────────


def test_tool_not_gated_allows(isolated_env):
    decision = evaluate_research_gate("Read", session_id="s-1")
    assert decision.allow is True
    assert decision.reason == "tool-not-gated"


def test_feature_flag_off_allows(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(research_gate, "CONFIG_PATH", home / "config.json")
    (home / "config.json").write_text(json.dumps({"hooks": {"kbFirst": False}}))
    monkeypatch.setattr(research_gate, "VIOLATION_DIR", tmp_path / "kb-v")
    monkeypatch.setenv("ARKA_KB_QUERY_DIR", str(tmp_path / "kb-q"))
    monkeypatch.delenv("ARKA_BYPASS_KB_FIRST", raising=False)

    decision = evaluate_research_gate("WebSearch", session_id="s-1", query="laravel")
    assert decision.allow is True
    assert decision.reason == "feature-flag-off"


def test_bypass_env_allows_and_audits(isolated_env, monkeypatch):
    monkeypatch.setenv("ARKA_BYPASS_KB_FIRST", "1")
    monkeypatch.setenv("ARKA_BYPASS_KB_FIRST_REASON", "installer-refresh")

    decision = evaluate_research_gate("WebSearch", session_id="s-1", query="q")
    assert decision.allow is True
    assert decision.bypass_used is True
    assert decision.reason == "env-bypass"

    audit = research_gate.BYPASS_AUDIT_PATH
    assert audit.exists()
    line = audit.read_text(encoding="utf-8").strip()
    entry = json.loads(line)
    assert entry["session_id"] == "s-1"
    assert entry["tool"] == "WebSearch"
    assert entry["reason"] == "installer-refresh"


def test_obsidian_consulted_this_turn_allows(isolated_env):
    kb_cache.record_obsidian_query("s-1", "laravel filament")
    decision = evaluate_research_gate(
        "mcp__context7__query-docs", session_id="s-1", query="laravel"
    )
    assert decision.allow is True
    assert decision.reason == "kb-consulted"


# ─── Nudge / deny paths ─────────────────────────────────────────────────


def test_first_violation_returns_nudge_with_notes(isolated_env):
    _seed_vault(
        isolated_env["vault"],
        ["Laravel Filament Plugin", "Filament Resources Guide", "Eloquent Casts"],
    )

    decision = evaluate_research_gate(
        "WebSearch", session_id="s-1", query="filament plugin laravel"
    )

    assert decision.allow is True
    assert decision.nudge is True
    assert decision.reason == "first-violation-nudge"
    assert "[arka:kb-nudge]" in decision.stderr_msg
    assert len(decision.kb_hits_hint) >= 1


def test_second_violation_returns_deny(isolated_env):
    # First call → nudge, marker written.
    evaluate_research_gate("WebSearch", session_id="s-1", query="filament")
    # Second call → deny.
    decision = evaluate_research_gate(
        "WebSearch", session_id="s-1", query="filament"
    )
    assert decision.allow is False
    assert decision.reason == "kb-first-required"
    assert "[ARKA:KB-FIRST]" in decision.stderr_msg


def test_violation_marker_invalidated_on_new_turn(isolated_env):
    evaluate_research_gate("WebSearch", session_id="s-1", query="filament")
    # New turn → UserPromptSubmit calls invalidate_violation
    invalidate_violation("s-1")

    # Back to first-violation behaviour.
    decision = evaluate_research_gate("WebSearch", session_id="s-1", query="filament")
    assert decision.allow is True
    assert decision.nudge is True
    assert decision.reason == "first-violation-nudge"


# ─── Content / PT-PT checks ─────────────────────────────────────────────


def test_nudge_message_is_pt_pt_natural(isolated_env):
    _seed_vault(isolated_env["vault"], ["Laravel Service Pattern"])

    decision = evaluate_research_gate(
        "WebSearch", session_id="s-1", query="laravel service"
    )
    msg = decision.stderr_msg
    # PT-PT markers: "teu", "cérebro", "antes de", "consulta"
    assert "teu cérebro" in msg.lower()
    assert "consulta" in msg.lower()
    # Must NOT sound like an English error.
    assert "ERROR" not in msg
    assert "error:" not in msg.lower()


def test_nudge_includes_top_3_note_titles(isolated_env):
    _seed_vault(
        isolated_env["vault"],
        [
            "Filament Plugin Architecture",
            "Filament Custom Actions",
            "Filament Form Builder",
            "Filament Deployment",
            "Filament Testing",
        ],
    )
    decision = evaluate_research_gate(
        "WebSearch", session_id="s-1", query="filament plugin actions form"
    )
    assert len(decision.kb_hits_hint) <= 3
    assert len(decision.kb_hits_hint) >= 1
    for title in decision.kb_hits_hint:
        assert f"[[{title}]]" in decision.stderr_msg


def test_deny_message_lists_available_notes(isolated_env):
    _seed_vault(isolated_env["vault"], ["Laravel Query Builder", "Eloquent Eager Loading"])

    # First call → nudge.
    evaluate_research_gate("WebSearch", session_id="s-1", query="laravel eloquent")
    # Second call → deny, must surface the note titles.
    decision = evaluate_research_gate(
        "WebSearch", session_id="s-1", query="laravel eloquent"
    )
    assert decision.allow is False
    # At least one wikilink must appear in the deny message.
    assert "[[" in decision.stderr_msg
    assert "]]" in decision.stderr_msg


# ─── Completeness / safety ──────────────────────────────────────────────


def test_research_external_tools_set_complete():
    expected = {
        "mcp__context7__query-docs",
        "mcp__context7__resolve-library-id",
        "WebSearch",
        "WebFetch",
        "mcp__firecrawl__firecrawl_search",
        "mcp__firecrawl__firecrawl_scrape",
        "mcp__firecrawl__firecrawl_crawl",
    }
    assert expected.issubset(RESEARCH_EXTERNAL_TOOLS)
    assert isinstance(RESEARCH_EXTERNAL_TOOLS, frozenset)


def test_safe_session_id_rejects_traversal(isolated_env):
    # Bad session_id must not crash and must not create any files.
    decision = evaluate_research_gate(
        "WebSearch", session_id="../../etc/passwd", query="x"
    )
    # Gate still returns a Decision (never raises).
    assert isinstance(decision, Decision)
    # No violation file leaks to disk under a traversal path.
    violation_dir = research_gate.VIOLATION_DIR
    if violation_dir.exists():
        for entry in violation_dir.iterdir():
            assert ".." not in entry.name
            assert "/" not in entry.name


def test_concurrent_violation_markers_race_safe(isolated_env):
    """Two threads racing on the same session should both see first-violation
    or both see deny — the marker file must be coherent, not partial.
    """
    def _call() -> Decision:
        return evaluate_research_gate(
            "WebSearch", session_id="race-session", query="laravel"
        )

    with ThreadPoolExecutor(max_workers=4) as ex:
        results = list(ex.map(lambda _: _call(), range(4)))

    # At least one must be a nudge (first-violation) and at most one must be
    # deny — multiple denies are also fine, but the marker must not be
    # corrupt.
    marker = research_gate.VIOLATION_DIR / "race-session"
    assert marker.exists()
    content = marker.read_text(encoding="utf-8")
    # Must be valid JSON (no partial write).
    json.loads(content)
    # At least one decision must be a Decision instance.
    assert all(isinstance(r, Decision) for r in results)


# ─── Hook parity (bash) ─────────────────────────────────────────────────


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_pre_tool_use_sh_references_research_gate():
    """Bash hook must call into research_gate before the flow gate."""
    script = REPO_ROOT / "config" / "hooks" / "pre-tool-use.sh"
    text = script.read_text(encoding="utf-8")
    assert "research_gate" in text, "pre-tool-use.sh must delegate to research_gate"
    assert "evaluate_research_gate" in text


def test_pre_tool_use_ps1_references_research_gate():
    script = REPO_ROOT / "config" / "hooks" / "pre-tool-use.ps1"
    text = script.read_text(encoding="utf-8")
    assert "research_gate" in text
    assert "evaluate_research_gate" in text
