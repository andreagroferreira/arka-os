"""PR-C3 shield --fix: the remediator applies what it can and NAMES what
it cannot. Spec: .arkaos/specs/harness-remediation.yaml.

The load-bearing property is not "it fixes things" — it is that a
finding never disappears without an accounting. A silent skip converts
an unfixed vulnerability into a clean-looking run.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from core.governance import harness_scanner
from core.governance.harness_scanner import scan
from core.harness import remediation
from core.harness.spec import HARD_DENY_RULES


def _write_settings(root: Path, permissions: dict) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    path = root / "settings.json"
    path.write_text(
        json.dumps({"permissions": permissions}, indent=2), encoding="utf-8"
    )
    return path


# ─── Classification is total ────────────────────────────────────────────


def _scanner_rule_ids() -> set[str]:
    """Every rule id the scanner can emit, read from its own source."""
    import re

    source = Path(harness_scanner.__file__).read_text(encoding="utf-8")
    return set(re.findall(r'rule="([a-z-]+)"', source))


def test_every_scanner_rule_is_classified():
    """A new scanner rule must not silently join the unfixed set."""
    unclassified = _scanner_rule_ids() - set(remediation.FIXABLE) - set(
        remediation.NON_FIXABLE
    )
    assert not unclassified, (
        f"scanner rules with no remediation classification: "
        f"{sorted(unclassified)} — add them to FIXABLE or NON_FIXABLE"
    )


def test_unknown_rule_is_reported_not_dropped():
    finding = harness_scanner.Finding(
        rule="settings-invented-rule",
        severity=harness_scanner.Severity.HIGH,
        where="settings.json", detail="x", fix="y",
    )
    kind, reason = remediation.classify(finding)
    assert kind == "unknown-rule"
    assert "no classification" in reason


def test_classification_sets_do_not_overlap():
    assert not set(remediation.FIXABLE) & set(remediation.NON_FIXABLE)


# ─── Dry run writes nothing ─────────────────────────────────────────────


def test_dry_run_writes_nothing(tmp_path):
    path = _write_settings(tmp_path, {"allow": ["Bash(rm:*)", "Read(*)"]})
    before = path.read_bytes()
    report = remediation.fix(tmp_path, apply=False)
    assert report.applied is False
    assert report.changed is True
    assert report.removed_allow == ["Bash(rm:*)"]
    assert path.read_bytes() == before
    assert report.backup is None
    assert "DRY RUN" in remediation.render(report)


# ─── Applying ───────────────────────────────────────────────────────────


def test_unscoped_allow_is_named_never_dropped(tmp_path):
    """The scanner's fix for unscoped is 'scope it', and only the
    operator knows the pattern — so the rule is reported, not removed."""
    _write_settings(tmp_path, {"allow": ["Read(*)"], "deny": ["Bash(x:*)"]})
    report = remediation.fix(tmp_path, apply=True)
    assert "Read(*)" not in report.removed_allow
    allow = json.loads(
        (tmp_path / "settings.json").read_text()
    )["permissions"]["allow"]
    assert "Read(*)" in allow
    named = [s for s in report.skipped if s.rule == "settings-unscoped-allow"]
    assert named and named[0].reason == "needs-human"


def test_apply_removes_only_the_offending_rules(tmp_path):
    keep = ["Read(*)", "Bash(git status:*)", "Grep(*)"]
    _write_settings(
        tmp_path,
        {"allow": ["Bash(rm:*)", *keep, "Bash(curl:*)"],
         "deny": ["Bash(sudo:*)"]},
    )
    report = remediation.fix(tmp_path, apply=True)
    assert report.applied is True
    settings = json.loads((tmp_path / "settings.json").read_text())
    allow = settings["permissions"]["allow"]
    for rule in keep:
        assert rule in allow, f"{rule} must survive — it is not dangerous"
    assert "Bash(rm:*)" not in allow
    assert set(report.removed_allow) == {"Bash(rm:*)", "Bash(curl:*)"}


def test_apply_seeds_the_hard_deny_defaults(tmp_path):
    _write_settings(tmp_path, {"allow": ["Read(*)", "Grep(*)"]})
    report = remediation.fix(tmp_path, apply=True)
    deny = json.loads(
        (tmp_path / "settings.json").read_text()
    )["permissions"]["deny"]
    assert deny, "a missing deny list must be seeded"
    assert set(HARD_DENY_RULES) <= set(deny)
    assert report.seeded_deny


def test_existing_deny_rules_survive_seeding(tmp_path):
    mine = "Bash(my-private-thing:*)"
    _write_settings(tmp_path, {"allow": ["Read(*)"], "deny": [mine]})
    remediation.fix(tmp_path, apply=True)
    deny = json.loads(
        (tmp_path / "settings.json").read_text()
    )["permissions"]["deny"]
    assert mine in deny, "the operator's own deny rules must not be lost"


def test_backup_is_written_before_mutation_and_restores(tmp_path):
    path = _write_settings(tmp_path, {"allow": ["Bash(rm:*)", "Read(*)"]})
    original = path.read_bytes()
    report = remediation.fix(tmp_path, apply=True)
    assert report.backup is not None and report.backup.is_file()
    assert report.backup.read_bytes() == original, (
        "the backup must restore the original byte-for-byte"
    )
    assert path.read_bytes() != original
    assert str(report.backup) in remediation.render(report)


def test_removed_rules_are_listed_verbatim(tmp_path):
    rule = 'Bash(python3 -c "import os; os.system(\'x\')")'
    _write_settings(tmp_path, {"allow": [rule, "Read(*)"]})
    report = remediation.fix(tmp_path, apply=True)
    assert rule in report.removed_allow, (
        "a rule with quotes must reach the report verbatim from the live "
        "allow list — it is never parsed back out of the finding detail"
    )
    assert rule in remediation.render(report)


# ─── Refusals never raise ───────────────────────────────────────────────


def test_corrupt_settings_never_mutates_and_is_named(tmp_path):
    """An unparseable file is reported, not written to and not silently
    passed over: the scanner's own config-unparseable finding reaches
    the skipped list with its reason."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "settings.json"
    path.write_text("{not json", encoding="utf-8")
    before = path.read_bytes()
    report = remediation.fix(tmp_path, apply=True)
    assert report.applied is False
    assert report.changed is False
    assert path.read_bytes() == before
    named = [s for s in report.skipped if s.rule == "config-unparseable"]
    assert named, "the corrupt file must be named, not silently skipped"
    assert named[0].reason == "needs-human"
    assert named[0].rule in remediation.render(report)


