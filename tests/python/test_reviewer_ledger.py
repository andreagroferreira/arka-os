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

    def test_accepts_plain_json_fence(self, ledger_home):
        """Deployed reviewers emit ```json today — capture must not depend
        on them adopting the new fence before the channel works."""
        record = reviewer_ledger.record_reviewer_output(
            "sess-json", "eduardo-copy", _reviewer_output(fence="json"),
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


class TestReadback:
    def test_latest_verdicts_per_reviewer(self, ledger_home):
        reviewer_ledger.record_reviewer_output(
            "sess-9", "francisca-tech", _reviewer_output(), "post-tool-use"
        )
        reviewer_ledger.record_reviewer_output(
            "sess-9", "eduardo-copy",
            _reviewer_output(dict(VERDICT_BODY, reviewer="copy-director-eduardo")),
            "post-tool-use",
        )
        latest = reviewer_ledger.latest_verdicts("sess-9")
        assert set(latest) == {"francisca-tech", "eduardo-copy"}

    def test_empty_for_unknown_session(self, ledger_home):
        assert reviewer_ledger.latest_verdicts("nope") == {}

    def test_corrupt_file_is_skipped_not_raised(self, ledger_home):
        reviewer_ledger.record_reviewer_output(
            "sess-10", "francisca-tech", _reviewer_output(), "post-tool-use"
        )
        (reviewer_ledger.ledger_root() / "sess-10" / "junk.json").write_text(
            "{{{", encoding="utf-8"
        )
        assert set(reviewer_ledger.latest_verdicts("sess-10")) == {"francisca-tech"}


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
        assert "ambiguous: 2 verdict fences" in record["parse_error"]

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

    def test_latest_verdicts_past_nine_rounds(self, ledger_home):
        """Lexical filename order puts -10 before -2: a redo loop past
        nine rounds returned a stale verdict."""
        for i in range(11):
            reviewer_ledger.record_reviewer_output(
                "sess-many", "francisca-tech",
                _reviewer_output(dict(VERDICT_BODY, notes=f"round {i}")),
                "subagent-stop",
            )
        latest = reviewer_ledger.latest_verdicts("sess-many")
        assert latest["francisca-tech"]["seq"] == 11

    def test_dot_ids_are_rejected(self, ledger_home):
        """'.' and '..' match the safe-id charset and would resolve the
        ledger onto ~/.arkaos itself."""
        for bad in (".", ".."):
            assert reviewer_ledger.record_reviewer_output(
                bad, "francisca-tech", _reviewer_output(), "subagent-stop"
            ) is None
            assert reviewer_ledger.latest_verdicts(bad) == {}


class TestSweepSafety:
    def test_symlinked_session_dir_is_never_followed(self, ledger_home, tmp_path):
        import time

        victim = tmp_path / "victim"
        victim.mkdir()
        (victim / "important.txt").write_text("keep me", encoding="utf-8")
        reviewer_ledger.ledger_root().mkdir(parents=True, exist_ok=True)
        link = reviewer_ledger.ledger_root() / "linked-session"
        link.symlink_to(victim)
        ancient = time.time() - (100 * 86400)
        os.utime(victim, (ancient, ancient))

        reviewer_ledger.sweep_expired(days=90)
        assert (victim / "important.txt").is_file(), "sweep followed a symlink"
