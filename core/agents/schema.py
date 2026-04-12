"""Agent schema — Pydantic models for the 4-framework behavioral DNA.

Every ArkaOS agent has a complete behavioral profile composed of:
- DISC: How they act (observable behavior)
- Enneagram: Why they act (core motivation)
- Big Five/OCEAN: How much of each trait (continuous 0-100)
- MBTI: How they process information (cognitive functions)
"""

from enum import Enum
from typing import Literal, Optional
from pydantic import BaseModel, Field, model_validator


ModelTier = Literal["haiku", "sonnet", "opus"]


def tier_default_model(tier: int) -> ModelTier:
    """Return default Claude model for a given agent tier."""
    if tier == 0:
        return "opus"
    return "sonnet"


# --- DISC Framework ---

class DISCType(str, Enum):
    D = "D"  # Dominance
    I = "I"  # Influence
    S = "S"  # Steadiness
    C = "C"  # Conscientiousness


class DISCProfile(BaseModel):
    """DISC behavioral profile — how the agent acts."""
    primary: DISCType
    secondary: DISCType
    label: str = ""
    communication_style: str = ""
    under_pressure: str = ""
    motivator: str = ""

    @model_validator(mode="after")
    def primary_differs_from_secondary(self) -> "DISCProfile":
        if self.primary == self.secondary:
            raise ValueError("DISC primary and secondary must be different")
        if not self.label:
            labels = {"D": "Driver", "I": "Inspirer", "S": "Supporter", "C": "Analyst"}
            self.label = f"{labels[self.primary.value]}-{labels[self.secondary.value]}"
        return self


# --- Enneagram Framework ---

class EnneagramType(int, Enum):
    REFORMER = 1
    HELPER = 2
    ACHIEVER = 3
    INDIVIDUALIST = 4
    INVESTIGATOR = 5
    LOYALIST = 6
    ENTHUSIAST = 7
    CHALLENGER = 8
    PEACEMAKER = 9


class EnneagramCenter(str, Enum):
    BODY = "body"      # 8, 9, 1 — Anger/Instinct
    HEART = "heart"    # 2, 3, 4 — Shame/Feeling
    HEAD = "head"      # 5, 6, 7 — Fear/Thinking


class InstinctualSubtype(str, Enum):
    SP = "self-preservation"
    SO = "social"
    SX = "sexual"


ENNEAGRAM_CENTERS = {
    1: EnneagramCenter.BODY, 2: EnneagramCenter.HEART, 3: EnneagramCenter.HEART,
    4: EnneagramCenter.HEART, 5: EnneagramCenter.HEAD, 6: EnneagramCenter.HEAD,
    7: EnneagramCenter.HEAD, 8: EnneagramCenter.BODY, 9: EnneagramCenter.BODY,
}

ENNEAGRAM_NAMES = {
    1: "The Reformer", 2: "The Helper", 3: "The Achiever",
    4: "The Individualist", 5: "The Investigator", 6: "The Loyalist",
    7: "The Enthusiast", 8: "The Challenger", 9: "The Peacemaker",
}

# Growth and stress arrows
ENNEAGRAM_GROWTH = {1: 7, 2: 4, 3: 6, 4: 1, 5: 8, 6: 9, 7: 5, 8: 2, 9: 3}
ENNEAGRAM_STRESS = {1: 4, 2: 8, 3: 9, 4: 2, 5: 7, 6: 3, 7: 1, 8: 5, 9: 6}


class EnneagramProfile(BaseModel):
    """Enneagram motivational profile — why the agent acts."""
    type: EnneagramType
    wing: int = Field(ge=1, le=9)
    label: str = ""
    core_motivation: str = ""
    core_fear: str = ""
    center: EnneagramCenter = EnneagramCenter.HEAD
    growth_arrow: int = Field(default=0, ge=0, le=9)
    stress_arrow: int = Field(default=0, ge=0, le=9)
    subtype: InstinctualSubtype = InstinctualSubtype.SP

    @model_validator(mode="after")
    def validate_wing_and_arrows(self) -> "EnneagramProfile":
        t = self.type.value
        # Wing must be adjacent
        valid_wings = {t - 1 if t > 1 else 9, t + 1 if t < 9 else 1}
        if self.wing not in valid_wings:
            raise ValueError(f"Enneagram {t} wing must be {valid_wings}, got {self.wing}")
        # Auto-fill center and arrows
        self.center = ENNEAGRAM_CENTERS[t]
        if self.growth_arrow == 0:
            self.growth_arrow = ENNEAGRAM_GROWTH[t]
        if self.stress_arrow == 0:
            self.stress_arrow = ENNEAGRAM_STRESS[t]
        if not self.label:
            self.label = f"{t}w{self.wing} — {ENNEAGRAM_NAMES[t]}"
        return self


# --- Big Five / OCEAN Framework ---

class BigFiveProfile(BaseModel):
    """Big Five personality traits — continuous scale 0-100."""
    openness: int = Field(ge=0, le=100, description="Creativity, curiosity")
    conscientiousness: int = Field(ge=0, le=100, description="Organization, discipline")
    extraversion: int = Field(ge=0, le=100, description="Energy, sociability")
    agreeableness: int = Field(ge=0, le=100, description="Cooperation, empathy")
    neuroticism: int = Field(ge=0, le=100, description="Emotional reactivity")


# --- MBTI Framework ---

