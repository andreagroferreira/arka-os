"""PostToolUse — consolidated entrypoint (PR-6 v4.1.0 hook hygiene).

Replaces the ~38 python3/jq spawn sites of the old ``post-tool-use.sh``
with ONE python process (plus one detached child for the cognition
capture, preserving its fire-and-forget backgrounding, and one optional
venv fallback for the yaml-needing workflow sections on machines whose
ambient python3 lacks PyYAML — mirroring the old ARKAOS_PY resolution).

Section order is preserved exactly:
    1. Flow marker cache write ([arka:routing]/[arka:trivial] detection)
    2. CQO REJECTED experience auto-record + APPROVED pattern stub
    3. Activation tracking for every Task/Agent dispatch
    4. Early exit `{}` when the tool output carries no error signal
    5. Gotchas memory (~/.arkaos/gotchas.json, flock, top-100)
    6. Workflow violation rules 1-3 (branch-isolation, spec-driven,
       sequential-validation) against ~/.arkaos/workflow-state.json
    7. Enforcement engine (core/workflow/enforcer.py, all rules)
    8. Forge scope-creep detection (yaml plan deliverables)
    9. Cognition capture enqueue (detached background process)
   10. Hook metrics append + additionalContext output

Sections 6-8 need core.workflow / yaml. When the in-process import fails
(PyYAML-less ambient python3) and the ArkaOS venv exists, they are
delegated ONCE to ``<venv>/bin/python3 -m core.hooks.post_tool_use
--workflow-sections`` — the same interpreter the old hook used for them.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from core.hooks._shared import (
    ensure_root_on_path,
    get_str,
    read_stdin_json,
    repo_path,
    resolve_arkaos_root,
    venv_python,
)

try:
    import fcntl  # POSIX only
    _HAS_FLOCK = True
except ImportError:
    _HAS_FLOCK = False


_ROUTING_RE = re.compile(
    r"\[arka:routing\][ \t]*([A-Za-z_-]+)[ \t]*->[ \t]*([A-Za-z_-]+)",
    re.IGNORECASE,
)
_TRIVIAL_RE = re.compile(r"\[arka:trivial\][ \t]*\S+", re.IGNORECASE)
_REJECTED_RE = re.compile(r"Quality Gate Verdict:[ \t]*REJECTED")
_APPROVED_RE = re.compile(r"Quality Gate Verdict:[ \t]*APPROVED")
_REVIEWING_RE = re.compile(r"\[arka:reviewing[ \t]+([A-Za-z0-9_.-]+)\]")
_PATTERN_SUGGEST_RE = re.compile(
    r"\[arka:pattern-suggest[ \t]+([A-Za-z0-9_.-]+)[ \t]+([^][]+)\]"
)
_ERROR_TRIGGER_RE = re.compile(
    r"(error:|fatal:|exception:|failed|ENOENT|EACCES|EPERM|panic:)",
    re.IGNORECASE,
)
_ERROR_LINE_RE = re.compile(
    r"(error|fatal|exception|failed|ENOENT|EACCES|EPERM|panic|cannot"
    r"|not found|permission denied)",
    re.IGNORECASE,
)
_CODE_FILE_RE = re.compile(r"\.(py|js|ts|vue|php|jsx|tsx)$")

_CATEGORY_RES: tuple[tuple[str, re.Pattern], ...] = (
    ("laravel", re.compile(
        r"(artisan|eloquent|laravel|blade|migration|composer|php )", re.I)),
    ("frontend", re.compile(
        r"(npm|node|vue|react|nuxt|next|vite|webpack|typescript|tsx|jsx)",
        re.I)),
    ("git", re.compile(
        r"(git |merge|rebase|checkout|branch|commit|push|pull)", re.I)),
    ("database", re.compile(
        r"(sql|postgres|mysql|database|migration|table|column|constraint)",
        re.I)),
    ("permissions", re.compile(
        r"(permission|denied|EACCES|EPERM|chmod|chown|sudo)", re.I)),
    ("testing", re.compile(
        r"(test|assert|expect|jest|phpunit|bats|coverage)", re.I)),
)


def _locked(fh) -> None:
    if _HAS_FLOCK:
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        except OSError:
            pass


def _unlocked(fh) -> None:
    if _HAS_FLOCK:
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass


# ─── Section 1: flow marker cache ────────────────────────────────────────


def _confirm_flow_authorization(session_id: str, transcript_path: str) -> None:
    """Confirm persistent flow authorization from the transcript.

    Replaces the dead ``_write_flow_marker`` that read a non-existent
    ``assistant_message`` payload field. Reads the same transcript the
    enforcer trusts and, when a flow marker is present, writes a confirmed
    authorization that survives compaction and the 20-message window.
    """
    if not session_id:
        return
    try:
        from core.workflow.flow_authorization import confirm
        from core.workflow.flow_enforcer import (
            _load_last_assistant_messages,
            _scan_markers,
        )
    except Exception:
        return
    try:
        messages = _load_last_assistant_messages(transcript_path, 20)
        marker_found, _ = _scan_markers(messages)
        if marker_found is not None:
            confirm(session_id, marker_found)
    except Exception:
        pass


# ─── Section 2+3: CQO verdicts, pattern stubs, activation ───────────────


def _record_cqo_rejected(tool_output: str, prompt: str, session_id: str) -> None:
    if not _REJECTED_RE.search(tool_output):
        return
    match = _REVIEWING_RE.search(prompt)
    if not match:
        return
    try:
        from core.governance.cqo_experience_recorder import record_from_verdict
        record_from_verdict(
            verdict_text=tool_output,
            agent_id=match.group(1),
            session_id=session_id,
            context="auto-recorded via PostToolUse hook (cqo dispatch REJECTED)",
        )
    except Exception:
        pass


def _record_pattern_stub(tool_output: str, prompt: str) -> None:
    if not _APPROVED_RE.search(tool_output):
        return
    match = _PATTERN_SUGGEST_RE.search(prompt)
    if not match:
        return
    pid, pname = match.group(1), match.group(2).strip()
    if not pid or not pname:
        return
    try:
        from core.knowledge.pattern_cards import (
            PatternCard,
            query_patterns,
            record_pattern,
        )
        if any(c.id == pid for c in query_patterns(limit=1000)):
            return
        ts = datetime.now(timezone.utc).isoformat()
        record_pattern(PatternCard(
            id=pid,
            name=pname,
            feature_keywords=[pid.replace("-", " "), pname.lower()],
            description=(
                "Stub auto-created from APPROVED CQO verdict — enrich via "
                "record_pattern() or by editing the JSONL."
            ),
            stack=[], files=[], acceptance_criteria=[], edge_cases=[],
            references=[], projects_using=["arkaos"],
            created_at=ts, last_updated=ts,
        ))
    except Exception:
        pass


def _record_activation(subagent_type: str, session_id: str) -> None:
    if not subagent_type:
        return
    try:
        from core.governance.activation_tracker import record_activation
        record_activation(subagent_type=subagent_type, session_id=session_id)
    except Exception:
        pass


# ─── Section 5: gotchas memory ───────────────────────────────────────────


def _extract_error_line(tool_output: str) -> str:
    lines = tool_output.splitlines()
    for line in lines:
        if _ERROR_LINE_RE.search(line):
            return line
    # Fallback mirrors `head -5 | tail -1`.
    head = lines[:5]
    return head[-1] if head else ""


def _normalize_pattern(error_line: str) -> str:
    pattern = re.sub(
        r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}[^ ]*", "TIMESTAMP",
        error_line,
    )
    pattern = re.sub(r"[0-9a-f]{7,40}", "HASH", pattern)
    pattern = re.sub(r"line \d+", "line N", pattern)
    pattern = re.sub(r":\d+:", ":N:", pattern)
    return pattern[:200]


def _categorize(error_line: str) -> str:
    for category, regex in _CATEGORY_RES:
        if regex.search(error_line):
            return category
    return "general"


def _fixes_file() -> Path:
    arka_os = os.environ.get(
        "ARKA_OS", str(Path.home() / ".claude" / "skills" / "arka")
    )
    fixes = Path(arka_os) / "config" / "gotchas-fixes.json"
    if fixes.is_file():
        return fixes
    try:
        repo = (Path(arka_os) / ".repo-path").read_text(encoding="utf-8").strip()
    except OSError:
        repo = ""
    return Path(repo) / "config" / "gotchas-fixes.json" if repo else fixes


def _match_suggestion(error_line: str) -> str:
    fixes_path = _fixes_file()
    if not fixes_path.is_file():
        return ""
    try:
        fixes = json.loads(fixes_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    for fix in fixes.get("fixes", []):
        pattern = fix.get("pattern_match", "")
        try:
            if pattern and re.search(pattern, error_line, re.IGNORECASE):
                return str(fix.get("suggestion", ""))
        except re.error:
            continue
    return ""


def _detect_project(cwd: str) -> str:
    if not cwd:
        return ""
    arka_os = os.environ.get(
        "ARKA_OS", str(Path.home() / ".claude" / "skills" / "arka")
    )
    try:
        repo = (Path(arka_os) / ".repo-path").read_text(encoding="utf-8").strip()
    except OSError:
        repo = ""
    if repo and (Path(repo) / "projects").is_dir():
        for proj_dir in sorted((Path(repo) / "projects").iterdir()):
            marker = proj_dir / ".project-path"
            if not marker.is_file():
                continue
            try:
                proj_path = marker.read_text(encoding="utf-8").strip()
            except OSError:
                continue
            if proj_path and cwd.startswith(proj_path):
                return proj_dir.name
    return Path(cwd).name


def _store_gotcha(
    pattern: str, error_line: str, category: str,
    tool_name: str, project: str, suggestion: str,
) -> None:
    gotchas_file = Path.home() / ".arkaos" / "gotchas.json"
    lock_file = Path.home() / ".arkaos" / "gotchas.lock"
    gotchas_file.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        with lock_file.open("a", encoding="utf-8") as lock_fh:
            _locked(lock_fh)
            try:
                try:
                    entries = json.loads(
                        gotchas_file.read_text(encoding="utf-8")
                    )
                    if not isinstance(entries, list):
                        entries = []
                except (OSError, json.JSONDecodeError):
                    entries = []
                existing = next(
                    (e for e in entries if e.get("pattern") == pattern), None
                )
                if existing is not None:
                    existing["count"] = int(existing.get("count", 0)) + 1
                    existing["last_seen"] = now
                    if project and project not in existing.get("projects", []):
                        existing.setdefault("projects", []).append(project)
                    if suggestion and not existing.get("suggestion"):
                        existing["suggestion"] = suggestion
                else:
                    entries.append({
                        "pattern": pattern,
                        "full_pattern": error_line[:500],
                        "category": category,
                        "tool": tool_name,
                        "count": 1,
                        "first_seen": now,
                        "last_seen": now,
                        "projects": [project] if project else [],
                        "suggestion": suggestion or None,
                    })
                entries.sort(key=lambda e: -int(e.get("count", 0)))
                tmp = gotchas_file.with_suffix(".json.tmp")
                tmp.write_text(
                    json.dumps(entries[:100]), encoding="utf-8"
                )
                tmp.replace(gotchas_file)
            finally:
                _unlocked(lock_fh)
    except OSError:
        pass


# ─── Sections 6-8: workflow rules, enforcer, forge (yaml-needing) ───────


def _workflow_state() -> dict | None:
    state_file = Path.home() / ".arkaos" / "workflow-state.json"
    if not state_file.is_file():
        return None
    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return state if isinstance(state, dict) else None


def _phase_status(state: dict, phase: str) -> str:
    return str(
        (state.get("phases", {}) or {}).get(phase, {}).get("status", "")
    )


def _detect_rule_violations(input_data: dict) -> tuple[str, list[tuple]]:
    """Rules 1-3 (stdlib detection). Returns (violation_msg, to_persist)."""
    state = _workflow_state()
    if state is None:
        return "", []
    tool_name = get_str(input_data, "tool_name")
    tool_output = get_str(input_data, "tool_output")
    violation_msg = ""
    persist: list[tuple] = []

    if tool_name == "Bash":
        on_master = any(
            re.match(r"^\[(master|main)", line)
            for line in tool_output.splitlines()
        )
        cmd_text = get_str(input_data, "command")
        if on_master and re.search(r"git commit", cmd_text):
            persist.append((
                "branch-isolation",
                "Commit on master/main while workflow active", "Bash", "",
            ))
            violation_msg = (
                "VIOLATION [branch-isolation]: Commit on master while "
                "workflow active. Use a feature branch."
            )

    if tool_name in ("Write", "Edit"):
        file_path = get_str(input_data, "file_path")
        if _CODE_FILE_RE.search(file_path):
            if _phase_status(state, "spec") != "completed":
                persist.append((
                    "spec-driven", "Code edited without completed spec",
                    tool_name, file_path,
                ))
                violation_msg = (
                    f"VIOLATION [spec-driven]: Code edited without completed "
                    f"spec ({file_path}). Complete the spec phase first."
                )
            if not violation_msg and _phase_status(
                state, "implementation"
            ) == "pending":
                persist.append((
                    "sequential-validation",
                    "Code written before implementation phase started",
                    tool_name, file_path,
                ))
                violation_msg = (
                    f"VIOLATION [sequential-validation]: Implementation "
                    f"started before planning completed ({file_path})."
                )

    return violation_msg, persist


def _run_workflow_sections(input_data: dict, persist: list, msg: str) -> str:
    """Persist rule violations + run enforcer + forge check (needs yaml).

    Raises ImportError when the interpreter lacks the dependencies —
    caller falls back to the venv delegate.
    """
    import yaml  # noqa: F401 — probe: forge + core.workflow need it
    from core.workflow.enforcer import enforce_tool
    from core.workflow.state import add_violation

    for rule_id, message, tool, file_path in persist:
        try:
            add_violation(rule_id, message, tool, file_path)
        except Exception:
            pass

    msg = _enforcer_messages(input_data, enforce_tool, add_violation, msg)
    if not msg:
        msg = _forge_violation(input_data, yaml)
    return msg


def _enforcer_messages(input_data, enforce_tool, add_violation, msg: str) -> str:
    tool_name = get_str(input_data, "tool_name")
    extra = {}
    if tool_name == "Bash":
        try:
            branch = subprocess.check_output(
                ["git", "branch", "--show-current"],
                text=True, stderr=subprocess.DEVNULL,
            ).strip()
            extra["git_branch"] = branch
        except Exception:
            extra["git_branch"] = ""
    try:
        result = enforce_tool(
            tool_name=tool_name,
            command=get_str(input_data, "command"),
            file_path=get_str(input_data, "file_path"),
            user_input=get_str(input_data, "user_input"),
            **extra,
        )
    except Exception:
        return msg
    if not result.violations:
        return msg
    for v in result.violations:
        try:
            add_violation(v.rule_id, v.message, v.tool, v.file_path, v.severity)
        except Exception:
            pass
    for message in result.messages:
        if message:
            msg = f"{msg}\n{message}" if msg else message
    if result.blocked:
        msg = f"🔴 BLOCK: {msg}"
    return msg


def _forge_violation(input_data: dict, yaml_mod) -> str:
    active = Path.home() / ".arkaos" / "plans" / "active.yaml"
    if not active.is_file():
        return ""
    tool_name = get_str(input_data, "tool_name")
    if tool_name not in ("Edit", "Write"):
        return ""
    try:
        forge_id = active.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    forge_file = Path.home() / ".arkaos" / "plans" / f"{forge_id}.yaml"
    if not forge_file.is_file():
        return ""
    edited = get_str(input_data, "file_path")
    if not edited:
        return ""
    try:
        plan = yaml_mod.safe_load(forge_file.read_text(encoding="utf-8")) or {}
    except Exception:
        return ""
    if plan.get("status", "") != "executing":
        return ""
    deliverables = [
        d for p in plan.get("plan_phases", []) for d in p.get("deliverables", [])
    ]
    if not deliverables:
        return ""
    if any(d in edited or edited.endswith(d) for d in deliverables):
        return ""
    return (
        f"⚠ Forge scope-creep: editing {edited} which is outside forge "
        f"plan deliverables."
    )


def _workflow_sections_with_fallback(
    input_data: dict, root: str, persist: list, msg: str
) -> str:
    """In-process when yaml is importable; else delegate ONCE to the venv."""
    try:
        return _run_workflow_sections(input_data, persist, msg)
    except ImportError:
        pass
    except Exception:
        return msg
    venv_py = venv_python()
    if venv_py is None:
        return msg
    payload = json.dumps({
        "input": input_data,
        "persist": persist,
        "violation_msg": msg,
    })
    try:
        proc = subprocess.run(
            [venv_py, "-m", "core.hooks.post_tool_use", "--workflow-sections"],
            input=payload, capture_output=True, text=True, timeout=8,
            env={**os.environ, "PYTHONPATH": root},
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return str(
                json.loads(proc.stdout).get("violation_msg", msg) or msg
            )
    except Exception:
        pass
    return msg


# ─── Section 9: cognition capture (detached, fire-and-forget) ───────────


def _enqueue_cognition_capture(session_id: str, tool_output: str) -> None:
    if not session_id or not tool_output:
        return
    repo = repo_path()
    if not repo or not Path(repo).is_dir():
        return
    try:
        proc = subprocess.Popen(
            [sys.executable, "-m", "core.cognition.retrieval", "capture",
             session_id],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env={**os.environ, "PYTHONPATH": repo},
            start_new_session=True,  # replaces `& disown`
        )
        if proc.stdin is not None:
            try:
                proc.stdin.write(tool_output.encode("utf-8", "replace"))
                proc.stdin.close()
            except (BrokenPipeError, OSError):
                pass
    except Exception:
        pass


# ─── Section 10: metrics ─────────────────────────────────────────────────


def _log_metrics(duration_ms: int) -> None:
    metrics_file = Path.home() / ".arkaos" / "hook-metrics.json"
    lock_file = Path.home() / ".arkaos" / "hook-metrics.lock"
    metrics_file.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        with lock_file.open("a", encoding="utf-8") as lock_fh:
            _locked(lock_fh)
            try:
                try:
                    entries = json.loads(
                        metrics_file.read_text(encoding="utf-8")
                    )
                    if not isinstance(entries, list):
                        entries = []
                except (OSError, json.JSONDecodeError):
                    entries = []
                entries.append({
                    "hook": "post-tool-use",
                    "duration_ms": duration_ms,
                    "timestamp": now,
                })
                tmp = metrics_file.with_suffix(".json.tmp")
                tmp.write_text(json.dumps(entries[-500:]), encoding="utf-8")
                tmp.replace(metrics_file)
            finally:
                _unlocked(lock_fh)
    except OSError:
        pass


# ─── Entry point ─────────────────────────────────────────────────────────


def main(stdin_json: dict | None = None) -> int:
    start = time.monotonic()
    if stdin_json is None:
        stdin_json, _ = read_stdin_json()
    root = resolve_arkaos_root()
    ensure_root_on_path(root)

    tool_name = get_str(stdin_json, "tool_name")
    tool_output = get_str(stdin_json, "tool_output")
    exit_code = get_str(stdin_json, "exit_code") or "0"
    cwd = get_str(stdin_json, "cwd")
    session_id = get_str(stdin_json, "session_id")
    transcript_path = get_str(stdin_json, "transcript_path")

    # Claude Code sends no `assistant_message` field (confirmed against the
    # hook docs, 2026-07-05) — the old read was dead and the marker cache
    # was never written. Scan the transcript (the only source hooks have)
    # and confirm persistent authorization when a marker is present.
    _confirm_flow_authorization(session_id, transcript_path)

    # MCP usage telemetry — must run BEFORE the error-signal early exit
    # below (MCP calls normally succeed). record() is a no-op for
    # non-MCP tools and never raises on I/O; the guard covers import
    # failures on stripped installs.
    try:
        from core.runtime.mcp_telemetry import record as _record_mcp_usage
        _record_mcp_usage(tool_name, session_id=session_id)
    except Exception:  # noqa: BLE001 — telemetry must never break the hook
        pass

    if tool_name in ("Task", "Agent"):
        subagent_type = get_str(stdin_json, "tool_input", "subagent_type")
        if subagent_type == "cqo":
            prompt = get_str(stdin_json, "tool_input", "prompt")
            _record_cqo_rejected(tool_output, prompt, session_id)
            _record_pattern_stub(tool_output, prompt)
        _record_activation(subagent_type, session_id)

    # Only process further if there was an error signal (same early exit
    # as the bash version — violations/metrics only run on error turns).
    if exit_code in ("0", "") and not _ERROR_TRIGGER_RE.search(tool_output):
        print("{}")
        return 0

    error_line = _extract_error_line(tool_output)
    if not error_line:
        print("{}")
        return 0
    pattern = _normalize_pattern(error_line)
    if not pattern:
        print("{}")
        return 0

    _store_gotcha(
        pattern, error_line, _categorize(error_line), tool_name,
        _detect_project(cwd), _match_suggestion(error_line),
    )

    violation_msg, persist = _detect_rule_violations(stdin_json)
    violation_msg = _workflow_sections_with_fallback(
        stdin_json, root, persist, violation_msg
    )

    _enqueue_cognition_capture(session_id, tool_output)
    _log_metrics(int((time.monotonic() - start) * 1000))

    if violation_msg:
        print(json.dumps({"additionalContext": violation_msg}))
    else:
        print("{}")
    return 0


def _workflow_sections_main() -> int:
    """`--workflow-sections` mode — the venv delegate entry."""
    payload, _ = read_stdin_json()
    root = resolve_arkaos_root()
    ensure_root_on_path(root)
    input_data = payload.get("input", {})
    persist = [tuple(item) for item in payload.get("persist", [])]
    msg = str(payload.get("violation_msg", ""))
    try:
        msg = _run_workflow_sections(input_data, persist, msg)
    except Exception:
        pass
    print(json.dumps({"violation_msg": msg}))
    return 0


if __name__ == "__main__":
    try:
        if "--workflow-sections" in sys.argv[1:]:
            raise SystemExit(_workflow_sections_main())
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        print("{}")
        raise SystemExit(0)
