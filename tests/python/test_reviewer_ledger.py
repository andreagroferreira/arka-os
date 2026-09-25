"""Reviewer ledger — the direct channel from QG reviewers to the operator.

The defect these tests pin: of 81 corpus records, 80 were authored by
the aggregator and none by a reviewer, and every persisted reviewer
output on disk came from the parent transcript rather than the
subagent's own. A reviewer's verdict must land verbatim, hashed, and
only when attribution is proven.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from core.governance import reviewer_ledger


@pytest.fixture
def ledger_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".arkaos").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    return home


VERDICT_BODY = {
    "verdict": "REJECTED",
    "evidence_report": {
        "overall": "fail",
        "checks_ran": ["lint"],
        "checks_failed": ["lint"],
        "checks_skipped": [],
    },
    "blockers": [
        {"check": "lint", "detail": "ruff exit 1", "file": "a.py",
         "verdict": "CONFIRMED"},
        {"check": "tests", "detail": "3 failed", "file": "b.py",
         "verdict": "CONFIRMED"},
    ],
    "reviewer": "tech-director-francisca",
    "model_used": "opus",
}


def _reviewer_output(body: dict | None = None, fence: str = "arka-qgverdict") -> str:
    payload = json.dumps(body if body is not None else VERDICT_BODY, indent=2)
    return (
        "Technical review complete. Two blockers reproduced.\n\n"
        f"```{fence}\n{payload}\n```\n"
    )


class TestCapture:
    def test_records_verbatim_with_digest(self, ledger_home):
        raw = _reviewer_output()
        record = reviewer_ledger.record_reviewer_output(
            "sess-1", "francisca-tech", raw, "post-tool-use"
        )
        assert record is not None
        assert record["raw_output"] == raw, "reviewer text must survive verbatim"
        assert record["raw_sha256"] == __import__("hashlib").sha256(
            raw.encode("utf-8")
        ).hexdigest()
        assert record["verdict"]["verdict"] == "REJECTED"
        assert len(record["verdict"]["blockers"]) == 2
        assert record["source"] == "post-tool-use"
        assert Path(record["path"]).is_file()
        session_dir = Path(record["path"]).parent
        mode = os.stat(session_dir).st_mode & 0o777
        assert mode == 0o700, (
            f"the record path must tighten the session dir too, got {oct(mode)}"
        )

    def test_accepts_plain_json_fence(self, ledger_home):
        """Deployed reviewers emit ```json today — capture must not depend
        on them adopting the new fence before the channel works."""
        record = reviewer_ledger.record_reviewer_output(
            "sess-json", "eduardo-copy",
            _reviewer_output(dict(VERDICT_BODY, reviewer="copy-director-eduardo"),
                             fence="json"),
            "post-tool-use",
        )
        assert record["verdict"]["verdict"] == "REJECTED"

    def test_file_is_owner_only(self, ledger_home):
        record = reviewer_ledger.record_reviewer_output(
            "sess-perm", "francisca-tech", _reviewer_output(), "post-tool-use"
        )
        mode = os.stat(record["path"]).st_mode & 0o777
        assert mode == 0o600, f"reviewer verdicts must be 0600, got {oct(mode)}"

    def test_ignores_non_reviewer_agents(self, ledger_home):
        assert reviewer_ledger.record_reviewer_output(
            "sess-2", "frontend-dev", "some output", "post-tool-use"
        ) is None
        assert not (reviewer_ledger.ledger_root() / "sess-2").exists()

    def test_captures_the_aggregator_too(self, ledger_home):
        record = reviewer_ledger.record_reviewer_output(
            "sess-agg", "marta-cqo", _reviewer_output(), "post-tool-use"
        )
        assert record is not None, "the aggregate belongs on the audit surface"

    def test_rejects_unsafe_session_id(self, ledger_home):
        assert reviewer_ledger.record_reviewer_output(
            "../escape", "francisca-tech", _reviewer_output(), "post-tool-use"
        ) is None

    def test_dedupes_across_sources(self, ledger_home):
        raw = _reviewer_output()
        first = reviewer_ledger.record_reviewer_output(
            "sess-3", "francisca-tech", raw, "post-tool-use"
        )
        second = reviewer_ledger.record_reviewer_output(
            "sess-3", "francisca-tech", raw, "subagent-stop"
        )
        assert second["raw_sha256"] == first["raw_sha256"]
        assert second["source"] == "post-tool-use", "same text, one record"
        files = list((reviewer_ledger.ledger_root() / "sess-3").glob("*.json"))
        assert len(files) == 1

    def test_divergent_text_is_a_second_record(self, ledger_home):
        """Divergent captures land as separate records — collision safety,
        not a delivered tamper signal (see the ledger module docstring)."""
        reviewer_ledger.record_reviewer_output(
            "sess-4", "francisca-tech", _reviewer_output(), "post-tool-use"
        )
        altered = dict(VERDICT_BODY, verdict="APPROVED", blockers=[])
        reviewer_ledger.record_reviewer_output(
            "sess-4", "francisca-tech", _reviewer_output(altered), "subagent-stop"
        )
        files = sorted((reviewer_ledger.ledger_root() / "sess-4").glob("*.json"))
        assert len(files) == 2
        digests = {json.loads(f.read_text())["raw_sha256"] for f in files}
        assert len(digests) == 2


class TestParseFailures:
    def test_malformed_json_is_recorded_never_silent(self, ledger_home):
        raw = "Review done.\n\n```arka-qgverdict\n{not: valid json,,}\n```\n"
        record = reviewer_ledger.record_reviewer_output(
            "sess-5", "francisca-tech", raw, "post-tool-use"
        )
        assert record["verdict"] is None
        assert record["parse_error"], "a broken verdict must be visible"
        assert record["raw_output"] == raw, "raw text survives a parse failure"

    def test_schema_mismatch_keeps_the_dict_and_the_error(self, ledger_home):
        raw = _reviewer_output({"verdict": "MAYBE"})
        record = reviewer_ledger.record_reviewer_output(
            "sess-6", "francisca-tech", raw, "post-tool-use"
        )
        assert record["verdict"] == {"verdict": "MAYBE"}
        assert record["parse_error"].startswith("schema:")

    def test_prose_only_output_still_recorded(self, ledger_home):
        record = reviewer_ledger.record_reviewer_output(
            "sess-7", "eduardo-copy", "I approve, looks good.", "post-tool-use"
        )
        assert record["verdict"] is None
        assert record["parse_error"] is None
        assert record["raw_output"] == "I approve, looks good."


class TestSanitizerBoundary:
    def test_missing_config_keeps_the_words(self, ledger_home, monkeypatch):
        """Erasing a reviewer's verdict to avoid an unproven redaction is
        the relay failure this ledger exists to end. Local-only, 0600."""
        from core.evals import sanitizer

        def _raise(_text):
            raise sanitizer.SanitizerConfigMissing("no redaction config")

        monkeypatch.setattr(sanitizer, "sanitize_text", _raise)
        raw = _reviewer_output()
        record = reviewer_ledger.record_reviewer_output(
            "sess-8", "francisca-tech", raw, "post-tool-use"
        )
        assert record["raw_output"] == raw
        assert record["sanitized"] is False


class TestRetention:
    def test_sweep_removes_only_expired(self, ledger_home):
        import time

        reviewer_ledger.record_reviewer_output(
            "sess-old", "francisca-tech", _reviewer_output(), "post-tool-use"
        )
        reviewer_ledger.record_reviewer_output(
            "sess-new", "francisca-tech", _reviewer_output(), "post-tool-use"
        )
        old_dir = reviewer_ledger.ledger_root() / "sess-old"
        ancient = time.time() - (100 * 86400)
        os.utime(old_dir, (ancient, ancient))

        assert reviewer_ledger.sweep_expired(days=90) == 1
        assert not old_dir.exists()
        assert (reviewer_ledger.ledger_root() / "sess-new").is_dir()


class TestVerdictSelection:
    def test_last_fence_wins_over_an_illustrated_schema(self, ledger_home):
        """A review that quotes the schema before stating its verdict must
        file the VERDICT, not the illustration. Taking the first fence
        filed a REJECTED review as APPROVED with no error recorded."""
        illustration = json.dumps({"verdict": "APPROVED", "evidence_report": {
            "overall": "pass", "checks_ran": [], "checks_failed": [],
            "checks_skipped": []}, "blockers": [],
            "reviewer": "tech-director-francisca", "model_used": "opus",
            "notes": "EXAMPLE ONLY"})
        raw = (
            "The schema looks like this:\n\n```json\n" + illustration + "\n```\n\n"
            "My actual verdict:\n\n```json\n" + json.dumps(VERDICT_BODY) + "\n```\n"
        )
        record = reviewer_ledger.record_reviewer_output(
            "sess-fence", "francisca-tech", raw, "subagent-stop"
        )
        assert record["verdict"]["verdict"] == "REJECTED"
        assert "ambiguous: 2 own verdict fences" in record["parse_error"]

    def test_arka_fence_outranks_a_json_fence(self, ledger_home):
        raw = (
            "```json\n" + json.dumps({"verdict": "APPROVED", "evidence_report": {
                "overall": "pass", "checks_ran": [], "checks_failed": [],
                "checks_skipped": []}, "blockers": [],
                "reviewer": "x", "model_used": "opus"}) + "\n```\n"
            "```arka-qgverdict\n" + json.dumps(VERDICT_BODY) + "\n```\n"
        )
        record = reviewer_ledger.record_reviewer_output(
            "sess-fence2", "francisca-tech", raw, "subagent-stop"
        )
        assert record["verdict"]["verdict"] == "REJECTED"
        assert record["parse_error"] is None


