"""Frontend excellence gate — PreToolUse enforcement for UI file edits.

Constitution: ``excellence-mandate`` (NON-NEGOTIABLE, Excellence Reform
2026-07-05). UI work must load the frontend design skills and judge
against a named benchmark BEFORE code is written. This gate makes that
duty mechanical: a Write/Edit/MultiEdit touching a UI file requires the
STRUCTURED design marker in the recent assistant messages:

    [arka:design] benchmark=<Company> skills=<comma,list> tokens=<path|none>

(the same ceremony contract as ``[arka:routing]`` / ``[arka:dispatch]``,
upgraded in PR-D2 from the bare ``[arka:design] <anything>`` form — the
bare form is now a LEGACY marker: tolerated in warn mode with a nudge,
counted separately in telemetry, treated as missing in hard mode).

Modes via ``hooks.frontendGate`` in ``~/.arkaos/config.json``:

    absent / "warn"   → nudge on stderr, allow (rollout default)
    true / "hard"     → deny UI edits without the structured marker
    false / "off"     → gate disabled

Scope: component/stylesheet suffixes (now including ``.html``), plus a
WARN-only content heuristic for ``.ts/.js`` files that visibly carry UI
(className=/styled/@apply/tailwind/cva) — heuristic hits never deny,
even in hard mode, and carry their own ``ui_scope`` so the telemetry can
exclude them from the hard-flip decision if they prove FP-heavy.

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

# Any [arka:design] marker line; classification into structured vs legacy
# happens on the tail (order-insensitive key scan, see _classify_marker).
DESIGN_LINE_RE = re.compile(r"\[arka:design\]([^\n]*)", re.IGNORECASE)
_BENCHMARK_KEY_RE = re.compile(r"\bbenchmark=\S+", re.IGNORECASE)
_SKILLS_KEY_RE = re.compile(r"\bskills=\S+", re.IGNORECASE)

MARKER_TEMPLATE = (
    "[arka:design] benchmark=<Company> skills=<comma,list> tokens=<path|none>"
)

_GATED_TOOLS = frozenset({"Write", "Edit", "MultiEdit"})

# Component + stylesheet extensions. Plain .ts/.js stay out of the suffix
# set (stores, utils, configs would flood the gate) — they are covered by
# the WARN-only content heuristic below when they visibly carry UI.
UI_SUFFIXES = frozenset({
    ".vue", ".tsx", ".jsx", ".svelte", ".astro",
    ".css", ".scss", ".sass", ".less",
    ".html", ".htm",
})

_HEURISTIC_SUFFIXES = frozenset({".ts", ".js", ".mjs", ".cjs"})
_UI_CONTENT_RE = re.compile(
    r"className=|styled\.|styled\(|@apply\b|\btailwind\b|cva\("
)
_UI_FILENAME_RE = re.compile(
    r"(?:^|/)tailwind\.config\.[cm]?[tj]s$|\.styles?\.[tj]s$|(?:^|/)theme\.[tj]s$"
)


@dataclass
class Decision:
    """Outcome of frontend-gate evaluation."""

    allow: bool
    reason: str
    mode: str = "warn"
    target_file: str = ""
    marker_found: str | None = None
    marker_kind: str = "none"   # structured | legacy | trivial | none
    ui_scope: str = "suffix"    # suffix | heuristic

    def to_stderr_message(self) -> str:
        if self.reason == "legacy-marker":
            head = "[arka:suggest]" if self.allow else "[ARKA:DESIGN]"
            return (
                f"{head} Legacy design marker found ({self.marker_found}). "
                f"The structured form is now required for hard-mode passage: "
                f"`{MARKER_TEMPLATE}` — name the benchmark company and the "
                f"skills actually loaded (or skills=degraded:<missing>)."
            )
        if self.reason != "no-design-marker":
            return ""
        head = "[arka:suggest]" if self.allow else "[ARKA:DESIGN]"
        verb = "should" if self.allow else "MUST"
        return (
            f"{head} UI edit to {self.target_file or 'this file'} without "
            f"design evidence. Frontend work {verb} load the design skills "
            f"(frontend-design, ui-ux-pro-max, project design system) at "
            f"maximum effort and judge against a named benchmark FIRST "
            f"(constitution `excellence-mandate`). Emit "
            f"`{MARKER_TEMPLATE}` before UI edits, "
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


def _edit_payloads(tool_name: str, tool_input: dict) -> list[str]:
    """The text this tool call is about to write, per tool shape."""
    if tool_name == "Write":
        return [str(tool_input.get("content", ""))]
    if tool_name == "Edit":
        return [str(tool_input.get("new_string", ""))]
    if tool_name == "MultiEdit":
        edits = tool_input.get("edits") or []
        return [str(e.get("new_string", "")) for e in edits if isinstance(e, dict)]
    return []


def is_heuristic_ui_file(
    file_path: str, tool_name: str, tool_input: dict
) -> bool:
    """WARN-only UI detection for .ts/.js: filename or visible UI content."""
    path = Path(file_path)
    if path.suffix.lower() not in _HEURISTIC_SUFFIXES:
        return False
    if _UI_FILENAME_RE.search(file_path.replace("\\", "/")):
        return True
    return any(
        _UI_CONTENT_RE.search(payload)
        for payload in _edit_payloads(tool_name, tool_input)
    )


def _classify_marker(messages: list[str]) -> tuple[str | None, str]:
    """Return (matched_marker, kind) — kind: structured|legacy|trivial|none.

    A structured marker anywhere in the window wins over legacy ones.
    """
    legacy: str | None = None
    for message in messages:
        for match in DESIGN_LINE_RE.finditer(message):
            tail = match.group(1)
            if _BENCHMARK_KEY_RE.search(tail) and _SKILLS_KEY_RE.search(tail):
                return match.group(0).strip(), "structured"
            if tail.strip() and legacy is None:
                legacy = match.group(0).strip()
        trivial = TRIVIAL_RE.search(message)
        if trivial:
            return trivial.group(0), "trivial"
    if legacy is not None:
        return legacy, "legacy"
    return None, "none"


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
    if tool_name not in _GATED_TOOLS:
        return Decision(allow=True, reason="not-ui-scope", target_file=file_path)
    if is_ui_file(file_path):
        ui_scope = "suffix"
    elif is_heuristic_ui_file(file_path, tool_name, tool_input):
        ui_scope = "heuristic"
    else:
        return Decision(allow=True, reason="not-ui-scope", target_file=file_path)
    mode = _mode()
    if mode == "off":
        return Decision(allow=True, reason="flag-off", mode=mode,
                        target_file=file_path, ui_scope=ui_scope)
    if os.environ.get("ARKA_BYPASS_DESIGN") == "1":
        return Decision(allow=True, reason="env-bypass", mode=mode,
                        target_file=file_path, ui_scope=ui_scope)
    if messages is None:
        messages = _load_last_assistant_messages(
            transcript_path, ASSISTANT_WINDOW
        )
    marker, kind = _classify_marker(messages)
    if kind in ("structured", "trivial"):
        return Decision(allow=True, reason="design-evidence", mode=mode,
                        target_file=file_path, marker_found=marker,
                        marker_kind=kind, ui_scope=ui_scope)
    # Heuristic scope is WARN-only by design: it never denies, even in
    # hard mode — its telemetry (ui_scope=heuristic) informs whether it
    # ever graduates to denying scope.
    deniable = mode == "hard" and ui_scope == "suffix"
    if kind == "legacy":
        return Decision(allow=not deniable, reason="legacy-marker", mode=mode,
                        target_file=file_path, marker_found=marker,
                        marker_kind=kind, ui_scope=ui_scope)
    return Decision(allow=not deniable, reason="no-design-marker",
                    mode=mode, target_file=file_path, marker_kind=kind,
                    ui_scope=ui_scope)


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
