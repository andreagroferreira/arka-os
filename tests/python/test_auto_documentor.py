"""Tests for core.cognition.auto_documentor.

Covers extraction heuristics, LLM-agnostic synthesis (delegating to
`core.runtime.llm_provider.get_llm_provider`), template fallback, and
the full `document_session` pipeline that integrates with the Obsidian
cataloger + relator (Task #4).

Task #13 removed the `choose_model` / `model_hint` machinery. The
module now knows NOTHING about which model runs — those tests are gone
and replaced with LLMProvider-delegation tests plus a static source
guard that locks in the invariant.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from core.cognition import auto_documentor as ad
from core.cognition.auto_documentor import (
    Learning,
    document_session,
    extract_learnings,
    synthesize,
)
from core.runtime.llm_provider import LLMResponse, LLMUnavailable


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


# ─── Stub provider for LLM-delegation tests ────────────────────────────


class _StubLLM:
    def __init__(
        self,
        *,
        text: str = "",
        available: bool = True,
        raise_on_complete: Exception | None = None,
    ) -> None:
        self._text = text
        self._available = available
        self._raise = raise_on_complete
        self.calls: list[dict] = []

    def name(self) -> str:
        return "stub-test"

    def is_available(self) -> bool:
        return self._available

    def complete(self, prompt: str, *, max_tokens: int = 2000, system: str = "") -> LLMResponse:
        self.calls.append(
            {"prompt": prompt, "max_tokens": max_tokens, "system": system}
        )
        if self._raise is not None:
            raise self._raise
        return LLMResponse(
            text=self._text,
            tokens_in=10,
            tokens_out=20,
            cached_tokens=0,
            model="",
        )


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


# ─── _call_llm (LLMProvider delegation) ────────────────────────────────


def test_call_llm_delegates_to_provider(monkeypatch):
    stub = _StubLLM(text="  Real LLM output  ")
    monkeypatch.setattr(ad, "get_llm_provider", lambda: stub, raising=False)
    # Import-level reference used inside _call_llm goes through core.runtime.
    from core import runtime as rt
    monkeypatch.setattr(rt, "get_llm_provider", lambda: stub)

    lg = Learning(topic="t", content="body", sources=["https://example.com"])
    assert ad._call_llm(lg) == "Real LLM output"
    assert len(stub.calls) == 1
    assert stub.calls[0]["max_tokens"] == ad._LLM_MAX_TOKENS
    assert "auto-documentor" in stub.calls[0]["system"].lower()
    assert "https://example.com" in stub.calls[0]["prompt"]


def test_call_llm_returns_empty_on_provider_unavailable(monkeypatch):
    stub = _StubLLM(text="should not be used", available=False)
    from core import runtime as rt
    monkeypatch.setattr(rt, "get_llm_provider", lambda: stub)

    assert ad._call_llm(Learning(topic="t", content="x")) == ""
    assert stub.calls == []  # complete() never invoked


def test_call_llm_returns_empty_on_llm_unavailable_exception(monkeypatch):
    stub = _StubLLM(raise_on_complete=LLMUnavailable("cli down"))
    from core import runtime as rt
    monkeypatch.setattr(rt, "get_llm_provider", lambda: stub)

    assert ad._call_llm(Learning(topic="t", content="x")) == ""


def test_call_llm_returns_empty_on_unexpected_exception(monkeypatch):
    stub = _StubLLM(raise_on_complete=RuntimeError("boom"))
    from core import runtime as rt
    monkeypatch.setattr(rt, "get_llm_provider", lambda: stub)

    # Must not propagate — doc job must survive any LLM failure.
    assert ad._call_llm(Learning(topic="t", content="x")) == ""


def test_call_llm_returns_empty_when_factory_raises(monkeypatch):
    def boom():
        raise RuntimeError("factory down")

    from core import runtime as rt
    monkeypatch.setattr(rt, "get_llm_provider", boom)

    assert ad._call_llm(Learning(topic="t", content="x")) == ""


# ─── _build_synthesis_prompt ───────────────────────────────────────────


def test_build_synthesis_prompt_deterministic():
    lg = Learning(
        topic="My Topic",
        content="The body.",
        sources=["https://a.example", "https://b.example"],
        decisions=["chose X", "selected Y"],
        metadata={"dept": "dev", "stack": "Laravel"},
    )
    first = ad._build_synthesis_prompt(lg)
    second = ad._build_synthesis_prompt(lg)
    assert first == second
    assert "My Topic" in first
    assert "https://a.example" in first
    assert "chose X" in first
    assert "dept: dev" in first


def test_build_synthesis_prompt_handles_empty_fields():
    lg = Learning(topic="Bare", content="")
    prompt = ad._build_synthesis_prompt(lg)
    assert "Bare" in prompt
    # Must not crash, must still ask for output.
    assert "Output only markdown" in prompt


# ─── synthesize ────────────────────────────────────────────────────────


def test_synthesize_template_fallback_when_no_llm(monkeypatch):
    # Force empty LLM → template path.
    monkeypatch.setattr(ad, "_call_llm", lambda learning: "")
    lg = Learning(
        topic="My Topic",
        content="## Request\n\nBuild X",
        sources=["https://example.com"],
        decisions=["chose pattern Y"],
    )
    out = synthesize(lg)
    assert "# My Topic" in out
    assert ad._AUTO_DOC_SUFFIX in out
    assert "https://example.com" in out
    assert "chose pattern Y" in out


def test_synthesize_uses_llm_when_available(monkeypatch):
    monkeypatch.setattr(ad, "_call_llm", lambda learning: "Real LLM output")
    lg = Learning(topic="t", content="body")
    assert synthesize(lg) == "Real LLM output"


def test_synthesize_falls_back_to_template_when_llm_empty(monkeypatch):
    monkeypatch.setattr(ad, "_call_llm", lambda learning: "")
    lg = Learning(topic="Fallback", content="body", decisions=["d1"])
    out = synthesize(lg)
    assert out.startswith("# Fallback")
    assert "d1" in out


# ─── document_session ──────────────────────────────────────────────────


def test_document_session_skips_if_qg_not_approved(simple_transcript, vault):
    written = document_session(simple_transcript, "sess-1", vault, "REJECTED")
    assert written == []


def test_document_session_end_to_end_uses_cataloger_and_relator(
    simple_transcript, vault, monkeypatch
):
    # Force template path so the note content is deterministic.
    monkeypatch.setattr(ad, "_call_llm", lambda learning: "")
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


def test_document_session_tags_by_detected_domain(
    simple_transcript, vault, monkeypatch
):
    monkeypatch.setattr(ad, "_call_llm", lambda learning: "")
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
    monkeypatch.setattr(ad, "_call_llm", lambda learning: "")

    def boom(*_args, **_kwargs):
        raise RuntimeError("relator down")

    monkeypatch.setattr(ad._relator, "find_related", boom)
    # Pipeline must still return the written note even if relator fails.
    written = document_session(simple_transcript, "sess-6", vault, "APPROVED")
    assert len(written) == 1
    assert written[0].exists()


def test_document_session_appends_related_block_when_matches(
    tmp_path, vault, monkeypatch
):
    monkeypatch.setattr(ad, "_call_llm", lambda learning: "")
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


# ─── Invariant: no model-name leakage ─────────────────────────────────


def test_document_one_writes_auto_documented_suffix_no_model(
    simple_transcript, vault, monkeypatch
):
    monkeypatch.setattr(ad, "_call_llm", lambda learning: "")
    written = document_session(simple_transcript, "sess-nm", vault, "APPROVED")
    assert written
    body = written[0].read_text(encoding="utf-8")
    assert ad._AUTO_DOC_SUFFIX in body
    lower = body.lower()
    for forbidden in ("opus", "sonnet", "haiku", "gpt-4", "gemini"):
        # Frontmatter may contain 'model' key but never a hardcoded id.
        assert forbidden not in lower, f"Model name leaked into note: {forbidden}"


def test_no_model_names_in_auto_documentor_source():
    """Static guard: the module source must stay model-agnostic forever.

    If this fails, someone hardcoded a model name (haiku/sonnet/opus/
    gpt-4/gemini) into auto_documentor.py. Route model selection through
    the LLMProvider / runtime env instead.
    """
    source_path = Path(ad.__file__)
    source = source_path.read_text(encoding="utf-8")
    forbidden = re.compile(r"\b(opus|sonnet|haiku|gpt-4|gemini)\b", re.IGNORECASE)
    hits = forbidden.findall(source)
    assert hits == [], (
        f"auto_documentor.py contains forbidden model name(s): {hits!r}. "
        "Model selection must stay in LLMProvider / runtime env."
    )
