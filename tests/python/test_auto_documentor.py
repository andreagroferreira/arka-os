"""Tests for core.cognition.auto_documentor — Task #7 (intelligence-v2).

Covers extraction heuristics, dynamic model routing, template synthesis,
and the full `document_session` pipeline that integrates with the Task #4
Obsidian cataloger + relator.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.cognition import auto_documentor as ad
from core.cognition.auto_documentor import (
    Learning,
    choose_model,
    document_session,
    extract_learnings,
    synthesize,
)


# ─── Transcript builder helpers ────────────────────────────────────────


def _msg_user(text: str) -> dict:
    return {"role": "user", "content": [{"type": "text", "text": text}]}


def _msg_assistant(text: str, tool_uses: list[dict] | None = None) -> dict:
    content: list[dict] = [{"type": "text", "text": text}]
    for tu in tool_uses or []:
        content.append({"type": "tool_use", **tu})
    return {"role": "assistant", "content": content}


def _write_transcript(path: Path, records: list[dict]) -> Path:
    path.write_text(
        "\n".join(json.dumps(r) for r in records), encoding="utf-8"
    )
    return path


@pytest.fixture
def simple_transcript(tmp_path) -> Path:
    return _write_transcript(tmp_path / "t.jsonl", [
        _msg_user("Implement an OrderService in Laravel with repository pattern."),
        _msg_assistant(
            "[arka:routing] dev -> paulo\n\n"
            "I'll decide to use a Service + Repository pattern.",
            tool_uses=[{
                "name": "WebFetch",
                "input": {"url": "https://laravel.com/docs/11.x/eloquent"},
            }],
        ),
        _msg_assistant("Done. Wrote OrderService.php.", tool_uses=[{
            "name": "Write",
            "input": {"file_path": "/repo/app/Services/OrderService.php"},
        }]),
    ])


@pytest.fixture
def vault(tmp_path) -> Path:
    root = tmp_path / "vault"
    root.mkdir()
    # Pre-create the MOC so relator.update_mocs has a target.
    (root / "Topics MOC.md").write_text("# Topics MOC\n", encoding="utf-8")
    (root / "WizardingCode MOC.md").write_text("# WC MOC\n", encoding="utf-8")
    return root


# ─── extract_learnings ─────────────────────────────────────────────────


def test_extract_learnings_from_transcript(simple_transcript):
    learnings = extract_learnings(simple_transcript)
    assert len(learnings) == 1
    lg = learnings[0]
    assert "OrderService" in lg.topic or "Laravel" in lg.topic
    assert lg.content  # non-empty synthesis blob


def test_extract_identifies_sources_from_tool_uses(simple_transcript):
    lg = extract_learnings(simple_transcript)[0]
    assert any("laravel.com" in s for s in lg.sources)


def test_extract_identifies_decisions_from_routing_markers(simple_transcript):
    lg = extract_learnings(simple_transcript)[0]
    assert any("routed: dev -> paulo" in d.lower() for d in lg.decisions)


def test_extract_from_missing_file_is_empty(tmp_path):
    result = extract_learnings(tmp_path / "nope.jsonl")
    assert result == []


def test_extract_from_malformed_json_skips_bad_lines(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_text(
        "not-json\n"
        + json.dumps(_msg_user("hello")) + "\n"
        + "{truncated\n"
        + json.dumps(_msg_assistant("[arka:routing] dev -> paulo\ndecided to ship")) + "\n",
        encoding="utf-8",
    )
    learnings = extract_learnings(path)
    assert len(learnings) == 1
    assert any("dev -> paulo" in d for d in learnings[0].decisions)


def test_extract_unicode_content(tmp_path):
    path = _write_transcript(tmp_path / "u.jsonl", [
        _msg_user("Implementar página em português — acentuação e emojis 🧠"),
        _msg_assistant("[arka:routing] dev -> paulo"),
    ])
    lg = extract_learnings(path)[0]
    assert "🧠" in lg.content or "português" in lg.content.lower()


def test_extract_empty_transcript_returns_empty(tmp_path):
    path = tmp_path / "empty.jsonl"
    path.write_text("", encoding="utf-8")
    assert extract_learnings(path) == []


def test_extract_detects_stack_metadata(simple_transcript):
    lg = extract_learnings(simple_transcript)[0]
    assert lg.metadata.get("stack") == "Laravel"
    assert lg.metadata.get("dept") == "dev"


# ─── choose_model ──────────────────────────────────────────────────────


def test_choose_model_haiku_for_short_summary():
    lg = Learning(topic="t", content="Small note about indent width.")
    assert choose_model(lg) == "haiku"


def test_choose_model_sonnet_for_analysis():
    lg = Learning(
        topic="Benchmark",
        content=("analysis of redis vs memcached " * 40),
        decisions=["chose redis"],
    )
    assert choose_model(lg) == "sonnet"


def test_choose_model_opus_for_architectural():
    lg = Learning(
        topic="ADR",
        content="This is an architecture decision with trade-offs and migration plan. " * 20,
        decisions=["selected hexagonal", "decided to split repo", "chose pg"],
    )
    assert choose_model(lg) == "opus"


def test_choose_model_opus_on_length_plus_decisions():
    lg = Learning(
        topic="t",
        content="x" * 5000,
        decisions=["d1", "d2", "d3", "d4"],
    )
    assert choose_model(lg) == "opus"


# ─── synthesize ─────────────────────────────────────────────────────────


def test_synthesize_template_fallback_no_llm():
    lg = Learning(
        topic="My Topic",
        content="## Request\n\nBuild X",
        sources=["https://example.com"],
        decisions=["chose pattern Y"],
    )
    out = synthesize(lg, "haiku")
    assert "# My Topic" in out
    assert "haiku" in out
    assert "https://example.com" in out
    assert "chose pattern Y" in out


def test_synthesize_honors_llm_hook(monkeypatch):
    lg = Learning(topic="t", content="body")
    monkeypatch.setattr(
        ad, "_call_llm", lambda learning, hint: "LLM OUTPUT"
    )
    assert synthesize(lg, "sonnet") == "LLM OUTPUT"


# ─── document_session ──────────────────────────────────────────────────


def test_document_session_skips_if_qg_not_approved(simple_transcript, vault):
    written = document_session(simple_transcript, "sess-1", vault, "REJECTED")
    assert written == []


def test_document_session_end_to_end_uses_cataloger_and_relator(
    simple_transcript, vault
):
    written = document_session(simple_transcript, "sess-1", vault, "APPROVED")
    assert len(written) == 1
    note = written[0]
    assert note.exists()
    # Cataloger routed to either a Laravel patterns or Sessions folder.
    text = note.read_text(encoding="utf-8")
    assert "Laravel" in str(note) or "Sessions" in str(note)
    # Frontmatter from cataloger writer.
    assert text.startswith("---")
    assert "arkaos" in text


def test_document_session_tags_by_detected_domain(simple_transcript, vault):
    written = document_session(simple_transcript, "sess-2", vault, "APPROVED")
    note = written[0]
    text = note.read_text(encoding="utf-8")
    # Either dept/dev tag or stack tag must have been propagated.
    assert "dept/dev" in text or "stack/laravel" in text


def test_document_session_empty_transcript_graceful(tmp_path, vault):
    empty = tmp_path / "empty.jsonl"
    empty.write_text("", encoding="utf-8")
    assert document_session(empty, "sess-3", vault, "APPROVED") == []


def test_document_session_uses_safe_session_id(simple_transcript, vault):
    assert document_session(simple_transcript, "../evil", vault, "APPROVED") == []
    assert document_session(simple_transcript, "", vault, "APPROVED") == []


def test_document_session_missing_transcript_graceful(tmp_path, vault):
    assert document_session(
        tmp_path / "missing.jsonl", "sess-4", vault, "APPROVED"
    ) == []


def test_document_session_cataloger_missing_vars_skipped(tmp_path, vault, monkeypatch):
    # Force cataloger.plan to raise ValueError (missing required vars).
    transcript = _write_transcript(tmp_path / "t.jsonl", [
        _msg_user("just a thing"),
        _msg_assistant("[arka:routing] dev -> paulo\nchose X"),
    ])

    def boom(*_args, **_kwargs):
        raise ValueError("missing required vars")

    monkeypatch.setattr(ad._cataloger, "plan", boom)
    assert document_session(transcript, "sess-5", vault, "APPROVED") == []


def test_document_session_relator_failure_does_not_crash(
    simple_transcript, vault, monkeypatch
):
    def boom(*_args, **_kwargs):
        raise RuntimeError("relator down")

    monkeypatch.setattr(ad._relator, "find_related", boom)
    # Pipeline must still return the written note even if relator fails.
    written = document_session(simple_transcript, "sess-6", vault, "APPROVED")
    assert len(written) == 1
    assert written[0].exists()


def test_document_session_appends_related_block_when_matches(
    tmp_path, vault
):
    # Seed vault with a very similar note so relator returns matches.
    seed = vault / "existing.md"
    seed.write_text(
        "# Existing\n\nOrderService Laravel repository pattern details.\n",
        encoding="utf-8",
    )
    transcript = _write_transcript(tmp_path / "t.jsonl", [
        _msg_user("Laravel OrderService repository pattern refactor"),
        _msg_assistant(
            "[arka:routing] dev -> paulo\n"
            "```php\nclass OrderService {}\n```\n"
            "Decided to keep repository pattern.",
            tool_uses=[{
                "name": "Write",
                "input": {"file_path": "/repo/OrderService.php"},
            }],
        ),
    ])
    written = document_session(transcript, "sess-r", vault, "APPROVED")
    assert written
    body = written[0].read_text(encoding="utf-8")
    # Relator should have either added Related heading or a backlink.
    assert "## Related" in body or "[[" in body
