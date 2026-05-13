"""Tests for core.runtime.path_resolver.

Validates the contract documented in
``core/specs/SPEC-paths-portability.md`` (PR1 v2.23.0). Each test maps
to a numbered scenario in the spec's *Test Scenarios* table.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from core.runtime import path_resolver
from core.runtime.path_resolver import (
    ProfileMissingError,
    ProfileV3,
    _derive_project_roots,
    load_profile,
    project_root_regex,
    reset_cache,
    resolve,
    resolve_dict,
)


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    """Each test runs against an isolated ~/.arkaos and clean env."""
    fake_home = tmp_path / "home"
    arkaos_dir = fake_home / ".arkaos"
    arkaos_dir.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(fake_home))
    for var in (
        "ARKAOS_VAULT_PATH",
        "ARKAOS_VAULT",
        "ARKAOS_REPOS_ROOT",
        "ARKAOS_PROJECT_ROOTS",
        "ARKAOS_GIT_HOST",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(
        "core.runtime.path_resolver.user_data_root", lambda: arkaos_dir
    )
    reset_cache()
    yield arkaos_dir
    reset_cache()


def _write_profile(arkaos_dir: Path, **overrides) -> None:
    base = {
        "version": "3",
        "vaultPath": "/v",
        "reposRoot": "/r",
        "projectRoots": ["/p1", "/p2"],
    }
    base.update(overrides)
    (arkaos_dir / "profile.json").write_text(json.dumps(base), encoding="utf-8")


def test_scenario_1_resolve_vault_path_token(_isolate):
    _write_profile(_isolate, vaultPath="/v")
    assert resolve("${VAULT_PATH}/foo") == "/v/foo"


def test_scenario_2_resolve_home_token(_isolate, monkeypatch):
    _write_profile(_isolate)
    monkeypatch.setenv("HOME", "/expanded")
    assert resolve("${HOME}/bar") == "/expanded/bar"


def test_scenario_3_unknown_token_passes_through(_isolate):
    _write_profile(_isolate)
    assert resolve("${UNKNOWN}/baz") == "${UNKNOWN}/baz"
    assert resolve("Run echo ${SHELL_VAR} inside") == "Run echo ${SHELL_VAR} inside"


def test_scenario_4_missing_profile_raises(_isolate):
    with pytest.raises(ProfileMissingError, match="Run /arka setup"):
        resolve("${VAULT_PATH}/anything")


def test_scenario_4b_corrupt_profile_raises(_isolate):
    (_isolate / "profile.json").write_text("{not valid json", encoding="utf-8")
    with pytest.raises(ProfileMissingError, match="could not be parsed"):
        load_profile(refresh=True)


def test_scenario_5_env_var_overrides_profile(_isolate, monkeypatch):
    _write_profile(_isolate, vaultPath="/from-profile")
    monkeypatch.setenv("ARKAOS_VAULT_PATH", "/from-env")
    assert resolve("${VAULT_PATH}/x") == "/from-env/x"


def test_scenario_5b_legacy_arkaos_vault_env_supported(_isolate, monkeypatch):
    _write_profile(_isolate, vaultPath="/p")
    monkeypatch.setenv("ARKAOS_VAULT", "/legacy-env")
    assert resolve("${VAULT_PATH}/y") == "/legacy-env/y"


def test_scenario_5c_arkaos_vault_path_wins_over_legacy(_isolate, monkeypatch):
    _write_profile(_isolate, vaultPath="/p")
    monkeypatch.setenv("ARKAOS_VAULT", "/legacy")
    monkeypatch.setenv("ARKAOS_VAULT_PATH", "/new")
    assert resolve("${VAULT_PATH}") == "/new"


def test_scenario_6_resolve_dict_recursive(_isolate):
    _write_profile(_isolate, vaultPath="/v", reposRoot="/r")
    payload = {
        "a": "${VAULT_PATH}/x",
        "b": ["${VAULT_PATH}", "${ARKA_OS_REPOS}"],
        "c": {"nested": "${ARKA_OS_REPOS}/y"},
        "d": 42,
    }
    out = resolve_dict(payload)
    assert out == {
        "a": "/v/x",
        "b": ["/v", "/r"],
        "c": {"nested": "/r/y"},
        "d": 42,
    }


def test_scenario_7_project_root_regex_matches_configured_root(_isolate):
    _write_profile(_isolate, projectRoots=["/tmp/herd", "/tmp/work"])
    rx = project_root_regex()
    match = rx.search("digest mentions /tmp/work/mvp-api/file.py here")
    assert match is not None
    assert match.group(2) == "mvp-api"


def test_scenario_8_project_root_regex_handles_windows_paths(_isolate):
    _write_profile(_isolate, projectRoots=["C:\\Users\\dev\\Work"])
    rx = project_root_regex()
    match = rx.search("log: C:\\Users\\dev\\Work\\myproj\\src")
    assert match is not None
    assert match.group(2) == "myproj"


def test_scenario_11_legacy_profile_auto_derives_project_roots(_isolate):
    """Legacy v2 profile with free-text projectsDir migrates in-memory."""
    legacy = {
        "version": "2",
        "vaultPath": "/v",
        "projectsDir": (
            "/Users/jane/Herd para Laravel, /Users/jane/Work para Nuxt, "
            "/Users/jane/AIProjects para Python"
        ),
    }
    (_isolate / "profile.json").write_text(json.dumps(legacy), encoding="utf-8")
    profile = load_profile()
    assert profile.project_roots == [
        "/Users/jane/Herd",
        "/Users/jane/Work",
        "/Users/jane/AIProjects",
    ]
    assert profile.repos_root == "~/AIProjects"


def test_scenario_11b_legacy_profile_with_no_paths_uses_defaults(_isolate):
    legacy = {"version": "2", "vaultPath": "/v", "projectsDir": ""}
    (_isolate / "profile.json").write_text(json.dumps(legacy), encoding="utf-8")
    profile = load_profile()
    assert profile.project_roots == ["~/Herd", "~/Work", "~/AIProjects"]


def test_scenario_13_no_critical_grep_hits_in_resolver_module():
    """The resolver itself must contain no hardcoded user paths."""
    src = Path(__file__).resolve().parents[2] / "core/runtime/path_resolver.py"
    text = src.read_text(encoding="utf-8")
    assert "andreagroferreira" not in text


def test_scenario_14_git_host_env_overrides_default(_isolate, monkeypatch):
    _write_profile(_isolate)
    assert resolve("clone from ${GIT_HOST}") == "clone from github.com"
    monkeypatch.setenv("ARKAOS_GIT_HOST", "gitlab.example.com")
    assert resolve("clone from ${GIT_HOST}") == "clone from gitlab.example.com"


def test_scenario_15_arka_os_repos_token(_isolate):
    _write_profile(_isolate, reposRoot="/repos")
    assert resolve("${ARKA_OS_REPOS}/comfyui") == "/repos/comfyui"


def test_scenario_16_empty_projects_dir_falls_back_to_defaults(_isolate):
    _write_profile(_isolate, projectRoots=[])
    profile = load_profile()
    assert profile.project_roots == ["~/Herd", "~/Work", "~/AIProjects"]


def test_scenario_17_empty_env_string_treated_as_unset(_isolate, monkeypatch):
    _write_profile(_isolate, vaultPath="/profile-wins")
    monkeypatch.setenv("ARKAOS_VAULT_PATH", "")
    assert resolve("${VAULT_PATH}") == "/profile-wins"


def test_load_profile_caches_until_refresh(_isolate):
    _write_profile(_isolate, vaultPath="/first")
    assert load_profile().vault_path == "/first"
    _write_profile(_isolate, vaultPath="/second")
    assert load_profile().vault_path == "/first"
    assert load_profile(refresh=True).vault_path == "/second"


def test_profile_v3_dataclass_is_frozen():
    p = ProfileV3(
        version="3",
        vault_path="/v",
        repos_root="/r",
        project_roots=["/p"],
        raw={},
    )
    with pytest.raises(Exception):
        p.vault_path = "/mutated"  # type: ignore[misc]


def test_derive_project_roots_handles_linux_paths():
    text = "/home/user/Herd then /home/user/Work"
    assert _derive_project_roots(text) == [
        "/home/user/Herd",
        "/home/user/Work",
    ]


def test_derive_project_roots_handles_mixed_separators():
    text = "C:\\Users\\dev\\Work and /Users/dev/AIProjects"
    roots = _derive_project_roots(text)
    assert "C:\\Users\\dev\\Work" in roots
    assert "/Users/dev/AIProjects" in roots


def test_missing_vault_path_in_profile_raises(_isolate):
    (_isolate / "profile.json").write_text(
        json.dumps({"version": "3", "vaultPath": ""}), encoding="utf-8"
    )
    with pytest.raises(ProfileMissingError, match="no vaultPath"):
        load_profile()


def test_project_roots_uses_os_pathsep(_isolate):
    _write_profile(_isolate, projectRoots=["/a", "/b"])
    result = resolve("${PROJECT_ROOTS}")
    assert result == os.pathsep.join(["/a", "/b"])
