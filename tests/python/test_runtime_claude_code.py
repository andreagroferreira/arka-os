"""core.runtime.claude_code — version-gated feature support (Runtime Sync PR1).

Before this, ``supports_feature`` answered True for every string, so nothing
in ArkaOS could tell a 2.1.240 binary from the 2.1.259 it was written
against. The floors are changelog facts (verified 2026-09-03), the binary
probe is cached once per process, and an unknown version answers False.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from core.runtime.claude_code import (
    FEATURE_FLOORS,
    VERSION_ENV,
    ClaudeCodeAdapter,
    detect_claude_code_version,
    parse_version,
    reset_version_cache,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCTOR_JS = REPO_ROOT / "installer" / "doctor.js"


Version = tuple[int, int, int] | None


@pytest.fixture(autouse=True)
def _fresh_probe(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.delenv(VERSION_ENV, raising=False)
    reset_version_cache()
    yield
    reset_version_cache()


def _fake_run(stdout: str, returncode: int = 0) -> Callable[..., subprocess.CompletedProcess[str]]:
    def run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(argv, returncode, stdout=stdout, stderr="")

    return run


def _binary_at(monkeypatch: pytest.MonkeyPatch, path: str | None) -> None:
    """Point the probe's `shutil.which` at a fake binary (or at nothing).

    The adapter resolves `shutil` and `subprocess` as shared module
    objects, so patching those modules directly is both mypy-clean and
    the honest seam.
    """
    monkeypatch.setattr(shutil, "which", lambda name: path)


class TestFloors:
    def test_floors_are_the_changelog_facts(self) -> None:
        assert FEATURE_FLOORS == {
            "fallback_model_setting": (2, 1, 166),
            "fork_default": (2, 1, 232),
            "todo_tools_removed": (2, 1, 233),
            "hook_json_strict": (2, 1, 248),
            "pre_model_switch": (2, 1, 251),
            "fable_5_1": (2, 1, 257),
            "subagent_model_force": (2, 1, 257),
            "block_reads_outside_cwd": (2, 1, 257),
        }

    def test_doctor_floor_equals_the_highest_feature_floor(self) -> None:
        """installer/doctor.js and this table are two copies of one
        truth; parse the JS pin rather than trust a comment."""
        source = DOCTOR_JS.read_text(encoding="utf-8")
        match = re.search(r'export const CLAUDE_CODE_MIN_VERSION = "(\d+)\.(\d+)\.(\d+)";', source)
        assert match, "CLAUDE_CODE_MIN_VERSION pin not found in installer/doctor.js"
        assert tuple(int(g) for g in match.groups()) == max(FEATURE_FLOORS.values())


class TestParseVersion:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("2.1.259 (Claude Code)", (2, 1, 259)),
            ("2.1.257", (2, 1, 257)),
            ("claude mock 0.0.0", (0, 0, 0)),
            ("v2.2.0-beta", (2, 2, 0)),
            ("", None),
            (None, None),
            ("no version here", None),
        ],
    )
    def test_first_dotted_triple(self, text: str | None, expected: Version) -> None:
        assert parse_version(text) == expected


class TestDetect:
    def test_env_override_wins_and_is_read_every_call(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _binary_at(monkeypatch, "/nope/claude")
        monkeypatch.setattr(subprocess, "run", _fake_run("2.1.259"))
        monkeypatch.setenv(VERSION_ENV, "2.1.240")
        assert detect_claude_code_version() == (2, 1, 240)
        monkeypatch.setenv(VERSION_ENV, "2.1.259 (Claude Code)")
        assert detect_claude_code_version() == (2, 1, 259), "override must not be cached"

    def test_env_override_never_consults_the_binary(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def boom(*args: object, **kwargs: object) -> None:
            raise AssertionError("binary probed despite the override")

        monkeypatch.setattr(subprocess, "run", boom)
        monkeypatch.setenv(VERSION_ENV, "2.1.250")
        assert detect_claude_code_version() == (2, 1, 250)

    def test_unparsable_override_is_unknown(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(VERSION_ENV, "latest")
        assert detect_claude_code_version() is None

    def test_no_binary_is_unknown_without_raising(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _binary_at(monkeypatch, None)
        assert detect_claude_code_version() is None

    def test_probe_is_cached_once_per_process(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[list[str]] = []

        def run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            calls.append(list(argv))
            return subprocess.CompletedProcess(argv, 0, stdout="2.1.259 (Claude Code)", stderr="")

        _binary_at(monkeypatch, "/opt/bin/claude")
        monkeypatch.setattr(subprocess, "run", run)
        assert detect_claude_code_version() == (2, 1, 259)
        assert detect_claude_code_version() == (2, 1, 259)
        assert calls == [["/opt/bin/claude", "--version"]]

    def test_reset_forgets_the_probe(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _binary_at(monkeypatch, "/opt/bin/claude")
        monkeypatch.setattr(subprocess, "run", _fake_run("2.1.240"))
        assert detect_claude_code_version() == (2, 1, 240)
        monkeypatch.setattr(subprocess, "run", _fake_run("2.1.259"))
        assert detect_claude_code_version() == (2, 1, 240), "still the cached answer"
        reset_version_cache()
        assert detect_claude_code_version() == (2, 1, 259)

    def test_failing_probe_is_unknown(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _binary_at(monkeypatch, "/opt/bin/claude")
        monkeypatch.setattr(subprocess, "run", _fake_run("2.1.259", returncode=1))
        assert detect_claude_code_version() is None

    def test_probe_error_is_unknown(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            raise subprocess.TimeoutExpired(argv, 10)

        _binary_at(monkeypatch, "/opt/bin/claude")
        monkeypatch.setattr(subprocess, "run", run)
        assert detect_claude_code_version() is None


class TestSupportsFeature:
    @pytest.mark.parametrize(
        "version,expected",
        [
            ("2.1.250", False),
            ("2.1.256", False),
            ("2.1.257", True),
            ("2.1.259", True),
            ("2.2.0", True),
        ],
    )
    def test_fable_5_1_is_gated_on_its_floor(
        self, monkeypatch: pytest.MonkeyPatch, version: str, expected: bool
    ) -> None:
        monkeypatch.setenv(VERSION_ENV, version)
        assert ClaudeCodeAdapter().supports_feature("fable_5_1") is expected

    def test_every_floored_feature_holds_on_the_current_binary(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(VERSION_ENV, "2.1.259 (Claude Code)")
        adapter = ClaudeCodeAdapter()
        assert all(adapter.supports_feature(feature) for feature in FEATURE_FLOORS)

    def test_unknown_version_is_conservative_and_never_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _binary_at(monkeypatch, None)
        adapter = ClaudeCodeAdapter()
        assert all(adapter.supports_feature(feature) is False for feature in FEATURE_FLOORS)

    def test_config_and_static_features_are_not_version_gated(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _binary_at(monkeypatch, None)
        adapter = ClaudeCodeAdapter()
        assert adapter.supports_feature("hooks") is True
        assert adapter.supports_feature("subagents") is True
        assert adapter.supports_feature("mcp") is True
        assert adapter.supports_feature("parallel_agents") is True
        assert adapter.supports_feature("worktrees") is True

    def test_unknown_feature_is_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(VERSION_ENV, "2.1.259")
        assert ClaudeCodeAdapter().supports_feature("teleportation") is False

    def test_capabilities_matrix_is_unchanged(self) -> None:
        assert ClaudeCodeAdapter().capabilities() == {
            "agent_dispatch": True,
            "headless": True,
            "file_ops": True,
            "hooks": True,
        }
