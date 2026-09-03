"""core.harness.manager — assert under the policies, audit, flags.

Every test drives a full tmp HOME + fake ArkaOS root; nothing touches
the real machine.
"""

import json
from pathlib import Path

import pytest

from core.harness import cli, drift, paths
from core.harness.manager import FLAG_NAMES, ClaudeConfigManager
from core.harness.spec import spec_for

SPEC = spec_for("claude-code")


@pytest.fixture
def env(tmp_path):
    """(home, hooks_root) with every spec script deployed."""
    hooks = tmp_path / "root" / "config" / "hooks"
    hooks.mkdir(parents=True)
    for reg in SPEC.hook_registrations:
        (hooks / f"{reg.script}.sh").write_text("#!/bin/bash\n")
    (tmp_path / "root" / "config" / "statusline.sh").write_text("#!/bin/bash\n")
    home = tmp_path / "home"
    home.mkdir()
    return home, str(tmp_path / "root")


def make_manager(env, platform="linux"):
    home, root = env
    return ClaudeConfigManager(home=home, hooks_root=root, platform=platform)


def read_settings(env):
    home, _root = env
    return json.loads(
        paths.claude_settings_path(home).read_text(encoding="utf-8")
    )


class TestAssertFromScratch:
    def test_creates_a_settings_file_with_zero_drift(self, env):
        mgr = make_manager(env)
        report = mgr.assert_ownership()
        assert report.changed
        home, root = env
        scan = drift.scan(home=home, platform="linux", hooks_root=root)
        assert scan.findings == []

    def test_self_consistency_scan_grade_is_a_or_b(self, env):
        """Plan C2 acceptance: assert into a tmp HOME, then the
        harness scanner grades the result >= B with zero CRITICAL."""
        from core.governance.harness_scanner import Severity, scan

        mgr = make_manager(env)
        mgr.assert_ownership()
        home, _root = env
        scan_report = scan(paths.claude_home(home))
        assert scan_report.by_severity(Severity.CRITICAL) == []
        assert scan_report.grade in ("A", "B")

    def test_assert_is_idempotent(self, env):
        mgr = make_manager(env)
        mgr.assert_ownership()
        first = read_settings(env)
        second_report = mgr.assert_ownership()
        assert second_report.changed is False
        assert read_settings(env) == first


class TestOperatorPreservation:
    def test_operator_hooks_and_rules_survive_assert(self, env):
        mgr = make_manager(env)
        mgr.assert_ownership()
        home, _root = env
        settings = read_settings(env)
        settings["hooks"]["Stop"].append(
            {"hooks": [{"type": "command", "command": "/op/mine.sh"}]}
        )
        settings["autoMode"]["hard_deny"].insert(0, "Bash(shutdown*)")
        settings["myKey"] = {"custom": True}
        from core.harness.json_store import write_json_atomic

        write_json_atomic(paths.claude_settings_path(home), settings)
        mgr.assert_ownership()
        after = read_settings(env)
        assert {"hooks": [{"type": "command", "command": "/op/mine.sh"}]} in (
            after["hooks"]["Stop"]
        )
        assert after["autoMode"]["hard_deny"][0] == "Bash(shutdown*)"
        assert after["myKey"] == {"custom": True}

    def test_operator_deny_extensions_are_merged(self, env):
        home, _root = env
        ext = paths.hard_deny_extension_path(home)
        ext.parent.mkdir(parents=True, exist_ok=True)
        ext.write_text(
            json.dumps({"hard_deny": ["Bash(halt*)"]}), encoding="utf-8"
        )
        make_manager(env).assert_ownership()
        assert "Bash(halt*)" in read_settings(env)["autoMode"]["hard_deny"]


class TestSeedPolicy:
    def test_adopted_statusline_is_never_reverted_by_assert(self, env):
        mgr = make_manager(env)
        mgr.assert_ownership()
        home, _root = env
        settings = read_settings(env)
        settings["statusLine"] = {"type": "command", "command": "starship"}
        from core.harness.json_store import write_json_atomic

        write_json_atomic(paths.claude_settings_path(home), settings)
        report = mgr.assert_ownership()
        assert read_settings(env)["statusLine"]["command"] == "starship"
        skips = [a for a in report.actions if a.action == "adopted-skip"]
        assert [a.surface for a in skips] == ["settings:statusLine"]

    def test_restore_reseeds_the_adopted_surface(self, env):
        mgr = make_manager(env)
        mgr.assert_ownership()
        home, _root = env
        settings = read_settings(env)
        settings["statusLine"] = {"type": "command", "command": "starship"}
        settings["worktree"] = {"baseRef": "detached"}
        settings["fallbackModel"] = ["claude-sonnet-5"]
        from core.harness.json_store import write_json_atomic

        write_json_atomic(paths.claude_settings_path(home), settings)
        report = mgr.restore()
        after = read_settings(env)
        assert after["statusLine"]["command"].endswith("statusline.sh")
        assert after["worktree"] == {"baseRef": "head"}
        assert after["fallbackModel"] == ["claude-opus-5", "claude-sonnet-5"]
        assert {a.surface for a in report.actions
                if a.action == "reseeded"} == {
            "settings:statusLine", "settings:worktree", "settings:fallbackModel",
        }


