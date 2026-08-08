"""Tests for core.cognition.dreaming — Dreaming v2 engine.

Mocks the LLM provider so the engine is exercised end-to-end without
needing Ollama or Claude Code running in CI.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from core.cognition.dreaming import (
    _MAX_CLUSTER_CHUNKS,
    _MAX_TOKENS_PER_CHUNK,
    _MIN_DISTINCT_ORIGINS,
    Chunk,
    Cluster,
    Dreaming,
    Insight,
    _build_critic_prompt,
    _build_insight_prompt,
    _distinctive,
    _extract_topic_tokens,
    _origin_group,
    _parse_insight,
    _slugify,
    _split_for_clustering,
    _strip_non_topic_text,
)
from core.runtime.llm_provider import LLMResponse, LLMUnavailable

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def fake_provider():
    """A provider mock that returns scripted responses per call index."""
    provider = MagicMock()
    provider.complete = MagicMock()
    return provider


@pytest.fixture
def synthetic_vault(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    # One folder per project, mirroring a PARA vault. Clustering requires
    # chunks to span at least _MIN_DISTINCT_ORIGINS folders, so a flat
    # folder holding every note would produce no clusters at all.
    (vault / "Projects").mkdir()
    (vault / "Projects" / "Clientalpha").mkdir()
    (vault / "Projects" / "ArkaOS").mkdir()
    clientalpha = vault / "Projects" / "Clientalpha" / "Clientalpha.md"
    clientalpha.write_text(
        "# Clientalpha\n\n"
        "Decided to migrate Clientalpha to Inertia v3 this week, the supplier sync "
        "module was the main reason — the v2 React shell could not handle the "
        "pagination over 1000 rows that Clientalpha pricing screen needs.\n\n"
        "Pest browser tests fail on pagination over 1000 rows consistently in "
        "the Clientalpha batch_decisions screen — third occurrence this month and "
        "the pattern looks structural, not flaky.\n\n"
        "Clientalpha pricing tier B requires confirmation of 35 percent margin "
        "across the Sicily handbag line — Marta flagged the contradiction "
        "with the auditor evidence earlier in the week.\n\n"
        "Pest pagination bug recurs in Clientalpha batch_decisions screen again; "
        "shared helper paginatesLargeDataset would close this once and for "
        "all across three projects that share the pattern.\n",
        encoding="utf-8",
    )
    # Sibling note in a different folder that shares the Clientalpha /
    # Pest / pagination vocabulary, so a genuine cross-folder cluster
    # exists for the engine to find.
    (vault / "Areas").mkdir()
    (vault / "Areas" / "Testing").mkdir()
    (vault / "Areas" / "Testing" / "Pagination.md").write_text(
        "# Pagination testing\n\n"
        "Pest browser tests keep failing on pagination over 1000 rows in the "
        "Clientalpha batch_decisions screen; the shared helper "
        "paginatesLargeDataset would close this across every project.\n\n"
        "Clientalpha pricing screen pagination is the third Pest failure this "
        "month, so the batch_decisions pattern looks structural rather than "
        "flaky and deserves a shared paginatesLargeDataset helper.\n",
        encoding="utf-8",
    )
    arka = vault / "Projects" / "ArkaOS" / "ArkaOS.md"
    arka.write_text(
        "# ArkaOS notes\n\n"
        "PathResolver wraps profile.json paths and exposes ${VAULT_PATH} as "
        "the canonical token for SKILL.md substitution across the project; "
        "PathResolver shipped in v2.23.0 with 24 tests and 99 percent coverage.\n\n"
        "Cognitive layer is multi-backend after Conclave Phase 4 correction; "
        "Claude Code is the default backend, Ollama is opt-in, Anthropic API "
        "is supported for power users with API keys configured in env.\n\n"
        "PathResolver replaced hardcoded vault path in obsidian-config.json "
        "via the resolve_dict recursive substitution helper, see PR1 v2.23.0 "
        "release notes in the Knowledge Base for full diff metrics.\n",
        encoding="utf-8",
    )
    return vault


def test_split_for_clustering_filters_short_pieces():
    text = (
        "short\n\nthis is a longer paragraph that definitely exceeds the "
        "minimum chunk size threshold we use for clustering today in the engine"
    )
    pieces = _split_for_clustering(text)
    assert len(pieces) == 1
    assert "longer paragraph" in pieces[0]


def test_split_for_clustering_caps_long_pieces():
    text = "x" * 5000
    pieces = _split_for_clustering(text)
    assert len(pieces) == 1
    assert len(pieces[0]) <= 1200


def test_slugify_handles_titles_with_punctuation():
    assert _slugify("Pest Pagination > 1000 rows: bug!") == "pest-pagination-1000-rows-bug"


def test_slugify_truncates_long_titles():
    long_title = "x" * 200
    assert len(_slugify(long_title)) <= 60


def test_parse_insight_returns_none_for_pass():
    resp = LLMResponse(text="PASS", tokens_in=1, tokens_out=1, cached_tokens=0, model="x")
    cluster = Cluster(topic="Test", chunks=[])
    assert _parse_insight(resp, cluster) is None


def test_parse_insight_extracts_title_body_confidence():
    resp = LLMResponse(
        text=(
            "TITLE: Pest pagination recurring bug\n"
            "BODY: Three notes show pagination Pest tests fail. "
            "Add a shared helper.\nCONFIDENCE: high"
        ),
        tokens_in=20, tokens_out=20, cached_tokens=0, model="x",
    )
    cluster = Cluster(topic="Pest", chunks=[Chunk("Projects/Clientalpha.md", "...", "vault")])
    insight = _parse_insight(resp, cluster)
    assert insight is not None
    assert insight.title == "Pest pagination recurring bug"
    assert "shared helper" in insight.body
    assert insight.confidence == "high"
    assert insight.sources == ["Projects/Clientalpha.md"]
    assert insight.tags == ["pest"]


def test_parse_insight_defaults_confidence_when_missing():
    resp = LLMResponse(
        text="TITLE: Something\nBODY: Body here",
        tokens_in=1, tokens_out=1, cached_tokens=0, model="x",
    )
    cluster = Cluster(topic="X", chunks=[])
    insight = _parse_insight(resp, cluster)
    assert insight is not None
    assert insight.confidence == "medium"


def test_parse_insight_clamps_invalid_confidence():
    resp = LLMResponse(
        text="TITLE: X\nBODY: y\nCONFIDENCE: nuclear",
        tokens_in=1, tokens_out=1, cached_tokens=0, model="x",
    )
    cluster = Cluster(topic="X", chunks=[])
    insight = _parse_insight(resp, cluster)
    assert insight.confidence == "medium"


def test_build_insight_prompt_includes_sources_and_excerpts():
    cluster = Cluster(
        topic="Clientalpha",
        chunks=[
            Chunk("Projects/Clientalpha.md", "First excerpt about pagination.", "vault"),
            Chunk("Projects/Clientalpha.md", "Second excerpt about migration.", "vault"),
        ],
    )
    prompt = _build_insight_prompt(cluster)
    assert "Topic anchor: Clientalpha" in prompt
    assert "Projects/Clientalpha.md" in prompt
    assert "First excerpt about pagination" in prompt


def test_build_critic_prompt_asks_for_single_word_verdict():
    insight = Insight(title="X", body="Y", confidence="high")
    prompt = _build_critic_prompt(insight)
    assert "VALUABLE" in prompt
    assert "NOISE" in prompt
    assert "one word" in prompt.lower()


def test_dreaming_returns_empty_when_no_chunks(tmp_path, fake_provider):
    empty = tmp_path / "empty-vault"
    empty.mkdir()
    engine = Dreaming(vault_path=empty, output_dir=tmp_path / "out", provider=fake_provider)
    insights = engine.run()
    assert insights == []
    assert fake_provider.complete.call_count == 0


def test_dreaming_end_to_end_with_scripted_provider(synthetic_vault, tmp_path, fake_provider):
    fake_provider.complete.side_effect = [
        # First cluster — produce insight
        LLMResponse(
            text=(
                "TITLE: Pest pagination recurring\n"
                "BODY: Three Clientalpha notes mention pagination Pest "
                "tests failing. Consider a shared helper.\n"
                "CONFIDENCE: high"
            ),
            tokens_in=20, tokens_out=20, cached_tokens=0, model="test",
        ),
        # Critic — accept
        LLMResponse(text="VALUABLE", tokens_in=1, tokens_out=1, cached_tokens=0, model="test"),
    ] + [
        # Spare responses for any further clusters — all PASS
        LLMResponse(text="PASS", tokens_in=1, tokens_out=1, cached_tokens=0, model="test"),
    ] * 20
    engine = Dreaming(
        vault_path=synthetic_vault,
        output_dir=tmp_path / "dreams",
        provider=fake_provider,
        max_insights=3,
    )
    insights = engine.run()
    assert len(insights) >= 1
    assert insights[0].title == "Pest pagination recurring"
    # Verify a file was written
    written = list((tmp_path / "dreams").glob("*.md"))
    assert len(written) >= 1
    body = written[0].read_text(encoding="utf-8")
    assert "type: arkaos-insight" in body
    assert "Pest pagination recurring" in body


def test_dreaming_dry_run_does_not_write_files(synthetic_vault, tmp_path, fake_provider):
    fake_provider.complete.side_effect = [
        LLMResponse(
            text="TITLE: x\nBODY: y\nCONFIDENCE: medium",
            tokens_in=1, tokens_out=1, cached_tokens=0, model="t",
        ),
        LLMResponse(text="VALUABLE", tokens_in=1, tokens_out=1, cached_tokens=0, model="t"),
    ] + [LLMResponse(text="PASS", tokens_in=1, tokens_out=1, cached_tokens=0, model="t")] * 20
    engine = Dreaming(
        vault_path=synthetic_vault,
        output_dir=tmp_path / "dreams",
        provider=fake_provider,
    )
    insights = engine.run(dry_run=True)
    assert len(insights) >= 1
    # No files written despite insights generated
    if (tmp_path / "dreams").exists():
        assert list((tmp_path / "dreams").glob("*.md")) == []


def test_dreaming_critic_rejects_filter_noise(synthetic_vault, tmp_path, fake_provider):
    fake_provider.complete.side_effect = [
        # Insight draft passes parsing
        LLMResponse(
            text=(
                "TITLE: Noisy claim\nBODY: Generic statement about "
                "general patterns.\nCONFIDENCE: low"
            ),
            tokens_in=5, tokens_out=5, cached_tokens=0, model="t",
        ),
        # Critic rejects
        LLMResponse(text="NOISE", tokens_in=1, tokens_out=1, cached_tokens=0, model="t"),
    ] + [LLMResponse(text="PASS", tokens_in=1, tokens_out=1, cached_tokens=0, model="t")] * 20
    engine = Dreaming(
        vault_path=synthetic_vault,
        output_dir=tmp_path / "dreams",
        provider=fake_provider,
    )
    insights = engine.run()
    assert insights == []


def test_dreaming_handles_provider_unavailable(synthetic_vault, tmp_path, fake_provider):
    fake_provider.complete.side_effect = LLMUnavailable("ollama down")
    engine = Dreaming(
        vault_path=synthetic_vault,
        output_dir=tmp_path / "dreams",
        provider=fake_provider,
    )
    insights = engine.run()
    assert insights == []  # zero insights, no crash


def _chunk(path: str, text: str, kind: str = "vault") -> Chunk:
    return Chunk(source_path=path, text=text, kind=kind)


def _engine(tmp_path, fake_provider) -> Dreaming:
    return Dreaming(
        vault_path=tmp_path / "vault",
        output_dir=tmp_path / "dreams",
        provider=fake_provider,
    )


def test_cluster_ranks_specific_topics_above_broad_anchors(tmp_path, fake_provider):
    """A tight, distinctive group must outrank a large generic collision.

    Ranking used to be by bucket size, which put the broadest anchor
    first and starved the LLM budget of real clusters.
    """
    # Both groups clear every filter, so only the ranking separates them.
    # The broad group is larger (8 chunks) but shares only two tokens.
    broad = [
        _chunk(f"Areas/Zone{i}/n{i}.md", f"Integration Middleware Unique{i:02d} note.")
        for i in range(8)
    ]
    # The tight group is smaller (3 chunks) but shares five tokens.
    tight = [
        _chunk("Projects/Alpha/a.md", "Kafka Debezium Outbox Envelope Snapshot alpha."),
        _chunk("Projects/Beta/b.md", "Kafka Debezium Outbox Envelope Snapshot bravo."),
        _chunk("Areas/Data/c.md", "Kafka Debezium Outbox Envelope Snapshot charlie."),
    ]
    clusters = _engine(tmp_path, fake_provider)._cluster(broad + tight)

    topics = [c.topic for c in clusters]
    assert "Integration" in topics, "broad cluster should still be a candidate"
    assert clusters[0].topic in {"Debezium", "Envelope", "Kafka", "Outbox", "Snapshot"}, (
        f"specific cluster must rank first, got {topics[:3]}"
    )


def test_cluster_drops_one_folder_groups_when_a_cross_folder_one_exists(
    tmp_path, fake_provider
):
    """Consecutive chapters of one book are not a cross-source insight.

    They are only tolerated when nothing else clusters at all (see the
    flat-vault fallback below), so this pins the preference: while a
    genuine cross-folder group is on the table, the single-folder group
    must not reach the LLM.
    """
    same_folder = [
        _chunk("Resources/Books/ReleaseIt/06.md", "Stability Bulkhead Circuit Breaker."),
        _chunk("Resources/Books/ReleaseIt/07.md", "Stability Bulkhead Circuit Breaker."),
        _chunk("Resources/Books/ReleaseIt/08.md", "Stability Bulkhead Circuit Breaker."),
    ]
    cross_folder = [
        _chunk("Projects/Alpha/a.md", "Kafka Debezium Outbox Envelope alpha."),
        _chunk("Projects/Beta/b.md", "Kafka Debezium Outbox Envelope bravo."),
        _chunk("Areas/Data/c.md", "Kafka Debezium Outbox Envelope charlie."),
    ]
    clusters = _engine(tmp_path, fake_provider)._cluster(same_folder + cross_folder)

    assert clusters, "the cross-folder group must survive"
    for cluster in clusters:
        origins = {_origin_group(c) for c in cluster.chunks}
        assert len(origins) >= _MIN_DISTINCT_ORIGINS, cluster.topic
    sources = {c.source_path for cluster in clusters for c in cluster.chunks}
    assert not any(s.startswith("Resources/Books/") for s in sources)


def test_flat_vault_clusters_instead_of_reporting_a_quiet_night(
    tmp_path, fake_provider, caplog
):
    """Every note in the vault root shares one origin.

    Rejecting on origin alone made the commonest vault layout — no PARA
    tree, everything at the top level — report "quiet night" forever.
    Silence that looks like nothing happened is worse than a weaker
    signal, so the fallback accepts single-origin clusters and says so.
    """
    chunks = [
        _chunk("a.md", "Kafka Debezium Outbox Envelope Snapshot alpha note."),
        _chunk("b.md", "Kafka Debezium Outbox Envelope Snapshot bravo note."),
        _chunk("c.md", "Kafka Debezium Outbox Envelope Snapshot charlie note."),
    ]
    with caplog.at_level(logging.INFO, logger="core.cognition.dreaming"):
        clusters = _engine(tmp_path, fake_provider)._cluster(chunks)

    assert clusters != [], "a flat vault is not an empty vault"
    assert {c.source_path for c in clusters[0].chunks} == {"a.md", "b.md", "c.md"}
    assert "[single-origin-fallback]" in caplog.text
    assert "quiet night" not in caplog.text


def test_cluster_truncates_an_oversized_bucket_instead_of_dropping_it(
    tmp_path, fake_provider
):
    """One chunk past the ceiling used to delete the whole cluster.

    Nine notes on one topic is a better cluster than eight, not a worse
    one; the ceiling caps how much reaches the prompt, and capping is
    truncation, not rejection.
    """
    chunks = [
        _chunk(
            f"Projects/P{i}/n.md",
            f"Kafka Debezium Outbox Envelope Snapshot note Unique{i:02d}.",
        )
        for i in range(9)
    ]
    clusters = _engine(tmp_path, fake_provider)._cluster(chunks)

    assert clusters, "nine chunks around one topic must not vanish"
    assert clusters[0].topic in {
        "Debezium", "Envelope", "Kafka", "Outbox", "Snapshot",
    }
    assert len(clusters[0].chunks) == _MAX_CLUSTER_CHUNKS


def test_truncation_keeps_the_cross_origin_spread(tmp_path, fake_provider):
    """Truncation must not hand the origin filter a single-folder cluster.

    The ten chapters share four tokens the two cross-folder notes lack,
    so they own the top ten overlap scores outright. A pure
    highest-overlap cut fills all eight slots with them, and the very
    next check rejects the cluster truncation was meant to save.
    """
    chapters = [
        _chunk(
            f"Areas/Books/ReleaseIt/{i:02d}.md",
            "Bulkhead Circuit Breaker Timeout Steady Stability "
            "Chapter Excerpt Marginalia Annotated.",
        )
        for i in range(10)
    ]
    cross = [
        _chunk("Projects/Alpha/a.md",
               "Bulkhead Circuit Breaker Timeout Steady Stability alpha."),
        _chunk("Zones/Ops/b.md",
               "Bulkhead Circuit Breaker Timeout Steady Stability bravo."),
    ]
    clusters = _engine(tmp_path, fake_provider)._cluster(chapters + cross)

    assert clusters
    origins = {_origin_group(c) for c in clusters[0].chunks}
    assert len(origins) >= _MIN_DISTINCT_ORIGINS, (
        f"truncation collapsed the cluster into {origins}"
    )


def test_dedup_keeps_the_most_specific_anchor_for_the_same_notes(
    tmp_path, fake_provider
):
    """Two anchors selecting the same notes are one cluster seen twice.

    Deduplicating before ranking let the alphabet pick the survivor, so
    the broad `Alpha` anchor claimed the notes and the four-token
    `Zookeeper` group — the specific one the ranking exists to promote —
    was discarded as a duplicate.
    """
    chunks = [
        _chunk("Projects/A/a.md", "Alpha Common ledger reconciliation, alpha stream."),
        _chunk("Projects/B/b.md", "Alpha Common ledger reconciliation, bravo stream."),
        _chunk("Areas/C/c.md", "Alpha Common ledger reconciliation, charlie stream."),
        _chunk("Projects/A/a.md", "Zookeeper Chroot Znode Quorum Common alpha ensemble."),
        _chunk("Projects/B/b.md", "Zookeeper Chroot Znode Quorum Common bravo ensemble."),
        _chunk("Areas/C/c.md", "Zookeeper Chroot Znode Quorum Common charlie ensemble."),
    ]
    clusters = _engine(tmp_path, fake_provider)._cluster(chunks)

    topics = [c.topic for c in clusters]
    assert topics, "the group must survive dedup"
    assert topics[0] in {"Chroot", "Quorum", "Znode", "Zookeeper"}, topics
    assert "Alpha" not in topics, "the broad anchor must lose, not win by sort order"


def test_distinctive_keeps_the_rarest_tokens_not_the_alphabetical_head():
    """The per-chunk cap used to slice an alphabetically sorted set.

    A note's distinctive vocabulary then survived or died by its initial
    letter: `Zookeeper` was always dropped, `Common00` always kept, and
    the rare tokens the specificity ranking runs on never reached a
    bucket at all.
    """
    doc_freq: Counter[str] = Counter({f"Common{i:02d}": 50 for i in range(20)})
    doc_freq.update({"Zookeeper": 2, "Znode": 2})
    tokens = set(doc_freq)

    kept = _distinctive(tokens, doc_freq)

    assert len(kept) == _MAX_TOKENS_PER_CHUNK
    assert {"Zookeeper", "Znode"} <= kept
    assert kept == _distinctive(set(doc_freq), doc_freq), "must not vary per run"


def test_distinctive_leaves_small_token_sets_untouched():
    doc_freq: Counter[str] = Counter({"Kafka": 3, "Debezium": 2})
    assert _distinctive({"Kafka", "Debezium"}, doc_freq) == {"Kafka", "Debezium"}


def test_cluster_requires_more_than_one_shared_token(tmp_path, fake_provider):
    """One token in common is a coincidence, not a topic."""
    chunks = [
        _chunk("Projects/A/a.md", "Postgres alpha unique-alpha-words here."),
        _chunk("Projects/B/b.md", "Postgres bravo distinct-bravo-terms here."),
        _chunk("Areas/C/c.md", "Postgres charlie separate-charlie-nouns here."),
    ]
    assert _engine(tmp_path, fake_provider)._cluster(chunks) == []


def test_extract_topic_tokens_drops_template_and_query_scaffolding():
    text = "Synopsis Sources Resources TABLE FROM WHERE SORT Kafka Debezium"
    tokens = _extract_topic_tokens(text)
    assert tokens == ["Debezium", "Kafka"]


def test_extract_topic_tokens_is_sorted_and_stable():
    """Set iteration order for strings varies with PYTHONHASHSEED, so any
    downstream step that keeps a subset would keep a different one per
    run. The subset step itself now lives in `_distinctive`, which needs
    corpus frequencies this function cannot see."""
    words = " ".join(f"Token{i:03d}" for i in range(60))
    assert _extract_topic_tokens(words) == sorted(_extract_topic_tokens(words))
    assert _extract_topic_tokens(words) == _extract_topic_tokens(words)
    assert len(_extract_topic_tokens(words)) == 60, "the cap moved to _distinctive"


def test_dreaming_never_ingests_its_own_output(tmp_path, fake_provider):
    """Insights live inside the vault; re-reading them amplifies findings."""
    vault = tmp_path / "vault"
    dreams = vault / "Projects" / "ArkaOS" / "Dreams"
    dreams.mkdir(parents=True)
    (dreams / "2026-08-04-old-insight.md").write_text(
        "Yesterday's observation about Kafka Debezium Outbox that must not "
        "be fed back into today's corpus under any circumstances at all.\n",
        encoding="utf-8",
    )
    engine = Dreaming(vault_path=vault, output_dir=dreams, provider=fake_provider)
    assert engine._collect_vault_chunks() == []


# --- _strip_non_topic_text: document-level noise removal ------------------


def test_strip_removes_yaml_frontmatter():
    """`aliases:` and `tags:` describe filing, not subject matter."""
    text = "---\naliases: [Router, EIP]\ntags: [patterns]\n---\n\nA router sends a message."
    out = _strip_non_topic_text(text)
    assert "aliases" not in out
    assert "A router sends a message." in out


def test_strip_removes_cross_reference_section_and_its_body():
    """The heading and the lines it governs both go, up to the next heading."""
    text = (
        "## Topic\n\nA router inspects the payload.\n\n"
        "## Related\n\n- [[Message Broker]]\n- [[Content Filter]]\n\n"
        "## Consequences\n\nThroughput drops.\n"
    )
    out = _strip_non_topic_text(text)
    assert "Message Broker" not in out
    assert "Content Filter" not in out
    # The section AFTER the cross-reference block must survive.
    assert "Throughput drops." in out
    assert "A router inspects the payload." in out


def test_strip_handles_portuguese_and_alternate_headings():
    for heading in ("## Connections", "## Relacionadas", "## Sources", "## See also"):
        text = "Real content here.\n\n" + heading + "\n\n- [[Some Note]]\n"
        out = _strip_non_topic_text(text)
        assert "Some Note" not in out, heading
        assert "Real content here." in out, heading


def test_strip_removes_bare_wikilink_lines():
    """Catches a cross-reference block whose heading fell in another chunk."""
    text = (
        "The content based router pattern applies whenever consumers differ.\n\n"
        "[[Router]], [[Splitter]], [[Aggregator]]\n"
    )
    out = _strip_non_topic_text(text)
    assert "Splitter" not in out
    assert "content based router pattern applies" in out


def test_strip_removes_attribution_lines():
    text = (
        "Big ball of mud is the commonest architecture.\n\n"
        "— Brian Foote and Joseph Yoder\n"
    )
    out = _strip_non_topic_text(text)
    assert "Brian Foote" not in out
    assert "Big ball of mud" in out


def test_strip_keeps_blockquote_bodies():
    """Deliberate trade-off: the Synopsis lives in a blockquote and is the
    densest real content in a book note. Stripping quotes to catch the
    attribution lines would cost far more signal than it removes."""
    text = "> **Synopsis:** Layered architecture separates concerns.\n"
    out = _strip_non_topic_text(text)
    assert "Layered architecture separates concerns." in out


def test_strip_keeps_a_heading_that_only_starts_with_a_link_word():
    """`## Sources of latency` is analysis, not a cross-reference block.

    Unanchored, the heading pattern matched it and deleted everything
    down to the next heading — the failure mode here is silent data
    loss, so the heading must match to end of line.
    """
    text = (
        "## Sources of latency\n\n"
        "Queue depth drives the tail, not the median service time.\n\n"
        "## Related\n\n- [[Message Broker]]\n"
    )
    out = _strip_non_topic_text(text)
    assert "Queue depth drives the tail" in out
    assert "Message Broker" not in out


def test_strip_still_removes_a_related_notes_heading():
    """`## Related Notes` is unambiguously a cross-reference block."""
    text = "Real content about routers.\n\n## Related Notes\n\n- [[Splitter]]\n"
    out = _strip_non_topic_text(text)
    assert "Splitter" not in out
    assert "Real content about routers." in out


def test_strip_keeps_the_body_after_a_leading_horizontal_rule():
    """A note opening on `---` has no frontmatter.

    The old pattern matched the rule as an opening fence and ran to the
    next rule, deleting the note's first section as if it were metadata.
    """
    text = (
        "---\n\n"
        "The outbox pattern keeps the write and the event atomic.\n\n"
        "---\n\n"
        "Idempotent consumers make the replay safe.\n"
    )
    out = _strip_non_topic_text(text)
    assert "outbox pattern keeps the write" in out
    assert "Idempotent consumers make the replay safe." in out


def test_split_for_clustering_drops_cross_reference_chunks():
    """Wiring check: the strip must run before chunking, not per chunk."""
    text = (
        "Routers dispatch each message to the right consumer by inspecting\n"
        "its content, which keeps the producer unaware of the topology.\n\n"
        "## Related\n\n"
        "- [[Message Broker]] and [[Content Based Router]] and [[Recipient List]]\n"
        "- [[Dynamic Router]] and [[Routing Slip]] and [[Process Manager]]\n"
        "- [[Splitter]] and [[Aggregator]] and [[Resequencer]] and [[Scatter Gather]]\n"
    )
    joined = " ".join(_split_for_clustering(text))
    assert "Message Broker" not in joined
    assert "Routers dispatch each message" in joined


# --- CLI entry point ------------------------------------------------------


def _run_dreaming_cli(home: Path, *args: str) -> subprocess.CompletedProcess:
    """Run the module the way the scheduler does: `python -m`.

    Same shape as tests/python/test_core_hooks_entrypoints.py::_run_module.
    HOME and USERPROFILE are set together because Path.home() consults
    USERPROFILE on Windows and HOME on POSIX, and the child inherits
    os.environ — setting one alone leaves the developer's real profile
    in play.
    """
    env = dict(os.environ)
    env.update({
        "PYTHONPATH": str(REPO_ROOT),
        "ARKAOS_ROOT": str(REPO_ROOT),
        "HOME": str(home),
        "USERPROFILE": str(home),
    })
    # An exported vault override would beat the fixture's profile.json.
    env.pop("ARKAOS_VAULT_PATH", None)
    env.pop("ARKAOS_VAULT", None)
    return subprocess.run(
        [sys.executable, "-m", "core.cognition.dreaming", *args],
        capture_output=True, text=True, timeout=120, env=env, check=False,
    )


@pytest.fixture
def cli_home(tmp_path):
    """A synthetic HOME the CLI can start from, with no real LLM behind it."""
    home = tmp_path / "home"
    (home / ".arkaos").mkdir(parents=True)
    vault = home / "vault"
    (vault / "Notes").mkdir(parents=True)
    (home / ".arkaos" / "profile.json").write_text(json.dumps({
        "version": "3",
        "vaultPath": str(vault),
        "reposRoot": str(home / "repos"),
    }), encoding="utf-8")
    # Pin the stub provider: this test proves the entry point loads and
    # runs, not that a model answers. Without the pin the fallback chain
    # could shell out to whatever runtime the developer has installed.
    (home / ".arkaos" / "config.json").write_text(
        json.dumps({"llm": {"provider": "stub"}}), encoding="utf-8",
    )
    (vault / "Notes" / "kafka.md").write_text(
        "---\naliases: [CDC]\ntags: [streaming]\n---\n\n"
        "# Kafka\n\n"
        "The Debezium outbox envelope replays change events for every "
        "downstream consumer without ever needing a full backfill.\n\n"
        "## Related\n\n- [[Message Broker]]\n",
        encoding="utf-8",
    )
    return home


def test_dreaming_cli_runs_as_a_module(cli_home):
    """`python -m core.cognition.dreaming run` must reach the end.

    This is how the nightly scheduler starts Dreaming
    (config/cognition/schedules.yaml: python_module + module_args).
    Names defined below the `__main__` guard do not exist yet when
    main() runs, so the CLI died on NameError inside the first chunking
    call while every in-process test stayed green — importing the module
    executes the whole file and never fires the guard.
    """
    result = _run_dreaming_cli(cli_home, "run", "--dry-run")

    assert result.returncode == 0, result.stderr
    assert "NameError" not in result.stderr, result.stderr
    assert "Dreaming produced" in result.stdout, result.stdout


def test_dreaming_cli_reports_a_missing_profile_without_a_traceback(tmp_path):
    """The other CLI exit path, so a regression there is not silent."""
    home = tmp_path / "bare-home"
    home.mkdir()
    result = _run_dreaming_cli(home, "run")

    assert result.returncode == 2, result.stderr
    assert "Cannot start Dreaming" in result.stdout
    assert "Traceback" not in result.stderr
