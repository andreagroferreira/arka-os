"""OpenCode plugin bridge — JSON stdin/stdout hook adapter.

OpenCode has no shell-hook chain like Claude Code; its plugin system
(TypeScript, ``~/.config/opencode/plugins/``) emits events instead. The
``arka.ts`` plugin shells out to this module so the OpenCode runtime
gets the same governance stack as the Claude runtime:

    prompt    token-hygiene checks (UserPromptSubmit parity)
    pre_tool  research gate + frontend gate (PreToolUse parity)
    post_tool MCP usage telemetry (PostToolUse parity)
    idle      kb-citation + [arka:meta] compliance (Stop-hook parity)
              + detached turn capture into the shared cross-runtime
              session memory (core.memory.turn_capture capture-text)
    memory    L9.5 parity — cross-runtime session memory retrieval +
              once-per-session handoff digest on the prompt hot path
    compact   gate state context (PreCompact parity)

CLI contract::

    echo '{"action": "pre_tool", ...}' | arka-py -m core.runtime.opencode_hooks

Output is a single JSON object on stdout. The module NEVER raises and
always exits 0 — a hook bridge must never break a turn (fail-open,
same posture as the bash hooks it mirrors).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_TELEMETRY_DIR = Path.home() / ".arkaos" / "telemetry"
_PROMPT_CACHE_DIR = Path.home() / ".arkaos" / "context-cache"

_BUILTIN_MAP = {
    "webfetch": "WebFetch",
    "websearch": "WebSearch",
    "edit": "Edit",
    "write": "Write",
    "read": "Read",
    "bash": "Bash",
    "grep": "Grep",
    "glob": "Glob",
    "task": "Task",
}

_ARG_KEY_MAP = {
    "filePath": "file_path",
    "newString": "new_string",
    "oldString": "old_string",
}

_VAGUE_RE = re.compile(
    r"\b(fix the bug|that file|esse ficheiro|esse bug|o erro|aquilo)\b",
    re.IGNORECASE,
)

_STOPWORDS = frozenset({
    "a", "o", "e", "de", "do", "da", "que", "em", "um", "uma", "para",
    "com", "os", "as", "no", "na", "the", "and", "to", "of", "in", "is",
})


def _map_tool_name(name: str) -> str:
    """OpenCode ``server_tool`` / builtin -> Claude-style tool name."""
    if name in _BUILTIN_MAP:
        return _BUILTIN_MAP[name]
    if name.startswith("mcp__"):
        return name
    server, sep, tool = name.partition("_")
    if sep and server and tool:
        return f"mcp__{server}__{tool}"
    return name


def _map_args(args: dict) -> dict:
    return {_ARG_KEY_MAP.get(k, k): v for k, v in (args or {}).items()}


def _keywords(text: str) -> set[str]:
    return {
        w
        for w in re.findall(r"[a-zA-ZÀ-ÿ]{4,}", text.lower())
        if w not in _STOPWORDS
    }


def _append_jsonl(path: Path, entry: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _recent_prompts(session_id: str) -> list[str]:
    safe = re.sub(r"[^A-Za-z0-9_-]", "", session_id or "default")
    path = _PROMPT_CACHE_DIR / f"opencode-prompts-{safe}.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []


def _store_prompt(session_id: str, prompt: str) -> None:
    safe = re.sub(r"[^A-Za-z0-9_-]", "", session_id or "default")
    path = _PROMPT_CACHE_DIR / f"opencode-prompts-{safe}.json"
    history = _recent_prompts(session_id)
    history.append(prompt[:500])
    _append = history[-3:]
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(_append), encoding="utf-8")
    except OSError:
        pass


def _load_commands_registry() -> list[dict]:
    """knowledge/commands-registry.json from the repo root arka-py runs
    against (PYTHONPATH chain: .repo-path -> dev checkout -> lib)."""
    path = Path(__file__).resolve().parents[2] / "knowledge" / "commands-registry.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        commands = data.get("commands", [])
        return commands if isinstance(commands, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _routing_lines(prompt: str, session_id: str, cwd: str) -> list[str]:
    """UserPromptSubmit routing parity (core/hooks/user_prompt_submit.py):
    [ARKA:ROUTE] on every prompt + L1 [dept:X] + L5 [hint:/cmd] +
    [ARKA:WORKFLOW-REQUIRED] on creation/implementation prompts. The
    directive strings and the verb regex are IMPORTED from the claude
    hook — one source of truth, zero drift."""
    from core.hooks.user_prompt_submit import (
        _ROUTE_REMINDER,
        _WF_VERB_RE,
        _WORKFLOW_DIRECTIVE,
    )

    lines = [_ROUTE_REMINDER.strip()]
    if not prompt:
        return lines
    try:
        from core.synapse.layers import (
            CommandHintsLayer,
            DepartmentLayer,
            PromptContext,
        )

        ctx = PromptContext(
            user_input=prompt,
            cwd=cwd,
            project_name=Path(cwd).name if cwd else "",
            runtime_id="opencode",
            extra={"session_id": session_id},
        )
        dept = DepartmentLayer().compute(ctx)
        if dept.tag:
            lines.append(dept.tag)
        commands = _load_commands_registry()
        if commands:
            hints = CommandHintsLayer(commands=commands).compute(ctx)
            if hints.tag:
                lines.append(hints.tag)
    except Exception:  # noqa: BLE001 — routing hints are a bonus, never a blocker
        pass
    if prompt[0] not in ("/", "!") and _WF_VERB_RE.search(prompt):
        lines.append(_WORKFLOW_DIRECTIVE.strip())
    return lines


def _action_prompt(payload: dict) -> dict:
    """Token-hygiene parity (config/hooks/token-hygiene.sh) + the routing
    injection (UserPromptSubmit parity) that makes /arka optional."""
    prompt = str(payload.get("prompt", ""))
    session_id = str(payload.get("session_id", ""))
    suggestions: list[str] = []
    routing = _routing_lines(prompt, session_id, str(payload.get("cwd", "")))

    ctx = payload.get("context_pct")
    if isinstance(ctx, (int, float)):
        if ctx > 80:
            suggestions.append(
                f"[arka:warn] Contexto a {int(ctx)}% — considera /compact."
            )
        elif ctx > 60:
            suggestions.append(
                f"[arka:suggest] Contexto a {int(ctx)}% — vigia o orçamento."
            )

    history = _recent_prompts(session_id)
    if history and prompt:
        current = _keywords(prompt)
        if current:
            recent = set().union(*(_keywords(p) for p in history[-3:]))
            if recent and len(current & recent) / len(current) < 0.3:
                suggestions.append(
                    "[arka:suggest] Mudança de tópico — considera /clear "
                    "para libertar contexto."
                )
    if prompt:
        _store_prompt(session_id, prompt)

    if len(prompt) > 2000 and "```" in prompt:
        suggestions.append(
            "[arka:suggest] Paste grande — usa @filepath em vez de colar "
            "código no prompt."
        )

    if _VAGUE_RE.search(prompt) and "@" not in prompt:
        suggestions.append(
            "[arka:suggest] Referência vaga — usa @path para apontar o "
            "ficheiro concreto."
        )

    return {"suggestions": suggestions, "routing": routing}


def _action_pre_tool(payload: dict) -> dict:
    tool = str(payload.get("tool", ""))
    mapped = _map_tool_name(tool)
    session_id = str(payload.get("session_id", ""))
    args = _map_args(payload.get("args") or {})

    from core.workflow import research_gate

    decision = research_gate.evaluate_research_gate(
        mapped,
        session_id=session_id,
        query=str(args.get("query", "") or args.get("url", "")),
    )
    if not decision.allow:
        research_gate.record_telemetry(session_id, mapped, decision)
        return {
            "allow": False,
            "reason": decision.reason,
            "message": decision.to_stderr_message(),
        }
    if decision.nudge:
        research_gate.record_telemetry(session_id, mapped, decision)
        return {
            "allow": True,
            "reason": decision.reason,
            "message": decision.to_stderr_message(),
        }

    if tool in ("edit", "write"):
        from core.workflow import frontend_gate

        fe = frontend_gate.evaluate(
            _map_tool_name(tool),
            "",
            session_id,
            str(payload.get("cwd", "")),
            args,
            messages=payload.get("messages") or [],
        )
        frontend_gate.record_telemetry(session_id, mapped, fe)
        if not fe.allow or fe.reason == "no-design-marker":
            return {
                "allow": fe.allow,
                "reason": fe.reason,
                "message": fe.to_stderr_message(),
            }

    return {"allow": True, "reason": "ok", "message": ""}


def _action_post_tool(payload: dict) -> dict:
    tool = str(payload.get("tool", ""))
    mapped = _map_tool_name(tool)
    session_id = str(payload.get("session_id", ""))

    from core.runtime import mcp_telemetry

    recorded = mcp_telemetry.record(mapped, session_id=session_id)
    _append_jsonl(
        _TELEMETRY_DIR / "opencode-tools.jsonl",
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "session": session_id,
            "tool": mapped,
            "ok": bool(payload.get("ok", True)),
        },
    )
    return {"recorded_mcp": recorded}


def _enqueue_turn_capture(session_id: str, text: str, cwd: str) -> None:
    """F1-A2 parity: fire-and-forget semantic turn capture — the same
    detached-worker pattern as core/hooks/stop.py, fed with the assistant
    text directly (OpenCode has no Claude-style JSONL transcript)."""
    if not session_id or not text.strip():
        return
    repo = Path(__file__).resolve().parents[2]
    if not (repo / "core" / "memory" / "turn_capture.py").is_file():
        return
    try:
        proc = subprocess.Popen(
            [sys.executable, "-m", "core.memory.turn_capture",
             "capture-text", session_id, cwd or "", "opencode"],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env={**os.environ, "PYTHONPATH": str(repo)},
            start_new_session=True,
        )
        if proc.stdin:
            try:
                proc.stdin.write(text.encode("utf-8", "replace"))
                proc.stdin.close()
            except (BrokenPipeError, OSError):
                pass
    except Exception:  # noqa: BLE001 — a hook bridge never breaks a turn
        pass


def _action_idle(payload: dict) -> dict:
    """Stop-hook parity: kb-citation + [arka:meta] compliance (soft),
    plus detached turn capture into the shared cross-runtime memory."""
    text = str(payload.get("response_text", ""))
    session_id = str(payload.get("session_id", ""))
    nudges: list[str] = []

    from core.governance import kb_cite_check

    result = kb_cite_check.check_citation(text)
    if not result.passed and result.suggestion:
        nudges.append(result.suggestion)

    if len(text) > 400 and "[arka:meta]" not in text and "[arka:trivial]" not in text:
        nudges.append(
            "[arka:suggest] Resposta substantiva sem tag [arka:meta] — "
            "fecha com kb=N research=X persona=Y gap=Z critic=W."
        )

    _enqueue_turn_capture(session_id, text, str(payload.get("cwd", "")))

    _append_jsonl(
        _TELEMETRY_DIR / "opencode-compliance.jsonl",
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "session": session_id,
            "kb_cite": result.reason,
            "meta_tag": "[arka:meta]" in text,
            "nudges": len(nudges),
        },
    )
    return {"nudges": nudges}


_HANDOFF_MAX_AGE_H = 24
_HANDOFF_SUMMARY_CHARS = 160


def _handoff_marker(session_id: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_-]", "", session_id or "default")
    return _PROMPT_CACHE_DIR / f"opencode-handoff-{safe}.json"


def _handoff_line(session_id: str, project: str) -> str:
    """Once per session: when the newest turn in this project was captured
    by ANOTHER runtime, surface it — that is the cross-runtime handoff."""
    if not project or _handoff_marker(session_id).exists():
        return ""
    from core.memory.semantic_store import (
        SessionMemoryStore,
        default_db_path,
        neutralize_summary,
    )

    if not default_db_path().is_file():
        return ""
    latest = SessionMemoryStore().cross_runtime_handoff(
        project, "opencode", exclude_session=session_id,
        max_age_h=_HANDOFF_MAX_AGE_H,
    )
    if not latest:
        return ""
    try:
        _handoff_marker(session_id).parent.mkdir(parents=True, exist_ok=True)
        _handoff_marker(session_id).write_text(
            json.dumps({"shown_at": datetime.now(timezone.utc).isoformat()}),
            encoding="utf-8",
        )
    except OSError:
        pass
    summary = neutralize_summary(latest.summary)[:_HANDOFF_SUMMARY_CHARS]
    stamp = latest.ts[11:16] + "Z" if len(latest.ts) >= 16 else latest.ts
    tail = f": {summary}" if summary else ""
    return f"[arka:handoff] última sessão em {latest.runtime} ({stamp}){tail}"


def _action_memory(payload: dict) -> dict:
    """L9.5 parity for the prompt hot path: pre-ranked semantic neighbours
    + live scoped keyword hits from the shared cross-runtime store, plus
    the once-per-session handoff digest. Never embeds — zero cost here."""
    prompt = str(payload.get("prompt", ""))
    session_id = str(payload.get("session_id", ""))
    cwd = str(payload.get("cwd", ""))
    lines: list[str] = []
    try:
        from core.synapse.session_memory_layer import (
            _format_item,
            _l95_feature_flag_on,
            _read_session_cache,
        )

        if not _l95_feature_flag_on():
            return {"context": []}
        seen: set[str] = set()
        items, ranked_at = _read_session_cache(session_id)
        for item in items:
            line = _format_item(item, ranked_at)
            if line and item.get("summary") not in seen:
                seen.add(item.get("summary"))
                lines.append(line)
        project = Path(cwd).name if cwd else ""
        if prompt and project:
            from core.memory.semantic_store import (
                SessionMemoryStore,
                default_db_path,
            )

            if default_db_path().is_file():
                hits = SessionMemoryStore().keyword_search(prompt, project, top_k=2)
                for hit in hits:
                    line = _format_item(hit)
                    if line and hit.get("summary") not in seen:
                        seen.add(hit.get("summary"))
                        lines.append(line)
        handoff = _handoff_line(session_id, project)
        if handoff:
            lines.insert(0, handoff)
    except Exception:  # noqa: BLE001 — memory is a bonus, never a blocker
        return {"context": []}
    return {"context": lines[:6]}


def _action_compact(payload: dict) -> dict:
    """PreCompact parity: carry gate state across compaction."""
    from core.workflow import state

    context: list[str] = [
        "## ArkaOS gate state (injected by the opencode bridge)",
        "Obrigatório: evidence flow G1 contexto -> G2 plano (aprovação) "
        "-> G3 execução (teste real, exit 0) -> G4 review. Emite "
        "[arka:gate:N] em cada gate; [arka:trivial] <razão> só para "
        "edição de 1 ficheiro < 10 linhas.",
    ]
    try:
        current = state.get_state()
        if current:
            context.append(f"Workflow activo: {json.dumps(current)[:400]}")
    except Exception:  # noqa: BLE001 — fail-open
        pass
    return {"context": context}


_ACTIONS = {
    "prompt": _action_prompt,
    "pre_tool": _action_pre_tool,
    "post_tool": _action_post_tool,
    "idle": _action_idle,
    "memory": _action_memory,
    "compact": _action_compact,
}


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        payload = {}
    action = str(payload.pop("action", ""))
    handler = _ACTIONS.get(action)
    result: dict
    if handler is None:
        result = {"error": f"unknown action: {action!r}"}
    else:
        try:
            result = handler(payload)
        except Exception as exc:  # noqa: BLE001 — fail-open, never block
            result = {"error": f"{type(exc).__name__}: {exc}"}
    sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
