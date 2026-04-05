"""Tests for the Living Specs engine."""

import pytest
from pathlib import Path
import tempfile

from core.specs.schema import (
    Spec, SpecStatus, SpecSection, SpecDelta,
    AcceptanceCriterion, SectionStatus,
)
from core.specs.manager import SpecManager


class TestSpecSchema:
    def test_create_spec(self):
        spec = Spec(id="spec-auth", title="User Authentication", description="OAuth2 auth system")
        assert spec.status == SpecStatus.DRAFT
        assert spec.completion_percentage == 0.0

    def test_add_sections(self):
        spec = Spec(
            id="spec-1", title="Test",
            sections=[
                SpecSection(id="s1", title="Backend API", content="REST endpoints"),
                SpecSection(id="s2", title="Frontend UI", content="Login form"),
            ],
        )
        assert len(spec.sections) == 2
        assert spec.get_section("s1").title == "Backend API"

    def test_completion_percentage(self):
        spec = Spec(
            id="spec-1", title="Test",
            sections=[
                SpecSection(id="s1", title="A", status=SectionStatus.IMPLEMENTED),
                SpecSection(id="s2", title="B", status=SectionStatus.PENDING),
                SpecSection(id="s3", title="C", status=SectionStatus.IMPLEMENTED),
                SpecSection(id="s4", title="D", status=SectionStatus.SKIPPED),
            ],
        )
        assert spec.completion_percentage == 75.0

    def test_add_delta(self):
        spec = Spec(
            id="spec-1", title="Test",
            sections=[SpecSection(id="s1", title="API")],
        )
        delta = spec.add_delta(
            section_id="s1",
            original="REST with JSON",
            actual="GraphQL with SDL",
            reason="Team decided GraphQL is better for this use case",
            decided_by="cto-marco",
        )
        assert delta.section_id == "s1"
        assert spec.delta_count == 1
        assert spec.get_section("s1").status == SectionStatus.MODIFIED

    def test_mark_section_complete(self):
        spec = Spec(
            id="spec-1", title="Test",
            sections=[SpecSection(id="s1", title="API")],
        )
        assert spec.mark_section_complete("s1", notes="Implemented with tests")
        assert spec.get_section("s1").status == SectionStatus.IMPLEMENTED

    def test_verify_criterion(self):
        spec = Spec(
            id="spec-1", title="Test",
            sections=[SpecSection(
                id="s1", title="API",
                acceptance_criteria=[
                    AcceptanceCriterion(id="ac-1", description="Returns 200 on success"),
                    AcceptanceCriterion(id="ac-2", description="Returns 401 without auth"),
                ],
            )],
        )
        assert spec.verify_criterion("s1", "ac-1", True, verified_by="qa-rita")
        assert spec.verify_criterion("s1", "ac-2", True, verified_by="qa-rita")
        assert spec.is_fully_verified

    def test_not_fully_verified_with_pending(self):
        spec = Spec(
            id="spec-1", title="Test",
            sections=[SpecSection(
                id="s1", title="API",
                acceptance_criteria=[
                    AcceptanceCriterion(id="ac-1", description="Test"),
                ],
            )],
        )
        assert not spec.is_fully_verified

    def test_criteria_summary(self):
        spec = Spec(
            id="spec-1", title="Test",
            sections=[SpecSection(
                id="s1", title="API",
                acceptance_criteria=[
                    AcceptanceCriterion(id="ac-1", description="A", status="passed"),
                    AcceptanceCriterion(id="ac-2", description="B", status="failed"),
                    AcceptanceCriterion(id="ac-3", description="C", status="pending"),
                ],
            )],
        )
        summary = spec.criteria_summary
        assert summary["total"] == 3
        assert summary["passed"] == 1
        assert summary["failed"] == 1
        assert summary["pending"] == 1


class TestSpecManager:
    def test_create_spec(self):
        mgr = SpecManager()
        spec = mgr.create(
            "spec-auth", "Authentication",
            project="client_retail", department="dev",
            sections=[
                {"id": "s1", "title": "API", "content": "Endpoints", "acceptance_criteria": ["Returns 200"]},
                {"id": "s2", "title": "UI", "content": "Login form"},
            ],
        )
        assert spec.id == "spec-auth"
        assert len(spec.sections) == 2
        assert len(spec.sections[0].acceptance_criteria) == 1

    def test_lifecycle_draft_to_completed(self):
        mgr = SpecManager()
        spec = mgr.create("spec-1", "Test")

        assert spec.status == SpecStatus.DRAFT
        assert mgr.approve("spec-1", approved_by="user")
        assert spec.status == SpecStatus.APPROVED
        assert mgr.start_implementation("spec-1")
        assert spec.status == SpecStatus.IN_PROGRESS
        assert mgr.complete("spec-1")
        assert spec.status == SpecStatus.COMPLETED

    def test_cannot_approve_in_progress(self):
        mgr = SpecManager()
        spec = mgr.create("spec-1", "Test")
        mgr.approve("spec-1")
        mgr.start_implementation("spec-1")
        assert not mgr.approve("spec-1")  # Already in progress

    def test_cannot_start_unapproved(self):
        mgr = SpecManager()
        mgr.create("spec-1", "Test")
        assert not mgr.start_implementation("spec-1")

    def test_list_by_status(self):
        mgr = SpecManager()
        mgr.create("s1", "Spec 1")
        mgr.create("s2", "Spec 2")
        mgr.approve("s1")

        drafts = mgr.list_all(status=SpecStatus.DRAFT)
        approved = mgr.list_all(status=SpecStatus.APPROVED)
        assert len(drafts) == 1
        assert len(approved) == 1

    def test_save_and_load_yaml(self):
        mgr = SpecManager()
        spec = mgr.create(
            "spec-test", "Test Spec",
            sections=[{"id": "s1", "title": "Section 1", "content": "Content"}],
        )
        spec.add_delta("s1", "original", "actual", "reason")

        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
            path = f.name

        assert mgr.save_to_yaml("spec-test", path)

        mgr2 = SpecManager()
        loaded = mgr2.load_from_yaml(path)
        assert loaded.id == "spec-test"
        assert loaded.title == "Test Spec"
        assert len(loaded.sections) == 1
        assert len(loaded.deltas) == 1

        Path(path).unlink()

    def test_extract_patterns(self):
        mgr = SpecManager()
        spec = mgr.create(
            "spec-1", "Auth Feature",
            department="dev",
            sections=[
                {"id": "s1", "title": "API Design", "content": "REST endpoints for auth"},
                {"id": "s2", "title": "Database", "content": "Users table with RLS"},
            ],
        )
        mgr.approve("spec-1")
        mgr.start_implementation("spec-1")

        # Implement s1 as-is
        spec.mark_section_complete("s1")
        # Implement s2 with modification
        spec.add_delta("s2", "Users table with RLS", "Users table with Policies", "Better Supabase integration")
        spec.mark_section_complete("s2")

        mgr.complete("spec-1")
        patterns = mgr.extract_patterns("spec-1")
        assert len(patterns) == 2
        assert any("API Design" in p for p in patterns)
        assert any("changed to" in p for p in patterns)

    def test_summary(self):
        mgr = SpecManager()
        mgr.create("s1", "A")
        mgr.create("s2", "B")
        mgr.approve("s2")
        s = mgr.summary()
        assert s["total"] == 2
        assert s["by_status"]["draft"] == 1
        assert s["by_status"]["approved"] == 1
