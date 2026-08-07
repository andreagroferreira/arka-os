"""Anti-self-approval guard (PR-B3): the 2026-07-20 incident, refused.

On 2026-07-20 an aggregate verdict entered the eval corpus with zero
reviewer artifacts behind it. Every test here builds a session ledger
on disk and asserts the guard's behaviour against it — the incident
reconstruction is the first test.
"""

from __future__ import annotations

import json

import pytest

from core.evals.record_cli import main as record_main
from core.evals.verdict_labels import load_verdict_labels
from core.governance import redo_counter
from core.governance.aggregate_guard import (
    AGGREGATE_NAME,
    GuardResult,
    check_aggregate,
    ledger_root,
    write_aggregate,
)

DIGEST_A = "a" * 64
DIGEST_B = "b" * 64


@pytest.fixture()
def guard_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv(
        "ARKA_QG_LABELS_PATH", str(tmp_path / "qg-verdicts.jsonl")
    )
    yield tmp_path


def _reviewer_verdict(
    reviewer: str = "francisca-tech",
    verdict: str = "APPROVED",
    blockers: list | None = None,
    # A well-shaped dispatch is the baseline since PR-B4 made the
    # digest mandatory; shape-specific tests pass "" explicitly.
    evidence_digest: str = DIGEST_A,
) -> dict:
    body = {
        "verdict": verdict,
        "evidence_report": {
            "overall": "pass" if verdict == "APPROVED" else "fail"
        },
        "reviewer": reviewer,
        "model_used": "opus",
        "blockers": blockers or [],
    }
    if evidence_digest:
        body["evidence_digest"] = evidence_digest
    return body


def _write_ledger_record(
    session_id: str,
    reviewer_id: str,
    seq: int = 1,
    source: str = "subagent-stop",
    parse_error: str | None = None,
    verdict: dict | None = None,
    name: str | None = None,
    ts: str = "",
) -> None:
    session_dir = ledger_root() / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "session_id": session_id,
        "reviewer_id": reviewer_id,
        "seq": seq,
        "ts": ts,
        "source": source,
        "parse_error": parse_error,
        "verdict": verdict if verdict is not None else _reviewer_verdict(
            reviewer=reviewer_id
        ),
        "raw_output": "captured review text",
    }
    file_name = name or f"{reviewer_id}-{seq}-{'0' * 8}.json"
    (session_dir / file_name).write_text(
        json.dumps(record), encoding="utf-8"
    )


def _aggregate(
    verdict: str = "APPROVED",
    blockers: list | None = None,
    evidence_digest: str = DIGEST_A,
) -> dict:
    body = {
        "verdict": verdict,
        "evidence_report": {
            "overall": "pass" if verdict == "APPROVED" else "fail"
        },
        "reviewer": "cqo-marta",
        "model_used": "opus",
        "blockers": blockers or [],
    }
    if evidence_digest:
        body["evidence_digest"] = evidence_digest
    return body


class TestQuorum:
    def test_2026_07_20_incident_refused(self, guard_home):
        """Zero reviewer artifacts: the incident shape is unrecordable."""
        result = check_aggregate(_aggregate(), "sess-incident")
        assert not result.ok
        assert "0 hook-captured reviewer verdict(s)" in result.reasons[0]

    def test_one_reviewer_is_not_a_quorum(self, guard_home):
        _write_ledger_record("sess-1", "francisca-tech")
        result = check_aggregate(_aggregate(), "sess-1")
        assert not result.ok
        assert "1 hook-captured reviewer verdict(s)" in result.reasons[0]

    def test_two_distinct_reviewers_pass(self, guard_home):
        _write_ledger_record("sess-2", "francisca-tech", seq=1)
        _write_ledger_record("sess-2", "eduardo-copy", seq=2)
        result = check_aggregate(_aggregate(), "sess-2")
        assert result.ok
        assert result.reviewers == sorted(result.reviewers)
        assert len(result.artifacts) == 2

    def test_aliases_of_one_person_count_once(self, guard_home):
        """eduardo-copy + copy-director-eduardo = ONE reviewer."""
        _write_ledger_record("sess-3", "eduardo-copy", seq=1)
        _write_ledger_record("sess-3", "copy-director-eduardo", seq=2)
        result = check_aggregate(_aggregate(), "sess-3")
        assert not result.ok

    def test_aggregator_records_never_count(self, guard_home):
        _write_ledger_record("sess-4", "francisca-tech", seq=1)
        _write_ledger_record("sess-4", "marta-cqo", seq=2)
        result = check_aggregate(_aggregate(), "sess-4")
        assert not result.ok

    def test_reviewer_and_aggregator_ids_are_disjoint(self):
        """_counted keys the aggregator exclusion on this disjointness;
        an id added to both sets would silently admit the aggregator
        into its own quorum."""
        from core.governance.reviewer_ledger import (
            AGGREGATOR_IDS,
            REVIEWER_IDS,
        )

        assert not (REVIEWER_IDS & AGGREGATOR_IDS)

    def test_uncaptured_source_never_counts(self, guard_home):
        """A record any writer could fabricate is not a reviewer."""
        _write_ledger_record("sess-5", "francisca-tech", seq=1)
        _write_ledger_record(
            "sess-5", "eduardo-copy", seq=2, source="record-cli"
        )
        result = check_aggregate(_aggregate(), "sess-5")
        assert not result.ok

    def test_parse_error_record_never_counts(self, guard_home):
        _write_ledger_record("sess-6", "francisca-tech", seq=1)
        _write_ledger_record(
            "sess-6", "eduardo-copy", seq=2,
            parse_error="schema: tree_digest is RESERVED",
        )
        result = check_aggregate(_aggregate(), "sess-6")
        assert not result.ok

    def test_foreign_file_names_never_count(self, guard_home):
        """Only names the ledger itself writes enter the pool."""
        _write_ledger_record("sess-7", "francisca-tech", seq=1)
        _write_ledger_record(
            "sess-7", "eduardo-copy", seq=2, name="operator-note.json"
        )
        result = check_aggregate(_aggregate(), "sess-7")
        assert not result.ok

    def test_missing_session_id_refused(self, guard_home):
        result = check_aggregate(_aggregate(), "")
        assert not result.ok
        assert "--session-id is mandatory" in result.reasons[0]


class TestDigests:
    def _quorum(self, session_id, digest_f="", digest_e=""):
        _write_ledger_record(
            session_id, "francisca-tech", seq=1,
            verdict=_reviewer_verdict(
                "francisca-tech", evidence_digest=digest_f
            ),
        )
        _write_ledger_record(
            session_id, "eduardo-copy", seq=2,
            verdict=_reviewer_verdict(
                "eduardo-copy", evidence_digest=digest_e
            ),
        )

    def test_matching_digests_pass(self, guard_home):
        self._quorum("sess-d1", DIGEST_A, DIGEST_A)
        result = check_aggregate(
            _aggregate(evidence_digest=DIGEST_A), "sess-d1"
        )
        assert result.ok
        assert not result.warnings or all(
            "mismatch" not in w for w in result.warnings
        )

    def test_mismatch_refused(self, guard_home):
        """Reviewers reviewed one report, the aggregate cites another."""
        self._quorum("sess-d2", DIGEST_A, DIGEST_A)
        result = check_aggregate(
            _aggregate(evidence_digest=DIGEST_B), "sess-d2"
        )
        assert not result.ok
        assert any("mismatch" in r for r in result.reasons)

    def test_one_mismatched_reviewer_refused(self, guard_home):
        self._quorum("sess-d3", DIGEST_A, DIGEST_B)
        result = check_aggregate(
            _aggregate(evidence_digest=DIGEST_A), "sess-d3"
        )
        assert not result.ok

    def test_absent_reviewer_digest_refuses_approved(self, guard_home):
        """PR-B4 dispatch shape: a digest-less reviewer artifact means
        the dispatch was malformed — an APPROVED aggregate is refused."""
        self._quorum("sess-d4")
        result = check_aggregate(
            _aggregate(evidence_digest=DIGEST_A), "sess-d4"
        )
        assert not result.ok
        missing = [r for r in result.reasons if "must populate it" in r]
        # Each refusal names WHICH reviewer to re-dispatch (Francisca
        # B4 r2 M9: a literal in place of rid still refuses, but sends
        # the operator after the wrong reviewer — both names required,
        # so no single hardcoded literal can satisfy this).
        assert any("francisca-tech" in r for r in missing)
        assert any("eduardo-copy" in r for r in missing)

    def test_absent_reviewer_digest_warns_on_rejected(self, guard_home):
        """Verdict-aware (item 7): the same shape violation on a
        REJECTED aggregate records with a warning — a rejection label
        is never thrown away over dispatch shape."""
        self._quorum("sess-d4b")
        result = check_aggregate(
            _aggregate("REJECTED", evidence_digest=DIGEST_A), "sess-d4b"
        )
        assert result.ok
        assert any("must populate it" in w for w in result.warnings)
        assert any("recorded anyway" in w for w in result.warnings)

    def test_absent_aggregate_digest_refuses_approved(self, guard_home):
        self._quorum("sess-d5", DIGEST_A, DIGEST_A)
        result = check_aggregate(
            _aggregate(evidence_digest=""), "sess-d5"
        )
        assert not result.ok
        assert any(
            "aggregate carries no evidence_digest" in r
            for r in result.reasons
        )

    def test_absent_aggregate_digest_warns_on_rejected(self, guard_home):
        self._quorum("sess-d5b", DIGEST_A, DIGEST_A)
        result = check_aggregate(
            _aggregate("REJECTED", evidence_digest=""), "sess-d5b"
        )
        assert result.ok
        assert any(
            "aggregate carries no evidence_digest" in w
            for w in result.warnings
        )