class TestStaleRootRepair:
    def test_m6_stale_root_is_reported_and_repaired(self, env):
        """QG #439 register M6: a hook command whose basename matches
        but whose directory is a dead ArkaOS root must read as
        diverged (stale-root) and assert must repair it."""
        mgr = make_manager(env)
        mgr.assert_ownership()
        home, root = env
        settings = read_settings(env)
        inner = settings["hooks"]["Stop"][0]["hooks"][0]
        inner["command"] = "/old/npx/cache/config/hooks/stop.sh"
        from core.harness.json_store import write_json_atomic

        write_json_atomic(paths.claude_settings_path(home), settings)
        scan = drift.scan(home=home, platform="linux", hooks_root=root)
        stale = [f for f in scan.findings if "stale-root" in f.detail]
        assert [f.where for f in stale] == ["hooks.Stop"]
        report = mgr.assert_ownership()
        repaired = [a for a in report.actions if a.detail == "stale-root"]
        assert [a.surface for a in repaired] == ["hooks.Stop"]
        after = read_settings(env)
        command = after["hooks"]["Stop"][0]["hooks"][0]["command"]
        assert command == f"{root}/config/hooks/stop.sh"

    def test_lib_snapshot_deployment_is_not_stale(self, env):
        home, root = env
        lib_hooks = home / ".arkaos" / "lib" / "config" / "hooks"
        lib_hooks.mkdir(parents=True)
        mgr = make_manager(env)
        mgr.assert_ownership()
        settings = read_settings(env)
        inner = settings["hooks"]["Stop"][0]["hooks"][0]
        inner["command"] = str(lib_hooks / "stop.sh")
        from core.harness.json_store import write_json_atomic

        write_json_atomic(paths.claude_settings_path(home), settings)
        scan = drift.scan(home=home, platform="linux", hooks_root=root)
        assert [f for f in scan.findings if "stale-root" in f.detail] == []


