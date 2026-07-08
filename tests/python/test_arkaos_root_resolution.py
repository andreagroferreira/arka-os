"""resolve_arkaos_root must survive an npx cache purge.

`.repo-path` points at the npx cache `npm cache clean` can delete at any
time; the resolver has to fall through to the ~/.arkaos/lib snapshot the
installer writes, instead of handing hooks a dangling root (the v4.3.6
`/arka update` failure mode: core.sync unresolvable outside the repo cwd).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.hooks._shared import resolve_arkaos_root


def _write_core_package(root: Path, *, with_sync: bool = True) -> None:
    (root / "core" / "hooks").mkdir(parents=True, exist_ok=True)
    (root / "core" / "__init__.py").touch()
    (root / "core" / "hooks" / "__init__.py").touch()
    if with_sync:
        (root / "core" / "sync").mkdir(parents=True, exist_ok=True)
        (root / "core" / "sync" / "__init__.py").touch()


@pytest.fixture()
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    monkeypatch.delenv("ARKAOS_ROOT", raising=False)
    monkeypatch.delenv("ARKA_OS", raising=False)
    (tmp_path / ".arkaos").mkdir()
    return tmp_path


def _point_repo_path(home: Path, target: Path) -> None:
    (home / ".arkaos" / ".repo-path").write_text(str(target), encoding="utf-8")


def test_env_override_wins_unconditionally(fake_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARKAOS_ROOT", "/explicit/operator/choice")
    assert resolve_arkaos_root() == "/explicit/operator/choice"


def test_valid_repo_path_is_used(fake_home: Path, tmp_path: Path) -> None:
    repo = tmp_path / "npx-cache" / "arkaos"
    _write_core_package(repo)
    _point_repo_path(fake_home, repo)
    assert resolve_arkaos_root() == str(repo)


def test_pruned_npx_cache_falls_back_to_lib_snapshot(fake_home: Path, tmp_path: Path) -> None:
    _point_repo_path(fake_home, tmp_path / "npx-cache-that-was-purged")
    lib = fake_home / ".arkaos" / "lib"
    _write_core_package(lib)
    assert resolve_arkaos_root() == str(lib)


def test_partial_core_copy_does_not_win_over_snapshot(fake_home: Path, tmp_path: Path) -> None:
    # The cognitive scheduler's ~/.arkaos/core copy has no core/sync —
    # a root like that must not be trusted for `-m core.sync.*`.
    partial = tmp_path / "partial-root"
    _write_core_package(partial, with_sync=False)
    _point_repo_path(fake_home, partial)
    lib = fake_home / ".arkaos" / "lib"
    _write_core_package(lib)
    assert resolve_arkaos_root() == str(lib)


def test_existing_repo_dir_kept_as_legacy_fallback(fake_home: Path, tmp_path: Path) -> None:
    # No snapshot: an existing-but-coreless repo dir still wins over
    # ~/.arkaos so legacy VERSION readers keep working.
    partial = tmp_path / "partial-root"
    _write_core_package(partial, with_sync=False)
    _point_repo_path(fake_home, partial)
    assert resolve_arkaos_root() == str(partial)


def test_last_resort_is_arkaos_dir(fake_home: Path) -> None:
    assert resolve_arkaos_root() == str(fake_home / ".arkaos")
