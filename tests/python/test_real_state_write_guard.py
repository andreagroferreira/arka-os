"""Tests for the suite's real-state write guard (issue #497).

The guard is the thing that keeps `pytest tests/python/` from rewriting
the working tree, so its own comparison has to be right: the symptom it
exists to catch wrote BYTE-IDENTICAL content, which means a guard that
compares only hashes reports a clean run and is indistinguishable from
one that works — and the mirror error, comparing only mtime, goes blind
to a metadata-preserving write.

Imported by unique module name, never ``from conftest import ...``:
``sys.modules["conftest"]`` belongs to whichever conftest pytest loads
first, and this tree has three.
"""

from __future__ import annotations

from pathlib import Path

from _real_state_guard import (
    REPO_ROOT,
    collect_violations,
    describe,
    fingerprints,
    format_failure,
)

_A = Path("/repo/config/claude-agents/architect.md")
_B = Path("/repo/departments/brand/workflows/audit.yaml")


class TestCollectViolations:
    def test_identical_snapshots_report_nothing(self):
        snapshot = {_A: (100, "hash-a")}
        found = collect_violations(snapshot, dict(snapshot))
        assert found == {
            "rewritten": [], "mutated": [], "created": [], "deleted": [],
        }

    def test_byte_identical_rewrite_is_still_a_violation(self):
        """THE regression: same bytes, new mtime — the #497 symptom."""
        found = collect_violations({_A: (100, "h")}, {_A: (200, "h")})
        assert found["rewritten"] == [str(_A)]
        assert found["mutated"] == []

    def test_content_change_is_reported_as_both(self):
        found = collect_violations({_A: (100, "h1")}, {_A: (200, "h2")})
        assert found["rewritten"] == [str(_A)]
        assert found["mutated"] == [str(_A)]

    def test_created_and_deleted_are_reported(self):
        found = collect_violations({_A: (1, "h")}, {_B: (1, "h")})
        assert found["created"] == [str(_B)]
        assert found["deleted"] == [str(_A)]

    def test_a_read_does_not_move_mtime(self, tmp_path):
        """Reads must stay legal — the agent-parity tests read these paths."""
        target = tmp_path / "descriptor.md"
        target.write_text("x", encoding="utf-8")
        before = {target: (target.stat().st_mtime_ns, "h")}
        target.read_text(encoding="utf-8")
        after = {target: (target.stat().st_mtime_ns, "h")}
        assert collect_violations(before, after)["rewritten"] == []


class TestFormatFailure:
    def test_clean_session_formats_nothing(self):
        assert format_failure(collect_violations({_A: (1, "h")},
                                                 {_A: (1, "h")})) == ""

    def test_byte_identical_rewrite_fails_the_session(self):
        report = format_failure(collect_violations({_A: (1, "h")},
                                                   {_A: (2, "h")}))
        assert report
        assert str(_A) in report

    def test_mtime_preserved_content_change_fails_the_session(self):
        """Timestamp-carrying writers (shutil.copy2 via copystat, rsync -t,
        tar -p) stamp the SOURCE mtime onto the destination. When that
        timestamp matches the snapshot, the bytes change and mtime does
        not. Gating on `rewritten` alone let that through while `mutated`
        silently held the truth."""
        report = format_failure(collect_violations({_A: (1, "h1")},
                                                   {_A: (1, "h2")}))
        assert report, "content change with preserved mtime must fail"
        assert "mtime preserved" in report
        assert str(_A) in report

    def test_copystat_blind_spot_is_reachable_on_a_real_filesystem(
        self, tmp_path
    ):
        """Proved against the real filesystem, not asserted.

        Plain copy2 usually MOVES mtime, because the source rarely shares
        the destination's timestamp — so the blind spot is conditional,
        and the honest demonstration makes that condition explicit: a
        source carrying the destination's own mtime (a snapshot restore,
        a tar/rsync round trip) writes new bytes at the old timestamp.
        """
        import os
        import shutil

        guarded = tmp_path / "guarded.md"
        guarded.write_text("old content", encoding="utf-8")
        original_ns = guarded.stat().st_mtime_ns

        source = tmp_path / "restored-from-backup.md"
        source.write_text("new content", encoding="utf-8")
        os.utime(source, ns=(original_ns, original_ns))

        before = {guarded: (original_ns, "old")}
        shutil.copy2(source, guarded)  # copystat carries the timestamp over
        after = {guarded: (guarded.stat().st_mtime_ns, "new")}

        assert after[guarded][0] == original_ns, "mtime did not move"
        assert guarded.read_text(encoding="utf-8") == "new content"

        found = collect_violations(before, after)
        assert found["rewritten"] == [], "the mtime test alone is blind here"
        assert found["mutated"] == [describe(guarded)]
        assert format_failure(found), "the session must still fail"

    def test_created_and_deleted_fail_the_session(self):
        assert format_failure(collect_violations({}, {_B: (1, "h")}))
        assert format_failure(collect_violations({_A: (1, "h")}, {}))


class TestGuardWiring:
    def test_fingerprints_cover_the_generated_agent_catalog(self):
        tracked = fingerprints()
        assert any(
            "config/claude-agents" in describe(path) for path in tracked
        ), "the guard must watch the generated agent catalog"

    def test_fingerprints_cover_the_workflow_yamls(self):
        tracked = fingerprints()
        assert any(
            "/workflows/" in describe(path) for path in tracked
        ), "the guard must watch departments/*/workflows/*.yaml"

    def test_repo_paths_are_reported_relative(self):
        """Repo-relative names keep the failure message readable; paths
        outside the repo (~/.arkaos/projects) stay absolute."""
        tracked = sorted(fingerprints())
        assert tracked, "guard tracked nothing — globs are wrong"
        in_repo = [p for p in tracked if str(p).startswith(str(REPO_ROOT))]
        assert in_repo, "no guarded path inside the repo"
        assert all(not describe(path).startswith("/") for path in in_repo)

    def test_conftest_exposes_only_the_fixture(self):
        """Lock the split that fixes the bare-name collision: helpers live
        in _real_state_guard, so no sibling conftest can shadow them."""
        source = (REPO_ROOT / "tests" / "python" / "conftest.py").read_text(
            encoding="utf-8"
        )
        assert "from _real_state_guard import" in source
        assert "def collect_violations" not in source
        assert "def fingerprints" not in source
