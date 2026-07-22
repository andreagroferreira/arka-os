"""Vendor tree integrity for dev/diagram (no node required)."""
from __future__ import annotations

import hashlib
from pathlib import Path

import yaml

from core.skills.provenance import parse_provenance

REPO_ROOT = Path(__file__).resolve().parents[3]
SKILL_DIR = REPO_ROOT / "departments" / "dev" / "skills" / "diagram"
VENDOR_DIR = SKILL_DIR / "vendor"

# Tamper guard for the 520KB unreviewable template blob. Moves ONLY on an
# intentional upstream bump, together with the version line in
# docs/THIRD-PARTY-NOTICES.md.
TEMPLATE_SHA256 = "62a03e27012698103613429db262cd608442f40132f6a4f3f8302491edc70c40"


def test_license_carries_both_copyrights() -> None:
    text = (VENDOR_DIR / "LICENSE").read_text(encoding="utf-8")
    assert "tt-a1i" in text
    assert "Cocoon AI" in text


def test_no_rendered_html_examples() -> None:
    assert not list((VENDOR_DIR / "examples").glob("*.html"))


def test_no_node_modules_committed() -> None:
    assert not list(VENDOR_DIR.rglob("node_modules"))


def test_template_sha256_pin() -> None:
    digest = hashlib.sha256(
        (VENDOR_DIR / "assets" / "template.html").read_bytes()
    ).hexdigest()
    assert digest == TEMPLATE_SHA256, (
        "template.html changed — if this is an intentional upstream bump, "
        "update TEMPLATE_SHA256 and the version in docs/THIRD-PARTY-NOTICES.md"
    )


def test_skill_metadata_matches_provenance_registry() -> None:
    skill = parse_provenance((SKILL_DIR / "SKILL.md").read_text(encoding="utf-8"))
    registry = yaml.safe_load(
        (REPO_ROOT / "config" / "skills-provenance.yaml").read_text(encoding="utf-8")
    )
    entry = registry["derived"]["departments/dev/skills/diagram"]
    assert skill.origin == entry["origin"]
    assert skill.source == entry["source"]
    assert skill.license == entry["license"]
