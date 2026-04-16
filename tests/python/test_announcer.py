"""Tests for the phase announcer."""

import pytest
from core.workflow.announcer import PhaseAnnouncer, Announcement, make_announcer


class TestPhaseAnnouncer:
    """Tests for PhaseAnnouncer class."""

    def test_announcer_records_announcements(self):
        output = []
        announcer = PhaseAnnouncer(on_announce=output.append)
        announcer.starting("spec", "Spec Creation")
        assert len(announcer.announcements) == 1
        assert announcer.announcements[0].event == "starting"

    def test_starting_emits_correct_format(self):
        output = []
        announcer = PhaseAnnouncer(on_announce=output.append)
        announcer.starting("spec", "Spec Creation", agents="dev-paulo")
        assert "[PHASE] Starting: Spec Creation" in output[0]
        assert "agents" in output[0]

    def test_completed_emits_with_duration(self):
        output = []
        announcer = PhaseAnnouncer(on_announce=output.append)
        announcer.starting("impl", "Implementation")
        duration = announcer.completed("impl", "Implementation")
        assert duration >= 0
        assert "[PHASE] Completed: Implementation" in output[1]

    def test_failed_emits_correct_format(self):
        output = []
        announcer = PhaseAnnouncer(on_announce=output.append)
        announcer.failed("impl", "Implementation", "Compilation error")
        assert "[PHASE] Failed: Implementation" in output[0]
        assert "Compilation error" in output[0]

    def test_blocked_emits_correct_format(self):
        output = []
        announcer = PhaseAnnouncer(on_announce=output.append)
        announcer.blocked("qa", "QA Review", "waiting for spec")
        assert "[PHASE] Blocked: QA Review" in output[0]
        assert "waiting for" in output[0]

    def test_skipped_emits_correct_format(self):
        output = []
        announcer = PhaseAnnouncer(on_announce=output.append)
        announcer.skipped("docs", "Documentation", "auto-generated")
        assert "[PHASE] Skipped: Documentation" in output[0]
        assert "auto-generated" in output[0]

    def test_workflow_start_emits(self):
        output = []
        announcer = PhaseAnnouncer(on_announce=output.append)
        announcer.workflow_start("Feature Workflow", 5, "enterprise")
        assert "[WORKFLOW] Starting: Feature Workflow" in output[0]
        assert "5 phases" in output[0]

    def test_workflow_complete_emits(self):
        output = []
        announcer = PhaseAnnouncer(on_announce=output.append)
        announcer.workflow_complete("Feature Workflow", 12345)
        assert "[WORKFLOW] Completed: Feature Workflow" in output[0]
        assert "12345ms" in output[0]

    def test_get_phase_announcements(self):
        announcer = PhaseAnnouncer(on_announce=lambda x: None)
        announcer.starting("spec", "Spec Creation")
        announcer.completed("spec", "Spec Creation")
        start_ann, complete_ann = announcer.get_phase_announcements("spec")
        assert start_ann is not None
        assert complete_ann is not None
        assert start_ann.event == "starting"
        assert complete_ann.event == "completed"

    def test_validate_phase_completion(self):
        announcer = PhaseAnnouncer(on_announce=lambda x: None)
        announcer.starting("spec", "Spec Creation")
        announcer.completed("spec", "Spec Creation")
        assert announcer.validate_phase_completion("spec") is True

    def test_validate_phase_incomplete(self):
        announcer = PhaseAnnouncer(on_announce=lambda x: None)
        announcer.starting("spec", "Spec Creation")
        assert announcer.validate_phase_completion("spec") is False

    def test_get_total_duration_ms(self):
        announcer = PhaseAnnouncer(on_announce=lambda x: None)
        announcer.starting("p1", "Phase 1")
        announcer.completed("p1", "Phase 1")
        announcer.starting("p2", "Phase 2")
        announcer.completed("p2", "Phase 2")
        assert announcer.get_total_duration_ms() >= 0

    def test_make_announcer_factory(self):
        output = []
        announcer = make_announcer(on_announce=output.append)
        announcer.starting("test", "Test Phase")
        assert len(output) == 1


class TestAnnouncement:
    """Tests for Announcement dataclass."""

    def test_announcement_fields(self):
        ann = Announcement(
            phase_id="spec",
            phase_name="Spec Creation",
            event="starting",
            duration_ms=1000,
            metadata={"agents": "dev-paulo"},
        )
        assert ann.phase_id == "spec"
        assert ann.phase_name == "Spec Creation"
        assert ann.event == "starting"
        assert ann.duration_ms == 1000
        assert ann.metadata["agents"] == "dev-paulo"
