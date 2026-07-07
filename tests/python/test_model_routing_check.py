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
      runtime: {best: opus, default: sonnet, fast: haiku}
    roles:
      quality_gate: {provider: runtime, model: best, effort: max}
      mechanical:   {provider: runtime, model: sonnet, effort: low}
      execution:    {provider: ollama, model: "kimi-k2.7-code:cloud", effort: high}
      strategy:     {provider: runtime, model: claude-fable-5, effort: max}
    """
)


@pytest.fixture()
def models_path(tmp_path: Path) -> Path:
    p = tmp_path / "models.yaml"
    p.write_text(_MODELS_YAML, encoding="utf-8")
    return p


def test_resolved_routes(models_path: Path):
    routes = resolved_routes(models_path)
    assert routes["opus"] == "anthropic:claude-opus-4-8"
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
