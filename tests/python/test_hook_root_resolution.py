"""Regression: hook wrappers must survive an npx cache purge (QG B1).

The wrappers export ARKAOS_ROOT for `-m core.hooks.*`. Before the fix they
read `.repo-path` raw; with the cache purged they exported a dead root and
every gate silently failed open. Now they resolve through
arka_resolve_root() in config/hooks/_lib/arka_python.sh, which falls
through to the ~/.arkaos/lib snapshot. These tests drive the REAL
pre-tool-use.sh wrapper end-to-end with a fake HOME.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_SRC = REPO_ROOT / "config" / "hooks"


def _deploy_wrapper(install: Path) -> Path:
    hooks = install / "config" / "hooks"
    hooks.mkdir(parents=True)
    shutil.copy2(HOOKS_SRC / "pre-tool-use.sh", hooks / "pre-tool-use.sh")
    shutil.copytree(HOOKS_SRC / "_lib", hooks / "_lib")
    return hooks / "pre-tool-use.sh"


def _write_fake_core(root: Path) -> None:
    hooks_pkg = root / "core" / "hooks"
    hooks_pkg.mkdir(parents=True)
    (root / "core" / "__init__.py").touch()
    (root / "core" / "sync").mkdir()
    (root / "core" / "sync" / "__init__.py").touch()
    (hooks_pkg / "__init__.py").touch()
    # Prints the root it executed from, so the assertion proves WHERE
    # `-m core.hooks.pre_tool_use` was resolved, not just that it ran.
    (hooks_pkg / "pre_tool_use.py").write_text(
        "import pathlib, sys\n"
        "sys.stdin.read()\n"
        "print('RESOLVED_FROM=' + str(pathlib.Path(__file__).resolve().parents[2]))\n",
        encoding="utf-8",
    )


def _run_wrapper(
    wrapper: Path, home: Path, extra_env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    env = {
        "PATH": os.environ["PATH"],
        "HOME": str(home),
        **(extra_env or {}),
    }
    # cwd MUST be neutral: `python -m` puts the cwd first on sys.path, so
    # running from the repo would resolve the real core package and mask
    # exactly the failure this suite guards against (works from the repo
    # cwd, breaks everywhere else).
    return subprocess.run(
        ["bash", str(wrapper)],
        input="{}",
        env=env,
        cwd=str(home),
        capture_output=True,
        text=True,
        timeout=30,
    )


@pytest.fixture()
def purged_cache_home(tmp_path: Path) -> tuple[Path, Path]:
    home = tmp_path / "home"
    (home / ".arkaos").mkdir(parents=True)
    (home / ".arkaos" / ".repo-path").write_text(
        str(tmp_path / "npx-cache-that-npm-clean-purged"), encoding="utf-8"
    )
    wrapper = _deploy_wrapper(home / ".arkaos")
    return home, wrapper


def test_hook_resolves_core_from_snapshot_after_cache_purge(
    purged_cache_home: tuple[Path, Path],
) -> None:
    home, wrapper = purged_cache_home
    lib = home / ".arkaos" / "lib"
    _write_fake_core(lib)

    result = _run_wrapper(wrapper, home)

    assert result.returncode == 0, result.stderr
    assert f"RESOLVED_FROM={lib.resolve()}" in result.stdout


def test_hook_still_fails_open_when_no_snapshot_exists(
    purged_cache_home: tuple[Path, Path],
) -> None:
    # Purged cache AND no snapshot: the wrapper must keep the fail-open
    # contract (exit 0, no crash) instead of blocking every tool call.
    home, wrapper = purged_cache_home

    result = _run_wrapper(wrapper, home)

    assert result.returncode == 0, result.stderr


def test_hook_env_override_still_wins(purged_cache_home: tuple[Path, Path], tmp_path: Path) -> None:
    home, wrapper = purged_cache_home
    _write_fake_core(home / ".arkaos" / "lib")
    override = tmp_path / "operator-choice"
    _write_fake_core(override)

    result = _run_wrapper(wrapper, home, {"ARKAOS_ROOT": str(override)})

    assert result.returncode == 0, result.stderr
    assert f"RESOLVED_FROM={override.resolve()}" in result.stdout
