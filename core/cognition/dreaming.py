"""Dreaming v2 — nightly cognitive consolidation that surfaces insights.

Runs (manually or on a schedule) over the user's recent vault notes and
session digests, groups related content into clusters, asks the
configured LLM (Claude Code by default, Ollama / Anthropic / OpenAI on
opt-in) for one observation per cluster, and applies a second LLM pass
that filters noise. Accepted insights are written to the Obsidian vault
in a plugin-compat shape that a future mobile reader can consume.

Backend-agnostic by design — completion goes through
``core.runtime.llm_provider.get_llm_provider()``. The same engine works
with any registered provider; the user picks in ``profile.json``.

See PR8 v2.30.0 and the 2026-05-13 Conclave Phase 4 correction (multi-
backend, not Ollama-only) for the architectural rationale.
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from core.runtime.llm_provider import LLMResponse, LLMUnavailable, get_llm_provider
from core.runtime.path_resolver import ProfileMissingError, load_profile

logger = logging.getLogger(__name__)

_DEFAULT_VAULT_LOOKBACK_DAYS = 7
_DEFAULT_MIN_CLUSTER_SIZE = 3
_DEFAULT_MAX_CLUSTERS = 12
_DEFAULT_MAX_INSIGHTS = 5
_MIN_CHUNK_CHARS = 80
_MAX_CHUNK_CHARS = 1200
_CRITIC_PASS_TOKEN = "VALUABLE"
# A cluster wider than this is an anchor collision, not a topic: the
# broadest token in a real vault ("Integration") hits hundreds of chunks
# that share nothing else.
_MAX_CLUSTER_CHUNKS = 8
# One shared token is a coincidence. Requiring a second one is what
# separates "these notes discuss the same thing" from "these notes both
# happen to contain a capitalised word".
_MIN_SHARED_TOKENS = 2
# Chunks confined to a single folder are one book or one document read
# end to end. Dreaming exists to connect across sources, not summarise.
_MIN_DISTINCT_ORIGINS = 2
_MAX_TOKENS_PER_CHUNK = 16


@dataclass
class Insight:
    """One accepted insight ready for vault write."""

    title: str
    body: str
    confidence: str  # "high" | "medium" | "low"
    sources: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    def to_frontmatter(self, date_str: str) -> dict:
        return {
            "type": "arkaos-insight",
            "date": date_str,
            "status": "surfaced",
            "confidence": self.confidence,
            # Grounding quarantine (PR-3 v4.1): Dreaming output is
            # LLM-inferred, not extracted from authoritative sources.
            # Synapse L2.5 reads this marker and excludes (or explicitly
            # labels) these notes so they never masquerade as grounded KB.
            "grounding": "inferred",
            "sources": [f"[[{s}]]" for s in self.sources],
            "tags": ["arkaos-dream", *self.tags],
            "plugin_compat_version": "1.0",
        }


@dataclass
class Chunk:
    """A piece of source text fed into clustering."""

    source_path: str
    text: str
    kind: str  # "vault" | "session-digest" | "capture"


@dataclass
class Cluster:
    """A group of related chunks."""

    topic: str
    chunks: list[Chunk] = field(default_factory=list)


class Dreaming:
    """Engine that produces nightly insights from recent activity."""

    def __init__(
        self,
        vault_path: Path,
        output_dir: Path,
        digest_dir: Path | None = None,
        lookback_days: int = _DEFAULT_VAULT_LOOKBACK_DAYS,
        max_insights: int = _DEFAULT_MAX_INSIGHTS,
        provider=None,
    ) -> None:
        self._vault = Path(vault_path)
        self._output_dir = Path(output_dir)
        self._digest_dir = Path(digest_dir) if digest_dir else None
        self._lookback_days = lookback_days
        self._max_insights = max_insights
        self._provider = provider or get_llm_provider()

    @classmethod
    def from_profile(cls, output_subpath: str = "Projects/ArkaOS/Dreams") -> Dreaming:
        """Construct a Dreaming engine from the user's profile.json."""
        profile = load_profile()
        vault = Path(profile.vault_path)
        output = vault / output_subpath
        digests = Path.home() / ".arkaos" / "session-digests"
        return cls(vault_path=vault, output_dir=output, digest_dir=digests)

    def run(self, dry_run: bool = False) -> list[Insight]:
        """Execute one dreaming pass. Returns accepted insights."""
        chunks = self._collect_chunks()
        if not chunks:
            logger.info("Dreaming: no chunks to process — quiet night")
            return []

        clusters = self._cluster(chunks)
        if not clusters:
            logger.info("Dreaming: no clusters formed — quiet night")
            return []

        accepted: list[Insight] = []
        for cluster in clusters[: _DEFAULT_MAX_CLUSTERS]:
            insight = self._draft_insight(cluster)
            if insight is None:
                continue
            if not self._critic_accepts(insight):
                continue
            accepted.append(insight)
            if len(accepted) >= self._max_insights:
                break

        if not dry_run:
            for insight in accepted:
                self._write_insight(insight)
        return accepted

    def _collect_chunks(self) -> list[Chunk]:
        chunks: list[Chunk] = []
        chunks.extend(self._collect_vault_chunks())
        chunks.extend(self._collect_digest_chunks())
        return chunks

    def _is_own_output(self, path: Path) -> bool:
        """True when ``path`` is a previously written insight.

        The output directory lives inside the vault, so without this
        guard every insight re-enters the next run's corpus. Yesterday's
        observation then clusters with itself and gets re-derived, which
        is how a single unfixed finding can dominate days of output.
        """
        try:
            path.relative_to(self._output_dir)
        except ValueError:
            return False
        return True

    def _collect_vault_chunks(self) -> list[Chunk]:
        if not self._vault.is_dir():
            return []
        cutoff = datetime.now(UTC).timestamp() - self._lookback_days * 86400
        out: list[Chunk] = []
        for md in self._vault.rglob("*.md"):
            if self._is_own_output(md):
                continue
            try:
                if md.stat().st_mtime < cutoff:
                    continue
                text = md.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            relative = str(md.relative_to(self._vault))
            for piece in _split_for_clustering(text):
                out.append(Chunk(source_path=relative, text=piece, kind="vault"))
        return out

    def _collect_digest_chunks(self) -> list[Chunk]:
        if not self._digest_dir or not self._digest_dir.is_dir():
            return []
        cutoff = datetime.now(UTC).timestamp() - self._lookback_days * 86400
        out: list[Chunk] = []
        for f in self._digest_dir.glob("*.md"):
            try:
                if f.stat().st_mtime < cutoff:
                    continue
                text = f.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for piece in _split_for_clustering(text):
                out.append(Chunk(source_path=f.name, text=piece, kind="session-digest"))
        return out

    def _cluster(self, chunks: list[Chunk]) -> list[Cluster]:
        """Group chunks by shared topic tokens, ranked by specificity.

        Ranking by bucket size (the original behaviour) selected the most
        generic anchors first, because the broadest token always owns the
        biggest bucket. Only the top ``_DEFAULT_MAX_CLUSTERS`` reach the
        LLM, so size-ranking guaranteed that only anchor collisions were
        ever drafted. Specificity ranking inverts that: clusters sharing
        the most, rarest tokens go first.

        Embedding-based clustering is the obvious upgrade but requires
        fastembed to be installed and warmed. The token-overlap baseline
        ships value today and the embedding path is a follow-up.
        """
        raw_sets = [set(_extract_topic_tokens(c.text)) for c in chunks]
        doc_freq: Counter[str] = Counter(t for ts in raw_sets for t in ts)
        token_sets = [_distinctive(ts, doc_freq) for ts in raw_sets]

        buckets: dict[str, list[tuple[Chunk, set[str]]]] = {}
        for chunk, tokens in zip(chunks, token_sets, strict=True):
            for token in tokens:
                buckets.setdefault(token, []).append((chunk, tokens))

        scored = _rank_buckets(buckets, doc_freq, require_distinct_origins=True)
        if not scored:
            # A vault whose notes all sit in one folder — the default
            # layout before anyone builds a PARA tree — has exactly one
            # origin, so the cross-source filter rejects everything and
            # the caller reports a quiet night that never happened.
            # Falling back to single-origin clusters trades a weaker
            # signal for an honest one; the marker says which it was.
            scored = _rank_buckets(
                buckets, doc_freq, require_distinct_origins=False
            )
            if scored:
                logger.info(
                    "Dreaming: [single-origin-fallback] nothing spans %d "
                    "origins; accepting %d single-origin cluster(s) rather "
                    "than reporting silence",
                    _MIN_DISTINCT_ORIGINS, len(scored),
                )
        return [Cluster(topic=topic, chunks=cs) for _, _, topic, cs in scored]

    def _draft_insight(self, cluster: Cluster) -> Insight | None:
        prompt = _build_insight_prompt(cluster)
        try:
            response = self._provider.complete(prompt, max_tokens=400)
        except LLMUnavailable as exc:
            logger.warning("Dreaming: provider unavailable, skipping cluster (%s)", exc)
            return None
        return _parse_insight(response, cluster)

    def _critic_accepts(self, insight: Insight) -> bool:
        prompt = _build_critic_prompt(insight)
        try:
            response = self._provider.complete(prompt, max_tokens=20)
        except LLMUnavailable:
            return False  # safer to reject than to publish unchecked
        return _CRITIC_PASS_TOKEN in response.text.upper()

    def _write_insight(self, insight: Insight) -> Path:
        self._output_dir.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now(UTC).strftime("%Y-%m-%d")
        slug = _slugify(insight.title) or "insight"
        path = self._output_dir / f"{date_str}-{slug}.md"
        frontmatter = insight.to_frontmatter(date_str)
        path.write_text(_render_markdown(frontmatter, insight), encoding="utf-8")
        return path