class TestBlockerFlow:
    def _quorum_with_confirmed(self, session_id):
        _write_ledger_record(
            session_id, "francisca-tech", seq=1,
            verdict=_reviewer_verdict(
                "francisca-tech", "REJECTED",
                blockers=[{
                    "check": "tests", "detail": "half-pinned guard",
                    "file": "x.py", "verdict": "CONFIRMED",
                }],
            ),
        )
        _write_ledger_record(session_id, "eduardo-copy", seq=2)

    def test_confirmed_blocker_vanishing_refused(self, guard_home):
        self._quorum_with_confirmed("sess-b1")
        result = check_aggregate(_aggregate("APPROVED"), "sess-b1")
        assert not result.ok
        assert any("never disappears silently" in r for r in result.reasons)

    def test_confirmed_carried_in_aggregate_passes(self, guard_home):
        self._quorum_with_confirmed("sess-b2")
        result = check_aggregate(
            _aggregate("REJECTED", blockers=[{
                "check": "tests", "detail": "half-pinned guard",
                "file": "x.py", "verdict": "CONFIRMED",
            }]),
            "sess-b2",
        )
        assert result.ok

    def test_refuted_with_detail_passes(self, guard_home):
        """The refute path decides when the reviewer APPROVED while
        carrying a CONFIRMED blocker; an APPROVED aggregate over a
        REJECTED reviewer is refused regardless (Francisca B3 r1 B2 —
        quality SKILL step 4 is categorical)."""
        _write_ledger_record(
            "sess-b3", "francisca-tech", seq=1,
            verdict=_reviewer_verdict(
                "francisca-tech", "APPROVED",
                blockers=[{
                    "check": "tests", "detail": "half-pinned guard",
                    "file": "x.py", "verdict": "CONFIRMED",
                }],
            ),
        )
        _write_ledger_record("sess-b3", "eduardo-copy", seq=2)
        result = check_aggregate(
            _aggregate("APPROVED", blockers=[{
                "check": "tests",
                "detail": "reproduced against HEAD: the assertion is "
                          "non-vacuous, refuted by execution",
                "file": "x.py", "verdict": "REFUTED",
            }]),
            "sess-b3",
        )
        assert result.ok

    def test_refuted_without_detail_refused(self, guard_home):
        self._quorum_with_confirmed("sess-b4")
        result = check_aggregate(
            _aggregate("APPROVED", blockers=[{
                "check": "tests", "detail": "",
                "file": "x.py", "verdict": "REFUTED",
            }]),
            "sess-b4",
        )
        assert not result.ok
        assert any("substantive reason" in r for r in result.reasons)

    def test_refuted_with_token_detail_refused(self, guard_home):
        """Francisca B3 r1: detail "n/a" satisfied the old non-empty
        check — a drop needs a reason a reader can act on."""
        self._quorum_with_confirmed("sess-b4b")
        result = check_aggregate(
            _aggregate("APPROVED", blockers=[{
                "check": "tests", "detail": "n/a",
                "file": "x.py", "verdict": "REFUTED",
            }]),
            "sess-b4b",
        )
        assert not result.ok

    def test_aggregates_own_finding_warns_never_refuses(self, guard_home):
        """Deviation from the plan literal, on record: the aggregate's
        own-hand blocker is the veto working, not invention."""
        _write_ledger_record("sess-b5", "francisca-tech", seq=1)
        _write_ledger_record("sess-b5", "eduardo-copy", seq=2)
        result = check_aggregate(
            _aggregate("REJECTED", blockers=[{
                "check": "stale-evidence-doc",
                "detail": "doc pinned to a superseded commit",
                "file": "b2-evidence.md", "verdict": "CONFIRMED",
            }]),
            "sess-b5",
        )
        assert result.ok
        assert any("own finding" in w for w in result.warnings)


class TestLaunderingVectors:
    """Francisca B3 r1 blockers B1/B2, reproduced as regressions."""

    def _five_confirmed_quorum(self, session_id):
        checks = ["security-grep", "test-coverage", "typecheck"]
        _write_ledger_record(
            session_id, "francisca-tech", seq=1,
            verdict=_reviewer_verdict(
                "francisca-tech", "REJECTED",
                blockers=[{
                    "check": c, "detail": f"finding for {c}",
                    "file": "x.py", "verdict": "CONFIRMED",
                } for c in checks],
            ),
        )
        _write_ledger_record(
            session_id, "eduardo-copy", seq=2,
            verdict=_reviewer_verdict(
                "eduardo-copy", "REJECTED",
                blockers=[{
                    "check": c, "detail": f"finding for {c}",
                    "file": "y.md", "verdict": "CONFIRMED",
                } for c in ("human-writing", "actionable-output")],
            ),
        )

    def test_single_char_refuted_entries_cannot_launder(self, guard_home):
        """Her exact reproduction: checks "e" and "n", REFUTED, detail
        "n/a" laundered FIVE CONFIRMED blockers under substring
        matching. Token-set matching plus the detail floor kills it."""
        self._five_confirmed_quorum("sess-l1")
        result = check_aggregate(
            _aggregate("APPROVED", blockers=[
                {"check": "e", "detail": "n/a", "file": "",
                 "verdict": "REFUTED"},
                {"check": "n", "detail": "n/a", "file": "",
                 "verdict": "REFUTED"},
            ]),
            "sess-l1",
        )
        assert not result.ok
        assert len(result.reasons) >= 5  # every CONFIRMED blocker uncovered

    def test_single_char_with_substantive_detail_cannot_launder(
        self, guard_home
    ):
        """The detail floor must not be the only thing stopping the
        substring vector: a one-character check with a LONG detail
        still covers nothing under token matching."""
        self._five_confirmed_quorum("sess-l1b")
        long_detail = (
            "reproduced against HEAD by execution: the finding does "
            "not hold on the committed tree"
        )
        result = check_aggregate(
            _aggregate("APPROVED", blockers=[
                {"check": "e", "detail": long_detail, "file": "",
                 "verdict": "REFUTED"},
                {"check": "n", "detail": long_detail, "file": "",
                 "verdict": "REFUTED"},
            ]),
            "sess-l1b",
        )
        assert not result.ok
        assert len(result.reasons) >= 5

    def test_approved_over_rejecting_reviewer_refused(self, guard_home):
        """Her I2: both reviewers REJECTED with empty blocker lists —
        the decision itself must not be out-voted by the aggregate."""
        _write_ledger_record(
            "sess-l2", "francisca-tech", seq=1,
            verdict=_reviewer_verdict("francisca-tech", "REJECTED"),
        )
        _write_ledger_record(
            "sess-l2", "eduardo-copy", seq=2,
            verdict=_reviewer_verdict("eduardo-copy", "REJECTED"),
        )
        result = check_aggregate(_aggregate("APPROVED"), "sess-l2")
        assert not result.ok
        assert any("rejecting reviewer" in r for r in result.reasons)

    def test_approved_carrying_confirmed_blocker_refused(self, guard_home):
        """Her I1: keep the blocker string, flip the decision."""
        self._five_confirmed_quorum("sess-l3")
        carried = [{
            "check": c, "detail": f"finding for {c}",
            "file": "x.py", "verdict": "CONFIRMED",
        } for c in (
            "security-grep", "test-coverage", "typecheck",
            "human-writing", "actionable-output",
        )]
        result = check_aggregate(
            _aggregate("APPROVED", blockers=carried), "sess-l3"
        )
        assert not result.ok
        assert any("carried un-refuted" in r for r in result.reasons)

    def test_approved_downgrading_confirmed_to_plausible_refused(
        self, guard_home
    ):
        """Her I4: CONFIRMED -> PLAUSIBLE downgrade under APPROVED."""
        self._five_confirmed_quorum("sess-l4")
        downgraded = [{
            "check": c, "detail": f"finding for {c}",
            "file": "x.py", "verdict": "PLAUSIBLE",
        } for c in (
            "security-grep", "test-coverage", "typecheck",
            "human-writing", "actionable-output",
        )]
        result = check_aggregate(
            _aggregate("APPROVED", blockers=downgraded), "sess-l4"
        )
        assert not result.ok

    def test_rejected_aggregate_over_rejecting_reviewers_passes(
        self, guard_home
    ):
        """A REJECTED aggregate carrying every CONFIRMED blocker is the
        honest path and must stay recordable."""
        self._five_confirmed_quorum("sess-l5")
        carried = [{
            "check": c, "detail": f"finding for {c}",
            "file": "x.py", "verdict": "CONFIRMED",
        } for c in (
            "security-grep", "test-coverage", "typecheck",
            "human-writing", "actionable-output",
        )]
        result = check_aggregate(
            _aggregate("REJECTED", blockers=carried), "sess-l5"
        )
        assert result.ok