class TestCollisionSafety:
    def test_divergent_text_never_overwrites(self, ledger_home):
        """The digest is in the filename, so two captures that disagree
        cannot collapse into one file at the same seq unless their 8-hex
        prefixes also collide (~2^-32), which _publish adopts on name
        alone."""
        reviewer_ledger.record_reviewer_output(
            "sess-div", "francisca-tech", _reviewer_output(), "post-tool-use"
        )
        altered = dict(VERDICT_BODY, verdict="APPROVED", blockers=[])
        reviewer_ledger.record_reviewer_output(
            "sess-div", "francisca-tech", _reviewer_output(altered), "subagent-stop"
        )
        files = sorted((reviewer_ledger.ledger_root() / "sess-div").glob("*.json"))
        assert len(files) == 2, "divergence must be preserved, not overwritten"

    def test_prefix_ids_do_not_collide(self, ledger_home):
        """copy-director must not scan copy-director-eduardo's records."""
        reviewer_ledger.record_reviewer_output(
            "sess-prefix", "copy-director-eduardo", _reviewer_output(),
            "subagent-stop",
        )
        record = reviewer_ledger.record_reviewer_output(
            "sess-prefix", "copy-director",
            _reviewer_output(dict(VERDICT_BODY, reviewer="copy-director")),
            "subagent-stop",
        )
        assert record["seq"] == 1, "seq must count only this reviewer's records"

    def test_dot_ids_are_rejected(self, ledger_home):
        """'.' and '..' match the safe-id charset: '.' would scatter
        records across the ledger root, '..' onto ~/.arkaos itself."""
        for bad in (".", ".."):
            assert reviewer_ledger.record_reviewer_output(
                bad, "francisca-tech", _reviewer_output(), "subagent-stop"
            ) is None
            assert reviewer_ledger.record_reviewer_output(
                "sess-ok", bad, _reviewer_output(), "subagent-stop"
            ) is None
            reviewer_ledger.queue_notice(bad, None, "x")
            assert reviewer_ledger.notices_context(bad) == ""
        root = reviewer_ledger.ledger_root()
        assert not list(root.glob("*.json")), "no record may land in the root"

    def test_divergent_text_takes_the_next_seq(self, ledger_home):
        """The seq must actually count. A constant seq=1 still lands both
        records — the digest is in the name — so counting files leaves
        the increment itself unpinned."""
        first = reviewer_ledger.record_reviewer_output(
            "sess-seq", "francisca-tech", _reviewer_output(), "post-tool-use"
        )
        altered = dict(VERDICT_BODY, verdict="APPROVED", blockers=[])
        second = reviewer_ledger.record_reviewer_output(
            "sess-seq", "francisca-tech", _reviewer_output(altered),
            "subagent-stop",
        )
        assert first["seq"] == 1
        assert second["seq"] == 2, "a divergent capture must take the next seq"
        assert "-1-" in Path(first["path"]).name
        assert "-2-" in Path(second["path"]).name

    def test_a_dot_session_id_cannot_write_into_the_quarantine(self, ledger_home):
        """'.quarantine' matches the safe-id charset, so a session by that
        name filed LIVE records into the evidence directory — which the
        sweep deliberately refuses to age out (sweep_expired's entry skip
        is the whole guard; _purge contributes none)."""
        assert reviewer_ledger.record_reviewer_output(
            ".quarantine", "francisca-tech", _reviewer_output(), "subagent-stop"
        ) is None
        assert not (reviewer_ledger.ledger_root() / ".quarantine").exists()
        reviewer_ledger.queue_notice(".quarantine", None, "[arka:subagent-qa] x")
        assert reviewer_ledger.notices_context(".quarantine") == ""


class TestSweepSafety:
    def test_symlinked_session_dir_is_never_followed(self, ledger_home, tmp_path):
        import time

        victim = tmp_path / "victim"
        victim.mkdir()
        # A .json file, so the sweep's own unlink filter cannot make this
        # test pass for the wrong reason (a mutation survived that way).
        # A name the ledger DOES write, so only the symlink guard can
        # save it: a foreign name would be refused by _is_own_file and
        # the test would pass even with the symlink check removed.
        (victim / "francisca-tech-1-deadbeef.json").write_text(
            "{}", encoding="utf-8"
        )
        reviewer_ledger.ledger_root().mkdir(parents=True, exist_ok=True)
        link = reviewer_ledger.ledger_root() / "linked-session"
        link.symlink_to(victim)
        ancient = time.time() - (100 * 86400)
        os.utime(victim, (ancient, ancient))

        reviewer_ledger.sweep_expired(days=90)
        assert (victim / "francisca-tech-1-deadbeef.json").is_file(), (
            "sweep followed a symlink into a directory it does not own"
        )
        assert victim.is_dir()
        assert link.is_symlink(), "the link itself must survive too"

    def test_an_interrupted_publish_does_not_block_the_sweep(self, ledger_home):
        """A crash between temp-write and link leaves a .tmp- file behind.
        _purge must recognise it as the ledger's own, or the session dir
        is refused whole and retention never reclaims it."""
        import time

        reviewer_ledger.record_reviewer_output(
            "sess-stale", "francisca-tech", _reviewer_output(), "post-tool-use"
        )
        session_dir = reviewer_ledger.ledger_root() / "sess-stale"
        stale = session_dir / ".francisca-tech-2-deadbeef.json.tmp-99-abcd1234"
        stale.write_text("{}", encoding="utf-8")
        ancient = time.time() - (100 * 86400)
        os.utime(session_dir, (ancient, ancient))

        assert reviewer_ledger.sweep_expired(days=90) == 1, (
            "a stale temp file must not block the sweep"
        )
        assert not session_dir.exists()


