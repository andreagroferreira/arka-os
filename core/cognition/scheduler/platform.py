"""Cross-platform service adapters for the ArkaOS cognitive scheduler.

Supports macOS (launchd), Linux (systemd), and Windows (schtasks).
"""

import shutil
import subprocess
import sys
from abc import ABC, abstractmethod
from pathlib import Path


def _default_daemon_script() -> str:
    return str(Path.home() / ".arkaos" / "bin" / "scheduler-daemon.py")


def _python_executable() -> str:
    """Resolve Python, preferring the ArkaOS venv over random system pythons.

    shutil.which("python3") in a daemon context may pick up a venv from an
    unrelated project (e.g., ai-jarvis). We check the ArkaOS venv first.
    """
    home = Path.home()
    # Check both common venv directory names
    for venv_dir in ("venv", ".venv"):
        arkaos_venv = home / ".arkaos" / venv_dir / "bin" / "python3"
        if arkaos_venv.is_file():
            return str(arkaos_venv)
        # Windows venv layout
        arkaos_venv_win = home / ".arkaos" / venv_dir / "Scripts" / "python.exe"
        if arkaos_venv_win.is_file():
            return str(arkaos_venv_win)
    return shutil.which("python3") or sys.executable


def _daemon_path_value() -> str:
    """Return a PATH string with known Claude CLI locations for daemon contexts."""
    home = str(Path.home())
    return f"{home}/.local/bin:{home}/.arkaos/bin:/usr/local/bin:/usr/bin:/bin"


class PlatformAdapter(ABC):
    """Abstract base for OS-level service management."""

    platform_name: str

    @abstractmethod
    def install_service(self) -> bool: ...

    @abstractmethod
    def uninstall_service(self) -> bool: ...

    @abstractmethod
    def is_running(self) -> bool: ...

    @abstractmethod
    def start(self) -> bool: ...

    @abstractmethod
    def stop(self) -> bool: ...


