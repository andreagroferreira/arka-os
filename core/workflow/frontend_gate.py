"""Frontend excellence gate — PreToolUse enforcement for UI file edits.

Constitution: ``excellence-mandate`` (NON-NEGOTIABLE, Excellence Reform
2026-07-05). UI work must load the frontend design skills and judge
against a named benchmark BEFORE code is written. This gate makes that
duty mechanical: a Write/Edit/MultiEdit touching a UI file requires an
``[arka:design] <skills/benchmark>`` marker in the recent assistant
messages — the same ceremony contract as ``[arka:routing]``
(flow_enforcer) and ``[arka:dispatch]`` (specialist_enforcer).

Modes via ``hooks.frontendGate`` in ``~/.arkaos/config.json``:

    absent / "warn"   → nudge on stderr, allow (rollout default)
    true / "hard"     → deny UI edits without the marker
    false / "off"     → gate disabled

Bypasses: ``[arka:trivial] <reason>`` marker (same contract as the
evidence flow — single-file edits under 10 lines) and
``ARKA_BYPASS_DESIGN=1`` env (logged for accountability).
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from core.shared import safe_session_id as _safe_session_id_module
from core.workflow.flow_enforcer import (
    TRIVIAL_RE,
    _load_last_assistant_messages,
)
from core.workflow.specialist_enforcer import _locked_append

CONFIG_PATH = Path.home() / ".arkaos" / "config.json"
TELEMETRY_PATH = Path.home() / ".arkaos" / "telemetry" / "frontend-gate.jsonl"

ASSISTANT_WINDOW = 20

DESIGN_RE = re.compile(r"\[arka:design\]\s*\S+", re.IGNORECASE)

_GATED_TOOLS = frozenset({"Write", "Edit", "MultiEdit"})

# Component + stylesheet extensions. Plain .ts/.js are excluded: they are
# ambiguous (stores, utils, configs) and would flood the gate with false
# positives — the component file is where the visual decision lands.
UI_SUFFIXES = frozenset({
    ".vue", ".tsx", ".jsx", ".svelte", ".astro",
    ".css", ".scss", ".sass", ".less",
})


@dataclass
class Decision:
    """Outcome of frontend-gate evaluation."""

    allow: bool
    reason: str
    mode: str = "warn"
    target_file: str = ""
    marker_found: str | None = None

    def to_stderr_message(self) -> str:
        if self.reason not in ("no-design-marker",):
            return ""
        head = "[arka:suggest]" if self.allow else "[ARKA:DESIGN]"
        verb = "should" if self.allow else "MUST"
        return (
            f"{head} UI edit to {self.target_file or 'this file'} without "
            f"design evidence. Frontend work {verb} load the design skills "
            f"(frontend-design, ui-ux-pro-max, project design system) at "
            f"maximum effort and judge against a named benchmark FIRST "
            f"(constitution `excellence-mandate`). Emit "
            f"`[arka:design] <skills> benchmark=<name>` before UI edits, "
            f"or `[arka:trivial] <reason>` for sub-10-line fixes."
        )


def _mode() -> str:
    """Resolve ``hooks.frontendGate`` to 'off' | 'warn' | 'hard'."""
    if not CONFIG_PATH.exists():
        return "warn"
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return "warn"
    raw = data.get("hooks", {}).get("frontendGate", "warn")
    if raw in (False, "off", "false"):
        return "off"
    if raw in (True, "hard", "true"):
        return "hard"
    return "warn"


def is_ui_file(file_path: str) -> bool:
    """True when the path carries a gated UI extension."""
    return Path(file_path).suffix.lower() in UI_SUFFIXES


def _scan(messages: list[str]) -> str | None:
    """Return the matched evidence marker, or None."""
    for message in messages:
        match = DESIGN_RE.search(message) or TRIVIAL_RE.search(message)
        if match:
            return match.group(0)
    return None


def evaluate(
    tool_name: str,
    transcript_path: str,
    session_id: str,
    cwd: str,
    tool_input: dict,
    messages: list[str] | None = None,
) -> Decision:
    """Evaluate one tool call against the frontend excellence gate."""
    file_path = str(tool_input.get("file_path", ""))
    if tool_name not in _GATED_TOOLS or not is_ui_file(file_path):
        return Decision(allow=True, reason="not-ui-scope", target_file=file_path)
    mode = _mode()
    if mode == "off":
        return Decision(allow=True, reason="flag-off", mode=mode,
                        target_file=file_path)
    if os.environ.get("ARKA_BYPASS_DESIGN") == "1":
        return Decision(allow=True, reason="env-bypass", mode=mode,
                        target_file=file_path)
    if messages is None:
        messages = _load_last_assistant_messages(
            transcript_path, ASSISTANT_WINDOW
        )
    marker = _scan(messages)
    if marker is not None:
        return Decision(allow=True, reason="design-evidence", mode=mode,
                        target_file=file_path, marker_found=marker)
    return Decision(allow=(mode != "hard"), reason="no-design-marker",
                    mode=mode, target_file=file_path)


def record_telemetry(session_id: str, tool: str, decision: Decision) -> None:
    """Append a structured record to the frontend-gate telemetry log.

    Drops the record silently when session_id fails the safe-id check
    (path-traversal mitigation, CWE-22). Never blocks the hook.
    """
    safe = _safe_session_id_module.safe_session_id(session_id)
    if safe is None:
        return
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "session_id": safe,
        "tool": tool,
        **asdict(decision),
    }
    try:
        with _locked_append(TELEMETRY_PATH) as fh:
            fh.write(json.dumps(entry) + "\n")
    except OSError:
        pass
