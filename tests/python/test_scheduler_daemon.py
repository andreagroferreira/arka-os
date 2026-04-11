"""Tests for ArkaScheduler and ScheduleConfig."""

import sys
from datetime import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from core.cognition.scheduler import ArkaScheduler, ScheduleConfig
from core.cognition.scheduler.cli import list_schedules, run_now, scheduler_status


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

        # Create a fake claude binary in a known location
        fake_claude = tmp_path / ".local" / "bin" / "claude"
        fake_claude.parent.mkdir(parents=True)
        fake_claude.write_text("#!/bin/sh\n")
        fake_claude.chmod(0o755)

        with patch.object(Path, "home", return_value=tmp_path):
            cmd = scheduler._build_command(schedule)

        assert str(fake_claude) == cmd[0]
        assert "--dangerously-skip-permissions" in cmd
        assert "-p" in cmd
        assert "dream about the future" in cmd

    def test_resolve_claude_binary_fallback_to_which(
        self, scheduler: ArkaScheduler, tmp_path: Path
    ) -> None:
        """Falls back to shutil.which when known paths don't exist."""
        with (
            patch.object(Path, "home", return_value=tmp_path),
            patch("shutil.which", side_effect=lambda x: "/usr/bin/claude" if x == "claude" else None),
        ):
            result = ArkaScheduler._resolve_claude_binary()
        assert result == "/usr/bin/claude"

    def test_resolve_claude_binary_raises_when_missing(
        self, scheduler: ArkaScheduler, tmp_path: Path
    ) -> None:
        """Raises FileNotFoundError when claude is nowhere to be found."""
        with (
            patch.object(Path, "home", return_value=tmp_path),
            patch("shutil.which", return_value=None),
        ):
            with pytest.raises(FileNotFoundError, match="Claude CLI not found"):
                ArkaScheduler._resolve_claude_binary()

    def test_daemon_env_includes_claude_paths(self, scheduler: ArkaScheduler) -> None:
        """_daemon_env PATH must include .local/bin and .arkaos/bin."""
        env = scheduler._daemon_env()
        assert ".local/bin" in env["PATH"]
        assert ".arkaos/bin" in env["PATH"]
        assert "/usr/local/bin" in env["PATH"]

    def test_execute_success(self, scheduler: ArkaScheduler, tmp_path: Path) -> None:
        """execute returns True when the subprocess exits 0."""
        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("test prompt")
        schedule = ScheduleConfig(
            command="test_cmd", prompt_file=str(prompt_file), run_time=time(2, 0),
        )

        fake_result = MagicMock(returncode=0)
        with (
            patch.object(scheduler, "_resolve_claude_binary", return_value="/bin/echo"),
            patch("subprocess.run", return_value=fake_result),
        ):
            assert scheduler.execute(schedule) is True

        log = (tmp_path / "logs" / "test_cmd").glob("*.log")
        assert any(log)

    def test_execute_retries_on_failure(self, scheduler: ArkaScheduler, tmp_path: Path) -> None:
        """execute retries up to max_retries on non-zero exit codes."""
        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("test")
        schedule = ScheduleConfig(
            command="retry_cmd", prompt_file=str(prompt_file),
            run_time=time(2, 0), retry_on_fail=True, max_retries=2,
        )

        fail_result = MagicMock(returncode=1)
        with (
            patch.object(scheduler, "_resolve_claude_binary", return_value="/bin/false"),
            patch("subprocess.run", return_value=fail_result),
            patch("time.sleep"),  # Skip actual backoff
        ):
            assert scheduler.execute(schedule) is False

    def test_execute_backoff_delay(self, scheduler: ArkaScheduler, tmp_path: Path) -> None:
        """Retry backoff increases: 30s after first fail, 60s after second."""
        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("test")
        schedule = ScheduleConfig(
            command="backoff_cmd", prompt_file=str(prompt_file),
            run_time=time(2, 0), retry_on_fail=True, max_retries=2,
        )

        fail_result = MagicMock(returncode=1)
        sleep_calls = []
        with (
            patch.object(scheduler, "_resolve_claude_binary", return_value="/bin/false"),
            patch("subprocess.run", return_value=fail_result),
            patch("time.sleep", side_effect=lambda d: sleep_calls.append(d)),
        ):
            scheduler.execute(schedule)

        assert sleep_calls == [30, 60]

    def test_execute_returns_false_when_claude_missing(
        self, scheduler: ArkaScheduler, tmp_path: Path,
    ) -> None:
        """execute returns False and logs FATAL when claude binary not found."""
        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("test")
        schedule = ScheduleConfig(
            command="missing_cmd", prompt_file=str(prompt_file), run_time=time(2, 0),
        )

        with patch.object(
            scheduler, "_resolve_claude_binary",
            side_effect=FileNotFoundError("Claude CLI not found"),
        ):
            assert scheduler.execute(schedule) is False

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


