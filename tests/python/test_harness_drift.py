"""core.harness.drift — spec-vs-disk comparison, read-only, never raises."""

import json

from core.harness import drift
from core.harness.drift import DriftStatus, scan
from core.harness.spec import spec_for

SPEC = spec_for("claude-code")


def make_hooks_root(tmp_path):
    """A fake ArkaOS root whose config/hooks has every spec script."""
    hooks = tmp_path / "arkaos-root" / "config" / "hooks"
    hooks.mkdir(parents=True)
    for reg in SPEC.hook_registrations:
        (hooks / f"{reg.script}.sh").write_text("#!/bin/bash\n")
    return str(tmp_path / "arkaos-root")


def settings_from_spec(hooks_root, ext=".sh"):
    """The settings.json the adapter would write, derived from the spec."""
    hooks: dict[str, list] = {}
    for reg in SPEC.hook_registrations:
        group = {
            "hooks": [
                {
                    "type": "command",
                    "command": f"{hooks_root}/config/hooks/{reg.script}{ext}",
                    "timeout": reg.timeout,
                }
            ]
        }
        if reg.matcher:
            group["matcher"] = reg.matcher
        hooks.setdefault(reg.event, []).append(group)
    return {
        "hooks": hooks,
        "autoMode": {"hard_deny": list(SPEC.hard_deny_rules)},
        "statusLine": {
            "type": "command",
            "command": f"{hooks_root}/config/statusline{'.ps1' if ext == '.ps1' else '.sh'}",
            "padding": 2,
        },
        "worktree": {"baseRef": "head"},
        "fallbackModel": ["claude-opus-5", "claude-sonnet-5"],
    }


def write_settings(home, settings):
    path = home / ".claude" / "settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(settings) if isinstance(settings, dict) else settings,
        encoding="utf-8",
    )
    return path


def statuses(report):
    return {(f.surface, f.status) for f in report.findings}


class TestCleanHarness:
    def test_settings_built_from_spec_report_zero_findings(self, tmp_path):
        root = make_hooks_root(tmp_path)
        write_settings(tmp_path, settings_from_spec(root))
        report = scan(home=tmp_path, platform="linux", hooks_root=root)
        assert report.findings == []
        assert report.ok

    def test_windows_shape_is_also_clean(self, tmp_path):
        root = make_hooks_root(tmp_path)
        settings = settings_from_spec(root, ext=".ps1")
        # The adapter never registers the posix-only Task entry on
        # Windows — a clean Windows settings file doesn't carry it.
        settings["hooks"]["PreToolUse"] = [
            g
            for g in settings["hooks"]["PreToolUse"]
            if "matcher" not in g
        ]
        write_settings(tmp_path, settings)
        report = scan(home=tmp_path, platform="win32", hooks_root=root)
        assert report.findings == []