class TestSessionIdSafety:
    """Francisca B3 r1 blocker B4: session_id joined onto ledger_root
    unvalidated — traversal read other sessions' records as quorum."""

    @pytest.mark.parametrize("hostile", [
        "../quality-gate/sess-victim",
        "./sess-victim",
        "sess-victim/",
        "a/../sess-victim",
        "../../.arkaos/quality-gate/sess-victim",
        ".hidden",
    ])
    def test_hostile_session_ids_refused(self, guard_home, hostile):
        _write_ledger_record("sess-victim", "francisca-tech", seq=1)
        _write_ledger_record("sess-victim", "eduardo-copy", seq=2)
        result = check_aggregate(_aggregate(), hostile)
        assert not result.ok
        assert any("safety rule" in r for r in result.reasons)

    def test_write_aggregate_refuses_hostile_ids(self, guard_home):
        result = GuardResult(ok=True)
        assert write_aggregate(
            "../sess-victim", _aggregate(), result
        ) is None


class TestWriteFailure:
    """Francisca B3 r1 blocker B3: an accepted-but-unwritten aggregate
    recorded anyway is the incident shape, one filesystem error away."""

    def _quorum(self, session_id):
        _write_ledger_record(session_id, "francisca-tech", seq=1)
        _write_ledger_record(session_id, "eduardo-copy", seq=2)

    def test_readonly_session_dir_records_nothing(
        self, guard_home, tmp_path, capsys
    ):
        import os as _os

        self._quorum("sess-ro")
        session_dir = ledger_root() / "sess-ro"
        f = tmp_path / "v.json"
        f.write_text(json.dumps(_aggregate()), encoding="utf-8")
        _os.chmod(session_dir, 0o500)
        try:
            rc = record_main([
                "--file", str(f), "--kind", "qg",
                "--session-id", "sess-ro",
            ])
        finally:
            _os.chmod(session_dir, 0o700)
        assert rc == 1
        assert "incident shape" in capsys.readouterr().err
        assert load_verdict_labels() == []
        assert redo_counter.current("sess-ro").count == 0
        assert not (session_dir / AGGREGATE_NAME).exists()

    def test_aggregate_name_as_directory_records_nothing(
        self, guard_home, tmp_path, capsys
    ):
        self._quorum("sess-dir")
        (ledger_root() / "sess-dir" / AGGREGATE_NAME).mkdir()
        f = tmp_path / "v.json"
        f.write_text(json.dumps(_aggregate()), encoding="utf-8")
        rc = record_main([
            "--file", str(f), "--kind", "qg", "--session-id", "sess-dir",
        ])
        assert rc == 1
        assert load_verdict_labels() == []


