#!/usr/bin/env python3
"""Shared /watch configuration helpers (ArkaOS-native).

Every filesystem anchor resolves at CALL time, never import time, so a
redirected HOME (tests, sandboxes) always takes effect. Key resolution
order: environment -> ~/.arkaos/keys.json (managed by `/arka keys`) ->
~/.arkaos/watch.env -> ./.env.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

DEFAULT_DETAIL = "balanced"

DETAILS = {"transcript", "efficient", "balanced", "token-burner"}


def arkaos_home() -> Path:
    """User-data root — ~/.arkaos, or ARKAOS_HOME when set."""
    override = os.environ.get("ARKAOS_HOME")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".arkaos"


def config_file() -> Path:
    return arkaos_home() / "watch.env"


def keys_file() -> Path:
    return arkaos_home() / "keys.json"


def telemetry_file() -> Path:
    return arkaos_home() / "telemetry" / "watch-usage.jsonl"


def read_env_file(path: Path | None = None) -> dict[str, str]:
    if path is None:
        path = config_file()
    values: dict[str, str] = {}
    if not path.exists():
        return values
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return values
    for line in lines:
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, _, value = raw.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] in ('"', "'") and value[-1] == value[0]:
            value = value[1:-1]
        else:
            # Strip an inline comment (a '#' preceded by whitespace) from an
            # unquoted value. Without this, `WATCH_DETAIL=balanced  # note`
            # parses as "balanced  # note", fails validation, and silently
            # falls back to the default. Keeps '#' inside quotes / API keys.
            for i, ch in enumerate(value):
                if ch == "#" and i > 0 and value[i - 1] in " \t":
                    value = value[:i].rstrip()
                    break
        values[key.strip()] = value
    return values


def read_keys_json() -> dict[str, str]:
    """API keys stored by `/arka keys` (~/.arkaos/keys.json). Fail-open."""
    path = keys_file()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): str(v) for k, v in data.items() if v}


def resolve_api_key(name: str) -> str | None:
    """env -> ~/.arkaos/keys.json -> ~/.arkaos/watch.env -> ./.env."""
    value = os.environ.get(name)
    if value and value.strip():
        return value.strip()
    value = read_keys_json().get(name)
    if value and value.strip():
        return value.strip()
    for path in (config_file(), Path.cwd() / ".env"):
        value = read_env_file(path).get(name)
        if value and value.strip():
            return value.strip()
    return None


def get_config() -> dict[str, object]:
    file_values = read_env_file()

    detail = (
        os.environ.get("WATCH_DETAIL")
        or file_values.get("WATCH_DETAIL")
        or DEFAULT_DETAIL
    )
    if detail not in DETAILS:
        detail = DEFAULT_DETAIL

    return {
        "detail": detail,
        "config_file": str(config_file()),
    }


def frame_cap(detail: str) -> int | None:
    if detail == "efficient":
        return 50
    if detail == "balanced":
        return 100
    if detail == "token-burner":
        return None
    if detail == "transcript":
        return None
    return 100


def record_telemetry(event: dict) -> None:
    """Append one usage record to ~/.arkaos/telemetry/watch-usage.jsonl.

    Observability must never break a watch run: filesystem failures
    (OSError) are reported to stderr and swallowed (fail-open). Callers
    pass only JSON-serializable scalars, so serialization cannot raise.
    """
    try:
        path = telemetry_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {"ts": round(time.time(), 3), **event}
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as exc:
        print(f"[watch] telemetry write skipped: {exc}", file=sys.stderr)