def test_dry_run_plans_without_writing(tmp_path):
    """A sound plan on a writable file still writes nothing without
    --apply. (The write-failure path is covered separately by
    test_write_failure_refuses_and_says_so.)"""
    tmp_path.mkdir(parents=True, exist_ok=True)
    settings = tmp_path / "settings.json"
    settings.write_text(
        json.dumps({"permissions": {"allow": ["Bash(rm:*)"]}}),
        encoding="utf-8",
    )
    before = settings.read_bytes()
    report = remediation.fix(tmp_path, apply=False)
    assert report.changed is True and report.applied is False
    assert settings.read_bytes() == before


def test_missing_settings_is_a_quiet_noop(tmp_path):
    """No settings file: nothing changed, nothing written, nothing said
    beyond the standard 'nothing mechanically fixable found'."""
    empty = tmp_path / "empty"
    empty.mkdir()
    report = remediation.fix(empty, apply=True)
    assert report.applied is False
    assert report.changed is False
    assert report.refused is None
    assert list(empty.iterdir()) == [], "a no-op must not create files"
    assert "nothing mechanically fixable found" in remediation.render(report)


def test_permissions_not_an_object_refuses(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "settings.json").write_text(
        json.dumps({"permissions": ["oops"]}), encoding="utf-8"
    )
    report = remediation.fix(tmp_path, apply=True)
    assert report.applied is False
    # Either the scan finds nothing actionable, or the shape is refused —
    # what must never happen is a write.
    assert report.changed is False or report.refused