class TestMalformedRecords:
    def test_garbage_seq_does_not_crash(self, guard_home):
        """Francisca M1: a forged seq must not turn the CLI into a
        traceback — fail-closed, never crash-shaped."""
        session_dir = ledger_root() / "sess-seq"
        session_dir.mkdir(parents=True)
        record = {
            "reviewer_id": "francisca-tech", "seq": "not-a-number",
            "source": "subagent-stop", "parse_error": None,
            "verdict": _reviewer_verdict("francisca-tech"),
        }
        (session_dir / "francisca-tech-1-00000000.json").write_text(
            json.dumps(record), encoding="utf-8"
        )
        _write_ledger_record("sess-seq", "eduardo-copy", seq=2)
        result = check_aggregate(_aggregate(), "sess-seq")
        assert result.ok  # both counted, no ValueError

    def test_dot_prefixed_names_never_count(self, guard_home):
        """Francisca M2: dot-prefixed files are not ledger writes."""
        _write_ledger_record("sess-dot", "francisca-tech", seq=1)
        _write_ledger_record(
            "sess-dot", "eduardo-copy", seq=2,
            name=".eduardo-copy-2-00000000.json",
        )
        result = check_aggregate(_aggregate(), "sess-dot")
        assert not result.ok

    def test_empty_check_confirmed_matches_on_detail(self, guard_home):
        """Francisca M6: an empty check must not make a CONFIRMED
        blocker permanently uncoverable (liveness deadlock). The file
        field is ALSO empty here so the detail step itself decides."""
        _write_ledger_record(
            "sess-mt", "francisca-tech", seq=1,
            verdict=_reviewer_verdict(
                "francisca-tech", "REJECTED",
                blockers=[{
                    "check": "", "detail": "the harvest guard is vacuous",
                    "file": "", "verdict": "CONFIRMED",
                }],
            ),
        )
        _write_ledger_record("sess-mt", "eduardo-copy", seq=2)
        result = check_aggregate(
            _aggregate("REJECTED", blockers=[{
                "check": "", "detail": "the harvest guard is vacuous",
                "file": "", "verdict": "CONFIRMED",
            }]),
            "sess-mt",
        )
        assert result.ok

    def test_empty_check_and_detail_fall_back_to_file(self, guard_home):
        _write_ledger_record(
            "sess-mf", "francisca-tech", seq=1,
            verdict=_reviewer_verdict(
                "francisca-tech", "REJECTED",
                blockers=[{
                    "check": "", "detail": "",
                    "file": "core/x.py", "verdict": "CONFIRMED",
                }],
            ),
        )
        _write_ledger_record("sess-mf", "eduardo-copy", seq=2)
        result = check_aggregate(
            _aggregate("REJECTED", blockers=[{
                "check": "", "detail": "",
                "file": "core/x.py", "verdict": "CONFIRMED",
            }]),
            "sess-mf",
        )
        assert result.ok

    def test_uppercase_digest_compares_case_insensitively(self, guard_home):
        """Francisca M7: hex case is not a content difference."""
        _write_ledger_record(
            "sess-uc", "francisca-tech", seq=1,
            verdict=_reviewer_verdict(
                "francisca-tech", evidence_digest=DIGEST_A.upper()
            ),
        )
        _write_ledger_record(
            "sess-uc", "eduardo-copy", seq=2,
            verdict=_reviewer_verdict(
                "eduardo-copy", evidence_digest=DIGEST_A
            ),
        )
        result = check_aggregate(
            _aggregate(evidence_digest=DIGEST_A), "sess-uc"
        )
        assert result.ok
        assert not any("mismatch" in r for r in result.reasons)

    def test_multi_round_session_uses_latest_record_per_reviewer(
        self, guard_home
    ):
        """Supersession: a redo round replaces the reviewer's earlier
        verdict. Without it no real multi-round session could close
        honestly — the final APPROVED aggregate would have to cover
        blockers already fixed in earlier rounds."""
        _write_ledger_record(
            "sess-mr", "francisca-tech", seq=1,
            verdict=_reviewer_verdict(
                "francisca-tech", "REJECTED",
                blockers=[{
                    "check": "half-pinned-test", "detail": "round 1",
                    "file": "x.py", "verdict": "CONFIRMED",
                }],
            ),
        )
        _write_ledger_record(
            "sess-mr", "francisca-tech", seq=3,
            verdict=_reviewer_verdict("francisca-tech", "APPROVED"),
            name="francisca-tech-3-00000001.json",
        )
        _write_ledger_record("sess-mr", "eduardo-copy", seq=2)
        result = check_aggregate(_aggregate("APPROVED"), "sess-mr")
        assert result.ok  # the r1 blocker is superseded, not laundered
        assert "francisca-tech-3-00000001.json" in result.artifacts
        assert "francisca-tech-1-00000000.json" not in result.artifacts

    def test_superseded_rejection_no_longer_blocks_approval(
        self, guard_home
    ):
        """The verdict rule also reads the LATEST record only."""
        _write_ledger_record(
            "sess-mr2", "eduardo-copy", seq=1,
            verdict=_reviewer_verdict("eduardo-copy", "REJECTED"),
        )
        _write_ledger_record(
            "sess-mr2", "eduardo-copy", seq=4,
            verdict=_reviewer_verdict("eduardo-copy", "APPROVED"),
            name="eduardo-copy-4-00000001.json",
        )
        _write_ledger_record("sess-mr2", "francisca-tech", seq=2)
        result = check_aggregate(_aggregate("APPROVED"), "sess-mr2")
        assert result.ok

    def test_alias_switch_never_hides_the_newest_rejection(
        self, guard_home
    ):
        """Francisca r3 B1: seq is assigned per SPELLING, so an
        alias-switched dispatch restarts at 1 — under seq ordering the
        person's NEWEST verdict lost to their older one and a live
        REJECTED with a CONFIRMED blocker vanished. The record clock
        decides now."""
        _write_ledger_record(
            "sess-al", "francisca-tech", seq=3,
            ts="2026-07-30T10:00:00+00:00",
            verdict=_reviewer_verdict("francisca-tech", "APPROVED"),
            name="francisca-tech-3-00000000.json",
        )
        _write_ledger_record(
            "sess-al", "tech-ux-director", seq=1,
            ts="2026-07-30T11:00:00+00:00",  # NEWER, lower seq
            verdict=_reviewer_verdict(
                "tech-ux-director", "REJECTED",
                blockers=[{
                    "check": "security-grep", "detail": "live finding",
                    "file": "x.py", "verdict": "CONFIRMED",
                }],
            ),
        )
        _write_ledger_record(
            "sess-al", "eduardo-copy", seq=2,
            ts="2026-07-30T09:00:00+00:00",
        )
        result = check_aggregate(_aggregate("APPROVED"), "sess-al")
        assert not result.ok
        assert "tech-ux-director-1-00000000.json" in result.artifacts

    def test_alias_switched_redo_still_closes(self, guard_home):
        """The mirror direction: a NEWER approval under the other
        spelling supersedes the older rejection (liveness)."""
        _write_ledger_record(
            "sess-al2", "francisca-tech", seq=3,
            ts="2026-07-30T10:00:00+00:00",
            verdict=_reviewer_verdict("francisca-tech", "REJECTED"),
            name="francisca-tech-3-00000000.json",
        )
        _write_ledger_record(
            "sess-al2", "tech-ux-director", seq=1,
            ts="2026-07-30T11:00:00+00:00",
            verdict=_reviewer_verdict("tech-ux-director", "APPROVED"),
        )
        _write_ledger_record(
            "sess-al2", "eduardo-copy", seq=2,
            ts="2026-07-30T09:00:00+00:00",
        )
        result = check_aggregate(_aggregate("APPROVED"), "sess-al2")
        assert result.ok

    def test_backwards_clock_step_never_hides_a_same_spelling_rejection(
        self, guard_home
    ):
        """Francisca r4 B1: clock-first ordering let a backwards clock
        step (NTP step, VM suspend) make an older APPROVED supersede
        the newer REJECTED of the SAME spelling — where seq is monotone
        by construction and must decide."""
        _write_ledger_record(
            "sess-ck", "francisca-tech", seq=1,
            ts="2026-07-30T10:05:00+00:00",  # later clock, older round
            verdict=_reviewer_verdict("francisca-tech", "APPROVED"),
        )
        _write_ledger_record(
            "sess-ck", "francisca-tech", seq=2,
            ts="2026-07-30T10:00:00+00:00",  # earlier clock, NEWER round
            verdict=_reviewer_verdict(
                "francisca-tech", "REJECTED",
                blockers=[{
                    "check": "security-grep", "detail": "live finding",
                    "file": "x.py", "verdict": "CONFIRMED",
                }],
            ),
            name="francisca-tech-2-00000000.json",
        )
        _write_ledger_record("sess-ck", "eduardo-copy", seq=3)
        result = check_aggregate(_aggregate("APPROVED"), "sess-ck")
        assert not result.ok
        assert "francisca-tech-2-00000000.json" in result.artifacts

    def test_clockless_alias_switch_fails_closed(self, guard_home):
        """Francisca r4 M2: without a usable clock on both sides,
        cross-spelling recency is unprovable — the rejecting record
        holds; a superseding approval must prove its recency. The
        APPROVED spelling is iterated FIRST here so the outcome rests
        on the fail-closed rule, never on iteration order (battery
        G28)."""
        _write_ledger_record(
            "sess-cl", "francisca-tech", seq=1,
            verdict=_reviewer_verdict("francisca-tech", "APPROVED"),
        )
        _write_ledger_record(
            "sess-cl", "tech-ux-director", seq=3,
            verdict=_reviewer_verdict(
                "tech-ux-director", "REJECTED",
                blockers=[{
                    "check": "tests", "detail": "live finding",
                    "file": "x.py", "verdict": "CONFIRMED",
                }],
            ),
            name="tech-ux-director-3-00000000.json",
        )
        _write_ledger_record("sess-cl", "eduardo-copy", seq=2)
        result = check_aggregate(_aggregate("APPROVED"), "sess-cl")
        assert not result.ok

    def test_alias_switch_refusal_is_order_independent(self, guard_home):
        """The mirror seq assignment of the alias-switch shape: the
        APPROVED spelling iterates FIRST and the newer REJECTED must
        still supersede it BY THE CLOCK — never by iteration order
        (battery G27)."""
        _write_ledger_record(
            "sess-oi", "francisca-tech", seq=1,
            ts="2026-07-30T10:00:00+00:00",
            verdict=_reviewer_verdict("francisca-tech", "APPROVED"),
        )
        _write_ledger_record(
            "sess-oi", "tech-ux-director", seq=3,
            ts="2026-07-30T11:00:00+00:00",  # newer, iterated last
            verdict=_reviewer_verdict(
                "tech-ux-director", "REJECTED",
                blockers=[{
                    "check": "security-grep", "detail": "live finding",
                    "file": "x.py", "verdict": "CONFIRMED",
                }],
            ),
            name="tech-ux-director-3-00000000.json",
        )
        _write_ledger_record("sess-oi", "eduardo-copy", seq=2)
        result = check_aggregate(_aggregate("APPROVED"), "sess-oi")
        assert not result.ok
        assert "tech-ux-director-3-00000000.json" in result.artifacts

    def test_same_seq_divergent_pair_severity_decides(self, guard_home):
        """Francisca r5 B1: two live records at the SAME seq (the
        two-writer window, or a reused seq after a removal), BOTH
        rejecting by the old binary flag — an APPROVED carrying a
        CONFIRMED blocker vs a REJECTED. Severity ranks separate
        them; filename byte order never decides."""
        _write_ledger_record(
            "sess-sq", "francisca-tech", seq=2,
            ts="2026-07-30T10:00:00+00:00",
            verdict=_reviewer_verdict(
                "francisca-tech", "APPROVED",
                blockers=[{
                    "check": "coverage", "detail": "minor gap",
                    "file": "x.py", "verdict": "CONFIRMED",
                }],
            ),
            name="francisca-tech-2-00000000.json",  # sorts FIRST
        )
        _write_ledger_record(
            "sess-sq", "francisca-tech", seq=2,
            ts="2026-07-30T10:00:00+00:00",
            verdict=_reviewer_verdict(
                "francisca-tech", "REJECTED",
                blockers=[{
                    "check": "coverage", "detail": "uncovered arm",
                    "file": "x.py", "verdict": "CONFIRMED",
                }],
            ),
            name="francisca-tech-2-ffffffff.json",
        )
        _write_ledger_record("sess-sq", "eduardo-copy", seq=3)
        result = check_aggregate(_aggregate("APPROVED"), "sess-sq")
        assert not result.ok
        assert "francisca-tech-2-ffffffff.json" in result.artifacts

    def test_same_seq_same_severity_ties_break_by_clock(self, guard_home):
        """At severity parity the record clock breaks the tie — the
        newer of two same-seq REJECTED records is the live one
        (battery mutant G33: dropping ts from the level-one key)."""
        _write_ledger_record(
            "sess-sc", "francisca-tech", seq=2,
            ts="2026-07-30T10:00:00+00:00",
            verdict=_reviewer_verdict(
                "francisca-tech", "REJECTED",
                blockers=[{
                    "check": "old-finding", "detail": "superseded",
                    "file": "a.py", "verdict": "CONFIRMED",
                }],
            ),
            name="francisca-tech-2-00000000.json",
        )
        _write_ledger_record(
            "sess-sc", "francisca-tech", seq=2,
            ts="2026-07-30T11:00:00+00:00",  # newer
            verdict=_reviewer_verdict(
                "francisca-tech", "REJECTED",
                blockers=[{
                    "check": "new-finding", "detail": "live",
                    "file": "b.py", "verdict": "CONFIRMED",
                }],
            ),
            name="francisca-tech-2-11111111.json",
        )
        _write_ledger_record("sess-sc", "eduardo-copy", seq=3)
        result = check_aggregate(
            _aggregate("REJECTED", blockers=[{
                "check": "new-finding", "detail": "live",
                "file": "b.py", "verdict": "CONFIRMED",
            }]),
            "sess-sc",
        )
        assert result.ok  # only the NEWER record's blocker needs cover

    def test_one_sided_clockless_rejection_holds(self, guard_home):
        """Francisca r5 M2: the ONE-SIDED clockless case — a clocked
        APPROVED cannot supersede a clockless REJECTED, which nothing
        can prove itself newer than."""
        _write_ledger_record(
            "sess-os", "francisca-tech", seq=1,
            ts="2026-07-30T11:00:00+00:00",
            verdict=_reviewer_verdict("francisca-tech", "APPROVED"),
        )
        _write_ledger_record(
            "sess-os", "tech-ux-director", seq=3,
            verdict=_reviewer_verdict(
                "tech-ux-director", "REJECTED",
                blockers=[{
                    "check": "tests", "detail": "live finding",
                    "file": "x.py", "verdict": "CONFIRMED",
                }],
            ),
            name="tech-ux-director-3-00000000.json",
        )
        _write_ledger_record("sess-os", "eduardo-copy", seq=2)
        result = check_aggregate(_aggregate("APPROVED"), "sess-os")
        assert not result.ok

    def test_true_tie_prefers_the_rejecting_record(self, guard_home):
        """Equal clock and seq (the two-writer divergent-text shape):
        the rejecting record wins — fail-closed, never hash luck."""
        _write_ledger_record(
            "sess-tie", "francisca-tech", seq=1,
            ts="2026-07-30T10:00:00+00:00",
            verdict=_reviewer_verdict("francisca-tech", "APPROVED"),
            name="francisca-tech-1-aaaaaaaa.json",
        )
        _write_ledger_record(
            "sess-tie", "francisca-tech", seq=1,
            ts="2026-07-30T10:00:00+00:00",
            verdict=_reviewer_verdict("francisca-tech", "REJECTED"),
            name="francisca-tech-1-bbbbbbbb.json",
        )
        _write_ledger_record("sess-tie", "eduardo-copy", seq=2)
        result = check_aggregate(_aggregate("APPROVED"), "sess-tie")
        assert not result.ok

    def test_all_empty_blocker_refuses_with_redispatch_remedy(
        self, guard_home
    ):
        """Francisca r3 B4: the liveness branch shipped unpinned —
        this is the pin (and battery mutant G25)."""
        _write_ledger_record(
            "sess-ae", "francisca-tech", seq=1,
            verdict=_reviewer_verdict(
                "francisca-tech", "REJECTED",
                blockers=[{
                    "check": "", "detail": "", "file": "",
                    "verdict": "CONFIRMED",
                }],
            ),
        )
        _write_ledger_record("sess-ae", "eduardo-copy", seq=2)
        result = check_aggregate(_aggregate("REJECTED"), "sess-ae")
        assert not result.ok
        assert any("re-dispatch" in r for r in result.reasons)

    def test_write_aggregate_refuses_a_failed_result(self, guard_home):
        """Francisca r3 Mi2: the guard's own writer must never file a
        refusal — that would be the incident shape through the front
        door."""
        assert write_aggregate(
            "sess-mi2", _aggregate(), GuardResult(ok=False)
        ) is None

    def test_newline_suffixed_record_name_never_counts(self, guard_home):
        """Francisca r3 Mi1: match accepted a trailing newline in the
        record NAME — the class _safe_id just fixed, one file over."""
        _write_ledger_record("sess-nn", "francisca-tech", seq=1)
        _write_ledger_record(
            "sess-nn", "eduardo-copy", seq=2,
            name="eduardo-copy-2-00000000.json\n",
        )
        result = check_aggregate(_aggregate(), "sess-nn")
        assert not result.ok

    def test_accepted_aggregate_session_still_sweeps(self, guard_home):
        """Francisca r3 B2: AGGREGATE.json was a name the ledger did
        not own, so _purge refused the directory whole and retention
        became a no-op for every session that PASSED the gate."""
        import os as _os
        import time as _time

        from core.governance.reviewer_ledger import sweep_expired

        _write_ledger_record("sess-sw", "francisca-tech", seq=1)
        _write_ledger_record("sess-sw", "eduardo-copy", seq=2)
        aggregate = _aggregate()
        result = check_aggregate(aggregate, "sess-sw")
        assert write_aggregate("sess-sw", aggregate, result) is not None
        session_dir = ledger_root() / "sess-sw"
        ancient = _time.time() - (200 * 86400)
        _os.utime(session_dir, (ancient, ancient))
        assert sweep_expired(days=90) == 1
        assert not session_dir.exists()

    def test_foreign_file_still_blocks_the_sweep(self, guard_home):
        import os as _os
        import time as _time

        from core.governance.reviewer_ledger import sweep_expired

        _write_ledger_record("sess-sw2", "francisca-tech", seq=1)
        (ledger_root() / "sess-sw2" / "operator-note.json").write_text(
            "keep me", encoding="utf-8"
        )
        session_dir = ledger_root() / "sess-sw2"
        ancient = _time.time() - (200 * 86400)
        _os.utime(session_dir, (ancient, ancient))
        assert sweep_expired(days=90) == 0
        assert session_dir.exists()

    def test_trailing_newline_session_id_refused(self, guard_home):
        """Francisca r2 M4: _safe_id used .match against a $-anchored
        pattern, and $ accepts a trailing newline. Through the CLI the
        symptom was a misleading zero-reviewer count; the sibling
        directory appeared only in her direct write_aggregate probe,
        because check_aggregate refuses first."""
        _write_ledger_record("sess-nl", "francisca-tech", seq=1)
        _write_ledger_record("sess-nl", "eduardo-copy", seq=2)
        result = check_aggregate(_aggregate(), "sess-nl\n")
        assert not result.ok
        assert any("safety rule" in r for r in result.reasons)
        assert write_aggregate("sess-nl\n", _aggregate(), GuardResult(
            ok=True
        )) is None

    def test_reviewers_list_uses_canonical_agent_ids(self, guard_home):
        """Francisca M4: canonical deployed agent-file ids in the
        output, not min() of the alias group (which mixed spellings).
        The inputs here are the config/constitution.yaml ids — a
        DIFFERENT set from the canonical output."""
        _write_ledger_record("sess-can", "copy-director-eduardo", seq=1)
        _write_ledger_record("sess-can", "tech-director-francisca", seq=2)
        result = check_aggregate(_aggregate(), "sess-can")
        assert result.reviewers == ["eduardo-copy", "francisca-tech"]


