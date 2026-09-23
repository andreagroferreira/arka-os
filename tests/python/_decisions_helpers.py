"""Shared fixtures-as-functions for the ``test_decisions_*`` modules.

Kept out of ``conftest.py`` on purpose: sibling conftests claim the bare
``conftest`` import name (see ``conftest.py`` docstring).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

# Values from the 2026-09-23 smoke test against OpenRouter.
SMOKE_MODEL_ECHO = "typesafe/jev-1.13-20260917"
SMOKE_INPUT_TOKENS = 749
SMOKE_OUTPUT_TOKENS = 118
SMOKE_COST = 3.1458e-05


class FakeResponse:
    """Minimal context-manager stand-in for ``urlopen``'s return value."""

    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> bool:
        return False

    def read(self) -> bytes:
        return self._body


def response_body(answers: dict[str, dict[str, Any]], *, cost: float | None = SMOKE_COST) -> bytes:
    """A response shaped like the real endpoint (extra id/provider keys)."""
    usage: dict[str, Any] = {
        "input_tokens": SMOKE_INPUT_TOKENS,
        "output_tokens": SMOKE_OUTPUT_TOKENS,
    }
    if cost is not None:
        usage["cost"] = cost
    return json.dumps({
        "model": SMOKE_MODEL_ECHO,
        "answers": answers,
        "usage": usage,
        "id": "gen-dec-test",
        "provider": "TypeSafe",
    }).encode("utf-8")


def fake_ok(answers: dict[str, dict[str, Any]], **kw: Any) -> FakeResponse:
    return FakeResponse(response_body(answers, **kw))


def isolate_decisions(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    key: str | None = "sk-or-test",
    clients: list[str] | None = None,
) -> Path:
    """Opt out of the suite bypass and redirect every path into tmp_path.

    Returns the fake HOME, which always holds a redaction config (egress
    is fail-closed without one); tests of the denial delete it.
    """
    monkeypatch.delenv("ARKA_BYPASS_DECISIONS", raising=False)
    home = tmp_path / "home"
    (home / ".arkaos").mkdir(parents=True)
    names = ["clientey"] if clients is None else clients
    (home / ".arkaos" / "redaction-clients.json").write_text(
        json.dumps({"clients": names}), encoding="utf-8"
    )
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("ARKA_DECISIONS_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("ARKA_DECISIONS_TELEMETRY_PATH", str(tmp_path / "decisions.jsonl"))
    monkeypatch.setenv("ARKA_LLM_COST_PATH", str(tmp_path / "llm-cost.jsonl"))
    monkeypatch.setattr("core.decisions.transport._KEYS_PATH", home / ".arkaos" / "keys.json")
    monkeypatch.setattr("core.decisions.config.CONFIG_PATH", home / ".arkaos" / "config.json")
    if key:
        monkeypatch.setenv("OPENROUTER_API_KEY", key)
    return home


def write_config(home: Path, block: dict[str, Any]) -> None:
    (home / ".arkaos" / "config.json").write_text(
        json.dumps({"decisions": block}), encoding="utf-8"
    )


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def sent_payload(mock: Any, call_index: int = -1) -> dict[str, Any]:
    """The JSON body of one mocked ``urlopen`` call."""
    request = mock.call_args_list[call_index].args[0]
    return json.loads(request.data.decode("utf-8"))