class TestOrchestratorNotices:
    """SubagentStop cannot tell the orchestrator anything — its context is
    'delivered to the subagent' (2.1.220). Notices are queued and drained
    by the Stop hook, whose context IS 'delivered to the model'."""

    def test_verdict_notice_round_trip(self, ledger_home):
        record = reviewer_ledger.record_reviewer_output(
            "sess-notice", "francisca-tech", _reviewer_output(), "subagent-stop"
        )
        reviewer_ledger.queue_notice("sess-notice", record, "")
        context = reviewer_ledger.notices_context("sess-notice")
        assert "[arka:qg:reviewer-verdict] francisca-tech REJECTED" in context
        assert "blockers=2" in context
        assert record["path"] in context
        assert "quote the verdict verbatim" in context

    def test_refuted_blockers_are_not_counted(self, ledger_home):
        """A REFUTED claim is one the reviewer considered and dismissed;
        counting it inflates the headline the orchestrator reads."""
        body = dict(VERDICT_BODY, blockers=[
            {"check": "lint", "detail": "d", "file": "a.py",
             "verdict": "CONFIRMED"},
            {"check": "perf", "detail": "d", "file": "b.py",
             "verdict": "REFUTED"},
            {"check": "sec", "detail": "d", "file": "c.py",
             "verdict": "REFUTED"},
        ])
        body = dict(body, reviewer="copy-director-eduardo")
        record = reviewer_ledger.record_reviewer_output(
            "sess-refuted", "eduardo-copy", _reviewer_output(body), "subagent-stop"
        )
        reviewer_ledger.queue_notice("sess-refuted", record, "")
        assert "blockers=1" in reviewer_ledger.notices_context("sess-refuted")

    def test_reading_does_not_clear_and_clearing_is_one_shot(self, ledger_home):
        """Read and clear are split so a failed delivery cannot lose a
        verdict; once cleared, re-delivery would be the loop again."""
        record = reviewer_ledger.record_reviewer_output(
            "sess-once", "francisca-tech", _reviewer_output(), "subagent-stop"
        )
        reviewer_ledger.queue_notice("sess-once", record, "")
        assert reviewer_ledger.notices_context("sess-once")
        assert reviewer_ledger.notices_context("sess-once"), (
            "reading must not consume: an emit that fails after the read "
            "would drop the verdict entirely"
        )
        context, tokens = reviewer_ledger.claim_notices_context("sess-once")
        assert context and tokens
        assert reviewer_ledger.notices_context("sess-once"), (
            "a claim that is never cleared must still be re-deliverable"
        )
        reviewer_ledger.clear_notices("sess-once", tokens)
        assert reviewer_ledger.notices_context("sess-once") == ""

    def test_a_notice_queued_during_delivery_is_not_destroyed(self, ledger_home):
        """The whole queue file used to be unlinked after the read, so a
        SubagentStop that appended while the orchestrator was being told
        was destroyed unread — a reviewer verdict lost in the window."""
        first = reviewer_ledger.record_reviewer_output(
            "sess-window", "francisca-tech", _reviewer_output(), "subagent-stop"
        )
        reviewer_ledger.queue_notice("sess-window", first, "")
        context, tokens = reviewer_ledger.claim_notices_context("sess-window")
        assert "francisca-tech" in context

        # A second reviewer finishes DURING the delivery.
        late = reviewer_ledger.record_reviewer_output(
            "sess-window", "eduardo-copy",
            _reviewer_output(dict(VERDICT_BODY, reviewer="copy-director-eduardo")),
            "subagent-stop",
        )
        reviewer_ledger.queue_notice("sess-window", late, "")
        reviewer_ledger.clear_notices("sess-window", tokens)

        remaining = reviewer_ledger.notices_context("sess-window")
        assert "eduardo-copy" in remaining, "the late verdict must survive"
        assert "francisca-tech" not in remaining, "the delivered one is gone"

    def test_an_interrupted_claim_is_re_delivered(self, ledger_home):
        record = reviewer_ledger.record_reviewer_output(
            "sess-crash", "francisca-tech", _reviewer_output(), "subagent-stop"
        )
        reviewer_ledger.queue_notice("sess-crash", record, "")
        _context, _tokens = reviewer_ledger.claim_notices_context("sess-crash")
        # Simulate a crash before clear_notices: the claim file remains.
        again, tokens = reviewer_ledger.claim_notices_context("sess-crash")
        assert "francisca-tech" in again, "a crashed drain must re-deliver"
        reviewer_ledger.clear_notices("sess-crash", tokens)
        assert reviewer_ledger.notices_context("sess-crash") == ""

    def test_nudge_only_notice(self, ledger_home):
        reviewer_ledger.queue_notice("sess-nudge", None, "[arka:subagent-qa] x")
        assert "[arka:subagent-qa] x" in reviewer_ledger.notices_context("sess-nudge")

    def test_a_record_supersedes_the_nudge(self, ledger_home):
        """The real producer (subagent_stop) passes record and nudge
        together on every reviewer dispatch. The only nudge produced says
        "route it through the Quality Gate" — and a captured verdict IS
        the Quality Gate speaking, so the nudge is dropped by design."""
        record = reviewer_ledger.record_reviewer_output(
            "sess-both", "francisca-tech", _reviewer_output(), "subagent-stop"
        )
        reviewer_ledger.queue_notice(
            "sess-both", record, "[arka:subagent-qa] never delivered"
        )
        context = reviewer_ledger.notices_context("sess-both")
        assert "[arka:qg:reviewer-verdict] francisca-tech" in context
        assert "[arka:subagent-qa]" not in context, (
            "a verdict must not arrive alongside advice to go get one"
        )

    def test_nothing_to_say_writes_nothing(self, ledger_home):
        reviewer_ledger.queue_notice("sess-quiet", None, "")
        assert reviewer_ledger.notices_context("sess-quiet") == ""

    def test_unsafe_session_id_is_inert(self, ledger_home):
        reviewer_ledger.queue_notice("../escape", None, "x")
        assert reviewer_ledger.notices_context("../escape") == ""


class TestTruthfulness:
    """The module's own claims must hold — it exists so records can be
    trusted, and a false statement about itself is the same defect class
    it was built to end."""

    def test_notice_names_a_reason_not_a_python_none(self, ledger_home):
        """A reviewer who filed no parsable verdict is exactly who this
        line exists to surface; printing None tells the operator nothing."""
        record = reviewer_ledger.record_reviewer_output(
            "sess-none", "eduardo-copy", "Approved, looks good.", "subagent-stop"
        )
        assert record["parse_error"] is None
        reviewer_ledger.queue_notice("sess-none", record, "")
        context = reviewer_ledger.notices_context("sess-none")
        assert "(None)" not in context
        assert "no verdict block in the reply" in context

    def test_queue_notice_tightens_the_session_dir(self, ledger_home):
        """mkdir honours the umask (0o755); the dir holds verdicts."""
        reviewer_ledger.queue_notice("sess-perm2", None, "[arka:subagent-qa] x")
        mode = os.stat(reviewer_ledger.ledger_root() / "sess-perm2").st_mode & 0o777
        assert mode == 0o700, f"session dir must be 0700, got {oct(mode)}"

    def test_the_queue_file_is_owner_only(self, ledger_home):
        """The queue names reviewers and verdicts — 0600 like the records
        it points at, not the 0644 the umask would leave."""
        reviewer_ledger.queue_notice("sess-perm3", None, "[arka:subagent-qa] x")
        path = reviewer_ledger.ledger_root() / "sess-perm3" / "NOTICES.jsonl"
        mode = os.stat(path).st_mode & 0o777
        assert mode == 0o600, f"queue file must be 0600, got {oct(mode)}"

    def test_capture_refuses_an_unknown_source(self, ledger_home):
        """The fail-closed rule is enforced in the ledger, not only in
        the hook: post_tool_use does not consult _attributable."""
        assert reviewer_ledger.record_reviewer_output(
            "sess-src", "francisca-tech", _reviewer_output(), "parent"
        ) is None
        assert reviewer_ledger.record_reviewer_output(
            "sess-src", "francisca-tech", _reviewer_output(), ""
        ) is None
        assert reviewer_ledger.record_reviewer_output(
            "sess-src", "francisca-tech", _reviewer_output(), "subagent-stop"
        ) is not None

    def test_sweep_never_destroys_while_reporting_zero(self, ledger_home):
        """Globbing *.json deleted every verdict, then failed the rmdir on
        NOTICES.jsonl and returned 0 — destruction with a clean receipt."""
        import time

        record = reviewer_ledger.record_reviewer_output(
            "sess-sweep", "francisca-tech", _reviewer_output(), "subagent-stop"
        )
        reviewer_ledger.queue_notice("sess-sweep", record, "")
        session_dir = reviewer_ledger.ledger_root() / "sess-sweep"
        assert (session_dir / "NOTICES.jsonl").is_file()
        ancient = time.time() - (100 * 86400)
        os.utime(session_dir, (ancient, ancient))

        removed = reviewer_ledger.sweep_expired(days=90)
        assert removed == 1, "a sweep that deletes must report what it deleted"
        assert not session_dir.exists()

    def test_sweep_leaves_a_dir_holding_foreign_content(self, ledger_home):
        import time

        reviewer_ledger.record_reviewer_output(
            "sess-foreign", "francisca-tech", _reviewer_output(), "subagent-stop"
        )
        session_dir = reviewer_ledger.ledger_root() / "sess-foreign"
        (session_dir / "nested").mkdir()
        ancient = time.time() - (100 * 86400)
        os.utime(session_dir, (ancient, ancient))

        assert reviewer_ledger.sweep_expired(days=90) == 0
        assert session_dir.is_dir(), "foreign content must be left alone"
        assert list(session_dir.glob("*.json")), (
            "a refused sweep must not have deleted the verdicts first — "
            "that is destruction with a clean receipt"
        )

    def test_torn_notice_line_does_not_swallow_the_rest(self, ledger_home):
        reviewer_ledger.queue_notice("sess-torn", None, "[arka:subagent-qa] first")
        path = reviewer_ledger.ledger_root() / "sess-torn" / "NOTICES.jsonl"
        with path.open("a", encoding="utf-8") as fh:
            fh.write('{"kind": "subagent-qa", "mess\n')
        reviewer_ledger.queue_notice("sess-torn", None, "[arka:subagent-qa] third")
        context = reviewer_ledger.notices_context("sess-torn")
        assert "first" in context and "third" in context