class TestAggregateFile:
    def test_write_and_replace(self, guard_home):
        _write_ledger_record("sess-w1", "francisca-tech", seq=1)
        _write_ledger_record("sess-w1", "eduardo-copy", seq=2)
        aggregate = _aggregate()
        result = check_aggregate(aggregate, "sess-w1")
        path = write_aggregate("sess-w1", aggregate, result)
        assert path is not None and path.name == AGGREGATE_NAME
        first = json.loads(path.read_text(encoding="utf-8"))
        assert first["reviewers"] == result.reviewers
        assert len(first["aggregate_verdict_digest"]) == 64
        # A redo round re-issues: replace, never collide.
        again = write_aggregate("sess-w1", aggregate, result)
        assert again is not None

    def test_aggregate_file_never_enters_the_quorum(self, guard_home):
        _write_ledger_record("sess-w2", "francisca-tech", seq=1)
        _write_ledger_record("sess-w2", "eduardo-copy", seq=2)
        aggregate = _aggregate()
        result = check_aggregate(aggregate, "sess-w2")
        write_aggregate("sess-w2", aggregate, result)
        result2 = check_aggregate(aggregate, "sess-w2")
        assert result2.ok and len(result2.artifacts) == 2


class TestRecordCliIntegration:
    def _quorum(self, session_id):
        _write_ledger_record(session_id, "francisca-tech", seq=1)
        _write_ledger_record(session_id, "eduardo-copy", seq=2)

    def test_kind_qg_without_session_id_refused(
        self, guard_home, tmp_path, capsys
    ):
        f = tmp_path / "v.json"
        f.write_text(json.dumps(_aggregate()), encoding="utf-8")
        assert record_main(["--file", str(f), "--kind", "qg"]) == 1
        assert "requires --session-id" in capsys.readouterr().err
        assert load_verdict_labels() == []

    def test_refused_aggregate_records_nothing(
        self, guard_home, tmp_path, capsys
    ):
        """The incident, end to end: refusal leaves the corpus untouched."""
        f = tmp_path / "v.json"
        f.write_text(json.dumps(_aggregate()), encoding="utf-8")
        rc = record_main(
            ["--file", str(f), "--kind", "qg", "--session-id", "sess-cli1"]
        )
        assert rc == 1
        err = capsys.readouterr().err
        assert "anti-self-approval" in err
        # The SPECIFIC guard reason must reach the operator — after the
        # write_aggregate ok-gate (r3 Mi2) the CLI's own check became
        # redundant for the OUTCOME, so the reasons are what pin it
        # (actionable-output; battery mutant G9).
        assert "hook-captured reviewer verdict(s)" in err
        assert load_verdict_labels() == []
        assert not (ledger_root() / "sess-cli1" / AGGREGATE_NAME).exists()

    def test_accepted_aggregate_records_label_and_file(
        self, guard_home, tmp_path, capsys
    ):
        self._quorum("sess-cli2")
        f = tmp_path / "v.json"
        f.write_text(json.dumps(_aggregate()), encoding="utf-8")
        rc = record_main([
            "--file", str(f), "--kind", "qg", "--session-id", "sess-cli2",
            "--round", "14", "--head", "f81b7f8b",
        ])
        assert rc == 0
        out = json.loads(capsys.readouterr().out)
        assert out["recorded"] and out["aggregate"].endswith(AGGREGATE_NAME)
        labels = load_verdict_labels()
        assert len(labels) == 1
        assert labels[0]["kind"] == "qg"
        assert labels[0]["round"] == "14"
        assert labels[0]["head"] == "f81b7f8b"

    def test_rejected_drives_redo_counter(self, guard_home, tmp_path, capsys):
        self._quorum("sess-cli3")
        f = tmp_path / "v.json"
        f.write_text(
            json.dumps(_aggregate("REJECTED", blockers=[{
                "check": "x", "detail": "y", "file": "z",
                "verdict": "CONFIRMED",
            }])),
            encoding="utf-8",
        )
        rc = record_main(
            ["--file", str(f), "--kind", "qg", "--session-id", "sess-cli3"]
        )
        assert rc == 0
        assert redo_counter.current("sess-cli3").count == 1
        assert "redo cycle 1" in json.loads(capsys.readouterr().out)["redo"]

    def test_approved_resets_redo_counter(self, guard_home, tmp_path, capsys):
        self._quorum("sess-cli4")
        redo_counter.record_rejected("sess-cli4")
        f = tmp_path / "v.json"
        f.write_text(json.dumps(_aggregate()), encoding="utf-8")
        rc = record_main(
            ["--file", str(f), "--kind", "qg", "--session-id", "sess-cli4"]
        )
        assert rc == 0
        assert redo_counter.current("sess-cli4").count == 0

    def test_kind_reviewer_records_and_cross_references(
        self, guard_home, tmp_path, capsys
    ):
        verdict = _reviewer_verdict("francisca-tech", "APPROVED")
        _write_ledger_record("sess-cli5", "francisca-tech", verdict=verdict)
        f = tmp_path / "v.json"
        f.write_text(json.dumps(verdict), encoding="utf-8")
        rc = record_main([
            "--file", str(f), "--kind", "reviewer",
            "--session-id", "sess-cli5",
        ])
        assert rc == 0
        out = json.loads(capsys.readouterr().out)
        assert out["ledger_match"].startswith("francisca-tech-1-")
        assert load_verdict_labels()[0]["kind"] == "reviewer"

    def test_kind_reviewer_no_match_is_empty_not_fabricated(
        self, guard_home, tmp_path, capsys
    ):
        f = tmp_path / "v.json"
        f.write_text(
            json.dumps(_reviewer_verdict("francisca-tech")), encoding="utf-8"
        )
        rc = record_main([
            "--file", str(f), "--kind", "reviewer",
            "--session-id", "sess-cli6",
        ])
        assert rc == 0
        out = json.loads(capsys.readouterr().out)
        assert out["ledger_match"] == ""
        assert not (ledger_root() / "sess-cli6").exists()

    def test_kind_reviewer_refuses_aggregator_identity(
        self, guard_home, tmp_path, capsys
    ):
        """Eduardo B3 r1 blocker 2, promoted from disclosure to code:
        the 2026-07-20 incident is described in reviewer terms, and an
        aggregator recording its own verdict under --kind reviewer
        would repeat it under a different flag."""
        f = tmp_path / "v.json"
        f.write_text(
            json.dumps(_reviewer_verdict("cqo-marta")), encoding="utf-8"
        )
        rc = record_main(["--file", str(f), "--kind", "reviewer"])
        assert rc == 1
        assert "aggregator identity" in capsys.readouterr().err
        assert load_verdict_labels() == []


