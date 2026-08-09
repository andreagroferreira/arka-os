"""Mechanical carry advisor (Gate Economy PR-3) — every edge fails
closed to re-dispatch; only a provably untouched domain carries."""

from __future__ import annotations

import json

import pytest

from core.governance.aggregate_guard import ledger_root
from core.governance.carry_advisor import (
    carry_candidates,
    delta_kind,
    main,
)

DIGEST_A = "a" * 64


@pytest.fixture()
def advisor_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


def _write_artifact(
    session_id: str,
    reviewer_id: str,
    verdict: str = "APPROVED",
    digest: str = DIGEST_A,
    seq: int = 1,
) -> None:
    session_dir = ledger_root() / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    body = {
        "verdict": verdict,
        "evidence_report": {
            "overall": "pass" if verdict == "APPROVED" else "fail"
        },
        "reviewer": reviewer_id,
        "model_used": "opus",
        "blockers": [],
    }
    if digest:
        body["evidence_digest"] = digest
    record = {
        "session_id": session_id,
        "reviewer_id": reviewer_id,
        "seq": seq,
        "ts": f"2026-08-09T00:0{seq}:00+00:00",
        "source": "subagent-stop",
        "parse_error": None,
        "verdict": body,
        "raw_output": "captured review text",
    }
    (session_dir / f"{reviewer_id}-{seq}-{'0' * 8}.json").write_text(
        json.dumps(record), encoding="utf-8"
    )


def _quorum(session_id: str, **kwargs) -> None:
    _write_artifact(session_id, "francisca-tech", **kwargs)
    _write_artifact(session_id, "eduardo-copy", seq=2, **kwargs)


class TestDeltaKind:
    def test_pure_code(self):
        assert delta_kind(["core/x.py", "app/y.vue"]) == "code"

    def test_pure_prose(self):
        assert delta_kind(["docs/a.md", "README.txt"]) == "prose"

    def test_mixed_is_mixed(self):
        assert delta_kind(["core/x.py", "docs/a.md"]) == "mixed"

    def test_unknown_suffix_fails_closed(self):
        assert delta_kind(["config/settings.yaml"]) == "mixed"

    def test_empty_delta_fails_closed(self):
        assert delta_kind([]) == "mixed"


class TestCarryCandidates:
    def test_pure_code_delta_carries_eduardo_only(self, advisor_home):
        _quorum("sess-ca-1")
        result = carry_candidates("sess-ca-1", ["core/governance/x.py"])
        carried = {c["reviewer"] for c in result["carries"]}
        redo = {r["reviewer"] for r in result["re_dispatch"]}
        assert carried == {"eduardo-copy"}
        assert redo == {"francisca-tech"}

    def test_pure_prose_delta_carries_francisca_only(self, advisor_home):
        _quorum("sess-ca-2")
        result = carry_candidates("sess-ca-2", ["docs/guide.md"])
        carried = {c["reviewer"] for c in result["carries"]}
        assert carried == {"francisca-tech"}

    def test_mixed_delta_carries_nobody(self, advisor_home):
        _quorum("sess-ca-3")
        result = carry_candidates(
            "sess-ca-3", ["core/x.py", "docs/a.md"]
        )
        assert result["carries"] == []
        assert len(result["re_dispatch"]) == 2

    def test_rejected_artifact_never_carries(self, advisor_home):
        _write_artifact(
            "sess-ca-4", "eduardo-copy", verdict="REJECTED"
        )
        result = carry_candidates("sess-ca-4", ["core/x.py"])
        assert result["carries"] == []
        assert "never carries" in result["re_dispatch"][0]["why"]

    def test_digest_less_artifact_never_carries(self, advisor_home):
        _write_artifact("sess-ca-5", "eduardo-copy", digest="")
        result = carry_candidates("sess-ca-5", ["core/x.py"])
        assert result["carries"] == []
        assert "no evidence_digest" in result["re_dispatch"][0]["why"]

    def test_carry_shape_matches_digest_carry_contract(self, advisor_home):
        _quorum("sess-ca-6")
        result = carry_candidates("sess-ca-6", ["core/x.py"])
        carry = result["carries"][0]
        assert set(carry) == {"reviewer", "evidence_digest", "reason"}
        assert carry["evidence_digest"] == DIGEST_A
        assert len(carry["reason"]) >= 40

    def test_hostile_session_id_yields_empty(self, advisor_home):
        result = carry_candidates("../evil", ["core/x.py"])
        assert result["carries"] == []
        assert result["re_dispatch"] == []

    def test_latest_artifact_wins(self, advisor_home):
        _write_artifact(
            "sess-ca-7", "eduardo-copy", verdict="REJECTED", seq=1
        )
        _write_artifact(
            "sess-ca-7", "eduardo-copy", verdict="APPROVED", seq=2
        )
        result = carry_candidates("sess-ca-7", ["core/x.py"])
        assert {c["reviewer"] for c in result["carries"]} == {
            "eduardo-copy"
        }


class TestCli:
    def test_cli_prints_json(self, advisor_home, capsys):
        _quorum("sess-ca-cli")
        assert main(
            ["sess-ca-cli", "--delta-files", "core/x.py,core/y.py"]
        ) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["delta_kind"] == "code"
        assert {c["reviewer"] for c in payload["carries"]} == {
            "eduardo-copy"
        }