class TestConcurrentCapture:
    def test_same_text_racing_writers_produce_one_record(self, ledger_home):
        """A file created with O_EXCL is visible before its content is
        flushed: the concurrent writer parsed nothing, believed the text
        was new, and filed a duplicate under the next seq. The digest is
        in the filename, so dedup needs no content."""
        import threading

        raw = _reviewer_output()
        barrier = threading.Barrier(2)

        def capture(source):
            barrier.wait()
            reviewer_ledger.record_reviewer_output(
                "sess-race", "francisca-tech", raw, source
            )

        threads = [
            threading.Thread(target=capture, args=(s,))
            for s in ("post-tool-use", "subagent-stop")
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        files = list((reviewer_ledger.ledger_root() / "sess-race").glob("*.json"))
        assert len(files) == 1, f"identical text must dedupe, got {files}"

    def test_torn_file_never_shadows_the_verdict(self, ledger_home):
        """Publishing the NAME before the BODY let a hook killed on its
        timeout budget leave a 0-byte record that shadowed the real
        verdict forever, while the operator was told the reviewer filed
        none. A name must always imply complete content."""
        raw = _reviewer_output()
        digest = __import__("hashlib").sha256(raw.encode()).hexdigest()
        session_dir = reviewer_ledger.ledger_root() / "sess-torn-file"
        session_dir.mkdir(parents=True)
        (session_dir / f"francisca-tech-1-{digest[:8]}.json").write_text(
            "", encoding="utf-8"
        )
        record = reviewer_ledger.record_reviewer_output(
            "sess-torn-file", "francisca-tech", raw, "subagent-stop"
        )
        assert record is not None
        assert record["verdict"]["verdict"] == "REJECTED", (
            "a torn file must never stand in for the verdict"
        )
        assert record.get("reviewer_id") == "francisca-tech"
        reviewer_ledger.queue_notice("sess-torn-file", record, "")
        context = reviewer_ledger.notices_context("sess-torn-file")
        assert "None" not in context, context
        assert "francisca-tech REJECTED" in context

    def test_publish_is_atomic_no_partial_names(self, ledger_home):
        """Every visible record parses: the body lands before the name."""
        for i in range(25):
            reviewer_ledger.record_reviewer_output(
                "sess-atomic", "francisca-tech",
                _reviewer_output(dict(VERDICT_BODY, notes=f"r{i}")),
                "subagent-stop",
            )
        session_dir = reviewer_ledger.ledger_root() / "sess-atomic"
        for path in session_dir.glob("*.json"):
            assert json.loads(path.read_text(encoding="utf-8"))["raw_sha256"]
        assert not list(session_dir.glob(".*tmp*")), "temp files must not linger"


class TestVerdictOwnership:
    """The aggregator is REQUIRED to quote each reviewer verbatim, so the
    last fence in its reply belongs to someone else. Filing it as the
    aggregator's own put a 7-blocker verdict under an agent whose own
    list held 12 — observed live in marta-cqo-6-c15aff5e.json."""

    def _quoting_reply(self) -> str:
        eduardo = dict(VERDICT_BODY, reviewer="copy-director-eduardo",
                       blockers=[{"check": "copy", "detail": "d",
                                  "file": "a.md", "verdict": "CONFIRMED"}])
        francisca = dict(VERDICT_BODY, reviewer="tech-director-francisca")
        return (
            "### Eduardo — verbatim\n\n```json\n" + json.dumps(eduardo) + "\n```\n"
            "### Francisca — verbatim\n\n```json\n" + json.dumps(francisca) + "\n```\n"
        )

    def test_quoted_reviewers_are_not_filed_as_the_aggregator(self, ledger_home):
        record = reviewer_ledger.record_reviewer_output(
            "sess-quote", "marta-cqo", self._quoting_reply(), "subagent-stop"
        )
        assert record["verdict"] is None, "a quotation is not the quoter's verdict"
        assert "none authored by marta-cqo" in record["parse_error"]
        assert "tech-director-francisca" in record["parse_error"]
        reviewer_ledger.queue_notice("sess-quote", record, "")
        context = reviewer_ledger.notices_context("sess-quote")
        assert "marta-cqo verdict-unparsed" in context
        assert "blockers=" not in context, "no borrowed blocker count"

    def test_own_verdict_after_quotations_is_used(self, ledger_home):
        own = dict(VERDICT_BODY, reviewer="cqo-marta", blockers=[
            {"check": "a", "detail": "d", "file": "f", "verdict": "CONFIRMED"},
            {"check": "b", "detail": "d", "file": "f", "verdict": "CONFIRMED"},
            {"check": "c", "detail": "d", "file": "f", "verdict": "CONFIRMED"},
        ])
        raw = self._quoting_reply() + "\n```json\n" + json.dumps(own) + "\n```\n"
        record = reviewer_ledger.record_reviewer_output(
            "sess-own", "marta-cqo", raw, "subagent-stop"
        )
        assert record["verdict"]["reviewer"] == "cqo-marta"
        assert len(record["verdict"]["blockers"]) == 3
        reviewer_ledger.queue_notice("sess-own", record, "")
        assert "marta-cqo REJECTED blockers=3" in (
            reviewer_ledger.notices_context("sess-own")
        )

    def test_alias_spellings_count_as_the_same_person(self, ledger_home):
        raw = _reviewer_output(dict(VERDICT_BODY, reviewer="tech-director-francisca"))
        record = reviewer_ledger.record_reviewer_output(
            "sess-alias", "francisca-tech", raw, "subagent-stop"
        )
        assert record["verdict"]["verdict"] == "REJECTED", (
            "the dispatch id and the verdict's reviewer field are different "
            "spellings of the same reviewer"
        )

    def test_unclaimed_verdict_is_still_the_dispatched_agent(self, ledger_home):
        body = {k: v for k, v in VERDICT_BODY.items() if k != "reviewer"}
        record = reviewer_ledger.record_reviewer_output(
            "sess-unclaimed", "francisca-tech", _reviewer_output(body),
            "subagent-stop",
        )
        assert record["verdict"] is not None


class TestDigestHonesty:
    """The headline promise is verifiable: hashing a record's
    ``raw_output`` field yields its ``stored_sha256`` (the record is
    JSON, so the digest is over the stored text, not over the file).
    ``raw_sha256`` is the dedup key over the text as returned, which
    redaction may have rewritten."""

    def test_stored_digest_matches_the_raw_output_field(self, ledger_home):
        import hashlib

        record = reviewer_ledger.record_reviewer_output(
            "sess-digest", "francisca-tech", _reviewer_output(), "subagent-stop"
        )
        on_disk = json.loads(Path(record["path"]).read_text(encoding="utf-8"))
        assert on_disk["stored_sha256"] == hashlib.sha256(
            on_disk["raw_output"].encode("utf-8")
        ).hexdigest()

    def test_digests_diverge_only_when_redaction_rewrote_the_text(
        self, ledger_home, monkeypatch
    ):
        import hashlib

        from core.evals import sanitizer

        monkeypatch.setattr(
            sanitizer, "sanitize_text",
            lambda text: (text.replace("Two blockers", "[REDACTED]"), {"n": 1}),
        )
        raw = _reviewer_output()
        record = reviewer_ledger.record_reviewer_output(
            "sess-redacted", "francisca-tech", raw, "subagent-stop"
        )
        assert record["sanitized"] is True
        assert record["raw_sha256"] == hashlib.sha256(raw.encode()).hexdigest()
        assert record["stored_sha256"] != record["raw_sha256"]
        assert record["stored_sha256"] == hashlib.sha256(
            record["raw_output"].encode()
        ).hexdigest(), "the operator must be able to verify what is on disk"


class TestSweepScope:
    def test_quarantine_is_never_swept(self, ledger_home):
        """.quarantine/ holds invalidated verdicts kept deliberately as
        evidence; retention must never age them out."""
        import time

        quarantine = reviewer_ledger.ledger_root() / ".quarantine"
        quarantine.mkdir(parents=True)
        # A name _purge WOULD delete, so only sweep_expired's entry skip
        # can save it (a foreign name would be refused anyway). Both of
        # that skip's clauses now catch a leading dot, so this pins the
        # skip as a whole, not startswith(".") on its own.
        kept = quarantine / "francisca-tech-1-deadbeef.json"
        kept.write_text("{}", encoding="utf-8")
        ancient = time.time() - (300 * 86400)
        os.utime(quarantine, (ancient, ancient))

        assert reviewer_ledger.sweep_expired(days=90) == 0
        assert kept.is_file(), "quarantined evidence must survive retention"
        assert quarantine.is_dir()

    def test_foreign_file_is_never_deleted(self, ledger_home):
        """Unlinking whatever happened to be a regular file destroyed an
        operator's notes this module never wrote."""
        import time

        reviewer_ledger.record_reviewer_output(
            "sess-notes", "francisca-tech", _reviewer_output(), "subagent-stop"
        )
        session_dir = reviewer_ledger.ledger_root() / "sess-notes"
        notes = session_dir / "operators-notes.txt"
        notes.write_text("do not delete", encoding="utf-8")
        ancient = time.time() - (200 * 86400)
        os.utime(session_dir, (ancient, ancient))

        assert reviewer_ledger.sweep_expired(days=90) == 0
        assert notes.is_file(), "a file the ledger did not write must survive"
        assert list(session_dir.glob("*.json")), (
            "and the refusal must come BEFORE any unlink"
        )


class TestWriteGuards:
    """Both exception arms of _write_record are load-bearing and both
    survived mutation until now."""

    def test_adopt_on_existing_name_returns_the_record(self, ledger_home):
        """`except FileExistsError: pass` — under `return None` instead,
        7 of 8 concurrent writers reported failure for a verdict that IS
        on disk, and the notice for it was never queued."""
        raw = _reviewer_output()
        first = reviewer_ledger.record_reviewer_output(
            "sess-adopt", "francisca-tech", raw, "post-tool-use"
        )
        session_dir = reviewer_ledger.ledger_root() / "sess-adopt"
        # Force the collision path: call the writer directly, so the
        # dedup scan in record_reviewer_output is bypassed and os.link
        # meets a name that already exists — a second writer, same seq.
        record = reviewer_ledger._build_record(
            "sess-adopt", "francisca-tech", raw, "subagent-stop",
            first["raw_sha256"], 1,
        )
        path = reviewer_ledger._write_record(session_dir, record)
        assert path is not None, "an existing name means already captured"
        assert Path(path).is_file()
        assert json.loads(Path(path).read_text())["raw_sha256"] == (
            first["raw_sha256"]
        )

    def test_failed_link_never_returns_a_path(self, ledger_home, monkeypatch):
        """`except OSError: return None` — under `pass` instead, the
        record claimed a path for a file that was never created and the
        notice pointed the operator at it."""
        raw = _reviewer_output()
        session_dir = reviewer_ledger.ledger_root() / "sess-linkfail"
        session_dir.mkdir(parents=True)

        def _boom(_src, _dst):
            raise OSError("cross-device link")

        monkeypatch.setattr(reviewer_ledger.os, "link", _boom)
        record = reviewer_ledger._build_record(
            "sess-linkfail", "francisca-tech", raw, "subagent-stop", "a" * 64, 1,
        )
        assert reviewer_ledger._write_record(session_dir, record) is None
        assert not list(session_dir.glob("*.json")), "no phantom artifact"
        assert not list(session_dir.glob(".*tmp*")), "temp must be cleaned up"

    def test_record_reviewer_output_returns_none_when_publish_fails(
        self, ledger_home, monkeypatch
    ):
        def _boom(_src, _dst):
            raise OSError("cross-device link")

        monkeypatch.setattr(reviewer_ledger.os, "link", _boom)
        assert reviewer_ledger.record_reviewer_output(
            "sess-nopath", "francisca-tech", _reviewer_output(), "subagent-stop"
        ) is None


def test_prefix_collision_does_not_adopt_a_different_text(ledger_home):
    """The filename carries 32 bits of the digest; the body carries 256.
    A prefix match with a different body is a different verdict.

    The impostor is planted with NO genuine record present, so the
    256-bit confirmation is the only thing standing between the capture
    and someone else's words. An earlier version planted it at seq 9,
    which sorts after a genuine seq 1 — the guard was never reached and
    the test passed without exercising it.
    """
    raw = _reviewer_output()
    digest = __import__("hashlib").sha256(raw.encode("utf-8")).hexdigest()
    session_dir = reviewer_ledger.ledger_root() / "sess-collide"
    session_dir.mkdir(parents=True)
    impostor = session_dir / f"francisca-tech-1-{digest[:8]}.json"
    impostor.write_text(
        json.dumps({
            "raw_sha256": "f" * 64,
            "raw_output": "WORDS THE REVIEWER NEVER WROTE",
        }),
        encoding="utf-8",
    )
    record = reviewer_ledger.record_reviewer_output(
        "sess-collide", "francisca-tech", raw, "post-tool-use"
    )
    assert record is not None
    assert record["raw_sha256"] == digest
    assert record["raw_output"] == raw, (
        "a 32-bit filename match must never substitute another text"
    )
    assert "NEVER WROTE" not in record["raw_output"]


def test_sanitized_reports_whether_redaction_ran_not_whether_it_changed(
    ledger_home, monkeypatch
):
    """A record with sanitized: true and equal digests was inspected and
    left alone — the flag is about the pass running, not about a rewrite."""
    from core.evals import sanitizer

    monkeypatch.setattr(sanitizer, "sanitize_text", lambda text: (text, {}))
    record = reviewer_ledger.record_reviewer_output(
        "sess-noop", "francisca-tech", _reviewer_output(), "subagent-stop"
    )
    assert record["sanitized"] is True, "redaction ran"
    assert record["stored_sha256"] == record["raw_sha256"], (
        "and changed nothing, so the digests agree"
    )


class TestUnpinnedInvariants:
    """Round-6 pins: three guards Francisca's independent set proved
    deletable with the suite green, plus the capture-failure telemetry
    introduced in the same commit to close her B5. Each mutation was
    applied and re-run before the pin was written."""

    def test_reviewer_identities_are_not_interchangeable(self, ledger_home):
        """Fusing the two alias groups makes Eduardo and Francisca one
        person, so either could be filed under the other's name."""
        eduardo_verdict = _reviewer_output(
            dict(VERDICT_BODY, reviewer="copy-director-eduardo")
        )
        record = reviewer_ledger.record_reviewer_output(
            "sess-ident", "francisca-tech", eduardo_verdict, "subagent-stop"
        )
        assert record["verdict"] is None, (
            "Eduardo's verdict must never be filed as Francisca's"
        )
        assert "none authored by francisca-tech" in record["parse_error"]
        assert "copy-director-eduardo" in record["parse_error"]

    def test_retention_default_is_the_value_production_uses(self, ledger_home):
        """session_end calls sweep_expired() with NO argument, so the
        default is the only window that ever runs in production; every
        test passing days= explicitly left it unpinned."""
        import time

        reviewer_ledger.record_reviewer_output(
            "sess-89", "francisca-tech", _reviewer_output(), "subagent-stop"
        )
        reviewer_ledger.record_reviewer_output(
            "sess-91", "francisca-tech",
            _reviewer_output(dict(VERDICT_BODY, notes="older")),
            "subagent-stop",
        )
        root = reviewer_ledger.ledger_root()
        for name, age in (("sess-89", 89), ("sess-91", 91)):
            when = time.time() - (age * 86400)
            os.utime(root / name, (when, when))

        assert reviewer_ledger.sweep_expired() == 1, "the default is 90 days"
        assert (root / "sess-89").is_dir(), "89 days old: inside the window"
        assert not (root / "sess-91").exists(), "91 days old: expired"

    def test_a_fence_without_a_verdict_key_is_not_a_verdict(self, ledger_home):
        """Relaxing the rule to 'is it a dict' would let any JSON block a
        reviewer happens to quote become their verdict."""
        raw = (
            "Here is the evidence report I read:\n\n```json\n"
            + json.dumps({"overall": "pass", "checks_ran": ["lint"]})
            + "\n```\n"
        )
        record = reviewer_ledger.record_reviewer_output(
            "sess-nokey", "francisca-tech", raw, "subagent-stop"
        )
        assert record["verdict"] is None
        assert "carries no 'verdict' key" in record["parse_error"]

    def test_a_failed_capture_is_never_silent(self, ledger_home, monkeypatch):
        """The outer except returns None on any failure; without a
        telemetry line the operator is simply never told a verdict
        existed."""
        def _boom(*_a, **_k):
            raise RuntimeError("disk on fire")

        monkeypatch.setattr(reviewer_ledger, "_capture", _boom)
        assert reviewer_ledger.record_reviewer_output(
            "sess-boom", "francisca-tech", _reviewer_output(), "subagent-stop"
        ) is None

        log = ledger_home / ".arkaos" / "telemetry" / "reviewer-ledger.jsonl"
        assert log.is_file(), "a total capture failure must leave a trace"
        entry = json.loads(log.read_text(encoding="utf-8").splitlines()[-1])
        assert entry["event"] == "capture-failed"
        assert entry["reviewer_id"] == "francisca-tech"
        assert "disk on fire" in entry["error"]


class TestBalancedFenceExtraction:
    """QG r13 production incident: francisca-tech-17's notes STRING
    contained a literal fence pair, the first-close cut ended the JSON
    mid-string ("Unterminated string"), and a completed verdict lost
    its structured columns. Balanced extraction recovers it."""

    def _verdict(self, notes: str) -> dict:
        return {
            "verdict": "REJECTED",
            "evidence_report": {"overall": "fail"},
            "reviewer": "francisca-tech",
            "model_used": "opus",
            "notes": notes,
        }

    def test_fences_inside_a_json_string_still_parse(self):
        import json as _json

        notes = "probes: ```json vs ```arka-qgverdict fences, hex sweep"
        raw = (
            "review text\n```arka-qgverdict\n"
            + _json.dumps(self._verdict(notes), indent=2)
            + "\n```\ntrailing prose"
        )
        verdict, error = reviewer_ledger._extract_verdict(
            raw, "francisca-tech"
        )
        assert error is None
        assert verdict is not None and verdict["notes"] == notes

    def test_unparseable_fence_keeps_first_close_error(self):
        raw = "text\n```arka-qgverdict\n{broken json\n```\ntail"
        verdict, error = reviewer_ledger._extract_verdict(
            raw, "francisca-tech"
        )
        assert verdict is None
        assert error and "json:" in error

    def test_unterminated_fence_yields_no_body_and_a_parse_error(self):
        """Master pinned ``error is None`` here, the behaviour behind the
        #568 stale read: a record with neither a verdict nor an error was skipped by
        the guard (QG round 2, Eduardo M1)."""
        raw = "text\n```arka-qgverdict\n{\"verdict\": \"REJECTED\""
        verdict, error = reviewer_ledger._extract_verdict(
            raw, "francisca-tech"
        )
        assert verdict is None
        assert error == "unterminated arka-qgverdict fence"


class TestRejectedDigestsNeverHarvested:
    """QG r12: _validated is fail-soft (raw text is never lost), but a
    value the validator REJECTED must not enter the corpus through the
    harvested digest columns."""

    def test_rejected_tree_digest_not_harvested(self, tmp_path, monkeypatch):
        import json

        monkeypatch.setenv("HOME", str(tmp_path))
        from core.governance import reviewer_ledger

        verdict = {
            "verdict": "REJECTED",
            "evidence_report": {"overall": "fail"},
            "reviewer": "francisca-tech",
            "model_used": "opus",
            "tree_digest": "a" * 64,  # RESERVED — validator rejects it
            # Non-hex value on the OTHER guarded column too: without it,
            # the evidence_digest assertion below is vacuous (.get() on a
            # missing key is None with or without the guard) — QG r13.
            "evidence_digest": "NOT-A-DIGEST",
        }
        raw = (
            "review text\n```arka-qgverdict\n"
            + json.dumps(verdict) + "\n```\n"
        )
        record = reviewer_ledger.record_reviewer_output(
            session_id="r12-harvest", reviewer_id="francisca-tech",
            raw_output=raw, source="post-tool-use",
        )
        assert record is not None
        assert record["parse_error"]  # rejection is on record
        assert record["tree_digest"] is None  # but never harvested
        assert record["evidence_digest"] is None
        # The raw text itself is preserved — fail-soft, not fail-lossy.
        assert "a" * 64 in record["raw_output"]


def test_prescreen_name_is_in_the_contract_and_retention_keeps_working(ledger_home):
    """JEV PR3: qg_prescreen writes PRESCREEN.json beside the verdicts. An
    unowned name would make _purge refuse the dir (retention a no-op);
    it must also never pass as a reviewer record."""
    import time

    assert reviewer_ledger.PRESCREEN_NAME == "PRESCREEN.json"
    assert not reviewer_ledger._RECORD_NAME_RE.fullmatch(reviewer_ledger.PRESCREEN_NAME)
    reviewer_ledger.record_reviewer_output(
        "sess-prescreen", "francisca-tech", _reviewer_output(), "subagent-stop"
    )
    session_dir = reviewer_ledger.ledger_root() / "sess-prescreen"
    prescreen = session_dir / reviewer_ledger.PRESCREEN_NAME
    prescreen.write_text('{"verdict": "approved"}', encoding="utf-8")
    assert reviewer_ledger._is_own_file(prescreen)
    ancient = time.time() - (100 * 86400)
    os.utime(session_dir, (ancient, ancient))
    assert reviewer_ledger.sweep_expired(days=90) == 1
    assert not session_dir.exists()


# ─── Issue #568: fence recovery from the reviewer's own transcript ────────

FIXTURE = Path(__file__).parent / "fixtures" / "reviewer_transcript_post_handback.jsonl"
PROSE = "Handback delivered. The verdict is in the report above."


def _assistant(block: dict) -> str:
    return json.dumps({"type": "assistant", "isSidechain": True,
                       "message": {"role": "assistant", "content": [block]}})


def _write_transcript(tmp_path: Path, lines: list[str], name: str = "t.jsonl") -> str:
    path = tmp_path / name
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)


