"""ArkaScheduler — cross-platform daemon for running cognitive tasks on schedule.

Reads a YAML schedule config, acquires a file lock to prevent duplicate runs,
and executes Claude CLI commands with logging per task.
"""

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, time
from pathlib import Path

import yaml


@dataclass
class ScheduleConfig:
    """Configuration for a single scheduled cognitive task."""

    command: str
    prompt_file: str
    run_time: time
    enabled: bool = True
    retry_on_fail: bool = True
    max_retries: int = 2
    timeout_minutes: int = 60

    @classmethod
    def load(cls, config_path: str) -> "list[ScheduleConfig]":
        """Load schedules from YAML, returning only enabled entries."""
        with open(config_path) as fh:
            data = yaml.safe_load(fh)

        schedules = []
        for _name, cfg in (data.get("schedules") or {}).items():
            if not cfg.get("enabled", True):
                continue
            raw_time = cfg["time"]
            hour, minute = (int(p) for p in raw_time.split(":"))
            schedules.append(
                cls(
                    command=cfg["command"],
                    prompt_file=cfg["prompt_file"],
                    run_time=time(hour, minute),
                    enabled=cfg.get("enabled", True),
                    retry_on_fail=cfg.get("retry_on_fail", True),
                    max_retries=cfg.get("max_retries", 2),
                    timeout_minutes=cfg.get("timeout_minutes", 60),
                )
            )
        return schedules


class ArkaScheduler:
    """Cross-platform scheduler daemon for ArkaOS cognitive tasks."""

    def __init__(self, config_path: str, log_dir: str, lock_path: str) -> None:
        self._config_path = config_path
        self._log_dir = log_dir
        self._lock_path = lock_path
        self._lock_fd = None
        self.schedules: list[ScheduleConfig] = ScheduleConfig.load(config_path)

    # ------------------------------------------------------------------
    # Lock management
    # ------------------------------------------------------------------

    def acquire_lock(self) -> bool:
        """Acquire an exclusive file lock. Returns False if already locked."""
        Path(self._lock_path).parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = open(self._lock_path, "w")  # noqa: WPS515
            if sys.platform == "win32":
                import msvcrt  # type: ignore[import]

                msvcrt.locking(fd.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl  # type: ignore[import]

                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._lock_fd = fd
            return True
        except (OSError, IOError):
            return False

    def release_lock(self) -> None:
        """Release the file lock if held."""
        if self._lock_fd is None:
            return
        try:
            if sys.platform == "win32":
                import msvcrt  # type: ignore[import]

                msvcrt.locking(self._lock_fd.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl  # type: ignore[import]

                fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
        finally:
            self._lock_fd.close()
            self._lock_fd = None

    # ------------------------------------------------------------------
    # Schedule logic
    # ------------------------------------------------------------------

    def _should_run(self, schedule: ScheduleConfig, current_time: time) -> bool:
        """Return True when current_time matches schedule's run_time (HH:MM)."""
        return (
            current_time.hour == schedule.run_time.hour
            and current_time.minute == schedule.run_time.minute
        )

    def _build_command(self, schedule: ScheduleConfig) -> list[str]:
        """Build the Claude CLI invocation for a schedule."""
        claude_bin = shutil.which("claude") or "claude"
        prompt_path = os.path.expanduser(schedule.prompt_file)
        prompt_content = Path(prompt_path).read_text(encoding="utf-8")
        return [claude_bin, "-p", prompt_content, "--dangerously-skip-permissions"]

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def _log_path(self, command: str) -> Path:
        """Return the log file path for today's run of a command."""
        today = datetime.now().strftime("%Y-%m-%d")
        log_dir = Path(self._log_dir) / command
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir / f"{today}.log"

    def execute(self, schedule: ScheduleConfig) -> bool:
        """Run the scheduled command, writing output to a dated log file."""
        log_file = self._log_path(schedule.command)
        timeout_seconds = schedule.timeout_minutes * 60
        attempts = 0
        max_attempts = schedule.max_retries + 1 if schedule.retry_on_fail else 1

        while attempts < max_attempts:
            attempts += 1
            cmd = self._build_command(schedule)
            with open(log_file, "a", encoding="utf-8") as lf:
                lf.write(f"\n--- attempt {attempts} at {datetime.now().isoformat()} ---\n")
                try:
                    result = subprocess.run(
                        cmd,
                        stdout=lf,
                        stderr=lf,
                        timeout=timeout_seconds,
                    )
                    if result.returncode == 0:
                        return True
                    lf.write(f"exit code: {result.returncode}\n")
                except subprocess.TimeoutExpired:
                    lf.write("TIMEOUT\n")
                except Exception as exc:  # noqa: BLE001
                    lf.write(f"ERROR: {exc}\n")

        return False

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run_once(self) -> None:
        """Check all schedules against current time and execute matching ones."""
        now = datetime.now().time().replace(second=0, microsecond=0)
        for schedule in self.schedules:
            if self._should_run(schedule, now):
                self.execute(schedule)