def _split_for_clustering(text: str) -> list[str]:
    pieces = re.split(r"\n\s*\n", _strip_non_topic_text(text))
    out: list[str] = []
    for p in pieces:
        p = p.strip()
        if len(p) < _MIN_CHUNK_CHARS:
            continue
        out.append(p[:_MAX_CHUNK_CHARS])
    return out


def _origin_group(chunk: Chunk) -> str:
    """Coarse origin of a chunk, used to reject single-source clusters.

    Vault chunks group by folder, so consecutive chapters of one book
    collapse into a single origin. Session digests group by file, since
    each digest is already a distinct session.
    """
    if chunk.kind != "vault":
        return chunk.source_path
    return PurePosixPath(chunk.source_path.replace("\\", "/")).parent.as_posix()


def _rank_buckets(
    buckets: dict[str, list[tuple[Chunk, set[str]]]],
    doc_freq: Counter[str],
    *,
    require_distinct_origins: bool,
) -> list[tuple[int, float, str, list[Chunk]]]:
    """Score every bucket, rank by specificity, then drop duplicates.

    The order of those three steps is the point. Deduplicating first —
    the original — let whichever anchor sorted first alphabetically
    claim a set of notes, so ``Alpha`` beat ``Zookeeper`` for the same
    cluster and the specificity ranking was decided by the alphabet.
    Ranking first means the survivor is the tightest anchor.
    """
    scored: list[tuple[int, float, str, list[Chunk]]] = []
    for topic, items in sorted(buckets.items()):
        candidate = _score_bucket(
            topic, items, doc_freq,
            require_distinct_origins=require_distinct_origins,
        )
        if candidate is not None:
            scored.append(candidate)
    scored.sort(key=lambda s: (-s[0], s[1], s[2]))

    deduped: list[tuple[int, float, str, list[Chunk]]] = []
    seen_keys: set[str] = set()
    for candidate in scored:
        # Keyed on the chunks that survived truncation, not on the raw
        # bucket: the key must describe the cluster actually drafted.
        key = "|".join(sorted({c.source_path for c in candidate[3]}))
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped.append(candidate)
    return deduped


