"""DNA Fidelity Checker — PR5 Squad Intelligence Upgrade v3.76.0.

Compares agent output text against the `signature_markers` block declared
in the agent's YAML. Detects forbidden patterns (avoid_patterns) and missing
opening phrases, then records violations to telemetry.

Soft-warn mode for v1. Hard-block mode lands in a later PR once telemetry
shows the marker set is stable. Never raises — hook helpers must not break
the execution path.
"""

from __future__ import annotations

import json
import re
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import yaml

from core.shared import safe_session_id as _safe_session_id_module

try:
    import fcntl
    _HAS_FLOCK = True
except ImportError:
    _HAS_FLOCK = False


# ─── Module-level constants (monkeypatched by tests) ──────────────────────────

AGENT_YAML_SEARCH_DIRS: list[Path] = [
    Path(__file__).resolve().parent.parent.parent / "departments",
]
TELEMETRY_PATH: Path = Path.home() / ".arkaos" / "telemetry" / "dna-fidelity.jsonl"

_OPENING_WINDOW: int = 300


# ─── Dataclasses ──────────────────────────────────────────────────────────────

@dataclass
class SignatureMarkers:
    opening_phrases: list[str] = field(default_factory=list)
    typical_patterns: list[str] = field(default_factory=list)
    closing_style: str | None = None
    avoid_patterns: list[str] = field(default_factory=list)


@dataclass
class FidelityViolation:
    kind: str    # "forbidden_pattern" | "missing_opening"
    pattern: str
    span: str


# ─── Internal helpers ─────────────────────────────────────────────────────────

def _register_yaml_entry(index: dict[str, Path], path: Path, data: dict) -> None:
    """Add all lookup keys for one agent YAML into the shared index dict.

    Keys registered per file:
    - ``data["id"].lower()``                   e.g. ``tech-lead-paulo``
    - ``data["name"].lower()``                 e.g. ``paulo``
    - last hyphen-separated segment of id      e.g. ``paulo`` (deduped)
    """
    agent_id: str | None = data.get("id")
    if agent_id and isinstance(agent_id, str):
        key = agent_id.lower()
        index.setdefault(key, path)
        suffix = key.rsplit("-", 1)[-1]
        index.setdefault(suffix, path)
    name: str | None = data.get("name")
    if name and isinstance(name, str):
        index.setdefault(name.lower(), path)


@lru_cache(maxsize=1)
def _index_agents() -> dict[str, Path]:
    """Walk AGENT_YAML_SEARCH_DIRS once and build a name/id → path index.

    Three keys per YAML (id, name, id-suffix) allow callers to pass the
    short persona name (``paulo``) instead of the full id (``tech-lead-paulo``).
    """
    index: dict[str, Path] = {}
    for search_dir in AGENT_YAML_SEARCH_DIRS:
        if not search_dir.is_dir():
            continue
        for candidate in search_dir.rglob("*.yaml"):
            try:
                data = yaml.safe_load(candidate.read_text(encoding="utf-8"))
            except (OSError, yaml.YAMLError):
                continue
            if isinstance(data, dict):
                _register_yaml_entry(index, candidate, data)
    return index


def _yaml_path_for(agent_id: str) -> Path | None:
    """Resolve an agent persona name to its YAML path via the index.

    Returns None when agent_id fails the safe-session-id check (CWE-22
    hardening) or when no matching YAML is found.
    """
    if _safe_session_id_module.safe_session_id(agent_id) is None:
        return None
    return _index_agents().get(agent_id.lower())


@lru_cache(maxsize=128)
def _load_markers(agent_id: str) -> SignatureMarkers | None:
    """Load and parse signature_markers from an agent YAML. Cached per process."""
    path = _yaml_path_for(agent_id)
    if path is None:
        return None
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return None
    if not isinstance(raw, dict):
        return None
    block = raw.get("signature_markers")
    if not block or not isinstance(block, dict):
        return None
    return SignatureMarkers(
        opening_phrases=block.get("opening_phrases") or [],
        typical_patterns=block.get("typical_patterns") or [],
        closing_style=block.get("closing_style"),
        avoid_patterns=block.get("avoid_patterns") or [],
    )


# Chain cache invalidation so existing callers of `_load_markers.cache_clear()`
# also flush the agent index (both are file-system snapshots; stale index
# would return wrong paths after AGENT_YAML_SEARCH_DIRS is monkeypatched).
_original_load_markers_cache_clear = _load_markers.cache_clear


def _chained_cache_clear() -> None:
    _index_agents.cache_clear()
    _original_load_markers_cache_clear()


_load_markers.cache_clear = _chained_cache_clear  # type: ignore[method-assign]


def _search_avoid_patterns(
    output: str, patterns: list[str]
) -> list[FidelityViolation]:
    """Return one FidelityViolation per avoid_pattern that matches output."""
    violations: list[FidelityViolation] = []
    for pattern in patterns:
        match = re.search(pattern, output, re.IGNORECASE)
        if match:
            violations.append(
                FidelityViolation(
                    kind="forbidden_pattern",
                    pattern=pattern,
                    span=match.group(0),
                )
            )
    return violations


def _check_opening(
    output: str, opening_phrases: list[str]
) -> FidelityViolation | None:
    """Return a violation when none of the opening phrases appear near the top."""
    if not opening_phrases:
        return None
    window = output[:_OPENING_WINDOW]
    for phrase in opening_phrases:
        if re.search(re.escape(phrase), window, re.IGNORECASE):
            return None
    return FidelityViolation(
        kind="missing_opening",
        pattern=", ".join(opening_phrases),
        span=output[:80],
    )


@contextmanager
def _locked_append(path: Path):
    """Append to path under POSIX flock; Windows falls back to O_APPEND atomicity."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fh = path.open("a", encoding="utf-8")
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


# ─── Public API ───────────────────────────────────────────────────────────────

def check_fidelity(agent_id: str, output: str) -> list[FidelityViolation]:
    """Compare output against the agent's signature_markers.

    Returns a list of FidelityViolation. Empty list means clean pass or
    no markers defined for the agent.
    """
    markers = _load_markers(agent_id)
    if markers is None:
        return []
    violations: list[FidelityViolation] = []
    violations.extend(_search_avoid_patterns(output, markers.avoid_patterns))
    opening_violation = _check_opening(output, markers.opening_phrases)
    if opening_violation is not None:
        violations.append(opening_violation)
    return violations


def record_fidelity(
    agent_id: str,
    session_id: str,
    violations: list[FidelityViolation],
) -> None:
    """Append one JSONL telemetry record for this fidelity check.

    Silently drops when agent_id is unsafe or filesystem I/O fails.
    Zero violations are still recorded — absence of violations is signal too.
    """
    safe_id = _safe_session_id_module.safe_session_id(agent_id)
    if safe_id is None:
        return
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "agent_id": agent_id,
        "session_id": session_id,
        "violation_count": len(violations),
        "violations": [asdict(v) for v in violations],
    }
    try:
        with _locked_append(TELEMETRY_PATH) as fh:
            fh.write(json.dumps(record) + "\n")
    except OSError:
        return
