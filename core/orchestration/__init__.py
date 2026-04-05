"""Orchestration protocol — coordination patterns for multi-agent work."""

from core.orchestration.protocol import OrchestrationPattern, PhaseHandoff, OrchestrationPlan
from core.orchestration.patterns import PATTERNS

__all__ = ["OrchestrationPattern", "PhaseHandoff", "OrchestrationPlan", "PATTERNS"]