def _score_bucket(
    topic: str,
    items: list[tuple[Chunk, set[str]]],
    doc_freq: Counter[str],
    *,
    require_distinct_origins: bool = True,
) -> tuple[int, float, str, list[Chunk]] | None:
    """Score one candidate cluster, or reject it.

    Returns ``(shared_token_count, mean_document_frequency, topic,
    chunks)``. Callers sort by descending shared count then ascending
    frequency, so tight groups around rare tokens rank first.

    An oversized bucket is truncated, never rejected. Rejecting it threw
    away the tight subgroup hiding inside the collision along with the
    collision: one extra chunk past the ceiling and a real cluster
    silently stopped existing.
    """
    if len(items) < _DEFAULT_MIN_CLUSTER_SIZE:
        return None
    if len(items) > _MAX_CLUSTER_CHUNKS:
        items = _truncate_to_ceiling(topic, items, _MAX_CLUSTER_CHUNKS)
    shared = set.intersection(*[tokens for _, tokens in items])
    if len(shared) < _MIN_SHARED_TOKENS:
        return None
    chunks = [c for c, _ in items]
    if require_distinct_origins and (
        len({_origin_group(c) for c in chunks}) < _MIN_DISTINCT_ORIGINS
    ):
        return None
    mean_freq = sum(doc_freq[t] for t in shared) / len(shared)
    return len(shared), mean_freq, topic, chunks


