"""Template-token path resolver for ArkaOS.

Resolves user-specific paths from ``~/.arkaos/profile.json`` and environment
variables, so source files can use neutral tokens like ``${VAULT_PATH}`` and
``${ARKA_OS_REPOS}`` instead of hardcoded absolute paths.

Token precedence (highest → lowest):
  1. Environment variable (e.g. ``ARKAOS_VAULT_PATH``)
  2. profile.json field (e.g. ``vaultPath``)
  3. For ``${GIT_HOST}`` only: hardcoded default ``github.com``

If ``~/.arkaos/profile.json`` is missing or unparseable and an
unconfigured token is requested, ``ProfileMissingError`` is raised
with a clear remediation message. Unknown tokens pass through
unchanged so that prompt strings containing ``${SOME_BASH_VAR}`` for
the agent are preserved.

See ``core/specs/SPEC-paths-portability.md`` for the full contract.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from core.runtime.user_paths import user_data_root

_PROFILE_FILENAME = "profile.json"
_TOKEN_PATTERN = re.compile(r"\$\{([A-Z_]+)\}")

_DEFAULT_PROJECT_ROOTS = ["~/Herd", "~/Work", "~/AIProjects"]
_DEFAULT_REPOS_ROOT = "~/AIProjects"
_DEFAULT_GIT_HOST = "github.com"

_PROFILE_CACHE: "ProfileV3 | None" = None


class ProfileMissingError(RuntimeError):
    """Raised when ``~/.arkaos/profile.json`` cannot be loaded."""


@dataclass(frozen=True)
class ProfileV3:
    """In-memory representation of profile.json v3."""

    version: str
    vault_path: str
    repos_root: str
    project_roots: list[str] = field(default_factory=list)
    raw: dict = field(default_factory=dict)


def profile_path() -> Path:
    """Absolute path to ``~/.arkaos/profile.json``."""
    return user_data_root() / _PROFILE_FILENAME


def load_profile(*, refresh: bool = False) -> ProfileV3:
    """Load and validate profile.json.

    Cached per process; pass ``refresh=True`` to force a re-read.

    Raises:
        ProfileMissingError: file absent, unreadable, or unparseable JSON.
    """
    global _PROFILE_CACHE
    if _PROFILE_CACHE is not None and not refresh:
        return _PROFILE_CACHE

    path = profile_path()
    if not path.exists():
        raise ProfileMissingError(
            f"~/.arkaos/profile.json not found at {path}. "
            "Run /arka setup to configure ArkaOS paths."
        )
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProfileMissingError(
            f"~/.arkaos/profile.json could not be parsed ({exc}). "
            "Run /arka setup to repair, or restore from a .bak file."
        ) from exc

    _PROFILE_CACHE = _project_from_raw(raw)
    return _PROFILE_CACHE


def reset_cache() -> None:
    """Drop the cached profile (for tests)."""
    global _PROFILE_CACHE
    _PROFILE_CACHE = None


def resolve(template: str) -> str:
    """Substitute known ``${VAR}`` tokens in *template*.

    Tokens recognised:
      - ``${VAULT_PATH}``    → ``ARKAOS_VAULT_PATH`` env or ``profile.vaultPath``
      - ``${ARKA_OS_REPOS}`` → ``ARKAOS_REPOS_ROOT`` env or ``profile.reposRoot``
      - ``${PROJECT_ROOTS}`` → ``os.pathsep``-joined profile.projectRoots
      - ``${GIT_HOST}``      → ``ARKAOS_GIT_HOST`` env, default ``github.com``
      - ``${HOME}``          → ``os.path.expanduser("~")``

    Unknown tokens pass through unchanged.
    """
    return _TOKEN_PATTERN.sub(_resolve_token_match, template)


def resolve_dict(obj):
    """Recursively resolve every string value in nested dicts/lists."""
    if isinstance(obj, str):
        return resolve(obj)
    if isinstance(obj, dict):
        return {k: resolve_dict(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [resolve_dict(item) for item in obj]
    return obj


def project_root_regex() -> re.Pattern[str]:
    """Compile a regex matching paths under any configured project root.

    Used by ``core/cognition/capture/collector.py`` to detect project paths
    inside captured session digests across macOS, Linux and Windows.
    """
    profile = load_profile()
    roots = [os.path.expanduser(r) for r in profile.project_roots] or [
        os.path.expanduser(r) for r in _DEFAULT_PROJECT_ROOTS
    ]
    alternation = "|".join(re.escape(r.rstrip("/").rstrip("\\")) for r in roots)
    return re.compile(rf"({alternation})[/\\]([^\s/\\]+)")


def _resolve_token_match(match: re.Match[str]) -> str:
    return _resolve_token(match.group(1), match.group(0))


def _resolve_token(name: str, original: str) -> str:
    if name == "HOME":
        return os.path.expanduser("~")
    if name == "GIT_HOST":
        return _env_or("ARKAOS_GIT_HOST", _DEFAULT_GIT_HOST)
    if name == "VAULT_PATH":
        env_val = _env_or("ARKAOS_VAULT_PATH", _env_or("ARKAOS_VAULT", ""))
        return env_val or load_profile().vault_path
    if name == "ARKA_OS_REPOS":
        env_val = _env_or("ARKAOS_REPOS_ROOT", "")
        return env_val or load_profile().repos_root
    if name == "PROJECT_ROOTS":
        env_val = _env_or("ARKAOS_PROJECT_ROOTS", "")
        if env_val:
            return env_val
        return os.pathsep.join(load_profile().project_roots)
    return original


def _env_or(name: str, fallback: str) -> str:
    value = os.environ.get(name, "")
    return value if value else fallback


def _project_from_raw(raw: dict) -> ProfileV3:
    vault_path = raw.get("vaultPath") or raw.get("vault_path") or ""
    if not vault_path:
        raise ProfileMissingError(
            "profile.json has no vaultPath. Run /arka setup to configure it."
        )
    repos_root = (
        raw.get("reposRoot")
        or raw.get("repos_root")
        or _DEFAULT_REPOS_ROOT
    )
    project_roots = list(raw.get("projectRoots") or [])
    if not project_roots:
        project_roots = _derive_project_roots(raw.get("projectsDir", ""))
    return ProfileV3(
        version=str(raw.get("version", "2")),
        vault_path=vault_path,
        repos_root=repos_root,
        project_roots=project_roots,
        raw=raw,
    )


def _derive_project_roots(projects_dir_text: str) -> list[str]:
    """Best-effort parse of the legacy free-text ``projectsDir`` field.

    Looks for absolute paths on macOS/Linux/Windows. Falls back to
    ``_DEFAULT_PROJECT_ROOTS`` when no path can be extracted. This keeps
    the ~20K legacy users functional until ``npx arkaos update`` rewrites
    their profile.json with the new ``projectRoots`` field.
    """
    if not projects_dir_text:
        return list(_DEFAULT_PROJECT_ROOTS)
    posix = r"(?:/Users|/home)/\S+?/(?:Herd|Work|AIProjects|code|repos)"
    windows = r"[A-Z]:\\Users\\[^\s\\]+\\(?:Herd|Work|AIProjects|code|repos)"
    pattern = re.compile(rf"({posix}|{windows})")
    found = pattern.findall(projects_dir_text)
    return found or list(_DEFAULT_PROJECT_ROOTS)
