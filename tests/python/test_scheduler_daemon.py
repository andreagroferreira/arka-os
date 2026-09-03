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
    yaml_file.write_text(yaml.dump(SCHEDULE_YAML), encoding="utf-8")
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

    def test_load_goal_and_task_budget_fields(self, tmp_path: Path) -> None:
        """PR54 v2.71.0 — YAML loader reads goal_condition + task_budget
        when present, leaves them None when absent."""
        yaml_file = tmp_path / "schedules.yaml"
        yaml_file.write_text(yaml.dump({
            "schedules": {
                "with_goal": {
                    "command": "research",
                    "prompt_file": "~/r.md",
                    "time": "05:00",
                    "goal_condition": "briefing on disk AND json log exists",
                    "task_budget": 15,
                },
                "without_goal": {
                    "command": "dreaming",
                    "prompt_file": "~/d.md",
                    "time": "02:00",
                },
            }
        }), encoding="utf-8")
        schedules = ScheduleConfig.load(str(yaml_file))
        with_goal = next(s for s in schedules if s.command == "research")
        without_goal = next(s for s in schedules if s.command == "dreaming")
        assert with_goal.goal_condition == "briefing on disk AND json log exists"
        assert with_goal.task_budget == 15
        assert without_goal.goal_condition is None
        assert without_goal.task_budget is None


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
        prompt_file.write_text("dream about the future", encoding="utf-8")

        schedule = ScheduleConfig(
            command="dreaming",
            prompt_file=str(prompt_file),
            run_time=time(2, 0),
        )

        # Create a fake claude binary in a known location
        fake_claude = tmp_path / ".local" / "bin" / "claude"
        fake_claude.parent.mkdir(parents=True)
        fake_claude.write_text("#!/bin/sh\n", encoding="utf-8")
        fake_claude.chmod(0o755)

        with patch.object(Path, "home", return_value=tmp_path):
            cmd = scheduler._build_command(schedule)

        assert str(fake_claude) == cmd[0]
        assert "--dangerously-skip-permissions" in cmd
        assert "-p" in cmd
        assert "dream about the future" in cmd

    def test_legacy_claude_p_emits_metered_billing_warning(
        self, scheduler: ArkaScheduler, tmp_path: Path, capsys
    ) -> None:
        """PR52 v2.68.0 — operator must be warned the legacy claude -p path
        hits the metered $200 pool after 2026-06-15. Warning is one-time
        per schedule (marker under ~/.arkaos/telemetry/)."""
        prompt_file = tmp_path / "dreaming.md"
        prompt_file.write_text("dream about the future", encoding="utf-8")
        fake_claude = tmp_path / ".local" / "bin" / "claude"
        fake_claude.parent.mkdir(parents=True)
        fake_claude.write_text("#!/bin/sh\n", encoding="utf-8")
        fake_claude.chmod(0o755)
        schedule = ScheduleConfig(
            command="legacy-dreaming",
            prompt_file=str(prompt_file),
            run_time=time(2, 0),
        )
        with patch.object(Path, "home", return_value=tmp_path):
            scheduler._build_command(schedule)
            err = capsys.readouterr().err
            assert "2026-06-15" in err
            assert "legacy-dreaming" in err
            # Second invocation should NOT emit (marker exists)
            scheduler._build_command(schedule)
            err2 = capsys.readouterr().err
            assert err2 == ""

    def test_goal_condition_appends_goal_and_budget_flags(
        self, scheduler: ArkaScheduler, tmp_path: Path
    ) -> None:
        """PR54 v2.71.0 — goal_condition + task_budget produce the
        `--goal <cond> --task-budget <N>` argv suffix."""
        prompt_file = tmp_path / "research.md"
        prompt_file.write_text("# research prompt", encoding="utf-8")
        fake_claude = tmp_path / ".local" / "bin" / "claude"
        fake_claude.parent.mkdir(parents=True)
        fake_claude.write_text("#!/bin/sh\n", encoding="utf-8")
        fake_claude.chmod(0o755)
        schedule = ScheduleConfig(
            command="research",
            prompt_file=str(prompt_file),
            run_time=time(5, 0),
            goal_condition=(
                "Today's Research briefing is on disk AND the JSON log exists"
            ),
            task_budget=12,
        )
        with patch.object(Path, "home", return_value=tmp_path):
            cmd = scheduler._build_command(schedule)
        assert "--goal" in cmd
        idx = cmd.index("--goal")
        assert cmd[idx + 1] == (
            "Today's Research briefing is on disk AND the JSON log exists"
        )
        assert "--task-budget" in cmd
        assert cmd[cmd.index("--task-budget") + 1] == "12"

    def test_goal_without_task_budget_raises(
        self, scheduler: ArkaScheduler, tmp_path: Path
    ) -> None:
        """Pairing --goal with --task-budget is mandatory. Setting one
        without the other must fail loudly rather than silently dropping
        the goal or the budget."""
        prompt_file = tmp_path / "x.md"
        prompt_file.write_text("x", encoding="utf-8")
        fake_claude = tmp_path / ".local" / "bin" / "claude"
        fake_claude.parent.mkdir(parents=True)
        fake_claude.write_text("#!/bin/sh\n", encoding="utf-8")
        fake_claude.chmod(0o755)
        schedule = ScheduleConfig(
            command="bad",
            prompt_file=str(prompt_file),
            run_time=time(2, 0),
            goal_condition="something",
            task_budget=None,
        )
        with (
            patch.object(Path, "home", return_value=tmp_path),
            pytest.raises(ValueError, match="task_budget"),
        ):
            scheduler._build_command(schedule)

    def test_no_goal_condition_yields_legacy_argv(
        self, scheduler: ArkaScheduler, tmp_path: Path
    ) -> None:
        """When goal_condition is unset, argv must not gain --goal nor
        --task-budget. Pre-PR54 schedules stay byte-identical."""
        prompt_file = tmp_path / "x.md"
        prompt_file.write_text("legacy prompt", encoding="utf-8")
        fake_claude = tmp_path / ".local" / "bin" / "claude"
        fake_claude.parent.mkdir(parents=True)
        fake_claude.write_text("#!/bin/sh\n", encoding="utf-8")
        fake_claude.chmod(0o755)
        schedule = ScheduleConfig(
            command="legacy",
            prompt_file=str(prompt_file),
            run_time=time(2, 0),
        )
        with patch.object(Path, "home", return_value=tmp_path):
            cmd = scheduler._build_command(schedule)
        assert "--goal" not in cmd
        assert "--task-budget" not in cmd

    def test_python_module_path_does_not_emit_metered_warning(
        self, scheduler: ArkaScheduler, tmp_path: Path, capsys
    ) -> None:
        """python_module path is the migration target — never warn for it."""
        schedule = ScheduleConfig(
            command="dreaming-v2",
            prompt_file="/unused",
            run_time=time(2, 0),
            python_module="core.cognition.dreaming",
        )
        with patch.object(Path, "home", return_value=tmp_path):
            scheduler._build_command(schedule)
        err = capsys.readouterr().err
        assert "2026-06-15" not in err

    def test_resolve_claude_binary_fallback_to_which(
        self, scheduler: ArkaScheduler, tmp_path: Path
    ) -> None:
        """Falls back to shutil.which when known paths don't exist."""
        which = {"claude": "/usr/bin/claude"}
        with (
            patch.object(Path, "home", return_value=tmp_path),
            patch("shutil.which", side_effect=which.get),
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
            pytest.raises(FileNotFoundError, match="Claude CLI not found"),
        ):
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
        prompt_file.write_text("test prompt", encoding="utf-8")
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

    def test_execute_spawns_child_without_a_console(
        self, scheduler: ArkaScheduler, tmp_path: Path,
    ) -> None:
        """The child must never be handed a console window of its own.

        The daemon runs under pythonw.exe and owns no console, so a
        console-subsystem child (the claude CLI, on the prompt_file path)
        would otherwise get a fresh window. It shows nothing -- stdout goes
        to the task log -- so the operator closes it and kills the run with
        0xC000013A.
        """
        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("test prompt", encoding="utf-8")
        schedule = ScheduleConfig(
            command="test_cmd", prompt_file=str(prompt_file), run_time=time(2, 0),
        )

        fake_result = MagicMock(returncode=0)
        with (
            patch.object(scheduler, "_resolve_claude_binary", return_value="/bin/echo"),
            patch("subprocess.run", return_value=fake_result) as run_mock,
        ):
            assert scheduler.execute(schedule) is True

        expected = 0x08000000 if sys.platform == "win32" else 0
        assert run_mock.call_args.kwargs["creationflags"] == expected

    def test_execute_retries_on_failure(self, scheduler: ArkaScheduler, tmp_path: Path) -> None:
        """execute retries up to max_retries on non-zero exit codes."""
        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("test", encoding="utf-8")
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
        prompt_file.write_text("test", encoding="utf-8")
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
        prompt_file.write_text("test", encoding="utf-8")
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
    prompt_file.write_text("think deeply", encoding="utf-8")

    yaml_data = {
        "schedules": {
            name: {**cfg, "prompt_file": str(prompt_file)}
            for name, cfg in CLI_SCHEDULE_YAML["schedules"].items()
        }
    }
    yaml_file = tmp_path / "schedules.yaml"
    yaml_file.write_text(yaml.dump(yaml_data), encoding="utf-8")

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


