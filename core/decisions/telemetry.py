"""Decision telemetry: one JSONL line per site per decision.

Writer (:func:`record`, never raises) appends to
``~/.arkaos/telemetry/decisions.jsonl`` (``ARKA_DECISIONS_TELEMETRY_PATH``
overrides) under an advisory lock, rotating through
``core.shared.telemetry_rotate``. API cost goes to the shared LLM cost
ledger with ``category="decision"``. :func:`summarise` is read-only and
mirrors ``core.runtime.mcp_telemetry`` periods and corrupt-line
tolerance.
"""

from __future__ import annotations

import contextlib
import hashlib
import hmac
import json
import os
import statistics
from collections import Counter, defaultdict
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import IO, Any

from core.decisions.models import State, Usage
from core.decisions.paths import cache_root, telemetry_path
from core.decisions.transport import Transport
from core.egress.audit import load_or_create_salt

try:
    import fcntl  # POSIX only

    _HAS_FLOCK = True
except ImportError:  # pragma: no cover — Windows
    _HAS_FLOCK = False

VALID_PERIODS: frozenset[str] = frozenset({"today", "week", "month", "all"})
_TOP_REASONS = 5
# Per-install salt for ``state_sha16`` (0600, directory 0700). Short
# prompts ("sim", "continua") are low-entropy: an unsalted digest in a
# readable log confirms a guess (security review 2026-09-23, finding 9).
SALT_NAME = "telemetry.salt"
_FILE_MODE = 0o600


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class DecisionRecord:
    """One site's decision for one turn."""

    session_id: str = ""
    site: str = ""
    mode: str = ""
    call_id: str = ""
    question_keys: list[str] = field(default_factory=list)
    answers: dict[str, dict[str, Any]] = field(default_factory=dict)
    confidence: float | None = None
    latency_ms: int | None = None
    input_tokens: int = 0
    cost_usd: float | None = None
    transport: str = ""
    model: str = ""
    fallback_used: bool = False
    reason: str = ""
    heuristic_result: Any = None
    jev_result: Any = None
    agree: bool | None = None
    acted_on: str = "heuristic"
    state_sha16: str = ""
    cache_hit: bool = False
    ts: str = field(default_factory=_now_iso)


def state_sha16(state: State) -> str:
    """Keyed 16-hex digest of a decision state (HMAC-SHA256, per-install salt).

    Correlates telemetry lines of the same state without being a
    confirm-a-guess oracle. An unreadable salt degrades to ``b""``
    (still no raw material, only the guess resistance is lost).
    """
    try:
        blob = json.dumps(state, sort_keys=True, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        blob = repr(state)
    salt = load_or_create_salt(cache_root() / SALT_NAME)
    payload = blob.encode("utf-8", errors="surrogatepass")
    return hmac.new(salt, payload, hashlib.sha256).hexdigest()[:16]


def _open_private(path: Path) -> IO[str]:
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, _FILE_MODE)
    with contextlib.suppress(AttributeError, OSError):
        os.fchmod(fd, _FILE_MODE)  # repair a file created looser earlier
    return os.fdopen(fd, "a", encoding="utf-8")


@contextmanager
def _locked_append(path: Path) -> Iterator[IO[str]]:
    path.parent.mkdir(parents=True, exist_ok=True)
    fh = _open_private(path)
    try:
        if _HAS_FLOCK:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        yield fh
    finally:
        if _HAS_FLOCK:
            with contextlib.suppress(OSError):
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        fh.close()


def record(rec: DecisionRecord) -> bool:
    """Append one line; False on any failure. Never raises."""
    try:
        target = telemetry_path()
        _rotate(target)
        line = json.dumps(asdict(rec), ensure_ascii=False, default=str)
        with _locked_append(target) as fh:
            fh.write(line + "\n")
    except Exception:
        return False
    return True


def _rotate(target: Path) -> None:
    with contextlib.suppress(Exception):
        from core.shared.telemetry_rotate import rotate_if_oversized

        rotate_if_oversized(target)


def call_cost_usd(transport: Transport, usage: Usage) -> float | None:
    """Provider-reported cost, else the static pricing of the REQUESTED id."""
    if usage.cost is not None:
        return float(usage.cost)
    from core.runtime.pricing import estimate_cost_usd

    return estimate_cost_usd(transport.model, usage.input_tokens, usage.output_tokens)


def record_call_cost(session_id: str, transport: Transport, usage: Usage) -> None:
    """Mirror one API call into the LLM cost ledger (``category=decision``)."""
    with contextlib.suppress(Exception):
        from core.runtime.llm_cost_telemetry import record_cost

        cost = call_cost_usd(transport, usage)
        record_cost(
            session_id, transport.name, transport.model,
            usage.input_tokens, usage.output_tokens, 0, cost,
            category="decision",
            pricing_status="" if cost is not None else "unknown-model",
        )


