"""core.governance.qg_prescreen — the advisory Jev prescreen (JEV PR3, site #9).

Network is mocked at ``urlopen``; no test reaches OpenRouter. The central
invariant: the reviewer list is the tier's on every Jev path.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from _decisions_helpers import fake_ok, isolate_decisions, sent_payload, write_config

from core.decisions.sites.quality import BLOCKERS, MAX_DIFF_CHARS
from core.governance import qg_prescreen as qp
from core.governance import reviewer_ledger as rl
from core.governance.qg_tier import FULL_REVIEWERS, compute_tier, dispatch_reviewers

URLOPEN = "core.decisions.client.urllib.request.urlopen"
SESSION = "sess-prescreen-1"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@example.invalid", "-c", "user.name=t", *args],
        cwd=repo, check=True, capture_output=True,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "core" / "governance").mkdir(parents=True)
    (root / "core" / "governance" / "gate.py").write_text("X = 1\n", encoding="utf-8")
    _git(root, "init", "-q", "-b", "master")
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "base")
    (root / "core" / "governance" / "gate.py").write_text("X = 2\nY = 3\n", encoding="utf-8")
    (root / "notes.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    return root


@pytest.fixture
def jev(monkeypatch, tmp_path):
    """Jev isolated, the site in ``act`` by operator override (default: shadow)."""
    home = isolate_decisions(monkeypatch, tmp_path)
    write_config(home, {"sites": {"qg-prescreen": "act"}})
    return home


def _verdict(
    verdict: str, blocker: str = "none", conf: float = 0.9, blocker_conf: float | None = None
) -> object:
    return fake_ok({
        "qg_prescreen__likely_verdict": {"type": "choice", "choice": verdict, "confidence": conf},
        "qg_prescreen__blocker_class": {
            "type": "choice", "choice": blocker,
            "confidence": conf if blocker_conf is None else blocker_conf},
    })


# --- chunking ---------------------------------------------------------------

def test_a_60k_diff_is_three_requests_each_under_the_cap(jev, tmp_path):
    root = tmp_path / "big"
    root.mkdir()
    _git(root, "init", "-q", "-b", "master")
    (root / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "base")
    (root / "big.py").write_text("".join(f"V_{i:06d} = {i}  # pad pad pad\n"
                                         for i in range(2000)), encoding="utf-8")
    diff = qp.file_diff(root, "HEAD", "big.py")
    assert len(diff) >= 60_000
    with patch(URLOPEN, return_value=_verdict("approved")) as net:
        report = qp.run_prescreen(root, ["big.py"], SESSION)
    states = [sent_payload(net, i)["state"]["diff"] for i in range(net.call_count)]
    assert net.call_count == report["requests"] == len(qp.chunk_diff("big.py", diff)) == 3
    assert all(len(s) <= MAX_DIFF_CHARS for s in states)
    assert all("[truncated]" not in s for s in states)  # no chunk was cut by diff_state
    bodies = [s.split("\n", 1)[1] for s in states]
    head = "diff --git a/big.py b/big.py\n"
    assert all(b.startswith(head) for b in bodies)  # finding 52: every chunk names its file
    assert bodies[0] + "".join(b[len(head):] for b in bodies[1:]) == diff  # nothing lost


def test_chunks_cut_between_lines_and_a_huge_line_keeps_only_its_head():
    # Security review PR3, finding 35: a line longer than a chunk used to be
    # hard-split across two requests, each half of a token unrecognisable to
    # the privacy checks. Now its head is cut on whitespace, the tail dropped.
    diff = "a\n" * 10 + "x " * 25_000 + "\n"
    chunks = qp.chunk_diff("f.py", diff)
    assert all(len(c) <= MAX_DIFF_CHARS for c in chunks)
    assert len(chunks) == 2 and chunks[0].startswith("# file: f.py part 1/2")
    body = "".join(c.split("\n", 1)[1] for c in chunks)
    assert body.startswith("a\n" * 10 + "x x ") and body.endswith(qp.LINE_CUT)
    assert len(body) < len(diff)


def test_empty_diff_has_no_chunks():
    assert qp.chunk_diff("f.py", "") == []


# --- aggregation ------------------------------------------------------------

def _p(verdict: str, blockers: set[str] | None = None, p: float | None = 0.8) -> qp.Prediction:
    return qp.Prediction(verdict, blockers or set(), p, True, ["jev"])


def test_rejected_wins_with_the_union_of_blockers_and_max_p():
    folded = qp.fold([_p("approved", p=0.95), _p("rejected", {"tests"}, 0.7),
                      _p("rejected", {"security"}, 0.9)])
    assert (folded.verdict, folded.blockers, folded.p) == ("rejected", {"tests", "security"}, 0.9)


def test_approved_needs_every_part_and_takes_the_min_p():
    assert qp.fold([_p("approved", p=0.9), _p("approved", p=0.8)]).p == 0.8
    assert qp.fold([_p("approved"), qp.Prediction(reasons=["abstain"])]).verdict == "unknown"


def test_file_and_session_fold_the_same_way():
    files = [qp.fold([_p("approved"), _p("rejected", {"lint"})]), qp.fold([_p("approved")])]
    assert qp.fold(files).verdict == "rejected" and qp.fold(files).blockers == {"lint"}


def test_rejected_report_names_every_blocker(jev, repo):
    def answer(request, timeout):  # urlopen signature
        body = json.loads(request.data.decode("utf-8"))["state"]["diff"]
        return _verdict("rejected", "security") if "gate.py" in body else _verdict("approved")

    with patch(URLOPEN, side_effect=answer):
        report = qp.run_prescreen(repo, ["core/governance/gate.py", "notes.py"], SESSION)
    assert (report["verdict"], report["blocker"], report["source"]) == (
        "rejected", "security", "jev")
    assert report["marker"] == (
        "[arka:qg-prescreen] verdict=rejected blocker=security p=0.90 blocker_p=0.90 "
        "source=jev")
    assert {r["file"]: r["verdict"] for r in report["files"]} == {
        "core/governance/gate.py": "rejected", "notes.py": "approved"}


# --- the reviewer list is the tier's on every path -----------------------------

CHANGED = ["core/governance/gate.py", "notes.py"]


def _run_under(response: object | None, repo: Path, monkeypatch, bypass: bool) -> dict:
    if bypass:
        monkeypatch.setenv("ARKA_BYPASS_DECISIONS", "1")
    with patch(URLOPEN, return_value=response, side_effect=None if response else OSError):
        return qp.run_prescreen(repo, CHANGED, SESSION)


# path → (Jev response, bypass, the prediction that proves the path was taken)
PATHS = {
    "unavailable": (None, False, ("unknown", "unavailable:")),
    "abstains": (("rejected", "tests", 0.3), False, ("unknown", "unavailable:abstain")),
    "hostile": (("rejected", "security", 0.99), False, ("rejected", None)),
    "approves": (("approved", "none", 0.99), False, ("approved", None)),
    "bypassed": (("rejected", "security", 0.99), True, ("unknown", "bypass")),
}


@pytest.mark.parametrize("path", sorted(PATHS))
def test_reviewer_list_is_identical_on_every_jev_path(jev, repo, monkeypatch, path):
    baseline = dispatch_reviewers(compute_tier(repo, CHANGED))
    assert baseline == list(FULL_REVIEWERS)  # sensitive surface → FULL
    answer, bypass, (verdict, skipped) = PATHS[path]
    report = _run_under(_verdict(*answer) if answer else None, repo, monkeypatch, bypass)
    assert report["verdict"] == verdict  # the path really was taken
    assert (report["skipped"] or "").startswith(skipped or "") and bool(skipped) == bool(
        report["skipped"])
    assert report["reviewers"] == baseline


@pytest.mark.parametrize("blocker", sorted(BLOCKERS))
def test_a_hostile_jev_on_any_blocker_class_keeps_the_reviewers(jev, repo, monkeypatch, blocker):
    """QG r1 m1: a reviewer mapping keyed on ONE class (``spellcheck`` →
    ``['eduardo-copy']``) must die, not only the ``security`` path above."""
    baseline = dispatch_reviewers(compute_tier(repo, CHANGED))
    report = _run_under(_verdict("rejected", blocker, 0.99), repo, monkeypatch, False)
    assert (report["verdict"], report["blocker"]) == ("rejected", blocker)
    assert report["reviewers"] == baseline == list(FULL_REVIEWERS)


def test_prescreen_budget_and_chunk_cap_are_pinned():
    """QG r1 m2: literals, never the constants compared with themselves."""
    assert qp.PRESCREEN_TOTAL_MS == 20_000
    assert MAX_DIFF_CHARS == 24_000 and qp.MAX_DIFF_CHARS == 24_000


def test_light_tier_keeps_its_single_reviewer_when_jev_is_hostile(jev, tmp_path, monkeypatch):
    root = tmp_path / "light"
    root.mkdir()
    _git(root, "init", "-q", "-b", "master")
    (root / "app.py").write_text("A = 1\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "base")
    (root / "app.py").write_text("A = 2\n", encoding="utf-8")
    for answer in (("rejected", "security", 0.99), ("approved", "none", 0.99)):
        monkeypatch.setenv("ARKA_DECISIONS_CACHE_DIR", str(tmp_path / f"cache-{answer[0]}"))
        with patch(URLOPEN, return_value=_verdict(*answer)):
            report = qp.run_prescreen(root, ["app.py"], SESSION)
        assert report["tier"] == "LIGHT" and report["reviewers"] == ["francisca-tech"]
        assert report["verdict"] == answer[0]


def test_dispatch_reviewers_fails_closed_to_the_pair():
    assert dispatch_reviewers({"tier": "FULL", "reviewer": None}) == list(FULL_REVIEWERS)
    assert dispatch_reviewers({"tier": "LIGHT", "reviewer": "eduardo-copy"}) == ["eduardo-copy"]
    assert dispatch_reviewers({"tier": "LIGHT", "reviewer": "someone"}) == list(FULL_REVIEWERS)
    assert dispatch_reviewers({}) == list(FULL_REVIEWERS)


# --- skips ------------------------------------------------------------------

def test_bypass_skips_with_no_network(repo, monkeypatch):
    monkeypatch.setenv("ARKA_BYPASS_DECISIONS", "1")
    with patch(URLOPEN) as net:
        report = qp.run_prescreen(repo, CHANGED, SESSION)
    net.assert_not_called()
    assert report["marker"] == "[arka:qg-prescreen] skipped reason=bypass"
    assert report["requests"] == 0


def test_missing_redaction_list_skips_with_no_network(jev, repo):
    (jev / ".arkaos" / "redaction-clients.json").unlink()
    with patch(URLOPEN) as net:
        report = qp.run_prescreen(repo, CHANGED, SESSION)
    net.assert_not_called()
    assert report["marker"] == "[arka:qg-prescreen] skipped reason=redaction-config-missing"


def test_unavailable_jev_is_a_skip_with_the_reason(jev, repo):
    with patch(URLOPEN, side_effect=OSError("down")):
        report = qp.run_prescreen(repo, CHANGED, SESSION)
    assert report["marker"].startswith("[arka:qg-prescreen] skipped reason=unavailable:")
    assert report["verdict"] == "unknown" and report["source"] == "neutral"


def test_spent_budget_stops_asking(jev, repo, monkeypatch):
    monkeypatch.setattr(qp, "PRESCREEN_TOTAL_MS", 0)
    with patch(URLOPEN) as net:
        report = qp.run_prescreen(repo, CHANGED, SESSION)
    net.assert_not_called()
    assert report["skipped"] == "unavailable:deadline"


@pytest.mark.parametrize("name", [".git/config", ".GIT/config", ".Git/config"])
def test_git_metadata_is_never_sent_in_any_case(jev, repo, name):
    # Security review PR3, finding 40: on APFS ``.GIT/config`` opens
    # ``.git/config``. The canary is no credential shape, so only the read
    # path keeps it out. Kills: the finding 40 fix reverted (on APFS the
    # case-folded part test and the inode comparison each refuse alone).
    with (repo / ".git" / "config").open("a", encoding="utf-8") as fh:
        fh.write("[remote \"origin\"]\n\turl = https://git.example.invalid/CANARY-GIT-40\n")
    with patch(URLOPEN, return_value=_verdict("APPROVED")) as net:
        qp.run_prescreen(repo, [name], SESSION)
    bodies = "".join(json.dumps(sent_payload(net, i)) for i in range(net.call_count))
    assert "CANARY-GIT-40" not in bodies


# --- PRESCREEN.json and the ledger name contract ------------------------------

def test_prescreen_json_lands_in_the_session_ledger(jev, repo):
    with patch(URLOPEN, return_value=_verdict("rejected", "tests")):
        report = qp.run_prescreen(repo, CHANGED, SESSION)
    path = qp.write_prescreen(SESSION, report)
    assert path == rl.ledger_root() / SESSION / rl.PRESCREEN_NAME
    assert json.loads(path.read_text(encoding="utf-8"))["verdict"] == "rejected"
    assert qp.read_prescreen(SESSION) == {
        "verdict": "rejected", "blocker": "tests", "p": 0.9, "source": "jev"}


def test_hostile_session_id_writes_nothing(jev):
    assert qp.write_prescreen("../escape", {"verdict": "approved"}) is None
    assert qp.read_prescreen("../escape") is None


def test_prescreen_name_is_owned_and_never_a_reviewer_record():
    assert rl.PRESCREEN_NAME == "PRESCREEN.json"
    assert not rl._RECORD_NAME_RE.fullmatch(rl.PRESCREEN_NAME)
    assert rl.PRESCREEN_NAME not in {rl.AGGREGATE_NAME, rl.ENDED_NAME}


def test_retention_purges_a_session_holding_prescreen(jev):
    import os

    path = qp.write_prescreen(SESSION, {"verdict": "approved"})
    assert path is not None and rl._is_own_file(path)
    old = 1_000_000_000  # 2001: far past any retention window
    os.utime(path.parent, (old, old))
    assert rl.sweep_expired(days=90) == 1
    assert not path.parent.exists()


def test_aggregate_guard_pool_ignores_prescreen(jev):
    from core.governance.aggregate_guard import _session_records

    qp.write_prescreen(SESSION, {"verdict": "approved"})
    assert _session_records(SESSION) == []


# --- CLI --------------------------------------------------------------------

def test_cli_json_and_marker(jev, repo, capsys):
    with patch(URLOPEN, return_value=_verdict("approved", conf=0.95)):
        assert qp.main([str(repo), "--changed-files", ",".join(CHANGED),
                        "--session-id", SESSION, "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["advisory"] is True and report["reviewers"] == list(FULL_REVIEWERS)
    assert report["prescreen_path"].endswith(f"{SESSION}/PRESCREEN.json")
    with patch(URLOPEN, return_value=_verdict("approved", conf=0.95)):
        assert qp.main([str(repo), "--changed-files", CHANGED[0],
                        "--changed-files", CHANGED[1]]) == 0
    first = capsys.readouterr().out.splitlines()[0]
    assert first == (
        "[arka:qg-prescreen] verdict=approved blocker=none p=0.95 blocker_p=- source=jev")


def test_verdict_label_envelope_carries_the_prescreen(jev, tmp_path, monkeypatch):
    from core.evals.verdict_labels import load_verdict_labels, record_verdict_label
    from core.governance.qg_verdict import QGVerdict

    monkeypatch.setenv("ARKA_QG_LABELS_PATH", str(tmp_path / "qg-verdicts.jsonl"))
    qp.write_prescreen(SESSION, {"verdict": "rejected", "blocker": "lint", "p": 0.8,
                                 "source": "jev", "skipped": None})
    verdict = QGVerdict.model_validate({
        "verdict": "APPROVED", "evidence_report": {"overall": "pass"},
        "reviewer": "marta-cqo", "model_used": "x"})
    record_verdict_label(verdict, session_id=SESSION)
    record_verdict_label(verdict, session_id="no-prescreen-session")
    first, second = load_verdict_labels()
    assert first["prescreen"] == {"verdict": "rejected", "blocker": "lint", "p": 0.8,
                                  "source": "jev"}
    assert second["prescreen"] is None


# --- p is the verdict's own confidence; shadow is the default ----------------------

def test_p_is_the_verdict_confidence_and_blocker_p_the_blockers(jev, repo):
    # The engine's Outcome.confidence is the minimum across both answers
    # (0.40 here): p must not inherit an unsure blocker.
    with patch(URLOPEN, return_value=_verdict("rejected", "tests", 0.92, blocker_conf=0.40)):
        report = qp.run_prescreen(repo, CHANGED, SESSION)
    assert (report["verdict"], report["blocker"]) == ("rejected", "none")
    assert (report["p"], report["blocker_p"]) == (0.92, 0.4)
    assert report["marker"] == (
        "[arka:qg-prescreen] verdict=rejected blocker=none p=0.92 blocker_p=0.40 source=jev")


def test_a_config_without_the_key_runs_the_prescreen_in_shadow(monkeypatch, tmp_path, repo):
    isolate_decisions(monkeypatch, tmp_path)  # no decisions.sites.qg-prescreen
    spawned: list[str] = []
    monkeypatch.setattr("core.decisions.engine.spawn_shadow",
                        lambda calls, state, sid: spawned.append(calls[0].site.name) or True)
    with patch(URLOPEN) as net:
        report = qp.run_prescreen(repo, CHANGED, SESSION)
    net.assert_not_called()  # detached: the hook path sends nothing itself
    assert spawned and set(spawned) == {"qg-prescreen"}
    assert report["skipped"] == "shadow" and report["verdict"] == "unknown"
    assert report["marker"] == "[arka:qg-prescreen] skipped reason=shadow"
    assert report["reviewers"] == dispatch_reviewers(compute_tier(repo, CHANGED))


def test_a_shadow_outcome_carrying_jevs_value_is_marked_shadow():
    from core.decisions.models import Answer
    from core.decisions.site import Outcome

    value = {"verdict": "rejected", "blocker": "lint", "blocker_p": 0.81}
    outcome = Outcome(
        value=qp.prescreen_heuristic(), heuristic=qp.prescreen_heuristic(), jev=value,
        confidence=0.5, mode="shadow", acted_on="heuristic", reason="shadow",
        answers={"likely_verdict": Answer(type="choice", choice="rejected", confidence=0.88)})
    pred = qp._from_outcome(outcome)
    assert (pred.verdict, pred.blockers, pred.p, pred.blocker_p, pred.shadow) == (
        "rejected", {"lint"}, 0.88, 0.81, True)
    report = qp._report({"tier": "FULL"}, qp.fold([pred]), None, [], 1)
    assert report["marker"] == (
        "[arka:qg-prescreen] shadow verdict=rejected blocker=lint p=0.88 blocker_p=0.81 "
        "source=jev")


def test_a_shadow_prescreen_envelope_says_so(jev):
    qp.write_prescreen(SESSION, {"verdict": "approved", "blocker": "none", "p": 0.9,
                                 "source": "jev", "shadow": True, "skipped": None})
    assert qp.read_prescreen(SESSION)["source"] == "shadow:jev"
