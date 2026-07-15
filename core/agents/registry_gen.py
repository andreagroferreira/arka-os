"""Generate agents-registry-v2.json from all agent YAML files.

Scans departments/*/agents/*.yaml and produces the single canonical
machine-readable registry with all agent metadata including behavioral
DNA. The legacy knowledge/agents-registry.json (v1) was removed —
tests/python/test_registry_gen.py guards against its resurrection.
"""

import json
from datetime import datetime
from pathlib import Path

from core.agents.loader import load_agent
from core.agents.provenance import Provenance, agent_provenance


def _provenance_entry(prov: Provenance) -> dict:
    """The full origin/source/licence trail for the registry — not just
    origin, so the shipped file can answer 'what licence is this under?'."""
    entry = {"origin": prov.origin}
    if not prov.is_first_party:
        entry["source"] = prov.source
        entry["license"] = prov.license
    return entry


def _dna_dict(dna) -> dict:
    """The four-framework behavioral DNA, flattened for the registry."""
    return {
        "disc": {
            "primary": dna.disc.primary.value,
            "secondary": dna.disc.secondary.value,
            "label": dna.disc.label,
        },
        "enneagram": {
            "type": dna.enneagram.type.value,
            "wing": dna.enneagram.wing,
            "label": dna.enneagram.label,
        },
        "big_five": {
            "O": dna.big_five.openness,
            "C": dna.big_five.conscientiousness,
            "E": dna.big_five.extraversion,
            "A": dna.big_five.agreeableness,
            "N": dna.big_five.neuroticism,
        },
        "mbti": dna.mbti.type.value,
    }


def _agent_entry(agent, prov: Provenance, yaml_file: Path, root: Path) -> dict:
    """One registry entry for a loaded agent + its provenance."""
    return {
        "id": agent.id,
        "name": agent.name,
        "role": agent.role,
        "department": agent.department,
        "tier": agent.tier,
        "model": agent.get_model(),
        "provenance": _provenance_entry(prov),
        "parent_squad": agent.parent_squad,
        "sub_squad_role": agent.sub_squad_role,
        **_dna_dict(agent.behavioral_dna),
        "authority": {
            k: v for k, v in agent.authority.model_dump().items()
            if v and v != [] and k not in ("delegates_to", "escalates_to")
        },
        "expertise_domains": agent.expertise.domains,
        "frameworks": agent.expertise.frameworks,
        "knowledge_sources": agent.expertise.knowledge_sources,
        "file": str(yaml_file.relative_to(root)),
        "memory_path": agent.memory_path,
    }


def _summaries(agents: list[dict]) -> dict:
    """Tier, department, and DISC-primary counts for the registry meta."""
    tiers, depts, disc = {}, {}, {}
    for a in agents:
        tiers[a["tier"]] = tiers.get(a["tier"], 0) + 1
        depts[a["department"]] = depts.get(a["department"], 0) + 1
        primary = a["disc"]["primary"]
        disc[primary] = disc.get(primary, 0) + 1
    return {"tiers": tiers, "departments": depts, "disc_distribution": disc}


def generate_registry(departments_dir: str | Path, output_path: str | Path) -> dict:
    """Generate agents-registry-v2.json from YAML agent files.

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

    # Recursive: also picks up sub-squad subdirectories
    # (e.g. dev/agents/backend-core/*.yaml, brand/agents/design-ops/*.yaml).
    for yaml_file in sorted(departments_dir.glob("*/agents/**/*.yaml")):
        try:
            agent = load_agent(yaml_file)
            prov = agent_provenance(yaml_file)
            agents.append(_agent_entry(
                agent, prov, yaml_file, departments_dir.parent))
        except Exception as e:
            errors.append(f"{yaml_file.name}: {e}")

    registry = {
        "_meta": {
            "version": "2.0.0",
            "generated": datetime.now().isoformat(),
            "total_agents": len(agents),
            "generator": "core/agents/registry_gen.py",
            **_summaries(agents),
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