class MacOSAdapter(PlatformAdapter):
    """launchd adapter for macOS."""

    platform_name = "macos"

    _LABEL = "com.arkaos.scheduler"

    def __init__(self, daemon_script: str, plist_dir: str | None = None) -> None:
        self._daemon_script = daemon_script
        self._plist_dir = plist_dir or str(
            Path.home() / "Library" / "LaunchAgents"
        )

    def _plist_path(self) -> str:
        return str(Path(self._plist_dir) / f"{self._LABEL}.plist")

    def _plist_env_block(self) -> str:
        """Generate the EnvironmentVariables section of the plist."""
        home = str(Path.home())
        return (
            "\t<key>EnvironmentVariables</key>\n\t<dict>\n"
            f"\t\t<key>PATH</key>\n\t\t<string>{_daemon_path_value()}</string>\n"
            f"\t\t<key>HOME</key>\n\t\t<string>{home}</string>\n"
            "\t</dict>\n"
        )

    def _generate_plist(self) -> str:
        """Generate the launchd plist XML for the scheduler daemon."""
        python = _python_executable()
        log_dir = Path.home() / ".arkaos" / "logs"
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"'
            ' "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
            '<plist version="1.0">\n<dict>\n'
            f"\t<key>Label</key>\n\t<string>{self._LABEL}</string>\n"
            f"\t<key>ProgramArguments</key>\n\t<array>\n"
            f"\t\t<string>{python}</string>\n"
            f"\t\t<string>{self._daemon_script}</string>\n\t</array>\n"
            + self._plist_env_block()
            + "\t<key>RunAtLoad</key>\n\t<true/>\n"
            "\t<key>KeepAlive</key>\n\t<true/>\n"
            f"\t<key>StandardOutPath</key>\n\t<string>{log_dir / 'scheduler-stdout.log'}</string>\n"
            f"\t<key>StandardErrorPath</key>\n\t<string>{log_dir / 'scheduler-stderr.log'}</string>\n"
            "</dict>\n</plist>\n"
        )

    def install_service(self) -> bool:
        """Write plist and load it via launchctl."""
        plist = Path(self._plist_path())
        plist.parent.mkdir(parents=True, exist_ok=True)
        plist.write_text(self._generate_plist(), encoding="utf-8")
        return self.start()

    def uninstall_service(self) -> bool:
        """Unload and remove the plist."""
        self.stop()
        plist = Path(self._plist_path())
        if plist.exists():
            plist.unlink()
        return True

    def is_running(self) -> bool:
        """Return True when launchctl reports the service as running."""
        try:
            result = subprocess.run(
                ["launchctl", "list", self._LABEL],
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
        except Exception:  # noqa: BLE001
            return False

    def start(self) -> bool:
        try:
            result = subprocess.run(
                ["launchctl", "load", self._plist_path()],
                capture_output=True,
            )
            return result.returncode == 0
        except Exception:  # noqa: BLE001
            return False

    def stop(self) -> bool:
        try:
            result = subprocess.run(
                ["launchctl", "unload", self._plist_path()],
                capture_output=True,
            )
            return result.returncode == 0
        except Exception:  # noqa: BLE001
            return False


class LinuxAdapter(PlatformAdapter):
    """systemd --user adapter for Linux."""

    platform_name = "linux"

    _SERVICE_NAME = "arkaos-scheduler.service"

    def __init__(self, daemon_script: str, service_dir: str | None = None) -> None:
        self._daemon_script = daemon_script
        self._service_dir = service_dir or str(
            Path.home() / ".config" / "systemd" / "user"
        )

    def _service_path(self) -> str:
        return str(Path(self._service_dir) / self._SERVICE_NAME)

    def _generate_unit(self) -> str:
        """Generate the systemd unit file for the scheduler daemon."""
        python = _python_executable()
        return (
            "[Unit]\n"
            "Description=ArkaOS Cognitive Scheduler\n"
            "After=network.target\n\n"
            "[Service]\n"
            "Type=simple\n"
            f"Environment=PATH={_daemon_path_value()}\n"
            f"ExecStart={python} {self._daemon_script}\n"
            "Restart=on-failure\n"
            "RestartSec=60\n\n"
            "[Install]\n"
            "WantedBy=default.target\n"
        )

    def install_service(self) -> bool:
        """Write unit file and enable it via systemctl --user."""
        service = Path(self._service_path())
        service.parent.mkdir(parents=True, exist_ok=True)
        service.write_text(self._generate_unit(), encoding="utf-8")
        return self.start()

    def uninstall_service(self) -> bool:
        """Disable and remove the unit file."""
        self.stop()
        service = Path(self._service_path())
        if service.exists():
            service.unlink()
        return True

    def is_running(self) -> bool:
        try:
            result = subprocess.run(
                ["systemctl", "--user", "is-active", self._SERVICE_NAME],
                capture_output=True,
                text=True,
            )
            return result.stdout.strip() == "active"
        except Exception:  # noqa: BLE001
            return False

    def start(self) -> bool:
        try:
            result = subprocess.run(
                ["systemctl", "--user", "enable", "--now", self._SERVICE_NAME],
                capture_output=True,
            )
            return result.returncode == 0
        except Exception:  # noqa: BLE001
            return False

    def stop(self) -> bool:
        try:
            result = subprocess.run(
                ["systemctl", "--user", "disable", "--now", self._SERVICE_NAME],
                capture_output=True,
            )
            return result.returncode == 0
        except Exception:  # noqa: BLE001
            return False


class WindowsAdapter(PlatformAdapter):
    """schtasks adapter for Windows."""

    platform_name = "windows"

    _TASK_NAME = "ArkaOS-Scheduler"

    def __init__(self, daemon_script: str) -> None:
        self._daemon_script = daemon_script

    def _build_schtasks_command(self) -> list[str]:
        python = _python_executable()
        return [
            "schtasks",
            "/Create",
            "/F",
            "/TN",
            self._TASK_NAME,
            "/SC",
            "ONLOGON",
            "/TR",
            f"{python} {self._daemon_script}",
        ]

    def install_service(self) -> bool:
        try:
            result = subprocess.run(
                self._build_schtasks_command(),
                capture_output=True,
            )
            return result.returncode == 0
        except Exception:  # noqa: BLE001
            return False

    def uninstall_service(self) -> bool:
        try:
            result = subprocess.run(
                ["schtasks", "/Delete", "/F", "/TN", self._TASK_NAME],
                capture_output=True,
            )
            return result.returncode == 0
        except Exception:  # noqa: BLE001
            return False

    def is_running(self) -> bool:
        try:
            result = subprocess.run(
                ["schtasks", "/Query", "/TN", self._TASK_NAME, "/FO", "LIST"],
                capture_output=True,
                text=True,
            )
            return result.returncode == 0 and "Running" in result.stdout
        except Exception:  # noqa: BLE001
            return False

    def start(self) -> bool:
        try:
            result = subprocess.run(
                ["schtasks", "/Run", "/TN", self._TASK_NAME],
                capture_output=True,
            )
            return result.returncode == 0
        except Exception:  # noqa: BLE001
            return False

    def stop(self) -> bool:
        try:
            result = subprocess.run(
                ["schtasks", "/End", "/TN", self._TASK_NAME],
                capture_output=True,
            )
            return result.returncode == 0
        except Exception:  # noqa: BLE001
            return False


def detect_platform() -> PlatformAdapter:
    """Return the correct adapter for the current operating system."""
    daemon_script = _default_daemon_script()
    if sys.platform == "darwin":
        return MacOSAdapter(daemon_script=daemon_script)
    if sys.platform.startswith("linux"):
        return LinuxAdapter(daemon_script=daemon_script)
    if sys.platform == "win32":
        return WindowsAdapter(daemon_script=daemon_script)
    raise RuntimeError(f"Unsupported platform: {sys.platform}")
