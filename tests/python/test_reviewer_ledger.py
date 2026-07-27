"""Reviewer ledger — the direct channel from QG reviewers to the operator.

The defect these tests pin: of 81 corpus verdicts, 80 were authored by
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
        """Two sources disagreeing is a tamper signal, not an overwrite."""
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
        cannot collapse into one file even at the same seq."""
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

    def test_stored_digest_matches_the_file_on_disk(self, ledger_home):
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
        kept = quarantine / "fabricated-francisca-tech-1.json"
        kept.write_text("{}", encoding="utf-8")
        ancient = time.time() - (300 * 86400)
        os.utime(quarantine, (ancient, ancient))

        assert reviewer_ledger.sweep_expired(days=90) == 0
        assert kept.is_file(), "quarantined evidence must survive retention"

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
        # Force the collision path: the name exists, the dedup scan is
        # bypassed by removing nothing — a second writer at the same seq.
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
    A prefix match with a different body is a different verdict."""
    raw = _reviewer_output()
    record = reviewer_ledger.record_reviewer_output(
        "sess-collide", "francisca-tech", raw, "subagent-stop"
    )
    session_dir = reviewer_ledger.ledger_root() / "sess-collide"
    # Same 8-hex prefix in the name, a different full digest in the body.
    prefix = record["raw_sha256"][:8]
    impostor = session_dir / f"francisca-tech-9-{prefix}.json"
    impostor.write_text(
        json.dumps({"raw_sha256": "f" * 64, "raw_output": "someone else"}),
        encoding="utf-8",
    )
    again = reviewer_ledger.record_reviewer_output(
        "sess-collide", "francisca-tech", raw, "post-tool-use"
    )
    assert again["raw_sha256"] == record["raw_sha256"]
    assert again["raw_output"] == raw, "must not adopt the impostor's body"


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