def _handback(text: str) -> str:
    return _assistant({"type": "tool_use", "id": "toolu_x", "name": "SubagentHandback",
                       "input": {"message": text}})


def _text(text: str) -> str:
    return _assistant({"type": "text", "text": text})


class TestFenceRecovery:
    def test_fixture_pins_the_real_transcript_shape(self):
        """The shape read from a round-7 reviewer transcript: the fence
        rides in tool_use(SubagentHandback).input.message and the final
        assistant text is prose without it."""
        lines = [json.loads(line) for line in FIXTURE.read_text().splitlines()]
        handback = [
            block for rec in lines if rec.get("type") == "assistant"
            for block in rec["message"]["content"]
            if block.get("type") == "tool_use"
        ]
        assert [b["name"] for b in handback] == ["SubagentHandback"]
        assert "```arka-qgverdict" in handback[0]["input"]["message"]
        final = lines[-1]["message"]["content"][-1]
        assert final["type"] == "text" and "arka-qgverdict" not in final["text"]

    def test_last_message_fence_is_unchanged(self, ledger_home, tmp_path):
        raw = _reviewer_output()
        approved = {**VERDICT_BODY, "verdict": "APPROVED", "blockers": []}
        transcript = _write_transcript(
            tmp_path, [_handback(_reviewer_output(approved))]
        )
        record = reviewer_ledger.record_reviewer_output(
            "sess-568a", "francisca-tech", raw, "subagent-stop", transcript
        )
        assert record["raw_output"] == raw
        assert record["verdict"]["verdict"] == "REJECTED"
        assert record["fence_source"] == "last_message"
        assert record["capture_error"] is None

    def test_prose_after_handback_recovers_the_handback_fence(self, ledger_home):
        record = reviewer_ledger.record_reviewer_output(
            "sess-568b", "eduardo-copy", PROSE, "subagent-stop", str(FIXTURE)
        )
        assert record["verdict"]["verdict"] == "REJECTED"
        assert record["fence_source"] == "transcript_handback"
        assert record["capture_error"] is None
        assert record["raw_output"].startswith("Copy review, round 7.")
        assert "```arka-qgverdict" in record["raw_output"]

    def test_fence_in_an_earlier_assistant_block(self, ledger_home, tmp_path):
        fenced = _reviewer_output()
        transcript = _write_transcript(tmp_path, [
            _handback("an older handback, no fence"), _text(fenced), _text(PROSE),
        ])
        record = reviewer_ledger.record_reviewer_output(
            "sess-568c", "francisca-tech", PROSE, "subagent-stop", transcript
        )
        assert record["fence_source"] == "transcript_assistant"
        assert record["raw_output"] == fenced
        assert record["raw_sha256"] == __import__("hashlib").sha256(
            fenced.encode("utf-8")).hexdigest()

    def test_the_last_fence_wins_across_blocks(self, ledger_home, tmp_path):
        older = _reviewer_output({**VERDICT_BODY, "verdict": "APPROVED", "blockers": []})
        transcript = _write_transcript(tmp_path, [
            _text(older), _handback(_reviewer_output()), _text(PROSE),
        ])
        record = reviewer_ledger.record_reviewer_output(
            "sess-568d", "francisca-tech", PROSE, "subagent-stop", transcript
        )
        assert record["fence_source"] == "transcript_handback"
        assert record["verdict"]["verdict"] == "REJECTED"

    def test_no_fence_anywhere_is_filed_with_capture_error(self, ledger_home, tmp_path):
        transcript = _write_transcript(tmp_path, [_handback("no fence"), _text(PROSE)])
        record = reviewer_ledger.record_reviewer_output(
            "sess-568e", "eduardo-copy", PROSE, "subagent-stop", transcript
        )
        assert record is not None, "a fenceless capture is still audited"
        assert record["verdict"] is None
        assert record["capture_error"] == "no-fence"
        assert record["fence_source"] is None
        assert record["raw_output"] == PROSE
        assert Path(record["path"]).is_file()

    def test_no_transcript_means_no_fence(self, ledger_home):
        record = reviewer_ledger.record_reviewer_output(
            "sess-568f", "eduardo-copy", PROSE, "post-tool-use"
        )
        assert record["capture_error"] == "no-fence"

    def test_broken_fence_keeps_the_parse_error_path(self, ledger_home, tmp_path):
        broken = "Review.\n\n```arka-qgverdict\n{bad json,,}\n```\n"
        transcript = _write_transcript(tmp_path, [_handback(_reviewer_output())])
        record = reviewer_ledger.record_reviewer_output(
            "sess-568g", "eduardo-copy", broken, "subagent-stop", transcript
        )
        assert record["raw_output"] == broken
        assert record["parse_error"]
        assert record["capture_error"] is None
        assert record["fence_source"] == "last_message"

    def test_a_transcript_larger_than_the_tail_bound_finds_a_fence_inside_it(
        self, ledger_home, tmp_path, monkeypatch
    ):
        from core.governance import fence_recovery

        monkeypatch.setattr(fence_recovery, "TAIL_BYTES", 4096)
        filler = [_text("x" * 200) for _ in range(200)]  # ~62 KiB of prose
        transcript = _write_transcript(
            tmp_path, [*filler, _handback(_reviewer_output()), _text(PROSE)]
        )
        assert Path(transcript).stat().st_size > 10 * 4096
        record = reviewer_ledger.record_reviewer_output(
            "sess-568h", "francisca-tech", PROSE, "subagent-stop", transcript
        )
        assert record["fence_source"] == "transcript_handback"

    def test_a_fence_outside_the_tail_bound_is_not_read(self, tmp_path):
        from core.governance import fence_recovery

        transcript = _write_transcript(
            tmp_path, [_handback(_reviewer_output())] + [_text("y" * 200)] * 50
        )
        assert fence_recovery.recover_fence(transcript, max_bytes=2048) is None
        assert fence_recovery.recover_fence(transcript)[1] == "transcript_handback"

    def test_malformed_lines_are_skipped(self, ledger_home, tmp_path):
        transcript = _write_transcript(tmp_path, [
            _handback(_reviewer_output()), "{not json", '"a string"', "[1, 2]",
            json.dumps({"type": "assistant", "message": "odd"}),
            json.dumps({"type": "assistant", "message": {"content": ["x", None]}}),
            _text(PROSE)[:-5],
        ])
        record = reviewer_ledger.record_reviewer_output(
            "sess-568i", "francisca-tech", PROSE, "subagent-stop", transcript
        )
        assert record["fence_source"] == "transcript_handback"

    def test_other_tools_input_is_not_a_handback(self, tmp_path):
        from core.governance import fence_recovery

        transcript = _write_transcript(tmp_path, [_assistant({
            "type": "tool_use", "name": "Write",
            "input": {"message": _reviewer_output()}})])
        assert fence_recovery.recover_fence(transcript) is None

    def test_unreadable_transcript_never_raises(self, ledger_home, tmp_path):
        record = reviewer_ledger.record_reviewer_output(
            "sess-568j", "eduardo-copy", PROSE, "subagent-stop",
            str(tmp_path / "missing.jsonl"),
        )
        assert record["capture_error"] == "no-fence"

    def test_notice_names_the_missing_verdict(self, ledger_home):
        record = reviewer_ledger.record_reviewer_output(
            "sess-568k", "eduardo-copy", PROSE, "subagent-stop"
        )
        reviewer_ledger.queue_notice("sess-568k", record, "")
        context = reviewer_ledger.notices_context("sess-568k")
        assert "verdict-unparsed" in context
        assert "the gate treats eduardo-copy as missing: re-dispatch it" in context
        assert "re-issue" not in context


