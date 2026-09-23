"""Prepare a decision state for egress to a third party.

Order: refuse secrets in every RAW string of the state (before JSON
escaping hides quoted values) → serialise (JSON for dict/list) →
normalise the operator home to ``<home>`` → with ``redact=True`` run
``core.egress.policy.evaluate`` (clients, secrets, home paths;
fail-closed) and keep the REDACTED text;
with ``redact=False`` (prompt/command only; diff and transcript are
always redacted) still refuse any secret and audit the send → cap at
:data:`MAX_STATE_CHARS`. A denial raises
``DecisionUnavailable("egress-denied:<kind>")`` so the caller falls back
to its heuristic.

The cap runs AFTER the checks (security review 2026-09-23): capping
first split an identifier or a secret straddling the cut, and the
half that survived ("Acme" of "Acme Industries", a key prefix) no
longer matched the redaction or secret patterns and left in clear.

Missing redaction config (no ``~/.arkaos/redaction-clients.json``, or an
explicit ``{"clients": []}``; a corrupt or unreadable file is NOT
missing — the operator has a list we cannot read): a state of class
``prompt`` or ``command`` still leaves, with secrets refused and the home
normalised, because it is the operator's own text sent with the
operator's own key; the override is written to the egress audit (no
audit, no egress) and noted once per session in the decisions
telemetry. Every other class (``diff``, ``transcript``, unknown) stays
fail-closed.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
from collections.abc import Iterable
from pathlib import Path

from core.decisions.client import DecisionUnavailable
from core.decisions.models import State
from core.decisions.paths import cache_root
from core.decisions.site import StateClass
from core.egress import audit
from core.egress.credentials import egress_secret_labels
from core.egress.policy import default_redaction_config_path, evaluate, payload_digest

MAX_STATE_CHARS = 96_000
# Raw text beyond this is dropped before the checks run (bounds their
# cost); the guard below keeps the cut from shipping a split token.
MAX_SCAN_CHARS = 1_000_000
_TAIL_GUARD = 4096  # longer than any identifier or secret the checks know
DESTINATION = "decisions:jev"
CONFIG_MISSING = "redaction-config-missing"
# Classes allowed to leave without a redaction config. Anything else —
# including a class this module has never heard of — is fail-closed.
DEGRADABLE: frozenset[str] = frozenset({"prompt", "command"})
# Most sensitive first: a mixed call is judged by its strictest site.
_STRICTNESS: tuple[str, ...] = ("transcript", "diff", "command", "prompt")
_HOME_TOKEN = "<home>"
_TRUNCATED = "…[truncated]"


def prepare_state(
    state: State,
    *,
    redact: bool,
    state_class: StateClass | str = "prompt",
    session_id: str = "",
) -> State:
    """The state as it may leave the machine, or DecisionUnavailable."""
    _refuse_leaf_secrets(state)
    structured = isinstance(state, dict | list)
    text, scan_cut = _bounded(_normalise_home(_serialise(state)))
    # redactClients:false is honoured for prompt/command only: a diff or a
    # transcript is always redacted, whatever the config (QG r1 m1).
    if redact or state_class not in DEGRADABLE:
        clean = _redacted(text, state_class, session_id)
    else:
        clean = _unredacted(text)
    if scan_cut and len(clean) <= MAX_STATE_CHARS:
        clean = clean[: max(0, len(clean) - _TAIL_GUARD)]
    return _restore(_cap(clean), structured)


def strictest_state_class(classes: Iterable[str]) -> str:
    """The most sensitive class among ``classes`` (unknown wins)."""
    seen = set(classes)
    unknown = seen - set(_STRICTNESS)
    if unknown:
        return sorted(unknown)[0]
    return next((c for c in _STRICTNESS if c in seen), "prompt")


def _serialise(state: State) -> str:
    if isinstance(state, str):
        return state
    try:
        return json.dumps(state, ensure_ascii=False, sort_keys=True, default=str)
    except (TypeError, ValueError) as exc:
        raise DecisionUnavailable("invalid-shape", "state not serialisable") from exc


def _normalise_home(text: str) -> str:
    home = str(Path.home()).rstrip("/")
    if home:
        # No boundary: the egress home-path check matches the bare prefix
        # case-insensitively, so anything it would deny is normalised.
        text = re.sub(re.escape(home), _HOME_TOKEN, text, flags=re.IGNORECASE)
    return text.replace("~/", f"{_HOME_TOKEN}/")


def _bounded(text: str) -> tuple[str, bool]:
    if len(text) <= MAX_SCAN_CHARS:
        return text, False
    return text[:MAX_SCAN_CHARS], True


def _cap(text: str) -> str:
    if len(text) <= MAX_STATE_CHARS:
        return text
    return text[: MAX_STATE_CHARS - len(_TRUNCATED)] + _TRUNCATED


def _redacted(text: str, state_class: str, session_id: str) -> str:
    # home= scopes the redaction config, allowlist and audit to the
    # CURRENT home (evaluated now, not at import) — same file in prod.
    decision = evaluate(text, DESTINATION, home=Path.home())
    if decision.allowed and decision.redacted_text is not None:
        return decision.redacted_text
    kinds = [f.kind for f in decision.findings]
    if kinds == [CONFIG_MISSING] and state_class in DEGRADABLE and _config_absent():
        return _degraded(text, state_class, session_id)
    raise DecisionUnavailable(f"egress-denied:{kinds[0] if kinds else 'denied'}")


def _config_absent() -> bool:
    """True only for NO file or an explicit ``{"clients": []}``.

    The loader reads a corrupt, unreadable or mis-shaped file as "no
    clients" too; for an operator who HAS a list, degrading then would
    ship their client names in clear. Those cases stay fail-closed.
    """
    path = default_redaction_config_path(Path.home())
    if not os.path.lexists(path):
        return True
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(data, dict) and data.get("clients") == []


def _leaves(state: object) -> Iterable[str]:
    """Every string a state would serialise: keys, values, ``str()`` of the rest.

    Iterative (a deep state cannot blow the stack) and bounded by
    :data:`MAX_SCAN_CHARS` in total, the same budget as the text scan.
    """
    stack: list[object] = [state]
    budget = MAX_SCAN_CHARS
    while stack and budget > 0:
        node = stack.pop()
        if isinstance(node, dict):
            stack.extend(node.values())
            stack.extend(node.keys())
            continue
        if isinstance(node, list | tuple):
            stack.extend(node)
            continue
        leaf = node if isinstance(node, str) else _leaf_text(node)
        budget -= len(leaf)
        yield leaf[:MAX_SCAN_CHARS]


def _leaf_text(node: object) -> str:
    if node is None or isinstance(node, bool | int | float):
        return ""
    try:
        return str(node)  # json.dumps(default=str) ships exactly this
    except Exception:
        return ""


def _refuse_leaf_secrets(state: object) -> None:
    """Scan the RAW strings, before ``json.dumps`` escapes them.

    Serialising first turned ``API_TOKEN="v"`` into ``API_TOKEN=\\"v\\"``,
    and the value patterns captured only the backslash: quoted
    credentials left on every path (QG PR2 r1 B1). The serialised text
    is still scanned afterwards, as the second layer.
    """
    if any(egress_secret_labels(leaf) for leaf in _leaves(state)):
        raise DecisionUnavailable("egress-denied:secret")


def _refuse_secrets(text: str) -> str:
    # One secret vocabulary with the policy (R-P1): vendor prefixes AND
    # context-marked credentials (export TOKEN=, Bearer, -p, user:pass@).
    if egress_secret_labels(text):
        raise DecisionUnavailable("egress-denied:secret")
    return text


def _unredacted(text: str) -> str:
    """``redactClients: false``: secrets refused, and still audited."""
    clean = _refuse_secrets(text)
    if not _audit_override(clean, "redact-disabled"):
        raise DecisionUnavailable("egress-denied:audit-unavailable")
    return clean


def _degraded(text: str, state_class: str, session_id: str) -> str:
    """Prompt/command egress without a client list: secrets still refused."""
    clean = _refuse_secrets(text)
    if not _audit_override(clean, f"{CONFIG_MISSING}:{state_class}"):
        raise DecisionUnavailable("egress-denied:audit-unavailable")
    _note_once(session_id)
    return clean


def _audit_override(text: str, override: str) -> bool:
    """Record the ALLOW the policy could not give; False = do not send."""
    home = Path.home()
    entry = {
        "allowed": True,
        "destination": DESTINATION,
        "payload_sha256": payload_digest(text),
        "redacted_sha256": payload_digest(text),
        "findings": [],
        "allowlisted": [],
        "override": override,
    }
    try:
        return audit.record(entry, audit.default_audit_path(home))
    except Exception:
        return False


def _note_once(session_id: str) -> None:
    """One telemetry line per session saying the client list is absent."""
    with contextlib.suppress(Exception):
        marker = _notice_marker(session_id)
        marker.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
        from core.decisions.telemetry import DecisionRecord, record

        record(DecisionRecord(
            session_id=session_id, site="egress-notice", mode="off",
            reason=CONFIG_MISSING, fallback_used=False, acted_on="heuristic",
        ))


def _notice_marker(session_id: str) -> Path:
    digest = hashlib.sha256(session_id.encode("utf-8", errors="surrogatepass")).hexdigest()
    return cache_root() / "notices" / f"{CONFIG_MISSING}-{digest[:32]}"


def _restore(text: str, structured: bool) -> State:
    if not structured:
        return text
    try:
        restored = json.loads(text)
    except ValueError:
        return text  # capped mid-document: ship the text, still meaningful
    return restored if isinstance(restored, dict | list) else text
