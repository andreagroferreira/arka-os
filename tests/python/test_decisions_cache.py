"""core.decisions.cache — responses only, atomic, 0600, TTL."""

from __future__ import annotations

import stat

import pytest

from core.decisions import cache
from core.decisions.models import Answer, DecisionResponse, Question

Q = {"a__b": Question(type="noul", instructions="x")}


@pytest.fixture(autouse=True)
def _root(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKA_DECISIONS_CACHE_DIR", str(tmp_path / "c"))
    return tmp_path / "c"


def _resp() -> DecisionResponse:
    return DecisionResponse(model="jev", answers={"a__b": Answer(noul=0.9)})


def test_key_is_deterministic_and_order_independent():
    k1 = cache.cache_key("m", {"a": 1, "b": 2}, Q)
    k2 = cache.cache_key("m", {"b": 2, "a": 1}, Q)
    assert k1 == k2 and len(k1) == 64
    assert cache.cache_key("other", {"a": 1, "b": 2}, Q) != k1
    other_q = {"a__b": Question(type="noul", instructions="y")}
    assert cache.cache_key("m", {"a": 1, "b": 2}, other_q) != k1


def test_roundtrip_layout_and_mode(_root):
    key = cache.cache_key("m", "secret prompt text", Q)
    assert cache.put(key, _resp(), now=100.0) is True
    path = _root / key[:2] / f"{key}.json"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert "secret prompt text" not in path.read_text(encoding="utf-8")
    got = cache.get(key, 60, now=150.0)
    assert got is not None and got.answers["a__b"].noul == 0.9


def test_expired_and_zero_ttl_miss():
    key = cache.cache_key("m", "s", Q)
    cache.put(key, _resp(), now=0.0)
    assert cache.get(key, 60, now=61.0) is None
    assert cache.get(key, 0, now=0.0) is None


def test_corrupt_entry_is_miss(_root):
    key = cache.cache_key("m", "s", Q)
    cache.put(key, _resp())
    (_root / key[:2] / f"{key}.json").write_text("{nope", encoding="utf-8")
    assert cache.get(key, 60) is None


@pytest.mark.parametrize("key", ["../../etc/passwd", "ABC", ""])
def test_foreign_keys_rejected(key):
    assert cache.put(key, _resp()) is False
    assert cache.get(key, 60) is None


def test_unwritable_root_is_false(tmp_path, monkeypatch):
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")
    monkeypatch.setenv("ARKA_DECISIONS_CACHE_DIR", str(blocker))
    assert cache.put(cache.cache_key("m", "s", Q), _resp()) is False


def test_full_path_never_writes_the_state_to_disk(tmp_path, monkeypatch):
    # End to end through engine.run_sync: every file the layer writes
    # under the cache root (entry, backoff, notices) is grepped for a
    # unique marker from the state. Kills: caching the request (or the
    # prepared state) next to the response.
    from unittest.mock import patch

    from _decisions_helpers import fake_ok, isolate_decisions

    from core.decisions.config import load_decisions_config
    from core.decisions.engine import run_sync
    from core.decisions.site import SiteCall
    from core.decisions.sites.prompt import TOPIC_DRIFT
    from core.decisions.transport import resolve_transport

    isolate_decisions(monkeypatch, tmp_path)
    marker = "MARKER-7f3c2a-unique-state"
    cfg = load_decisions_config()
    transport = resolve_transport(cfg)
    assert transport is not None
    ok = fake_ok({"topic_drift__topic_shift": {"noul": 0.9}})
    with patch("core.decisions.client.urllib.request.urlopen", return_value=ok):
        response, reason, _ = run_sync([SiteCall(TOPIC_DRIFT, False)], {"prompt": marker},
                                       transport=transport, cfg=cfg, timeout_s=1.0)
    assert reason == "ok" and response is not None
    written = [p for p in (tmp_path / "cache").rglob("*") if p.is_file()]
    assert written, "the response should have been cached"
    for path in written:
        assert marker not in path.read_text(encoding="utf-8", errors="replace")
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_created_directory_chain_is_private(tmp_path, monkeypatch):
    # Kills: reverting to mkdir(parents=True) (new parents follow the umask).
    import os

    root = tmp_path / "x" / "y" / "cache"
    monkeypatch.setenv("ARKA_DECISIONS_CACHE_DIR", str(root))
    key = cache.cache_key("m", "s", Q)
    old = os.umask(0o022)
    try:
        assert cache.put(key, _resp()) is True
    finally:
        os.umask(old)
    for d in (tmp_path / "x", tmp_path / "x" / "y", root, root / key[:2]):
        assert stat.S_IMODE(d.stat().st_mode) == 0o700, d