class TestOwnedEntriesDrift:
    def test_removed_hook_event_is_missing(self, tmp_path):
        root = make_hooks_root(tmp_path)
        settings = settings_from_spec(root)
        del settings["hooks"]["Stop"]
        write_settings(tmp_path, settings)
        report = scan(home=tmp_path, platform="linux", hooks_root=root)
        assert ("settings:hooks", DriftStatus.MISSING) in statuses(report)
        assert any(f.where == "hooks.Stop" for f in report.findings)
        assert not report.ok

    def test_changed_timeout_is_diverged(self, tmp_path):
        root = make_hooks_root(tmp_path)
        settings = settings_from_spec(root)
        inner = settings["hooks"]["UserPromptSubmit"][0]["hooks"][0]
        inner["timeout"] = 10
        write_settings(tmp_path, settings)
        report = scan(home=tmp_path, platform="linux", hooks_root=root)
        diverged = [
            f for f in report.findings if f.status is DriftStatus.DIVERGED
        ]
        assert [f.where for f in diverged] == ["hooks.UserPromptSubmit"]

    def test_missing_hard_deny_rules_are_one_aggregated_finding(
        self, tmp_path
    ):
        root = make_hooks_root(tmp_path)
        settings = settings_from_spec(root)
        settings["autoMode"]["hard_deny"] = list(SPEC.hard_deny_rules)[:-2]
        write_settings(tmp_path, settings)
        report = scan(home=tmp_path, platform="linux", hooks_root=root)
        rule_findings = [
            f
            for f in report.findings
            if f.surface == "settings:autoMode.hard_deny"
        ]
        assert len(rule_findings) == 1
        assert rule_findings[0].status is DriftStatus.MISSING
        assert (
            f"2 of {len(SPEC.hard_deny_rules)}" in rule_findings[0].detail
        )

    def test_operator_additions_are_not_drift(self, tmp_path):
        root = make_hooks_root(tmp_path)
        settings = settings_from_spec(root)
        settings["hooks"]["Stop"].append(
            {"hooks": [{"type": "command", "command": "/home/op/mine.sh"}]}
        )
        settings["autoMode"]["hard_deny"].append("Bash(shutdown*)")
        settings["myCustomKey"] = {"anything": True}
        write_settings(tmp_path, settings)
        report = scan(home=tmp_path, platform="linux", hooks_root=root)
        assert report.findings == []


class TestSeedSurfaces:
    def test_operator_status_line_is_adopted_and_does_not_fail(
        self, tmp_path
    ):
        root = make_hooks_root(tmp_path)
        settings = settings_from_spec(root)
        settings["statusLine"] = {"type": "command", "command": "starship"}
        write_settings(tmp_path, settings)
        report = scan(home=tmp_path, platform="linux", hooks_root=root)
        assert statuses(report) == {
            ("settings:statusLine", DriftStatus.ADOPTED)
        }
        assert report.ok

    def test_absent_seed_surfaces_are_missing(self, tmp_path):
        root = make_hooks_root(tmp_path)
        settings = settings_from_spec(root)
        del settings["statusLine"]
        del settings["worktree"]
        del settings["fallbackModel"]
        write_settings(tmp_path, settings)
        report = scan(home=tmp_path, platform="linux", hooks_root=root)
        assert statuses(report) == {
            ("settings:statusLine", DriftStatus.MISSING),
            ("settings:worktree", DriftStatus.MISSING),
            ("settings:fallbackModel", DriftStatus.MISSING),
        }

    def test_operator_worktree_is_adopted(self, tmp_path):
        root = make_hooks_root(tmp_path)
        settings = settings_from_spec(root)
        settings["worktree"] = {"baseRef": "detached"}
        write_settings(tmp_path, settings)
        report = scan(home=tmp_path, platform="linux", hooks_root=root)
        assert statuses(report) == {
            ("settings:worktree", DriftStatus.ADOPTED)
        }

    def test_operator_fallback_chain_is_adopted(self, tmp_path):
        """Runtime Sync PR3: a chain the operator wrote — array or the
        legacy string form — is theirs; the seed policy never reverts it."""
        root = make_hooks_root(tmp_path)
        settings = settings_from_spec(root)
        settings["fallbackModel"] = "claude-sonnet-5"
        write_settings(tmp_path, settings)
        report = scan(home=tmp_path, platform="linux", hooks_root=root)
        assert statuses(report) == {
            ("settings:fallbackModel", DriftStatus.ADOPTED)
        }


class TestConditionalRegistrations:
    def test_task_entry_not_expected_when_script_not_deployed(
        self, tmp_path
    ):
        root = make_hooks_root(tmp_path)
        (
            tmp_path / "arkaos-root" / "config" / "hooks"
            / "agent-provision.sh"
        ).unlink()
        settings = settings_from_spec(root)
        settings["hooks"]["PreToolUse"] = [
            g
            for g in settings["hooks"]["PreToolUse"]
            if "matcher" not in g
        ]
        write_settings(tmp_path, settings)
        report = scan(home=tmp_path, platform="linux", hooks_root=root)
        assert report.findings == []