class TestRefusesToDestroy:
    """The blockers that made C2 r1 unshippable — each one reproduced.

    This module writes the file that decides what executes on the
    operator's machine; every entry here is a path where r1 destroyed
    configuration and reported success.
    """

    def write_raw(self, env, payload: bytes):
        home, _root = env
        path = paths.claude_settings_path(home)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        return path

    @pytest.mark.parametrize(
        ("label", "payload"),
        [
            ("invalid-json", b'{"env": {"K": "V"}, }'),
            ("not-an-object", b'[{"env": {"K": "V"}}]'),
            ("bom", b'\xef\xbb\xbf{"env": {"K": "V"}}'),
            ("bad-utf8", b'{"env": {"K": "\xff"}}'),
        ],
    )
    def test_unreadable_settings_are_never_overwritten(
        self, env, label, payload
    ):
        """QG C2 r1, Francisca B2: r1 replaced env/permissions/plugins
        with an ArkaOS-only file and exited 0."""
        path = self.write_raw(env, payload)
        before = path.read_bytes()
        report = make_manager(env).assert_ownership()
        assert report.refused
        assert report.changed is False
        assert path.read_bytes() == before

    def test_oversized_settings_are_never_overwritten(self, env):
        payload = (
            b'{"env": {"pad": "' + b"x" * (2 * 1024 * 1024 + 10) + b'"}}'
        )
        path = self.write_raw(env, payload)
        report = make_manager(env).assert_ownership()
        assert report.refused == "settings file exceeds the 2 MiB read ceiling"
        assert path.read_bytes() == payload

    @pytest.mark.parametrize(
        ("key", "value", "surface"),
        [
            ("hooks", "DISABLED-BY-OPERATOR", "settings:hooks"),
            ("autoMode", "off", "settings:autoMode.hard_deny"),
        ],
    )
    def test_wrong_typed_operator_values_are_left_untouched(
        self, env, key, value, surface
    ):
        """QG C2 r1, Francisca B4: r1 coerced these to empty containers
        and deleted whatever the operator had there."""
        home, _root = env
        from core.harness.json_store import write_json_atomic

        write_json_atomic(
            paths.claude_settings_path(home), {key: value, "keep": 1}
        )
        report = make_manager(env).assert_ownership()
        after = read_settings(env)
        assert after[key] == value
        assert after["keep"] == 1
        refusals = [a for a in report.actions if a.action == "refused"]
        assert surface in {a.surface for a in refusals}

    def test_wrong_typed_event_list_is_left_untouched(self, env):
        home, _root = env
        from core.harness.json_store import write_json_atomic

        write_json_atomic(
            paths.claude_settings_path(home),
            {"hooks": {"Stop": "/op/legacy.sh"}},
        )
        report = make_manager(env).assert_ownership()
        assert read_settings(env)["hooks"]["Stop"] == "/op/legacy.sh"
        assert any(
            a.action == "refused" and a.surface == "hooks.Stop"
            for a in report.actions
        )

    def test_non_hashable_deny_rule_never_raises(self, env):
        """QG C2 r1, Francisca B3: merge_unique hashes its input, so a
        dict member raised TypeError out of a never-raises path."""
        home, _root = env
        from core.harness.json_store import write_json_atomic

        write_json_atomic(
            paths.claude_settings_path(home),
            {"autoMode": {"hard_deny": ["Bash(shutdown*)", 42, {"x": 1}]}},
        )
        make_manager(env).assert_ownership()
        rules = read_settings(env)["autoMode"]["hard_deny"]
        assert "Bash(shutdown*)" in rules
        assert {"x": 1} in rules and 42 in rules  # operator data intact

    def test_installer_deployment_dir_is_not_stale(self, env):
        """QG C2 r1, Francisca B1: ~/.arkaos/config/hooks is where the
        installer actually deploys; r1 read every real install as
        stale and repointed it at the purgeable npx cache."""
        home, root = env
        deployed = paths.arkaos_home(home) / "config" / "hooks"
        deployed.mkdir(parents=True)
        mgr = make_manager(env)
        mgr.assert_ownership()
        settings = read_settings(env)
        for event in ("Stop", "SessionStart"):
            inner = settings["hooks"][event][0]["hooks"][0]
            inner["command"] = str(
                deployed / f"{'stop' if event == 'Stop' else 'session-start'}.sh"
            )
        from core.harness.json_store import write_json_atomic

        write_json_atomic(paths.claude_settings_path(home), settings)
        scan = drift.scan(home=home, platform="linux", hooks_root=root)
        assert [f for f in scan.findings if "stale-root" in f.detail] == []
        report = mgr.assert_ownership()
        assert [a for a in report.actions if a.detail == "stale-root"] == []

    def test_cjs_fastpath_suffix_survives_a_stale_root_repair(self, env):
        """A deployed .cjs must not be rewritten to .sh — that silently
        drops the Node fastpath (QG C2 r1, Francisca B1)."""
        home, root = env
        (Path(root) / "config" / "hooks" / "post-tool-use.cjs").write_text("")
        mgr = make_manager(env)
        mgr.assert_ownership()
        settings = read_settings(env)
        inner = settings["hooks"]["PostToolUse"][0]["hooks"][0]
        inner["command"] = "/old/cache/config/hooks/post-tool-use.cjs"
        from core.harness.json_store import write_json_atomic

        write_json_atomic(paths.claude_settings_path(home), settings)
        mgr.assert_ownership()
        command = read_settings(env)["hooks"]["PostToolUse"][0]["hooks"][0][
            "command"
        ]
        assert command.endswith("post-tool-use.cjs")

    def test_quoted_command_is_not_duplicated(self, env):
        """QG C2 r1, Francisca B7: matching the raw string appended a
        SECOND registration, so every ArkaOS hook fired twice."""
        home, root = env
        mgr = make_manager(env)
        mgr.assert_ownership()
        settings = read_settings(env)
        inner = settings["hooks"]["Stop"][0]["hooks"][0]
        inner["command"] = f'"{root}/config/hooks/stop.sh"'
        from core.harness.json_store import write_json_atomic

        write_json_atomic(paths.claude_settings_path(home), settings)
        mgr.assert_ownership()
        assert len(read_settings(env)["hooks"]["Stop"]) == 1

    def test_interpreter_prefix_is_not_read_as_stale(self, env):
        home, root = env
        mgr = make_manager(env)
        mgr.assert_ownership()
        settings = read_settings(env)
        inner = settings["hooks"]["Stop"][0]["hooks"][0]
        inner["command"] = f"bash {root}/config/hooks/stop.sh"
        from core.harness.json_store import write_json_atomic

        write_json_atomic(paths.claude_settings_path(home), settings)
        scan = drift.scan(home=home, platform="linux", hooks_root=root)
        assert [f for f in scan.findings if "stale-root" in f.detail] == []

    def test_timeout_divergence_is_repaired(self, env):
        """QG C2 r1, Francisca B8 mutant M8: the timeout repair had no
        test at all."""
        home, _root = env
        mgr = make_manager(env)
        mgr.assert_ownership()
        settings = read_settings(env)
        settings["hooks"]["Stop"][0]["hooks"][0]["timeout"] = 999
        from core.harness.json_store import write_json_atomic

        write_json_atomic(paths.claude_settings_path(home), settings)
        report = mgr.assert_ownership()
        assert any(a.detail == "timeout" for a in report.actions)
        assert read_settings(env)["hooks"]["Stop"][0]["hooks"][0][
            "timeout"
        ] == 5


