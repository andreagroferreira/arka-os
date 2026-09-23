"""core.decisions.transport — OpenRouter only, key resolution, headers."""

from __future__ import annotations

import json

import pytest

from core.decisions.config import DecisionsConfig
from core.decisions.transport import DECISIONS_URL, resolve_model, resolve_transport


@pytest.fixture
def keys_path(tmp_path, monkeypatch):
    path = tmp_path / "keys.json"
    monkeypatch.setattr("core.decisions.transport._KEYS_PATH", path)
    return path


def test_no_key_no_transport(keys_path):
    assert resolve_transport(DecisionsConfig()) is None


def test_env_key_builds_openrouter_transport(keys_path, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", " sk-or-env ")
    t = resolve_transport(DecisionsConfig())
    assert t is not None
    assert (t.name, t.url, t.model) == ("openrouter", DECISIONS_URL, "typesafe/jev-1.13")
    assert t.headers["Authorization"] == "Bearer sk-or-env"
    assert t.headers["Content-Type"] == "application/json"
    assert t.headers["X-Title"] == "ArkaOS" and "HTTP-Referer" in t.headers


def test_keys_json_fallback(keys_path):
    keys_path.write_text(json.dumps({"OPENROUTER_API_KEY": "sk-or-file"}), encoding="utf-8")
    t = resolve_transport(DecisionsConfig())
    assert t is not None and t.key == "sk-or-file"


@pytest.mark.parametrize("content", ["{broken", "[1]", json.dumps({"OPENROUTER_API_KEY": 5})])
def test_bad_keys_json_is_no_key(keys_path, content):
    keys_path.write_text(content, encoding="utf-8")
    assert resolve_transport(DecisionsConfig()) is None


def test_unknown_transport_is_none(keys_path, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-env")
    assert resolve_transport(DecisionsConfig(transport="direct")) is None


def test_key_never_in_repr(keys_path, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-secret-value")
    assert "sk-or-secret-value" not in repr(resolve_transport(DecisionsConfig()))


def test_provider_data_collection_denied_by_default(keys_path, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-env")
    t = resolve_transport(DecisionsConfig())
    assert t is not None and t.body_extras == {"provider": {"data_collection": "deny"}}


@pytest.mark.parametrize(("raw", "expected"), [
    (None, "typesafe/jev-1.13"), ("jev-1.13", "typesafe/jev-1.13"),
    ("typesafe/jev-2.0", "typesafe/jev-2.0"), ("  ", "typesafe/jev-1.13"),
])
def test_model_alias(raw, expected):
    assert resolve_model(raw) == expected


def test_configured_model_reads_models_yaml_and_never_raises(monkeypatch):
    from core.decisions.transport import configured_model
    from core.runtime import model_router

    cfg = model_router.ModelsConfig(decisions={"model": "typesafe/jev-2"})
    monkeypatch.setattr(model_router, "load_config", lambda *a, **k: (cfg, "user"))
    assert configured_model() == "typesafe/jev-2"

    def _broken(*_a, **_k):
        raise OSError("unreadable")

    monkeypatch.setattr(model_router, "load_config", _broken)
    assert configured_model() is None
