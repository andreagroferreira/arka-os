"""The skill-hints candidate menu — one builder for the hook and the replay.

The ``skill-hints`` decision site (``core/decisions/sites/dispatch.py``)
asks Jev to pick one command from a pre-filtered menu, never from the
whole registry (308 commands; the endpoint caps a choice at 255 options).
The menu is the union of two recalls:

* the live L5 keyword ranking (``_score_commands``), top
  :data:`MENU_TOP_KEYWORD` — what L5 would hint without Jev;
* every command of the routed department — what keyword scoring misses
  on pt-PT prompts ("desenha uma paleta de cores" scores zero keywords).

Keyword hits come first so the cap never cuts them; the menu is capped at
:data:`MENU_CAP`. Pure: the caller passes the registry it already holds.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from core.synapse.layers import PREFIX_DEPARTMENTS, _score_commands

MENU_TOP_KEYWORD = 20
MENU_CAP = 60
# The option text the site builds is capped at 240 chars; a shorter
# description keeps the request (state + criteria) small on every turn.
MENU_DESCRIPTION_CHARS = 160


def command_department(command: dict[str, Any]) -> str:
    """The L1 department key of a registry command, from its ``/prefix``.

    ``/mkt ...`` → ``marketing``; a prefix L1 does not know (``/arka``)
    → "". The registry's own ``department`` field uses hub slugs
    (``mkt``, ``leadership``), so the prefix is the reliable key.
    """
    prefix = str(command.get("command", "")).lstrip("/").split(" ")[0]
    return PREFIX_DEPARTMENTS.get(prefix, "")


def _menu_entry(command: dict[str, Any]) -> dict[str, str]:
    return {
        "id": str(command.get("id", "")),
        "command": str(command.get("command", "")),
        "description": str(command.get("description", ""))[:MENU_DESCRIPTION_CHARS],
    }


def skill_hint_candidates(
    commands: Sequence[dict[str, Any]], prompt: str, dept: str
) -> list[dict[str, str]]:
    """Top keyword commands plus the ``dept`` commands, de-duped by id, capped.

    ``dept`` is an L1 department key (the route decision); "" adds none.
    """
    listed = list(commands)
    by_command = {str(c.get("command", "")): c for c in reversed(listed)}
    ranked = [
        by_command[cmd]
        for _, cmd, _ in _score_commands(listed, prompt.lower())[:MENU_TOP_KEYWORD]
        if cmd in by_command
    ]
    routed = [c for c in listed if dept and command_department(c) == dept]
    menu: dict[str, dict[str, str]] = {}
    for command in [*ranked, *routed]:
        entry = _menu_entry(command)
        if entry["id"]:
            menu.setdefault(entry["id"], entry)
    return list(menu.values())[:MENU_CAP]