class TestWritesTargetTheInstalledTree:
    """QG C2 r2, Francisca B1: r1 fixed the READ side of the npx-cache
    repointing and left the WRITE side unfixed — everything the manager
    created or repaired still pointed at a directory `npm cache clean`
    can purge. Every other test injects an explicit hooks_root, which
    is why the only path an operator takes had zero coverage."""

    def operator_env(self, tmp_path):
        """A HOME with a real install, and a resolved root that is a
        purgeable npx cache — exactly what the CLI produces."""
        home = tmp_path / "home"
        installed = home / ".arkaos" / "config" / "hooks"
        installed.mkdir(parents=True)
        for reg in SPEC.hook_registrations:
            (installed / f"{reg.script}.sh").write_text("#!/bin/bash\n")
        cache = tmp_path / ".npm" / "_npx" / "9f2c" / "arkaos"
        (cache / "config" / "hooks").mkdir(parents=True)
        return home, installed, cache

    def test_created_entries_land_in_the_installed_tree(
        self, tmp_path, monkeypatch
    ):
        home, installed, cache = self.operator_env(tmp_path)
        monkeypatch.setenv("ARKAOS_ROOT", str(cache))
        mgr = ClaudeConfigManager(home=home, hooks_root=None, platform="linux")
        mgr.assert_ownership()
        settings = json.loads(
            paths.claude_settings_path(home).read_text(encoding="utf-8")
        )
        command = settings["hooks"]["Stop"][0]["hooks"][0]["command"]
        assert command == str(installed / "stop.sh")
        assert str(cache) not in command

    def test_repaired_entries_land_in_the_installed_tree(
        self, tmp_path, monkeypatch
    ):
        home, installed, cache = self.operator_env(tmp_path)
        monkeypatch.setenv("ARKAOS_ROOT", str(cache))
        mgr = ClaudeConfigManager(home=home, hooks_root=None, platform="linux")
        mgr.assert_ownership()
        settings_path = paths.claude_settings_path(home)
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        settings["hooks"]["PreCompact"][0]["hooks"][0]["command"] = (
            "/dead/root/config/hooks/pre-compact.sh"
        )
        from core.harness.json_store import write_json_atomic

        write_json_atomic(settings_path, settings)
        mgr.assert_ownership()
        after = json.loads(settings_path.read_text(encoding="utf-8"))
        command = after["hooks"]["PreCompact"][0]["hooks"][0]["command"]
        assert command == str(installed / "pre-compact.sh")

    def test_reseeded_statusline_lands_in_the_installed_tree(
        self, tmp_path, monkeypatch
    ):
        home, installed, cache = self.operator_env(tmp_path)
        monkeypatch.setenv("ARKAOS_ROOT", str(cache))
        mgr = ClaudeConfigManager(home=home, hooks_root=None, platform="linux")
        mgr.assert_ownership()
        settings_path = paths.claude_settings_path(home)
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        settings["statusLine"] = {"type": "command", "command": "starship"}
        from core.harness.json_store import write_json_atomic

        write_json_atomic(settings_path, settings)
        mgr.restore()
        after = json.loads(settings_path.read_text(encoding="utf-8"))
        assert after["statusLine"]["command"] == str(
            installed.parent / "statusline.sh"
        )

    def test_assert_is_idempotent_under_an_operator_char_path(
        self, tmp_path, monkeypatch
    ):
        """A source checkout under a directory named R&D: the r3
        parser cut the path at the ampersand, so the manager never
        recognised the entry it had just written and appended a Stop
        group per run — 1, 2, 3 groups across three asserts (QG C2 r4
        Francisca B2, corrected r5: with an installed tree present the
        written command has no ampersand in it and the test could not
        discriminate)."""
        home = tmp_path / "home"
        home.mkdir()
        checkout = tmp_path / "R&D" / "arkaos"
        (checkout / "config" / "hooks").mkdir(parents=True)
        monkeypatch.setenv("ARKAOS_ROOT", str(checkout))
        mgr = ClaudeConfigManager(home=home, hooks_root=None, platform="linux")
        for _ in range(3):
            mgr.assert_ownership()
        settings = json.loads(
            paths.claude_settings_path(home).read_text(encoding="utf-8")
        )
        assert len(settings["hooks"]["Stop"]) == 1
        scan = drift.scan(home=home, platform="linux", hooks_root=None)
        assert scan.findings == []

    def test_source_checkout_without_an_install_uses_the_root(
        self, tmp_path, monkeypatch
    ):
        """No ~/.arkaos/config/hooks means no install — the resolved
        root is then the only sensible target."""
        home = tmp_path / "home"
        home.mkdir()
        checkout = tmp_path / "checkout"
        (checkout / "config" / "hooks").mkdir(parents=True)
        monkeypatch.setenv("ARKAOS_ROOT", str(checkout))
        mgr = ClaudeConfigManager(home=home, hooks_root=None, platform="linux")
        mgr.assert_ownership()
        settings = json.loads(
            paths.claude_settings_path(home).read_text(encoding="utf-8")
        )
        command = settings["hooks"]["Stop"][0]["hooks"][0]["command"]
        assert command == str(checkout / "config" / "hooks" / "stop.sh")

    @pytest.mark.parametrize(
        "command",
        [
            # Shapes the OPERATOR CUT rescues — each one duplicates
            # the registration with the cut neutered: the second token
            # would win the scan (defect QG C2 r2 Francisca B2; these
            # discriminating rows are QG C2 r3, where the shapes first
            # shipped left the cut deletable with the suite green).
            "{root}/config/hooks/stop.sh 2>/tmp/hook-debug.sh",
            "{root}/config/hooks/stop.sh && /usr/local/bin/notify.sh",
            "{root}/config/hooks/stop.sh > /var/log/arka.sh",
            "{root}/config/hooks/stop.sh 2> /tmp/err.cjs",
            "{root}/config/hooks/stop.sh; /opt/after.ps1",
            # Handled by the suffix scan alone; kept so a regression in
            # EITHER scan shows up here.
            "{root}/config/hooks/stop.sh 2>/dev/null",
            "{root}/config/hooks/stop.sh | tee /tmp/x",
            "{root}/config/hooks/stop.sh >> /tmp/arka.log 2>&1",
        ],
    )
    def test_shell_operator_does_not_duplicate_the_registration(
        self, env, command
    ):
        """QG C2 r2 Francisca B2: a redirect or chained command whose
        second token wins the scan hides the ArkaOS entry, so assert
        appends a SECOND one and the hook fires twice."""
        home, root = env
        mgr = make_manager(env)
        mgr.assert_ownership()
        settings = read_settings(env)
        inner = settings["hooks"]["Stop"][0]["hooks"][0]
        inner["command"] = command.format(root=root)
        from core.harness.json_store import write_json_atomic

        write_json_atomic(paths.claude_settings_path(home), settings)
        mgr.assert_ownership()
        assert len(read_settings(env)["hooks"]["Stop"]) == 1

    @pytest.mark.parametrize(
        ("command", "expected"),
        [
            ("/r/config/hooks/stop.sh 2>/tmp/hook-debug.sh", "stop.sh"),
            ("/r/config/hooks/stop.sh && /usr/local/bin/notify.sh", "stop.sh"),
            ("/r/config/hooks/stop.sh > /var/log/arka.sh", "stop.sh"),
            ("/r/config/hooks/stop.sh; /opt/after.ps1", "stop.sh"),
            ("bash /r/config/hooks/stop 2>/dev/null", "stop"),
            ("/r/config/hooks/stop.sh | tee /tmp/x.sh", "stop.sh"),
            ("env A=1 /r/config/hooks/stop.sh", "stop.sh"),
            ('"/r/config/hooks/stop.sh"', "stop.sh"),
            ("", ""),
            # A path-shaped ARGUMENT after the script: only the
            # suffix-preference loop tells the two apart, and without
            # these rows that loop reads as dead code and can be
            # deleted with the suite still green (QG C2 r4, Francisca
            # B1, mutant Y0).
            ("/r/config/hooks/stop.sh /tmp/extra/arg", "stop.sh"),
            (
                "bash /r/config/hooks/stop.sh --log /var/log/arka/out",
                "stop.sh",
            ),
            ("node /r/config/hooks/stop.cjs /tmp/state/x", "stop.cjs"),
            # An operator CHARACTER inside a directory name is not an
            # operator POSITION. Cutting there made the manager stop
            # recognising its own entry and assert went non-idempotent
            # (QG C2 r4, Francisca B2 — a regression from the r3 fix).
            ("/Users/x/R&D/config/hooks/stop.sh", "stop.sh"),
            ("/Users/x/a;b/config/hooks/stop.sh", "stop.sh"),
            ("/Users/x/Rock&Roll/config/hooks/stop.sh", "stop.sh"),
        ],
    )
    def test_command_parsing_stops_at_the_shell_operator(
        self, command, expected
    ):
        """The parser's own contract: the SCRIPT is returned, never the
        redirect target or the chained command — including for a
        suffix-less script, where the slash scan would otherwise return
        /dev/null. (Whether such an entry then matches an ArkaOS
        registration is a separate question: a suffix-less command is
        not an ArkaOS shape.)"""
        assert drift.hook_command_path(command).name == expected

    @pytest.mark.parametrize(
        ("left", "right", "same"),
        [
            ("/a/b/hooks", "/a/b/hooks/", True),
            ("/a/b/hooks", "/a/b/./hooks", True),
            ("/a/b/hooks", "/a/x/../b/hooks", True),
            ("/a/b/hooks", "/a/b/other", False),
        ],
    )
    def test_path_comparison_is_lexically_normalised(
        self, left, right, same
    ):
        """QG C2 r1 M2 (pinned in r3): a trailing slash or a `..`
        segment names the same directory and must not read as a
        different root."""
        assert (
            drift._normalised(Path(left)) == drift._normalised(Path(right))
        ) is same

    def test_path_comparison_is_case_folded_where_the_fs_is(self):
        """macOS resolves case variants to the same file, so a case
        variant must not read as a stale root."""
        import os

        folded = drift._normalised(Path("/A/B/Hooks"))
        assert folded == os.path.normcase("/A/B/Hooks")


