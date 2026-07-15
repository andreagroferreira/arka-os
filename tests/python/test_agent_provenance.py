"""Agent provenance — supply-chain lineage in agent YAML.

Mirror of test_skill_provenance.py for the agent tree. The point is the
same: no agent can enter the tree unclassified, so a ported third-party agent
lands in a diff with its licence written down.
"""

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from core.agents.provenance import (
    FIRST_PARTY,
    Provenance,
    ProvenanceError,
    agent_provenance,
    declares_provenance,
    provenance_from_yaml,
    provenance_issues_from_yaml,
)

BASE_DIR = Path(__file__).parent.parent.parent
AGENT_FILES = sorted(BASE_DIR.glob("departments/*/agents/**/*.yaml"))
PROVENANCE_YAML = BASE_DIR / "config" / "agents-provenance.yaml"

DERIVED = {
    "origin": "vendor-derived",
    "source": "https://example.com/upstream",
    "license": "MIT",
}


def agent(provenance=None) -> dict:
    data = {"id": "x", "name": "X", "role": "R", "department": "dev"}
    if provenance is not None:
        data["provenance"] = provenance
    return data


class TestModel:
    def test_default_is_first_party(self):
        assert Provenance().is_first_party

    def test_third_party_needs_source_and_license(self):
        with pytest.raises(ValidationError, match="source, license required"):
            Provenance(origin="vendor-derived")

    def test_plaintext_source_refused(self):
        with pytest.raises(ValidationError, match="not an https"):
            Provenance(origin="vendor-derived",
                       source="http://github.com/x", license="MIT")

    def test_first_party_with_a_trail_is_incoherent(self):
        with pytest.raises(ValidationError, match="but declares"):
            Provenance(origin=FIRST_PARTY, license="MIT")


class TestParse:
    def test_no_block_is_first_party(self):
        assert provenance_from_yaml(agent()).is_first_party

    def test_reads_the_block(self):
        prov = provenance_from_yaml(agent(DERIVED))
        assert prov.origin == "vendor-derived"
        assert prov.license == "MIT"

    def test_scalar_block_is_an_error(self):
        with pytest.raises(ProvenanceError, match="must be a mapping"):
            provenance_from_yaml(agent("vendor-derived"))

    def test_unknown_key_is_an_error(self):
        with pytest.raises(ProvenanceError, match="unknown metadata keys"):
            provenance_from_yaml(agent({"orgin": "vendor-derived"}))

    def test_non_mapping_yaml_is_an_error(self):
        with pytest.raises(ProvenanceError, match="not a mapping"):
            provenance_from_yaml(["a", "list"])


class TestDeclares:
    def test_absent_is_not_a_declaration(self):
        assert not declares_provenance(agent())

    def test_present_block_is_a_declaration(self):
        assert declares_provenance(agent(DERIVED))

    def test_broken_block_still_counts_as_declaring(self):
        assert declares_provenance(agent("junk"))
        assert provenance_issues_from_yaml(agent("junk"))

    def test_non_dict_is_not_a_declaration(self):
        assert not declares_provenance(["a", "list"])
        assert not declares_provenance("a string")


class TestIssues:
    def test_clean_has_no_issues(self):
        assert provenance_issues_from_yaml(agent()) == []
        assert provenance_issues_from_yaml(agent(DERIVED)) == []

    def test_incomplete_third_party_reports(self):
        issues = provenance_issues_from_yaml(agent({"origin": "community"}))
        assert issues and "source, license required" in issues[0]

    def test_issues_never_raise(self):
        assert provenance_issues_from_yaml(agent({"origin": "BAD"}))


class TestAgentProvenanceFromPath:
    def test_reads_a_real_agent_file(self, tmp_path):
        p = tmp_path / "a.yaml"
        p.write_text(yaml.safe_dump(agent(DERIVED)))
        assert agent_provenance(p).origin == "vendor-derived"

    def test_unreadable_file_raises_named(self, tmp_path):
        with pytest.raises(ProvenanceError, match="cannot read"):
            agent_provenance(tmp_path / "nope.yaml")


class TestTreeIsClean:
    @pytest.mark.parametrize(
        "agent_file", AGENT_FILES,
        ids=lambda f: f"{f.parent.parent.name}/{f.stem}",
    )
    def test_every_agent_provenance_is_valid(self, agent_file):
        data = yaml.safe_load(agent_file.read_text(encoding="utf-8"))
        issues = provenance_issues_from_yaml(data)
        assert not issues, f"{agent_file}: {'; '.join(issues)}"


class TestEveryAgentIsClassified:
    """The control for the vector no parser can see — a port that never
    declares. Every agent must be baseline, derived, or self-declaring."""

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
    def name_of(agent_file: Path) -> str:
        return str(agent_file.relative_to(BASE_DIR))

    def test_coverage_is_every_agent(self):
        on_disk = {self.name_of(f) for f in AGENT_FILES}
        classified = self.baseline() | set(self.registry())
        declaring = {
            self.name_of(f) for f in AGENT_FILES
            if declares_provenance(
                yaml.safe_load(f.read_text(encoding="utf-8")))
        }
        unclassified = on_disk - classified - declaring
        assert not unclassified, (
            f"unclassified agents — add a provenance block to the YAML, or "
            f"register them in config/agents-provenance.yaml: "
            f"{sorted(unclassified)}"
        )

    def test_baseline_holds_only_real_agents(self):
        stale = self.baseline() - {self.name_of(f) for f in AGENT_FILES}
        assert not stale, f"baseline names agents that no longer exist: {sorted(stale)}"

    def test_baseline_and_registry_disjoint(self):
        both = self.baseline() & set(self.registry())
        assert not both, f"claimed first-party AND derived: {sorted(both)}"

    @classmethod
    def tree_derived(cls) -> dict[str, Provenance]:
        found = {}
        for f in AGENT_FILES:
            prov = provenance_from_yaml(
                yaml.safe_load(f.read_text(encoding="utf-8")))
            if not prov.is_first_party:
                found[cls.name_of(f)] = prov
        return found

    def test_every_registered_agent_declares_it(self):
        missing = set(self.registry()) - set(self.tree_derived())
        assert not missing, (
            f"registered as derived but the YAML does not say so: "
            f"{sorted(missing)}"
        )

    def test_every_derived_agent_is_registered(self):
        unregistered = set(self.tree_derived()) - set(self.registry())
        assert not unregistered, (
            f"derived agents missing from config/agents-provenance.yaml: "
            f"{sorted(unregistered)}"
        )

    def test_registry_matches_yaml_field_for_field(self):
        tree = self.tree_derived()
        for name, entry in self.registry().items():
            prov = tree[name]
            assert entry.get("origin") == prov.origin, name
            assert entry.get("source") == prov.source, name
            assert entry.get("license") == prov.license, name
