"""DISC Communication Adapter — adapt messages based on recipient's DISC profile.

When sending a message to another agent, this adapter modifies the message
tone and structure to match the recipient's preferred communication style.
"""

from core.agents.dna_registry import DNARegistry, get_registry
from core.agents.schema import Agent, DISCType


TONE_ADAPTERS = {
    DISCType.D: {
        "prefix": "",
        "suffix": "",
        "structure": "bullet_summary_first",
        "urgency_words": ["critical", "key", "essential", "must", "need"],
        "peace_words": [],
        "opening": "Direct.",
    },
    DISCType.I: {
        "prefix": "",
        "suffix": "",
        "structure": "friendly_narrative",
        "urgency_words": ["exciting", "great", "amazing", "fantastic"],
        "peace_words": [],
        "opening": "Hey!",
    },
    DISCType.S: {
        "prefix": "",
        "suffix": "",
        "structure": "supportive_explanation",
        "urgency_words": [],
        "peace_words": ["steady", "reliable", "together", "support", "help"],
        "opening": "",
    },
    DISCType.C: {
        "prefix": "",
        "suffix": "",
        "structure": "structured_data_first",
        "urgency_words": [],
        "peace_words": ["thorough", "precise", "accurate", "detailed"],
        "opening": "Analysis:",
    },
}


class DISCAdapter:
    """Adapt messages for recipients based on their DISC profile."""

    def __init__(self, registry: DNARegistry | None = None):
        self.registry = registry or get_registry()

    def adapt_message(
        self,
        message: str,
        sender_id: str,
        recipient_id: str,
    ) -> str:
        """Adapt a message for the recipient's DISC profile.

        Args:
            message: The original message to adapt
            sender_id: ID of the sending agent
            recipient_id: ID of the receiving agent

        Returns:
            Adapted message optimized for the recipient
        """
        sender = self.registry.get(sender_id)
        recipient = self.registry.get(recipient_id)

        if not sender or not recipient:
            return message

        recipient_disc = recipient.behavioral_dna.disc.primary
        adapter = TONE_ADAPTERS.get(recipient_disc)

        if not adapter:
            return message

        adapted = message

        if adapter["opening"]:
            if not adapted.startswith(adapter["opening"]):
                adapted = f"{adapter['opening']} {adapted}"

        return adapted

    def get_opening(self, recipient_id: str) -> str:
        """Get the appropriate opening for a recipient."""
        recipient = self.registry.get(recipient_id)
        if not recipient:
            return ""

        disc = recipient.behavioral_dna.disc.primary
        return TONE_ADAPTERS.get(disc, {}).get("opening", "")

    def get_structure_hint(self, recipient_id: str) -> str:
        """Get the recommended message structure for a recipient."""
        recipient = self.registry.get(recipient_id)
        if not recipient:
            return "standard"

        disc = recipient.behavioral_dna.disc.primary
        return TONE_ADAPTERS.get(disc, {}).get("structure", "standard")

    def adapt_for_disc(
        self,
        message: str,
        target_disc: DISCType,
    ) -> str:
        """Adapt a message directly for a DISC type.

        Args:
            message: Original message
            target_disc: Target DISC type

        Returns:
            Adapted message
        """
        adapter = TONE_ADAPTERS.get(target_disc, {})
        if not adapter:
            return message

        adapted = message
        if adapter["opening"]:
            if not adapted.startswith(adapter["opening"]):
                adapted = f"{adapter['opening']} {adapted}"

        return adapted


def adapt_message(
    message: str,
    sender_id: str,
    recipient_id: str,
) -> str:
    """Convenience function to adapt a message between two agents.

    Args:
        message: Original message
        sender_id: ID of the sender
        recipient_id: ID of the recipient

    Returns:
        Adapted message
    """
    adapter = DISCAdapter()
    return adapter.adapt_message(message, sender_id, recipient_id)
