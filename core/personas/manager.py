"""Persona manager — CRUD operations and cloning to agents."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

from core.personas.schema import Persona


class PersonaManager:
    """Manages persona lifecycle: create, store, list, clone to agent."""

    def __init__(self, storage_path: str | Path = "") -> None:
        self._personas: dict[str, Persona] = {}
        self._storage_path = Path(storage_path) if storage_path else None
        if self._storage_path and self._storage_path.exists():
            self._load()

    def create(self, persona: Persona) -> Persona:
        """Create a new persona."""
        persona.created_at = datetime.now().isoformat()
        persona.updated_at = persona.created_at
        self._personas[persona.id] = persona
        self._save()
        return persona

    def get(self, persona_id: str) -> Optional[Persona]:
        return self._personas.get(persona_id)

    def list_all(self) -> list[Persona]:
        return list(self._personas.values())

    def update(self, persona_id: str, updates: dict) -> Optional[Persona]:
        persona = self._personas.get(persona_id)
        if not persona:
            return None
        for key, value in updates.items():
            if hasattr(persona, key):
                setattr(persona, key, value)
        persona.updated_at = datetime.now().isoformat()
        self._save()
        return persona

    def delete(self, persona_id: str) -> bool:
        if persona_id in self._personas:
            del self._personas[persona_id]
            self._save()
            return True
        return False

    def clone_to_agent(
        self,
        persona_id: str,
        department: str = "strategy",
        tier: int = 2,
        agents_dir: str | Path = "",
    ) -> Optional[str]:
        """Clone a persona to an ArkaOS agent YAML file.

        Returns the agent ID if successful, None if persona not found.
        """
        persona = self._personas.get(persona_id)
        if not persona:
            return None

        agent_data = persona.to_agent_yaml(department=department, tier=tier)
        agent_id = agent_data["id"]

        if agents_dir:
            output_dir = Path(agents_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"{agent_id}.yaml"
            with open(output_path, "w") as f:
                yaml.dump(agent_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

        # Track the clone
        persona.cloned_to_agents.append(agent_id)
        persona.updated_at = datetime.now().isoformat()
        self._save()

        return agent_id

    def _save(self) -> None:
        if self._storage_path is None:
            return
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = {pid: p.model_dump(mode="json") for pid, p in self._personas.items()}
        with open(self._storage_path, "w") as f:
            json.dump(data, f, indent=2)

    def _load(self) -> None:
        if self._storage_path is None or not self._storage_path.exists():
            return
        content = self._storage_path.read_text().strip()
        if not content:
            return
        data = json.loads(content)
        for pid, pdata in data.items():
            self._personas[pid] = Persona.model_validate(pdata)