class TestGuardsArePinned:
    """QG C2 r2, Francisca B3: six guard paths this PR introduced
    survived mutation against the full suite. Three are pinned here;
    the CLI exit-code trio lives in TestCliExitCodes."""

    def test_hard_deny_dict_is_refused_not_merged(self, env):
        home, _root = env
        from core.harness.json_store import write_json_atomic

        write_json_atomic(
            paths.claude_settings_path(home),
            {"autoMode": {"hard_deny": {"rules": ["Bash(shutdown*)"]}}},
        )
        report = make_manager(env).assert_ownership()
        after = read_settings(env)
        assert after["autoMode"]["hard_deny"] == {
            "rules": ["Bash(shutdown*)"]
        }
        assert any(
            a.action == "refused"
            and a.surface == "settings:autoMode.hard_deny"
            for a in report.actions
        )

    def test_non_string_deny_extensions_are_filtered(self, env):
        home, _root = env
        ext = paths.hard_deny_extension_path(home)
        ext.parent.mkdir(parents=True, exist_ok=True)
        ext.write_text(
            json.dumps({"hard_deny": ["Bash(halt*)", 7, None, {"a": 1}]}),
            encoding="utf-8",
        )
        make_manager(env).assert_ownership()
        rules = read_settings(env)["autoMode"]["hard_deny"]
        assert "Bash(halt*)" in rules
        assert all(isinstance(r, str) for r in rules)

    def test_unrepairable_divergence_is_named(self, env, monkeypatch):
        mgr = make_manager(env)
        mgr.assert_ownership()
        monkeypatch.setattr(
            drift, "entry_divergences",
            lambda entry, reg, accepted: ["shell: powershell expected"],
        )
        report = mgr.assert_ownership()
        unrepaired = [a for a in report.actions if a.action == "unrepaired"]
        assert unrepaired
        assert all(
            a.detail.startswith("unrepairable:shell") for a in unrepaired
        )
        # The ACTION, not only the detail: labelling it "repaired"
        # would be the silent success this PR exists to kill (QG C2
        # r3, Eduardo).
        assert not [a for a in report.actions if a.action == "repaired"]


