"""Every .arkaos/specs/*.yaml must parse and be visible to the gate.

QG D3 r2, Francisca B1: a spec shipped that yaml.safe_load could not
read AND that carried no column-0 ``status:``, so
``rules_registry._spec_file_is_active`` reported it inactive — the
spec-driven gate could not see the spec of the feature it gates. 7763
tests passed with that file on disk, because nothing checked either
property. This does.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

_SPECS_DIR = Path(__file__).resolve().parents[2] / ".arkaos" / "specs"


def _spec_files() -> list[Path]:
    return sorted(_SPECS_DIR.glob("*.yaml"))


def test_specs_directory_is_populated():
    assert _spec_files(), "no specs found — did .arkaos/specs/ move?"


@pytest.mark.parametrize("path", _spec_files(), ids=lambda p: p.name)
def test_spec_parses_as_yaml(path: Path):
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:  # pragma: no cover - message is the point
        pytest.fail(f"{path.name} is not valid YAML: {exc}")
    assert isinstance(data, dict), f"{path.name} must map at the top level"
    assert "spec" in data, f"{path.name} must carry a spec block"


@pytest.mark.parametrize("path", _spec_files(), ids=lambda p: p.name)
def test_spec_carries_the_column_zero_status_mirror(path: Path):
    """rules_registry matches ^status: at column 0 — a spec without the
    mirror is invisible to the gate that requires it."""
    from core.workflow import rules_registry

    text = path.read_text(encoding="utf-8")
    assert any(
        line.startswith("status:") for line in text.splitlines()
    ), (
        f"{path.name} has no column-0 'status:' mirror; the spec-driven "
        f"gate cannot see it (see notebooklm-chokepoint.yaml for the form)"
    )
    assert rules_registry._spec_file_is_active(path), (
        f"{path.name} parses and has a status line, but the gate still "
        f"reports it inactive"
    )
