"""Behavior enforcement middleware.

Validates agent outputs against their stated behavioral DNA profile.
Detects "behavior drift" — when an agent acts outside their profile.

This is advisory only (WARN severity) — it doesn't block operations
but surfaces discrepancies for human review.
"""

import re
from dataclasses import dataclass
from typing import Any

from core.agents.dna_registry import DNARegistry, get_registry
from core.agents.schema import Agent, DISCType


@dataclass
class BehaviorDrift:
    """A detected deviation from an agent's DNA profile."""

    agent_id: str
    drift_type: str  # "tone", "vocabulary", "approach", "communication_style"
    expected: str
    detected: str
    severity: str = "WARN"  # WARN or INFO
    suggestion: str = ""


class BehaviorEnforcer:
    """Middleware to enforce behavioral DNA profiles on agent outputs."""

    def __init__(self, registry: DNARegistry | None = None):
        self.registry = registry or get_registry()

    def check_output(
        self,
        agent_id: str,
        output: str,
        context: str = "",
    ) -> list[BehaviorDrift]:
        """Check if an output deviates from the agent's DNA profile.

        Args:
            agent_id: ID of the agent that produced the output
            output: The text output to check
            context: Optional context about the interaction type

        Returns:
            List of detected behavior drifts
        """
        agent = self.registry.get(agent_id)
        if not agent:
            return []

        drifts: list[BehaviorDrift] = []

        drifts.extend(self._check_tone(agent, output))
        drifts.extend(self._check_vocabulary(agent, output))
        drifts.extend(self._check_communication_style(agent, output))
        drifts.extend(self._check_avoid_list(agent, output))

        return drifts

    def _check_tone(self, agent: Agent, output: str) -> list[BehaviorDrift]:
        """Check if output tone matches agent's stated DISC style."""
        drifts = []
        disc = agent.behavioral_dna.disc
        output_lower = output.lower()

        if disc.primary == DISCType.D:
            if not any(
                word in output_lower for word in ["need", "must", "require", "demand", "critical"]
            ):
                if len(output) > 100 and "?" not in output:
                    drifts.append(
                        BehaviorDrift(
                            agent_id=agent.id,
                            drift_type="tone",
                            expected="Direct, decisive, bottom-line first",
                            detected="Lacks direct command language",
                            suggestion="Lead with conclusions. Use 'must', 'need', 'critical'.",
                        )
                    )

        elif disc.primary == DISCType.I:
            if not any(
                word in output_lower
                for word in [
                    "great",
                    "amazing",
                    "exciting",
                    "fantastic",
                    "!" * 3 if "!!" in output else "",
                ]
            ):
                if len(output) > 200 and "!" not in output and "great" not in output_lower:
                    drifts.append(
                        BehaviorDrift(
                            agent_id=agent.id,
                            drift_type="tone",
                            expected="Enthusiastic, engaging, positive",
                            detected="Lacks enthusiasm markers",
                            suggestion="Show energy. Use 'great', 'amazing', 'exciting'.",
                        )
                    )

        elif disc.primary == DISCType.S:
            if any(word in output_lower for word in ["must", "immediately", "urgent", "asap"]):
                if output.count("must") > 2 or "immediately" in output:
                    drifts.append(
                        BehaviorDrift(
                            agent_id=agent.id,
                            drift_type="tone",
                            expected="Supportive, steady, patient",
                            detected="Overly urgent or demanding",
                            suggestion="Soften language. Avoid 'must', 'immediately', 'asap'.",
                        )
                    )

        elif disc.primary == DISCType.C:
            if not any(
                pattern in output
                for pattern in ["1.", "2.", "3.", "• ", "- ", "data:", "analysis:"]
            ):
                if len(output) > 150 and not re.search(r"\d+", output):
                    drifts.append(
                        BehaviorDrift(
                            agent_id=agent.id,
                            drift_type="tone",
                            expected="Precise, analytical, structured",
                            detected="Lacks structured format",
                            suggestion="Use numbered lists, bullet points, and data references.",
                        )
                    )

        return drifts

    def _check_vocabulary(self, agent: Agent, output: str) -> list[BehaviorDrift]:
        """Check if output uses appropriate vocabulary level."""
        drifts = []
        vocab_level = agent.communication.vocabulary_level
        output_lower = output.lower()

        if vocab_level == "specialist":
            tech_terms = ["architecture", "infrastructure", "optimization", "latency", "throughput"]
            if not any(term in output_lower for term in tech_terms):
                if len(output) > 150:
                    drifts.append(
                        BehaviorDrift(
                            agent_id=agent.id,
                            drift_type="vocabulary",
                            expected="Specialist-level technical vocabulary",
                            detected="Generic language detected",
                            suggestion="Use precise technical terms relevant to the domain.",
                        )
                    )

        return drifts

    def _check_communication_style(self, agent: Agent, output: str) -> list[BehaviorDrift]:
        """Check if output matches preferred communication format."""
        drifts = []
        preferred = agent.communication.preferred_format
        output_lower = output.lower()

        if "structured" in preferred or "diagrams" in preferred:
            if len(output) > 300 and not any(
                marker in output for marker in ["1.", "2.", "3.", "##", "###", "|"]
            ):
                drifts.append(
                    BehaviorDrift(
                        agent_id=agent.id,
                        drift_type="communication_style",
                        expected=f"Structured with {preferred}",
                        detected="Free-form text without structure",
                        suggestion="Add headers, numbered steps, or tabular format.",
                    )
                )

        if "code examples" in preferred:
            if "```" not in output and len(output) > 200:
                drifts.append(
                    BehaviorDrift(
                        agent_id=agent.id,
                        drift_type="communication_style",
                        expected="Includes code examples",
                        detected="No code blocks found",
                        suggestion="Add code examples to illustrate points.",
                    )
                )

        return drifts

    def _check_avoid_list(self, agent: Agent, output: str) -> list[BehaviorDrift]:
        """Check if output contains items from agent's avoid list."""
        drifts = []
        avoid_list = agent.communication.avoid
        output_lower = output.lower()

        for item in avoid_list:
            if item.lower() in output_lower:
                drifts.append(
                    BehaviorDrift(
                        agent_id=agent.id,
                        drift_type="tone",
                        expected=f"Avoid: {item}",
                        detected=f"Contains '{item}'",
                        severity="INFO",
                        suggestion=f"Avoid using '{item}' when communicating.",
                    )
                )

        return drifts

    def enforce_output(
        self,
        agent_id: str,
        output: str,
        context: str = "",
    ) -> tuple[str, list[BehaviorDrift]]:
        """Check output and return (possibly modified) output with drifts.

        This is advisory — it doesn't modify output but returns drifts
        for logging or review purposes.

        Args:
            agent_id: ID of the agent
            output: The output to check
            context: Optional interaction context

        Returns:
            Tuple of (output unchanged, list of drifts)
        """
        drifts = self.check_output(agent_id, output, context)
        return output, drifts


def check_agent_behavior(
    agent_id: str,
    output: str,
    context: str = "",
) -> list[BehaviorDrift]:
    """Convenience function to check an agent's output.

    Args:
        agent_id: ID of the agent
        output: Output text to check
        context: Optional context

    Returns:
        List of BehaviorDrift objects
    """
    enforcer = BehaviorEnforcer()
    return enforcer.check_output(agent_id, output, context)