def _truncate_to_ceiling(
    topic: str, items: list[tuple[Chunk, set[str]]], limit: int
) -> list[tuple[Chunk, set[str]]]:
    """Keep the ``limit`` chunks that make the tightest cluster.

    Chunks are ordered by how much vocabulary they share with the rest
    of the bucket — the anchor itself excluded, since every chunk in the
    bucket carries it and a constant cannot rank anything. Selection
    then takes one chunk per origin before filling the remaining slots.

    That origin pass is load-bearing. The highest-overlap chunks of a
    wide bucket are near-duplicate pages of one document, so a pure
    overlap cut hands ``_score_bucket`` a single-origin cluster and the
    very next check rejects what truncation was meant to save.

    Ties break on source path then original position, so the kept set is
    identical across runs and interpreter seeds.
    """
    freq: Counter[str] = Counter(t for _, tokens in items for t in tokens)

    def overlap(index: int) -> int:
        return sum(freq[t] - 1 for t in items[index][1] if t != topic)

    order = sorted(
        range(len(items)),
        key=lambda i: (-overlap(i), items[i][0].source_path, i),
    )

    kept: list[int] = []
    origins: set[str] = set()
    for i in order:
        origin = _origin_group(items[i][0])
        if origin in origins:
            continue
        origins.add(origin)
        kept.append(i)
        if len(kept) == limit:
            break
    if len(kept) < limit:
        chosen = set(kept)
        for i in order:
            if i in chosen:
                continue
            kept.append(i)
            if len(kept) == limit:
                break
    return [items[i] for i in sorted(kept)]


def _distinctive(tokens: set[str], doc_freq: Counter[str]) -> set[str]:
    """The ``_MAX_TOKENS_PER_CHUNK`` rarest tokens of one chunk.

    Slicing the alphabetically sorted set — the original cap — dropped
    late-alphabet tokens no matter what they were worth, so a chunk's
    distinctive vocabulary survived or died by its initial letter and
    ``Zookeeper`` never reached a bucket. Corpus document frequency is
    the signal the specificity ranking already runs on, so the cap runs
    on it too: the rarest tokens are the ones that make a cluster tight.
    """
    if len(tokens) <= _MAX_TOKENS_PER_CHUNK:
        return tokens
    ranked = sorted(tokens, key=lambda t: (doc_freq[t], t))
    return set(ranked[:_MAX_TOKENS_PER_CHUNK])


def _extract_topic_tokens(text: str) -> list[str]:
    tokens = re.findall(r"\b([A-Z][a-zA-Z0-9_-]{3,})\b", text)
    # sorted(), not list(set()): set iteration order for strings varies
    # with PYTHONHASHSEED, so anything downstream that keeps a subset
    # used to keep a different one per run and clustering was
    # irreproducible. The per-chunk cap itself lives in _distinctive(),
    # which needs corpus frequencies this function cannot see.
    return sorted({t for t in tokens if t not in _STOP_TOPIC_TOKENS})


_STOP_TOPIC_TOKENS = frozenset({
    "The", "This", "That", "When", "Where", "Then", "Note", "TODO", "FIXME",
    "README", "ArkaOS", "Claude", "Read", "Write", "Edit", "Run",
    # Note-template section headers. These co-occur across notes that
    # share nothing but the template, which is the single largest source
    # of false clusters in a real vault.
    "Synopsis", "Sources", "Resources", "Summary", "Context", "Status",
    "Tags", "Links", "Overview", "Details", "What", "Why", "How",
    # Dataview / SQL keywords embedded in vault queries.
    "TABLE", "FROM", "WHERE", "SORT", "LIMIT", "GROUP", "FLATTEN",
    # Capitalised connectives that survive the sentence-start regex.
    "They", "Each", "Every", "There", "These", "Those", "With", "Only",
    "Also", "Both", "Some", "Such", "Which", "While", "After", "Before",
    "Between", "Because", "Would", "Could", "Should",
})


