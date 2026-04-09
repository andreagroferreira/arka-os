"""CLI functions for managing the ArkaOS cognitive scheduler."""

from pathlib import Path

from core.cognition.scheduler.daemon import ArkaScheduler, ScheduleConfig


def list_schedules(config_path: str) -> list[dict]:
    """Return a list of dicts with command, time, timeout, retry for each schedule."""
    schedules = ScheduleConfig.load(config_path)
    return [
        {
            "command": s.command,
            "time": s.run_time.strftime("%H:%M"),
            "timeout": s.timeout_minutes,
            "retry": s.retry_on_fail,
        }
        for s in schedules
    ]


def _last_run_date(log_dir: str, command: str) -> str:
    """Return the most recent log date for a command, or 'never'."""
    command_log_dir = Path(log_dir) / command
    if not command_log_dir.exists():
        return "never"

    log_files = sorted(command_log_dir.glob("*.log"), reverse=True)
    if not log_files:
        return "never"

    return log_files[0].stem


def scheduler_status(config_path: str, log_dir: str, lock_path: str) -> str:
    """Return a formatted status string with schedule info and last runs."""
    is_running = Path(lock_path).exists()
    status_label = "RUNNING" if is_running else "STOPPED"

    schedules = ScheduleConfig.load(config_path)

    schedule_lines = []
    for s in schedules:
        time_str = s.run_time.strftime("%H:%M")
        retry_str = ", retry" if s.retry_on_fail else ""
        schedule_lines.append(
            f"  {s.command:<12} at {time_str}  (timeout: {s.timeout_minutes}m{retry_str})"
        )

    last_run_lines = []
    for s in schedules:
        last_date = _last_run_date(log_dir, s.command)
        last_run_lines.append(f"  {s.command:<12} last: {last_date}")

    lines = [
        "=== ArkaOS Scheduler Status ===",
        "",
        f"Status: {status_label}",
        "",
        "Schedules:",
        *schedule_lines,
        "",
        "Last runs:",
        *last_run_lines,
        "",
        "===============================",
    ]
    return "\n".join(lines)


def run_now(command: str, config_path: str, log_dir: str, lock_path: str) -> bool:
    """Execute a specific schedule immediately by command name.

    Raises ValueError if the command is not found in the config.
    """
    scheduler = ArkaScheduler(
        config_path=config_path,
        log_dir=log_dir,
        lock_path=lock_path,
    )

    match = next((s for s in scheduler.schedules if s.command == command), None)
    if match is None:
        raise ValueError(f"Unknown schedule command: {command!r}")

    return scheduler.execute(match)