def _prompt(content: object, **extra: object) -> str:
    return json.dumps({"type": "user", "isSidechain": True,
                       "message": {"role": "user", "content": content}, **extra})


def _tool_result() -> str:
    return _prompt([{"type": "tool_result", "tool_use_id": "toolu_x",
                     "content": "ok"}])


APPROVED_BODY = {**VERDICT_BODY, "verdict": "APPROVED", "blockers": []}


class TestTurnBoundary:
    """A resumed reviewer appends its next round to the same transcript:
    only the current turn may supply the fence (QG round 1, M1)."""

    def test_a_resumed_round_ending_in_prose_is_no_fence(self, ledger_home, tmp_path):
        transcript = _write_transcript(tmp_path, [
            _prompt("review round 1"), _handback(_reviewer_output(APPROVED_BODY)),
            _tool_result(), _prompt("round 2: your blockers are fixed, re-judge"),
            _text("REJECTED: two findings remain."),
        ])
        record = reviewer_ledger.record_reviewer_output(
            "sess-568t", "francisca-tech", "REJECTED: two findings remain.",
            "subagent-stop", transcript,
        )
        assert record["capture_error"] == "no-fence"
        assert record["verdict"] is None
        assert record["raw_output"] == "REJECTED: two findings remain."

    def test_the_current_turn_fence_wins_over_the_previous_turn(self, tmp_path):
        from core.governance import fence_recovery

        current = _reviewer_output()
        transcript = _write_transcript(tmp_path, [
            _prompt("review round 1"), _handback(_reviewer_output(APPROVED_BODY)),
            _prompt("round 2"), _handback(current), _tool_result(), _text(PROSE),
        ])
        assert fence_recovery.recover_fence(transcript) == (
            current, "transcript_handback"
        ), "a tool_result is not a turn boundary"

    def test_a_list_prompt_and_a_mid_turn_meta_message_are_boundaries(self, tmp_path):
        from core.governance import fence_recovery

        for boundary in (
            _prompt([{"type": "text", "text": "round 2"}]),
            _prompt("The coordinator sent a message while you were working",
                    isMeta=True),
        ):
            transcript = _write_transcript(tmp_path, [
                _handback(_reviewer_output()), boundary, _text(PROSE),
            ])
            assert fence_recovery.recover_fence(transcript) is None