def _build_insight_prompt(cluster: Cluster) -> str:
    excerpts = []
    sources = []
    for c in cluster.chunks[:6]:
        sources.append(c.source_path)
        excerpts.append(f"[{c.source_path}]\n{c.text[:400]}\n")
    src_lines = "\n".join(f"- {s}" for s in sorted(set(sources)))
    return (
        "You are reviewing the user's recent work. Several notes share a topic.\n\n"
        f"Topic anchor: {cluster.topic}\n\n"
        f"Sources:\n{src_lines}\n\n"
        f"Excerpts:\n{''.join(excerpts)}\n"
        "Return ONE concrete observation, pattern, or action the user might "
        "want to consider. Two sentences maximum. If nothing is genuinely "
        "surprising or actionable, return literally: PASS\n\n"
        "Format your reply as:\n"
        "TITLE: <very short title>\n"
        "BODY: <two sentences>\n"
        "CONFIDENCE: high | medium | low\n"
    )


def _build_critic_prompt(insight: Insight) -> str:
    return (
        "Judge this insight as if it were going to land on the user's desk "
        "tomorrow morning. Is it specific, actionable, and non-generic? "
        "Or is it noise that would erode trust over time?\n\n"
        f"Title: {insight.title}\n"
        f"Body: {insight.body}\n\n"
        "Reply with exactly one word: VALUABLE or NOISE."
    )


def _parse_insight(response: LLMResponse, cluster: Cluster) -> Insight | None:
    text = response.text.strip()
    if not text or text.upper().startswith("PASS"):
        return None
    title = _extract_field(text, "TITLE") or _first_line(text)
    body = _extract_field(text, "BODY") or text
    confidence = _extract_field(text, "CONFIDENCE") or "medium"
    confidence = confidence.lower()
    if confidence not in {"high", "medium", "low"}:
        confidence = "medium"
    sources = sorted({c.source_path for c in cluster.chunks})[:6]
    tags = [cluster.topic.lower()] if cluster.topic else []
    return Insight(title=title.strip(), body=body.strip(), confidence=confidence,
                   sources=sources, tags=tags)


def _extract_field(text: str, field_name: str) -> str | None:
    pattern = re.compile(
        rf"^{re.escape(field_name)}\s*:\s*(.+?)$", re.IGNORECASE | re.MULTILINE
    )
    match = pattern.search(text)
    if match:
        return match.group(1).strip()
    return None


