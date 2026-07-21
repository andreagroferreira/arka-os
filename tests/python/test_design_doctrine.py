"""Locks the anti-default design doctrine (Excellence Reform PR-D1).

Every canonical brand design skill must load the installed design
intelligence (frontend-design + ui-ux-pro-max), carry the structured
`[arka:design]` marker template, declare the graceful-degradation
contract, and never regress to a stub body.
"""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
BRAND_SKILLS = REPO_ROOT / "departments" / "brand" / "skills"
SQUAD_REFERENCE = (
    REPO_ROOT / "departments" / "brand" / "references"
    / "uiux-knowledge-and-tools.md"
)

CANONICAL_DESIGN_SKILLS = [
    "colors",
    "wireframe",
    "mockup-generate",
    "identity-system",
    "logo-brief",
    "ux-audit",
    "design-review",
    "design-system",
]

MARKER_TEMPLATE = (
    "[arka:design] benchmark=<Company> skills=<comma,list> tokens=<path|none>"
)


def _body(skill: str) -> str:
    return (BRAND_SKILLS / skill / "SKILL.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("skill", CANONICAL_DESIGN_SKILLS)
class TestDesignDoctrine:
    def test_has_mandatory_loading_section(self, skill):
        assert "## Load design intelligence (MANDATORY" in _body(skill), (
            f"{skill}: missing the mandatory design-intelligence loading "
            "section — the anti-default doctrine regressed to a stub."
        )

    def test_names_both_plugin_skills(self, skill):
        body = _body(skill)
        for plugin in ("frontend-design", "ui-ux-pro-max"):
            assert plugin in body, (
                f"{skill}: does not instruct loading `{plugin}` — the rich "
                "design intelligence is name-dropped nowhere."
            )

    def test_carries_structured_marker_template(self, skill):
        assert MARKER_TEMPLATE in _body(skill), (
            f"{skill}: missing the literal structured marker template "
            f"`{MARKER_TEMPLATE}`."
        )

    def test_declares_graceful_degradation(self, skill):
        body = _body(skill)
        assert "degraded:" in body and "Graceful degradation" in body, (
            f"{skill}: missing the honest-degradation contract "
            "(`skills=degraded:<missing>` when a plugin is not installed)."
        )

    def test_requires_named_benchmark_before_producing(self, skill):
        # The benchmark-FIRST imperative ("NAME the …") must survive —
        # the marker template alone would keep "benchmark" in the body.
        assert "NAME the" in _body(skill), (
            f"{skill}: lost the benchmark-first imperative (NAME the "
            "reference company before producing anything)."
        )

    def test_body_is_not_a_stub(self, skill):
        lines = _body(skill).splitlines()
        assert len(lines) > 100, (
            f"{skill}: body has {len(lines)} lines — regressed toward the "
            "pre-reform 30-line stub."
        )


class TestAbsorbedDesignCanon:
    """Locks the impeccable/hallmark absorption (design campaign W1).

    The canonical homes must not drift: the hub owns the reflex-reject
    list (§11) and the design laws (§12); the slop gates stay a frozen
    58-gate fork; design-review routes through the gates pre-verdict.
    """

    REVIEW_REFS = BRAND_SKILLS / "design-review" / "references"

    def _hub(self) -> str:
        return SQUAD_REFERENCE.read_text(encoding="utf-8")

    def test_hub_carries_canonical_font_ban(self):
        text = self._hub()
        assert "Canonical Reflex-Reject" in text
        for font in ("Fraunces", "Inter", "Space Grotesk", "Playfair Display"):
            assert font in text, f"hub §11 lost banned font: {font}"
        assert "never-by-reflex" in text, (
            "hub §11 lost the never-by-reflex semantics — without the "
            "carve-outs the list conflicts with the hallmark theme catalog."
        )

    def test_hub_carries_design_laws(self):
        text = self._hub()
        assert "Design Laws" in text
        for law in ("65\u201375ch", "\u2264 6rem", "\u22120.04em",
                    "text-wrap: balance", "prefers-reduced-motion"):
            assert law in text, f"hub §12 lost design law anchor: {law}"

    def test_hub_carries_pre_emit_axes(self):
        text = self._hub()
        for axis in ("Philosophy", "Hierarchy", "Execution", "Specificity",
                     "Restraint", "Variety"):
            assert axis in text, f"hub §8 lost pre-emit critique axis: {axis}"
        assert "[arka:design-dna]" in text, (
            "hub lost the companion stamp contract (§9)."
        )

    def test_design_review_points_at_slop_gates(self):
        body = _body("design-review")
        assert "references/slop-test.md" in body
        assert "references/anti-patterns.md" in body
        assert "Slop gates" in body, (
            "design-review lost the mandatory pre-verdict slop-gate step."
        )

    def test_slop_test_carries_58_gates(self):
        import re

        text = (self.REVIEW_REFS / "slop-test.md").read_text(encoding="utf-8")
        # Upstream numbering is 1-57 plus gate 38a: 58 unique gates total.
        gates = {
            m.group(1)
            for m in re.finditer(r"^\s*(\d+[a-z]?)\.", text, re.MULTILINE)
        }
        assert len(gates) == 58, (
            f"slop-test.md carries {len(gates)} unique gates, expected 58 "
            "(1-57 + 38a) — the fork is frozen at the upstream count."
        )

    def test_vendored_licenses_present(self):
        for name in ("hallmark.LICENSE", "impeccable.LICENSE",
                     "impeccable.NOTICE"):
            assert (self.REVIEW_REFS / name).is_file(), (
                f"missing vendored license artifact: {name}"
            )


class TestSquadReferenceDoctrine:
    def test_reference_carries_the_three_default_looks(self):
        text = SQUAD_REFERENCE.read_text(encoding="utf-8")
        assert "Anti-Default Doctrine" in text
        for look in ("Cream + serif + terracotta", "acid accent", "Broadsheet"):
            assert look in text, f"squad reference lost default look: {look}"

    def test_reference_carries_marker_contract(self):
        text = SQUAD_REFERENCE.read_text(encoding="utf-8")
        assert "Design Marker Contract" in text
        assert MARKER_TEMPLATE in text

    def test_flow_g4_references_the_marker(self):
        flow = (REPO_ROOT / "arka" / "skills" / "flow" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        assert "[arka:design]" in flow, (
            "flow G4 excellence check no longer references the design marker."
        )
