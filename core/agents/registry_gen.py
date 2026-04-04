"""Generate agents-registry.json from all agent YAML files.

Scans departments/*/agents/*.yaml and produces a machine-readable
registry with all agent metadata including behavioral DNA.
"""

import json
from datetime import datetime
from pathlib import Path

from core.agents.loader import load_agent


def generate_registry(departments_dir: str | Path, output_path: str | Path) -> dict:
    """Generate agents-registry.json from YAML agent files.

    Args:
        departments_dir: Path to departments/ directory.
        output_path: Where to write the JSON registry.

    Returns:
        The registry dict.
    """
    departments_dir = Path(departments_dir)
    output_path = Path(output_path)

    agents = []
    errors = []

    for yaml_file in sorted(departments_dir.glob("*/agents/*.yaml")):
        try:
            agent = load_agent(yaml_file)
            entry = {
                "id": agent.id,
                "name": agent.name,
                "role": agent.role,
                "department": agent.department,
                "tier": agent.tier,
                "disc": {
                    "primary": agent.behavioral_dna.disc.primary.value,
                    "secondary": agent.behavioral_dna.disc.secondary.value,
                    "label": agent.behavioral_dna.disc.label,
                },
                "enneagram": {
                    "type": agent.behavioral_dna.enneagram.type.value,
                    "wing": agent.behavioral_dna.enneagram.wing,
                    "label": agent.behavioral_dna.enneagram.label,
                },
                "big_five": {
                    "O": agent.behavioral_dna.big_five.openness,
                    "C": agent.behavioral_dna.big_five.conscientiousness,
                    "E": agent.behavioral_dna.big_five.extraversion,
                    "A": agent.behavioral_dna.big_five.agreeableness,
                    "N": agent.behavioral_dna.big_five.neuroticism,
                },
                "mbti": agent.behavioral_dna.mbti.type.value,
                "authority": {
                    k: v for k, v in agent.authority.model_dump().items()
                    if v and v != [] and k not in ("delegates_to", "escalates_to")
                },
                "expertise_domains": agent.expertise.domains[:5],
                "frameworks": agent.expertise.frameworks[:5],
                "file": str(yaml_file.relative_to(departments_dir.parent)),
                "memory_path": agent.memory_path,
            }
            agents.append(entry)
        except Exception as e:
            errors.append(f"{yaml_file.name}: {e}")

    # Build tier summary
    tier_counts = {}
    for a in agents:
        tier_counts[a["tier"]] = tier_counts.get(a["tier"], 0) + 1

    # Build department summary
    dept_counts = {}
    for a in agents:
        dept_counts[a["department"]] = dept_counts.get(a["department"], 0) + 1

    # Build DISC distribution
    disc_counts = {}
    for a in agents:
        p = a["disc"]["primary"]
        disc_counts[p] = disc_counts.get(p, 0) + 1

    registry = {
        "_meta": {
            "version": "2.0.0",
            "generated": datetime.now().isoformat(),
            "total_agents": len(agents),
            "generator": "core/agents/registry_gen.py",
            "tiers": tier_counts,
            "departments": dept_counts,
            "disc_distribution": disc_counts,
        },
        "agents": agents,
    }

    if errors:
        registry["_meta"]["errors"] = errors

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)

    return registry


if __name__ == "__main__":
    base = Path(__file__).parent.parent.parent
    reg = generate_registry(
        base / "departments",
        base / "knowledge" / "agents-registry-v2.json",
    )
    print(f"Generated registry: {reg['_meta']['total_agents']} agents")
    print(f"Tiers: {reg['_meta']['tiers']}")
    print(f"Departments: {reg['_meta']['departments']}")
    print(f"DISC: {reg['_meta']['disc_distribution']}")
