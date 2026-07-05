"""Ollama discovery — is it installed, is it running, which models exist.

Model Fabric PR-C. Feeds three consumers: the `npx arkaos models` CLI
(show what the machine can actually run), the `/arka-fusion` advisor
(recommend local models for panel/mechanical roles), and the dashboard
Models page. Read-only: never starts the daemon, never pulls models.

Detection is two-layered on purpose: the binary can be installed while
the daemon is stopped (installed=True, running=False lets the advisor
say "start Ollama to unlock N local models" instead of pretending
Ollama does not exist).
"""

from __future__ import annotations

import json
import os
import shutil
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field

_DEFAULT_HOST = "http://localhost:11434"
_TAGS_TIMEOUT_S = 2.0


@dataclass(frozen=True)
class OllamaModel:
    """One locally available model as reported by /api/tags."""

    name: str
    size_gb: float
    family: str
    parameter_size: str


@dataclass(frozen=True)
class OllamaStatus:
    """Discovery result for the local Ollama installation."""

    installed: bool
    running: bool
    host: str
    models: list[OllamaModel] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _host() -> str:
    return os.environ.get("OLLAMA_HOST", _DEFAULT_HOST).rstrip("/")


def binary_installed() -> bool:
    """True when the `ollama` binary is on PATH."""
    return shutil.which("ollama") is not None


def _fetch_tags(host: str) -> list[dict] | None:
    """GET /api/tags; None when the daemon is unreachable."""
    try:
        with urllib.request.urlopen(
            f"{host}/api/tags", timeout=_TAGS_TIMEOUT_S
        ) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError,
            json.JSONDecodeError):
        return None
    models = data.get("models")
    return models if isinstance(models, list) else []


def _parse_model(record: dict) -> OllamaModel:
    details = record.get("details") or {}
    size_bytes = int(record.get("size", 0) or 0)
    return OllamaModel(
        name=str(record.get("name", "")),
        size_gb=round(size_bytes / 1_000_000_000, 1),
        family=str(details.get("family", "") or ""),
        parameter_size=str(details.get("parameter_size", "") or ""),
    )


def discover() -> OllamaStatus:
    """Full discovery: binary on PATH, daemon reachable, model list."""
    host = _host()
    tags = _fetch_tags(host)
    if tags is None:
        return OllamaStatus(
            installed=binary_installed(), running=False, host=host
        )
    models = [_parse_model(r) for r in tags if r.get("name")]
    models.sort(key=lambda m: m.name)
    # Daemon answering means Ollama is effectively installed even if the
    # binary is not on this shell's PATH (e.g. Docker deployment).
    return OllamaStatus(installed=True, running=True, host=host, models=models)