class TestCliExitCodes:
    """The exit code IS the Node wrapper's interface — one test per
    branch, none of them satisfied by both outcomes (QG C2 r2,
    Francisca B3)."""

    def run_cli(self, home, root, argv, monkeypatch, capsys):
        monkeypatch.setattr(
            cli, "ClaudeConfigManager",
            lambda: ClaudeConfigManager(
                home=home, hooks_root=root, platform="linux"
            ),
        )
        code = cli.main(argv)
        captured = capsys.readouterr()
        return code, captured.out, captured.err

    def test_refused_settings_file_exits_1(
        self, env, monkeypatch, capsys
    ):
        home, root = env
        path = paths.claude_settings_path(home)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{broken", encoding="utf-8")
        code, _out, err = self.run_cli(
            home, root, ["assert"], monkeypatch, capsys
        )
        assert code == 1
        assert "refused" in err

    def test_refused_action_exits_1(self, env, monkeypatch, capsys):
        home, root = env
        from core.harness.json_store import write_json_atomic

        write_json_atomic(
            paths.claude_settings_path(home), {"hooks": "DISABLED"}
        )
        code, out, _err = self.run_cli(
            home, root, ["assert"], monkeypatch, capsys
        )
        assert code == 1
        assert "refused" in out

    def test_harden_exits_2_on_a_dangerous_tree(
        self, env, monkeypatch, capsys
    ):
        home, root = env
        path = paths.claude_settings_path(home)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {"permissions": {"allow": ["Bash(*)", "Bash(sudo *)"],
                                 "deny": []}}
            ),
            encoding="utf-8",
        )
        code, out, _err = self.run_cli(
            home, root, ["harden"], monkeypatch, capsys
        )
        assert code == 2
        assert "grade: F" in out

    def test_harden_exits_0_on_a_clean_tree(self, env, monkeypatch, capsys):
        home, root = env
        code, out, _err = self.run_cli(
            home, root, ["harden"], monkeypatch, capsys
        )
        assert code == 0
        assert "grade: A" in out or "grade: B" in out

    def test_assert_json_emits_the_report(self, env, monkeypatch, capsys):
        """--json on the write verbs is what makes AssertReport.to_dict
        load-bearing (QG C2 r3, Francisca B2: it was dead code)."""
        home, root = env
        code, out, _err = self.run_cli(
            home, root, ["assert", "--json"], monkeypatch, capsys
        )
        payload = json.loads(out)
        assert code == 0
        assert payload["verb"] == "assert"
        assert payload["changed"] is True
        assert payload["refused"] is None
        assert any(a["action"] == "created" for a in payload["actions"])

    def test_harden_json_carries_the_grade(self, env, monkeypatch, capsys):
        home, root = env
        code, out, _err = self.run_cli(
            home, root, ["harden", "--json"], monkeypatch, capsys
        )
        payload = json.loads(out)
        assert code == 0
        assert payload["verb"] == "harden"
        assert payload["scan_grade"] in ("A", "B")

    def test_json_refusal_still_exits_1(self, env, monkeypatch, capsys):
        home, root = env
        path = paths.claude_settings_path(home)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{broken", encoding="utf-8")
        code, out, _err = self.run_cli(
            home, root, ["assert", "--json"], monkeypatch, capsys
        )
        assert code == 1
        assert json.loads(out)["refused"]


class TestAuditAndManifest:
    def test_flag_values_never_reach_the_audit_trail(self, env):
        """QG C2 r1, Francisca B6: set_flag wrote str(value) into the
        log the docstring says carries no values, and the test named
        for it only checked the KEY SET."""
        mgr = make_manager(env)
        mgr.set_flag("frontendGate", "warn")
        home, _root = env
        raw = paths.harness_audit_log_path(home).read_text(encoding="utf-8")
        assert "warn" not in raw
        entry = json.loads(raw.splitlines()[0])
        assert entry["detail"] == "str"

    def test_mutations_are_audited_without_values(self, env):
        mgr = make_manager(env)
        mgr.assert_ownership()
        home, _root = env
        raw = paths.harness_audit_log_path(home).read_text(encoding="utf-8")
        lines = [json.loads(line) for line in raw.splitlines()]
        assert all(
            set(entry) <= {"ts", "verb", "surface", "action", "detail",
                           "content_sha256"}
            for entry in lines
        )
        assert "statusline" not in raw.lower().replace(
            "settings:statusline", ""
        )
        assert all(entry["verb"] == "assert" for entry in lines)

    def test_manifest_records_the_assert(self, env):
        mgr = make_manager(env)
        mgr.assert_ownership()
        home, _root = env
        from core.harness.manifest import load_manifest

        manifest, error = load_manifest(paths.ownership_manifest_path(home))
        assert error is None
        assert all(r.last_asserted is not None for r in manifest.surfaces)
        assert all(
            r.content_sha256 and len(r.content_sha256) == 64
            for r in manifest.surfaces
        )

    def test_manifest_digest_is_per_surface_not_whole_file(self, env):
        """QG C2 r1, Francisca B5 / Eduardo B3: a whole-file digest
        changed whenever the operator touched ANYTHING, so it could not
        answer the one question the manifest exists for."""
        from core.harness.json_store import write_json_atomic
        from core.harness.manifest import load_manifest

        mgr = make_manager(env)
        mgr.assert_ownership()
        home, _root = env
        manifest_path = paths.ownership_manifest_path(home)
        before, _ = load_manifest(manifest_path)
        digests = {r.surface: r.content_sha256 for r in before.surfaces}
        assert len(set(digests.values())) > 1  # not one digest for all
        settings = read_settings(env)
        settings["myPersonalKey"] = {"untouched-by-arkaos": True}
        write_json_atomic(paths.claude_settings_path(home), settings)
        mgr.assert_ownership()
        after, _ = load_manifest(manifest_path)
        assert {
            r.surface: r.content_sha256 for r in after.surfaces
        } == digests

    def test_adopted_surface_is_not_stamped_as_asserted(self, env):
        """The manifest must not contradict the audit trail: an
        adopted seed surface was skipped, so it was not asserted."""
        from core.harness.json_store import write_json_atomic
        from core.harness.manifest import load_manifest

        mgr = make_manager(env)
        mgr.assert_ownership()
        home, _root = env
        settings = read_settings(env)
        settings["statusLine"] = {"type": "command", "command": "starship"}
        write_json_atomic(paths.claude_settings_path(home), settings)
        mgr.assert_ownership()
        manifest, _ = load_manifest(paths.ownership_manifest_path(home))
        by_surface = {r.surface: r for r in manifest.surfaces}
        assert by_surface["settings:statusLine"].last_asserted is None
        assert by_surface["settings:hooks"].last_asserted is not None


class TestStatusReadOnly:
    def test_status_never_mutates(self, env):
        mgr = make_manager(env)
        mgr.assert_ownership()
        home, _root = env
        before = paths.claude_settings_path(home).read_bytes()
        report = mgr.status()
        assert paths.claude_settings_path(home).read_bytes() == before
        assert report["drift"]["ok"] is True
        assert report["manifest"] is not None

    def test_status_on_a_bare_home_reports_missing(self, env):
        report = make_manager(env).status()
        assert report["drift"]["ok"] is False
        assert report["manifest"] is None
        assert report["manifest_error"] == "missing"


class TestFlags:
    def test_read_flags_on_bare_home(self, env):
        flags = make_manager(env).read_flags()
        assert set(flags) == set(FLAG_NAMES)
        assert all(v is None for v in flags.values())

    def test_set_flag_writes_and_audits(self, env):
        mgr = make_manager(env)
        flags = mgr.set_flag("frontendGate", "warn")
        assert flags["frontendGate"] == "warn"
        home, _root = env
        config = json.loads(
            paths.arkaos_config_path(home).read_text(encoding="utf-8")
        )
        assert config["hooks"]["frontendGate"] == "warn"
        raw = paths.harness_audit_log_path(home).read_text(encoding="utf-8")
        assert "config:hooks.frontendGate" in raw

    def test_set_flag_preserves_other_config_keys(self, env):
        home, _root = env
        config_path = paths.arkaos_config_path(home)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            json.dumps({"other": {"kept": 1}, "hooks": {"kbFirst": True}}),
            encoding="utf-8",
        )
        make_manager(env).set_flag("hardEnforcement", True)
        config = json.loads(config_path.read_text(encoding="utf-8"))
        assert config["other"] == {"kept": 1}
        assert config["hooks"]["kbFirst"] is True
        assert config["hooks"]["hardEnforcement"] is True

    def test_unknown_flag_is_an_explicit_error(self, env):
        with pytest.raises(ValueError, match="unknown flag"):
            make_manager(env).set_flag("turboMode", True)

    @pytest.mark.parametrize(
        ("name", "value"),
        [
            ("hardEnforcement", "warn"),  # bool() -> True == hard
            ("specialistEnforcement", "off"),
            ("frontendGate", True),
            ("frontendGate", "maybe"),
        ],
    )
    def test_value_outside_the_flag_vocabulary_is_refused(
        self, env, name, value
    ):
        """QG C2 r1, Eduardo B2: the gates read hardEnforcement with
        bool(), so an unvalidated 'warn' silently turned enforcement
        ON while the operator asked for warn."""
        with pytest.raises(ValueError, match="invalid value"):
            make_manager(env).set_flag(name, value)

    def test_hostile_config_is_not_replaced(self, env):
        home, _root = env
        config_path = paths.arkaos_config_path(home)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text('{"hooks": ["not-an-object"]}', encoding="utf-8")
        with pytest.raises(ValueError, match="refusing to replace"):
            make_manager(env).set_flag("hardEnforcement", True)
        assert config_path.read_text(encoding="utf-8") == (
            '{"hooks": ["not-an-object"]}'
        )

    def test_corrupt_config_is_not_overwritten(self, env):
        home, _root = env
        config_path = paths.arkaos_config_path(home)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text("{broken", encoding="utf-8")
        with pytest.raises(ValueError, match="refusing to overwrite"):
            make_manager(env).set_flag("hardEnforcement", True)
        assert config_path.read_text(encoding="utf-8") == "{broken"


