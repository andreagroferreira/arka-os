"""ArkaScheduler — cross-platform daemon for running cognitive tasks on schedule.

Reads a YAML schedule config, acquires a file lock to prevent duplicate runs,
and executes Claude CLI commands with logging per task.

Goal mode (opt-in, v4.1.0): a schedule may pair `goal_condition` with
`task_budget` to append `--goal <condition> --task-budget <N>` to the
Claude CLI argv, so Research/Dreaming cycles run until the condition is
met instead of stopping when the prompt's phases run out. The pairing is
mandatory (`_goal_argv` raises otherwise) and only applies to the
prompt_file path — `python_module` entries ignore it. Commented-out
examples live in the installer-seeded template `config/cognition/
schedules.yaml` (deployed to `~/.arkaos/schedules.yaml`); nothing
goal-based auto-runs without the operator uncommenting it.
"""

import os
import shutil
import subprocess
import sys
import time as time_mod
from dataclasses import dataclass, field
from datetime import datetime, time
from pathlib import Path

import yaml


@dataclass
class ScheduleConfig:
    """Configuration for a single scheduled cognitive task.

    Two execution modes (mutually exclusive):
      - prompt_file (default): shell out to the active Claude CLI with the
        rendered prompt as the user input. Backward-compat for legacy
        dreaming.md / research.md schedules.
      - python_module: invoke ``python -m <module> [args...]`` directly.
        Used by Dreaming v2 (PR8) which is a Python engine, not a
        prompt-only task.
    """

    command: str
    prompt_file: str
    run_time: time
    enabled: bool = True
    retry_on_fail: bool = True
    max_retries: int = 2
    timeout_minutes: int = 60
    python_module: str | None = None
    module_args: list[str] = field(default_factory=list)
    # PR54 v2.71.0 — opt-in Claude Code v2.1.139 /goal primitive.
    # When goal_condition is set the scheduler appends
    # `--goal <condition> --task-budget <N>` to the claude argv, so the
    # model keeps running until it decides the condition is met (instead
    # of stopping when the prompt's hardcoded phases run out). NEVER
    # pair --goal without --task-budget — KB caveat: sharp edges around
    # the model overcommitting to ambiguous goals (infinite-loop risk).
    goal_condition: str | None = None
    task_budget: int | None = None

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
                    prompt_file=cfg.get("prompt_file", ""),
                    run_time=time(hour, minute),
                    enabled=cfg.get("enabled", True),
                    retry_on_fail=cfg.get("retry_on_fail", True),
                    max_retries=cfg.get("max_retries", 2),
                    timeout_minutes=cfg.get("timeout_minutes", 60),
                    python_module=cfg.get("python_module"),
                    module_args=list(cfg.get("module_args") or []),
                    goal_condition=cfg.get("goal_condition"),
                    task_budget=cfg.get("task_budget"),
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

    @staticmethod
    def _resolve_claude_binary() -> str:
        """Resolve the Claude CLI binary by checking known install locations.

        In daemon context (launchd/systemd/schtasks), PATH is minimal and shell
        aliases don't exist, so we check absolute paths first.
        """
        home = Path.home()
        candidates = [
            home / ".local" / "bin" / "claude",
            home / ".arkaos" / "bin" / "arka-claude",
        ]
        for candidate in candidates:
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return str(candidate)
        # Fallback to PATH lookup (works in interactive shells)
        found = shutil.which("claude") or shutil.which("arka-claude")
        if found:
            return found
        raise FileNotFoundError(
            "Claude CLI not found. Checked: "
            + ", ".join(str(c) for c in candidates)
            + " and PATH lookup."
        )

    def _build_command(self, schedule: ScheduleConfig) -> list[str]:
        """Build the subprocess invocation for a schedule.

        Dispatches on python_module first (PR8 Dreaming v2 path), falls
        back to the legacy Claude-CLI-with-prompt path for unchanged
        schedules.
        """
        if schedule.python_module:
            return [sys.executable, "-m", schedule.python_module, *schedule.module_args]
        self._warn_metered_billing_cutover(schedule)
        claude_bin = self._resolve_claude_binary()
        prompt_path = os.path.expanduser(schedule.prompt_file)
        prompt_content = Path(prompt_path).read_text(encoding="utf-8")
        try:
            from core.runtime.path_resolver import resolve
            prompt_content = resolve(prompt_content)
        except Exception:
            pass  # fall back to raw template if profile unavailable
        argv = [claude_bin, "-p", prompt_content, "--dangerously-skip-permissions"]
        argv.extend(self._goal_argv(schedule))
        return argv

    @staticmethod
    def _goal_argv(schedule: ScheduleConfig) -> list[str]:
        """Build the --goal/--task-budget argv suffix when configured.

        Returns an empty list when goal_condition is unset (legacy
        single-shot behaviour). Raises ValueError when --goal is set
        without --task-budget — pairing the two is mandatory per the
        Claude Code v2.1.139 KB caveat (sharp edges around the model
        overcommitting to ambiguous goals → infinite-loop risk).
        """
        if not schedule.goal_condition:
            return []
        if not schedule.task_budget or schedule.task_budget <= 0:
            raise ValueError(
                f"schedule '{schedule.command}' sets goal_condition without "
                "a positive task_budget — pairing is mandatory to bound the "
                "metered burn (Claude Code v2.1.139 KB caveat)."
            )
        return [
            "--goal", str(schedule.goal_condition),
            "--task-budget", str(int(schedule.task_budget)),
        ]

    @staticmethod
    def _warn_metered_billing_cutover(schedule: ScheduleConfig) -> None:
        """Emit a one-time warning for legacy `claude -p` schedules.

        PR52 v2.68.0 — Anthropic's Agent SDK $200 credit policy takes
        effect 2026-06-15: programmatic Claude usage (`claude -p`,
        Agent SDK, GitHub Actions, third-party harnesses) is metered
        separately from interactive use. Subscriptions previously
        absorbed the burn; after the cutover they no longer do. Operator
        action: migrate this schedule to `python_module` (Dreaming v2)
        or to a direct-API-key invocation with explicit budget alarms.
        """
        marker_dir = Path.home() / ".arkaos" / "telemetry"
        marker = marker_dir / f"metered-billing-warned.{schedule.command}"
        if marker.exists():
            return
        try:
            marker_dir.mkdir(parents=True, exist_ok=True)
            marker.write_text(datetime.now().isoformat(), encoding="utf-8")
        except OSError:
            pass  # best-effort marker; warning still fires every time
        msg = (
            "[arkaos] schedule '" + schedule.command + "' uses the legacy "
            "`claude -p` path. From 2026-06-15, programmatic Claude usage "
            "is metered separately from interactive subscription credit "
            "(Pro $20 / Max5x $100 / Max20x $200, no rollover). "
            "Migrate to python_module or direct API key before then. "
            "See: knowledge-anthropic-agent-sdk-credit-policy-2026-06-15"
        )
        try:
            sys.stderr.write(msg + "\n")
            sys.stderr.flush()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def _log_path(self, command: str) -> Path:
        """Return the log file path for today's run of a command."""
        today = datetime.now().strftime("%Y-%m-%d")
        log_dir = Path(self._log_dir) / command
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir / f"{today}.log"

    @staticmethod
    def _daemon_env() -> dict[str, str]:
        """Build an environment with PATH that includes known Claude locations.

        Daemons (launchd/systemd) inherit a minimal PATH. We extend it so that
        any child processes spawned by Claude can also find common tools.
        """
        home = str(Path.home())
        extra_paths = [
            os.path.join(home, ".local", "bin"),
            os.path.join(home, ".arkaos", "bin"),
            "/usr/local/bin",
        ]
        env = os.environ.copy()
        existing = env.get("PATH", "/usr/bin:/bin")
        env["PATH"] = ":".join(extra_paths) + ":" + existing
        return env

    def _run_attempt(
        self, cmd: list[str], log_file: Path, attempt: int, timeout: int,
    ) -> bool:
        """Run a single attempt of a scheduled command. Returns True on success."""
        env = self._daemon_env()
        with open(log_file, "a", encoding="utf-8") as lf:
            lf.write(f"\n--- attempt {attempt} at {datetime.now().isoformat()} ---\n")
            lf.write(f"cmd: {cmd[0]}\n")
            try:
                result = subprocess.run(
                    cmd, stdout=lf, stderr=lf, timeout=timeout, env=env,
                )
                if result.returncode == 0:
                    return True
                lf.write(f"exit code: {result.returncode}\n")
            except subprocess.TimeoutExpired:
                lf.write("TIMEOUT\n")
            except Exception as exc:  # noqa: BLE001
                lf.write(f"ERROR: {exc}\n")
        return False

    def execute(self, schedule: ScheduleConfig) -> bool:
        """Run the scheduled command with retries and backoff."""
        log_file = self._log_path(schedule.command)
        timeout = schedule.timeout_minutes * 60
        max_attempts = schedule.max_retries + 1 if schedule.retry_on_fail else 1

        try:
            cmd = self._build_command(schedule)
        except FileNotFoundError as exc:
            with open(log_file, "a", encoding="utf-8") as lf:
                lf.write(f"\n--- at {datetime.now().isoformat()} ---\nFATAL: {exc}\n")
            return False

        for attempt in range(1, max_attempts + 1):
            if self._run_attempt(cmd, log_file, attempt, timeout):
                return True
            if attempt < max_attempts:
                time_mod.sleep(30 * attempt)
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