class MBTIType(str, Enum):
    INTJ = "INTJ"; INTP = "INTP"; ENTJ = "ENTJ"; ENTP = "ENTP"
    INFJ = "INFJ"; INFP = "INFP"; ENFJ = "ENFJ"; ENFP = "ENFP"
    ISTJ = "ISTJ"; ISFJ = "ISFJ"; ESTJ = "ESTJ"; ESFJ = "ESFJ"
    ISTP = "ISTP"; ISFP = "ISFP"; ESTP = "ESTP"; ESFP = "ESFP"


class CognitiveFunction(str, Enum):
    Ni = "Ni"  # Introverted Intuition
    Ne = "Ne"  # Extraverted Intuition
    Si = "Si"  # Introverted Sensing
    Se = "Se"  # Extraverted Sensing
    Ti = "Ti"  # Introverted Thinking
    Te = "Te"  # Extraverted Thinking
    Fi = "Fi"  # Introverted Feeling
    Fe = "Fe"  # Extraverted Feeling


# Cognitive function stacks per MBTI type
MBTI_STACKS: dict[str, list[str]] = {
    "INTJ": ["Ni", "Te", "Fi", "Se"], "INTP": ["Ti", "Ne", "Si", "Fe"],
    "ENTJ": ["Te", "Ni", "Se", "Fi"], "ENTP": ["Ne", "Ti", "Fe", "Si"],
    "INFJ": ["Ni", "Fe", "Ti", "Se"], "INFP": ["Fi", "Ne", "Si", "Te"],
    "ENFJ": ["Fe", "Ni", "Se", "Ti"], "ENFP": ["Ne", "Fi", "Te", "Si"],
    "ISTJ": ["Si", "Te", "Fi", "Ne"], "ISFJ": ["Si", "Fe", "Ti", "Ne"],
    "ESTJ": ["Te", "Si", "Ne", "Fi"], "ESFJ": ["Fe", "Si", "Ne", "Ti"],
    "ISTP": ["Ti", "Se", "Ni", "Fe"], "ISFP": ["Fi", "Se", "Ni", "Te"],
    "ESTP": ["Se", "Ti", "Fe", "Ni"], "ESFP": ["Se", "Fi", "Te", "Ni"],
}


class MBTIProfile(BaseModel):
    """MBTI cognitive profile — how the agent processes information."""
    type: MBTIType
    dominant: CognitiveFunction = CognitiveFunction.Ni
    auxiliary: CognitiveFunction = CognitiveFunction.Te
    tertiary: CognitiveFunction = CognitiveFunction.Fi
    inferior: CognitiveFunction = CognitiveFunction.Se

    @model_validator(mode="after")
    def auto_fill_stack(self) -> "MBTIProfile":
        stack = MBTI_STACKS[self.type.value]
        self.dominant = CognitiveFunction(stack[0])
        self.auxiliary = CognitiveFunction(stack[1])
        self.tertiary = CognitiveFunction(stack[2])
        self.inferior = CognitiveFunction(stack[3])
        return self


# --- Behavioral DNA (All 4 Frameworks Combined) ---

class BehavioralDNA(BaseModel):
    """Complete behavioral DNA — 4 frameworks combined."""
    disc: DISCProfile
    enneagram: EnneagramProfile
    big_five: BigFiveProfile
    mbti: MBTIProfile


# --- Mental Models ---

class MentalModels(BaseModel):
    """Mental models the agent uses for decision-making."""
    primary: list[str] = Field(default_factory=list, max_length=5)
    secondary: list[str] = Field(default_factory=list, max_length=5)


# --- Authority Matrix ---

class Authority(BaseModel):
    """What the agent is authorized to do."""
    veto: bool = False
    push_code: bool = False
    deploy: bool = False
    approve_architecture: bool = False
    approve_quality: bool = False
    approve_budget: bool = False
    block_release: bool = False
    block_delivery: bool = False
    orchestrate: bool = False
    delegates_to: list[str] = Field(default_factory=list)
    escalates_to: Optional[str] = None


# --- Communication Style ---

class Communication(BaseModel):
    """How the agent communicates."""
    language: str = "en"
    tone: str = "professional"
    vocabulary_level: str = "advanced"  # basic, intermediate, advanced, specialist
    preferred_format: str = "structured"
    avoid: list[str] = Field(default_factory=list)


# --- Expertise ---

class Expertise(BaseModel):
    """What the agent knows."""
    domains: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    depth: str = "expert"  # novice, intermediate, expert, master
    years_equivalent: int = 10


# --- The Complete Agent ---

class Agent(BaseModel):
    """Complete ArkaOS v2 agent definition.

    Every agent has:
    - Identity: id, name, role, department, tier
    - Behavioral DNA: DISC + Enneagram + Big Five + MBTI
    - Mental Models: primary + secondary decision frameworks
    - Authority: what they can approve, veto, or delegate
    - Expertise: domains, frameworks, depth
    - Communication: tone, format, language
    """
    id: str
    name: str
    role: str
    department: str
    tier: int = Field(ge=0, le=3)

    behavioral_dna: BehavioralDNA
    mental_models: MentalModels = Field(default_factory=MentalModels)
    authority: Authority = Field(default_factory=Authority)
    expertise: Expertise = Field(default_factory=Expertise)
    communication: Communication = Field(default_factory=Communication)

    memory_path: str = ""

    model: Optional[ModelTier] = Field(
        default=None,
        description="Claude model override for dispatch. Falls back to tier default when None.",
    )

    @model_validator(mode="after")
    def auto_fill_memory_path(self) -> "Agent":
        if not self.memory_path:
            self.memory_path = f"~/.claude/agent-memory/arka-{self.id}/MEMORY.md"
        return self

    def get_model(self) -> ModelTier:
        """Return the resolved Claude model, using tier default when unset."""
        return self.model or tier_default_model(self.tier)
