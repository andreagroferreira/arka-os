"""Render a LiteLLM proxy config + Claude Code launch env from models.yaml.

Claude Code exposes at most three subagent alias slots (``opus``,
``sonnet``, ``haiku``) plus the interactive main-loop model. The seven
Model Fabric roles therefore collapse onto those slots by tier:

    quality tier (design/review/architecture/quality_gate)  -> opus slot
    execution                                                -> haiku slot
    mechanical                                               -> sonnet slot
    strategy / orchestrator                                  -> main model

Each slot maps to a LiteLLM route (``arka-<slot>``) that fans out to the
role's real upstream — Anthropic-direct or local Ollama. The launch env
points ``ANTHROPIC_DEFAULT_<TIER>_MODEL`` at those routes, so a subagent
dispatched with ``model: haiku`` reaches Ollama while ``model: opus``
reaches Anthropic — in the same session. The Anthropic API key never
enters the client env; it stays server-side in the proxy's environment.
"""

from __future__ import annotations

from pydantic import BaseModel

from core.runtime.model_router import ModelsConfig, load_config, resolve

# The three Claude Code subagent alias slots we can address, plus a
# sentinel for the interactive main-loop model (not an alias).
_SLOTS = ("opus", "sonnet", "haiku")
_MAIN = "main"

# Which alias slot each work-role dispatches through. The orchestrator
# uses this to choose the Task `model` param per role; the launch env
# points each slot's default model at the matching gateway route.
ROLE_ALIAS: dict[str, str] = {
    "design": "opus",
    "review": "opus",
    "architecture": "opus",
    "quality_gate": "opus",
    "strategy": _MAIN,
    "execution": "haiku",
    "mechanical": "sonnet",
}

# Representative role whose configured upstream defines each slot's route.
# All quality roles share the opus slot, so one of them stands in.
_SLOT_ROLE: dict[str, str] = {
    "opus": "quality_gate",
    "sonnet": "mechanical",
    "haiku": "execution",
}

# runtime-tier tokens -> real Anthropic model ids the proxy calls upstream.
# Real ids (claude-fable-5, claude-*) pass straight through.
_RUNTIME_TO_ANTHROPIC: dict[str, str] = {
    "opus": "claude-opus-4-8",
    "best": "claude-opus-4-8",
    "sonnet": "claude-sonnet-5",
    "default": "claude-sonnet-5",
    "haiku": "claude-haiku-4-5-20251001",
    "fast": "claude-haiku-4-5-20251001",
}

_DEFAULT_OLLAMA_BASE = "http://localhost:11434"
_DEFAULT_PORT = 4000
_ANTHROPIC_KEY_REF = "os.environ/ANTHROPIC_API_KEY"


def role_alias(role: str) -> str:
    """Which Claude Code alias slot a role dispatches through.

    Unknown roles fall back to the opus slot — never the cheap tier —
    consistent with the model-router's quality-first posture.
    """
    return ROLE_ALIAS.get(role, "opus")


class Upstream(BaseModel):
    """A concrete backend a slot routes to."""

    kind: str  # "anthropic" | "ollama"
    model_id: str
    api_base: str | None = None


class GatewayPlan(BaseModel):
    """Resolved routing: one upstream per alias slot + the main model."""

    slots: dict[str, Upstream]  # keyed by "opus"/"sonnet"/"haiku"
    main_model: str
    source: str


def _upstream_for(provider: str, model: str, ollama_base: str) -> Upstream:
    if provider == "ollama":
        return Upstream(kind="ollama", model_id=model, api_base=ollama_base)
    # runtime + anthropic both terminate at Anthropic-direct.
    return Upstream(kind="anthropic", model_id=_RUNTIME_TO_ANTHROPIC.get(model, model))


def _ollama_base(config: ModelsConfig) -> str:
    return (config.providers.get("ollama", {}) or {}).get("base_url") or _DEFAULT_OLLAMA_BASE


def build_gateway_plan(user_path=None) -> GatewayPlan:
    """Resolve every alias slot to its upstream from the operator's config."""
    config, source = load_config(user_path)
    ollama_base = _ollama_base(config)
    slots: dict[str, Upstream] = {}
    for slot, role in _SLOT_ROLE.items():
        r = resolve(role, user_path)
        slots[slot] = _upstream_for(r.provider, r.model, ollama_base)
    main = resolve("strategy", user_path)
    main_model = _RUNTIME_TO_ANTHROPIC.get(main.model, main.model)
    return GatewayPlan(slots=slots, main_model=main_model, source=source)


def _litellm_params(up: Upstream) -> dict:
    if up.kind == "ollama":
        # ollama_chat/ enables tool-use translation; api_base points at the
        # local daemon (which forwards :cloud models to Ollama Cloud).
        return {"model": f"ollama_chat/{up.model_id}", "api_base": up.api_base}
    return {"model": up.model_id, "api_key": _ANTHROPIC_KEY_REF}


def build_litellm_config(user_path=None) -> dict:
    """The LiteLLM proxy config.yaml structure (regenerated per launch).

    One ``arka-<slot>`` route per alias slot, plus a wildcard passthrough
    so the interactive main-loop model and any direct model id still reach
    Anthropic. The Anthropic key is referenced via ``os.environ`` — never
    inlined — and the client authenticates with the gateway master key.
    """
    plan = build_gateway_plan(user_path)
    model_list = [
        {"model_name": f"arka-{slot}", "litellm_params": _litellm_params(plan.slots[slot])}
        for slot in _SLOTS
    ]
    # Wildcard last: LiteLLM matches explicit names first, this catches the
    # main-loop model and any raw claude-* id and forwards it to Anthropic.
    model_list.append(
        {"model_name": "*", "litellm_params": {"model": "anthropic/*", "api_key": _ANTHROPIC_KEY_REF}}
    )
    return {
        "model_list": model_list,
        "litellm_settings": {"drop_params": True},
        "general_settings": {"master_key": "os.environ/ARKA_GATEWAY_KEY"},
    }


def build_launch_env(master_key: str, port: int = _DEFAULT_PORT, user_path=None) -> dict[str, str]:
    """Env vars Claude Code launches with so subagent aliases hit the gateway.

    ``ANTHROPIC_API_KEY`` is deliberately absent — it belongs to the proxy,
    not the client. The client presents only the gateway master key.
    """
    return {
        "ANTHROPIC_BASE_URL": f"http://127.0.0.1:{port}",
        "ANTHROPIC_AUTH_TOKEN": master_key,
        "ANTHROPIC_DEFAULT_OPUS_MODEL": "arka-opus",
        "ANTHROPIC_DEFAULT_SONNET_MODEL": "arka-sonnet",
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": "arka-haiku",
    }


def render_config_yaml(user_path=None) -> str:
    """The LiteLLM config as a YAML string (what arka-claude writes to disk)."""
    import yaml

    return yaml.safe_dump(build_litellm_config(user_path), sort_keys=False)
