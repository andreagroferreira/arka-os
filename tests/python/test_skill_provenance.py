"""Skill provenance — supply-chain lineage in SKILL.md frontmatter.

The point of these tests is the LAUNDERING vectors: a derived skill
must never read as first-party because the author fat-fingered the
block. Absence is the only path to `arkaos`, and absence is itself
pinned by config/skills-derived.yaml.
"""

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from core.skills.provenance import (
    FIRST_PARTY,
    ProvenanceError,
    SkillProvenance,
    declares_provenance,
    parse_provenance,
    provenance_issues,
)

BASE_DIR = Path(__file__).parent.parent.parent
PROVENANCE_YAML = BASE_DIR / "config" / "skills-provenance.yaml"

# Every HAND-AUTHORED skill surface. A port can land in any of them —
# and the two that would do the most damage are not the obvious one:
# arka/ holds the core skills, and marketplace/ IS the distribution
# surface. All of them are classified.
SKILL_FILES = sorted(
    f
    for pattern in (
        "departments/*/skills/*/SKILL.md",
        "departments/*/SKILL.md",
        "arka/skills/*/SKILL.md",
        "arka/SKILL.md",
    )
    for f in BASE_DIR.glob(pattern)
)

# The only trees a SKILL.md may live in without being classified. Both
# are emitted from departments/ and byte-drift-gated — plugins/ by
# test_marketplace_gen, marketplace/ by test_marketplace_export_drift.
# The exclusion is therefore enforced, not asserted: a skill cannot
# reach either tree without first passing through a classified source.
GENERATED_TREES = ("plugins", "marketplace")


def skill_md(metadata: str = "") -> str:
    """A minimal SKILL.md body, optionally carrying a metadata block."""
    return (
        "---\n"
        "name: dev/example\n"
        "description: Example skill.\n"
        "allowed-tools: [Read]\n"
        f"{metadata}"
        "---\n\n# Example\n"
    )


DERIVED = (
    "metadata:\n"
    "  origin: vendor-derived\n"
    "  source: https://example.com/upstream\n"
    "  license: MIT\n"
)


class TestModel:
    def test_default_is_first_party(self):
        assert SkillProvenance().origin == FIRST_PARTY
        assert SkillProvenance().is_first_party

    def test_third_party_needs_source_and_license(self):
        with pytest.raises(ValidationError, match="source, license required"):
            SkillProvenance(origin="vendor-derived")

    def test_third_party_needs_license_alone(self):
        with pytest.raises(ValidationError, match="license required"):
            SkillProvenance(
                origin="vendor-derived", source="https://example.com/upstream"
            )

    def test_third_party_source_must_be_a_url(self):
        with pytest.raises(ValidationError, match="not an https"):
            SkillProvenance(
                origin="vendor-derived", source="example/upstream", license="MIT"
            )

    def test_plaintext_source_is_refused(self):
        with pytest.raises(ValidationError, match="not an https"):
            SkillProvenance(
                origin="vendor-derived",
                source="http://example.com/upstream",
                license="MIT",
            )

    def test_first_party_carrying_a_trail_is_incoherent(self):
        with pytest.raises(ValidationError, match="but declares source"):
            SkillProvenance(
                origin=FIRST_PARTY, source="https://example.com/upstream"
            )

    def test_first_party_carrying_a_licence_is_incoherent(self):
        with pytest.raises(ValidationError, match="but declares license"):
            SkillProvenance(origin=FIRST_PARTY, license="MIT")

    def test_valid_third_party(self):
        prov = SkillProvenance(
            origin="vendor-derived",
            source="https://example.com/upstream",
            license="MIT",
        )
        assert not prov.is_first_party
        assert prov.license == "MIT"

    def test_origin_must_be_a_slug(self):
        with pytest.raises(ValidationError, match="not a lowercase slug"):
            SkillProvenance(origin="Vendor-Derived")


class TestParse:
    def test_no_metadata_block_is_first_party(self):
        assert parse_provenance(skill_md()).origin == FIRST_PARTY

    def test_no_frontmatter_at_all_is_first_party(self):
        assert parse_provenance("# Just a heading\n").origin == FIRST_PARTY

    def test_empty_frontmatter_is_first_party(self):
        assert parse_provenance("---\n\n---\n").origin == FIRST_PARTY

    def test_reads_nested_metadata(self):
        prov = parse_provenance(skill_md(DERIVED))
        assert prov.origin == "vendor-derived"
        assert prov.source == "https://example.com/upstream"
        assert prov.license == "MIT"