class TestHostileInput:
    def test_missing_settings_is_a_single_finding(self, tmp_path):
        report = scan(home=tmp_path, platform="linux")
        assert [
            (f.surface, f.status) for f in report.findings
        ] == [("settings", DriftStatus.MISSING)]
        assert not report.ok

    def test_binary_settings_never_raises(self, tmp_path):
        path = tmp_path / ".claude" / "settings.json"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"\xff\xfe\x00")
        report = scan(home=tmp_path, platform="linux")
        assert statuses(report) == {("settings", DriftStatus.UNREADABLE)}

    def test_wrong_shapes_inside_settings_never_raise(self, tmp_path):
        write_settings(
            tmp_path,
            {
                "hooks": "not-a-dict",
                "autoMode": [],
                "statusLine": 7,
                "worktree": "yes",
            },
        )
        report = scan(home=tmp_path, platform="linux")
        assert not report.ok  # every owned hook entry is missing

    def test_unknown_runtime_names_the_runtime_not_the_settings(
        self, tmp_path
    ):
        report = scan(home=tmp_path, runtime="betamax")
        assert statuses(report) == {("runtime", DriftStatus.UNREADABLE)}
        finding = report.findings[0]
        assert finding.where == "betamax"
        assert "unknown runtime" in finding.detail

    def test_internal_failure_hits_the_boundary(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            drift.json_store,
            "load_json",
            lambda path: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        report = scan(home=tmp_path)
        assert statuses(report) == {("settings", DriftStatus.UNREADABLE)}
        assert "scan aborted" in report.findings[0].detail
        assert "RuntimeError" in report.findings[0].detail

    def test_corrupted_settings_wording_never_blames_the_installer(
        self, tmp_path
    ):
        """invalid-json gets a grammatical sentence and no installer
        remediation — re-running the installer does not repair a
        hand-corrupted file."""
        write_settings(tmp_path, "{nope")
        report = scan(home=tmp_path, platform="linux")
        finding = report.findings[0]
        assert finding.status is DriftStatus.UNREADABLE
        assert finding.detail == "settings file is not valid JSON"
        assert "installer" not in finding.detail

    def test_find_entry_guards_survive_hostile_group_shapes(self, tmp_path):
        """Non-dict groups and non-dict inner hooks are skipped, and a
        list with no ArkaOS command still resolves to missing — the
        _find_entry guards that keep the never-raises contract true."""
        root = make_hooks_root(tmp_path)
        settings = settings_from_spec(root)
        settings["hooks"]["Stop"] = [
            42,
            {"hooks": "not-a-list"},
            {"hooks": [7, {"type": "command", "command": ""}]},
            {"hooks": [{"type": "command", "command": "/op/other.sh"}]},
        ]
        write_settings(tmp_path, settings)
        report = scan(home=tmp_path, platform="linux", hooks_root=root)
        missing = [f for f in report.findings if f.where == "hooks.Stop"]
        assert len(missing) == 1
        assert missing[0].status is DriftStatus.MISSING

    def test_script_deployed_oserror_treats_conditional_as_absent(
        self, tmp_path, monkeypatch
    ):
        root = make_hooks_root(tmp_path)
        settings = settings_from_spec(root)
        settings["hooks"]["PreToolUse"] = [
            g
            for g in settings["hooks"]["PreToolUse"]
            if "matcher" not in g
        ]
        write_settings(tmp_path, settings)
        monkeypatch.setattr(
            drift.paths,
            "hooks_dir",
            lambda root=None: (_ for _ in ()).throw(OSError("denied")),
        )
        report = scan(home=tmp_path, platform="linux", hooks_root=root)
        assert report.findings == []


class TestReportShape:
    def test_to_dict_is_json_serializable(self, tmp_path):
        report = scan(home=tmp_path, platform="linux")
        payload = json.dumps(report.to_dict())
        decoded = json.loads(payload)
        assert decoded["ok"] is False
        assert decoded["runtime"] == "claude-code"
        assert decoded["findings"][0]["status"] == "missing"