class TestTailAndLineRules:
    """Round-1 minors on fence_recovery: tail cut, per-line errors,
    block order, line splitting and the compatibility fence."""

    def test_a_cut_on_a_newline_keeps_the_first_complete_line(self, tmp_path):
        from core.governance import fence_recovery

        fenced, prose = _handback(_reviewer_output()), _text(PROSE)
        transcript = _write_transcript(tmp_path, ["A" * 50, fenced, prose])
        bound = len(fenced) + 1 + len(prose) + 1  # starts right after "A…\n"
        assert fence_recovery.recover_fence(transcript, bound) == (
            _reviewer_output(), "transcript_handback"
        )

    def test_a_mid_line_cut_drops_the_fragment_even_when_it_parses(self, tmp_path):
        """The bytes after a mid-line cut are never trusted as a record,
        even when they happen to form a valid, fenced one."""
        from core.governance import fence_recovery

        fenced, prose = _handback(_reviewer_output()), _text(PROSE)
        path = tmp_path / "cut.jsonl"
        # The byte before the window is a space, so the dropped segment
        # (" " + fenced) is itself valid JSON: only the cut rule drops it.
        path.write_text("X" * 50 + " " + fenced + "\n" + prose + "\n",
                        encoding="utf-8")
        bound = len(fenced) + 1 + len(prose) + 1
        assert fence_recovery.recover_fence(str(path), bound) is None

    def test_a_huge_int_or_deeply_nested_line_is_skipped(self, tmp_path):
        from core.governance import fence_recovery

        transcript = _write_transcript(tmp_path, [
            _handback(_reviewer_output()),
            '{"n": ' + "9" * 5000 + "}",  # ValueError, not JSONDecodeError
            "[" * 200_000,  # RecursionError
            _text(PROSE),
        ])
        assert fence_recovery.recover_fence(transcript)[1] == "transcript_handback"

    def test_in_one_record_the_last_fenced_block_wins(self, ledger_home, tmp_path):
        both = json.dumps({"type": "assistant", "message": {"role": "assistant",
            "content": [{"type": "text", "text": _reviewer_output(APPROVED_BODY)},
                        {"type": "tool_use", "name": "SubagentHandback",
                         "input": {"message": _reviewer_output()}}]}})
        transcript = _write_transcript(tmp_path, [both, _text(PROSE)])
        record = reviewer_ledger.record_reviewer_output(
            "sess-568o", "francisca-tech", PROSE, "subagent-stop", transcript
        )
        assert record["fence_source"] == "transcript_handback"
        assert record["verdict"]["verdict"] == "REJECTED"

    def test_unicode_line_separators_do_not_split_a_record(self, tmp_path):
        from core.governance import fence_recovery

        message = "Report \u2028 line \u2029 para \u0085 next.\n" + _reviewer_output()
        line = json.dumps({"type": "assistant", "message": {"role": "assistant",
            "content": [{"type": "tool_use", "name": "SubagentHandback",
                         "input": {"message": message}}]}}, ensure_ascii=False)
        assert "\u2028" in line
        transcript = _write_transcript(tmp_path, [line, _text(PROSE)])
        assert fence_recovery.recover_fence(transcript) == (
            message, "transcript_handback"
        )

    def test_the_compatibility_json_fence_is_recovered(self, ledger_home, tmp_path):
        legacy = "Review.\n```json\n" + json.dumps(VERDICT_BODY) + "\n```\n"
        transcript = _write_transcript(tmp_path, [_handback(legacy), _text(PROSE)])
        record = reviewer_ledger.record_reviewer_output(
            "sess-568j2", "francisca-tech", PROSE, "subagent-stop", transcript
        )
        assert record["fence_source"] == "transcript_handback"
        assert record["verdict"]["verdict"] == "REJECTED"

    def test_a_json_fence_without_a_verdict_is_not_a_verdict(self, ledger_home, tmp_path):
        example = "Config:\n```json\n{\"a\": 1}\n```\n"
        transcript = _write_transcript(tmp_path, [
            _handback(_reviewer_output()), _text(example),
        ])
        record = reviewer_ledger.record_reviewer_output(
            "sess-568j3", "francisca-tech", example, "subagent-stop", transcript
        )
        assert record["fence_source"] == "transcript_handback"
        assert record["raw_output"] == _reviewer_output()


class TestEmptyPromptBoundary:
    def test_an_empty_content_list_prompt_ends_the_scan(self, tmp_path):
        """A user record whose content is an EMPTY list carries no
        tool_result, so it opens a turn (QG round 2, Francisca m1)."""
        from core.governance import fence_recovery

        transcript = _write_transcript(tmp_path, [
            _handback(_reviewer_output()), _prompt([]), _text(PROSE),
        ])
        assert fence_recovery.recover_fence(transcript) is None


