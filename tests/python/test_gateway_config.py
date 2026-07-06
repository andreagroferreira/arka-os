"""Gateway config generator: models.yaml -> LiteLLM config + launch env."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from core.runtime.gateway import (
    build_gateway_plan,
    build_launch_env,
    build_litellm_config,
    role_alias,
)

_MODELS_YAML = textwrap.dedent(
    """
    version: 1
    providers:
      runtime: {type: subagent}
      anthropic: {type: anthropic-direct}
      ollama: {type: ollama, base_url: "http://localhost:11434"}
    aliases:
      runtime: {best: opus, default: sonnet, fast: haiku}
    roles:
      design:       {provider: runtime, model: best, effort: max}
      review:       {provider: runtime, model: best, effort: max}
      architecture: {provider: runtime, model: best, effort: max}
      strategy:     {provider: runtime, model: claude-fable-5, effort: max}
      quality_gate: {provider: runtime, model: best, effort: max}
      execution:    {provider: ollama, model: "kimi-k2.7-code:cloud", effort: high}
      mechanical:   {provider: runtime, model: sonnet, effort: low}
    """
)


@pytest.fixture()
def models_path(tmp_path: Path) -> Path:
    p = tmp_path / "models.yaml"
    p.write_text(_MODELS_YAML, encoding="utf-8")
    return p


def _route(config: dict, name: str) -> dict:
    for entry in config["model_list"]:
        if entry["model_name"] == name:
            return entry["litellm_params"]
    raise AssertionError(f"route {name!r} not in config: {config}")


def test_role_alias_collapse():
    assert role_alias("quality_gate") == "opus"
    assert role_alias("review") == "opus"
    assert role_alias("execution") == "haiku"
    assert role_alias("mechanical") == "sonnet"
    assert role_alias("strategy") == "main"
    # unknown role never lands on the cheap tier
    assert role_alias("totally-unknown") == "opus"


def test_gateway_plan_maps_slots_to_upstreams(models_path: Path):
    plan = build_gateway_plan(models_path)
    assert plan.slots["opus"].kind == "anthropic"
    assert plan.slots["opus"].model_id == "claude-opus-4-8"
    assert plan.slots["sonnet"].kind == "anthropic"
    assert plan.slots["sonnet"].model_id == "claude-sonnet-5"
    # execution hijacks the haiku slot -> local Ollama
    assert plan.slots["haiku"].kind == "ollama"
    assert plan.slots["haiku"].model_id == "kimi-k2.7-code:cloud"
    assert plan.slots["haiku"].api_base == "http://localhost:11434"
    assert plan.main_model == "claude-fable-5"


def test_litellm_config_routes(models_path: Path):
    cfg = build_litellm_config(models_path)
    assert _route(cfg, "arka-opus")["model"] == "claude-opus-4-8"
    assert _route(cfg, "arka-sonnet")["model"] == "claude-sonnet-5"
    haiku = _route(cfg, "arka-haiku")
    assert haiku["model"] == "ollama_chat/kimi-k2.7-code:cloud"
    assert haiku["api_base"] == "http://localhost:11434"
    # wildcard passthrough for the main loop / raw ids
    assert _route(cfg, "*")["model"] == "anthropic/*"


def test_anthropic_key_never_inlined(models_path: Path):
    """The real key is referenced via os.environ, never written into config."""
    cfg = build_litellm_config(models_path)
    for entry in cfg["model_list"]:
        key = entry["litellm_params"].get("api_key")
        if key is not None:
            assert key == "os.environ/ANTHROPIC_API_KEY"
            assert not key.startswith("sk-"), "raw Anthropic key leaked into config"


def test_launch_env_points_aliases_at_routes(models_path: Path):
    env = build_launch_env(master_key="sentinel-key", port=4000, user_path=models_path)
    assert env["ANTHROPIC_BASE_URL"] == "http://127.0.0.1:4000"
    assert env["ANTHROPIC_AUTH_TOKEN"] == "sentinel-key"
    assert env["ANTHROPIC_DEFAULT_OPUS_MODEL"] == "arka-opus"
    assert env["ANTHROPIC_DEFAULT_SONNET_MODEL"] == "arka-sonnet"
    assert env["ANTHROPIC_DEFAULT_HAIKU_MODEL"] == "arka-haiku"


def test_launch_env_never_carries_anthropic_key(models_path: Path):
    """ANTHROPIC_API_KEY belongs to the proxy, not the client env."""
    env = build_launch_env(master_key="sentinel-key", user_path=models_path)
    assert "ANTHROPIC_API_KEY" not in env
