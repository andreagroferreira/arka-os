"""Agent DNA Registry — query and filter agents by behavioral DNA traits.

Provides:
- Load all agents from departments/*/agents/*.yaml
- Query agents by DISC type, Enneagram, Big Five traits, MBTI
- Find compatible agents for collaboration
- Validate DNA profile completeness
"""

from pathlib import Path
from typing import Iterator

from core.agents.loader import load_all_agents
from core.agents.schema import (
    Agent,
    BehavioralDNA,
    DISCType,
    EnneagramType,
    BigFiveProfile,
    MBTIType,
)


class DNARegistry:
    """Registry for querying agents by behavioral DNA traits."""

    def __init__(self, base_dir: str | Path | None = None):
        """Initialize registry.

        Args:
            base_dir: Root of departments tree. Defaults to repo root.
        """
        if base_dir is None:
            base_dir = Path(__file__).parent.parent.parent / "departments"
        self.base_dir = Path(base_dir)
        self._agents: list[Agent] = []
        self._by_id: dict[str, Agent] = {}
        self._load_agents()

    def _load_agents(self) -> None:
        """Load all agents from YAML files."""
        self._agents = load_all_agents(self.base_dir)
        self._by_id = {a.id: a for a in self._agents}

    def reload(self) -> None:
        """Reload all agents from disk."""
        self._load_agents()

    def get(self, agent_id: str) -> Agent | None:
        """Get agent by ID."""
        return self._by_id.get(agent_id)

    def all(self) -> list[Agent]:
        """Get all loaded agents."""
        return self._agents.copy()

    def by_disc(self, primary: DISCType) -> list[Agent]:
        """Find agents by DISC primary type."""
        return [a for a in self._agents if a.behavioral_dna.disc.primary == primary]

    def by_enneagram(self, type_: EnneagramType) -> list[Agent]:
        """Find agents by Enneagram type."""
        return [a for a in self._agents if a.behavioral_dna.enneagram.type == type_]

    def by_mbti(self, type_: MBTIType) -> list[Agent]:
        """Find agents by MBTI type."""
        return [a for a in self._agents if a.behavioral_dna.mbti.type == type_]

    def by_department(self, department: str) -> list[Agent]:
        """Find agents by department."""
        return [a for a in self._agents if a.department == department]

    def by_tier(self, tier: int) -> list[Agent]:
        """Find agents by tier (0-3)."""
        return [a for a in self._agents if a.tier == tier]

    def by_big_five(
        self,
        openness_min: int = 0,
        conscientiousness_min: int = 0,
        extraversion_min: int = 0,
        agreeableness_min: int = 0,
        neuroticism_max: int = 100,
    ) -> list[Agent]:
        """Find agents matching Big Five thresholds."""
        results = []
        for a in self._agents:
            bf = a.behavioral_dna.big_five
            if (
                bf.openness >= openness_min
                and bf.conscientiousness >= conscientiousness_min
                and bf.extraversion >= extraversion_min
                and bf.agreeableness >= agreeableness_min
                and bf.neuroticism <= neuroticism_max
            ):
                results.append(a)
        return results

    def compatible_with(self, agent_id: str) -> list[Agent]:
        """Find agents compatible for collaboration.

        Compatibility is based on complementary DISC profiles
        and similar communication styles.
        """
        agent = self.get(agent_id)
        if not agent:
            return []

        disc = agent.behavioral_dna.disc
        disc_map = {
            DISCType.D: {DISCType.I, DISCType.S},  # D works with I and S
            DISCType.I: {DISCType.D, DISCType.S},  # I works with D and S
            DISCType.S: {DISCType.D, DISCType.I, DISCType.C},  # S works with most
            DISCType.C: {DISCType.S, DISCType.C},  # C works with S and C
        }
        compatible_types = disc_map.get(disc.primary, set())

        return [
            a
            for a in self._agents
            if a.id != agent_id and a.behavioral_dna.disc.primary in compatible_types
        ]

    def contrasting_disc(self, agent_id: str) -> list[Agent]:
        """Find agents with contrasting DISC profiles.

        Useful for getting different perspectives.
        """
        agent = self.get(agent_id)
        if not agent:
            return []

        primary = agent.behavioral_dna.disc.primary
        opposites = {
            DISCType.D: {DISCType.S, DISCType.C},
            DISCType.I: {DISCType.C},
            DISCType.S: {DISCType.D},
            DISCType.C: {DISCType.D, DISCType.I},
        }
        opposite_types = opposites.get(primary, set())

        return [
            a
            for a in self._agents
            if a.id != agent_id and a.behavioral_dna.disc.primary in opposite_types
        ]

    def validate_dna_completeness(self) -> dict[str, list[str]]:
        """Validate that all agents have complete DNA profiles.

        Returns:
            Dict mapping agent_id to list of missing fields
        """
        missing: dict[str, list[str]] = {}
        for agent in self._agents:
            issues = []
            dna = agent.behavioral_dna

            if not dna.disc.primary:
                issues.append("disc.primary")
            if not dna.enneagram.type:
                issues.append("enneagram.type")
            if not dna.big_five.openness:
                issues.append("big_five.openness")
            if not dna.mbti.type:
                issues.append("mbti.type")

            if issues:
                missing[agent.id] = issues

        return missing

    def get_communication_style(self, agent_id: str) -> str | None:
        """Get the communication style hint for an agent."""
        agent = self.get(agent_id)
        if not agent:
            return None
        return agent.communication.tone

    def get_tone_for_recipient(self, sender_id: str, recipient_id: str) -> str:
        """Get adapted tone when sender communicates with recipient.

        Args:
            sender_id: The sender's agent ID
            recipient_id: The recipient's agent ID

        Returns:
            Communication tone adapted for the recipient
        """
        sender = self.get(sender_id)
        recipient = self.get(recipient_id)
        if not sender or not recipient:
            return "professional"

        sender_disc = sender.behavioral_dna.disc.primary
        recipient_disc = recipient.behavioral_dna.disc.primary

        tone_map = {
            (DISCType.D, DISCType.D): "direct and decisive",
            (DISCType.D, DISCType.I): "direct but enthusiastic",
            (DISCType.D, DISCType.S): "direct and supportive",
            (DISCType.D, DISCType.C): "direct and precise",
            (DISCType.I, DISCType.D): "enthusiastic but direct",
            (DISCType.I, DISCType.I): "enthusiastic and collaborative",
            (DISCType.I, DISCType.S): "enthusiastic and warm",
            (DISCType.I, DISCType.C): "enthusiastic but detailed",
            (DISCType.S, DISCType.D): "supportive but direct",
            (DISCType.S, DISCType.I): "warm and collaborative",
            (DISCType.S, DISCType.S): "warm and steady",
            (DISCType.S, DISCType.C): "supportive and precise",
            (DISCType.C, DISCType.D): "precise and direct",
            (DISCType.C, DISCType.I): "precise but friendly",
            (DISCType.C, DISCType.S): "precise and supportive",
            (DISCType.C, DISCType.C): "precise and thorough",
        }

        return tone_map.get((sender_disc, recipient_disc), "professional")


_REGISTRY: DNARegistry | None = None


def get_registry() -> DNARegistry:
    """Get the global DNA registry (singleton)."""
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = DNARegistry()
    return _REGISTRY


def reload_registry() -> DNARegistry:
    """Reload and return the global registry."""
    global _REGISTRY
    _REGISTRY = DNARegistry()
    return _REGISTRY