# ---------------------------------------------------------------------------
# Runtime Sync PR3 — model pin and fallback chain
# ---------------------------------------------------------------------------


import re as _re  # noqa: E402 — appended section keeps the module's import block intact

from core.runtime.claude_code import DEFAULT_FALLBACK_MODELS  # noqa: E402
from core.runtime.model_router import ResolvedModel  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]


def _fake_binary(tmp_path: Path) -> Path:
    fake_claude = tmp_path / ".local" / "bin" / "claude"
    fake_claude.parent.mkdir(parents=True, exist_ok=True)
    fake_claude.write_text("#!/bin/sh\n", encoding="utf-8")
    fake_claude.chmod(0o755)
    return fake_claude


def _prompt(tmp_path: Path) -> Path:
    prompt_file = tmp_path / "research.md"
    prompt_file.write_text("# research prompt", encoding="utf-8")
    return prompt_file


def _fabric(model: str, provider: str = "runtime") -> ResolvedModel:
    return ResolvedModel(
        role="strategy", provider=provider, model=model, effort="max", source="test"
    )


def _flag(cmd: list[str], flag: str) -> str | None:
    return cmd[cmd.index(flag) + 1] if flag in cmd else None


class TestModelPinAndFallback:
    """The nightly cycle no longer dies on one overload or model 404."""

    def test_default_chain_is_the_shared_constant(self) -> None:
        assert DEFAULT_FALLBACK_MODELS == ("claude-opus-5", "claude-sonnet-5")
        schedule = ScheduleConfig(command="x", prompt_file="/x", run_time=time(2, 0))
        assert schedule.model is None
        assert schedule.fallback_models == list(DEFAULT_FALLBACK_MODELS)

    def test_js_seed_carries_the_same_chain(self) -> None:
        """installer/fallback-model.js and the Python constant are two copies
        of one truth — parse the JS rather than trust a comment."""
        source = (REPO_ROOT / "installer" / "fallback-model.js").read_text(encoding="utf-8")
        match = _re.search(r"export const DEFAULT_FALLBACK_MODELS = \[(.*?)\];", source)
        assert match, "DEFAULT_FALLBACK_MODELS not found in installer/fallback-model.js"
        assert tuple(_re.findall(r'"([^"]+)"', match.group(1))) == DEFAULT_FALLBACK_MODELS

    def test_yaml_keys_are_read_and_defaulted(self, tmp_path: Path) -> None:
        data = {
            "schedules": {
                "pinned": {
                    "command": "pinned", "prompt_file": "/p", "time": "02:00",
                    "model": "claude-sonnet-5", "fallback_models": ["claude-opus-5"],
                },
                "bare": {"command": "bare", "prompt_file": "/p", "time": "03:00"},
                "nochain": {
                    "command": "nochain", "prompt_file": "/p", "time": "04:00",
                    "fallback_models": [],
                },
                "legacy-string": {
                    "command": "legacy-string", "prompt_file": "/p", "time": "05:00",
                    "fallback_models": "claude-opus-5",
                },
            }
        }
        path = tmp_path / "s.yaml"
        path.write_text(yaml.dump(data), encoding="utf-8")
        by_name = {s.command: s for s in ScheduleConfig.load(str(path))}
        assert by_name["pinned"].model == "claude-sonnet-5"
        assert by_name["pinned"].fallback_models == ["claude-opus-5"]
        assert by_name["bare"].model is None
        assert by_name["bare"].fallback_models == list(DEFAULT_FALLBACK_MODELS)
        assert by_name["nochain"].fallback_models == []
        assert by_name["legacy-string"].fallback_models == ["claude-opus-5"]

    def test_bare_schedule_gets_fabric_default_and_the_chain(
        self, scheduler: ArkaScheduler, tmp_path: Path
    ) -> None:
        """AC1: no `model` → no --model; ANTHROPIC_DEFAULT_MODEL is the Model
        Fabric strategy model; the chain is the shared default."""
        fake_claude = _fake_binary(tmp_path)
        schedule = ScheduleConfig(
            command="research", prompt_file=str(_prompt(tmp_path)), run_time=time(5, 0)
        )
        with (
            patch.object(Path, "home", return_value=tmp_path),
            patch("core.runtime.model_router.resolve", return_value=_fabric("fable")),
            patch(
                "core.runtime.claude_code.detect_claude_code_version",
                return_value=(2, 1, 259),
            ) as probe,
        ):
            cmd = scheduler._build_command(schedule)
            env = scheduler._schedule_env(schedule)
        assert cmd[0] == str(fake_claude)
        assert "--model" not in cmd
        assert _flag(cmd, "--fallback-model") == "claude-opus-5,claude-sonnet-5"
        assert env["ANTHROPIC_DEFAULT_MODEL"] == "fable"
        assert ".local/bin" in env["PATH"], "the daemon PATH extension survives"
        probe.assert_called_with(binary=str(fake_claude))

    def test_pinned_schedule_puts_the_pin_on_argv_and_env(
        self, scheduler: ArkaScheduler, tmp_path: Path
    ) -> None:
        """AC2: an explicit pin is `--model` (highest precedence) and also the
        session default; the chain is exactly what was configured."""
        _fake_binary(tmp_path)
        schedule = ScheduleConfig(
            command="research", prompt_file=str(_prompt(tmp_path)), run_time=time(5, 0),
            model="claude-sonnet-5", fallback_models=["claude-opus-5"],
        )
        with (
            patch.object(Path, "home", return_value=tmp_path),
            patch(
                "core.runtime.model_router.resolve",
                side_effect=AssertionError("the Model Fabric must not be consulted"),
            ),
            patch(
                "core.runtime.claude_code.detect_claude_code_version",
                return_value=(2, 1, 259),
            ),
        ):
            cmd = scheduler._build_command(schedule)
            env = scheduler._schedule_env(schedule)
        assert _flag(cmd, "--model") == "claude-sonnet-5"
        assert _flag(cmd, "--fallback-model") == "claude-opus-5"
        assert env["ANTHROPIC_DEFAULT_MODEL"] == "claude-sonnet-5"

    def test_chain_drops_the_primary_and_duplicates(
        self, scheduler: ArkaScheduler, tmp_path: Path
    ) -> None:
        _fake_binary(tmp_path)
        schedule = ScheduleConfig(
            command="research", prompt_file=str(_prompt(tmp_path)), run_time=time(5, 0),
            model="claude-opus-5",
            fallback_models=["claude-opus-5", "claude-sonnet-5", "claude-sonnet-5"],
        )
        with (
            patch.object(Path, "home", return_value=tmp_path),
            patch(
                "core.runtime.claude_code.detect_claude_code_version",
                return_value=(2, 1, 259),
            ),
        ):
            cmd = scheduler._build_command(schedule)
        assert _flag(cmd, "--fallback-model") == "claude-sonnet-5"

    def test_empty_chain_means_no_flag(
        self, scheduler: ArkaScheduler, tmp_path: Path
    ) -> None:
        _fake_binary(tmp_path)
        schedule = ScheduleConfig(
            command="research", prompt_file=str(_prompt(tmp_path)), run_time=time(5, 0),
            fallback_models=[],
        )
        with (
            patch.object(Path, "home", return_value=tmp_path),
            patch("core.runtime.model_router.resolve", return_value=_fabric("fable")),
            patch(
                "core.runtime.claude_code.detect_claude_code_version",
                side_effect=AssertionError("no chain → no probe"),
            ),
        ):
            cmd = scheduler._build_command(schedule)
        assert "--fallback-model" not in cmd

    @pytest.mark.parametrize("version", [None, (2, 1, 150)])
    def test_old_or_unknown_binary_omits_the_flag_with_a_warning(
        self, scheduler: ArkaScheduler, tmp_path: Path, capsys, version
    ) -> None:
        """AC4: below the 2.1.166 chain floor (or unknowable) the flag is
        omitted and the operator is told — never a silently ignored argv."""
        _fake_binary(tmp_path)
        schedule = ScheduleConfig(
            command="research", prompt_file=str(_prompt(tmp_path)), run_time=time(5, 0)
        )
        with (
            patch.object(Path, "home", return_value=tmp_path),
            patch("core.runtime.model_router.resolve", return_value=_fabric("fable")),
            patch(
                "core.runtime.claude_code.detect_claude_code_version",
                return_value=version,
            ),
        ):
            cmd = scheduler._build_command(schedule)
        assert "--fallback-model" not in cmd
        err = capsys.readouterr().err
        assert "--fallback-model omitted" in err
        assert "2.1.166" in err
        if version is None:
            assert "version unknown (probe of" in err
            assert "upgrade" not in err, "a failed probe is not an old binary"
        else:
            assert "2.1.150 is below 2.1.166" in err
            assert "upgrade the binary" in err

    def test_probe_failure_is_unknown_not_fatal(
        self, scheduler: ArkaScheduler, tmp_path: Path, capsys
    ) -> None:
        _fake_binary(tmp_path)
        schedule = ScheduleConfig(
            command="research-probe-fails", prompt_file=str(_prompt(tmp_path)),
            run_time=time(5, 0),
        )
        with (
            patch.object(Path, "home", return_value=tmp_path),
            patch("core.runtime.model_router.resolve", return_value=_fabric("fable")),
            patch(
                "core.runtime.claude_code.detect_claude_code_version",
                side_effect=OSError("boom"),
            ),
        ):
            cmd = scheduler._build_command(schedule)
        assert "--fallback-model" not in cmd
        assert "version unknown (probe of" in capsys.readouterr().err

    def test_missing_chain_warning_is_once_per_process(
        self, scheduler: ArkaScheduler, tmp_path: Path, capsys
    ) -> None:
        """Retries within one run must not repeat the line; a different
        version answer (an upgrade mid-life) warns again."""
        _fake_binary(tmp_path)
        schedule = ScheduleConfig(
            command="research-once", prompt_file=str(_prompt(tmp_path)), run_time=time(5, 0)
        )
        with (
            patch.object(Path, "home", return_value=tmp_path),
            patch("core.runtime.model_router.resolve", return_value=_fabric("fable")),
            patch(
                "core.runtime.claude_code.detect_claude_code_version",
                return_value=(2, 1, 150),
            ),
        ):
            scheduler._build_command(schedule)
            assert "--fallback-model omitted" in capsys.readouterr().err
            scheduler._build_command(schedule)
            assert capsys.readouterr().err == ""

    def test_fabric_role_on_a_local_provider_sets_no_default(
        self, scheduler: ArkaScheduler, tmp_path: Path
    ) -> None:
        """A strategy role parked on Ollama cannot be the CLI's default model."""
        schedule = ScheduleConfig(command="x", prompt_file="/x", run_time=time(2, 0))
        with (
            patch.object(Path, "home", return_value=tmp_path),
            patch(
                "core.runtime.model_router.resolve",
                return_value=_fabric("kimi-k2.7-code:cloud", provider="ollama"),
            ),
        ):
            env = scheduler._schedule_env(schedule)
        assert "ANTHROPIC_DEFAULT_MODEL" not in env

    def test_broken_models_yaml_never_stops_the_cron(
        self, scheduler: ArkaScheduler, tmp_path: Path
    ) -> None:
        schedule = ScheduleConfig(command="x", prompt_file="/x", run_time=time(2, 0))
        with (
            patch.object(Path, "home", return_value=tmp_path),
            patch("core.runtime.model_router.resolve", side_effect=ValueError("bad yaml")),
        ):
            env = scheduler._schedule_env(schedule)
        assert "ANTHROPIC_DEFAULT_MODEL" not in env

    def test_execute_passes_the_schedule_env_to_the_child(
        self, scheduler: ArkaScheduler, tmp_path: Path
    ) -> None:
        """The env is built once per execute and reaches subprocess.run."""
        prompt_file = _prompt(tmp_path)
        schedule = ScheduleConfig(
            command="research", prompt_file=str(prompt_file), run_time=time(5, 0),
            model="claude-sonnet-5",
        )
        seen: dict = {}

        def fake_run(cmd, **kwargs):
            seen["cmd"] = cmd
            seen["env"] = kwargs["env"]
            return MagicMock(returncode=0)

        with (
            patch.object(scheduler, "_resolve_claude_binary", return_value="/bin/echo"),
            patch(
                "core.runtime.claude_code.detect_claude_code_version",
                return_value=(2, 1, 259),
            ),
            patch("subprocess.run", side_effect=fake_run),
        ):
            assert scheduler.execute(schedule) is True
        assert seen["env"]["ANTHROPIC_DEFAULT_MODEL"] == "claude-sonnet-5"
        assert _flag(seen["cmd"], "--model") == "claude-sonnet-5"
        log = next((tmp_path / "logs" / "research").glob("*.log")).read_text(encoding="utf-8")
        assert "model: claude-sonnet-5 (pinned); fallback: claude-opus-5" in log

    def test_describe_model_names_what_the_run_asks_for(self) -> None:
        describe = ArkaScheduler._describe_model
        assert describe(["claude", "-p", "x"], {}) == "runtime default; fallback: none"
        assert describe(["claude", "-p", "x"], {"ANTHROPIC_DEFAULT_MODEL": "fable"}) == (
            "fable (ANTHROPIC_DEFAULT_MODEL; a settings model or /model pick overrides); "
            "fallback: none"
        )
        assert describe(
            ["claude", "--model", "claude-sonnet-5", "--fallback-model", "a,b"],
            {"ANTHROPIC_DEFAULT_MODEL": "claude-sonnet-5"},
        ) == "claude-sonnet-5 (pinned); fallback: a → b"

    def test_list_schedules_reports_the_pin_and_the_chain(self, tmp_path: Path) -> None:
        data = {
            "schedules": {
                "pinned": {
                    "command": "pinned", "prompt_file": "/p", "time": "02:00",
                    "model": "claude-sonnet-5", "fallback_models": ["claude-opus-5"],
                },
            }
        }
        path = tmp_path / "s.yaml"
        path.write_text(yaml.dump(data), encoding="utf-8")
        [row] = list_schedules(str(path))
        assert row["model"] == "claude-sonnet-5"
        assert row["fallback_models"] == ["claude-opus-5"]

    def test_python_module_schedules_are_untouched(
        self, scheduler: ArkaScheduler, tmp_path: Path
    ) -> None:
        schedule = ScheduleConfig(
            command="dreaming-v2", prompt_file="/unused", run_time=time(2, 0),
            python_module="core.cognition.dreaming",
        )
        with patch.object(Path, "home", return_value=tmp_path):
            cmd = scheduler._build_command(schedule)
        assert cmd[:3] == [sys.executable, "-m", "core.cognition.dreaming"]
        assert "--fallback-model" not in cmd and "--model" not in cmd


