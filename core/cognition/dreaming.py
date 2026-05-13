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

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

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
    def from_profile(cls, output_subpath: str = "Projects/ArkaOS/Dreams") -> "Dreaming":
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

    def _collect_vault_chunks(self) -> list[Chunk]:
        if not self._vault.is_dir():
            return []
        cutoff = datetime.now(timezone.utc).timestamp() - self._lookback_days * 86400
        out: list[Chunk] = []
        for md in self._vault.rglob("*.md"):
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
        cutoff = datetime.now(timezone.utc).timestamp() - self._lookback_days * 86400
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
        """Lightweight clustering by shared CamelCase / path tokens.

        Embedding-based clustering is the obvious upgrade but requires
        fastembed to be installed and warmed. The token-overlap baseline
        ships value today and the embedding path is a follow-up.
        """
        buckets: dict[str, list[Chunk]] = {}
        for chunk in chunks:
            for token in _extract_topic_tokens(chunk.text):
                buckets.setdefault(token, []).append(chunk)
        clusters: list[Cluster] = []
        seen_keys: set[str] = set()
        for topic, items in sorted(buckets.items(), key=lambda kv: -len(kv[1])):
            if len(items) < _DEFAULT_MIN_CLUSTER_SIZE:
                continue
            key = "|".join(sorted({c.source_path for c in items}))
            if key in seen_keys:
                continue
            seen_keys.add(key)
            clusters.append(Cluster(topic=topic, chunks=items))
        return clusters

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
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        slug = _slugify(insight.title) or "insight"
        path = self._output_dir / f"{date_str}-{slug}.md"
        frontmatter = insight.to_frontmatter(date_str)
        path.write_text(_render_markdown(frontmatter, insight), encoding="utf-8")
        return path


def _split_for_clustering(text: str) -> list[str]:
    pieces = re.split(r"\n\s*\n", text)
    out: list[str] = []
    for p in pieces:
        p = p.strip()
        if len(p) < _MIN_CHUNK_CHARS:
            continue
        out.append(p[:_MAX_CHUNK_CHARS])
    return out


def _extract_topic_tokens(text: str) -> list[str]:
    tokens = re.findall(r"\b([A-Z][a-zA-Z0-9_-]{3,})\b", text)
    return list({t for t in tokens if t not in _STOP_TOPIC_TOKENS})[:8]


_STOP_TOPIC_TOKENS = frozenset({
    "The", "This", "That", "When", "Where", "Then", "Note", "TODO", "FIXME",
    "README", "ArkaOS", "Claude", "Read", "Write", "Edit", "Run",
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
