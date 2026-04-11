"""Forge persistence — YAML plans, Obsidian export, pattern extraction."""

import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Optional
import yaml
from core.forge.schema import ForgePlan


def _plans_dir() -> Path:
    return Path.home() / ".arkaos" / "plans"


def _active_link() -> Path:
    return _plans_dir() / "active.yaml"


def save_plan(plan: ForgePlan) -> Path:
    """Save a forge plan as YAML. Atomic write."""
    plans = _plans_dir()
    plans.mkdir(parents=True, exist_ok=True)
    target = plans / f"{plan.id}.yaml"
    data = plan.model_dump(mode="json")
    fd = NamedTemporaryFile(mode="w", dir=str(plans), suffix=".tmp", delete=False, encoding="utf-8")
    try:
        yaml.dump(data, fd, default_flow_style=False, allow_unicode=True)
        fd.close()
        os.replace(fd.name, str(target))
    except BaseException:
        fd.close()
        os.unlink(fd.name)
        raise
    return target


def load_plan(plan_id: str) -> Optional[ForgePlan]:
    """Load a forge plan by ID. Returns None if not found."""
    path = _plans_dir() / f"{plan_id}.yaml"
    if not path.exists():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return ForgePlan(**data)


def list_plans() -> list[dict]:
    """List all saved plans as summary dicts."""
    plans = _plans_dir()
    if not plans.exists():
        return []
    results = []
    for path in sorted(plans.glob("*.yaml")):
        if path.name == "active.yaml":
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        results.append({
            "id": data.get("id", path.stem),
            "name": data.get("name", ""),
            "status": data.get("status", "draft"),
            "tier": data.get("complexity", {}).get("tier", "shallow"),
            "confidence": data.get("critic", {}).get("confidence", 0.0),
            "created_at": data.get("created_at", ""),
        })
    return results


def set_active_plan(plan_id: str) -> None:
    """Set a plan as the active forge plan."""
    link = _active_link()
    link.parent.mkdir(parents=True, exist_ok=True)
    link.write_text(plan_id, encoding="utf-8")


def get_active_plan() -> Optional[ForgePlan]:
    """Get the currently active forge plan."""
    link = _active_link()
    if not link.exists():
        return None
    plan_id = link.read_text(encoding="utf-8").strip()
    return load_plan(plan_id)


def clear_active_plan() -> None:
    """Clear the active forge plan."""
    link = _active_link()
    if link.exists():
        link.unlink()
