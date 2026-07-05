"""Model Fabric router — resolve a work role to (provider, model, effort).

The user owns ``~/.arkaos/models.yaml``; the packaged default ships at
``config/models.yaml``. Roles govern everything ArkaOS dispatches
(subagents, Quality Gate, Forge, fusion, cognition, daemons) — the
interactive runtime keeps its own main-loop model.

Constitution ``model-routing`` (Excellence Reform 2026-07-05): quality-
critical roles (design, review, architecture, strategy, quality_gate)
default to the best model available at maximum effort; only genuinely
mechanical work economises. The built-in fallback used when no YAML can
be read encodes the same posture — a missing file never silently
downgrades a quality role.

Public API::

    resolve("review")          -> ResolvedModel(provider, model, effort)
    load_config()              -> ModelsConfig
    ensure_user_config()       -> Path (creates ~/.arkaos/models.yaml)
    set_role("review", "anthropic/best", effort="max")
"""

from __future__ import annotations

import shutil
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator

USER_CONFIG_PATH = Path.home() / ".arkaos" / "models.yaml"

QUALITY_ROLES = frozenset({
    "design", "review", "architecture", "strategy", "quality_gate",
})

# Plain-language explanation of each role, surfaced in the dashboard and
# `npx arkaos models` so the operator knows what "execution" etc. drive.
ROLE_DESCRIPTIONS: dict[str, str] = {
    "design": "UI/UX and visual design — layout, typography, aesthetics.",
    "review": "Code review, Quality Gate reviewers, adversarial verification.",
    "architecture": "System design, API contracts, ADRs, technical decisions.",
    "strategy": "Business and product strategy, market analysis, planning.",
    "quality_gate": "The mandatory Quality Gate (Marta, Eduardo, Francisca).",
    "execution": "Implementation — specialists writing code and running build tasks.",
    "mechanical": "Rote work — commit messages, changelog, formatting, data fetch.",
}


def role_description(role: str) -> str:
    """Human-readable description of a role, or empty if unknown."""
    return ROLE_DESCRIPTIONS.get(role, "")
KNOWN_EFFORTS = ("low", "medium", "high", "max")

_ALIAS_NAMES = frozenset({"best", "default", "fast"})


class RoleChoice(BaseModel):
    """One role entry as written in models.yaml."""

    provider: str = "runtime"
    model: str = "best"
    effort: str = "high"

    @field_validator("effort")
    @classmethod
    def _known_effort(cls, value: str) -> str:
        if value not in KNOWN_EFFORTS:
            raise ValueError(
                f"effort must be one of {KNOWN_EFFORTS}, got {value!r}"
            )
        return value


class FusionConfig(BaseModel):
    """Judge + panel for the fusion engine (PR-D consumes this)."""

    judge: RoleChoice = Field(default_factory=lambda: RoleChoice(effort="max"))
    panel: list[RoleChoice] = Field(default_factory=list)


class ModelsConfig(BaseModel):
    """Validated shape of models.yaml."""

    version: int = 1
    providers: dict[str, dict] = Field(default_factory=dict)
    aliases: dict[str, dict[str, str]] = Field(default_factory=dict)
    roles: dict[str, RoleChoice] = Field(default_factory=dict)
    fusion: FusionConfig = Field(default_factory=FusionConfig)


class ResolvedModel(BaseModel):
    """A role after alias resolution — what a dispatcher actually uses."""

    role: str
    provider: str
    model: str
    effort: str
    source: str  # "user" | "packaged" | "builtin"


def _packaged_config_path() -> Path:
    return Path(__file__).resolve().parents[2] / "config" / "models.yaml"


def _builtin_config() -> ModelsConfig:
    """Quality-first posture used when no YAML is readable at all."""
    roles = {
        role: RoleChoice(model="best", effort="max") for role in QUALITY_ROLES
    }
    roles["execution"] = RoleChoice(model="default", effort="high")
    roles["mechanical"] = RoleChoice(model="fast", effort="low")
    return ModelsConfig(
        providers={"runtime": {"type": "subagent"}},
        aliases={"runtime": {"best": "opus", "default": "sonnet", "fast": "haiku"}},
        roles=roles,
    )


def _read_yaml(path: Path) -> ModelsConfig | None:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return None
    if not isinstance(data, dict):
        return None
    try:
        return ModelsConfig.model_validate(data)
    except ValueError:
        return None


def load_config(user_path: Path | None = None) -> tuple[ModelsConfig, str]:
    """Load config with provenance: user file, packaged default, builtin."""
    path = user_path or USER_CONFIG_PATH
    config = _read_yaml(path) if path.is_file() else None
    if config is not None:
        return config, "user"
    packaged = _packaged_config_path()
    config = _read_yaml(packaged) if packaged.is_file() else None
    if config is not None:
        return config, "packaged"
    return _builtin_config(), "builtin"


def _resolve_alias(config: ModelsConfig, provider: str, model: str) -> str:
    if model not in _ALIAS_NAMES:
        return model
    return config.aliases.get(provider, {}).get(model, "") or model


def resolve(role: str, user_path: Path | None = None) -> ResolvedModel:
    """Resolve a role name to a concrete (provider, model, effort).

    Unknown roles resolve conservatively: quality posture, not economy —
    a typo must never silently land on the cheap tier
    (``excellence-mandate``).
    """
    config, source = load_config(user_path)
    choice = config.roles.get(role)
    if choice is None:
        fallback = "execution" if role not in QUALITY_ROLES else role
        choice = config.roles.get(fallback, RoleChoice(model="best", effort="max"))
    return ResolvedModel(
        role=role,
        provider=choice.provider,
        model=_resolve_alias(config, choice.provider, choice.model),
        effort=choice.effort,
        source=source,
    )


def resolve_all(user_path: Path | None = None) -> list[ResolvedModel]:
    """Resolve every configured role — the CLI table."""
    config, _ = load_config(user_path)
    return [resolve(role, user_path) for role in sorted(config.roles)]


def ensure_user_config(user_path: Path | None = None) -> Path:
    """Create ~/.arkaos/models.yaml from the packaged default if absent."""
    path = user_path or USER_CONFIG_PATH
    if path.is_file():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    packaged = _packaged_config_path()
    if packaged.is_file():
        shutil.copy(packaged, path)
    else:
        path.write_text(
            yaml.safe_dump(_builtin_config().model_dump(), sort_keys=False),
            encoding="utf-8",
        )
    return path


def set_role(
    role: str,
    target: str,
    effort: str | None = None,
    user_path: Path | None = None,
) -> ResolvedModel:
    """Point a role at ``provider/model`` (e.g. ``anthropic/best``).

    Writes the user file (creating it first when needed) and returns the
    new resolution. Raises ValueError on a malformed target or effort.
    """
    if "/" not in target:
        raise ValueError(
            f"target must be provider/model (e.g. runtime/best), got {target!r}"
        )
    provider, model = target.split("/", 1)
    path = ensure_user_config(user_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    entry = {"provider": provider, "model": model}
    entry["effort"] = effort or data.get("roles", {}).get(role, {}).get(
        "effort", "max" if role in QUALITY_ROLES else "high"
    )
    RoleChoice.model_validate(entry)  # fail before writing anything
    data.setdefault("roles", {})[role] = entry
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return resolve(role, path)
