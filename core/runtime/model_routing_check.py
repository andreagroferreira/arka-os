"""Model-routing telemetry — answer "is the Model Fabric actually used?".

The gateway makes per-role routing real; this module makes it *observable*.
It reports the resolved route table, whether the LiteLLM proxy is live, and
a best-effort count of which ``arka-<slot>`` routes actually served traffic
(parsed from the proxy log). Everything degrades to a plain summary when the
gateway is off, so ``/arka status`` always has a truthful line to show.
"""

from __future__ import annotations

import re
from pathlib import Path

from core.runtime.gateway.litellm_config import build_gateway_plan

_GATEWAY_LOG = Path.home() / ".arkaos" / "gateway" / "litellm.log"
_DEFAULT_PORT = 4000
_ROUTE_RE = re.compile(r"\barka-(opus|sonnet|haiku)\b")


def resolved_routes(user_path=None) -> dict[str, str]:
    """Alias slot -> human 'kind:model' the gateway would route it to."""
    plan = build_gateway_plan(user_path)
    return {
        slot: f"{up.kind}:{up.model_id}" for slot, up in plan.slots.items()
    }


def gateway_healthy(port: int = _DEFAULT_PORT, timeout: float = 1.0) -> bool:
    """True when the LiteLLM proxy answers its liveness probe."""
    import urllib.error
    import urllib.request

    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/health/liveliness", timeout=timeout
        ) as resp:
            return resp.status == 200
    except (urllib.error.URLError, OSError, ValueError):
        return False


def served_counts(log_path: Path | None = None) -> dict[str, int]:
    """Best-effort count of arka-<slot> routes seen in the proxy log."""
    path = log_path or _GATEWAY_LOG
    counts: dict[str, int] = {}
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return counts
    for match in _ROUTE_RE.finditer(text):
        slot = match.group(1)
        counts[slot] = counts.get(slot, 0) + 1
    return counts


def status_summary(port: int = _DEFAULT_PORT, user_path=None, log_path=None) -> str:
    """One compact block for /arka status — reality, not intent."""
    live = gateway_healthy(port)
    routes = resolved_routes(user_path)
    header = (
        f"Gateway: {'LIVE' if live else 'off'} (:{port}) — per-role model routing "
        f"{'active' if live else 'not active; honour-system context injection only'}"
    )
    lines = [f"  {slot} → {target}" for slot, target in sorted(routes.items())]
    counts = served_counts(log_path)
    if counts:
        served = " ".join(f"{slot}={n}" for slot, n in sorted(counts.items()))
        lines.append(f"  served: {served}")
    return header + "\n" + "\n".join(lines)