class TestLaunderingIsRefused:
    """Every way of writing a broken block. None may read as arkaos."""

    def test_broken_yaml_is_an_error(self):
        with pytest.raises(ProvenanceError, match="does not parse"):
            parse_provenance("---\n:\n  : :\n\tx\n---\n")

    def test_tab_indented_block_is_an_error(self):
        content = skill_md("metadata:\n\torigin: vendor-derived\n")
        with pytest.raises(ProvenanceError, match="does not parse"):
            parse_provenance(content)

    def test_scalar_metadata_is_an_error(self):
        with pytest.raises(ProvenanceError, match="must be a mapping"):
            parse_provenance(skill_md("metadata: vendor-derived\n"))

    def test_list_metadata_is_an_error(self):
        with pytest.raises(ProvenanceError, match="must be a mapping"):
            parse_provenance(skill_md("metadata:\n  - origin: x\n"))

    def test_misspelt_metadata_key_is_an_error(self):
        content = skill_md("metadatas:\n  origin: vendor-derived\n")
        with pytest.raises(ProvenanceError, match="did you mean 'metadata'"):
            parse_provenance(content)

    @pytest.mark.parametrize("typo", ["meta-data", "meta_data", "Metadata"])
    def test_metadata_near_misses_are_errors(self, typo):
        content = skill_md(f"{typo}:\n  origin: vendor-derived\n")
        with pytest.raises(ProvenanceError, match="did you mean"):
            parse_provenance(content)

    def test_misspelt_origin_key_is_an_error(self):
        content = skill_md("metadata:\n  orgin: vendor-derived\n")
        with pytest.raises(ProvenanceError, match="unknown metadata keys"):
            parse_provenance(content)

    def test_non_mapping_frontmatter_is_an_error(self):
        with pytest.raises(ProvenanceError, match="not a mapping"):
            parse_provenance("---\n- one\n- two\n---\n")


class TestDeclaresProvenance:
    """`parse_provenance` cannot tell "said arkaos" from "said nothing".
    The classification control depends on exactly that distinction."""

    def test_silence_is_not_a_declaration(self):
        assert not declares_provenance(skill_md())

    def test_no_frontmatter_is_not_a_declaration(self):
        assert not declares_provenance("# Heading\n")

    def test_explicit_first_party_is_a_declaration(self):
        assert declares_provenance(skill_md("metadata:\n  origin: arkaos\n"))

    def test_derived_block_is_a_declaration(self):
        assert declares_provenance(skill_md(DERIVED))

    @pytest.mark.parametrize("metadata", [
        "metadata: junk\n",
        "metadatas:\n  origin: x\n",
        "metadata:\n  orgin: x\n",
    ])
    def test_a_broken_attempt_still_counts_as_declaring(self, metadata):
        """It must not fall through to "undeclared" and pass the baseline
        check — provenance_issues owns the failure instead."""
        assert declares_provenance(skill_md(metadata))
        assert provenance_issues(skill_md(metadata))


class TestIssues:
    def test_clean_skill_has_no_issues(self):
        assert provenance_issues(skill_md()) == []
        assert provenance_issues(skill_md(DERIVED)) == []

    def test_incomplete_third_party_reports_issue(self):
        issues = provenance_issues(skill_md("metadata:\n  origin: community\n"))
        assert len(issues) == 1
        assert "source, license required" in issues[0]

    @pytest.mark.parametrize("metadata", [
        "metadata: junk\n",
        "metadata:\n\torigin: x\n",
        "metadatas:\n  origin: x\n",
        "metadata:\n  orgin: x\n",
        "metadata:\n  origin: BAD\n",
    ])
    def test_every_broken_block_reports_and_never_raises(self, metadata):
        assert provenance_issues(skill_md(metadata))


