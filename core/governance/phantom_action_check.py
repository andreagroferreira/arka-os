"""Phantom-action soft-block (prompt-surface P0 2026-07-08).

Response-side classifier. A "phantom action" is prose in the closing
assistant message claiming a completed EFFECT ("criei o ficheiro X",
"fiz commit", "I pushed the fix") in a turn that contains ZERO tool_use
blocks — narrated work without a tool call on record is the grammatical
form of delivery-theatre the ``evidence-flow`` rule bans. Pattern
sourced from the 2026-07-08 prompt audit (Obsidian: "Projects/
WizardingCode Internal/ArkaOS/Prompt Audit — system_prompts_leaks
2026-07-08", finding "anti-phantom-action"; corpus clone at
~/AIProjects/system_prompts_leaks).

Precision-first: only claims whose completion implies a tool effect are
flagged. Ambiguous verbs ("escrevi", "wrote", "corri", "ran") count only
when bound to a concrete effect object (file, commit, tests, module…) —
"escrevi um resumo abaixo" is response prose, not an effect claim.

Mirrors the contract of ``core.governance.closing_marker_check``:
soft-block, never raises on any input, hooks consume the result and log
warn-only telemetry before any promotion to hard enforcement.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

# Objects whose creation/modification implies a tool effect.
_EFFECT_OBJECT = (
    r"(?:\b(?:ficheiros?|files?|m[óo]dulos?|modules?|branch(?:es)?|commits?"
    r"|PRs?|pull.requests?|scripts?|testes?|tests?|suites?|classes?"
    r"|fun[çc][õo]es?|functions?|hooks?|configs?|pipelines?|migra[çc][õo]es?"
    r"|migrations?|packages?|releases?|tags?|documentos?|documents?"
    r"|p[áa]ginas?|pages?|componentes?|components?|endpoints?|comandos?"
    r"|commands?|builds?)\b|\.[a-z]{2,4}\b|`[^`]+`)"
)

# Verbs whose completion is unambiguous on its own (git/publish/install).
_STANDALONE_PT = (
    r"(?<!não )\b(instalei|publiquei|gravei|renomeei|implementei"
    r"|fiz\s+(?:o\s+|um\s+)?(?:commit|push|merge|deploy|release|rebase"
    r"|revert))\b"
)
_STANDALONE_EN = (
    r"\bI(?:'ve| have)?\s+(?:just\s+)?(committed|pushed|merged|published"
    r"|released|deployed|installed)\b"
)
# Ambiguous verbs — only a claim when bound to an effect object nearby.
_BOUND_PT = (
    r"(?<!não )\b(criei|escrevi|atualizei|editei|apaguei|removi|adicionei"
    r"|movi|apliquei|corri|executei)\b[^.\n!?]{0,60}?" + _EFFECT_OBJECT
)
_BOUND_EN = (
    r"\bI(?:'ve| have)?\s+(?:just\s+)?(created|wrote|updated|deleted"
    r"|added|moved|applied|renamed|ran|executed)\b[^.\n!?]{0,60}?"
    + _EFFECT_OBJECT
)
_PASSIVE = (
    r"\b(commit|push|merge|deploy|release|PR)\s+(feito|criado|efetuado"
    r"|realizado|concluído)\b"
)

_CLAIM_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (_STANDALONE_PT, _STANDALONE_EN, _BOUND_PT, _BOUND_EN, _PASSIVE)
)

_SUGGESTION_TEXT: str = (
    "Phantom action — the closing message narrates a completed effect but "
    "the turn contains no tool call. Prose in the past tense describing an "
    "action is only valid with the corresponding tool call on record "
    "(evidence-flow: gates pass on evidence, never on narration)."
)


@dataclass(frozen=True)
class PhantomActionResult:
    """Verdict of a phantom-action check. Immutable; safe to log as JSON."""

    passed: bool
    reason: str
    claims: list[str] = field(default_factory=list)
    suggestion: str | None = None


def find_action_claims(response_text: str) -> list[str]:
    """Return the distinct completed-effect claims found in the text."""
    text = response_text or ""
    hits: list[str] = []
    for pattern in _CLAIM_PATTERNS:
        for match in pattern.finditer(text):
            token = match.group(0).strip().lower()
            if token not in hits:
                hits.append(token)
    return hits


def count_turn_tool_uses(raw_transcript: str | None) -> int | None:
    """Count tool_use blocks in the final assistant turn of a transcript.

    The turn is every record after the last REAL user message (a user
    record whose content is not exclusively tool_result blocks). Returns
    None when no parseable records exist OR when no real user message is
    found — callers must fail open on None.
    """
    if not raw_transcript:
        return None
    records = _parse_jsonl(raw_transcript)
    if not records:
        return None
    start = _last_real_user_index(records)
    if start < 0:
        return None
    count = 0
    for record in records[start + 1 :]:
        if _record_role(record) != "assistant":
            continue
        count += _count_tool_use_blocks(record)
    return count


def check_phantom_actions(
    response_text: str, raw_transcript: str | None
) -> PhantomActionResult:
    """Classify whether the closing message narrates unbacked effects.

    Fail-open at every layer: an unparseable transcript skips the check,
    and any unexpected error returns a passing "check-error" result — a
    false PASS is telemetry noise, a false FAIL (or a crash) erodes
    trust in the warn channel.
    """
    try:
        claims = find_action_claims(response_text)
        if not claims:
            return PhantomActionResult(True, "no-claims")
        tool_uses = count_turn_tool_uses(raw_transcript)
        if tool_uses is None:
            return PhantomActionResult(True, "transcript-unparseable", claims)
        if tool_uses > 0:
            return PhantomActionResult(True, "tools-present", claims)
        return PhantomActionResult(
            False, "phantom-action", claims, _SUGGESTION_TEXT
        )
    except Exception:
        return PhantomActionResult(True, "check-error")


def _parse_jsonl(raw: str) -> list[dict]:
    records: list[dict] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            records.append(record)
    return records


def _record_message(record: dict) -> dict:
    message = record.get("message")
    return message if isinstance(message, dict) else {}


def _record_role(record: dict) -> str:
    role = record.get("role") or _record_message(record).get("role")
    return role if isinstance(role, str) else ""


def _record_content(record: dict) -> object:
    content = record.get("content")
    if content is None:
        content = _record_message(record).get("content")
    return content


def _last_real_user_index(records: list[dict]) -> int:
    for idx in range(len(records) - 1, -1, -1):
        if _record_role(records[idx]) != "user":
            continue
        content = _record_content(records[idx])
        if isinstance(content, str):
            return idx
        if isinstance(content, list):
            block_types = {
                block.get("type")
                for block in content
                if isinstance(block, dict)
            }
            if block_types - {"tool_result"}:
                return idx
    return -1


def _count_tool_use_blocks(record: dict) -> int:
    content = _record_content(record)
    if not isinstance(content, list):
        return 0
    return sum(
        1
        for block in content
        if isinstance(block, dict) and block.get("type") == "tool_use"
    )