class TestDigestCarry:
    """PR-B4 item 11: per-reviewer digest equality forced a re-dispatch
    of every reviewer on ANY report change; a justified carry naming
    the report that reviewer actually reviewed now excuses the
    mismatch — and nothing less than that does."""

    CARRY_REASON = (
        "message-only amend after her round: tree byte-identical to the "
        "reviewed head, diff is commit prose only"
    )

    def _split_quorum(self, session_id):
        """Francisca reviewed report A (earlier round), Eduardo the
        final report B."""
        _write_ledger_record(
            session_id, "francisca-tech", seq=1,
            verdict=_reviewer_verdict(
                "francisca-tech", evidence_digest=DIGEST_A
            ),
        )
        _write_ledger_record(
            session_id, "eduardo-copy", seq=2,
            verdict=_reviewer_verdict(
                "eduardo-copy", evidence_digest=DIGEST_B
            ),
        )

    def _carry(self, reviewer="francisca-tech", digest=DIGEST_A, reason=None):
        return {
            "reviewer": reviewer,
            "evidence_digest": digest,
            "reason": self.CARRY_REASON if reason is None else reason,
        }

    def test_justified_carry_passes_and_lands_on_the_record(self, guard_home):
        self._split_quorum("sess-c1")
        agg = _aggregate(evidence_digest=DIGEST_B)
        agg["digest_carries"] = [self._carry()]
        result = check_aggregate(agg, "sess-c1")
        assert result.ok
        note = next(w for w in result.warnings if "carry accepted" in w)
        # The reviewer's OWN digest comes first, the aggregate's second
        # (Francisca B4 r2 M8: the constant hoist moved message
        # assembly away from the values, where an argument swap hides).
        assert note.index(DIGEST_A[:12]) < note.index(DIGEST_B[:12])

    def test_undeclared_mismatch_still_refuses_approved(self, guard_home):
        self._split_quorum("sess-c2")
        result = check_aggregate(
            _aggregate(evidence_digest=DIGEST_B), "sess-c2"
        )
        assert not result.ok
        assert any("digest_carries" in r for r in result.reasons)

    def test_mismatch_on_rejected_records_with_warning(self, guard_home):
        """Item 7 end to end: the CQO catches a bad delta and REJECTS —
        the rejection label survives the digest mismatch."""
        self._split_quorum("sess-c3")
        result = check_aggregate(
            _aggregate("REJECTED", evidence_digest=DIGEST_B), "sess-c3"
        )
        assert result.ok
        assert any("mismatch" in w for w in result.warnings)
        assert any("recorded anyway" in w for w in result.warnings)

    def test_carry_naming_a_report_never_reviewed_refused(self, guard_home):
        """A carry that cites the AGGREGATE's digest instead of the
        reviewer's is laundering with paperwork."""
        self._split_quorum("sess-c4")
        agg = _aggregate(evidence_digest=DIGEST_B)
        agg["digest_carries"] = [self._carry(digest=DIGEST_B)]
        result = check_aggregate(agg, "sess-c4")
        assert not result.ok
        assert any("actually reviewed" in r for r in result.reasons)

    def test_carry_with_bare_reason_refused(self, guard_home):
        self._split_quorum("sess-c5")
        agg = _aggregate(evidence_digest=DIGEST_B)
        agg["digest_carries"] = [self._carry(reason="n/a")]
        result = check_aggregate(agg, "sess-c5")
        assert not result.ok
        assert any("substantive reason" in r for r in result.reasons)

    def test_carry_matches_across_alias_spellings(self, guard_home):
        """A carry declared under the constitution spelling covers the
        deployed-agent spelling — one person, one identity."""
        self._split_quorum("sess-c6")
        agg = _aggregate(evidence_digest=DIGEST_B)
        agg["digest_carries"] = [self._carry(reviewer="tech-director-francisca")]
        result = check_aggregate(agg, "sess-c6")
        assert result.ok

    def test_carry_matches_when_ledger_uses_alias_spelling(self, guard_home):
        """The mirror pin: the LEDGER record under the constitution
        spelling, the carry under the deployed-agent id. Both lookups
        must go through _identity — keying either side raw breaks one
        direction and not the other."""
        _write_ledger_record(
            "sess-c6b", "tech-director-francisca", seq=1,
            verdict=_reviewer_verdict(
                "tech-director-francisca", evidence_digest=DIGEST_A
            ),
        )
        _write_ledger_record(
            "sess-c6b", "eduardo-copy", seq=2,
            verdict=_reviewer_verdict(
                "eduardo-copy", evidence_digest=DIGEST_B
            ),
        )
        agg = _aggregate(evidence_digest=DIGEST_B)
        agg["digest_carries"] = [self._carry(reviewer="francisca-tech")]
        result = check_aggregate(agg, "sess-c6b")
        assert result.ok

    def test_uppercase_reviewer_digest_still_matches(self, guard_home):
        """The comparison is case-normalised on BOTH sides (_norm) —
        load-bearing because the schema's hex rule is lowercase-only
        on the VALIDATED aggregate side while the ledger stores the
        raw captured fence, so an upper-case reviewer digest is a live
        shape (Francisca B4 r1 M3; her F23 mutant survived unpinned)."""
        _write_ledger_record(
            "sess-c8", "francisca-tech", seq=1,
            verdict=_reviewer_verdict(
                "francisca-tech", evidence_digest=DIGEST_A.upper()
            ),
        )
        _write_ledger_record("sess-c8", "eduardo-copy", seq=2)
        result = check_aggregate(_aggregate(), "sess-c8")
        assert result.ok
        assert not any("mismatch" in r for r in result.reasons)
        # Mirror: the AGGREGATE side is normalised too (schema hex is
        # lowercase-only at the CLI, but check_aggregate takes raw
        # dicts from direct callers).
        _write_ledger_record("sess-c9", "francisca-tech", seq=1)
        _write_ledger_record("sess-c9", "eduardo-copy", seq=2)
        upper = check_aggregate(
            _aggregate(evidence_digest=DIGEST_A.upper()), "sess-c9"
        )
        assert upper.ok
        assert not any("mismatch" in r for r in upper.reasons)

    def test_carry_for_matching_reviewer_is_inert(self, guard_home):
        """A carry for a reviewer whose digest already matches changes
        nothing — no refusal, no accepted-carry note."""
        _write_ledger_record("sess-c7", "francisca-tech", seq=1)
        _write_ledger_record("sess-c7", "eduardo-copy", seq=2)
        agg = _aggregate()
        agg["digest_carries"] = [self._carry(digest=DIGEST_A)]
        result = check_aggregate(agg, "sess-c7")
        assert result.ok
        assert not any("carry accepted" in w for w in result.warnings)


