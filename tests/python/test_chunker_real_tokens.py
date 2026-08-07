"""The chunker's token budget must be measured in REAL tokens.

The previous implementation counted whitespace words and called them
tokens; with a measured token/word factor of 1.87 (median) the default
512 budget produced chunks the embedding models silently truncated —
38% of a live corpus lost at embed time with no error.

These tests drive the chunker with a deterministic fake counter (every
word = 2 tokens) so the invariant is asserted without downloading a
model; one guarded test exercises the real fastembed tokenizer when the
environment has it.
"""

from __future__ import annotations

import pytest

from core.knowledge import chunker


@pytest.fixture
def two_tokens_per_word(monkeypatch):
    """Deterministic stand-in for a real tokenizer: 2 tokens per word."""
    monkeypatch.setattr(chunker, "_TOKEN_COUNTER", lambda t: 2 * len(t.split()))
    monkeypatch.setattr(chunker, "_TOKEN_COUNTER_FAILED", False)
    return lambda t: 2 * len(t.split())


class TestRealTokenBudget:
    def test_no_chunk_exceeds_budget_in_real_tokens(self, two_tokens_per_word):
        # 300 words per paragraph = 600 real tokens: under word counting
        # each paragraph "fit" a 512 budget; under real counting it must
        # be split. This is the exact silent-truncation failure mode.
        body = "\n\n".join(
            " ".join(f"w{i}x{j}" for j in range(300)) for i in range(5)
        )
        chunks = chunker.chunk_markdown(body, max_tokens=512)
        assert chunks
        for c in chunks:
            assert two_tokens_per_word(c.text) <= 512, (
                f"chunk of {two_tokens_per_word(c.text)} real tokens "
                f"escaped a 512 budget"
            )

    def test_unbreakable_run_is_hammer_split(self, two_tokens_per_word):
        # A single "sentence" with no sentence boundaries (URL/JSON blob
        # shape) used to pass through whole.
        blob = " ".join(f"tok{i}" for i in range(600))  # 1200 real tokens
        chunks = chunker.chunk_markdown(blob, max_tokens=512)
        assert len(chunks) >= 2
        for c in chunks:
            assert two_tokens_per_word(c.text) <= 512

    def test_hammer_pieces_are_reverified(self, monkeypatch):
        # Live-corpus regression: a single character-window pass left
        # pieces at 513-522 tokens on token-dense text. The invariant
        # must re-check every piece and re-split until it fits. The fake
        # counter adds a constant per-piece overhead so first-pass
        # windows land slightly over budget.
        counter = lambda t: 2 * len(t.split()) + 100  # noqa: E731
        monkeypatch.setattr(chunker, "_TOKEN_COUNTER", counter)
        monkeypatch.setattr(chunker, "_TOKEN_COUNTER_FAILED", False)
        blob = " ".join(f"tok{i}" for i in range(600))
        chunks = chunker.chunk_markdown(blob, max_tokens=400)
        assert chunks
        for c in chunks:
            assert counter(c.text) <= 400

    def test_headings_and_source_survive(self, two_tokens_per_word):
        body = "# Title\n\n" + " ".join(f"w{i}" for i in range(400))
        chunks = chunker.chunk_markdown(body, max_tokens=512, source="/v/x.md")
        assert all(c.source == "/v/x.md" for c in chunks)
        assert any(c.heading == "Title" for c in chunks)
        assert [c.index for c in chunks] == list(range(len(chunks)))

    def test_word_fallback_when_no_tokenizer(self, monkeypatch):
        # Without fastembed nothing embeds, so word counting is an
        # acceptable (and the only possible) budget.
        monkeypatch.setattr(chunker, "_TOKEN_COUNTER", None)
        monkeypatch.setattr(chunker, "_TOKEN_COUNTER_FAILED", True)
        body = "\n\n".join("word " * 100 for _ in range(4))
        chunks = chunker.chunk_markdown(body, max_tokens=150)
        assert chunks
        for c in chunks:
            assert len(c.text.split()) <= 150

    def test_counter_exception_falls_back_to_words(self, monkeypatch):
        def _boom(text):
            raise RuntimeError("tokenizer died")

        monkeypatch.setattr(chunker, "_TOKEN_COUNTER", _boom)
        monkeypatch.setattr(chunker, "_TOKEN_COUNTER_FAILED", False)
        chunks = chunker.chunk_markdown("hello world\n\nmore text", max_tokens=512)
        assert chunks  # never raises


def test_real_fastembed_tokenizer_respects_model_limit():
    pytest.importorskip("fastembed")
    # Force the real counter (fixture-free test: uses whatever model the
    # environment resolves). Portuguese text tokenizes well above 1
    # token/word on the English models — the case that used to truncate.
    counter = chunker._token_counter()
    if counter is None:
        pytest.skip("fastembed present but model unavailable")
    body = "\n\n".join(
        "Este parágrafo está escrito em português europeu com acentuação "
        "e vocabulário técnico de integração, arquitetura e qualidade. " * 20
        for _ in range(3)
    )
    chunks = chunker.chunk_markdown(body, max_tokens=480)
    assert chunks
    for c in chunks:
        assert counter(c.text) <= 480
