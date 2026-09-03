"""Model-routing telemetry: resolved routes, log parse, status summary."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from core.runtime.model_routing_check import (
    resolved_routes,
    served_counts,
    status_summary,
)

_MODELS_YAML = textwrap.dedent(
    """
    version: 1
    providers:
      ollama: {type: ollama, base_url: "http://localhost:11434"}
    aliases:
      runtime: {best: fable, default: sonnet, fast: sonnet}
    roles:
      quality_gate: {provider: runtime, model: best, effort: max}
      mechanical:   {provider: runtime, model: sonnet, effort: low}
      execution:    {provider: ollama, model: "kimi-k2.7-code:cloud", effort: high}
      strategy:     {provider: runtime, model: claude-fable-5-1, effort: max}
    """
)


@pytest.fixture()
def models_path(tmp_path: Path) -> Path:
    p = tmp_path / "models.yaml"
    p.write_text(_MODELS_YAML, encoding="utf-8")
    return p


def test_resolved_routes(models_path: Path):
    routes = resolved_routes(models_path)
    assert routes["opus"] == "anthropic:claude-fable-5-1"
    assert routes["sonnet"] == "anthropic:claude-sonnet-5"
    assert routes["haiku"] == "ollama:kimi-k2.7-code:cloud"


def test_served_counts_parses_routes(tmp_path: Path):
    log = tmp_path / "litellm.log"
    log.write_text(
        "POST /v1/messages model=arka-haiku\n"
        "POST /v1/messages model=arka-opus\n"
        "POST /v1/messages model=arka-haiku\n"
        "unrelated line\n",
        encoding="utf-8",
    )
    counts = served_counts(log)
    assert counts == {"haiku": 2, "opus": 1}


def test_served_counts_missing_log_is_empty(tmp_path: Path):
    assert served_counts(tmp_path / "nope.log") == {}


def test_status_summary_off_when_no_gateway(models_path: Path, tmp_path: Path):
    # No proxy running on this port in tests -> reports off, still lists routes.
    summary = status_summary(port=59999, user_path=models_path, log_path=tmp_path / "x.log")
    assert "Gateway: off" in summary
    assert "haiku → ollama:kimi-k2.7-code:cloud" in summary


# ── Runtime Sync PR3: the fallback chain the runtime will use ───────────

import json  # noqa: E402 — appended section

from core.runtime.model_routing_check import fallback_chain, fallback_line  # noqa: E402


def _settings(tmp_path: Path, payload) -> Path:
    p = tmp_path / "settings.json"
    p.write_text(payload if isinstance(payload, str) else json.dumps(payload), encoding="utf-8")
    return p


def test_fallback_chain_reads_the_array(tmp_path: Path):
    p = _settings(tmp_path, {"fallbackModel": ["claude-opus-5", "claude-sonnet-5"]})
    assert fallback_chain(p) == ["claude-opus-5", "claude-sonnet-5"]


def test_fallback_chain_normalises_the_legacy_string_without_rewriting(tmp_path: Path):
    p = _settings(tmp_path, {"fallbackModel": " claude-sonnet-5 "})
    before = p.read_text(encoding="utf-8")
    assert fallback_chain(p) == ["claude-sonnet-5"]
    assert p.read_text(encoding="utf-8") == before


@pytest.mark.parametrize(
    "payload",
    [{}, {"fallbackModel": []}, {"fallbackModel": ""}, {"fallbackModel": 7}, "{ not json", "[1]"],
)
def test_fallback_chain_is_none_when_unset_or_unreadable(tmp_path: Path, payload):
    assert fallback_chain(_settings(tmp_path, payload)) is None


def test_fallback_chain_is_none_when_the_file_is_missing(tmp_path: Path):
    assert fallback_chain(tmp_path / "absent.json") is None


def test_status_summary_shows_the_chain(models_path: Path, tmp_path: Path):
    p = _settings(tmp_path, {"fallbackModel": ["claude-opus-5", "claude-sonnet-5"]})
    summary = status_summary(
        port=59999, user_path=models_path, log_path=tmp_path / "x.log", settings_path=p
    )
    assert "  fallback: claude-opus-5 → claude-sonnet-5" in summary


def test_status_summary_says_unset_and_how_to_seed(models_path: Path, tmp_path: Path):
    p = _settings(tmp_path, {})
    summary = status_summary(
        port=59999, user_path=models_path, log_path=tmp_path / "x.log", settings_path=p
    )
    assert "  fallback: unset (npx arkaos update seeds claude-opus-5 → claude-sonnet-5)" in summary
    assert fallback_line(p) in summary