class TestSessionBinding:
    """PR-B4 item 1: a past session's ledger was a reusable quorum
    token; the SessionEnd stamp closes the common path."""

    def _quorum(self, session_id):
        _write_ledger_record(session_id, "francisca-tech", seq=1)
        _write_ledger_record(session_id, "eduardo-copy", seq=2)

    def _stamp(self, session_id):
        from core.governance.reviewer_ledger import ENDED_NAME

        (ledger_root() / session_id / ENDED_NAME).touch()

    def test_ended_session_refuses_approved(self, guard_home):
        self._quorum("sess-s1")
        self._stamp("sess-s1")
        result = check_aggregate(_aggregate(), "sess-s1")
        assert not result.ok
        assert any(
            "not a reusable quorum token" in r for r in result.reasons
        )

    def test_ended_session_warns_on_rejected(self, guard_home):
        self._quorum("sess-s2")
        self._stamp("sess-s2")
        result = check_aggregate(_aggregate("REJECTED"), "sess-s2")
        assert result.ok
        assert any(
            "not a reusable quorum token" in w for w in result.warnings
        )

    def test_stamp_never_enters_the_quorum_pool(self, guard_home):
        """Dot-prefixed on purpose: the stamp is a marker, not a record.

        The record pool is doubly defended (_session_records skips dot
        names AND _RECORD_NAME_RE rejects the stamp), so exclusion
        alone survives a renamed constant — the dot prefix itself is
        pinned because .quarantine/tmp handling and the sweep's
        dot-skip all assume it (Francisca B4 r1 M2)."""
        from core.governance.reviewer_ledger import ENDED_NAME

        assert ENDED_NAME.startswith(".")
        self._quorum("sess-s3")
        self._stamp("sess-s3")
        result = check_aggregate(_aggregate("REJECTED"), "sess-s3")
        assert sorted(result.reviewers) == ["eduardo-copy", "francisca-tech"]

    def test_mark_session_ended_stamps_only_existing_dirs(self, guard_home):
        from core.governance.reviewer_ledger import (
            ENDED_NAME,
            mark_session_ended,
        )

        mark_session_ended("sess-never-captured")
        assert not (ledger_root() / "sess-never-captured").exists()
        self._quorum("sess-s4")
        mark_session_ended("sess-s4")
        assert (ledger_root() / "sess-s4" / ENDED_NAME).is_file()

    def test_mark_session_ended_refuses_hostile_ids(self, guard_home):
        """_safe_id is the load-bearing guard here, not is_dir():
        Francisca's F12 mutant (validator deleted) passed the old
        version because every hostile path also failed to resolve.
        The dot-directory case resolves to an EXISTING dir — only the
        validator stops the stamp."""
        from core.governance.reviewer_ledger import (
            ENDED_NAME,
            mark_session_ended,
        )

        quarantine = ledger_root() / ".quarantine"
        quarantine.mkdir(parents=True)
        for hostile in ("../escape", ".quarantine", "", "a/b"):
            mark_session_ended(hostile)  # must not raise, must not stamp
        assert not (ledger_root() / ".." / "escape").exists()
        assert not (quarantine / ENDED_NAME).exists()
        # "" must never stamp the ledger root itself.
        assert not (ledger_root() / ENDED_NAME).exists()

    def test_retention_still_purges_a_stamped_session(self, guard_home):
        """The stamp is an OWNED name — a stamped dir must not turn
        retention into a no-op (the NOTICES.jsonl lesson, PR-B1)."""
        import os
        import time

        from core.governance.reviewer_ledger import sweep_expired

        self._quorum("sess-s5")
        self._stamp("sess-s5")
        session_dir = ledger_root() / "sess-s5"
        old = time.time() - 200 * 86400
        os.utime(session_dir, (old, old))
        assert sweep_expired(days=90) == 1
        assert not session_dir.exists()


