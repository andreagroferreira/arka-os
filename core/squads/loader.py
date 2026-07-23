"""Squad YAML loader."""

from pathlib import Path
import yaml

from core.squads.schema import Squad


def load_squad(path: str | Path) -> Squad:
    """Load a squad from a YAML file."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Squad file not found: {path}")

    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if data is None:
        raise ValueError(f"Empty squad file: {path}")

    return Squad.model_validate(data)


def load_all_squads(base_dir: str | Path) -> list[Squad]:
    """Load all squad YAML files from a directory tree.

    Expects squad.yaml files in department directories.
    """
    base_dir = Path(base_dir)
    squads = []

    for squad_file in sorted(base_dir.glob("*/squad.yaml")):
        try:
            squad = load_squad(squad_file)
            squads.append(squad)
        except Exception as e:
            import warnings
            warnings.warn(f"Failed to load squad: {squad_file}: {e}")

    return squads


def load_matrix_squads(squads_dir: str | Path) -> list[Squad]:
    """Load cross-department matrix squads (missions + transversal).

    These implement "Autonomy by Missions, not Departments": stream-aligned
    mission squads that own an outcome end-to-end, and transversal
    platform/enabling squads (RevOps, People & Org, Governance). Members are
    borrowed from their home departments — agents keep their department home.

    Discovers one level of categorised subdirectories (e.g.
    squads/missions/*.yaml, squads/transversal/*.yaml) — not arbitrary depth,
    so stray YAML elsewhere under the tree is never mistaken for a squad.
    """
    squads_dir = Path(squads_dir)
    squads = []

    for squad_file in sorted(squads_dir.glob("*/*.yaml")):
        try:
            squads.append(load_squad(squad_file))
        except Exception as e:
            import warnings
            warnings.warn(f"Failed to load matrix squad: {squad_file}: {e}")

    return squads
