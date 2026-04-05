"""Conclave persistence — save/load user profiles and boards."""

import json
from pathlib import Path
from typing import Optional

from core.conclave.schema import UserProfile, ConclaveBoard, Advisor
from core.conclave.matcher import match_advisors


DEFAULT_PROFILE_PATH = Path.home() / ".arkaos" / "conclave-profile.json"


def save_profile(board: ConclaveBoard, path: str | Path = "") -> None:
    """Save a ConclaveBoard (user profile + matched advisors) to JSON."""
    path = Path(path) if path else DEFAULT_PROFILE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "user": board.user.model_dump(mode="json"),
        "aligned": [a.model_dump(mode="json") for a in board.aligned],
        "contrarian": [a.model_dump(mode="json") for a in board.contrarian],
    }

    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_profile(path: str | Path = "") -> Optional[ConclaveBoard]:
    """Load a saved ConclaveBoard from JSON. Returns None if not found."""
    path = Path(path) if path else DEFAULT_PROFILE_PATH

    if not path.exists():
        return None

    content = path.read_text().strip()
    if not content:
        return None

    data = json.loads(content)

    user = UserProfile.model_validate(data["user"])
    aligned = [Advisor.model_validate(a) for a in data.get("aligned", [])]
    contrarian = [Advisor.model_validate(a) for a in data.get("contrarian", [])]

    return ConclaveBoard(user=user, aligned=aligned, contrarian=contrarian)


def profile_exists(path: str | Path = "") -> bool:
    """Check if a saved profile exists."""
    path = Path(path) if path else DEFAULT_PROFILE_PATH
    return path.exists() and path.stat().st_size > 0


def delete_profile(path: str | Path = "") -> bool:
    """Delete a saved profile."""
    path = Path(path) if path else DEFAULT_PROFILE_PATH
    if path.exists():
        path.unlink()
        return True
    return False
