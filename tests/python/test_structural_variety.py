"""Locks the design-absorption W2 surfaces (structural variety).

The macrostructure catalog and the component cookbook are frozen forks
of upstream hallmark: index and files must stay in parity, the
page-architect flow must read the diversification memory, and no
upstream branding may survive in the vendored trees.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
PA_REFS = (
    REPO_ROOT / "departments" / "landing" / "skills" / "page-architect"
    / "references"
)
DS_REFS = (
    REPO_ROOT / "departments" / "brand" / "skills" / "design-system"
    / "references"
)
W2_TREES = [
    PA_REFS,
    DS_REFS,
    REPO_ROOT / "departments" / "brand" / "skills" / "colors" / "references",
    REPO_ROOT / "departments" / "dev" / "skills" / "animated-website"
    / "references",
]

# Strings that must never survive outside attribution headers and
# license files. Attribution lines are the single sanctioned mention of
# the upstream repo name, so the repo-URL form is allowed; bare product
# branding is not.
FORBIDDEN = ("usehallmark.com", "Together AI", "impeccable.style",
             "IMPECCABLE_", ".hallmark/", "{{")


class TestStructuralVariety:
    def test_macrostructure_index_matches_files(self):
        files = sorted(
            p.stem for p in (PA_REFS / "macrostructures").glob("*.md")
        )
        assert len(files) == 21, (
            f"macrostructures/ carries {len(files)} shapes, expected 21 — "
            "the fork is frozen at the upstream count."
        )
        index = (PA_REFS / "macrostructures.md").read_text(encoding="utf-8")
        missing = [f for f in files if f not in index]
        assert not missing, f"index does not reference: {missing}"

    def test_component_cookbook_matches_files(self):
        files = sorted(
            p.name for p in (PA_REFS / "components").glob("*.md")
        )
        assert len(files) == 50, (
            f"components/ carries {len(files)} archetypes, expected 50 — "
            "the fork is frozen at the upstream count."
        )
        index = (PA_REFS / "component-cookbook.md").read_text(
            encoding="utf-8"
        )
        missing = [f for f in files if f not in index]
        assert not missing, f"cookbook does not reference: {missing}"

    def test_page_architect_reads_diversification_memory(self):
        body = (PA_REFS.parent / "SKILL.md").read_text(encoding="utf-8")
        assert ".arka/design/log.json" in body, (
            "page-architect lost the diversification-memory step."
        )
        assert "macrostructures.md" in body
        assert "component-cookbook.md" in body

    def test_design_system_carries_study_mode(self):
        body = (DS_REFS.parent / "SKILL.md").read_text(encoding="utf-8")
        assert "design-dna-study.md" in body
        assert "design-md-spec.md" in body
        study = (DS_REFS / "design-dna-study.md").read_text(encoding="utf-8")
        for anchor in ("169.254.169.254", "ThemeForest", "attestation"):
            assert anchor.lower() in study.lower(), (
                f"design-dna-study lost a safety-layer anchor: {anchor}"
            )

    def test_theme_catalog_parity(self):
        themes = sorted(p.stem for p in (DS_REFS / "themes").glob("*.md"))
        assert themes == ["carnival", "cobalt", "hum", "lumen"]

    def test_vendored_trees_are_sanitized(self):
        offenders: list[str] = []
        for tree in W2_TREES:
            for p in tree.rglob("*.md"):
                text = p.read_text(encoding="utf-8")
                lines = [
                    ln for ln in text.splitlines()
                    if not ln.lstrip().startswith(">")
                ]
                body = "\n".join(lines)
                for token in FORBIDDEN:
                    if token in body:
                        offenders.append(f"{p.relative_to(REPO_ROOT)}: {token}")
        assert not offenders, (
            "upstream branding/template residue in vendored trees:\n"
            + "\n".join(offenders)
        )

    def test_licenses_travel_with_material(self):
        for tree in W2_TREES:
            assert (tree / "hallmark.LICENSE").is_file(), (
                f"{tree}: missing hallmark.LICENSE"
            )

    def test_stamps_are_key_value(self):
        pattern = re.compile(r"\[arka:design-dna\] macrostructure:")
        offenders = [
            str(p.relative_to(REPO_ROOT))
            for tree in W2_TREES
            for p in tree.rglob("*.md")
            if pattern.search(p.read_text(encoding="utf-8"))
        ]
        assert not offenders, (
            f"colon-style design-dna stamps (must be key=value): {offenders}"
        )
