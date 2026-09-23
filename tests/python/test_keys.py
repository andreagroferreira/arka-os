"""Tests for core.keys — the PROVIDERS registry and get/set/list key
management (~/.arkaos/keys.json, 600 permissions).

Minimal coverage added alongside PR1 (JEV Decisions Layer campaign): no
dedicated test file existed for this module before OPENROUTER_API_KEY was
added to PROVIDERS.
"""

from __future__ import annotations

import json

import pytest

import core.keys as keys_mod


@pytest.fixture(autouse=True)
def _isolated_keys_path(tmp_path, monkeypatch):
    """Never touch the operator's real ~/.arkaos/keys.json.

    OPENROUTER_API_KEY (and every other provider var) is already stripped
    from the environment by the suite-wide autouse fixture in conftest.py
    (``_no_live_decisions``) — this fixture only isolates the on-disk
    keys.json path, the same technique test_openrouter_provider.py uses
    for its own ``_KEYS_PATH``.
    """
    monkeypatch.setattr(keys_mod, "KEYS_PATH", tmp_path / "keys.json")


def test_providers_registry_has_openrouter_and_openai():
    assert "OPENROUTER_API_KEY" in keys_mod.PROVIDERS
    assert "OPENAI_API_KEY" in keys_mod.PROVIDERS
    entry = keys_mod.PROVIDERS["OPENROUTER_API_KEY"]
    assert entry["name"] == "OpenRouter"
    assert "decisions" in entry["used_for"].lower()


def test_get_key_reads_env_before_keys_json(monkeypatch):
    keys_mod.KEYS_PATH.parent.mkdir(parents=True, exist_ok=True)
    keys_mod.KEYS_PATH.write_text(
        json.dumps({"OPENROUTER_API_KEY": "sk-or-from-file"}), encoding="utf-8"
    )
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-from-env")
    assert keys_mod.get_key("OPENROUTER_API_KEY") == "sk-or-from-env"


def test_get_key_falls_back_to_keys_json_without_env():
    keys_mod.KEYS_PATH.parent.mkdir(parents=True, exist_ok=True)
    keys_mod.KEYS_PATH.write_text(
        json.dumps({"OPENROUTER_API_KEY": "sk-or-from-file"}), encoding="utf-8"
    )
    assert keys_mod.get_key("OPENROUTER_API_KEY") == "sk-or-from-file"


def test_get_key_returns_none_when_unset():
    assert keys_mod.get_key("OPENROUTER_API_KEY") is None


def test_set_key_persists_and_get_key_reads_it_back():
    keys_mod.set_key("OPENROUTER_API_KEY", "sk-or-set")
    assert keys_mod.get_key("OPENROUTER_API_KEY") == "sk-or-set"
    assert keys_mod.KEYS_PATH.exists()


def test_list_keys_includes_openrouter_entry_when_configured():
    keys_mod.set_key("OPENROUTER_API_KEY", "sk-or-1234567890")
    listed = {row["key"]: row for row in keys_mod.list_keys()}
    assert "OPENROUTER_API_KEY" in listed
    row = listed["OPENROUTER_API_KEY"]
    assert row["provider"] == "OpenRouter"
    assert row["configured"] is True
    assert row["masked_value"] == "sk-o...7890"


def test_list_keys_includes_openrouter_entry_when_not_configured():
    listed = {row["key"]: row for row in keys_mod.list_keys()}
    assert "OPENROUTER_API_KEY" in listed
    assert listed["OPENROUTER_API_KEY"]["configured"] is False
