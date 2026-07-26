"""Reviewer ledger — the direct channel from QG reviewers to the operator.

The defect these tests pin: 81 corpus verdicts, 80 authored by the
aggregator, zero by a reviewer, and every persisted reviewer output on
disk was the 16-byte string ``<tool_use:Agent>`` (the parent's in-flight
turn, read from the wrong transcript scope). A reviewer's verdict must
land verbatim, hashed, from a surface the reviewer cannot fail to use.
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
