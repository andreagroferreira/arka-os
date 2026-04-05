"""Squad Framework — YAML-based squad definitions and cross-department collaboration."""

from core.squads.schema import Squad, SquadMember, SquadType
from core.squads.registry import SquadRegistry
from core.squads.loader import load_squad

__all__ = ["Squad", "SquadMember", "SquadType", "SquadRegistry", "load_squad"]
