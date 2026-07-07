"""ArkaOS model-routing gateway.

Turns the operator's ``~/.arkaos/models.yaml`` role routing into a running
LiteLLM proxy so per-role model choices actually take effect at dispatch
time. Claude Code points ``ANTHROPIC_BASE_URL`` at the proxy; the proxy
fans each request out to the right upstream (Anthropic-direct or local
Ollama) by the model name the alias slot carries.

See ``docs/adr`` and the plan for why a gateway is required: Claude Code's
``ANTHROPIC_BASE_URL`` is one endpoint per process, so honouring mixed
providers per role in a single session needs a fan-out proxy.
"""

from core.runtime.gateway.litellm_config import (
    GatewayPlan,
    build_gateway_plan,
    build_launch_env,
    build_litellm_config,
    role_alias,
)

__all__ = [
    "GatewayPlan",
    "build_gateway_plan",
    "build_launch_env",
    "build_litellm_config",
    "role_alias",
]