def _first_line(text: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        if line:
            return line[:80]
    return "Insight"


def _slugify(title: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9-]+", "-", title.lower()).strip("-")
    return slug[:60]


def _render_markdown(frontmatter: dict, insight: Insight) -> str:
    lines = ["---"]
    for key, value in frontmatter.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            for v in value:
                lines.append(f"  - {v}")
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    lines.append("")
    lines.append(f"# {insight.title}")
    lines.append("")
    lines.append("## What I noticed")
    lines.append(insight.body)
    if insight.sources:
        lines.append("")
        lines.append("## Sources")
        for s in insight.sources:
            lines.append(f"- [[{s}]]")
    return "\n".join(lines) + "\n"


# ─── Document-level noise removal ─────────────────────────────────────
#
# Everything below is module state that ``_split_for_clustering`` needs
# at call time, so it MUST stay above the ``__main__`` guard. Defined
# after it, the names simply do not exist when ``main()`` runs, and
# ``python -m core.cognition.dreaming`` — how the nightly scheduler
# starts Dreaming (config/cognition/schedules.yaml) — died on NameError
# while every in-process test stayed green, because importing the module
# runs the whole file and never fires the guard.

# Sections whose whole point is to name other notes. Every capitalised
# token in them is a pointer, not a subject, and they co-occur across
# notes that merely sit near each other in the vault graph.
#
# This MUST run on the whole document, before chunking. Chunks are split
# on blank lines, so the `## Related` heading always lands in a different
# chunk than the bullets under it — which is why "strip the Related
# section" was proposed three times as a per-chunk filter and would have
# changed nothing. The heading is never in the chunk it governs.
#
# The heading is anchored to end of line (bar an optional `Notes`/`Links`
# suffix and a trailing colon). Unanchored, `## Sources of latency` read
# as a cross-reference block and deleted a real analysis section down to
# the next heading — silent data loss, where the anchored version's worst
# case is leaving some link noise in.
_LINK_SECTION_RE = re.compile(
    r"^#{1,6}[ \t]*(?:related|connections?|conex(?:ões|oes)|relacionad[ao]s|"
    r"sources?|see also|refer(?:ences?|ências)?|liga(?:ções|coes)|"
    r"ver também)(?:[ \t]+(?:notes?|links?))?[ \t]*:?[ \t]*(?:\r?\n|\Z)"
    r".*?(?=^#{1,6}[ \t]|\Z)",
    re.IGNORECASE | re.MULTILINE | re.DOTALL,
)
# YAML frontmatter. `aliases:`, `tags:` and `chapter_title:` are dense
# with capitalised words that describe the note's filing, not its topic.
#
# The lookahead demands a YAML key on the first line inside the fence.
# Without it, a note opening on a `---` horizontal rule matched, and the
# non-greedy body ran to the next rule — so the note's first section was
# deleted as if it were frontmatter.
_FRONTMATTER_RE = re.compile(
    r"\A---[ \t]*\r?\n(?=[A-Za-z_][\w-]*[ \t]*:).*?\r?\n---[ \t]*\r?\n",
    re.DOTALL,
)
# A line that is nothing but wikilinks and separators. Catches a
# `## Related` block whose heading fell outside the chunk boundary.
_LINK_ONLY_LINE_RE = re.compile(
    r"^[\s>*\-]*(?:\[\[[^\]]+\]\][\s·,;|/&+]*)+$", re.MULTILINE
)
# Citation attribution: `— Brian Foote and Joseph Yoder`. The names are
# provenance, and clustering on them groups every note quoting the same
# author regardless of what the quote says.
# The em/en dash pair is the literal punctuation being matched, not an
# accidental lookalike — hence the RUF001 suppression.
_ATTRIBUTION_RE = re.compile(
    r"^[\s>]*[—–]{1,2}\s*[A-Z][^\n]*$",  # noqa: RUF001
    re.MULTILINE,
)


def _strip_non_topic_text(text: str) -> str:
    """Remove the parts of a note that name things instead of discussing them.

    Frontmatter, cross-reference sections, bare wikilink lines and
    citation attributions all carry capitalised tokens with no topical
    meaning. Left in, they are the dominant source of false clusters —
    every false anchor in the reviews between 2026-07-31 and 2026-08-05
    (generic nouns like Data/Architecture/HTTP, plus capitalised first
    names lifted from citation lines) traced back to one.

    Call this on the whole document, before ``_split_for_clustering``.
    Filtering per chunk cannot work: the section heading and the lines
    it governs are always in different chunks.

    Blockquote bodies are deliberately kept. This vault's note template
    puts the `> **Synopsis:**` in a blockquote, which is the densest
    real content in a book note; stripping quotes to catch attribution
    lines would cost far more signal than it removes.
    """
    text = _FRONTMATTER_RE.sub("", text)
    text = _LINK_SECTION_RE.sub("", text)
    text = _LINK_ONLY_LINE_RE.sub("", text)
    text = _ATTRIBUTION_RE.sub("", text)
    return text


# ─── CLI ──────────────────────────────────────────────────────────────


def main(argv: list[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["run"], help="action to perform")
    parser.add_argument("--dry-run", action="store_true", help="cluster + draft without writing")
    args = parser.parse_args(argv)

    try:
        engine = Dreaming.from_profile()
    except ProfileMissingError as exc:
        print(f"Cannot start Dreaming: {exc}")
        return 2

    insights = engine.run(dry_run=args.dry_run)
    print(f"Dreaming produced {len(insights)} insight(s).")
    for i, insight in enumerate(insights, start=1):
        print(f"{i}. ({insight.confidence}) {insight.title}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv[1:]))
