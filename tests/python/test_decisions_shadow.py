"""core.decisions.shadow — detached worker, spool hygiene."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import time
from unittest.mock import patch

import pytest
from _decisions_helpers import fake_ok, isolate_decisions, read_jsonl

from core.decisions import shadow
from core.decisions.paths import repo_root, spool_dir
from core.decisions.site import SiteCall
from core.decisions.sites.prompt import ROUTE, TOPIC_DRIFT, prompt_state

POPEN = "core.decisions.shadow.subprocess.Popen"
URLOPEN = "core.decisions.client.urllib.request.urlopen"
STATE = prompt_state("agora prepara o email de lançamento", ["corrige o bug do login"])


@pytest.fixture
def home(monkeypatch, tmp_path):
    return isolate_decisions(monkeypatch, tmp_path)


def _calls():
    return [SiteCall(TOPIC_DRIFT, False), SiteCall(ROUTE, "")]


def _spool(payload: dict) -> str:
    spool_dir().mkdir(parents=True, exist_ok=True)
    path = spool_dir() / "job.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def test_spawn_spools_0600_and_detaches(home):
    with patch(POPEN) as pop:
        assert shadow.spawn_shadow(_calls(), STATE, "s1") is True
    (spooled,) = list(spool_dir().glob("*.json"))
    assert stat.S_IMODE(spooled.stat().st_mode) == 0o600
    data = json.loads(spooled.read_text(encoding="utf-8"))
    assert data["session_id"] == "s1" and data["state"] == STATE
    assert data["sites"] == [{"name": "topic-drift", "heuristic": False},
                             {"name": "route", "heuristic": ""}]
    args, kwargs = pop.call_args
    assert args[0] == [sys.executable, "-m", "core.decisions.shadow", str(spooled)]
    assert kwargs["start_new_session"] is True
    assert kwargs["stdin"] == kwargs["stdout"] == kwargs["stderr"] == subprocess.DEVNULL
    assert kwargs["env"]["PYTHONPATH"] == str(repo_root())


def test_spool_cap(home):
    spool_dir().mkdir(parents=True)
    for i in range(shadow.SPOOL_MAX_PENDING):
        (spool_dir() / f"{i}.json").write_text("{}", encoding="utf-8")
    with patch(POPEN) as pop:
        assert shadow.spawn_shadow(_calls(), STATE, "s") is False
    pop.assert_not_called()


def test_stale_orphans_do_not_block_shadow_forever(home):
    # Workers killed before their finally leave spools; with none alive
    # to sweep, 8 orphans used to disable shadow mode for good.
    # Kills: removing sweep_stale() from spawn_shadow.
    spool_dir().mkdir(parents=True)
    past = time.time() - shadow.STALE_SPOOL_S - 10
    for i in range(shadow.SPOOL_MAX_PENDING):
        orphan = spool_dir() / f"orphan{i}.json"
        orphan.write_text("{}", encoding="utf-8")
        os.utime(orphan, (past, past))
    with patch(POPEN) as pop:
        assert shadow.spawn_shadow(_calls(), STATE, "s") is True
    pop.assert_called_once()
    assert len(list(spool_dir().glob("*.json"))) == 1


def test_worker_refuses_symlink_escaping_spool(home, tmp_path):
    outside = tmp_path / "precious.json"
    outside.write_text("{}", encoding="utf-8")
    spool_dir().mkdir(parents=True)
    link = spool_dir() / "link.json"
    link.symlink_to(outside)
    assert shadow.main([str(link)]) == 2
    assert outside.exists()


def test_popen_argv_has_no_caller_input(home):
    # session_id and state travel in the 0600 spool, never on argv.
    with patch(POPEN) as pop:
        shadow.spawn_shadow(_calls(), STATE, "s; rm -rf ~")
    argv = pop.call_args.args[0]
    assert all("rm -rf" not in a and "lançamento" not in a for a in argv)
    assert argv[-1].endswith(".json") and len(argv) == 4


def test_popen_failure_cleans_spool(home):
    with patch(POPEN, side_effect=OSError("no fork")):
        assert shadow.spawn_shadow(_calls(), STATE, "s") is False
    assert list(spool_dir().glob("*.json")) == []


def test_spawn_edge_cases(home, tmp_path, monkeypatch):
    assert shadow.spawn_shadow([], STATE, "s") is False
    blocker = tmp_path / "f"
    blocker.write_text("x", encoding="utf-8")
    monkeypatch.setenv("ARKA_DECISIONS_CACHE_DIR", str(blocker))
    with patch(POPEN) as pop:
        assert shadow.spawn_shadow(_calls(), STATE, "s") is False
    pop.assert_not_called()


def test_worker_records_shadow_telemetry_and_deletes_spool(home, tmp_path):
    path = _spool({"session_id": "s9", "state": STATE,
                   "sites": [{"name": "topic-drift", "heuristic": False},
                             {"name": "ghost", "heuristic": 1}]})
    body = fake_ok({"topic_drift__topic_shift": {"noul": 0.96}})
    with patch(URLOPEN, return_value=body) as net:
        assert shadow.main([path]) == 0
    assert net.call_args.kwargs["timeout"] == shadow.SHADOW_TIMEOUT_S
    (row,) = read_jsonl(tmp_path / "decisions.jsonl")
    assert (row["mode"], row["site"], row["session_id"]) == ("shadow", "topic-drift", "s9")
    assert (row["jev_result"], row["heuristic_result"], row["agree"]) == (True, False, False)
    assert row["acted_on"] == "heuristic"
    assert not os.path.exists(path)


def test_worker_respects_models_yaml_decisions_model(home, monkeypatch):
    """The detached worker asks the SAME model the hook asks (models.yaml)."""
    from core.runtime import model_router

    cfg = model_router.ModelsConfig(decisions={"model": "typesafe/jev-2"})
    monkeypatch.setattr(model_router, "load_config", lambda *a, **k: (cfg, "user"))
    path = _spool({"session_id": "s10", "state": STATE,
                   "sites": [{"name": "topic-drift", "heuristic": False}]})
    body = fake_ok({"topic_drift__topic_shift": {"noul": 0.1}})
    with patch(URLOPEN, return_value=body) as net:
        assert shadow.main([path]) == 0
    sent = json.loads(net.call_args.args[0].data.decode("utf-8"))
    assert sent["model"] == "typesafe/jev-2"


def test_worker_without_transport_just_cleans(monkeypatch, tmp_path):
    isolate_decisions(monkeypatch, tmp_path, key=None)
    path = _spool({"state": "x", "sites": [{"name": "route", "heuristic": ""}]})
    with patch(URLOPEN) as net:
        assert shadow.main([path]) == 0
    net.assert_not_called()
    assert not os.path.exists(path)


def test_worker_swallows_corrupt_spool(home):
    spool_dir().mkdir(parents=True)
    path = spool_dir() / "bad.json"
    path.write_text("{nope", encoding="utf-8")
    assert shadow.main([str(path)]) == 0
    assert not path.exists()


def test_worker_refuses_paths_outside_spool(home, tmp_path):
    outside = tmp_path / "precious.json"
    outside.write_text("{}", encoding="utf-8")
    assert shadow.main([str(outside)]) == 2
    assert outside.exists()
    assert shadow.main([]) == 2


def test_sweep_removes_only_stale(home):
    spool_dir().mkdir(parents=True)
    old, fresh = spool_dir() / "old.json", spool_dir() / "fresh.json"
    for p in (old, fresh):
        p.write_text("{}", encoding="utf-8")
    past = time.time() - shadow.STALE_SPOOL_S - 10
    os.utime(old, (past, past))
    assert shadow.sweep_stale() == 1
    assert fresh.exists() and not old.exists()


def test_spool_chain_is_private(home, tmp_path, monkeypatch):
    # Kills: reverting to spool.mkdir(parents=True, mode=0o700) (parents
    # 0755) or dropping the chmod of a pre-existing loose spool.
    root = tmp_path / "fresh" / "cache"
    monkeypatch.setenv("ARKA_DECISIONS_CACHE_DIR", str(root))
    old = os.umask(0o022)
    try:
        with patch(POPEN):
            assert shadow.spawn_shadow(_calls(), STATE, "s") is True
    finally:
        os.umask(old)
    for d in (tmp_path / "fresh", root, spool_dir()):
        assert stat.S_IMODE(d.stat().st_mode) == 0o700, d
    os.chmod(spool_dir(), 0o755)
    with patch(POPEN):
        shadow.spawn_shadow(_calls(), STATE, "s")
    assert stat.S_IMODE(spool_dir().stat().st_mode) == 0o700
