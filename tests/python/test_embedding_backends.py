"""Tests for core.knowledge.embedding_backends (F1-A1)."""

from __future__ import annotations

import io
import json
import urllib.error

import pytest

from core.knowledge import embedder, embedding_backends
from core.knowledge.embedding_backends import (
    EmbeddingResult,
    embed,
    embed_batch,
    get_backend_name,
    resolve_backend,
    reset_backend_cache,
)


@pytest.fixture(autouse=True)
def clean_state(monkeypatch, tmp_path):
    """Isolate config, env and per-process caches for every test."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("ARKA_EMBED_BACKEND", raising=False)
    monkeypatch.delenv("ARKA_EMBED_MODEL", raising=False)
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    reset_backend_cache()
    yield
    reset_backend_cache()


def _write_config(tmp_path, memory: dict) -> None:
    cfg_dir = tmp_path / ".arkaos"
    cfg_dir.mkdir(exist_ok=True)
    (cfg_dir / "config.json").write_text(json.dumps({"memory": memory}))


def _fake_urlopen_factory(responses: dict[str, dict]):
    """urlopen stub keyed by URL suffix; raises URLError on no match."""

    class _Resp:
        status = 200

        def __init__(self, payload: dict):
            self._payload = payload

        def read(self):
            return json.dumps(self._payload).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def _fake(request, timeout=None):
        url = request if isinstance(request, str) else request.full_url
        for suffix, payload in responses.items():
            if url.endswith(suffix):
                return _Resp(payload)
        raise urllib.error.URLError("connection refused")

    return _fake


# ─── Backend name resolution (env > config > default) ─────────────────


def test_default_backend_name_is_auto():
    assert get_backend_name() == "auto"


def test_config_backend_name(tmp_path):
    _write_config(tmp_path, {"embedBackend": "ollama"})
    assert get_backend_name() == "ollama"


def test_env_overrides_config(tmp_path, monkeypatch):
    _write_config(tmp_path, {"embedBackend": "ollama"})
    monkeypatch.setenv("ARKA_EMBED_BACKEND", "fastembed")
    assert get_backend_name() == "fastembed"


# ─── Auto resolution order ─────────────────────────────────────────────


def test_auto_prefers_fastembed(monkeypatch):
    monkeypatch.setattr(embedder, "is_available", lambda: True)
    assert resolve_backend() == "fastembed"


def test_auto_falls_back_to_ollama(monkeypatch):
    monkeypatch.setattr(embedder, "is_available", lambda: False)
    monkeypatch.setattr(
        embedding_backends.urllib.request,
        "urlopen",
        _fake_urlopen_factory({"/api/tags": {"models": []}}),
    )
    assert resolve_backend() == "ollama"


def test_auto_degrades_to_none(monkeypatch):
    monkeypatch.setattr(embedder, "is_available", lambda: False)
    monkeypatch.setattr(
        embedding_backends.urllib.request,
        "urlopen",
        _fake_urlopen_factory({}),
    )
    assert resolve_backend() == "none"


def test_api_never_auto_selected(monkeypatch):
    """Even with a key present, auto must not pick the paid backend."""
    monkeypatch.setattr(embedder, "is_available", lambda: False)
    monkeypatch.setattr(embedding_backends, "_api_key", lambda: "sk-test")
    monkeypatch.setattr(
        embedding_backends.urllib.request,
        "urlopen",
        _fake_urlopen_factory({}),
    )
    assert resolve_backend() == "none"


def test_explicit_api_without_key_degrades(monkeypatch):
    monkeypatch.setenv("ARKA_EMBED_BACKEND", "api")
    monkeypatch.setattr(embedding_backends, "_api_key", lambda: None)
    assert resolve_backend() == "none"


def test_explicit_fastembed_unavailable_degrades(monkeypatch):
    monkeypatch.setenv("ARKA_EMBED_BACKEND", "fastembed")
    monkeypatch.setattr(embedder, "is_available", lambda: False)
    assert resolve_backend() == "none"


def test_resolution_cached_per_process(monkeypatch):
    calls = {"n": 0}

    def _probe():
        calls["n"] += 1
        return True

    monkeypatch.setattr(embedder, "is_available", _probe)
    resolve_backend()
    resolve_backend()
    assert calls["n"] == 1


# ─── embed / embed_batch provenance ────────────────────────────────────


def test_fastembed_result_declares_backend(monkeypatch):
    monkeypatch.setattr(embedder, "is_available", lambda: True)
    monkeypatch.setattr(embedder, "get_model_name", lambda: "test-model")
    monkeypatch.setattr(
        embedder, "embed_batch", lambda texts: [[0.1, 0.2, 0.3] for _ in texts]
    )
    result = embed("hello")
    assert result.backend == "fastembed"
    assert result.model == "test-model"
    assert result.dims == 3
    assert result.vector == [0.1, 0.2, 0.3]


def test_ollama_embed_batch(monkeypatch, tmp_path):
    monkeypatch.setenv("ARKA_EMBED_BACKEND", "ollama")
    _write_config(tmp_path, {"embedModel": "nomic-embed-text"})
    monkeypatch.setattr(
        embedding_backends.urllib.request,
        "urlopen",
        _fake_urlopen_factory(
            {
                "/api/tags": {"models": []},
                "/api/embed": {"embeddings": [[1.0, 2.0], [3.0, 4.0]]},
            }
        ),
    )
    results = embed_batch(["a", "b"])
    assert [r.backend for r in results] == ["ollama", "ollama"]
    assert results[0].vector == [1.0, 2.0]
    assert results[1].dims == 2
    assert results[0].model == "nomic-embed-text"


def test_ollama_failure_degrades_per_item(monkeypatch):
    monkeypatch.setenv("ARKA_EMBED_BACKEND", "ollama")
    monkeypatch.setattr(
        embedding_backends.urllib.request,
        "urlopen",
        _fake_urlopen_factory({"/api/tags": {"models": []}}),
    )
    result = embed("boom")
    assert result.backend == "none"
    assert result.vector is None
    assert result.dims == 0


def test_api_embed_batch_ordered(monkeypatch):
    monkeypatch.setenv("ARKA_EMBED_BACKEND", "api")
    monkeypatch.setattr(embedding_backends, "_api_key", lambda: "sk-test")
    monkeypatch.setattr(
        embedding_backends.urllib.request,
        "urlopen",
        _fake_urlopen_factory(
            {
                "/v1/embeddings": {
                    "data": [
                        {"index": 1, "embedding": [3.0]},
                        {"index": 0, "embedding": [1.0]},
                    ]
                }
            }
        ),
    )
    results = embed_batch(["first", "second"])
    assert results[0].vector == [1.0]
    assert results[1].vector == [3.0]
    assert all(r.backend == "api" for r in results)


def test_none_backend_result(monkeypatch):
    monkeypatch.setenv("ARKA_EMBED_BACKEND", "none")
    result = embed("anything")
    assert result == EmbeddingResult(vector=None, backend="none", model="", dims=0)


def test_empty_batch():
    assert embed_batch([]) == []