# ---------------------------------------------------------------------------
# TestSchedulerCLI
# ---------------------------------------------------------------------------

CLI_SCHEDULE_YAML = {
    "schedules": {
        "dreaming": {
            "command": "dreaming",
            "prompt_file": "PROMPT_FILE_PLACEHOLDER",
            "time": "02:00",
            "enabled": True,
            "retry_on_fail": True,
            "max_retries": 2,
            "timeout_minutes": 60,
        },
        "research": {
            "command": "research",
            "prompt_file": "PROMPT_FILE_PLACEHOLDER",
            "time": "05:00",
            "enabled": True,
            "retry_on_fail": True,
            "max_retries": 1,
            "timeout_minutes": 90,
        },
    }
}


@pytest.fixture()
def cli_fixture(tmp_path: Path):
    """Temp schedules.yaml with 2 schedules and a real prompt file."""
    prompt_file = tmp_path / "prompt.md"
    prompt_file.write_text("think deeply")

    yaml_data = {
        "schedules": {
            name: {**cfg, "prompt_file": str(prompt_file)}
            for name, cfg in CLI_SCHEDULE_YAML["schedules"].items()
        }
    }
    yaml_file = tmp_path / "schedules.yaml"
    yaml_file.write_text(yaml.dump(yaml_data))

    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    lock_path = tmp_path / "arkascheduler.lock"

    return {
        "config_path": str(yaml_file),
        "log_dir": str(log_dir),
        "lock_path": str(lock_path),
        "tmp_path": tmp_path,
    }


class TestSchedulerCLI:
    def test_list_schedules(self, cli_fixture: dict) -> None:
        """list_schedules returns 2 items with correct command names."""
        result = list_schedules(cli_fixture["config_path"])

        assert len(result) == 2
        commands = {item["command"] for item in result}
        assert commands == {"dreaming", "research"}

        dreaming = next(item for item in result if item["command"] == "dreaming")
        assert dreaming["time"] == "02:00"
        assert dreaming["timeout"] == 60
        assert dreaming["retry"] is True

        research = next(item for item in result if item["command"] == "research")
        assert research["time"] == "05:00"
        assert research["timeout"] == 90

    def test_status_output(self, cli_fixture: dict) -> None:
        """scheduler_status output contains schedule commands, times, and status."""
        output = scheduler_status(
            config_path=cli_fixture["config_path"],
            log_dir=cli_fixture["log_dir"],
            lock_path=cli_fixture["lock_path"],
        )

        assert "dreaming" in output
        assert "research" in output
        assert "02:00" in output
        assert "05:00" in output
        assert "STOPPED" in output
        assert "Last runs:" in output
        assert "never" in output

    def test_status_shows_running_when_lock_exists(self, cli_fixture: dict) -> None:
        """scheduler_status shows RUNNING when the lock file is present."""
        Path(cli_fixture["lock_path"]).touch()

        output = scheduler_status(
            config_path=cli_fixture["config_path"],
            log_dir=cli_fixture["log_dir"],
            lock_path=cli_fixture["lock_path"],
        )

        assert "RUNNING" in output

    def test_run_now_raises_for_unknown_command(self, cli_fixture: dict) -> None:
        """run_now raises ValueError for an unrecognised command."""
        with pytest.raises(ValueError, match="unknown_cmd"):
            run_now(
                command="unknown_cmd",
                config_path=cli_fixture["config_path"],
                log_dir=cli_fixture["log_dir"],
                lock_path=cli_fixture["lock_path"],
            )
