"""PR-B5 (G7): the Stop-hook QG sweep reads the guard-accepted aggregate.

Before this PR `_auto_doc_enqueue` decided "QG approved" from
``~/.arkaos/telemetry/qg.jsonl`` — an unguarded log any writer can
append to — while the aggregate that actually passed
``aggregate_guard.check_aggregate`` sat unread in the session ledger.
The sweep order is now: marker → AGGREGATE.json → telemetry fallback,
and a present aggregate is authoritative in BOTH directions.
"""

from __future__ import annotations

import json
from pathlib import Path

from core.hooks import stop


def _write_aggregate(
    home: Path,
    session_id: str,
    verdict: str = "APPROVED",
    record_session: str | None = None,
    body: str | None = None,
) -> None:
    session_dir = home / ".arkaos" / "quality-gate" / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    text = (
        body
        if body is not None
        else json.dumps(
            {
                "session_id": record_session or session_id,
                "aggregate": {"verdict": verdict},
            }
        )
    )
    (session_dir / "AGGREGATE.json").write_text(text, encoding="utf-8")


def _write_telemetry(
    home: Path, session_id: str, verdict: str = "APPROVED"
) -> None:
    telemetry = home / ".arkaos" / "telemetry"
    telemetry.mkdir(parents=True, exist_ok=True)
    (telemetry / "qg.jsonl").write_text(
        json.dumps({"session_id": session_id, "verdict": verdict}) + "\n",
        encoding="utf-8",
    )


