"""Tests for core.knowledge.recipes + recipes_cli (Interaction Reform PR7).

Confidentiality is the load-bearing property: capture is fail-closed on
a missing redaction config, and every field/file is sanitized. All state
under tmp via ARKA_RECIPES_DIR; redaction config via ARKA_REDACTION env
of the sanitizer.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from core.evals.sanitizer import SanitizerConfigMissing
from core.knowledge.recipes import (
    Recipe,
    RecipeCaptureRefused,
    RecipeProvenance,
    capture_recipe,
    list_recipes,
    load_recipe,
)
from core.knowledge.recipes_cli import main as cli_main


@pytest.fixture(autouse=True)
def _isolated_recipes(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKA_RECIPES_DIR", str(tmp_path / "recipes"))


@pytest.fixture()
def redaction_config(tmp_path):
    config = tmp_path / "redaction-clients.json"
    config.write_text(
        json.dumps({"clients": ["acme corp", "globex"]}), encoding="utf-8"
    )
    return config


def _recipe(slug: str = "laravel-token-auth") -> Recipe:
    return Recipe(
        slug=slug,
        name="Laravel token auth",
        problem="Standard token login+refresh done the ArkaOS-approved way.",
        stack=["laravel", "php"],
        feature_keywords=["auth", "login", "token", "refresh"],
        acceptance_criteria=["FormRequest validation", "refresh invalidates old"],
        apply_notes="Swap the User model namespace per project.",
        provenance=RecipeProvenance(
            source_project="arkaos",
            qg_verdict="APPROVED",
            qg_verdict_ts="2026-07-09T18:00:00+00:00",
            captured_at="2026-07-09T18:05:00+00:00",
            department="dev",
        ),
    )


class TestSchema:
    def test_unsafe_slug_rejected(self):
        with pytest.raises(ValidationError):
            _recipe(slug="../../evil")

    def test_verdict_must_be_approved(self):
        with pytest.raises(ValidationError):
            RecipeProvenance(
                source_project="x", qg_verdict="REJECTED",
                qg_verdict_ts="t", captured_at="t",
            )

    def test_stack_and_keywords_required(self):
        with pytest.raises(ValidationError):
            Recipe(
                slug="x", name="n", problem="a long enough problem",
                stack=[], feature_keywords=["k"],
                provenance=_recipe().provenance,
            )


class TestCaptureFailClosed:
    def test_missing_redaction_config_refuses(self, tmp_path):
        with pytest.raises(SanitizerConfigMissing):
            capture_recipe(
                _recipe(), narrative="a narrative",
                reference_files={"AuthService.php": "<?php // code"},
                config_path=tmp_path / "absent.json",
            )
        assert list_recipes() == []

    def test_non_approved_verdict_refused_before_write(self, tmp_path):
        recipe = _recipe()
        # Force a non-APPROVED verdict past the schema by model_construct.
        recipe.provenance.qg_verdict = "REJECTED"  # type: ignore[assignment]
        with pytest.raises(RecipeCaptureRefused, match="APPROVED"):
            capture_recipe(recipe, "n", {"f.php": "x"},
                           config_path=tmp_path / "absent.json")

    def test_oversize_file_set_refused(self, redaction_config):
        files = {f"f{i}.php": "x" for i in range(21)}
        with pytest.raises(RecipeCaptureRefused, match="cap"):
            capture_recipe(_recipe(), "n", files,
                           config_path=redaction_config)

    def test_path_traversal_reference_refused(self, redaction_config):
        for bad in ("../escape.php", "/etc/passwd", "a\\b.php",
                    ".hidden", "sub/../../out.php", "./x.php"):
            with pytest.raises(RecipeCaptureRefused, match="unsafe"):
                capture_recipe(
                    _recipe(), "n", {bad: "x"},
                    config_path=redaction_config,
                )


class TestCaptureAndRedaction:
    def test_capture_redacts_client_identifiers_in_every_field(
        self, redaction_config
    ):
        # QG blocker (2026-07-09): name, feature_keywords, acceptance
        # criteria and provenance.source_project reach recipe.json and
        # MUST be sanitized too — not only problem/apply_notes/files.
        recipe = _recipe()
        recipe.name = "Acme Corp auth flow"
        recipe.problem = "Built for Acme Corp — token auth done right here."
        recipe.apply_notes = "Deployed at Globex too."
        recipe.stack = ["laravel", "acme corp"]  # stack is free text too
        recipe.feature_keywords = ["auth", "acme corp"]
        recipe.acceptance_criteria = ["Globex sign-off obtained"]
        recipe.provenance.source_project = "acme corp"
        target = capture_recipe(
            recipe,
            narrative="Acme Corp needed a login; Globex reused it.",
            reference_files={"AuthService.php": "// client: Acme Corp"},
            config_path=redaction_config,
        )
        stored = load_recipe(recipe.slug)
        assert stored is not None
        assert stored.sanitized is True
        # No client identifier survives in ANY field of the stored JSON.
        raw_json = (target / "recipe.json").read_text(encoding="utf-8")
        assert "Acme" not in raw_json and "Globex" not in raw_json
        assert "acme" not in raw_json.lower().replace("[client", "")
        assert stored.name == "[CLIENT-1] auth flow"
        assert stored.provenance.source_project == "[CLIENT-1]"
        assert "[CLIENT-1]" in stored.feature_keywords
        assert "[CLIENT-1]" in stored.stack
        narrative = (target / "RECIPE.md").read_text(encoding="utf-8")
        assert "Acme" not in narrative and "Globex" not in narrative
        file_body = (target / "files" / "AuthService.php").read_text(
            encoding="utf-8"
        )
        assert "Acme" not in file_body

    def test_reference_filename_with_client_identifier_refused(
        self, redaction_config
    ):
        # A filename cannot be silently rewritten to [CLIENT-N].php —
        # capture refuses so the operator renames it (QG 2026-07-09).
        with pytest.raises(RecipeCaptureRefused, match="client identifier"):
            capture_recipe(
                _recipe(),
                narrative="n",
                reference_files={"GlobexAuthService.php": "// code"},
                config_path=redaction_config,
            )

    def test_capture_then_list_and_show(self, redaction_config):
        capture_recipe(_recipe(), "n", {"f.php": "// x"},
                       config_path=redaction_config)
        recipes = list_recipes()
        assert len(recipes) == 1
        assert recipes[0].slug == "laravel-token-auth"


class TestCli:
    def test_capture_exit_2_without_redaction_config(
        self, tmp_path, monkeypatch, capsys
    ):
        monkeypatch.setattr(
            "core.governance.leak_scanner._DEFAULT_CONFIG_PATH",
            tmp_path / "absent.json",
        )
        spec = tmp_path / "spec.json"
        spec.write_text(json.dumps({
            "recipe": json.loads(_recipe().model_dump_json()),
            "narrative": "n",
            "files": {"f.php": "x"},
        }), encoding="utf-8")
        assert cli_main(["capture", "--spec", str(spec)]) == 2
        assert "capture refused" in capsys.readouterr().err

    def test_capture_invalid_spec_exit_1(self, tmp_path, capsys):
        spec = tmp_path / "bad.json"
        spec.write_text("{not json", encoding="utf-8")
        assert cli_main(["capture", "--spec", str(spec)]) == 1
        assert "invalid recipe spec" in capsys.readouterr().err

    def test_show_unknown_exit_1(self, capsys):
        assert cli_main(["show", "nope"]) == 1
