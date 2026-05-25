"""Tests for /api/health PR70 v2.87.0 — severity + timestamp."""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_API_PATH = REPO_ROOT / "scripts" / "dashboard-api.py"


@pytest.fixture(scope="module")
def dashboard_module():
    spec = importlib.util.spec_from_file_location("dashboard_api", DASHBOARD_API_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["dashboard_api"] = module
    spec.loader.exec_module(module)
    return module


class TestHealthEndpoint:
    def test_includes_ts_iso_timestamp(self, dashboard_module):
        result = dashboard_module.health()
        assert "ts" in result
        # Must round-trip through fromisoformat
        parsed = datetime.fromisoformat(result["ts"])
        assert parsed.tzinfo is not None

    def test_includes_aggregate_fields(self, dashboard_module):
        result = dashboard_module.health()
        for key in (
            "checks", "passed", "total",
            "failed_blocking", "warning_count", "healthy",
        ):
            assert key in result, f"missing {key}"

    def test_each_check_has_severity(self, dashboard_module):
        result = dashboard_module.health()
        for c in result["checks"]:
            assert "severity" in c
            assert c["severity"] in {"fail", "warn"}

    def test_each_check_has_required_fields(self, dashboard_module):
        result = dashboard_module.health()
        for c in result["checks"]:
            assert "name" in c
            assert "passed" in c
            assert isinstance(c["passed"], bool)
            assert "fix" in c

    def test_warn_checks_dont_count_as_blocking(self, dashboard_module):
        result = dashboard_module.health()
        # failed_blocking only counts severity=fail checks that didn't pass
        manual_blocking = sum(
            1 for c in result["checks"]
            if not c["passed"] and c["severity"] == "fail"
        )
        assert result["failed_blocking"] == manual_blocking

    def test_warning_count_matches_failed_warns(self, dashboard_module):
        result = dashboard_module.health()
        manual_warns = sum(
            1 for c in result["checks"]
            if not c["passed"] and c["severity"] == "warn"
        )
        assert result["warning_count"] == manual_warns

    def test_healthy_iff_no_blocking_failures(self, dashboard_module):
        """`healthy` ignores warnings — a warn-only env should still be healthy."""
        result = dashboard_module.health()
        assert result["healthy"] is (result["failed_blocking"] == 0)

    def test_known_warn_severities(self, dashboard_module):
        """knowledge_db + profile are deliberately warn-only."""
        result = dashboard_module.health()
        by_name = {c["name"]: c for c in result["checks"]}
        assert by_name.get("knowledge_db", {}).get("severity") == "warn"
        assert by_name.get("profile", {}).get("severity") == "warn"

    def test_constitution_check_is_blocking(self, dashboard_module):
        """Constitution is non-optional — must be fail-severity."""
        result = dashboard_module.health()
        by_name = {c["name"]: c for c in result["checks"]}
        assert by_name.get("constitution", {}).get("severity") == "fail"
