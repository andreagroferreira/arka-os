"""Persona schema — models for persona creation and cloning."""

from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel, Field


class PersonaDISC(BaseModel):
    primary: str = "C"
    secondary: str = "S"
    communication_style: str = ""
    under_pressure: str = ""
    motivator: str = ""


class PersonaEnneagram(BaseModel):
    type: int = 5
    wing: int = 6
    core_motivation: str = ""
    core_fear: str = ""
    subtype: str = "self-preservation"


class PersonaBigFive(BaseModel):
    openness: int = 50
    conscientiousness: int = 50
    extraversion: int = 50
    agreeableness: int = 50
    neuroticism: int = 50


class PersonaCommunication(BaseModel):
    tone: str = ""
    vocabulary_level: str = "specialist"
    preferred_format: str = ""
    avoid: list[str] = Field(default_factory=list)


class Persona(BaseModel):
    """A persona based on a real person or archetype."""
    id: str
    name: str
    title: str = ""                     # e.g., "Business Strategy", "Growth Marketing"
    tagline: str = ""                   # e.g., "The Natural Commander with emotional depth"
    source: str = ""                    # e.g., "Alex Hormozi", "Naval Ravikant"
    avatar_url: str = ""

    # Behavioral DNA
    disc: PersonaDISC = Field(default_factory=PersonaDISC)
    enneagram: PersonaEnneagram = Field(default_factory=PersonaEnneagram)
    big_five: PersonaBigFive = Field(default_factory=PersonaBigFive)
    mbti: str = "INTJ"

    # Knowledge
    mental_models: list[str] = Field(default_factory=list)
    expertise_domains: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    key_quotes: list[str] = Field(default_factory=list)

    # Communication
    communication: PersonaCommunication = Field(default_factory=PersonaCommunication)

    # Metadata
    created_at: str = ""
    updated_at: str = ""
    cloned_to_agents: list[str] = Field(default_factory=list)

    def to_agent_yaml(self, department: str = "strategy", tier: int = 2) -> dict:
        """Convert persona to an ArkaOS agent YAML structure."""
        agent_id = f"persona-{self.id}"
        return {
            "id": agent_id,
            "name": self.name,
            "role": self.title or f"{self.source} Persona",
            "department": department,
            "tier": tier,
            "behavioral_dna": {
                "disc": {
                    "primary": self.disc.primary,
                    "secondary": self.disc.secondary,
                    "communication_style": self.disc.communication_style,
                    "under_pressure": self.disc.under_pressure,
                    "motivator": self.disc.motivator,
                },
                "enneagram": {
                    "type": self.enneagram.type,
                    "wing": self.enneagram.wing,
                    "core_motivation": self.enneagram.core_motivation,
                    "core_fear": self.enneagram.core_fear,
                    "subtype": self.enneagram.subtype,
                },
                "big_five": {
                    "openness": self.big_five.openness,
                    "conscientiousness": self.big_five.conscientiousness,
                    "extraversion": self.big_five.extraversion,
                    "agreeableness": self.big_five.agreeableness,
                    "neuroticism": self.big_five.neuroticism,
                },
                "mbti": {"type": self.mbti},
            },
            "mental_models": {
                "primary": self.mental_models[:3],
                "secondary": self.mental_models[3:6],
            },
            "authority": {
                "veto": False,
                "approve_budget": False,
                "approve_architecture": False,
                "orchestrate": False,
                "delegates_to": [],
                "escalates_to": None,
            },
            "expertise": {
                "domains": self.expertise_domains[:5],
                "frameworks": self.frameworks[:5],
                "depth": "advanced",
                "years_equivalent": 10,
            },
            "communication": {
                "language": "en",
                "tone": self.communication.tone,
                "vocabulary_level": self.communication.vocabulary_level,
                "preferred_format": self.communication.preferred_format,
                "avoid": self.communication.avoid,
            },
        }