class TestAggregateVerdict:
    def test_approved_aggregate_is_true(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        _write_aggregate(tmp_path, "sess-agg-a")
        assert stop._qg_aggregate_verdict("sess-agg-a") is True

    def test_rejected_aggregate_is_false_not_none(self, monkeypatch, tmp_path):
        """False, not None: a present aggregate must SUPPRESS the
        fallback — None would hand the decision back to telemetry."""
        monkeypatch.setenv("HOME", str(tmp_path))
        _write_aggregate(tmp_path, "sess-agg-r", verdict="REJECTED")
        assert stop._qg_aggregate_verdict("sess-agg-r") is False

    def test_missing_aggregate_is_none(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        assert stop._qg_aggregate_verdict("sess-agg-none") is None

    def test_malformed_aggregate_is_none(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        _write_aggregate(tmp_path, "sess-agg-bad", body="{not json")
        assert stop._qg_aggregate_verdict("sess-agg-bad") is None

    def test_non_dict_aggregate_is_none(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        _write_aggregate(tmp_path, "sess-agg-list", body='["a", "b"]')
        assert stop._qg_aggregate_verdict("sess-agg-list") is None

    def test_foreign_session_record_is_none(self, monkeypatch, tmp_path):
        """A record whose session_id disagrees with the directory it
        sits in proves nothing about THIS session — fall back."""
        monkeypatch.setenv("HOME", str(tmp_path))
        _write_aggregate(
            tmp_path, "sess-agg-f", record_session="sess-other"
        )
        assert stop._qg_aggregate_verdict("sess-agg-f") is None

    def test_hostile_session_id_is_none(self, monkeypatch, tmp_path):
        """_safe_id gates the path build: a traversal id never reaches
        the filesystem, mirroring the ledger's own rule."""
        monkeypatch.setenv("HOME", str(tmp_path))
        assert stop._qg_aggregate_verdict("../../etc/passwd") is None
        assert stop._qg_aggregate_verdict(".quarantine") is None
        assert stop._qg_aggregate_verdict("") is None

    def test_traversal_to_a_real_aggregate_is_still_refused(
        self, monkeypatch, tmp_path
    ):
        """The case that distinguishes the _safe_id guard from the
        except-fallback: a traversal id that RESOLVES to a valid
        aggregate on disk, whose record even names the traversal id —
        so neither the read nor the foreign-session check refuses it.
        Only the guard does, and this pin kills the guard-removal
        mutant."""
        monkeypatch.setenv("HOME", str(tmp_path))
        traversal = "x/../sess-real"
        _write_aggregate(tmp_path, "sess-real", record_session=traversal)
        # The traversed-through component must EXIST: the kernel resolves
        # "x/.." only after resolving "x", so without this mkdir the read
        # ENOENTs and the except-path would mask a removed guard.
        (tmp_path / ".arkaos" / "quality-gate" / "x").mkdir()
        assert stop._qg_aggregate_verdict(traversal) is None


class TestTelemetryFallback:
    def test_approved_telemetry_is_true(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        _write_telemetry(tmp_path, "sess-t1")
        assert stop._qg_telemetry_approved("sess-t1") is True

    def test_missing_log_is_false(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        assert stop._qg_telemetry_approved("sess-t2") is False

    def test_blank_malformed_and_foreign_lines_are_skipped(
        self, monkeypatch, tmp_path
    ):
        """Carried over from the pre-B5 inline loop: blank lines and
        unparseable lines are skipped, records of other sessions are
        ignored, and a log with no record for this session says False."""
        monkeypatch.setenv("HOME", str(tmp_path))
        telemetry = tmp_path / ".arkaos" / "telemetry"
        telemetry.mkdir(parents=True)
        (telemetry / "qg.jsonl").write_text(
            "\n{broken json\n"
            + json.dumps({"session_id": "sess-other", "verdict": "APPROVED"})
            + "\n",
            encoding="utf-8",
        )
        assert stop._qg_telemetry_approved("sess-t4") is False

    def test_unreadable_log_is_false(self, monkeypatch, tmp_path):
        """The outer except: qg.jsonl exists but cannot be read as a
        file (here: it is a directory)."""
        monkeypatch.setenv("HOME", str(tmp_path))
        (tmp_path / ".arkaos" / "telemetry" / "qg.jsonl").mkdir(parents=True)
        assert stop._qg_telemetry_approved("sess-t5") is False

    def test_newest_record_for_session_wins(self, monkeypatch, tmp_path):
        """Behaviour carried over verbatim from the pre-B5 inline loop:
        the log is scanned newest-first and the first record for this
        session decides."""
        monkeypatch.setenv("HOME", str(tmp_path))
        telemetry = tmp_path / ".arkaos" / "telemetry"
        telemetry.mkdir(parents=True)
        lines = [
            json.dumps({"session_id": "sess-t3", "verdict": "APPROVED"}),
            json.dumps({"session_id": "sess-t3", "verdict": "REJECTED"}),
        ]
        (telemetry / "qg.jsonl").write_text(
            "\n".join(lines) + "\n", encoding="utf-8"
        )
        assert stop._qg_telemetry_approved("sess-t3") is False


class TestSweepPrecedence:
    """The wiring inside _auto_doc_enqueue itself."""

    def _run(self, monkeypatch, tmp_path, session_id):
        calls: list = []
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setattr(
            "core.jobs.auto_doc_worker.enqueue_job",
            lambda *a, **k: calls.append(a),
        )
        monkeypatch.setattr(
            "core.workflow.flow_enforcer._load_last_assistant_messages",
            lambda *a, **k: ["no marker in this turn"],
        )
        stop._auto_doc_enqueue(
            session_id,
            str(tmp_path / "transcript.jsonl"),
            "evidence gathered via WebFetch",
        )
        return calls

    def test_rejected_aggregate_beats_stale_approved_telemetry(
        self, monkeypatch, tmp_path
    ):
        """AC2 — the exact laundering shape G7 closes: an unguarded
        telemetry APPROVED must not resurrect a guard-refused round."""
        _write_aggregate(tmp_path, "sess-prec", verdict="REJECTED")
        _write_telemetry(tmp_path, "sess-prec", verdict="APPROVED")
        assert self._run(monkeypatch, tmp_path, "sess-prec") == []

    def test_rejected_aggregate_beats_the_assistant_marker(
        self, monkeypatch, tmp_path
    ):
        """QG r1 M4 (Francisca): a literal [arka:qg:approved] in the
        last assistant message is narration — it must not outrank the
        guard-accepted REJECTED aggregate it narrates."""
        calls: list = []
        monkeypatch.setenv("HOME", str(tmp_path))
        _write_aggregate(tmp_path, "sess-mrk", verdict="REJECTED")
        monkeypatch.setattr(
            "core.jobs.auto_doc_worker.enqueue_job",
            lambda *a, **k: calls.append(a),
        )
        monkeypatch.setattr(
            "core.workflow.flow_enforcer._load_last_assistant_messages",
            lambda *a, **k: ["[arka:qg:approved] shipped!"],
        )
        stop._auto_doc_enqueue(
            "sess-mrk",
            str(tmp_path / "transcript.jsonl"),
            "evidence gathered via WebFetch",
        )
        assert calls == []

    def test_marker_still_works_when_no_aggregate_exists(
        self, monkeypatch, tmp_path
    ):
        """Fallback preserved: marker-only sessions (no aggregate on
        disk) keep their historical behaviour."""
        calls: list = []
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setattr(
            "core.jobs.auto_doc_worker.enqueue_job",
            lambda *a, **k: calls.append(a),
        )
        monkeypatch.setattr(
            "core.workflow.flow_enforcer._load_last_assistant_messages",
            lambda *a, **k: ["[arka:qg:approved] shipped!"],
        )
        stop._auto_doc_enqueue(
            "sess-mrk2",
            str(tmp_path / "transcript.jsonl"),
            "evidence gathered via WebFetch",
        )
        assert len(calls) == 1

    def test_approved_aggregate_enqueues_without_marker(
        self, monkeypatch, tmp_path
    ):
        _write_aggregate(tmp_path, "sess-prec-a")
        calls = self._run(monkeypatch, tmp_path, "sess-prec-a")
        assert len(calls) == 1
        assert calls[0][2] == "APPROVED"

    def test_absent_aggregate_falls_back_to_telemetry(
        self, monkeypatch, tmp_path
    ):
        _write_telemetry(tmp_path, "sess-prec-t", verdict="APPROVED")
        assert len(self._run(monkeypatch, tmp_path, "sess-prec-t")) == 1

    def test_nothing_on_disk_never_enqueues(self, monkeypatch, tmp_path):
        assert self._run(monkeypatch, tmp_path, "sess-prec-n") == []
