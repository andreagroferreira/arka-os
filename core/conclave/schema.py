"""Conclave schema — User profiles, advisors, and the board.

The Conclave creates a personalized advisory board by:
1. Profiling the user's behavioral DNA (DISC + Enneagram + Big5 + MBTI)
2. Matching 5 aligned advisors (same cognitive profile)
3. Matching 5 contrarian advisors (opposite profile)
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

from core.agents.schema import (
    DISCProfile, DISCType,
    EnneagramProfile, EnneagramType,
    BigFiveProfile,
    MBTIProfile, MBTIType,
    BehavioralDNA,
)


class AdvisorType(str, Enum):
    ALIGNED = "aligned"
    CONTRARIAN = "contrarian"


class MentalModel(BaseModel):
    """A codified mental model used by an advisor."""
    name: str
    description: str = ""
    question: str = ""  # The key question this model asks
    example: str = ""   # Example of applying this model


class Advisor(BaseModel):
    """A real-world person serving as an AI advisor.

    Each advisor has a behavioral DNA profile, mental models,
    and a specific communication style based on the real person.
    """
    id: str
    name: str
    title: str = ""                      # e.g., "Investor, Berkshire Hathaway"
    why_selected: str = ""               # Why this advisor was matched
    advisor_type: AdvisorType = AdvisorType.ALIGNED

    behavioral_dna: BehavioralDNA
    mental_models: list[MentalModel] = Field(default_factory=list)

    key_questions: list[str] = Field(default_factory=list)
    communication_style: str = ""
    decision_framework: str = ""
    sources: list[str] = Field(default_factory=list)  # Books, talks, etc.

    def match_score_to(self, user_dna: BehavioralDNA) -> float:
        """Calculate how well this advisor's DNA matches a user's DNA.

        Higher score = more similar (for aligned advisors).
        Lower score = more different (for contrarian advisors).
        """
        score = 0.0
        total = 4.0

        # DISC match (same primary = +1)
        if self.behavioral_dna.disc.primary == user_dna.disc.primary:
            score += 1.0
        elif self.behavioral_dna.disc.secondary == user_dna.disc.primary:
            score += 0.5

        # Enneagram match (same center = +1, same type = +1)
        if self.behavioral_dna.enneagram.center == user_dna.enneagram.center:
            score += 0.5
        if self.behavioral_dna.enneagram.type == user_dna.enneagram.type:
            score += 0.5

        # Big Five match (average distance, inverted)
        user_bf = user_dna.big_five
        adv_bf = self.behavioral_dna.big_five
        diffs = [
            abs(user_bf.openness - adv_bf.openness),
            abs(user_bf.conscientiousness - adv_bf.conscientiousness),
            abs(user_bf.extraversion - adv_bf.extraversion),
            abs(user_bf.agreeableness - adv_bf.agreeableness),
            abs(user_bf.neuroticism - adv_bf.neuroticism),
        ]
        avg_diff = sum(diffs) / len(diffs)
        score += 1.0 - (avg_diff / 100.0)

        # MBTI match (same dominant function = +1)
        if self.behavioral_dna.mbti.dominant == user_dna.mbti.dominant:
            score += 1.0
        elif self.behavioral_dna.mbti.auxiliary == user_dna.mbti.dominant:
            score += 0.5

        return round(score / total, 2)


class UserProfile(BaseModel):
    """The user's behavioral DNA profile for Conclave matching."""
    name: str = ""
    company: str = ""
    role: str = ""
    behavioral_dna: BehavioralDNA
    objectives: list[str] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)


class ConclaveBoard(BaseModel):
    """The complete Conclave board: 5 aligned + 5 contrarian advisors."""
    user: UserProfile
    aligned: list[Advisor] = Field(default_factory=list, max_length=5)
    contrarian: list[Advisor] = Field(default_factory=list, max_length=5)

    @property
    def all_advisors(self) -> list[Advisor]:
        return self.aligned + self.contrarian

    @property
    def size(self) -> int:
        return len(self.aligned) + len(self.contrarian)

    def get_advisor(self, advisor_id: str) -> Optional[Advisor]:
        for a in self.all_advisors:
            if a.id == advisor_id:
                return a
        return None

    def advisor_names(self) -> dict[str, list[str]]:
        return {
            "aligned": [a.name for a in self.aligned],
            "contrarian": [a.name for a in self.contrarian],
        }
