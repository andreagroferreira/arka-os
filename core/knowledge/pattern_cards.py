"""Pattern Library — append-style store of prior implementations.

When a feature ships and Marta APPROVES it, the orchestrator may
register a `PatternCard` so future feature work has a "we have
already built this" reference: files, AC, edge cases, references.
The Synapse L7.5 layer queries this store on every user prompt and
injects top matching cards as context.

For v1 (PR4 v3.75.0): keyword + tag matching, recency-sorted, dedup
by id. Semantic similarity via vector embeddings lands in v3.75.x.

PR4 of the Squad Intelligence Upgrade.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timezone
from pathlib import Path

from core.shared import safe_session_id as _safe_session_id_module

try:
    import fcntl  # POSIX only
    _HAS_FLOCK = True
except ImportError:
    _HAS_FLOCK = False


PATTERNS_PATH: Path = Path.home() / ".arkaos" / "patterns" / "cards.jsonl"


@dataclass
class PatternCard:
    """One reusable feature implementation pattern."""

    id: str
    name: str
    feature_keywords: list[str]
    description: str
    stack: list[str]
    files: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    edge_cases: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)
    projects_using: list[str] = field(default_factory=list)
    created_at: str = ""
    last_updated: str = ""
    # F1-C1 decay fields — defaults keep every pre-existing JSONL line
    # loading unchanged (no migration).
    last_reinforced: str = ""
    use_count: int = 0


def pattern_to_dict(card: PatternCard) -> dict:
    """Public serialiser for callers that persist outside this store."""
    return asdict(card)


def _safe_id(id_: str) -> str | None:
    """Apply the same allowlist as session/agent IDs (CWE-22 guard)."""
    return _safe_session_id_module.safe_session_id(id_)


@contextmanager
def _locked(path: Path, mode: str):
    """Open `path` under an exclusive POSIX flock with Windows fallback."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fh = path.open(mode, encoding="utf-8")
    try:
        if _HAS_FLOCK:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        yield fh
    finally:
        if _HAS_FLOCK:
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
        fh.close()


def _load_all() -> list[PatternCard]:
    """Load all valid PatternCards. Malformed lines are skipped."""
    if not PATTERNS_PATH.exists():
        return []
    cards: list[PatternCard] = []
    try:
        with PATTERNS_PATH.open(encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    cards.append(PatternCard(**data))
                except (json.JSONDecodeError, TypeError, ValueError):
                    continue
    except OSError:
        return []
    return cards


def _stamp_card(card: PatternCard) -> None:
    """Set created_at on first persist, last_updated on every persist."""
    now = datetime.now(timezone.utc).isoformat()
    if not card.created_at:
        card.created_at = now
    card.last_updated = now


def _write_all(cards: list[PatternCard]) -> None:
    """Atomically rewrite the entire JSONL. Locked for cross-process safety."""
    try:
        with _locked(PATTERNS_PATH, "w") as fh:
            for c in cards:
                fh.write(json.dumps(asdict(c)) + "\n")
    except OSError:
        return


def record_pattern(card: PatternCard) -> None:
    """Persist a PatternCard. Silently drops on unsafe/empty id.

    Re-recording an existing id REPLACES the prior entry (dedup-by-id).
    The file is rewritten in full under exclusive lock — fine for the
    expected scale (low thousands of cards). Larger scales should move
    to per-card files in v3.75.x.
    """
    if _safe_id(card.id) is None:
        return
    _stamp_card(card)
    others = [c for c in _load_all() if c.id != card.id]
    others.append(card)
    _write_all(others)


def reinforce_pattern(pattern_id: str) -> bool:
    """Real usage evidence re-touches the card: refresh last_reinforced,
    bump use_count. Returns True when the card existed. Decay fades
    untouched cards; reinforcement is the only counter-force."""
    safe = _safe_id(pattern_id)
    if safe is None:
        return False
    cards = _load_all()
    target = next((c for c in cards if c.id == safe), None)
    if target is None:
        return False
    target.last_reinforced = datetime.now(UTC).isoformat()
    target.use_count += 1
    _write_all(cards)
    return True


def _card_text(card: PatternCard) -> str:
    """Flatten searchable text from a card."""
    parts = [card.name, card.description] + (card.feature_keywords or [])
    return " ".join(str(p) for p in parts).lower()


def _matches_keywords(card: PatternCard, keywords: list[str]) -> bool:
    if not keywords:
        return True
    text = _card_text(card)
    return any(kw.lower() in text for kw in keywords)


def _matches_tags(card: PatternCard, tags: list[str]) -> bool:
    if not tags:
        return True
    stack = {t.lower() for t in (card.stack or [])}
    return any(tag.lower() in stack for tag in tags)


def query_patterns(
    *,
    keywords: list[str] | None = None,
    tags: list[str] | None = None,
    limit: int = 10,
) -> list[PatternCard]:
    """Return cards matching ALL filters, most recent first.

    Empty filters return all cards. Match semantics: case-insensitive
    substring on name/description/feature_keywords; exact tag match
    against `stack`. Both filters must hold (intersection).
    """
    cards = _load_all()
    kws = keywords or []
    tgs = tags or []
    matched = [
        c for c in cards
        if _matches_keywords(c, kws) and _matches_tags(c, tgs)
    ]
    # F1-C1 decay: stale cards fade from injection (never from disk).
    # Weight decays from the freshest touch; below the floor the card
    # is dropped from RESULTS only — the JSONL is untouched.
    from core.shared.decay import INJECTION_FLOOR, decay_enabled, decayed_weight

    if decay_enabled():
        weighted = [
            (decayed_weight(c.last_reinforced or c.last_updated or c.created_at), c)
            for c in matched
        ]
        weighted = [(w, c) for w, c in weighted if w >= INJECTION_FLOOR]
        weighted.sort(key=lambda pair: (pair[0], pair[1].last_updated), reverse=True)
        return [c for _w, c in weighted[:limit]]
    matched.sort(key=lambda c: c.last_updated or c.created_at, reverse=True)
    return matched[:limit]
