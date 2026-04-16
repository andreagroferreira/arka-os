"""Tests for the workflow dashboard."""

import json
import pytest
from pathlib import Path
from core.workflow.dashboard import (
    WorkflowDashboard,
    format_duration,
    get_elapsed,
    read_state,
)


class TestFormatDuration:
    """Tests for duration formatting."""

    def test_seconds(self):
        assert format_duration(30) == "30s"

    def test_minutes(self):
        assert format_duration(90) == "1m 30s"

    def test_hours(self):
        assert format_duration(3700) == "1h 1m"


class TestGetElapsed:
    """Tests for elapsed time calculation."""

    def test_elapsed_calculation(self):
        iso = "2025-01-01T12:00:00+00:00"
        elapsed = get_elapsed(iso)
        # Should be a positive number of seconds since then
        assert elapsed > 0


class TestWorkflowDashboard:
    """Tests for WorkflowDashboard."""

    def test_inactive_when_no_state(self):
        dashboard = WorkflowDashboard(state=None)
        assert dashboard.is_active() is False

    def test_active_with_state(self):
        state = {
            "workflow": "test",
            "project": "test-project",
            "phases": {},
            "violations": [],
        }
        dashboard = WorkflowDashboard(state=state)
        assert dashboard.is_active() is True

    def test_get_current_phase(self):
        state = {
            "workflow": "test",
            "project": "test-project",
            "phases": {
                "spec": {"status": "completed"},
                "impl": {"status": "in_progress"},
            },
            "violations": [],
        }
        dashboard = WorkflowDashboard(state=state)
        assert dashboard.get_current_phase() == "impl"

    def test_get_violation_count(self):
        state = {
            "workflow": "test",
            "project": "test-project",
            "phases": {},
            "violations": [
                {"rule": "branch-isolation", "detail": "commit on main"},
                {"rule": "context-first", "detail": "CLAUDE.md not read"},
            ],
        }
        dashboard = WorkflowDashboard(state=state)
        assert dashboard.get_violation_count() == 2

    def test_render_output(self):
        state = {
            "workflow": "dev-feature",
            "project": "my-project",
            "started_at": "2025-01-01T12:00:00+00:00",
            "phases": {
                "spec": {"status": "completed"},
                "impl": {"status": "in_progress"},
            },
            "violations": [],
        }
        dashboard = WorkflowDashboard(state=state)
        lines = dashboard.render()
        assert any("ARKAOS WORKFLOW DASHBOARD" in line for line in lines)
        assert any("dev-feature" in line for line in lines)
        assert any("spec" in line for line in lines)
        assert any("impl" in line for line in lines)

    def test_render_with_violations(self):
        state = {
            "workflow": "test",
            "project": "test-project",
            "started_at": "2025-01-01T12:00:00+00:00",
            "phases": {
                "impl": {"status": "completed"},
            },
            "violations": [
                {"rule": "branch-isolation", "detail": "commit on main", "severity": "BLOCK"},
            ],
        }
        dashboard = WorkflowDashboard(state=state)
        lines = dashboard.render()
        assert any("VIOLATIONS (1)" in line for line in lines)
        assert any("🔴" in line for line in lines)

    def test_render_no_state(self):
        dashboard = WorkflowDashboard(state=None)
        lines = dashboard.render()
        assert "No active workflow" in lines


class TestDashboardCLI:
    """Tests for dashboard CLI functions."""

    def test_cmd_status_exits_with_1_when_no_workflow(self, monkeypatch):
        import sys
        from core.workflow import dashboard as dash_module

        monkeypatch.setattr(dash_module, "read_state", lambda: None)
        result = dash_module.cmd_status()
        assert result == 1