class TestCheckKeyContract:
    """PR-B4 item 1: coverage matching wants shared check vocabulary —
    a CONFIRMED blocker filed without a check key warns, never blocks
    (liveness stays with _blocker_key's detail/file fallback)."""

    def test_confirmed_blocker_without_check_key_warns(self, guard_home):
        blocker = {
            "check": "", "verdict": "CONFIRMED",
            "detail": "the mutation battery leaves _cross_key unpinned",
        }
        _write_ledger_record(
            "sess-k1", "francisca-tech", seq=1,
            verdict=_reviewer_verdict(
                "francisca-tech", "REJECTED", blockers=[blocker]
            ),
        )
        _write_ledger_record("sess-k1", "eduardo-copy", seq=2)
        result = check_aggregate(
            _aggregate("REJECTED", blockers=[dict(blocker)]), "sess-k1"
        )
        assert result.ok
        assert any("without a check key" in w for w in result.warnings)

    def test_unmatchable_blocker_never_draws_the_check_key_warning(
        self, guard_home
    ):
        """A CONFIRMED blocker with empty check AND empty detail/file
        draws the cannot-be-matched liveness reason, never a spurious
        check-key warning on top (Francisca B4 r2 M10: the second
        conjunct of the warning condition was unpinned in the
        direction F19 does not cover)."""
        blocker = {"check": "", "detail": "", "file": None,
                   "verdict": "CONFIRMED"}
        _write_ledger_record(
            "sess-k3", "francisca-tech", seq=1,
            verdict=_reviewer_verdict(
                "francisca-tech", "REJECTED", blockers=[blocker]
            ),
        )
        _write_ledger_record("sess-k3", "eduardo-copy", seq=2)
        result = check_aggregate(_aggregate("REJECTED"), "sess-k3")
        assert any("cannot be matched" in r for r in result.reasons)
        assert not any("without a check key" in w for w in result.warnings)

    def test_blocker_with_check_key_never_draws_the_warning(self, guard_home):
        """The false-positive side, pinned on a fixture that actually
        presents a keyed CONFIRMED blocker (Francisca B4 r1 B2: the
        blocker-less version could not fail, and her F19 mutant —
        warn on EVERY CONFIRMED blocker — survived the whole suite)."""
        blocker = {
            "check": "tests", "detail": "half-pinned guard",
            "file": "x.py", "verdict": "CONFIRMED",
        }
        _write_ledger_record(
            "sess-k2", "francisca-tech", seq=1,
            verdict=_reviewer_verdict(
                "francisca-tech", "REJECTED", blockers=[blocker]
            ),
        )
        _write_ledger_record("sess-k2", "eduardo-copy", seq=2)
        result = check_aggregate(
            _aggregate("REJECTED", blockers=[dict(blocker)]), "sess-k2"
        )
        assert result.ok
        assert not any("without a check key" in w for w in result.warnings)


class TestSessionBindingMtime:
    """M4 (PR-B5): the stamp only outlaws records that PREDATE it.

    A counted record captured strictly after the stamp's mtime proves
    the hook boundary came back to life under this session id, so the
    refusal lifts; ties and older records keep it (fail-closed).
    """

    def _quorum(self, session_id):
        _write_ledger_record(session_id, "francisca-tech", seq=1)
        _write_ledger_record(session_id, "eduardo-copy", seq=2)

    def _stamp_at(self, session_id, when: float):
        import os

        from core.governance.reviewer_ledger import ENDED_NAME

        stamp = ledger_root() / session_id / ENDED_NAME
        stamp.touch()
        os.utime(stamp, (when, when))

    def test_record_captured_after_stamp_lifts_refusal(self, guard_home):
        import time

        self._quorum("sess-m4a")
        self._stamp_at("sess-m4a", time.time() - 3600)
        result = check_aggregate(_aggregate(), "sess-m4a")
        assert result.ok

    def test_records_predating_stamp_still_refused(self, guard_home):
        import os
        import time

        self._quorum("sess-m4b")
        past = time.time() - 3600
        for item in (ledger_root() / "sess-m4b").iterdir():
            os.utime(item, (past, past))
        self._stamp_at("sess-m4b", time.time())
        result = check_aggregate(_aggregate(), "sess-m4b")
        assert not result.ok
        assert any(
            "not a reusable quorum token" in r for r in result.reasons
        )

    def test_newest_record_decides_with_mixed_ages(self, guard_home):
        """One record predates the stamp, one postdates it: the NEWEST
        decides (this is the pin that kills a max→min mutant — with
        uniform ages the two are indistinguishable)."""
        import os
        import time

        self._quorum("sess-m4d")
        session_dir = ledger_root() / "sess-m4d"
        now = time.time()
        ages = [now - 7200, now]  # one old, one fresh
        for item, when in zip(
            sorted(session_dir.iterdir()), ages, strict=True
        ):
            os.utime(item, (when, when))
        self._stamp_at("sess-m4d", now - 3600)  # stamp between them
        result = check_aggregate(_aggregate(), "sess-m4d")
        assert result.ok

    def test_mtime_tie_keeps_the_refusal(self, guard_home):
        """Equality cannot distinguish before from after — fail-closed."""
        import os
        import time

        self._quorum("sess-m4c")
        now = time.time()
        for item in (ledger_root() / "sess-m4c").iterdir():
            os.utime(item, (now, now))
        self._stamp_at("sess-m4c", now)
        result = check_aggregate(_aggregate(), "sess-m4c")
        assert not result.ok

    def test_ghost_artifact_keeps_the_refusal(self, guard_home):
        """The OSError path: a counted name that vanished between the
        listing and the stat cannot prove liveness — fail-closed."""
        from core.governance.aggregate_guard import _ended_issues

        self._quorum("sess-m4e")
        self._stamp_at("sess-m4e", 0)  # ancient stamp — records ARE newer
        issues = _ended_issues("sess-m4e", ["ghost.json"])
        assert issues, "an unreadable record set must keep the refusal"

    def test_stamp_is_chmod_0600(self, guard_home):
        """M11 pin: mark_session_ended tightens the stamp to 0600 —
        defence-in-depth under the 0700 session dir, and this pin is
        what kills the chmod-removal mutant."""
        import stat

        from core.governance.reviewer_ledger import (
            ENDED_NAME,
            mark_session_ended,
        )

        self._quorum("sess-m11")
        mark_session_ended("sess-m11")
        stamp = ledger_root() / "sess-m11" / ENDED_NAME
        assert stat.S_IMODE(stamp.stat().st_mode) == 0o600


class TestBlockerReasonBranches:
    """M12 (PR-B5): the previously unexercised _blocker_reasons paths."""

    def test_non_dict_blockers_are_skipped(self, guard_home):
        """A malformed blocker entry (string, int) never produces a
        coverage reason and never crashes the guard."""
        _write_ledger_record(
            "sess-m12a", "francisca-tech", seq=1,
            verdict=_reviewer_verdict(
                "francisca-tech", blockers=["just a string", 42]
            ),
        )
        _write_ledger_record("sess-m12a", "eduardo-copy", seq=2)
        result = check_aggregate(_aggregate(), "sess-m12a")
        assert result.ok

    def test_refuted_and_plausible_blockers_never_bind(self, guard_home):
        """Only CONFIRMED binds coverage — REFUTED/PLAUSIBLE entries
        (telemetry, not findings) leave an APPROVED aggregate alone."""
        blockers = [
            {
                "check": "lint", "detail": "refuted claim",
                "file": "a.py", "verdict": "REFUTED",
            },
            {
                "check": "tests", "detail": "plausible claim",
                "file": "b.py", "verdict": "PLAUSIBLE",
            },
        ]
        _write_ledger_record(
            "sess-m12b", "francisca-tech", seq=1,
            verdict=_reviewer_verdict("francisca-tech", blockers=blockers),
        )
        _write_ledger_record("sess-m12b", "eduardo-copy", seq=2)
        result = check_aggregate(_aggregate(), "sess-m12b")
        assert result.ok
