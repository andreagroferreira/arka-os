"""Correction-signal detector for ArkaOS hybrid learning (PR16 v2.38.0).

Implements the `hybrid-learning` NON-NEGOTIABLE rule from PR10
constitution. The detector scans a user message for signs that the user
is establishing a permanent rule (rather than a one-off comment), and
classifies the signal so the orchestrator can:

  * IMPLICIT  — low-leverage correction, auto-save with low confidence
  * EXPLICIT  — high-leverage correction, surface Marta confirmation
                question before saving

The detector is heuristic (regex + magnitude). It never writes memory
files itself — it only emits a structured verdict the Stop hook records
and the orchestrator acts upon.

Conclave 2026-05-13 brainstorm rule:
  * Implicit auto-detect with confidence scoring (default)
  * Explicit Marta-led confirmation for high-leverage rules
  * Marta is the owner of the learning loop
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Literal

CorrectionMode = Literal["explicit", "implicit", "none"]
CorrectionKind = Literal["rule", "preference", "one-off", "none"]

# Absolute-language cues — strong signal that user is asserting a rule.
_ABSOLUTE_CUES: tuple[re.Pattern, ...] = tuple(
    re.compile(p, re.IGNORECASE) for p in [
        r"\bsempre\b",
        r"\bnunca\b",
        r"\btodas?\s+as?\s+vezes\b",
        r"\bem\s+todos?\s+os?\s+casos\b",
        r"\bsem\s+exce[cç][oõ]es\b",
        r"\bno\s+exceptions\b",
        r"\balways\b",
        r"\bnever\b",
        r"\bevery\s+time\b",
        r"\bin\s+all\s+cases\b",
        r"\bNON-NEGOTIABLE\b",
        r"\bn[aã]o[\s-]+negoci[aá]vel\b",
        r"\bmandatory\b",
        r"\bobrigat[oó]rio\b",
        r"\bregra\s+permanente\b",
        r"\bpermanent\s+rule\b",
        r"\bguarda\s+isto\b",
        r"\bsave\s+this\b",
        r"\bencode\s+this\b",
        r"\benforce\s+this\b",
        r"\b(daqui\s+)?para\s+a\s+frente\b",
        r"\bgoing\s+forward\b",
    ]
)

# Correction verbs — "stop doing X" / "I want Y instead".
_CORRECTION_VERBS: tuple[re.Pattern, ...] = tuple(
    re.compile(p, re.IGNORECASE) for p in [
        r"\bn[aã]o\s+(quero|fa[cç]as?|continues?)\b",
        r"\bp[aá]ra\s+de\b",
        r"\bdeixa\s+de\b",
        r"\bevita\b",
        r"\bstop\s+(doing|saying)\b",
        r"\bdon[' ]t\s+(do|say|use|assume)\b",
        r"\bavoid\b",
        r"\bem\s+vez\s+de\b",
        r"\binstead\s+of\b",
        r"\bn[aã]o\s+é\s+(isso|assim)\b",
        r"\bwrong\b",
        r"\bnot\s+like\s+that\b",
    ]
)

# Self-affirmation cues — "I prefer X" / "what I want is".
_PREFERENCE_CUES: tuple[re.Pattern, ...] = tuple(
    re.compile(p, re.IGNORECASE) for p in [
        r"\b(eu\s+)?prefiro\b",
        r"\b(eu\s+)?gosto\s+(de|mais)\b",
        r"\bI\s+prefer\b",
        r"\bI\s+like\b",
        r"\bI\s+want\b",
        r"\bo\s+que\s+(eu\s+)?quero\s+é\b",
        r"\bwhat\s+I\s+want\s+is\b",
    ]
)

# Magnitude thresholds.
_MIN_CORRECTION_CHARS = 60
_HIGH_LEVERAGE_CHARS = 200


@dataclass
class CorrectionSignal:
    """Structured verdict on a potential correction message."""

    mode: CorrectionMode
    kind: CorrectionKind
    confidence: float  # 0.0 .. 1.0
    is_high_leverage: bool
    signals: list[str] = field(default_factory=list)
    suggested_memory_type: str = ""  # "feedback" | "preference" | ""
    message_length: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    def should_save(self) -> bool:
        """Whether the orchestrator should write a memory file."""
        return self.confidence >= 0.5

    def should_confirm(self) -> bool:
        """Whether Marta should ask the user to confirm before saving."""
        return self.is_high_leverage or self.confidence >= 0.85


def detect_correction_signal(text: str) -> CorrectionSignal:
    """Inspect *text* and return a CorrectionSignal verdict.

    Confidence scale (cumulative across signal types, capped at 1.0):
      0.0   no signal
      0.4   short message with correction verb
      0.55  absolute-language cue present (sempre/nunca/etc.)
      0.7   correction verb + absolute-language cue
      0.85  long message with multiple cue types
      1.0   explicit "guarda isto / save this / encode this"
    """
    stripped = (text or "").strip()
    if not stripped:
        return CorrectionSignal(
            mode="none", kind="none", confidence=0.0, is_high_leverage=False
        )

    signals: list[str] = []
    confidence = 0.0
    kind: CorrectionKind = "none"

    # Absolute-language cues (strong rule signal).
    abs_hits = [p.pattern for p in _ABSOLUTE_CUES if p.search(stripped)]
    if abs_hits:
        signals.append("absolute-language")
        confidence = max(confidence, 0.55)
        kind = "rule"

    # Correction verbs.
    correction_hits = [p.pattern for p in _CORRECTION_VERBS if p.search(stripped)]
    if correction_hits:
        signals.append("correction-verb")
        confidence = max(confidence, 0.4)
        if kind == "none":
            kind = "rule"

    # Preference cues — softer signal, "preference" not "rule".
    pref_hits = [p.pattern for p in _PREFERENCE_CUES if p.search(stripped)]
    if pref_hits:
        signals.append("preference-cue")
        confidence = max(confidence, 0.35)
        if kind == "none":
            kind = "preference"

    # Combination boosts confidence.
    if abs_hits and correction_hits:
        signals.append("rule-plus-correction-combo")
        confidence = max(confidence, 0.7)

    # Explicit save-this verbs are 1.0.
    save_now = re.search(
        r"\b(guarda\s+isto|save\s+this|encode\s+this|enforce\s+this|"
        r"regra\s+permanente|permanent\s+rule|going\s+forward)\b",
        stripped, re.IGNORECASE,
    )
    if save_now:
        signals.append("explicit-save-verb")
        confidence = 1.0
        kind = "rule"

    # Magnitude boost — long substantive corrections are more likely rules.
    msg_len = len(stripped)
    is_high_leverage = False
    if msg_len >= _HIGH_LEVERAGE_CHARS and (abs_hits or correction_hits):
        signals.append("high-magnitude")
        confidence = max(confidence, 0.85)
        is_high_leverage = True

    if msg_len < _MIN_CORRECTION_CHARS and not save_now and not abs_hits:
        # Too short to be a substantive rule, unless it explicitly says "save"
        # OR contains an absolute-language cue (e.g. "always", "never",
        # "NON-NEGOTIABLE"). Those are intentional declarative rules even
        # when phrased compactly — capping their confidence would silence
        # the user's clear intent.
        confidence = min(confidence, 0.4)

    # NON-NEGOTIABLE keyword always escalates to high-leverage.
    if re.search(r"\bNON-NEGOTIABLE\b|\bn[aã]o[\s-]+negoci[aá]vel\b", stripped, re.IGNORECASE):
        is_high_leverage = True

    # Mode selection.
    if confidence < 0.35:
        mode: CorrectionMode = "none"
    elif is_high_leverage or confidence >= 0.85:
        mode = "explicit"
    else:
        mode = "implicit"

    suggested = ""
    if kind == "rule" and confidence >= 0.5:
        suggested = "feedback"
    elif kind == "preference" and confidence >= 0.35:
        suggested = "preference"

    return CorrectionSignal(
        mode=mode,
        kind=kind,
        confidence=round(confidence, 2),
        is_high_leverage=is_high_leverage,
        signals=signals,
        suggested_memory_type=suggested,
        message_length=msg_len,
    )