class TestTreeIsClean:
    """Every shipped skill declares a coherent provenance."""

    @pytest.mark.parametrize(
        "skill_file", SKILL_FILES,
        ids=lambda f: f"{f.parent.parent.name}/{f.parent.name}",
    )
    def test_skill_provenance_is_valid(self, skill_file):
        issues = provenance_issues(skill_file.read_text(encoding="utf-8"))
        assert not issues, f"{skill_file}: {'; '.join(issues)}"


class TestEverySkillIsClassified:
    """The control for the vector no parser can see.

    A ported skill that never writes a metadata block reads as
    first-party — a forgotten port and an honest one are byte-identical
    to the parser. So the parser is not asked. Every skill in the tree
    must instead be CLASSIFIED, three ways and only three:

      - in `first_party` — the closed baseline, snapshotted at the cut;
      - in `derived` — registered, with source and licence;
      - self-declaring `metadata.origin` in its own frontmatter.

    A skill in none of the three is unclassified and fails. A new skill
    added tomorrow is not in the baseline, so it must declare. A port
    that declares nothing is not in the baseline either — it fails, by
    name, in CI. That is the whole mechanism.
    """

    @staticmethod
    def config() -> dict:
        return yaml.safe_load(PROVENANCE_YAML.read_text(encoding="utf-8"))

    @classmethod
    def baseline(cls) -> set[str]:
        return set(cls.config().get("first_party") or [])

    @classmethod
    def registry(cls) -> dict[str, dict]:
        return cls.config().get("derived") or {}

    @staticmethod
    def name_of(skill_file: Path) -> str:
        """Repo-relative skill directory — unambiguous across surfaces."""
        return str(skill_file.parent.relative_to(BASE_DIR))

    def test_coverage_is_every_authored_surface(self):
        """The classifier is worthless if a port can land outside it."""
        authored = {
            f for f in BASE_DIR.rglob("SKILL.md")
            if "node_modules" not in f.parts
            and ".git" not in f.parts
            and f.parts[len(BASE_DIR.parts)] not in GENERATED_TREES
        }
        uncovered = authored - set(SKILL_FILES)
        assert not uncovered, (
            f"hand-authored SKILL.md outside the classifier's reach: "
            f"{sorted(str(f.relative_to(BASE_DIR)) for f in uncovered)}"
        )

    def test_no_skill_is_unclassified(self):
        baseline, registry = self.baseline(), self.registry()
        unclassified = [
            self.name_of(f) for f in SKILL_FILES
            if self.name_of(f) not in baseline
            and self.name_of(f) not in registry
            and not declares_provenance(f.read_text(encoding="utf-8"))
        ]
        assert not unclassified, (
            f"unclassified skills — add metadata.origin to the SKILL.md, "
            f"or register them in config/skills-provenance.yaml: "
            f"{sorted(unclassified)}"
        )

    def test_baseline_is_a_closed_set_of_real_skills(self):
        stale = self.baseline() - {self.name_of(f) for f in SKILL_FILES}
        assert not stale, (
            f"baseline names skills that no longer exist — a deleted skill "
            f"must leave the baseline: {sorted(stale)}"
        )

    def test_baseline_and_registry_are_disjoint(self):
        both = self.baseline() & set(self.registry())
        assert not both, f"claimed first-party AND derived: {sorted(both)}"

    def test_every_registered_skill_declares_it_in_frontmatter(self):
        tree = self.tree_derived()
        missing = set(self.registry()) - set(tree)
        assert not missing, (
            f"registered as derived but the SKILL.md does not say so: "
            f"{sorted(missing)}"
        )

    def test_every_derived_skill_is_registered(self):
        unregistered = set(self.tree_derived()) - set(self.registry())
        assert not unregistered, (
            f"derived skills missing from config/skills-provenance.yaml: "
            f"{sorted(unregistered)}"
        )

    def test_registry_matches_frontmatter_field_for_field(self):
        tree = self.tree_derived()
        for name, entry in self.registry().items():
            prov = tree[name]
            assert entry.get("origin") == prov.origin, name
            assert entry.get("source") == prov.source, name
            assert entry.get("license") == prov.license, name

    @classmethod
    def tree_derived(cls) -> dict[str, SkillProvenance]:
        found = {}
        for skill_file in SKILL_FILES:
            prov = parse_provenance(skill_file.read_text(encoding="utf-8"))
            if not prov.is_first_party:
                found[cls.name_of(skill_file)] = prov
        return found
