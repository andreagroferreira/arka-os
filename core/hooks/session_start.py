"""SessionStart — consolidated entrypoint (F2-2, hook-hygiene completion).

Replaces the 13 python spawn sites of the old ``session-start.sh``
(profile x2, sync drift, forge YAML x4, Model Fabric, reorganizer
trigger, dashboard config read, rehydrator, memory recap, final JSON
print) with ONE python process that emits the full ``systemMessage``.
Measured baseline before this consolidation: 251ms p50 (isolated floor,
benchmarks/results.md); each spawn costs ~20-80ms.

Section order preserved exactly from the shell version:
    banner+greeting → workflow line → version+forge+drift →
    evidence-flow contract → meta-tag contract → Model Fabric directive
    → [SESSION] rehydrator resume → [SESSION-MEMORY] recap → JSON out.
Background side effects (reorganizer trigger, dashboard ensure) stay
detached and are config-gated; the NEW ``cognition.reorganize_on_session``
gate lands here (QG F2-1 follow-up, endorsed for this PR).

The shell wrapper only resolves the interpreter and ``exec``s this
module; with no usable venv it emits a static banner (fail-open).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from core.hooks._shared import get_str, read_stdin_json, repo_path

_BUDGET_MS = 300
_RECAP_ITEMS = 3
_SUMMARY_CHARS = 130

_BANNER = (
    "\n╔══════════════════════════════════════════════╗\n"
    "║                                              ║\n"
    "║              A R K A   O S                   ║\n"
    "║                                              ║\n"
    "║   The Operating System for AI Teams          ║\n"
    "║                  by WizardingCode            ║\n"
    "║                                              ║\n"
    "╚══════════════════════════════════════════════╝\n"
)

_EVIDENCE_CONTRACT = (
    "\n\n[ARKA:EVIDENCE-FLOW] NON-NEGOTIABLE. Every non-trivial request runs"
    " the 4-gate evidence flow (constitution rule evidence-flow; source"
    " arka/skills/flow/SKILL.md):"
    "\n  G1 CONTEXT ([arka:routing] <dept> -> <lead> + KB/graph grounding,"
    " cite or declare gap)"
    "\n  G2 PLAN (short plan -> EXPLICIT user approval; silence != approval)"
    "\n  G3 EXECUTE (closes only with real test run on record: command + exit 0)"
    "\n  G4 REVIEW (executable checks: lint/type/coverage/security/spell ->"
    " honest summary)"
    "\nEmit [arka:gate:N] at each gate start. Gates pass on evidence, never"
    " on narration."
    "\nBypass ONLY via [arka:trivial] <reason> for single-file edits under"
    " 10 lines."
)

_META_TAG_CONTRACT = (
    "\n\n[ARKA:META-TAG] Every substantive response ends with a single line:"
    "\n  [arka:meta] kb=N research=X persona=Y gap=Z critic=W"
    "\nFields: kb=N (Obsidian/KB notes consulted), research=X (MCPs invoked:"
    " perplexity,exa,context7,firecrawl,xmcp or 'none'), persona=Y (advisor"
    " name or 'orchestrator'), gap=Z (KB gap topic or 'none'), critic=W"
    " (passed|failed|skipped)."
    "\nMandatory after: EFFECT tool calls, plan/recommendation outputs, QG"
    " verdicts. Optional for pure read-only status replies."
    "\nAbsence is measured by the Stop hook (warn-only in v2.34.0) before"
    " promotion to hard enforcement."
)


def _config() -> dict:
    try:
        data = json.loads(
            (Path.home() / ".arkaos" / "config.json").read_text(encoding="utf-8")
        )
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _profile() -> tuple[str, str]:
    try:
        data = json.loads(
            (Path.home() / ".arkaos" / "profile.json").read_text(encoding="utf-8")
        )
        name = data.get("name") or data.get("role") or "founder"
        return str(name), str(data.get("company") or "WizardingCode")
    except (OSError, json.JSONDecodeError, AttributeError):
        return "founder", "WizardingCode"


def _version(repo: str) -> str:
    candidates = [Path.home() / ".arkaos" / "lib" / "VERSION"]
    if repo:
        candidates.insert(0, Path(repo) / "VERSION")
    for candidate in candidates:
        try:
            if candidate.is_file():
                return candidate.read_text(encoding="utf-8").strip()
        except OSError:
            continue
    return "2.x"


def _drift(version: str) -> str:
    sync_state = Path.home() / ".arkaos" / "sync-state.json"
    if not sync_state.is_file():
        return "\n[arka:update-available] Never synced. Run /arka update."
    try:
        synced = str(json.loads(sync_state.read_text(encoding="utf-8"))["version"])
    except (OSError, json.JSONDecodeError, KeyError):
        synced = "none"
    if synced != version:
        return (
            f"\n[arka:update-available] Core v{version} != synced"
            f" v{synced}. Run /arka update."
        )
    return ""


def _workflow_line() -> str:
    try:
        from core.workflow.state import get_state

        state = get_state()
    except Exception:  # degraded env — banner never breaks
        return ""
    if not state:
        return ""
    phases = state.get("phases") or {}
    completed = sum(
        1 for p in phases.values()
        if isinstance(p, dict) and p.get("status") == "completed"
    )
    line = f"\nWorkflow: {state.get('workflow', '')} ({completed}/{len(phases)})"
    if state.get("branch"):
        line += f" branch:{state['branch']}"
    violations = len(state.get("violations") or [])
    if violations:
        line += f" VIOLATIONS:{violations}"
    return line + "\n"


def _forge_line() -> str:
    try:
        from core.forge.persistence import get_active_plan

        plan = get_active_plan()
    except Exception:
        return ""
    if plan is None:
        return ""
    name = getattr(plan, "name", "")
    status = getattr(plan, "status", "")
    phases = len(getattr(plan, "plan_phases", []) or [])
    if status == "approved":
        return f"\n  ⚒ Forge plan pending: {name} | Phases: {phases} | /forge resume"
    if status == "executing":
        governance = getattr(plan, "governance", None)
        branch = getattr(governance, "branch_strategy", "") or "" if governance else ""
        return f"\n  ⚒ Forge executing: {name} | Phases: {phases} | Branch: {branch}"
    return ""


def _model_fabric() -> str:
    try:
        from core.runtime.model_routing_context import routing_directive

        directive = routing_directive()
        return f"\n\n{directive}" if directive else ""
    except Exception:
        return ""


def _session_resume() -> str:
    try:
        from core.memory.rehydrator import build_resume_context

        ctx = build_resume_context()
    except Exception:
        return ""
    if not ctx:
        return ""
    return "\n\n[SESSION] " + ctx.replace("\n", "\n[SESSION] ")


def _spawn_detached(cmd: list[str], repo: str, log_path: Path | None = None) -> None:
    stdout = subprocess.DEVNULL
    handle = None
    try:
        if log_path is not None:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            handle = log_path.open("a")
            stdout = handle
        subprocess.Popen(
            cmd,
            stdout=stdout,
            stderr=subprocess.STDOUT if handle else subprocess.DEVNULL,
            env={**os.environ, "PYTHONPATH": repo, "ARKAOS_NO_BROWSER": "1"},
            cwd=repo or None,
            start_new_session=True,
        )
    except Exception:
        pass
    finally:
        if handle is not None:
            handle.close()  # the child keeps its own inherited fd


def _trigger_reorganizer(repo: str, config: dict) -> None:
    """Stale-aware AND config-gated: ``cognition.reorganize_on_session``
    (default True) — the F2-1 QG follow-up gate lands here. The staleness
    guard uses UTC, same basis as before."""
    cognition = config.get("cognition") or {}
    if not cognition.get("reorganize_on_session", True):
        return
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    proposal = Path.home() / ".arkaos" / "reorganize-proposals" / f"{today}.md"
    if proposal.is_file() or not repo:
        return
    _spawn_detached([sys.executable, "-m", "core.cognition.reorganizer_cli"], repo)


def _ensure_dashboard(repo: str, config: dict) -> None:
    dashboard = config.get("dashboard") or {}
    if not dashboard.get("ensure_on_session", True):
        return
    script = Path(repo) / "scripts" / "start-dashboard.sh" if repo else None
    if script is None or not script.is_file():
        return
    _spawn_detached(
        ["bash", str(script), "ensure"], repo,
        log_path=Path.home() / ".arkaos" / "logs" / "dashboard-ensure.log",
    )


def build_message(cwd: str) -> str:
    repo = repo_path()
    config = _config()
    name, company = _profile()
    version = _version(repo)
    msg = _BANNER + f"\nOlá, {name} ({company})\n"
    msg += _workflow_line()
    msg += f"ArkaOS v{version}"
    msg += _forge_line()
    msg += _drift(version)
    msg += _EVIDENCE_CONTRACT
    msg += _META_TAG_CONTRACT
    msg += _model_fabric()
    _trigger_reorganizer(repo, config)
    _ensure_dashboard(repo, config)
    msg += _session_resume()
    recap = build_recap(cwd)
    if recap:
        msg += f"\n\n{recap}"
    return msg


def build_recap(cwd: str, budget_ms: int = _BUDGET_MS) -> str:
    """[SESSION-MEMORY] importance+recency recap (F1-A3, semantics kept)."""
    start = time.monotonic()
    try:
        from core.memory.semantic_store import (
            SessionMemoryStore,
            default_db_path,
            neutralize_summary,
        )
        if not default_db_path().is_file():
            return ""
        # Scope-or-skip (defense-in-depth, mirrors L9.5): no resolvable
        # project ⇒ no recap — never a silently-global read.
        project = Path(cwd).name if cwd else ""
        if not project:
            return ""
        store = SessionMemoryStore()
        records = store.recent(project_name=project, limit=_RECAP_ITEMS)
        if not records or (time.monotonic() - start) * 1000 > budget_ms:
            return ""
        lines = ["[SESSION-MEMORY] Prior turns (importance+recency — not semantic):"]
        for record in records:
            summary = neutralize_summary(record.summary)[:_SUMMARY_CHARS]
            if not summary:
                continue
            lines.append(f"[SESSION-MEMORY] - {record.ts[:10]}: {summary}")
        if len(lines) == 1:
            return ""
        backends = ",".join(sorted({r.embedding_backend for r in records})) or "none"
        lines.append(
            f"[SESSION-MEMORY] shown: {len(lines) - 1} turns ({project}),"
            f" backends={backends}"
        )
        return "\n".join(lines)
    except Exception:  # recap is best-effort, banner never breaks
        return ""


def main(stdin_json: dict | None = None) -> int:
    if stdin_json is None:
        stdin_json, _ = read_stdin_json()
    cwd = (
        get_str(stdin_json, "cwd")
        or os.environ.get("ARKA_HOOK_CWD", "")
        or os.getcwd()
    )
    try:
        message = build_message(cwd)
    except Exception:  # absolute fail-open: static banner, exit 0
        message = _BANNER + "\nOlá, founder (WizardingCode)\nArkaOS"
    print(json.dumps({"systemMessage": message}))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
