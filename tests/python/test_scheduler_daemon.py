"""Tests for ArkaScheduler and ScheduleConfig."""

import sys
from datetime import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from core.cognition.scheduler import ArkaScheduler, ScheduleConfig


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

SCHEDULE_YAML = {
    "schedules": {
        "dreaming": {
            "command": "dreaming",
            "prompt_file": "~/.arkaos/cognition/prompts/dreaming.md",
            "time": "02:00",
            "enabled": True,
            "retry_on_fail": True,
            "max_retries": 2,
            "timeout_minutes": 60,
        },
        "reflection": {
            "command": "reflection",
            "prompt_file": "~/.arkaos/cognition/prompts/reflection.md",
            "time": "06:30",
            "enabled": True,
            "retry_on_fail": False,
            "max_retries": 0,
            "timeout_minutes": 30,
        },
        "disabled_task": {
            "command": "disabled_task",
            "prompt_file": "~/.arkaos/cognition/prompts/disabled.md",
            "time": "12:00",
            "enabled": False,
        },
    }
}


@pytest.fixture()
def schedule_yaml_path(tmp_path: Path) -> str:
    """Write the YAML fixture to a temp file and return its path."""
    yaml_file = tmp_path / "schedules.yaml"
    yaml_file.write_text(yaml.dump(SCHEDULE_YAML))
    return str(yaml_file)


@pytest.fixture()
def scheduler(schedule_yaml_path: str, tmp_path: Path) -> ArkaScheduler:
    """Return an ArkaScheduler wired to temp directories."""
    return ArkaScheduler(
        config_path=schedule_yaml_path,
        log_dir=str(tmp_path / "logs"),
        lock_path=str(tmp_path / "arkascheduler.lock"),
    )


# ---------------------------------------------------------------------------
# TestScheduleConfig
# ---------------------------------------------------------------------------

class TestScheduleConfig:
    def test_load_from_yaml(self, schedule_yaml_path: str) -> None:
        """Loads two enabled schedules with correct times and timeouts."""
        schedules = ScheduleConfig.load(schedule_yaml_path)
        assert len(schedules) == 2  # disabled_task excluded

        dreaming = next(s for s in schedules if s.command == "dreaming")
        assert dreaming.run_time == time(2, 0)
        assert dreaming.timeout_minutes == 60
        assert dreaming.max_retries == 2
        assert dreaming.retry_on_fail is True

        reflection = next(s for s in schedules if s.command == "reflection")
        assert reflection.run_time == time(6, 30)
        assert reflection.timeout_minutes == 30
        assert reflection.max_retries == 0
        assert reflection.retry_on_fail is False

    def test_disabled_schedule_excluded(self, schedule_yaml_path: str) -> None:
        """Disabled schedules must not appear in the loaded list."""
        schedules = ScheduleConfig.load(schedule_yaml_path)
        commands = [s.command for s in schedules]
        assert "disabled_task" not in commands


# ---------------------------------------------------------------------------
# TestArkaScheduler
# ---------------------------------------------------------------------------

class TestArkaScheduler:
    def test_loads_schedules(self, scheduler: ArkaScheduler) -> None:
        """Scheduler should load exactly 2 enabled schedules."""
        assert len(scheduler.schedules) == 2

    def test_should_run_at_correct_time(self, scheduler: ArkaScheduler) -> None:
        """_should_run returns True for matching HH:MM, False otherwise."""
        dreaming = next(s for s in scheduler.schedules if s.command == "dreaming")

        matching = time(2, 0)
        non_matching = time(3, 0)
        also_non_matching = time(2, 1)

        assert scheduler._should_run(dreaming, matching) is True
        assert scheduler._should_run(dreaming, non_matching) is False
        assert scheduler._should_run(dreaming, also_non_matching) is False

    def test_build_claude_command(
        self, scheduler: ArkaScheduler, tmp_path: Path
    ) -> None:
        """Built command must include 'claude' binary and skip-permissions flag."""
        prompt_file = tmp_path / "dreaming.md"
        prompt_file.write_text("dream about the future")

        schedule = ScheduleConfig(
            command="dreaming",
            prompt_file=str(prompt_file),
            run_time=time(2, 0),
        )

        with patch("shutil.which", return_value="/usr/local/bin/claude"):
            cmd = scheduler._build_command(schedule)

        assert "claude" in cmd[0]
        assert "--dangerously-skip-permissions" in cmd
        assert "-p" in cmd
        assert "dream about the future" in cmd

    def test_lock_prevents_duplicate(
        self, scheduler: ArkaScheduler, tmp_path: Path
    ) -> None:
        """A second ArkaScheduler instance must fail to acquire the same lock."""
        second = ArkaScheduler(
            config_path=scheduler._config_path,
            log_dir=str(tmp_path / "logs2"),
            lock_path=scheduler._lock_path,
        )

        acquired_first = scheduler.acquire_lock()
        try:
            assert acquired_first is True
            acquired_second = second.acquire_lock()
            assert acquired_second is False
        finally:
            scheduler.release_lock()
