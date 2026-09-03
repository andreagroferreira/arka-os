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

Model pin and fallback chain (Runtime Sync PR3): a schedule's ``model``
goes on the argv as ``--model`` (highest precedence — a pin is a pin);
without one, the Model Fabric ``strategy`` role becomes
``ANTHROPIC_DEFAULT_MODEL`` in the child's environment (Claude Code
2.1.236+), a default that a settings-file ``model`` or a persisted
``/model`` pick still overrides. ``fallback_models`` becomes
``--fallback-model a,b`` (Claude Code 2.1.166+ chain semantics; omitted
with a warning on an older or unknown binary) so one overload or model
404 no longer ends the nightly cycle. The chain drops the Fabric primary,
not a settings-file primary the daemon cannot see — at worst one wasted
retry. Both keys are validated when the YAML loads; a malformed value
names the schedule and stops the load rather than reaching the argv.
"""

import os
import shutil
import subprocess
import sys
import time as time_mod
import traceback
from dataclasses import dataclass, field
from datetime import datetime, time
from pathlib import Path

import yaml

from core.runtime.claude_code import DEFAULT_FALLBACK_MODELS

# The Model Fabric role a schedule runs as when it pins no model: the
# nightly cycles are strategy work.
SCHEDULE_ROLE = "strategy"
# Providers the Claude CLI can run itself. A role parked on Ollama or
# OpenRouter cannot become ANTHROPIC_DEFAULT_MODEL — the CLI would 404.
_CLAUDE_PROVIDERS = frozenset({"runtime", "anthropic"})
# Where a schedule's model ids come from — named in the legacy-id notice
# so the operator is sent to the right file.
SCHEDULES_SOURCE = "schedules.yaml"
# What a bad ``fallback_models`` item is called in its error, so the
# operator is not sent to ``model:``.
_CHAIN_ENTRY = "fallback_models entry"


def _model_pin(raw: object, command: str, what: str = "model") -> str:
    """A validated model id from ``schedules.yaml``.

    A non-empty string, stripped, that cannot be mistaken for a flag: a
    pin such as ``--dangerously-skip-permissions`` would otherwise land on
    the argv as one. ``what`` names the key the error blames.
    """
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(
            f"schedule '{command}': {what} must be a non-empty string, got {raw!r}"
        )
    value = raw.strip()
    if value.startswith("-"):
        raise ValueError(
            f"schedule '{command}': {what} {value!r} looks like a flag, not a model id"
        )
    return value


def _optional_pin(raw: object, command: str) -> str | None:
    """``model:`` as loaded: absent or blank is no pin; anything else validates."""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None
    return _model_pin(raw, command)


def _fallback_list(raw: object, command: str) -> list[str]:
    """The YAML ``fallback_models`` value as a validated list.

    None means the default chain; a string is a one-entry chain; blank
    entries are dropped; anything that is not a model id raises, naming
    the schedule.
    """
    if raw is None:
        return list(DEFAULT_FALLBACK_MODELS)
    if isinstance(raw, str):
        return [_model_pin(raw, command, _CHAIN_ENTRY)] if raw.strip() else []
    if isinstance(raw, list):
        return [
            _model_pin(item, command, _CHAIN_ENTRY)
            for item in raw
            if not (isinstance(item, str) and not item.strip())
        ]
    raise ValueError(
        f"schedule '{command}': fallback_models must be a list of model ids, got {raw!r}"
    )


@dataclass(frozen=True)
class _ModelPlan:
    """What one run asks the CLI for, resolved once per execute."""

    pinned: str | None
    primary: str | None
    chain: list[str]


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
    # Runtime Sync PR3 — `model` pins the CLI model (argv --model); None
    # resolves the Model Fabric `strategy` role into ANTHROPIC_DEFAULT_MODEL.
    # `fallback_models` is the --fallback-model chain; an explicit empty
    # list disables it. Both are validated by `load`; a hand-built config
    # is validated again when the plan is built.
    model: str | None = None
    fallback_models: list[str] = field(
        default_factory=lambda: list(DEFAULT_FALLBACK_MODELS)
    )

    @classmethod
    def load(cls, config_path: str) -> "list[ScheduleConfig]":
        """Load schedules from YAML, returning only enabled entries."""
        with open(config_path, encoding="utf-8") as fh:
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
                    model=_optional_pin(cfg.get("model"), _name),
                    fallback_models=_fallback_list(cfg.get("fallback_models"), _name),
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
        # (schedule, version seen) pairs already warned about a missing
        # chain — once per scheduler, so retries within one run do not
        # repeat the line.
        self._fallback_warned: set[tuple[str, str]] = set()
        self.schedules: list[ScheduleConfig] = ScheduleConfig.load(config_path)

    # ------------------------------------------------------------------
    # Lock management
    # ------------------------------------------------------------------

    def acquire_lock(self) -> bool:
        """Acquire an exclusive file lock. Returns False if already locked."""
        Path(self._lock_path).parent.mkdir(parents=True, exist_ok=True)
        try:
            # The lock fd must outlive this method: it is held for the
            # daemon's lifetime and closed in release_lock.
            fd = open(self._lock_path, "w", encoding="utf-8")  # noqa: SIM115
            if sys.platform == "win32":
                import msvcrt  # type: ignore[import]

                msvcrt.locking(fd.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl  # type: ignore[import]

                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._lock_fd = fd
            return True
        except OSError:
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

    def _build_command(
        self, schedule: ScheduleConfig, plan: _ModelPlan | None = None
    ) -> list[str]:
        """Build the subprocess invocation for a schedule.

        Dispatches on python_module first (PR8 Dreaming v2 path), falls
        back to the legacy Claude-CLI-with-prompt path for unchanged
        schedules. ``plan`` is the model plan ``execute`` resolved once;
        a direct caller gets it resolved here.
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
        plan = plan or self._model_plan(schedule)
        if plan.pinned:
            argv.extend(["--model", plan.pinned])
        argv.extend(self._fallback_argv(schedule, plan, claude_bin))
        argv.extend(self._goal_argv(schedule))
        return argv

    # ------------------------------------------------------------------
    # Model pin and fallback chain (Runtime Sync PR3)
    # ------------------------------------------------------------------

    @staticmethod
    def _pinned_model(schedule: ScheduleConfig) -> str | None:
        """The model the schedule pins, with a legacy id mapped to its lane."""
        if schedule.model is None:
            return None
        from core.runtime.model_router import normalise_model_id

        return normalise_model_id(
            _model_pin(schedule.model, schedule.command), source=SCHEDULES_SOURCE
        )

    @staticmethod
    def _fabric_model() -> str | None:
        """The Model Fabric `strategy` model when the Claude CLI can run it."""
        try:
            from core.runtime.model_router import resolve

            resolved = resolve(SCHEDULE_ROLE)
        except Exception:  # a broken models.yaml must not stop the cron
            return None
        if resolved.provider not in _CLAUDE_PROVIDERS or not resolved.model:
            return None
        return resolved.model

    @classmethod
    def _model_plan(cls, schedule: ScheduleConfig) -> _ModelPlan:
        """Resolve pin, primary and chain once — one models.yaml read per run."""
        from core.runtime.model_router import normalise_model_id

        pinned = cls._pinned_model(schedule)
        primary = pinned or cls._fabric_model()
        chain: list[str] = []
        for model in schedule.fallback_models:
            lane = normalise_model_id(
                _model_pin(model, schedule.command, _CHAIN_ENTRY),
                source=SCHEDULES_SOURCE,
            )
            if lane != primary and lane not in chain:
                chain.append(lane)
        return _ModelPlan(pinned=pinned, primary=primary, chain=chain)

    def _fallback_argv(
        self, schedule: ScheduleConfig, plan: _ModelPlan, claude_bin: str
    ) -> list[str]:
        """``--fallback-model a,b`` when the binary knows fallback chains.

        Gated on the 2.1.166 floor (the changelog line that documents the
        chain semantics); an older or unknown binary gets no flag and one
        warning per (schedule, version) in the log.
        """
        if not plan.chain:
            return []
        from core.runtime.claude_code import FEATURE_FLOORS, detect_claude_code_version

        floor = FEATURE_FLOORS["fallback_model_setting"]
        try:
            version = detect_claude_code_version(binary=claude_bin)
        except Exception:  # the probe is advisory; the run is not
            version = None
        if version is not None and version >= floor:
            return ["--fallback-model", ",".join(plan.chain)]
        floor_text = ".".join(map(str, floor))
        if version is None:
            seen = "unknown"
            reason = (
                f"Claude Code version unknown (probe of {claude_bin} failed); "
                f"fallback chains need {floor_text} or newer."
            )
        else:
            seen = ".".join(map(str, version))
            reason = (
                f"Claude Code {seen} is below {floor_text}, where fallback chains "
                "are documented; upgrade the binary."
            )
        if (schedule.command, seen) not in self._fallback_warned:
            self._fallback_warned.add((schedule.command, seen))
            self._warn(
                f"[arkaos] schedule '{schedule.command}': --fallback-model omitted — "
                + reason
            )
        return []

    @classmethod
    def _schedule_env(
        cls, schedule: ScheduleConfig, plan: _ModelPlan | None = None
    ) -> dict[str, str]:
        """The daemon env plus ANTHROPIC_DEFAULT_MODEL for this schedule."""
        env = cls._daemon_env()
        plan = plan or cls._model_plan(schedule)
        if plan.primary:
            env["ANTHROPIC_DEFAULT_MODEL"] = plan.primary
        return env

    @staticmethod
    def _warn(message: str) -> None:
        try:
            sys.stderr.write(message + "\n")
            sys.stderr.flush()
        except Exception:  # stderr may be closed under launchd
            pass

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
        ]
        if os.name != "nt":
            extra_paths.append("/usr/local/bin")
        env = os.environ.copy()
        existing = env.get("PATH", "" if os.name == "nt" else "/usr/bin:/bin")
        # os.pathsep is ';' on Windows (where drive-letter entries contain
        # ':') and ':' on POSIX, so the joined PATH stays valid on both.
        parts = extra_paths + ([existing] if existing else [])
        env["PATH"] = os.pathsep.join(parts)
        return env

    def _run_attempt(
        self,
        cmd: list[str],
        log_file: Path,
        attempt: int,
        timeout: int,
        env: dict[str, str] | None = None,
    ) -> bool:
        """Run a single attempt of a scheduled command. Returns True on success."""
        env = env if env is not None else self._daemon_env()
        with open(log_file, "a", encoding="utf-8") as lf:
            lf.write(f"\n--- attempt {attempt} at {datetime.now().isoformat()} ---\n")
            lf.write(f"cmd: {cmd[0]}\n")
            lf.write(f"model: {self._describe_model(cmd, env)}\n")
            try:
                # The daemon runs under pythonw.exe and owns no console, so
                # a console-subsystem child (schedules on the `prompt_file`
                # path spawn the claude CLI directly) gets a fresh console
                # window of its own. It shows no output -- stdout is
                # redirected to the log -- so the operator closes it, which
                # kills the run with 0xC000013A. CREATE_NO_WINDOW is absent
                # on POSIX, where 0 means "no extra flags".
                result = subprocess.run(
                    cmd, stdout=lf, stderr=lf, timeout=timeout, env=env,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                if result.returncode == 0:
                    return True
                lf.write(f"exit code: {result.returncode}\n")
            except subprocess.TimeoutExpired:
                lf.write("TIMEOUT\n")
            except Exception as exc:
                lf.write(f"ERROR: {exc}\n")
        return False

    @staticmethod
    def _describe_model(cmd: list[str], env: dict[str, str]) -> str:
        """One log line with what the run asks for: the pin, else the env
        default a settings-file model still overrides, and the chain as
        passed (the runtime may trim it)."""
        pinned = cmd[cmd.index("--model") + 1] if "--model" in cmd else None
        default = env.get("ANTHROPIC_DEFAULT_MODEL")
        if pinned:
            model = f"{pinned} (pinned)"
        elif default:
            model = (
                f"{default} (ANTHROPIC_DEFAULT_MODEL; a settings model or "
                "/model pick overrides)"
            )
        else:
            model = "runtime default"
        chain = (
            cmd[cmd.index("--fallback-model") + 1].replace(",", " → ")
            if "--fallback-model" in cmd
            else "none"
        )
        return f"{model}; fallback: {chain}"

    def execute(self, schedule: ScheduleConfig) -> bool:
        """Run the scheduled command with retries and backoff."""
        log_file = self._log_path(schedule.command)
        timeout = schedule.timeout_minutes * 60
        max_attempts = schedule.max_retries + 1 if schedule.retry_on_fail else 1

        # A missing binary, an unreadable prompt or a malformed pin all end
        # here: FATAL in the log, False to the caller, the loop alive.
        try:
            plan = self._model_plan(schedule)
            cmd = self._build_command(schedule, plan)
            env = self._schedule_env(schedule, plan)
        except (OSError, ValueError, TypeError) as exc:
            detail = f"FATAL: {exc} ({type(exc).__name__})"
            if isinstance(exc, TypeError):  # a programming error, not a config one
                detail += "\n" + traceback.format_exc().rstrip()
            with open(log_file, "a", encoding="utf-8") as lf:
                lf.write(f"\n--- at {datetime.now().isoformat()} ---\n{detail}\n")
            return False

        for attempt in range(1, max_attempts + 1):
            if self._run_attempt(cmd, log_file, attempt, timeout, env=env):
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