# --- aggregation ------------------------------------------------------------


@dataclass(frozen=True)
class SiteSummary:
    """Per-site view over a telemetry slice."""

    calls: int
    agreement_pct: float | None
    fallback_pct: float
    p50_latency_ms: int | None
    cost_usd: float
    acted_jev_pct: float


@dataclass(frozen=True)
class DecisionsSummary:
    """Aggregated decisions view for ``/arka decisions`` and ``/arka status``."""

    period: str
    calls: int
    by_site: dict[str, SiteSummary] = field(default_factory=dict)
    total_cost_usd: float = 0.0
    p50_latency_ms: int | None = None
    cache_hit_pct: float = 0.0
    top_fallback_reasons: list[tuple[str, int]] = field(default_factory=list)
    corrupt_line_count: int = 0


def summarise(
    period: str = "today", path: Path | None = None, now: datetime | None = None
) -> DecisionsSummary:
    """Summarise one period (today | week | month | all)."""
    if period not in VALID_PERIODS:
        raise ValueError(f"invalid period: {period!r}")
    entries, corrupt = _read_jsonl(path or telemetry_path(), _period_cutoff(period, now))
    return _build_summary(period, entries, corrupt)


def _period_cutoff(period: str, now: datetime | None = None) -> datetime | None:
    ref = now or datetime.now(UTC)
    if period == "today":
        return ref.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "week":
        return ref - timedelta(days=7)
    if period == "month":
        return ref - timedelta(days=30)
    return None


def _parse_ts(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _read_jsonl(src: Path, cutoff: datetime | None) -> tuple[list[dict[str, Any]], int]:
    entries: list[dict[str, Any]] = []
    corrupt = 0
    for line in _lines(src):
        entry = _parse_line(line)
        if entry is None:
            corrupt += 1
        elif cutoff is None or _within(entry, cutoff):
            entries.append(entry)
    return entries, corrupt


def _lines(src: Path) -> Iterator[str]:
    # Line-stream: the file grows on every decision.
    try:
        with src.open("r", encoding="utf-8", errors="replace") as fh:
            yield from (line for line in fh if line.strip())
    except OSError:
        return


def _parse_line(line: str) -> dict[str, Any] | None:
    try:
        entry = json.loads(line)
    except ValueError:
        return None
    return entry if isinstance(entry, dict) else None


def _within(entry: dict[str, Any], cutoff: datetime) -> bool:
    ts = _parse_ts(entry.get("ts"))
    return ts is not None and ts >= cutoff


def _pct(part: int, whole: int) -> float:
    return round(100.0 * part / whole, 1) if whole else 0.0


def _p50(values: list[int]) -> int | None:
    return int(statistics.median(values)) if values else None


def _latencies(entries: list[dict[str, Any]]) -> list[int]:
    out: list[int] = []
    for e in entries:
        value = e.get("latency_ms")
        if isinstance(value, int | float) and not e.get("cache_hit") and not e.get("fallback_used"):
            out.append(int(value))
    return out


def _cost(entries: list[dict[str, Any]]) -> float:
    return round(sum(float(e.get("cost_usd") or 0.0) for e in entries), 8)


def _site_summary(entries: list[dict[str, Any]]) -> SiteSummary:
    judged = [e for e in entries if isinstance(e.get("agree"), bool)]
    agreement = _pct(sum(1 for e in judged if e["agree"]), len(judged)) if judged else None
    return SiteSummary(
        calls=len(entries),
        agreement_pct=agreement,
        fallback_pct=_pct(sum(1 for e in entries if e.get("fallback_used")), len(entries)),
        p50_latency_ms=_p50(_latencies(entries)),
        cost_usd=_cost(entries),
        acted_jev_pct=_pct(sum(1 for e in entries if e.get("acted_on") == "jev"), len(entries)),
    )


def _build_summary(period: str, entries: list[dict[str, Any]], corrupt: int) -> DecisionsSummary:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in entries:
        grouped[str(entry.get("site") or "?")].append(entry)
    reasons = Counter(
        str(e.get("reason") or "?") for e in entries if e.get("fallback_used")
    )
    return DecisionsSummary(
        period=period,
        calls=len(entries),
        by_site={name: _site_summary(rows) for name, rows in sorted(grouped.items())},
        total_cost_usd=_cost(entries),
        p50_latency_ms=_p50(_latencies(entries)),
        cache_hit_pct=_pct(sum(1 for e in entries if e.get("cache_hit")), len(entries)),
        top_fallback_reasons=reasons.most_common(_TOP_REASONS),
        corrupt_line_count=corrupt,
    )
