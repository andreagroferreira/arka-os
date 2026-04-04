"""Smoke tests for the ArkaOS installer."""

import pytest
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.parent


class TestInstallerSyntax:
    """All installer JS files must have valid syntax."""

    @pytest.mark.parametrize("js_file", [
        "installer/cli.js",
        "installer/index.js",
        "installer/detect-runtime.js",
        "installer/doctor.js",
        "installer/update.js",
        "installer/uninstall.js",
        "installer/adapters/claude-code.js",
        "installer/adapters/codex-cli.js",
        "installer/adapters/gemini-cli.js",
        "installer/adapters/cursor.js",
    ])
    def test_js_syntax_valid(self, js_file):
        path = BASE_DIR / js_file
        if path.exists():
            result = subprocess.run(
                ["node", "--check", str(path)],
                capture_output=True, text=True,
            )
            assert result.returncode == 0, f"{js_file} syntax error: {result.stderr}"


class TestInstallerHelp:
    def test_cli_help_runs(self):
        result = subprocess.run(
            ["node", str(BASE_DIR / "installer" / "cli.js"), "--help"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "ArkaOS" in result.stdout
        assert "install" in result.stdout

    def test_cli_version_runs(self):
        result = subprocess.run(
            ["node", str(BASE_DIR / "installer" / "cli.js"), "--version"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "2.0.0" in result.stdout


class TestHookScripts:
    """Hook scripts must be executable and valid bash."""

    @pytest.mark.parametrize("hook", [
        "config/hooks/user-prompt-submit-v2.sh",
        "config/hooks/post-tool-use-v2.sh",
        "config/hooks/pre-compact-v2.sh",
    ])
    def test_hook_is_bash(self, hook):
        path = BASE_DIR / hook
        if path.exists():
            content = path.read_text()
            assert content.startswith("#!/usr/bin/env bash"), f"{hook} missing bash shebang"

    @pytest.mark.parametrize("hook", [
        "config/hooks/user-prompt-submit-v2.sh",
        "config/hooks/post-tool-use-v2.sh",
        "config/hooks/pre-compact-v2.sh",
    ])
    def test_hook_syntax_valid(self, hook):
        path = BASE_DIR / hook
        if path.exists():
            result = subprocess.run(
                ["bash", "-n", str(path)],
                capture_output=True, text=True,
            )
            assert result.returncode == 0, f"{hook} syntax error: {result.stderr}"


class TestBinCLI:
    def test_arkaos_bin_exists(self):
        assert (BASE_DIR / "bin" / "arkaos").exists()

    def test_arkaos_bin_is_executable(self):
        path = BASE_DIR / "bin" / "arkaos"
        import os
        assert os.access(path, os.X_OK), "bin/arkaos is not executable"

    def test_arkaos_bin_shows_help(self):
        result = subprocess.run(
            [str(BASE_DIR / "bin" / "arkaos"), "help"],
            capture_output=True, text=True,
            env={**__import__("os").environ, "HOME": "/tmp/arkaos-test"},
        )
        assert "ArkaOS" in result.stdout
        assert "install" in result.stdout


class TestPackageJson:
    def test_package_json_valid(self):
        import json
        pkg = json.loads((BASE_DIR / "package.json").read_text())
        assert pkg["name"] == "arkaos"
        assert "2.0.0" in pkg["version"]
        assert "arkaos" in pkg["bin"]

    def test_pyproject_valid(self):
        content = (BASE_DIR / "pyproject.toml").read_text()
        assert "arkaos-core" in content
        assert "pydantic" in content
