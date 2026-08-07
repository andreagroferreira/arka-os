"""core.harness.manifest — policy vocabulary, tolerant load, spec link."""

import json

import pytest
from pydantic import ValidationError

from core.harness import spec as harness_spec
from core.harness.manifest import (
    OwnershipManifest,
    OwnershipPolicy,
    SurfaceRecord,
    load_manifest,
)


class TestPolicyVocabulary:
    def test_policy_values_are_the_campaign_vocabulary(self):
        """The four policies decided in the 2026-07-26 plan (C2), pinned
        as serialized values — a rename here breaks every manifest on
        every operator machine."""
        assert {p.value for p in OwnershipPolicy} == {
            "own", "own-subset", "seed", "operator",
        }

    def test_unknown_policy_fails_validation(self):
        with pytest.raises(ValidationError):
            SurfaceRecord(surface="settings:hooks", policy="dictator")


class TestDefaultManifest:
    def test_default_covers_every_spec_surface(self):
        manifest = OwnershipManifest.default("claude-code")
        spec_surfaces = {
            s.surface: s.policy
            for s in harness_spec.spec_for("claude-code").surfaces
        }
        got = {r.surface: r.policy.value for r in manifest.surfaces}
        assert got == spec_surfaces

    def test_default_never_pretends_an_assert_happened(self):
        manifest = OwnershipManifest.default()
        assert all(r.last_asserted is None for r in manifest.surfaces)
        assert all(r.content_sha256 is None for r in manifest.surfaces)

    def test_default_for_unknown_runtime_raises(self):
        with pytest.raises(ValueError, match="unknown runtime"):
            OwnershipManifest.default("betamax")


class TestLoadManifest:
    def test_round_trip(self, tmp_path):
        path = tmp_path / "ownership.json"
        original = OwnershipManifest.default()
        path.write_text(
            json.dumps(original.model_dump()), encoding="utf-8"
        )
        loaded, error = load_manifest(path)
        assert error is None
        assert loaded == original

    def test_missing_file(self, tmp_path):
        loaded, error = load_manifest(tmp_path / "absent.json")
        assert loaded is None
        assert error == "missing"

    def test_garbage_json(self, tmp_path):
        path = tmp_path / "ownership.json"
        path.write_text("{nope", encoding="utf-8")
        assert load_manifest(path) == (None, "invalid-json")

    def test_valid_json_wrong_schema(self, tmp_path):
        path = tmp_path / "ownership.json"
        path.write_text(
            '{"version": 1, "surfaces": "not-a-list"}', encoding="utf-8"
        )
        assert load_manifest(path) == (None, "invalid-schema")

    def test_unknown_policy_in_file_is_invalid_schema(self, tmp_path):
        path = tmp_path / "ownership.json"
        payload = {
            "version": 1,
            "runtime": "claude-code",
            "surfaces": [{"surface": "settings:hooks", "policy": "dictator"}],
        }
        path.write_text(json.dumps(payload), encoding="utf-8")
        assert load_manifest(path) == (None, "invalid-schema")
