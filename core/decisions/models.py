"""Pydantic contract of the OpenRouter Decisions endpoint (JEV).

Request: ``{"model", "state", "questions": {key: {type, instructions,
criteria}}}``. Response: ``{"model", "answers": {key: {...}}, "usage"}``.
Criteria shape depends on the question type: ``choice`` maps option →
description (1..255 options), ``score`` lists 2..10 ordered levels,
``noul`` (yes/no probability) takes none.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

MAX_CHOICE_OPTIONS = 255
SCORE_LEVELS = (2, 10)

State = str | dict[str, Any] | list[Any]


class QuestionType(StrEnum):
    """The three typed question kinds the JEV answers."""

    NOUL = "noul"
    CHOICE = "choice"
    SCORE = "score"


class Question(BaseModel):
    """One typed question; criteria are validated against the type."""

    model_config = ConfigDict(extra="forbid")

    type: QuestionType
    instructions: str = Field(min_length=1)
    criteria: dict[str, str] | list[str] | None = None

    @model_validator(mode="after")
    def _criteria_match_type(self) -> Question:
        if self.type is QuestionType.NOUL:
            _require(self.criteria is None, "noul takes no criteria")
        elif self.type is QuestionType.CHOICE:
            ok = isinstance(self.criteria, dict)
            _require(ok, "choice needs a dict of options")
            size = len(self.criteria or {})
            _require(1 <= size <= MAX_CHOICE_OPTIONS, "choice needs 1..255 options")
        else:
            ok = isinstance(self.criteria, list)
            _require(ok, "score needs a list of levels")
            low, high = SCORE_LEVELS
            _require(low <= len(self.criteria or []) <= high, "score needs 2..10 levels")
        return self

    def to_payload(self) -> dict[str, Any]:
        """Wire form: ``criteria`` omitted when absent."""
        payload: dict[str, Any] = {"type": self.type.value, "instructions": self.instructions}
        if self.criteria is not None:
            payload["criteria"] = self.criteria
        return payload


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


class DecisionRequest(BaseModel):
    """One call: a state and every question asked about it."""

    model: str = Field(min_length=1)
    state: State
    questions: dict[str, Question] = Field(min_length=1)

    def to_payload(self) -> dict[str, Any]:
        """JSON body for ``POST /api/alpha/decisions``."""
        return {
            "model": self.model,
            "state": self.state,
            "questions": {k: q.to_payload() for k, q in self.questions.items()},
        }


class Answer(BaseModel):
    """One typed answer. Unknown fields are ignored (alpha endpoint)."""

    model_config = ConfigDict(extra="ignore")

    type: QuestionType | None = None
    choice: str | None = None
    # Real responses carry a fractional expected level (e.g. 2.85);
    # ``legend``/``probabilities`` are keyed "0".."n" (smoke 2026-09-23).
    score: float | str | None = None
    noul: float | None = Field(default=None, ge=0.0, le=1.0)
    probabilities: dict[str, float] | list[float] | None = None
    legend: Any = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class Usage(BaseModel):
    """Token accounting; ``cost`` is the provider-reported USD cost."""

    model_config = ConfigDict(extra="ignore")

    input_tokens: int = 0
    output_tokens: int = 0
    cost: float | None = None


class DecisionResponse(BaseModel):
    """The endpoint's answer map plus usage."""

    model_config = ConfigDict(extra="ignore")

    model: str = ""
    answers: dict[str, Answer]
    usage: Usage = Field(default_factory=Usage)
