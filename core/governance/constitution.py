"""Constitution schema and loader.

The Constitution defines governance rules at 4 enforcement levels:
- NON-NEGOTIABLE: Violations abort operations
- QUALITY_GATE: Mandatory pre-delivery review
- MUST: Mandatory, violations logged
- SHOULD: Best practices, encouraged
"""

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field


class Rule(BaseModel):
    """A single governance rule."""
    id: str
    rule: str
    enforcement: str = ""
    pattern: str = ""
    metric: str = ""


class QualityAgent(BaseModel):
    """A quality gate agent."""
    id: str
    role: str = ""
    scope: str = ""
    authority: str = ""
    veto_power: bool = False


class QualityGateConfig(BaseModel):
    """Quality Gate configuration."""
    description: str = ""
    agents: dict = Field(default_factory=dict)
    process: list[str] = Field(default_factory=list)


class EnforcementLevel(BaseModel):
    """A group of rules at the same enforcement level."""
    description: str = ""
    rules: list[Rule] = Field(default_factory=list)


class TierConfig(BaseModel):
    """Configuration for an agent tier."""
    name: str
    description: str = ""
    max_agents: int = 0
    authorities: list[str] = Field(default_factory=list)


class ConflictRule(BaseModel):
    """A conflict resolution pattern."""
    pattern: str
    resolution: str


class ConflictResolution(BaseModel):
    """Conflict resolution rules."""
    description: str = ""
    rules: list[ConflictRule] = Field(default_factory=list)
    escalation: dict[str, str] = Field(default_factory=dict)


class Constitution(BaseModel):
    """The ArkaOS Constitution — governance for the entire system."""
    version: str
    name: str
    description: str = ""

    enforcement_levels: dict = Field(default_factory=dict)
    tier_hierarchy: dict = Field(default_factory=dict)
    conflict_resolution: ConflictResolution = Field(default_factory=ConflictResolution)
    amendments: dict = Field(default_factory=dict)

    def get_non_negotiable_rules(self) -> list[Rule]:
        """Get all NON-NEGOTIABLE rules."""
        nn = self.enforcement_levels.get("non_negotiable", {})
        raw_rules = nn.get("rules", [])
        return [Rule.model_validate(r) for r in raw_rules]

    def get_must_rules(self) -> list[Rule]:
        """Get all MUST rules."""
        must = self.enforcement_levels.get("must", {})
        raw_rules = must.get("rules", [])
        return [Rule.model_validate(r) for r in raw_rules]

    def get_should_rules(self) -> list[Rule]:
        """Get all SHOULD rules."""
        should = self.enforcement_levels.get("should", {})
        raw_rules = should.get("rules", [])
        return [Rule.model_validate(r) for r in raw_rules]

    def get_rule_ids(self) -> list[str]:
        """Get all rule IDs across all enforcement levels."""
        ids = []
        for rules in [self.get_non_negotiable_rules(), self.get_must_rules(), self.get_should_rules()]:
            ids.extend(r.id for r in rules)
        return ids

    def is_rule_non_negotiable(self, rule_id: str) -> bool:
        """Check if a rule is NON-NEGOTIABLE."""
        return rule_id in [r.id for r in self.get_non_negotiable_rules()]

    def compress_for_context(self) -> str:
        """Compress Constitution to a compact string for context injection.

        This creates the L0 context layer that Synapse injects into every prompt.
        """
        nn_ids = [r.id for r in self.get_non_negotiable_rules()]
        must_ids = [r.id for r in self.get_must_rules()]

        qg = self.enforcement_levels.get("quality_gate", {})
        qg_agents = qg.get("agents", {})
        orchestrator = qg_agents.get("orchestrator", {})
        reviewers = qg_agents.get("reviewers", [])

        qg_parts = []
        if orchestrator:
            qg_parts.append(orchestrator.get("id", ""))
        for r in reviewers:
            qg_parts.append(r.get("id", ""))

        parts = [
            f"[Constitution] NON-NEGOTIABLE: {', '.join(nn_ids)}",
            f"QUALITY-GATE: {', '.join(qg_parts)}",
            f"MUST: {', '.join(must_ids)}",
        ]
        return " | ".join(parts)


def load_constitution(path: str | Path) -> Constitution:
    """Load Constitution from YAML file.

    Args:
        path: Path to constitution.yaml

    Returns:
        Validated Constitution instance.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Constitution file not found: {path}")

    with open(path) as f:
        data = yaml.safe_load(f)

    return Constitution.model_validate(data)
