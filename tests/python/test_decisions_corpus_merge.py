"""scripts/tools/corpus_merge.py — consensus, arbitration, filters, floors, reproducibility."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from core.decisions.replay import ReplayCase

MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "tools" / "corpus_merge.py"
SOURCE_A, SOURCE_B = "handwritten-A", "handwritten-B"


@pytest.fixture(scope="module")
def cm() -> ModuleType:
    spec = importlib.util.spec_from_file_location("corpus_merge", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["corpus_merge"] = module
    spec.loader.exec_module(module)
    return module


def _write(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                    encoding="utf-8")


def _prompt(i: int, lang: str) -> str:
    return f"pedido {lang} número {i} sobre o módulo m{i} com critério c{i}"


# One training prompt per held-out site, far from every fixture held-out prompt.
TRAINING = {"learning-signal": ("ls-t1", "prefiro respostas curtas", "explicit"),
            "qg-prescreen": ("qg-t1", "+print('debug')\n", ["approved", "none"]),
            "slop-score": ("sl-t1", "um parágrafo sem floreados", [8, 8, 8, 8, 8])}


def _fixture(root: Path, *, disagree: bool = False) -> dict[str, Path]:
    """A tiny shipped corpus pair and a relabel dir (4 seed, 6 new per site).

    The held-out sites get a one-case training corpus each, the file
    ``merge_heldout`` checks every held-out case against.
    """
    shipped = {"refine": root / "corpora" / "refine.jsonl",
               "forge-complexity": root / "corpora" / "forge-complexity.jsonl"}
    for site, (case_id, prompt, expected) in TRAINING.items():
        shipped[site] = root / "corpora" / f"{site}.jsonl"
        _write(shipped[site], [{"id": case_id, "lang": "pt", "prompt": prompt,
                                "expected": expected}])
    seed = [{"id": f"s{i}", "lang": "pt", "prompt": _prompt(i, "pt"), "expected": False}
            for i in range(4)]
    _write(shipped["refine"], seed)
    _write(shipped["forge-complexity"], [{**r, "expected": "STANDARD"} for r in seed])
    rel = root / "relabel"
    _write(rel / "A" / "refine.A.jsonl", [{"id": r["id"], "label": "scope"} for r in seed])
    b_gap = "acceptance" if disagree else "scope"
    _write(rel / "B" / "refine.B.jsonl",
           [{"id": r["id"], "label": True, "gap": b_gap} for r in seed])
    _write(rel / "A" / "forge-complexity.A.jsonl",
           [{"id": r["id"], "tier": "SHALLOW"} for r in seed])
    _write(rel / "B" / "forge-complexity.B.jsonl",
           [{"id": r["id"], "label": "SHALLOW"} for r in seed])
    _new(rel)
    _heldout(rel)
    return shipped


def _new(rel: Path) -> None:
    for labeller, source, offset in (("A", SOURCE_A, 10), ("B", SOURCE_B, 20)):
        rows = [{"id": f"n{labeller}{i}", "lang": "pt" if i % 3 else "en",
                 "prompt": _prompt(offset + i, labeller), "source": source} for i in range(3)]
        refine = [{**r, "label": "target"} if labeller == "A"
                  else {**r, "label": False, "gap": "none"} for r in rows]
        forge = [{**r, "tier": "DEEP"} if labeller == "A" else {**r, "label": "DEEP"}
                 for r in rows]
        _write(rel / labeller / f"refine.new.{labeller}.jsonl", refine)
        _write(rel / labeller / f"forge-complexity.new.{labeller}.jsonl", forge)


def _heldout(rel: Path, qg_lang: str = "pt") -> None:
    a = [{"site": "learning-signal", "id": "hA1", "lang": "pt", "prompt": "nunca faças commit",
          "label": {"signal": "explicit", "high_leverage": True}, "source": SOURCE_A},
         {"site": "qg-prescreen", "id": "hA2", "lang": qg_lang,
          # arka:sec-ok(hardcoded-password): fixture placeholder the merge rewrites
          "prompt": '+DB_PASSWORD = "hunter2"\n',  # arka:sec-ok(hardcoded-password): fixture
          "label": {"verdict": "rejected", "blocker": "security"}, "source": SOURCE_A},
         {"site": "slop-score", "id": "hA3", "lang": "pt", "prompt": "texto claro e curto",
          "label": {"directness": 9, "rhythm": 8, "trust": 9, "authenticity": 9,
                    "density": 9, "total": 44}, "source": SOURCE_A}]
    b = [{"site": "learning-signal", "id": "hB1", "lang": "pt", "prompt": "nunca faças commit",
          "label": "explicit", "source": SOURCE_B}]
    _write(rel / "A" / "heldout.A.jsonl", a)
    _write(rel / "B" / "heldout.B.jsonl", b)


@pytest.fixture
def repo(cm: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    shipped = _fixture(tmp_path)
    monkeypatch.setattr(cm, "default_corpus_path", lambda site: shipped[site])
    monkeypatch.setattr(cm, "heldout_corpus_path",
                        lambda site: tmp_path / "corpora" / "heldout" / f"{site}.jsonl")
    monkeypatch.setattr(cm, "load_redaction_patterns", lambda _path: ["acme corp"])
    return shipped


def test_merge_relabels_by_consensus_and_writes_heldout(cm: ModuleType, repo, tmp_path: Path):
    code, stats = cm.run(tmp_path / "relabel", check=False)
    assert code == 0 and stats["failures"] == []
    refine = [json.loads(line) for line in repo["refine"].read_text().splitlines()]
    assert [(r["expected"], r.get("gap"), r["source"]) for r in refine[:4]] == [
        (True, "scope", "seed")] * 4
    assert {r["source"] for r in refine[4:]} == {SOURCE_A, SOURCE_B}
    forge = [json.loads(line) for line in repo["forge-complexity"].read_text().splitlines()]
    assert [r["expected"] for r in forge[:4]] == ["SHALLOW"] * 4
    held = tmp_path / "corpora" / "heldout"
    qg = [json.loads(line) for line in (held / "qg-prescreen.jsonl").read_text().splitlines()]
    got = qg[0]["prompt"]
    assert got == '+DB_PASSWORD = "changeme"\n'  # arka:sec-ok(hardcoded-password): placeholder
    assert qg[0]["expected"] == ["rejected", "security"]
    ls = (held / "learning-signal.jsonl").read_text().splitlines()
    assert len(ls) == 1, "B's near-duplicate of A's case is dropped"
    slop = json.loads((held / "slop-score.jsonl").read_text())
    assert slop["expected"] == [9, 8, 9, 9, 9]


def test_a_rerun_reproduces_the_files_byte_for_byte(cm: ModuleType, repo, tmp_path: Path):
    cm.run(tmp_path / "relabel", check=False)
    first = {p: p.read_bytes() for p in tmp_path.joinpath("corpora").rglob("*.jsonl")}
    assert cm.run(tmp_path / "relabel", check=False)[0] == 0
    assert {p: p.read_bytes() for p in first} == first


def test_check_writes_nothing(cm: ModuleType, repo, tmp_path: Path):
    before = repo["refine"].read_bytes()
    assert cm.run(tmp_path / "relabel", check=True)[0] == 0
    assert repo["refine"].read_bytes() == before
    assert not (tmp_path / "corpora" / "heldout").exists()


def test_unarbitrated_disagreement_is_an_error(cm: ModuleType, repo, tmp_path: Path):
    _fixture(tmp_path, disagree=True)
    with pytest.raises(cm.MergeError, match="unarbitrated"):
        cm.run(tmp_path / "relabel", check=True)
    assert cm.main(["--relabel", str(tmp_path / "relabel"), "--check"]) == 1


def test_the_operator_arbitration_settles_a_disagreement(cm: ModuleType):
    a, b = {"label": "scope"}, {"label": True, "gap": "acceptance"}
    assert cm.refine_consensus("rf-en-06", a, b) == (True, "target")
    assert cm.forge_consensus("forge-complexity-29", {"tier": "DEEP"},
                              {"label": "STANDARD"}) == "STANDARD"
    with pytest.raises(cm.MergeError, match="vague"):
        cm.refine_consensus("x", {"label": "none"}, {"label": True, "gap": "target"})


def test_floors_fail_the_merge(cm: ModuleType):
    stats = {"site": "refine", "new_share": 0.49, "pt_share": 0.54}
    assert len(cm.constraint_failures(stats)) == 2
    assert cm.constraint_failures({**stats, "new_share": 0.5, "pt_share": 0.55}) == []


@pytest.mark.parametrize(("share", "fails", "warns"), [
    (0.49, 1, 0),  # below the replay floor: the merge fails
    (0.5, 0, 1),  # exactly the floor (qg-prescreen today): a warning, not a failure
    (0.5499, 0, 1),
    (0.55, 0, 0),  # the target met: silent
])
def test_heldout_pt_share_floor_fails_and_target_warns(cm: ModuleType, share: float,
                                                       fails: int, warns: int):
    failures, warnings = cm.heldout_findings({"site": "qg-prescreen", "pt_share": share})
    assert (len(failures), len(warnings)) == (fails, warns)


def test_a_heldout_set_below_the_pt_floor_fails_the_run(cm: ModuleType, repo, tmp_path: Path):
    _heldout(tmp_path / "relabel", qg_lang="en")  # qg-prescreen held-out: 0 % pt-PT
    code, stats = cm.run(tmp_path / "relabel", check=True)
    assert code == 1
    assert any("qg-prescreen held-out" in f for f in stats["failures"])


def test_filters_drop_clients_secrets_and_near_duplicates(cm: ModuleType):
    merged = cm.Merged("refine")
    names_client = cm.client_matcher(["acme corp"])

    def case(i: str, prompt: str) -> ReplayCase:
        return ReplayCase(id=i, lang="pt", prompt=prompt, expected=True)

    for c in (case("keep", "corrige o formulário de contacto"),
              case("dup", "Corrige o formulario de contacto"),
              case("client", "melhora o site da ACME Corp"),
              case("secret", 'token = "ghp_' + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8" + '"')):
        cm.admit(merged, c, names_client)
    assert [c.id for c in merged.cases] == ["keep"]
    assert merged.dropped == {"near-duplicate": ["dup"], "client-name": ["client"],
                              "secret": ["secret"]}


def test_a_heldout_case_near_duplicating_training_is_dropped(cm: ModuleType, repo,
                                                             tmp_path: Path):
    """Spec D7: the held-out set never repeats its site's training corpus."""
    _write(repo["learning-signal"], [{"id": "ls-t1", "lang": "pt",
                                      "prompt": "Nunca faças commit!", "expected": "explicit"}])
    merged = cm.merge_heldout(tmp_path / "relabel", cm.client_matcher(["acme corp"]))
    assert merged["learning-signal"].cases == []
    assert merged["learning-signal"].dropped == {"duplicate-of-training": ["hA1", "hB1"]}
    assert [c.id for c in merged["slop-score"].cases] == ["hA3"], "far prompts are kept"


def test_admit_rejects_against_training_before_the_in_file_check(cm: ModuleType):
    merged = cm.Merged("learning-signal")
    case = ReplayCase(id="h1", lang="pt", prompt="Obrigado, ficou ótimo.", expected="none")
    cm.admit(merged, case, cm.client_matcher(["acme corp"]), ["obrigado ficou otimo!"])
    assert merged.cases == [] and merged.dropped == {"duplicate-of-training": ["h1"]}
    cm.admit(merged, case, cm.client_matcher(["acme corp"]), ["outra coisa qualquer"])
    assert [c.id for c in merged.cases] == ["h1"]


def test_no_client_patterns_refuses(cm: ModuleType, repo, tmp_path: Path,
                                    monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(cm, "load_redaction_patterns", lambda _path: [])
    assert cm.main(["--relabel", str(tmp_path / "relabel")]) == 2


def test_jaccard_is_case_and_accent_insensitive(cm: ModuleType):
    assert cm.jaccard("Atualiza a Configuração", "atualiza a configuracao") == 1.0
    assert cm.jaccard("", "") == 1.0
    assert cm.jaccard("a b", "c d") == 0.0
