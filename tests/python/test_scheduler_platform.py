"""Tests for cross-platform service adapters."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from core.cognition.scheduler.platform import (
    LinuxAdapter,
    MacOSAdapter,
    PlatformAdapter,
    WindowsAdapter,
    detect_platform,
)


# ---------------------------------------------------------------------------
# TestPlatformDetection
# ---------------------------------------------------------------------------

class TestPlatformDetection:
    def test_detect_returns_adapter(self) -> None:
        """detect_platform always returns a PlatformAdapter instance."""
        adapter = detect_platform()
        assert isinstance(adapter, PlatformAdapter)

    def test_detect_matches_current_os(self) -> None:
        """detect_platform returns the adapter matching the current platform."""
        adapter = detect_platform()
        if sys.platform == "darwin":
            assert isinstance(adapter, MacOSAdapter)
        elif sys.platform.startswith("linux"):
            assert isinstance(adapter, LinuxAdapter)
        elif sys.platform == "win32":
            assert isinstance(adapter, WindowsAdapter)

    def test_detect_unsupported_platform_raises(self) -> None:
        """detect_platform raises RuntimeError for unknown platforms."""
        with patch.object(sys, "platform", "freebsd12"):
            with pytest.raises(RuntimeError, match="Unsupported platform"):
                detect_platform()

    def test_detect_uses_default_daemon_script(self) -> None:
        """The detected adapter's daemon_script defaults to ~/.arkaos/bin/scheduler-daemon.py."""
        adapter = detect_platform()
        expected = str(Path.home() / ".arkaos" / "bin" / "scheduler-daemon.py")
        if isinstance(adapter, MacOSAdapter):
            assert adapter._daemon_script == expected
        elif isinstance(adapter, LinuxAdapter):
            assert adapter._daemon_script == expected
        elif isinstance(adapter, WindowsAdapter):
            assert adapter._daemon_script == expected


# ---------------------------------------------------------------------------
# TestMacOSAdapter
# ---------------------------------------------------------------------------

class TestMacOSAdapter:
    @pytest.fixture()
    def adapter(self, tmp_path: Path) -> MacOSAdapter:
        return MacOSAdapter(
            daemon_script="/usr/local/bin/scheduler-daemon.py",
            plist_dir=str(tmp_path),
        )

    def test_plist_path(self, adapter: MacOSAdapter, tmp_path: Path) -> None:
        """Plist path ends with the correct filename inside the given dir."""
        path = adapter._plist_path()
        assert path == str(tmp_path / "com.arkaos.scheduler.plist")

    def test_generates_plist(self, adapter: MacOSAdapter) -> None:
        """Generated plist contains required keys and values."""
        plist = adapter._generate_plist()
        assert "Label" in plist
        assert "com.arkaos.scheduler" in plist
        assert "ProgramArguments" in plist
        assert "scheduler-daemon.py" in plist
        assert "RunAtLoad" in plist
        assert "KeepAlive" in plist
        assert "<true/>" in plist

    def test_generates_plist_log_paths(self, adapter: MacOSAdapter) -> None:
        """Generated plist includes stdout/stderr log paths under ~/.arkaos/logs/."""
        plist = adapter._generate_plist()
        assert ".arkaos/logs" in plist
        assert "StandardOutPath" in plist
        assert "StandardErrorPath" in plist

    def test_generates_plist_with_environment_variables(self, adapter: MacOSAdapter) -> None:
        """Generated plist injects PATH with known Claude binary locations."""
        plist = adapter._generate_plist()
        assert "EnvironmentVariables" in plist
        assert ".local/bin" in plist
        assert ".arkaos/bin" in plist
        assert "<key>PATH</key>" in plist
        assert "<key>HOME</key>" in plist

    def test_platform_name(self, adapter: MacOSAdapter) -> None:
        assert adapter.platform_name == "macos"

    def test_install_writes_plist_file(self, adapter: MacOSAdapter, tmp_path: Path) -> None:
        """install_service writes the plist file to disk."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            adapter.install_service()

        plist = tmp_path / "com.arkaos.scheduler.plist"
        assert plist.exists()
        assert "com.arkaos.scheduler" in plist.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# TestLinuxAdapter
# ---------------------------------------------------------------------------

class TestLinuxAdapter:
    @pytest.fixture()
    def adapter(self, tmp_path: Path) -> LinuxAdapter:
        return LinuxAdapter(
            daemon_script="/usr/local/bin/scheduler-daemon.py",
            service_dir=str(tmp_path),
        )

    def test_service_path(self, adapter: LinuxAdapter, tmp_path: Path) -> None:
        """Service path ends with the correct filename inside the given dir."""
        path = adapter._service_path()
        assert path == str(tmp_path / "arkaos-scheduler.service")

    def test_generates_unit_file(self, adapter: LinuxAdapter) -> None:
        """Generated unit file contains required systemd sections and directives."""
        unit = adapter._generate_unit()
        assert "[Unit]" in unit
        assert "[Service]" in unit
        assert "[Install]" in unit
        assert "scheduler-daemon.py" in unit
        assert "Type=simple" in unit
        assert "Restart=on-failure" in unit
        assert "RestartSec=60" in unit
        assert "WantedBy=default.target" in unit

    def test_generates_unit_with_path_environment(self, adapter: LinuxAdapter) -> None:
        """Generated unit injects PATH with known Claude binary locations."""
        unit = adapter._generate_unit()
        assert "Environment=PATH=" in unit
        assert ".local/bin" in unit
        assert ".arkaos/bin" in unit

    def test_platform_name(self, adapter: LinuxAdapter) -> None:
        assert adapter.platform_name == "linux"

    def test_install_writes_unit_file(self, adapter: LinuxAdapter, tmp_path: Path) -> None:
        """install_service writes the unit file to disk."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            adapter.install_service()

        service = tmp_path / "arkaos-scheduler.service"
        assert service.exists()
        assert "[Unit]" in service.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# TestWindowsAdapter
