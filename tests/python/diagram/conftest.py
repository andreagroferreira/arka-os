"""Shared fixtures for the dev/diagram skill (vendored archify engine)."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

SKILL_DIR = (
    Path(__file__).resolve().parents[3]
    / "departments" / "dev" / "skills" / "diagram"
)
VENDOR_DIR = SKILL_DIR / "vendor"


@pytest.fixture(autouse=True)
def _isolated_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """No diagram test may read or write the real user home (Wave 3 rule)."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))  # Windows
    monkeypatch.delenv("ARKAOS_HOME", raising=False)
    return home


@pytest.fixture(scope="session")
def node() -> str:
    """The node binary, skipping when absent or older than the engine needs."""
    binary = shutil.which("node")
    if binary is None:
        pytest.skip("node not installed")
    result = subprocess.run(
        [binary, "--version"], capture_output=True, text=True, timeout=30
    )
    major = int(result.stdout.lstrip("v").split(".")[0])
    if major < 18:
        pytest.skip(f"node >= 18 required, found {result.stdout.strip()}")
    return binary


@pytest.fixture(scope="session")
def cli() -> Path:
    return VENDOR_DIR / "bin" / "archify.mjs"


@pytest.fixture(scope="session")
def architecture_example() -> Path:
    return VENDOR_DIR / "examples" / "web-app.architecture.json"


@pytest.fixture(scope="session")
def workflow_example() -> Path:
    return VENDOR_DIR / "examples" / "agent-tool-call.workflow.json"