class TestLoadBoundaryValidation:
    """QG round 1 (Francisca B2): a malformed pin must never reach the argv
    nor kill the daemon loop."""

    @pytest.mark.parametrize(
        "model",
        [{"lane": "opus"}, 5, ["claude-opus-5"], "--dangerously-skip-permissions", "-x"],
        ids=["mapping", "int", "list", "flag", "dash"],
    )
    def test_malformed_model_pin_fails_the_load_naming_the_schedule(
        self, tmp_path: Path, model: object
    ) -> None:
        bad = {"command": "bad", "prompt_file": "/p", "time": "02:00", "model": model}
        path = tmp_path / "s.yaml"
        path.write_text(yaml.dump({"schedules": {"bad": bad}}), encoding="utf-8")
        with pytest.raises(ValueError, match="schedule 'bad'"):
            ScheduleConfig.load(str(path))

    def test_blank_model_is_no_pin_and_items_are_stripped(self, tmp_path: Path) -> None:
        data = {
            "schedules": {
                "s": {
                    "command": "s", "prompt_file": "/p", "time": "02:00",
                    "model": "  ", "fallback_models": [" claude-opus-5 ", "", "claude-sonnet-5"],
                }
            }
        }
        path = tmp_path / "s.yaml"
        path.write_text(yaml.dump(data), encoding="utf-8")
        [schedule] = ScheduleConfig.load(str(path))
        assert schedule.model is None
        assert schedule.fallback_models == ["claude-opus-5", "claude-sonnet-5"]

    @pytest.mark.parametrize(
        "chain", [{"a": 1}, 7, [5], ["-x"]], ids=["mapping", "int", "int-item", "flag-item"]
    )
    def test_malformed_chain_fails_the_load(self, tmp_path: Path, chain: object) -> None:
        bad = {"command": "bad", "prompt_file": "/p", "time": "02:00", "fallback_models": chain}
        path = tmp_path / "s.yaml"
        path.write_text(yaml.dump({"schedules": {"bad": bad}}), encoding="utf-8")
        with pytest.raises(ValueError, match="schedule 'bad'"):
            ScheduleConfig.load(str(path))

    @pytest.mark.parametrize(
        "python_module", [None, "core.cognition.dreaming"], ids=["claude", "python_module"]
    )
    def test_execute_logs_fatal_on_a_hand_built_malformed_pin(
        self, scheduler: ArkaScheduler, tmp_path: Path, python_module: str | None
    ) -> None:
        """A ScheduleConfig built without `load` still cannot kill the loop:
        FATAL in the log, False to the caller, no exception."""
        schedule = ScheduleConfig(
            command="bad", prompt_file=str(_prompt(tmp_path)), run_time=time(2, 0),
            python_module=python_module, model={"lane": "opus"},  # type: ignore[arg-type]
        )
        with (
            patch.object(scheduler, "_resolve_claude_binary", return_value="/bin/echo"),
            patch("subprocess.run", side_effect=AssertionError("must not run")),
        ):
            assert scheduler.execute(schedule) is False
        log = next((tmp_path / "logs" / "bad").glob("*.log")).read_text(encoding="utf-8")
        assert "FATAL: schedule 'bad': model must be a non-empty string" in log

    def test_run_once_survives_a_malformed_schedule(
        self, scheduler: ArkaScheduler, tmp_path: Path
    ) -> None:
        bad = ScheduleConfig(
            command="bad", prompt_file=str(_prompt(tmp_path)), run_time=time(2, 0),
            model=5,  # type: ignore[arg-type]
        )
        scheduler.schedules = [bad]
        with patch.object(scheduler, "_should_run", return_value=True):
            scheduler.run_once()  # no exception escapes
        log = next((tmp_path / "logs" / "bad").glob("*.log")).read_text(encoding="utf-8")
        assert "FATAL" in log