# ─── Skipped findings are always reported ───────────────────────────────


def test_non_fixable_findings_are_named_with_a_reason(tmp_path):
    # The fixture is opaque-but-shapeless on purpose: it must trip the
    # scanner's NAME-based rule (a *_API_KEY bound to a long opaque
    # value) without carrying any vendor prefix, so it cannot look like
    # a real credential to the repo's own security grep. Lesson from the
    # D1 gate, applied the other way round.
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "settings.json").write_text(
        json.dumps({
            "permissions": {"allow": ["Bash(rm:*)"], "deny": ["Bash(x:*)"]},
            "env": {"OPENAI_API_KEY": "0123456789abcdef0123456789abcdef"},
        }),
        encoding="utf-8",
    )
    report = remediation.fix(tmp_path, apply=False)
    secrets = [s for s in report.skipped if "secret" in s.rule]
    assert secrets, "a secret in env must be reported as not fixed"
    assert secrets[0].reason == "needs-human"
    rendered = remediation.render(report)
    assert "NOT fixed automatically" in rendered
    assert secrets[0].rule in rendered


def test_every_unfixed_finding_reaches_the_report(tmp_path):
    """The anti-silence invariant: findings in, accounted-for out."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "settings.json").write_text(
        json.dumps({
            "permissions": {"allow": ["Bash(rm:*)", "Read"], "deny": []},
            "env": {"AWS_SECRET_ACCESS_KEY": "0123456789abcdef0123456789abcdef"},
        }),
        encoding="utf-8",
    )
    before = scan(tmp_path)
    report = remediation.fix(tmp_path, apply=False)
    accounted = len(report.skipped) + len(report.removed_allow)
    fixable_rules = {f.rule for f in before.findings} & set(
        remediation.FIXABLE
    )
    # Every finding is either dropped, seeded, or skipped-with-a-reason.
    assert accounted or report.seeded_deny or not before.findings
    assert accounted >= len(before.findings) - len(fixable_rules)


# ─── End-to-end: an F profile reaches A ─────────────────────────────────


def test_grade_f_profile_reaches_a(tmp_path):
    """The operator's shape: many dangerous allows, no deny list."""
    dangerous = [f"Bash({cmd}:*)" for cmd in
                 ("rm", "curl", "bash", "sh", "python3", "php", "node")]
    _write_settings(tmp_path, {"allow": [*dangerous, "Read(src/**)"]})
    assert scan(tmp_path).grade == "F"
    remediation.fix(tmp_path, apply=True)
    after = scan(tmp_path)
    assert after.grade == "A", (
        f"expected A after fix, got {after.grade}: "
        f"{[f.rule for f in after.findings]}"
    )


# ─── CLI wiring ─────────────────────────────────────────────────────────


def test_cli_fix_is_dry_by_default(tmp_path, capsys):
    from core.governance import harness_scanner_cli as cli

    path = _write_settings(tmp_path, {"allow": ["Bash(rm:*)"]})
    before = path.read_bytes()
    code = cli.main([str(tmp_path), "--fix"])
    assert path.read_bytes() == before, "--fix alone must not write"
    assert code == 2, "criticals remain, so the scanner contract exits 2"
    assert "DRY RUN" in capsys.readouterr().out


def test_cli_fix_apply_writes_and_exit_reflects_the_rescan(tmp_path, capsys):
    from core.governance import harness_scanner_cli as cli

    _write_settings(tmp_path, {"allow": ["Bash(rm:*)", "Read(src/**)"]})
    code = cli.main([str(tmp_path), "--fix", "--apply"])
    capsys.readouterr()
    assert code == 0, "a clean post-fix scan must exit 0"
    assert scan(tmp_path).grade == "A"