# ---------------------------------------------------------------------------

class TestWindowsAdapter:
    @pytest.fixture()
    def adapter(self) -> WindowsAdapter:
        return WindowsAdapter(daemon_script="C:\\arkaos\\scheduler-daemon.py")

    def test_generates_task_command(self, adapter: WindowsAdapter) -> None:
        """schtasks command contains required flags and task name."""
        cmd = adapter._build_schtasks_command()
        assert "schtasks" in cmd
        assert "ArkaOS-Scheduler" in cmd
        assert "/Create" in cmd
        assert "/SC" in cmd
        assert "ONLOGON" in cmd
        assert "/TN" in cmd

    def test_generates_task_command_includes_script(self, adapter: WindowsAdapter) -> None:
        """schtasks command includes the daemon script path."""
        cmd = adapter._build_schtasks_command()
        tr_value = cmd[cmd.index("/TR") + 1]
        assert "scheduler-daemon.py" in tr_value

    def test_platform_name(self, adapter: WindowsAdapter) -> None:
        assert adapter.platform_name == "windows"

    def test_install_calls_schtasks(self, adapter: WindowsAdapter) -> None:
        """install_service calls subprocess with schtasks /Create."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            result = adapter.install_service()

        assert result is True
        call_args = mock_run.call_args[0][0]
        assert "schtasks" in call_args
        assert "/Create" in call_args

    def test_task_run_uses_console_less_interpreter(self, adapter: WindowsAdapter) -> None:
        """The logon task launches pythonw.exe, never python.exe.

        python.exe forces Windows to allocate a console for a daemon that
        outlives the login session; the window then stays open for hours and
        closing it kills the scheduler.
        """
        venv_python = "C:\\Users\\op\\.arkaos\\venv\\Scripts\\python.exe"
        with patch(
            "core.cognition.scheduler.platform._python_executable",
            return_value=venv_python,
        ):
            with patch.object(Path, "is_file", return_value=True):
                cmd = adapter._build_schtasks_command()

        tr_value = cmd[cmd.index("/TR") + 1]
        assert "pythonw.exe" in tr_value
        assert "\\python.exe" not in tr_value

    def test_task_run_falls_back_when_pythonw_absent(self, adapter: WindowsAdapter) -> None:
        """Without pythonw.exe the daemon still installs, console and all.

        Embeddable distributions ship no pythonw.exe. A missing console-less
        interpreter must degrade the experience, not block installation.
        """
        venv_python = "C:\\Users\\op\\.arkaos\\venv\\Scripts\\python.exe"
        with patch(
            "core.cognition.scheduler.platform._python_executable",
            return_value=venv_python,
        ):
            with patch.object(Path, "is_file", return_value=False):
                cmd = adapter._build_schtasks_command()

        tr_value = cmd[cmd.index("/TR") + 1]
        assert "python.exe" in tr_value

    def test_task_run_quotes_both_paths(self) -> None:
        """/TR quotes the interpreter and the script.

        schtasks splits an unquoted /TR on the first space, so a profile like
        C:\\Users\\John Doe\\ produced an invalid task.
        """
        spaced = WindowsAdapter(daemon_script="C:\\Users\\John Doe\\.arkaos\\daemon.py")
        interpreter = "C:\\Users\\John Doe\\.arkaos\\venv\\Scripts\\python.exe"
        with patch(
            "core.cognition.scheduler.platform._python_executable",
            return_value=interpreter,
        ):
            with patch.object(Path, "is_file", return_value=True):
                cmd = spaced._build_schtasks_command()

        tr_value = cmd[cmd.index("/TR") + 1]
        assert tr_value.startswith('"')
        assert tr_value.endswith('"')
        assert tr_value.count('"') == 4


# ---------------------------------------------------------------------------
# TestPosixGeneratorsUnaffected
#
# The Windows console fix must not reach launchd or systemd. These tests pin
# the two POSIX generators to the shared resolver, so any future attempt to
# route them through a Windows-specific interpreter fails here.
# ---------------------------------------------------------------------------

class TestPosixGeneratorsUnaffected:
    def test_plist_uses_shared_resolver_only(self, tmp_path: Path) -> None:
        """The launchd plist is built from _python_executable, untouched."""
        adapter = MacOSAdapter(
            daemon_script="/usr/local/bin/scheduler-daemon.py",
            plist_dir=str(tmp_path),
        )
        with patch(
            "core.cognition.scheduler.platform._python_executable",
            return_value="/opt/arkaos/bin/python3",
        ):
            plist = adapter._generate_plist()

        assert "<string>/opt/arkaos/bin/python3</string>" in plist
        assert "pythonw" not in plist

    def test_unit_uses_shared_resolver_only(self, tmp_path: Path) -> None:
        """The systemd unit is built from _python_executable, untouched."""
        adapter = LinuxAdapter(
            daemon_script="/usr/local/bin/scheduler-daemon.py",
            service_dir=str(tmp_path),
        )
        with patch(
            "core.cognition.scheduler.platform._python_executable",
            return_value="/opt/arkaos/bin/python3",
        ):
            unit = adapter._generate_unit()

        assert "ExecStart=/opt/arkaos/bin/python3 /usr/local/bin/scheduler-daemon.py" in unit
        assert "pythonw" not in unit