class TestHarden:
    def test_harden_grades_a_clean_tree_at_least_b(self, env):
        report, grade = make_manager(env).harden()
        assert report.verb == "harden"
        assert grade in ("A", "B")

    def test_harden_reports_the_real_grade_on_a_dangerous_tree(self, env):
        """A blanket allow with no deny scores F — the assertion has to
        DISCRIMINATE, or a hard-coded 'A' ships (QG C2 r1, Francisca
        B8, mutant M7)."""
        home, _root = env
        settings_path = paths.claude_settings_path(home)
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(
            json.dumps(
                {"permissions": {"allow": ["Bash(*)", "Bash(sudo *)"],
                                 "deny": []}}
            ),
            encoding="utf-8",
        )
        _report, grade = make_manager(env).harden()
        assert grade == "F"

    def test_harden_verb_reaches_the_audit_trail(self, env):
        make_manager(env).harden()
        home, _root = env
        raw = paths.harness_audit_log_path(home).read_text(encoding="utf-8")
        assert all(
            json.loads(line)["verb"] == "harden"
            for line in raw.splitlines()
        )


class TestCli:
    def run_cli(self, env, argv, monkeypatch, capsys):
        home, root = env
        monkeypatch.setattr(
            cli, "ClaudeConfigManager",
            lambda: ClaudeConfigManager(
                home=home, hooks_root=root, platform="linux"
            ),
        )
        code = cli.main(argv)
        return code, capsys.readouterr().out

    def test_status_json(self, env, monkeypatch, capsys):
        code, out = self.run_cli(env, ["status", "--json"], monkeypatch, capsys)
        assert code == 0
        assert json.loads(out)["drift"]["ok"] is False

    def test_assert_then_status_ok(self, env, monkeypatch, capsys):
        code, out = self.run_cli(env, ["assert"], monkeypatch, capsys)
        assert code == 0
        assert "created" in out
        code, out = self.run_cli(env, ["status"], monkeypatch, capsys)
        assert "ok: True" in out

    def test_flags_set_and_read(self, env, monkeypatch, capsys):
        code, out = self.run_cli(
            env, ["flags", "--set", "hardEnforcement=true"],
            monkeypatch, capsys,
        )
        assert code == 0
        assert json.loads(out)["hardEnforcement"] is True

    def test_flags_bad_assignment(self, env, monkeypatch, capsys):
        code, _out = self.run_cli(
            env, ["flags", "--set", "nonsense"], monkeypatch, capsys
        )
        assert code == 1

    def test_harden_prints_the_grade(self, env, monkeypatch, capsys):
        """Output shape only — the exit-code branches are pinned
        individually in TestCliExitCodes."""
        code, out = self.run_cli(env, ["harden"], monkeypatch, capsys)
        assert "post-assert scan grade:" in out
        assert code == 0