class TestModelPlan:
    def test_fabric_is_resolved_once_per_execute(
        self, scheduler: ArkaScheduler, tmp_path: Path
    ) -> None:
        """QG round 1 (Francisca M3): one models.yaml read per run."""
        calls: list[str] = []

        def resolve(role: str, user_path: object = None) -> ResolvedModel:
            calls.append(role)
            return _fabric("fable")

        schedule = ScheduleConfig(
            command="research", prompt_file=str(_prompt(tmp_path)), run_time=time(5, 0)
        )
        with (
            patch.object(scheduler, "_resolve_claude_binary", return_value="/bin/echo"),
            patch("core.runtime.model_router.resolve", side_effect=resolve),
            patch(
                "core.runtime.claude_code.detect_claude_code_version",
                return_value=(2, 1, 259),
            ),
            patch("subprocess.run", return_value=MagicMock(returncode=0)),
        ):
            assert scheduler.execute(schedule) is True
        assert calls == ["strategy"]

    def test_legacy_pin_notice_names_schedules_yaml(
        self, scheduler: ArkaScheduler, tmp_path: Path, capsys, monkeypatch
    ) -> None:
        """QG round 1 (Eduardo / Francisca M2): the operator is sent to the
        file that holds the pin."""
        from core.runtime import model_router

        monkeypatch.setattr(model_router, "_LEGACY_NOTICED", set())
        _fake_binary(tmp_path)
        schedule = ScheduleConfig(
            command="research", prompt_file=str(_prompt(tmp_path)), run_time=time(5, 0),
            model="haiku", fallback_models=[],
        )
        with (
            patch.object(Path, "home", return_value=tmp_path),
            patch(
                "core.runtime.claude_code.detect_claude_code_version",
                return_value=(2, 1, 259),
            ),
        ):
            cmd = scheduler._build_command(schedule)
        assert _flag(cmd, "--model") == "sonnet"
        err = capsys.readouterr().err
        assert "schedules.yaml pins legacy model 'haiku'" in err
        assert "models.yaml pins" not in err
