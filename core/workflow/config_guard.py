"""Config-protection gate — the agent fixes the code, not the linter.

An agent that hits a lint or type error has two ways out: fix the code,
or edit the config so the check stops firing. The second is faster and
almost always wrong — it silences the signal for the whole team, not
just this change. This gate is the cheapest high-value control in the
set: refuse edits to linter/formatter/type-checker configs, and the
agent is left with the honest path.

This is a PreToolUse gate. It denies a Write/Edit to a protected config
file and tells the agent to fix the underlying code instead. Two escape
hatches, because the rule is a heuristic and the operator is in charge:

- ``ARKA_BYPASS_CONFIG_GUARD=1`` in the environment — a deliberate,
  auditable override for the sessions where editing the config IS the
  task (bumping a rule set, adopting a new formatter).
- an explicit instruction in a recent USER message that names the config
  file — if the operator asked for it, the agent is not sneaking around a
  check, it is doing what it was told.

The override reads the operator's messages, never the agent's. Reading
the agent's own turns would invert the control: the guarded actor could
authorise its own edit by naming the file, while the operator's real
request went unseen. The user-message source is the whole point.

Failure directions, chosen deliberately:
- The GATE CHAIN degrades open on infrastructure failure (missing module,
  import error) — a broken guard must not block all edits.
- The OVERRIDE fails closed: when the operator's intent cannot be read
  (no transcript, unreadable), the edit is treated as unauthorised and
  denied in hard mode. The env bypass is the escape hatch that never
  depends on the transcript, so a locked-out operator is never stuck.

Feature-flagged off by default via ``hooks.configGuard`` (off | warn |
hard) until telemetry says promote.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

CONFIG_PATH = Path.home() / ".arkaos" / "config.json"

# Config files whose whole purpose is to define a quality bar. Matched on
# the basename, case-insensitively. A change here weakens the check for
# everyone, so the agent must not reach for it to get unblocked.
_PROTECTED_BASENAMES = frozenset({
    # JS/TS linters & formatters
    ".eslintrc", ".eslintrc.js", ".eslintrc.cjs", ".eslintrc.json",
    ".eslintrc.yml", ".eslintrc.yaml", "eslint.config.js",
    "eslint.config.mjs", "eslint.config.cjs", ".prettierrc",
    ".prettierrc.json", ".prettierrc.js", ".prettierrc.yml",
    ".prettierrc.yaml", "prettier.config.js", "biome.json", "biome.jsonc",
    ".editorconfig",
    # Python
    "ruff.toml", ".ruff.toml", ".flake8", ".pylintrc", "mypy.ini",
    ".mypy.ini", ".pre-commit-config.yaml",
    # PHP / Ruby / Go / Rust
    ".php-cs-fixer.php", ".php-cs-fixer.dist.php", "phpstan.neon",
    "phpstan.neon.dist", "psalm.xml", ".rubocop.yml", ".golangci.yml",
    ".golangci.yaml", "rustfmt.toml", ".rustfmt.toml", "clippy.toml",
})
# Files that CARRY tool config among other things — protect only the
# lint/format/type sections conceptually, but at the file level we can
# only warn, not know. These are NOT hard-denied (they hold real project
# config too); they are left to the operator. Documented, not enforced:
#   pyproject.toml, package.json, setup.cfg, tox.ini
# The basename set above is deliberately the "config IS the check" tier.

_ENV_BYPASS = "ARKA_BYPASS_CONFIG_GUARD"


def mode() -> str:
    """Resolve ``hooks.configGuard`` to 'off' | 'warn' | 'hard'.

    Default 'warn': the gate observes and nudges but never blocks, so it
    ships dark and earns 'hard' on telemetry (the frontend-gate and
    specialist-gate rollout pattern). Unreadable config degrades to
    'warn', never to 'hard' — a guard must not start blocking because a
    file failed to parse.
    """
    if not CONFIG_PATH.exists():
        return "warn"
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return "warn"
    raw = data.get("hooks", {}).get("configGuard", "warn")
    if raw in (False, "off", "false"):
        return "off"
    if raw in (True, "hard", "true"):
        return "hard"
    return "warn"


@dataclass(frozen=True)
class ConfigGuardDecision:
    """Allow or deny, with the reason on record."""

    allow: bool
    reason: str = ""
    file_path: str = ""

    def to_stderr_message(self) -> str:
        if self.allow:
            return ""
        return (
            f"[arka:config-guard] Refusing to edit {self.file_path}. That "
            f"file defines the quality bar; editing it to clear a lint, "
            f"type, or format error silences the check for the whole team "
            f"instead of fixing the code. Fix the underlying code.\n"
            f"To lift this, the OPERATOR must name {self.file_path} in a "
            f"message (an agent cannot authorise its own config edit), or "
            f"set {_ENV_BYPASS}=1 in the environment."
        )


def is_protected_config(file_path: str) -> bool:
    """Whether a path is a config file whose edit weakens a check."""
    if not file_path:
        return False
    return Path(file_path).name.lower() in _PROTECTED_BASENAMES


def _operator_named_file(
    user_messages: list[str] | None, file_path: str
) -> bool:
    """Did the OPERATOR name this config file in a recent message?

    The whole basename must appear as its own token. The trailing guard
    blocks a sibling file — ``ruff.toml.bak``, ``ruff.toml~``,
    ``ruff.toml-old`` must not authorise an edit to ``ruff.toml`` — while
    still allowing a sentence-ending period (``edit ruff.toml.`` should
    match): the negative lookahead fires on a dot/tilde/hyphen only when
    it continues into a filename, not on end punctuation. Case-insensitive
    to match ``is_protected_config``, which lowercases the basename.
    """
    if not user_messages or not file_path:
        return False
    name = re.escape(Path(file_path).name)
    pattern = re.compile(
        rf"(?<![\w.]){name}(?![\w])(?!\.\w)(?![~-])", re.IGNORECASE
    )
    return any(
        pattern.search(m) for m in user_messages if isinstance(m, str)
    )


def evaluate(
    file_path: str,
    user_messages: list[str] | None = None,
) -> ConfigGuardDecision:
    """Decide whether to allow an edit to a protected config file.

    Allows everything that is not a protected config; denies a protected
    config edit unless the env bypass is set or the OPERATOR named the
    file in a recent message. ``user_messages`` must be operator turns —
    passing the agent's own messages inverts the control.
    """
    if not is_protected_config(file_path):
        return ConfigGuardDecision(allow=True)
    if os.environ.get(_ENV_BYPASS) == "1":
        return ConfigGuardDecision(
            allow=True, reason="env-bypass", file_path=file_path
        )
    if _operator_named_file(user_messages, file_path):
        return ConfigGuardDecision(
            allow=True, reason="operator-named-file", file_path=file_path
        )
    return ConfigGuardDecision(
        allow=False, reason="protected-config", file_path=file_path
    )