def _dir_records(session_id: str) -> list[dict]:
    session_dir = reviewer_ledger.ledger_root() / session_id
    return sorted(
        (json.loads(p.read_text(encoding="utf-8"))
         for p in session_dir.glob("*-*-*.json")),
        key=lambda rec: rec["seq"],
    )


class TestLatestOnlyDedup:
    """QG round 2, B1: dedup against ANY prior record deadlocked the gate."""

    def test_verdict_resent_after_a_fenceless_capture_is_a_new_record(
        self, ledger_home
    ):
        fenced = _reviewer_output()
        capture = reviewer_ledger.record_reviewer_output
        first = capture("sess-b1", "francisca-tech", fenced, "subagent-stop")
        prose = capture("sess-b1", "francisca-tech", PROSE, "subagent-stop")
        again = capture("sess-b1", "francisca-tech", fenced, "subagent-stop")
        assert (first["seq"], prose["seq"], again["seq"]) == (1, 2, 3)
        assert prose["capture_error"] == "no-fence"
        assert again["verdict"]["verdict"] == "REJECTED"
        assert again["raw_sha256"] == first["raw_sha256"]
        assert [r["seq"] for r in _dir_records("sess-b1")] == [1, 2, 3]

    def test_the_same_text_right_after_itself_is_adopted(self, ledger_home):
        fenced = _reviewer_output()
        capture = reviewer_ledger.record_reviewer_output
        capture("sess-b1b", "francisca-tech", PROSE, "subagent-stop")
        second = capture("sess-b1b", "francisca-tech", fenced, "post-tool-use")
        third = capture("sess-b1b", "francisca-tech", fenced, "subagent-stop")
        assert third["seq"] == second["seq"] == 2
        assert third["source"] == "post-tool-use"
        assert len(_dir_records("sess-b1b")) == 2

    def test_latest_is_the_highest_seq_not_the_last_name(self, ledger_home):
        """seq 10 sorts before seq 9 by name: latest is numeric."""
        capture = reviewer_ledger.record_reviewer_output
        for n in range(1, 10):
            capture("sess-b1c", "francisca-tech", f"prose {n}", "subagent-stop")
        tenth = capture("sess-b1c", "francisca-tech", _reviewer_output(),
                        "subagent-stop")
        again = capture("sess-b1c", "francisca-tech", _reviewer_output(),
                        "post-tool-use")
        assert tenth["seq"] == 10
        assert again["seq"] == 10 and again["source"] == "subagent-stop"
        assert len(_dir_records("sess-b1c")) == 10

    def test_a_stray_dashed_name_never_breaks_the_seq_read(self, ledger_home):
        """``_records_for`` admits ``<id>-<digits>-…``; the seq read must
        parse every name it admits, or the capture is lost."""
        capture = reviewer_ledger.record_reviewer_output
        capture("sess-b1d", "francisca-tech", PROSE, "subagent-stop")
        session_dir = reviewer_ledger.ledger_root() / "sess-b1d"
        (session_dir / "francisca-tech-1-x-y.json").write_text("{}", encoding="utf-8")
        record = capture("sess-b1d", "francisca-tech", _reviewer_output(),
                         "subagent-stop")
        assert record is not None and record["verdict"]["verdict"] == "REJECTED"



class TestRoundThreeFixForward:
    """QG round 3 minors, fixed forward by the CQO."""

    def test_a_non_ascii_digit_name_never_drops_a_capture(self, ledger_home):
        """``str.isdigit`` admits a superscript two that ``int`` rejects:
        the stray name crashed every capture and the guard read the
        previous round (Francisca r3 m1)."""
        capture = reviewer_ledger.record_reviewer_output
        capture("sess-r3a", "francisca-tech", PROSE, "subagent-stop")
        session_dir = reviewer_ledger.ledger_root() / "sess-r3a"
        (session_dir / "francisca-tech-\u00b2-bbbbbbbb.json").write_text(
            "{}", encoding="utf-8")
        record = capture("sess-r3a", "francisca-tech", _reviewer_output(),
                         "subagent-stop")
        assert record is not None and record["seq"] == 2

    def test_a_shared_top_seq_is_never_adopted(self, ledger_home):
        """Two divergent texts at the top seq: re-sending either one is
        filed at the next seq, so it is the unambiguous latest
        (Francisca r3 m2)."""
        capture = reviewer_ledger.record_reviewer_output
        fenced = _reviewer_output()
        capture("sess-r3b", "francisca-tech", fenced, "subagent-stop")
        session_dir = reviewer_ledger.ledger_root() / "sess-r3b"
        twin = json.loads((session_dir / next(
            p.name for p in session_dir.glob("francisca-tech-1-*.json")
        )).read_text(encoding="utf-8"))
        twin.update({"raw_output": PROSE, "raw_sha256": "f" * 64,
                     "stored_sha256": "f" * 64, "verdict": None,
                     "capture_error": "no-fence"})
        (session_dir / "francisca-tech-1-ffffffff.json").write_text(
            json.dumps(twin), encoding="utf-8")
        again = capture("sess-r3b", "francisca-tech", fenced, "subagent-stop")
        assert again["seq"] == 3
        assert again["verdict"]["verdict"] == "REJECTED"

    def test_a_verdict_beside_a_parse_error_renders_unparsed(self, ledger_home):
        """A closed fence before a cut one keeps its verdict for audit, but
        the guard treats the reviewer as missing: the notice headline
        must say so, not print the earlier verdict (Francisca r3 m3)."""
        closed = _reviewer_output()
        record = reviewer_ledger.record_reviewer_output(
            "sess-r3c", "francisca-tech", closed + "\n" + _cut(), "subagent-stop")
        assert record["verdict"] is not None and record["parse_error"]
        reviewer_ledger.queue_notice("sess-r3c", record, "")
        context = reviewer_ledger.notices_context("sess-r3c")
        assert "francisca-tech verdict-unparsed" in context
        assert "francisca-tech REJECTED" not in context


UNTERMINATED = "unterminated arka-qgverdict fence"


def _cut(body: dict | None = None) -> str:
    """A reply cut after the opener and body, before the closing fence."""
    payload = json.dumps(body if body is not None else VERDICT_BODY, indent=2)
    return f"Round 2.\n\n```arka-qgverdict\n{payload}\n"


class TestUnterminatedFence:
    """QG round 2, Eduardo M1: an opener with no close is a broken fence."""

    def test_last_message_opener_without_close_is_a_parse_error(self, ledger_home):
        record = reviewer_ledger.record_reviewer_output(
            "sess-ut", "francisca-tech", _cut(), "subagent-stop"
        )
        assert record["verdict"] is None
        assert record["parse_error"] == UNTERMINATED
        assert record["capture_error"] is None
        assert record["fence_source"] == "last_message"

    def test_transcript_opener_without_close_is_a_parse_error(
        self, ledger_home, tmp_path
    ):
        transcript = _write_transcript(tmp_path, [_handback(_cut()), _text(PROSE)])
        record = reviewer_ledger.record_reviewer_output(
            "sess-ut2", "francisca-tech", PROSE, "subagent-stop", transcript
        )
        assert record["fence_source"] == "transcript_handback"
        assert record["verdict"] is None
        assert record["parse_error"] == UNTERMINATED

    def test_a_cut_fence_after_a_closed_one_still_breaks_the_record(
        self, ledger_home
    ):
        """The closed fence may be a quoted earlier round: the cut one
        that follows it keeps the record out of the quorum."""
        text = _reviewer_output(APPROVED_BODY) + _cut()
        record = reviewer_ledger.record_reviewer_output(
            "sess-ut3", "francisca-tech", text, "subagent-stop"
        )
        assert record["parse_error"].startswith(UNTERMINATED)

    def test_an_unterminated_opener_is_not_rescued_by_a_json_fence(
        self, ledger_home
    ):
        legacy = "```json\n" + json.dumps(APPROVED_BODY) + "\n```\n"
        record = reviewer_ledger.record_reviewer_output(
            "sess-ut4", "francisca-tech", legacy + _cut(), "subagent-stop"
        )
        assert record["verdict"] is None
        assert record["parse_error"] == UNTERMINATED

    def test_unterminated_compatibility_json_fence_is_a_parse_error(
        self, ledger_home
    ):
        cut = "Review.\n```json\n" + json.dumps(VERDICT_BODY) + "\n"
        record = reviewer_ledger.record_reviewer_output(
            "sess-ut5", "francisca-tech", cut, "subagent-stop"
        )
        assert record["verdict"] is None
        assert record["parse_error"] == "unterminated json fence"
        assert record["capture_error"] == "no-fence"

    def test_a_closed_fence_carries_no_unterminated_error(self, ledger_home):
        record = reviewer_ledger.record_reviewer_output(
            "sess-ut6", "francisca-tech", _reviewer_output(), "subagent-stop"
        )
        assert record["parse_error"] is None
        assert record["verdict"]["verdict"] == "REJECTED"