def test_cli_fix_json_is_machine_readable(tmp_path, capsys):
    from core.governance import harness_scanner_cli as cli

    _write_settings(tmp_path, {"allow": ["Bash(rm:*)"]})
    cli.main([str(tmp_path), "--fix", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert isinstance(payload, list) and payload
    assert payload[0]["applied"] is False
    assert payload[0]["removed_allow"] == ["Bash(rm:*)"]
    assert "grade_after" in payload[0]


@pytest.mark.parametrize("flag", ["--fix", "--apply"])
def test_cli_advertises_the_flags(flag):
    from core.governance import harness_scanner_cli as cli

    with pytest.raises(SystemExit):
        cli.main(["--help"])
    # argparse writes help to stdout on --help; the flag must be listed.
    import contextlib
    import io

    buf = io.StringIO()
    with contextlib.suppress(SystemExit), contextlib.redirect_stdout(buf):
        cli.main(["--help"])
    assert flag in buf.getvalue()


# ─── QG C3 r1 closures: the defects Francisca reproduced ────────────────


def test_local_settings_findings_are_never_unaccounted(tmp_path):
    """Francisca B1: the scanner reads settings.local.json too. Every
    finding must be removed, seeded, or skipped — never silently gone."""
    # Survivors on purpose: an unscoped rule in each file, so the
    # invariant loop below can never silently run zero times (QG C3 r2,
    # Francisca B2 — the r1 vacuity pattern inside its own closure).
    _write_settings(
        tmp_path, {"allow": ["Read(src/**)", "Read(*)"], "deny": ["X(y)"]}
    )
    (tmp_path / "settings.local.json").write_text(
        json.dumps({"permissions": {
            "allow": ["Bash(rm:*)", "Bash(curl:*)", "Write(*)"],
            "deny": ["X(y)"]}}),
        encoding="utf-8",
    )
    before = scan(tmp_path)
    assert len(before.findings) >= 2
    report = remediation.fix(tmp_path, apply=True)
    local = json.loads((tmp_path / "settings.local.json").read_text())
    assert "Bash(rm:*)" not in local["permissions"]["allow"]
    # The invariant, in its strongest form: every finding that SURVIVES
    # the fix must be named in skipped. Counting inputs against outputs
    # is weaker — a fix and a skip are both accountings, but a survivor
    # nobody named is the silence this module exists to prevent.
    named = {(s.rule, s.where) for s in report.skipped}
    after = scan(tmp_path)
    assert len(after.findings) >= 2, (
        "the fixture must leave survivors, or the loop below asserts "
        "nothing at all"
    )
    for finding in after.findings:
        assert (finding.rule, finding.where) in named, (
            f"{finding.rule} @ {finding.where} survived the fix and is "
            f"named nowhere — anti-silence invariant broken"
        )


def test_seed_deny_goes_to_the_file_that_raised_it(tmp_path):
    """Francisca B2: a finding in one file must not mutate another."""
    _write_settings(tmp_path, {"allow": ["Read(src/**)"], "deny": ["X(y)"]})
    (tmp_path / "settings.local.json").write_text(
        json.dumps({"permissions": {"allow": ["Bash(rm:*)"]}}),
        encoding="utf-8",
    )
    remediation.fix(tmp_path, apply=True)
    main = json.loads((tmp_path / "settings.json").read_text())
    local = json.loads((tmp_path / "settings.local.json").read_text())
    assert main["permissions"]["deny"] == ["X(y)"], (
        "settings.json had no no-deny finding; it must not be seeded"
    )
    assert set(HARD_DENY_RULES) <= set(local["permissions"]["deny"])


def test_symlinked_settings_writes_through_to_the_target(tmp_path):
    """Francisca B3: the dotfiles layout must not get a false success."""
    real_dir = tmp_path / "dotfiles"
    real_dir.mkdir()
    real = real_dir / "settings.json"
    real.write_text(
        json.dumps({"permissions": {
            "allow": ["Bash(rm:*)"], "deny": ["X(y)"]}}),
        encoding="utf-8",
    )
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    (cfg / "settings.json").symlink_to(real)
    report = remediation.fix(cfg, apply=True)
    assert report.applied is True
    assert (cfg / "settings.json").is_symlink(), (
        "the symlink must survive — replacing it orphans the operator's "
        "source of truth"
    )
    assert "Bash(rm:*)" not in json.loads(real.read_text())[
        "permissions"]["allow"], "the authoritative file must be fixed"


def test_free_text_danger_is_named_never_dropped(tmp_path):
    """Francisca B4: a benign path containing 'eval' or 'sudo' trips the
    scanner's free-text branch. Deleting it would be fabrication."""
    benign = ["Read(core/eval/**)", "Edit(docs/sudo-setup.md)"]
    _write_settings(
        tmp_path, {"allow": [*benign, "Bash(rm:*)"], "deny": ["X(y)"]}
    )
    report = remediation.fix(tmp_path, apply=True)
    allow = json.loads(
        (tmp_path / "settings.json").read_text()
    )["permissions"]["allow"]
    for rule in benign:
        assert rule in allow, f"{rule} grants no execution — must survive"
        assert rule not in report.removed_allow
    assert "Bash(rm:*)" in report.removed_allow
    assert any(s.reason == "needs-human" for s in report.skipped)


def test_write_failure_refuses_and_says_so(tmp_path):
    """Francisca B5: the refusal paths were vacuously pinned — gutting
    every report.refused assignment left the suite green."""
    _write_settings(tmp_path, {"allow": ["Bash(rm:*)"], "deny": ["X(y)"]})
    tmp_path.chmod(0o555)  # writable file, unwritable parent
    try:
        report = remediation.fix(tmp_path, apply=True)
    finally:
        tmp_path.chmod(0o755)
    assert report.applied is False
    assert report.failed == ["settings.json"]
    assert report.refused and "settings.json" in report.refused
    rendered = remediation.render(report)
    assert "NOT WRITTEN" in rendered
    assert "DRY RUN" not in rendered, (
        "a failed --apply must never read as a routine preview"
    )
    # The backup is what FAILED here (copy2 into the unwritable parent),
    # so the report must not promise one (QG C3 r3, both reviewers).
    assert "no backup was taken" in rendered
    assert "the untouched original" not in rendered


def test_unusable_permissions_shape_is_named_not_written(tmp_path):
    """An unusable permissions object is named in skipped as
    config-unusable and nothing is written. report.refused is a
    different branch, pinned by test_write_failure_refuses_and_says_so."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "settings.json").write_text(
        json.dumps({"permissions": ["oops"]}), encoding="utf-8"
    )
    report = remediation.fix(tmp_path, apply=True)
    assert report.applied is False
    named = [s for s in report.skipped if s.rule == "config-unusable"]
    assert named, "an unusable permissions shape must be named"
    assert "not an object" in named[0].detail


def test_grade_label_distinguishes_dry_run_from_applied(tmp_path):
    """Eduardo: 'grade after fix' on a dry run reads as a failed fixer."""
    _write_settings(tmp_path, {"allow": ["Bash(rm:*)"], "deny": ["X(y)"]})
    dry = remediation.fix(tmp_path, apply=False)
    text = remediation.render(dry, scan(tmp_path))
    assert "grade after fix" not in text
    assert "unchanged — nothing applied" in text
    applied = remediation.fix(tmp_path, apply=True)
    assert "grade after fix" in remediation.render(applied, scan(tmp_path))


def test_skipped_findings_carry_enough_to_act_on(tmp_path):
    """Francisca M2: two byte-identical 'settings-unscoped-allow @
    settings.json' lines tell the operator nothing about WHICH rules."""
    _write_settings(
        tmp_path, {"allow": ["Read(*)", "Write(*)"], "deny": ["X(y)"]}
    )
    report = remediation.fix(tmp_path, apply=False)
    unscoped = [
        s for s in report.skipped if s.rule == "settings-unscoped-allow"
    ]
    assert len(unscoped) == 2, "one finding per unscoped rule"
    body = remediation.render(report)
    for rule in ("Read(*)", "Write(*)"):
        assert rule in body, (
            f"{rule} must appear in the report — otherwise the two "
            f"findings render as identical lines and the operator "
            f"cannot tell which is which"
        )


def test_apply_without_fix_is_an_error_not_a_silent_scan(tmp_path):
    """Francisca M1: a destructive flag must never degrade quietly."""
    from core.governance import harness_scanner_cli as cli

    _write_settings(tmp_path, {"allow": ["Bash(rm:*)"]})
    with pytest.raises(SystemExit) as exc:
        cli.main([str(tmp_path), "--apply"])
    assert exc.value.code == 2


def test_partial_apply_names_what_reached_disk(tmp_path):
    """Francisca/Eduardo r2 B1: one file written, the next failing, must
    never render as 'nothing was written' — the operator's disk HAS
    changed and the other file still carries its dangerous rule."""
    _write_settings(
        tmp_path, {"allow": ["Bash(rm:*)", "Read(src/**)"], "deny": ["X(y)"]}
    )
    # settings.local.json lives in a directory we make unwritable, so its
    # atomic write fails while settings.json succeeds.
    locked = tmp_path / "locked"
    locked.mkdir()
    real_local = locked / "settings.local.json"
    real_local.write_text(
        json.dumps({"permissions": {
            "allow": ["Bash(sudo rm:*)"], "deny": ["X(y)"]}}),
        encoding="utf-8",
    )
    (tmp_path / "settings.local.json").symlink_to(real_local)
    locked.chmod(0o555)
    try:
        report = remediation.fix(tmp_path, apply=True)
    finally:
        locked.chmod(0o755)

    if os.geteuid() == 0:
        pytest.skip("a directory mode does not stop root")
    # Unconditional: if the fixture stops producing a partial the test
    # must FAIL, not pass asserting nothing (QG C3 r3, Francisca B4).
    assert report.partial is True
    text = remediation.render(report, scan(tmp_path))
    assert "PARTIAL APPLY" in text
    assert "nothing was written" not in text, (
        "settings.json was written — saying otherwise is a lie about "
        "the operator's disk"
    )
    assert report.applied is False
    assert report.failed == ["settings.local.json"]
    assert report.written == ["settings.json"]
    # The surviving rule must NEVER appear under a past-tense removal:
    # a false "removed" on a CRITICAL grant ends the operator's
    # attention (QG C3 r3, both reviewers, reproduced).
    survivor = "Bash(sudo rm:*)"
    assert survivor in json.loads(real_local.read_text())[
        "permissions"]["allow"], "fixture must leave the rule live"
    removed_block = text.split("settings.local.json:")[0]
    assert survivor not in removed_block, (
        "the surviving rule is printed under the file that WAS written"
    )
    assert "would remove" in text, (
        "the failed file's rules are still only PLANNED removals"
    )
    payload = report.to_dict()
    assert payload["written"] == ["settings.json"]
    assert payload["failed"] == ["settings.local.json"]
    assert payload["partial"] is True


def test_free_text_skip_keeps_the_scanners_label(tmp_path):
    """Francisca r2 M1: a permission-bypass rule was described to the
    operator as probably benign because the label was discarded."""
    rule = "Bash(claude -p --dangerously-skip-permissions:*)"
    _write_settings(tmp_path, {"allow": [rule], "deny": ["X(y)"]})
    report = remediation.fix(tmp_path, apply=False)
    body = remediation.render(report)
    assert rule not in report.removed_allow, "free-text matches are named"
    assert "permission bypass" in body, (
        "the scanner's own label must survive into the skip detail — "
        "otherwise the tool nudges the operator to keep a real critical"
    )


def test_json_surface_names_which_files_reached_disk(tmp_path, capsys):
    """Francisca r3 B2: --json is the automation contract. A consumer
    reading only `applied: false` on a partial run concludes nothing was
    written while one file has already been replaced."""
    if os.geteuid() == 0:
        pytest.skip("a directory mode does not stop root")
    from core.governance import harness_scanner_cli as cli

    _write_settings(tmp_path, {"allow": ["Bash(rm:*)"], "deny": ["X(y)"]})
    locked = tmp_path / "locked"
    locked.mkdir()
    real = locked / "settings.local.json"
    real.write_text(
        json.dumps({"permissions": {
            "allow": ["Bash(sudo rm:*)"], "deny": ["X(y)"]}}),
        encoding="utf-8",
    )
    (tmp_path / "settings.local.json").symlink_to(real)
    locked.chmod(0o555)
    try:
        cli.main([str(tmp_path), "--fix", "--apply", "--json"])
    finally:
        locked.chmod(0o755)
    payload = json.loads(capsys.readouterr().out)[0]
    assert payload["partial"] is True
    assert payload["written"] == ["settings.json"]
    assert payload["failed"] == ["settings.local.json"]
    assert payload["applied"] is False


def test_run_level_refusal_is_rendered_not_swallowed(tmp_path, monkeypatch):
    """Francisca r4 B1: a scan that raises leaves no states, so the
    per-file render had nothing to print and returned the empty string —
    the one failure meaning 'I examined nothing' printing nothing."""
    def _boom(_root):
        raise RuntimeError("scan exploded")

    monkeypatch.setattr(remediation, "scan", _boom)
    report = remediation.fix(tmp_path, apply=True)
    assert report.refused and "scan failed" in report.refused
    rendered = remediation.render(report)
    assert rendered.strip(), "a refused run must not render as nothing"
    assert "REFUSED" in rendered
    assert report.refused in rendered


def test_unreadable_root_refuses_instead_of_raising(tmp_path, capsys):
    """Francisca r4 B2: an unreadable ROOT passes the is_dir() filter and
    then raises PermissionError out of scan — a security tool answering a
    locked directory with a traceback has told the operator nothing."""
    if os.geteuid() == 0:
        pytest.skip("mode 000 does not stop root")
    from core.governance import harness_scanner_cli as cli

    _write_settings(tmp_path, {"allow": ["Bash(rm:*)"], "deny": ["X(y)"]})
    tmp_path.chmod(0o000)
    try:
        code = cli.main([str(tmp_path), "--fix", "--apply"])
    finally:
        tmp_path.chmod(0o755)
    out = capsys.readouterr().out
    assert code == 2, "a root we could not read is not a clean run"
    assert "REFUSED" in out and "cannot scan" in out


def test_fix_pointed_at_a_settings_file_refuses_out_loud(tmp_path, capsys):
    """Francisca r5 B2, verbatim repro.

    `shield ~/.claude/settings.json --fix` — the file rather than its
    directory, a normal invocation — exited 2 with a single newline on
    stdout, the code reserved for "grade F or any CRITICAL", with nothing
    to explain it. The read-only path answered the SAME argument with
    Grade A (100/100).
    """
    from core.governance import harness_scanner_cli as cli

    path = _write_settings(tmp_path, {"allow": ["Bash(rm:*)"], "deny": []})
    code = cli.main([str(path), "--fix"])
    captured = capsys.readouterr()
    assert code == 2
    assert "REFUSED" in captured.err, "a bare exit code explains nothing"
    assert str(path) in captured.err
    assert cli.main([str(path)]) == 2, "one input, one answer from one tool"


def test_refused_rescan_still_reports_what_fix_planned(tmp_path, monkeypatch,
                                                       capsys):
    """Francisca r5 M3: the fix report was computed, then thrown away.

    Whatever `fix()` planned or wrote is exactly what the operator needs
    when the re-scan is the thing that broke.
    """
    from core.governance import harness_scanner_cli as cli

    _write_settings(tmp_path, {"allow": ["Bash(rm:*)"], "deny": []})
    monkeypatch.setattr(
        cli, "_safe_scan", lambda root: f"REFUSED: cannot scan {root} — boom")
    code = cli.main([str(tmp_path), "--fix"])
    out = capsys.readouterr().out
    assert code == 2
    assert "REFUSED" in out and "boom" in out
    assert "Bash(rm:*)" in out, "the plan must survive a failed re-grade"


def test_fix_that_graded_nothing_never_exits_clean():
    """QG C3 r6: `exit_code(merge([]))` grades an empty read as A.

    Two callers guard the empty-root case, so this was invisible from
    the CLI — the r5 B2 defect alive one level down, waiting for a
    third caller that did not guard.
    """
    import argparse

    from core.governance import harness_scanner_cli as cli

    args = argparse.Namespace(apply=False, as_json=False, fix=True, path=[])
    assert cli._fix([], args) == 2
    assert cli._grade([], args) == 2
    with pytest.raises(ValueError, match="nothing was scanned"):
        cli.merge([])  # the primitive under both guards (r7, Francisca M1)


def test_refused_rescan_json_payload_carries_the_fix_plan(tmp_path, monkeypatch,
                                                          capsys):
    """Francisca r6 M2: the text arm was pinned, the JSON arm was not.

    The r5 mutation was COMPOUND — it dropped the payload dict and the
    rendered text in one edit — and only the text half killed the test,
    so "KILLED" credited a guard that did not exist. A machine consumer
    reading --json got `{"root": ..., "refused": ...}` and nothing about
    what the fix had planned or written.
    """
    from core.governance import harness_scanner_cli as cli

    _write_settings(tmp_path, {"allow": ["Bash(rm:*)"], "deny": []})
    monkeypatch.setattr(
        cli, "_safe_scan", lambda root: f"REFUSED: cannot scan {root} — boom")
    code = cli.main([str(tmp_path), "--fix", "--json"])
    payload = json.loads(capsys.readouterr().out)[0]
    assert code == 2
    assert payload["refused"].endswith("boom")
    assert "Bash(rm:*)" in json.dumps(payload["removed_allow"])
    assert "skipped" in payload and "files" in payload


def test_fix_grades_from_the_scan_it_printed(tmp_path, monkeypatch):
    """Francisca r5 M1: the exit code came from a SECOND scan.

    Two reads of the same root can disagree — a concurrent edit between
    them makes the grade on screen and the code CI gates on describe
    different files. One read, one answer.
    """
    from core.governance import harness_scanner_cli as cli

    _write_settings(tmp_path, {"allow": ["Bash(rm:*)"], "deny": []})
    calls = []
    real = cli._safe_scan
    monkeypatch.setattr(
        cli, "_safe_scan", lambda root: (calls.append(root), real(root))[1])
    cli.main([str(tmp_path), "--fix"])
    assert len(calls) == 1, f"one re-scan per root, got {len(calls)}"


def test_failed_write_with_a_backup_names_it_as_the_original(tmp_path, monkeypatch):
    """Francisca r4 M3: the '(the untouched original)' arm is a ternary,
    so line coverage reports it green while nothing exercises it."""
    path = _write_settings(
        tmp_path, {"allow": ["Bash(rm:*)"], "deny": ["X(y)"]}
    )
    original = path.read_bytes()

    def _boom(*_a, **_k):
        raise OSError("disk full")

    monkeypatch.setattr(remediation.json_store, "write_json_atomic", _boom)
    report = remediation.fix(tmp_path, apply=True)
    assert report.applied is False and report.failed == ["settings.json"]
    rendered = remediation.render(report)
    assert "(the untouched original)" in rendered
    assert report.backups and report.backups[0].read_bytes() == original
    assert path.read_bytes() == original, "the write failed; disk unchanged"
