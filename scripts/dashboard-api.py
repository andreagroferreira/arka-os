#!/usr/bin/env python3
"""ArkaOS Dashboard API — FastAPI backend for the monitoring dashboard.

Exposes all ArkaOS data as REST endpoints consumed by the Nuxt 3 frontend.

Usage:
    python scripts/dashboard-api.py                    # Start on :3334
    python scripts/dashboard-api.py --port 8000        # Custom port
    python scripts/dashboard-api.py --host 0.0.0.0     # Allow external access
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

# Resolve ArkaOS root
ARKAOS_ROOT = Path(os.environ.get("ARKAOS_ROOT", Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(ARKAOS_ROOT))

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="ArkaOS Dashboard API", version="2.2.0")

# --- WebSocket — thread-safe message queue ---
import asyncio
import queue as _queue

_ws_clients: list[WebSocket] = []
_ws_message_queue: _queue.Queue = _queue.Queue()


def broadcast_from_thread(data: dict):
    """Thread-safe: put message in queue, WebSocket loop picks it up."""
    _ws_message_queue.put(data)


@app.websocket("/ws/tasks")
async def ws_tasks(websocket: WebSocket):
    await websocket.accept()
    _ws_clients.append(websocket)
    try:
        while True:
            # Check message queue every 100ms
            try:
                while not _ws_message_queue.empty():
                    msg = _ws_message_queue.get_nowait()
                    dead = []
                    for client in _ws_clients:
                        try:
                            await client.send_json(msg)
                        except Exception:
                            dead.append(client)
                    for d in dead:
                        if d in _ws_clients:
                            _ws_clients.remove(d)
            except _queue.Empty:
                pass
            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        if websocket in _ws_clients:
            _ws_clients.remove(websocket)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://localhost:\d+",
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# --- Data loaders (lazy, cached) ---

_agents_cache = None
_commands_cache = None


def _load_agents() -> list[dict]:
    global _agents_cache
    if _agents_cache is None:
        path = ARKAOS_ROOT / "knowledge" / "agents-registry-v2.json"
        if path.exists():
            data = json.loads(path.read_text())
            _agents_cache = data.get("agents", [])
        else:
            _agents_cache = []
    return _agents_cache


def _load_commands() -> list[dict]:
    global _commands_cache
    if _commands_cache is None:
        path = ARKAOS_ROOT / "knowledge" / "commands-registry-v2.json"
        if path.exists():
            data = json.loads(path.read_text())
            _commands_cache = data.get("commands", [])
        else:
            _commands_cache = []
    return _commands_cache


def _get_budget_manager():
    try:
        from core.budget.manager import BudgetManager
        db_path = Path.home() / ".arkaos" / "budget-usage.json"
        return BudgetManager(storage_path=db_path)
    except Exception:
        return None


def _get_task_manager():
    try:
        from core.tasks.manager import TaskManager
        db_path = Path.home() / ".arkaos" / "tasks.json"
        return TaskManager(storage_path=db_path)
    except Exception:
        return None


def _get_vector_store():
    try:
        from core.knowledge.vector_store import VectorStore
        db_path = Path.home() / ".arkaos" / "knowledge.db"
        if db_path.exists():
            return VectorStore(db_path)
    except Exception:
        pass
    return None


# --- Endpoints ---

@app.get("/api/overview")
def overview():
    agents = _load_agents()
    commands = _load_commands()
    departments = set(a.get("department", "") for a in agents)

    skills_count = 0
    try:
        skills_count = int(subprocess.run(
            ["find", str(ARKAOS_ROOT / "departments"), "-name", "SKILL.md", "-path", "*/skills/*/SKILL.md"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip().count("\n")) + 1
    except Exception:
        skills_count = 250

    budget_mgr = _get_budget_manager()
    task_mgr = _get_task_manager()
    store = _get_vector_store()

    return {
        "agents": len(agents),
        "commands": len(commands),
        "departments": len(departments),
        "skills": skills_count,
        "workflows": 24,
        "tests": 1809,
        "version": "2.0.3",
        "budget": budget_mgr.get_summary(tier=2).model_dump() if budget_mgr else None,
        "tasks": task_mgr.summary() if task_mgr else {"total": 0, "active": 0, "queued": 0},
        "knowledge": store.get_stats() if store else {"total_chunks": 0, "total_files": 0},
    }


@app.get("/api/agents")
def agents(dept: Optional[str] = Query(None)):
    data = _load_agents()
    if dept:
        data = [a for a in data if a.get("department") == dept]
    return {"agents": data, "total": len(data)}


@app.get("/api/agents/activity")
def agents_activity(period: str = "week"):
    """Per-department activity from the PR47 LLM cost telemetry.

    Returns ``{by_department: {dev: {call_count, total_cost_usd,
    total_tokens_in, total_tokens_out}}}`` derived from rows whose
    ``category`` field starts with ``subagent:``. Each agent's
    dispatch is currently tagged at the department level — finer
    per-agent attribution will land when orchestrators set
    ``ARKA_CALL_CATEGORY=subagent:<dept>:<agent>``.
    """
    try:
        from core.runtime.llm_cost_telemetry import summarise, VALID_PERIODS
    except Exception:  # pragma: no cover - import guard
        return {"by_department": {}, "period": period}
    if period not in VALID_PERIODS:
        period = "week"
    summary = summarise(period=period)
    out: dict[str, dict] = {}
    for category, row in (summary.by_category or {}).items():
        if not isinstance(category, str) or not category.startswith("subagent:"):
            continue
        dept = category.split(":", 1)[1] or "unknown"
        bucket = out.setdefault(dept, {
            "call_count": 0,
            "total_cost_usd": 0.0,
            "any_cost_known": False,
            "total_tokens_in": 0,
            "total_tokens_out": 0,
        })
        bucket["call_count"] += row.get("call_count", 0)
        bucket["total_tokens_in"] += row.get("total_tokens_in", 0)
        bucket["total_tokens_out"] += row.get("total_tokens_out", 0)
        cost = row.get("total_cost_usd")
        if isinstance(cost, (int, float)):
            bucket["total_cost_usd"] += float(cost)
            bucket["any_cost_known"] = True
    for dept, b in out.items():
        if not b.pop("any_cost_known"):
            b["total_cost_usd"] = None
        else:
            b["total_cost_usd"] = round(b["total_cost_usd"], 6)
    return {"by_department": out, "period": period}


@app.get("/api/agents/{agent_id}/activity-strip")
def agent_activity_strip(agent_id: str, period: str = "month"):
    """PR83d v3.6.0 + PR86b v3.16.0 — compact activity payload.

    When telemetry is tagged ``subagent:<dept>:<agent_id>``, the response
    prefers per-agent stats and includes a ``scope: "agent"`` flag.
    Otherwise it falls back to department-level stats with
    ``scope: "department"`` (the original PR83d behaviour).

    Returns:
      {
        "period": "month",
        "scope": "agent" | "department",
        "department": "<dept>",
        "calls": <int>,
        "cost_usd": <float|null>,
        "tokens_in": <int>, "tokens_out": <int>,
        "last_used": "<ISO ts>"|null,
        "dept_rank": <1-based int>|null,
        "dept_count": <int>
      }
    """
    agents = _load_agents()
    base = None
    for a in agents:
        if a.get("id") == agent_id:
            base = dict(a)
            break
    if not base:
        return {"error": "Agent not found"}
    dept = base.get("department") or ""
    try:
        from core.runtime.llm_cost_telemetry import (
            VALID_PERIODS,
            _load_slice,
            _period_cutoff,
            summarise,
        )
    except Exception:
        return {"error": "telemetry unavailable"}
    if period not in VALID_PERIODS:
        period = "month"

    summary = summarise(period=period)
    dept_costs_map: dict[str, float] = {}
    dept_row: dict | None = None
    agent_row: dict | None = None
    for category, row in (summary.by_category or {}).items():
        if not isinstance(category, str) or not category.startswith("subagent:"):
            continue
        # subagent:<dept> OR subagent:<dept>:<agent_id>
        parts = category.split(":", 2)
        cat_dept = parts[1] if len(parts) >= 2 and parts[1] else "unknown"
        cat_agent = parts[2] if len(parts) == 3 else None
        cost = row.get("total_cost_usd")
        cost_f = float(cost) if isinstance(cost, (int, float)) else 0.0
        dept_costs_map[cat_dept] = dept_costs_map.get(cat_dept, 0.0) + cost_f
        if cat_dept == dept and cat_agent is None:
            dept_row = row
        if cat_dept == dept and cat_agent == agent_id:
            agent_row = row

    dept_costs = sorted(dept_costs_map.items(), key=lambda t: t[1], reverse=True)
    dept_rank: Optional[int] = None
    for idx, (d, _) in enumerate(dept_costs, start=1):
        if d == dept:
            dept_rank = idx
            break

    use_agent_scope = agent_row is not None
    scope = "agent" if use_agent_scope else "department"
    target_row = agent_row if use_agent_scope else dept_row

    entries, _ = _load_slice(None, _period_cutoff(period, now=None))
    last_used: Optional[str] = None
    expect_cats = (
        {f"subagent:{dept}:{agent_id}"}
        if use_agent_scope
        else {f"subagent:{dept}"}
    )
    for entry in reversed(entries):
        cat = entry.get("category") or ""
        if isinstance(cat, str) and cat in expect_cats:
            last_used = entry.get("ts")
            break

    return {
        "period": period,
        "scope": scope,
        "department": dept,
        "calls": int(target_row.get("call_count", 0)) if target_row else 0,
        "cost_usd": (
            float(target_row.get("total_cost_usd"))
            if target_row and isinstance(target_row.get("total_cost_usd"), (int, float))
            else None
        ),
        "tokens_in": int(target_row.get("total_tokens_in", 0)) if target_row else 0,
        "tokens_out": int(target_row.get("total_tokens_out", 0)) if target_row else 0,
        "last_used": last_used,
        "dept_rank": dept_rank,
        "dept_count": len(dept_costs),
    }


@app.get("/api/personas/archetypes")
def personas_archetypes():
    """PR93b v3.44.0 — list curated persona archetype templates.

    Used by PersonaWizard step 1 to seed the description field + DNA
    defaults when the operator picks "Start from archetype".
    """
    from core.personas.archetypes import ARCHETYPES
    return {"archetypes": ARCHETYPES, "total": len(ARCHETYPES)}


@app.get("/api/personas/export-all.zip")
def personas_export_all(ids: Optional[str] = None):
    """PR92a v3.39.0 — stream every persona as Markdown inside a ZIP.

    PR93c v3.45.0 — optional ``?ids=a,b,c`` filter narrows the export
    to a specific subset.
    """
    mgr = _get_persona_manager()
    if not mgr:
        return {"error": "Persona manager unavailable"}
    try:
        items = list(mgr.list_all() or [])
    except Exception as exc:  # noqa: BLE001
        return {"error": f"list failed: {exc}"}

    # PR93c — optional id allow-list.
    id_filter: Optional[set[str]] = None
    if ids:
        id_filter = {s.strip() for s in ids.split(",") if s.strip()}
    if id_filter is not None:
        items = [p for p in items if hasattr(p, "id") and p.id in id_filter]

    from core.personas.obsidian_store import ObsidianPersonaStore

    import io
    import zipfile

    buffer = io.BytesIO()
    seen: set[str] = set()
    written = 0
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in items:
            persona = p if hasattr(p, "model_dump") else None
            if persona is None:
                continue
            slug = _zip_persona_slug(persona.name or persona.id)
            if slug in seen:
                slug = f"{slug}-{persona.id[:6]}"
            seen.add(slug)
            try:
                body = ObsidianPersonaStore._render(persona)
            except Exception:  # noqa: BLE001
                continue
            zf.writestr(f"{slug}.md", body)
            written += 1

    if written == 0:
        return {"error": "no personas to export"}

    from fastapi import Response
    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="arkaos-personas.zip"',
        },
    )


def _zip_persona_slug(name: str) -> str:
    """Sanitise a name for use as a zip member filename."""
    import re
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", str(name or ""))
    cleaned = cleaned.strip("-") or "persona"
    return cleaned[:80]


@app.get("/api/personas/{persona_id}/markdown")
def persona_download_markdown(persona_id: str):
    """PR90a v3.31.0 — return the persona as a Markdown file.

    Renders via ObsidianPersonaStore._render so the output matches
    exactly what gets written when the operator clicks Save with a
    configured vault. Responds with ``text/markdown`` and an
    attachment Content-Disposition.
    """
    detail = persona_detail(persona_id)
    if "error" in detail:
        return detail
    from core.personas.obsidian_store import ObsidianPersonaStore
    from core.personas.schema import (
        Persona, PersonaDISC, PersonaEnneagram, PersonaBigFive, PersonaCommunication,
    )
    try:
        persona = Persona(
            id=detail.get("id", ""),
            name=detail.get("name", ""),
            title=detail.get("title", ""),
            tagline=detail.get("tagline", ""),
            source=detail.get("source", ""),
            disc=PersonaDISC(**(detail.get("disc") or {})),
            enneagram=PersonaEnneagram(**(detail.get("enneagram") or {})),
            big_five=PersonaBigFive(**(detail.get("big_five") or {})),
            mbti=detail.get("mbti", "INTJ"),
            mental_models=detail.get("mental_models") or [],
            expertise_domains=detail.get("expertise_domains") or [],
            frameworks=detail.get("frameworks") or [],
            key_quotes=detail.get("key_quotes") or [],
            communication=PersonaCommunication(**(detail.get("communication") or {})),
            bio_md=detail.get("bio_md", "") or "",
            created_at=detail.get("created_at", ""),
        )
    except (TypeError, ValueError) as exc:
        return {"error": f"persona schema mismatch: {exc}"}
    content = ObsidianPersonaStore._render(persona)
    filename = f"{persona.name or persona.id}.md".replace("/", "-")
    from fastapi import Response
    return Response(
        content=content,
        media_type="text/markdown",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@app.get("/api/agents/{agent_id}/yaml")
def agent_download_yaml(agent_id: str):
    """PR89d v3.30.0 — return the raw YAML for the agent.

    Responds with ``application/x-yaml`` and an attachment Content-
    Disposition so browsers prompt a Save As. Refuses unknown agents.
    """
    yaml_file = _resolve_agent_yaml(agent_id)
    if yaml_file is None:
        return {"error": "Agent not found"}
    try:
        content = yaml_file.read_text(encoding="utf-8")
    except OSError as exc:
        return {"error": f"read failed: {exc}"}
    from fastapi import Response
    return Response(
        content=content,
        media_type="application/x-yaml",
        headers={
            "Content-Disposition": f'attachment; filename="{yaml_file.name}"',
        },
    )


@app.get("/api/agents/{agent_id}/history")
def agent_history(agent_id: str, limit: int = 20):
    """PR88d v3.26.0 — combined history for an agent.

    Sources:
      - git log of the YAML file (commit hash, date, subject, author)
      - trash entries (agent-delete + agent-move) where ``item_id``
        matches

    Returns ``{events: [{kind, ts, summary, ref?, author?}]}`` sorted
    desc by ts.
    """
    events: list[dict] = []
    yaml_file = _resolve_agent_yaml(agent_id)
    if yaml_file is not None:
        events.extend(_agent_git_log(yaml_file, limit=limit))
    try:
        from core import trash as _trash
        for entry in _trash.list_trash(limit=50):
            if entry.get("item_id") == agent_id and str(entry.get("kind", "")).startswith("agent-"):
                events.append({
                    "kind": entry.get("kind"),
                    "ts": _trash_ts_to_iso(entry.get("timestamp")),
                    "summary": _trash_summary(entry),
                    "ref": entry.get("id"),
                })
    except Exception:  # noqa: BLE001
        pass
    events.sort(key=lambda e: str(e.get("ts") or ""), reverse=True)
    return {"events": events[: max(0, int(limit))]}


def _agent_git_log(yaml_file: Path, limit: int = 20) -> list[dict]:
    """Run ``git log`` on the YAML file. Best-effort — empty on error."""
    try:
        rel = yaml_file.relative_to(ARKAOS_ROOT).as_posix()
    except ValueError:
        return []
    try:
        result = subprocess.run(
            [
                "git", "log", "--follow", f"-n{int(limit)}",
                "--pretty=format:%H%x09%cI%x09%an%x09%s",
                "--", rel,
            ],
            cwd=str(ARKAOS_ROOT),
            capture_output=True, text=True, timeout=5,
        )
    except (subprocess.SubprocessError, OSError):
        return []
    if result.returncode != 0:
        return []
    rows: list[dict] = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("\t", 3)
        if len(parts) < 4:
            continue
        sha, iso, author, subject = parts
        rows.append({
            "kind": "git-commit",
            "ts": iso,
            "summary": subject,
            "ref": sha[:8],
            "author": author,
        })
    return rows


def _trash_ts_to_iso(ts: object) -> str | None:
    if ts is None:
        return None
    try:
        from datetime import datetime, timezone
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return None


def _trash_summary(entry: dict) -> str:
    kind = entry.get("kind") or ""
    if kind == "agent-move":
        new_path = entry.get("new_path") or ""
        return f"Moved to {Path(new_path).parent.parent.name if new_path else '?'}"
    if kind == "agent-delete":
        return "Deleted (restorable from /trash)"
    return kind


@app.get("/api/agents/{agent_id}/activity")
def agent_activity_detail(agent_id: str, period: str = "month"):
    """PR86b v3.16.0 — alias for /activity-strip. Same payload shape.

    Exposed so callers can use a more natural name when they want the
    full activity row rather than the compact hero strip.
    """
    return agent_activity_strip(agent_id, period)


@app.get("/api/agents/{agent_id}")
def agent_detail(agent_id: str):
    """Get full agent detail including YAML data."""
    # First get registry data
    agents = _load_agents()
    base = None
    for a in agents:
        if a.get("id") == agent_id:
            base = dict(a)
            break
    if not base:
        return {"error": "Agent not found"}

    # Enrich with full YAML data
    yaml_file = ARKAOS_ROOT / base.get("file", "")
    if yaml_file.exists():
        try:
            import yaml
            raw = yaml.safe_load(yaml_file.read_text())
            dna = raw.get("behavioral_dna", {})
            disc = dna.get("disc", {})
            ennea = dna.get("enneagram", {})

            base["disc"]["communication_style"] = disc.get("communication_style", "")
            base["disc"]["under_pressure"] = disc.get("under_pressure", "")
            base["disc"]["motivator"] = disc.get("motivator", "")
            base["enneagram"]["core_motivation"] = ennea.get("core_motivation", "")
            base["enneagram"]["core_fear"] = ennea.get("core_fear", "")
            base["enneagram"]["subtype"] = ennea.get("subtype", "")

            base["mental_models"] = raw.get("mental_models", {})
            base["communication"] = raw.get("communication", {})

            auth = raw.get("authority", {})
            base["authority"]["delegates_to"] = auth.get("delegates_to", [])
            base["authority"]["escalates_to"] = auth.get("escalates_to", "")

            expertise = raw.get("expertise", {})
            base["expertise_depth"] = expertise.get("depth", "")
            base["expertise_years"] = expertise.get("years_equivalent", 0)
            base["frameworks"] = raw.get("frameworks", [])
            base["expertise_domains"] = raw.get("expertise_domains", [])
            # PR76 v2.94.0 — linked_personas: persona IDs the agent
            # draws from. Empty when not yet edited.
            base["linked_personas"] = raw.get("linked_personas", [])
            base["_yaml_path"] = str(yaml_file)
        except Exception:
            pass

    return base


@app.put("/api/agents/{agent_id}")
def agent_update(agent_id: str, body: dict):
    """PR76 v2.94.0 — edit an agent. Updates the YAML file with
    editable fields from body. Preserves untouched fields.
    """
    if not isinstance(body, dict):
        return {"error": "body must be an object"}
    agents = _load_agents()
    base = None
    for a in agents:
        if a.get("id") == agent_id:
            base = dict(a)
            break
    if not base:
        return {"error": "Agent not found"}
    yaml_file = ARKAOS_ROOT / base.get("file", "")
    if not yaml_file.exists():
        return {"error": "Agent YAML file missing on disk"}
    try:
        import yaml as _yaml
    except ImportError:
        return {"error": "PyYAML unavailable"}
    try:
        raw = _yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        return {"error": f"YAML parse failed: {exc}"}
    if not isinstance(raw, dict):
        return {"error": "agent YAML is not a mapping"}

    for top_key in ("name", "role"):
        if top_key in body and isinstance(body[top_key], str):
            raw[top_key] = body[top_key]
    if "tier" in body:
        try:
            raw["tier"] = int(body["tier"])
        except (TypeError, ValueError):
            pass
    if "mental_models" in body and isinstance(body["mental_models"], dict):
        mm = raw.setdefault("mental_models", {}) or {}
        for sub in ("primary", "secondary"):
            if sub in body["mental_models"]:
                mm[sub] = _agent_str_list(body["mental_models"][sub])
        raw["mental_models"] = mm
    if "frameworks" in body:
        raw["frameworks"] = _agent_str_list(body["frameworks"])
    if "expertise_domains" in body:
        raw["expertise_domains"] = _agent_str_list(body["expertise_domains"])
    if "expertise" in body and isinstance(body["expertise"], dict):
        expertise = raw.setdefault("expertise", {}) or {}
        if "depth" in body["expertise"]:
            expertise["depth"] = str(body["expertise"]["depth"])
        if "years_equivalent" in body["expertise"]:
            try:
                expertise["years_equivalent"] = int(body["expertise"]["years_equivalent"])
            except (TypeError, ValueError):
                pass
        raw["expertise"] = expertise
    if "communication" in body and isinstance(body["communication"], dict):
        comm = raw.setdefault("communication", {}) or {}
        for key in ("tone", "vocabulary_level", "preferred_format", "language"):
            if key in body["communication"]:
                comm[key] = str(body["communication"][key])
        if "avoid" in body["communication"]:
            comm["avoid"] = _agent_str_list(body["communication"]["avoid"])
        raw["communication"] = comm
    if "linked_personas" in body:
        raw["linked_personas"] = _agent_str_list(body["linked_personas"])
    # PR86d v3.18.0 — Markdown bio (long-form free text).
    if "bio_md" in body and isinstance(body["bio_md"], str):
        raw["bio_md"] = body["bio_md"]

    try:
        tmp = yaml_file.with_suffix(yaml_file.suffix + ".tmp")
        tmp.write_text(
            _yaml.safe_dump(raw, sort_keys=False, allow_unicode=True, default_flow_style=False),
            encoding="utf-8",
        )
        tmp.replace(yaml_file)
    except OSError as exc:
        return {"error": f"write failed: {exc}"}
    return {"id": agent_id, "updated": True, "yaml_path": str(yaml_file)}


def _agent_str_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, (str, int, float))]


@app.get("/api/commands")
def commands(dept: Optional[str] = Query(None), q: Optional[str] = Query(None)):
    data = _load_commands()
    if dept:
        data = [c for c in data if c.get("department") == dept]
    if q:
        q_lower = q.lower()
        data = [c for c in data if q_lower in c.get("command", "").lower() or q_lower in c.get("description", "").lower()]
    return {"commands": data, "total": len(data)}


@app.get("/api/budget")
def budget_all():
    mgr = _get_budget_manager()
    if not mgr:
        return {"tiers": [], "departments": [], "summary": {"total_tokens": 0, "total_ops": 0, "active_departments": 0}}

    # Department breakdown from raw usages
    dept_data: dict[str, dict] = {}
    for u in mgr._usages:
        dept = u.department or "system"
        if dept not in dept_data:
            dept_data[dept] = {"department": dept, "tokens": 0, "operations": 0}
        dept_data[dept]["tokens"] += u.tokens
        dept_data[dept]["operations"] += 1

    departments = sorted(dept_data.values(), key=lambda d: d["tokens"], reverse=True)
    max_tokens = departments[0]["tokens"] if departments else 1

    # Add relative percentage for bar width
    for d in departments:
        d["percent"] = round((d["tokens"] / max_tokens) * 100) if max_tokens > 0 else 0

    total_tokens = sum(d["tokens"] for d in departments)
    total_ops = sum(d["operations"] for d in departments)

    return {
        "summary": {
            "total_tokens": total_tokens,
            "total_ops": total_ops,
            "active_departments": len(departments),
            "estimated_cost_usd": round(total_tokens * 0.000003, 4),  # ~$3 per 1M input tokens
        },
        "departments": departments,
        "tiers": [mgr.get_summary(tier=t).model_dump() for t in range(4)],
    }


@app.get("/api/budget/{tier}")
def budget_tier(tier: int):
    mgr = _get_budget_manager()
    if not mgr:
        return {"error": "Budget manager unavailable"}
    return mgr.get_summary(tier=tier).model_dump()


@app.get("/api/tasks")
def tasks(status: Optional[str] = Query(None)):
    mgr = _get_task_manager()
    if not mgr:
        return {"tasks": [], "summary": {"total": 0}}
    from core.tasks.schema import TaskStatus
    task_list = mgr.list_all(TaskStatus(status) if status else None)
    return {
        "tasks": [t.model_dump() for t in task_list],
        "summary": mgr.summary(),
    }


@app.get("/api/tasks/active")
def tasks_active():
    mgr = _get_task_manager()
    if not mgr:
        return {"tasks": []}
    return {"tasks": [t.model_dump() for t in mgr.list_active()]}


# --- Job Queue (SQLite) ---

_job_manager = None

def _get_job_manager():
    global _job_manager
    if _job_manager is None:
        try:
            from core.jobs.manager import JobManager
            _job_manager = JobManager()
        except Exception:
            return None
    return _job_manager


@app.get("/api/jobs")
def jobs_list(status: Optional[str] = Query(None), limit: int = Query(50)):
    mgr = _get_job_manager()
    if not mgr:
        return {"jobs": [], "summary": {}}
    if status:
        jobs = mgr.list_by_status(status, limit)
    else:
        jobs = mgr.list_all(limit)
    return {"jobs": [j.to_dict() for j in jobs], "summary": mgr.summary()}


@app.get("/api/jobs/{job_id}")
def job_detail(job_id: str):
    mgr = _get_job_manager()
    if not mgr:
        return {"error": "Job manager unavailable"}
    job = mgr.get(job_id)
    if not job:
        return {"error": "Job not found"}
    return job.to_dict()


@app.delete("/api/jobs/{job_id}")
def job_cancel(job_id: str):
    mgr = _get_job_manager()
    if not mgr:
        return {"error": "Job manager unavailable"}
    if mgr.cancel(job_id):
        broadcast_from_thread({"type": "job_cancelled", "job_id": job_id})
        return {"cancelled": True}
    return {"error": "Can only cancel queued jobs"}


from fastapi import UploadFile

@app.post("/api/knowledge/upload-file")
async def knowledge_upload_file(file: UploadFile):
    """Upload and ingest a file (PDF, audio, markdown)."""
    import threading

    media_dir = Path.home() / ".arkaos" / "media"
    media_dir.mkdir(parents=True, exist_ok=True)

    # Save uploaded file
    file_path = media_dir / file.filename
    content = await file.read()
    file_path.write_bytes(content)

    source = str(file_path)
    from core.knowledge.ingest import detect_source_type
    source_type = detect_source_type(source)

    store = _get_vector_store()
    if not store:
        from core.knowledge.vector_store import VectorStore
        kb_db = Path.home() / ".arkaos" / "knowledge.db"
        kb_db.parent.mkdir(parents=True, exist_ok=True)
        store = VectorStore(kb_db)

    job_mgr = _get_job_manager()
    job = job_mgr.create(source=source, source_type=source_type, title=file.filename)
    job_id = job.id

    def run_ingest():
        from core.jobs.manager import JobManager as _JM
        from core.knowledge.ingest import IngestEngine
        local_mgr = _JM()
        engine = IngestEngine(store)
        def on_progress(pct, msg):
            status = "embedding" if "embed" in msg.lower() or "index" in msg.lower() else "processing"
            local_mgr.update_progress(job_id, pct, msg, status)
            broadcast_from_thread({"type": "job_progress", "job_id": job_id, "progress": pct, "message": msg, "status": status})
        try:
            local_mgr.start(job_id)
            result = engine.ingest(source, source_type, on_progress=on_progress)
            if result.success:
                local_mgr.complete(job_id, chunks_created=result.chunks_created)
                broadcast_from_thread({"type": "job_complete", "job_id": job_id, "chunks_created": result.chunks_created})
            else:
                local_mgr.fail(job_id, result.error)
                broadcast_from_thread({"type": "job_failed", "job_id": job_id, "error": result.error})
        except Exception as e:
            local_mgr.fail(job_id, str(e))
            broadcast_from_thread({"type": "job_failed", "job_id": job_id, "error": str(e)})

    threading.Thread(target=run_ingest, daemon=True).start()
    return {"job_id": job_id, "source_type": source_type, "filename": file.filename, "status": "queued"}


@app.post("/api/knowledge/ingest")
def knowledge_ingest(body: dict):
    """Ingest content into the knowledge base. Runs in background with SQLite job tracking."""
    import threading

    source = body.get("source", "")
    source_type = body.get("type", "")
    text_content = body.get("text", "")
    text_title = body.get("title", "")

    # Handle direct text paste — save to temp markdown file
    if text_content and len(text_content) > 10:
        media_dir = Path.home() / ".arkaos" / "media"
        media_dir.mkdir(parents=True, exist_ok=True)
        safe_name = "".join(c if c.isalnum() or c in " -_" else "" for c in (text_title or source)[:40]).strip() or "pasted-text"
        text_path = media_dir / f"{safe_name}.md"
        # Add title as heading
        md_content = f"# {text_title}\n\n{text_content}" if text_title else text_content
        text_path.write_text(md_content, encoding="utf-8")
        source = str(text_path)
        source_type = "markdown"

    if not source:
        return {"error": "source is required"}

    store = _get_vector_store()
    if not store:
        from core.knowledge.vector_store import VectorStore
        kb_db = Path.home() / ".arkaos" / "knowledge.db"
        kb_db.parent.mkdir(parents=True, exist_ok=True)
        store = VectorStore(kb_db)

    from core.knowledge.ingest import IngestEngine, detect_source_type
    if not source_type:
        source_type = detect_source_type(source)

    # Create job in SQLite
    job_mgr = _get_job_manager()
    job = job_mgr.create(source=source, source_type=source_type)

    job_id = job.id  # Capture ID for thread

    def run_ingest():
        # Create thread-local JobManager (SQLite objects can't cross threads)
        from core.jobs.manager import JobManager as _JM
        local_mgr = _JM()

        engine = IngestEngine(store)
        def on_progress(pct, msg):
            status = "processing"
            if "phase 2" in msg.lower() or "download" in msg.lower():
                status = "downloading"
            elif "phase 3" in msg.lower() or "extract" in msg.lower():
                status = "processing"
            elif "phase 4" in msg.lower() or "transcrib" in msg.lower():
                status = "transcribing"
            elif "embed" in msg.lower() or "index" in msg.lower():
                status = "embedding"
            local_mgr.update_progress(job_id, pct, msg, status)
            broadcast_from_thread({
                "type": "job_progress",
                "job_id": job_id,
                "progress": pct,
                "message": msg,
                "status": status,
            })
        try:
            local_mgr.start(job_id)
            broadcast_from_thread({"type": "job_progress", "job_id": job_id, "progress": 0, "message": "Starting...", "status": "processing"})
            result = engine.ingest(source, source_type, on_progress=on_progress)
            if result.success:
                local_mgr.complete(job_id, chunks_created=result.chunks_created)
                broadcast_from_thread({"type": "job_complete", "job_id": job_id, "chunks_created": result.chunks_created})
            else:
                local_mgr.fail(job_id, result.error)
                broadcast_from_thread({"type": "job_failed", "job_id": job_id, "error": result.error})
        except Exception as e:
            local_mgr.fail(job_id, str(e))
            broadcast_from_thread({"type": "job_failed", "job_id": job_id, "error": str(e)})

    thread = threading.Thread(target=run_ingest, daemon=True)
    thread.start()

    return {"job_id": job.id, "source_type": source_type, "status": "queued"}


@app.post("/api/knowledge/ingest-bulk")
def knowledge_ingest_bulk(body: dict):
    """PR56 v2.73.0 — bulk URL ingest.

    Accepts ``{"sources": ["url1", "url2", ...]}`` and queues one
    background job per source. Returns ``{"jobs": [{...}, ...]}`` so the
    dashboard can subscribe to each via the existing /ws/tasks stream.
    Empty / whitespace-only lines are filtered. Duplicates collapse on
    the JobManager side (one job per unique source).
    """
    raw_sources = body.get("sources") or []
    if not isinstance(raw_sources, list):
        return {"error": "sources must be a list"}
    cleaned = []
    seen: set[str] = set()
    for raw in raw_sources:
        if not isinstance(raw, str):
            continue
        s = raw.strip()
        if not s or s in seen:
            continue
        seen.add(s)
        cleaned.append(s)
    if not cleaned:
        return {"error": "no valid sources provided"}
    if len(cleaned) > 50:
        return {"error": "bulk ingest is capped at 50 sources per request"}
    jobs = []
    for source in cleaned:
        result = knowledge_ingest({"source": source})
        if "error" in result:
            jobs.append({"source": source, "error": result["error"]})
        else:
            jobs.append({
                "source": source,
                "job_id": result["job_id"],
                "source_type": result.get("source_type"),
                "status": result.get("status", "queued"),
            })
    return {"jobs": jobs, "count": len(jobs)}


@app.get("/api/tasks/{task_id}")
def task_detail(task_id: str):
    """Get a single task by ID. Also checks jobs."""
    # Check jobs first (new system)
    job_mgr = _get_job_manager()
    if job_mgr:
        job = job_mgr.get(task_id)
        if job:
            return job.to_dict()
    # Fallback to old task manager
    mgr = _get_task_manager()
    if not mgr:
        return {"error": "Task manager unavailable"}
    task = mgr.get(task_id)
    if not task:
        return {"error": "Task not found"}
    return task.model_dump()


@app.get("/api/knowledge/stats")
def knowledge_stats():
    """PR73 v2.91.0 — vec_unavailable_reason surfaced so the dashboard
    can show *why* vector search is offline instead of just a generic
    "Unavailable" badge."""
    store = _get_vector_store()
    if not store:
        return {
            "total_chunks": 0,
            "total_files": 0,
            "vss_available": False,
            "vec_available": False,
            "vec_unavailable_reason": "Vector store could not be opened.",
            "indexed": False,
        }
    stats = store.get_stats()
    stats["indexed"] = stats["total_chunks"] > 0
    if not stats.get("vec_available", False):
        try:
            from core.knowledge.vector_store import vec_unavailable_reason
            stats["vec_unavailable_reason"] = vec_unavailable_reason()
        except Exception:
            stats["vec_unavailable_reason"] = "unknown"
    else:
        stats["vec_unavailable_reason"] = ""
    return stats


@app.get("/api/knowledge/search")
def knowledge_search(q: str = Query(...), top_k: int = Query(5)):
    store = _get_vector_store()
    if not store:
        return {"results": [], "query": q}
    results = store.search(q, top_k=min(top_k, 20))
    return {"results": results, "query": q, "total": len(results)}


@app.get("/api/knowledge/sources")
def knowledge_list_sources():
    """PR88c v3.25.0 — list every distinct source + chunk count.

    Returns ``{sources: [{source, chunks}], total: N}``. Sorted
    descending by chunk count.
    """
    store = _get_vector_store()
    if not store:
        return {"sources": [], "total": 0, "error": "vector store unavailable"}
    try:
        rows = store.list_sources()
    except Exception as exc:  # noqa: BLE001
        return {"sources": [], "total": 0, "error": str(exc)}
    return {"sources": rows, "total": len(rows)}


@app.delete("/api/knowledge/sources")
def knowledge_delete_source(source: str = Query(...)):
    """PR71 v2.88.0 — remove all chunks from a given source.

    Operators sometimes ingest a noisy / wrong source and want to nuke
    every chunk that came from it without rebuilding the whole vector
    DB. The vector store already exposes `remove_file(source)` —
    this endpoint just exposes it on the wire.

    Returns ``{deleted: N, source: "..."}``. Refuses empty source
    paths so a runaway client doesn't accidentally request "delete
    everything that has no source".
    """
    clean = (source or "").strip()
    if not clean:
        return {"error": "source query param is required"}
    store = _get_vector_store()
    if not store:
        return {"error": "vector store unavailable", "deleted": 0}
    try:
        deleted = store.remove_file(clean)
    except Exception as exc:  # noqa: BLE001 — surface as 200+error
        return {"error": f"delete failed: {exc}", "deleted": 0}
    return {"deleted": int(deleted), "source": clean}


@app.get("/api/health")
def health():
    """PR70 v2.87.0 — per-check severity + response timestamp.

    Each check now carries a `severity` field:
      - "fail" — must-pass; missing breaks ArkaOS
      - "warn" — recommended; missing means a degraded but workable env

    Response also carries `ts` so the UI can show "last checked".
    Frontend polls every 30s and surfaces copy-fix buttons.
    """
    from datetime import datetime, timezone

    checks: list[dict] = []
    arkaos_home = Path.home() / ".arkaos"

    def check(name: str, condition: bool, fix: str = "", severity: str = "fail"):
        checks.append({
            "name": name,
            "passed": condition,
            "fix": fix,
            "severity": severity,
        })

    check("install_dir", arkaos_home.exists(), "npx arkaos install")
    check("manifest", (arkaos_home / "install-manifest.json").exists(),
          "npx arkaos install")
    check("constitution", (ARKAOS_ROOT / "config" / "constitution.yaml").exists())
    check("agents_registry",
          (ARKAOS_ROOT / "knowledge" / "agents-registry-v2.json").exists())
    check("commands_registry",
          (ARKAOS_ROOT / "knowledge" / "commands-registry-v2.json").exists())
    check("hooks_dir", (arkaos_home / "config" / "hooks").exists(),
          "npx arkaos install")

    try:
        subprocess.run(["python3", "--version"], capture_output=True, timeout=2)
        check("python", True)
    except Exception:
        check("python", False, "Install Python 3.11+")

    # Telemetry + knowledge — warn-only; missing them is a degraded
    # but workable state (new installs, never-indexed-anything).
    check("knowledge_db", (arkaos_home / "knowledge.db").exists(),
          "Open the Knowledge tab and ingest a source",
          severity="warn")
    check("profile",
          (arkaos_home / "profile.json").exists(),
          "Open Settings → Profile to introduce yourself",
          severity="warn")

    passed = sum(1 for c in checks if c["passed"])
    failed_blocking = sum(
        1 for c in checks
        if not c["passed"] and c["severity"] == "fail"
    )
    warning_count = sum(
        1 for c in checks
        if not c["passed"] and c["severity"] == "warn"
    )
    return {
        "checks": checks,
        "passed": passed,
        "total": len(checks),
        "failed_blocking": failed_blocking,
        "warning_count": warning_count,
        "healthy": failed_blocking == 0,
        "ts": datetime.now(timezone.utc).isoformat(),
    }


# --- Personas ---

def _get_persona_manager():
    try:
        from core.personas.manager import PersonaManager
        db_path = Path.home() / ".arkaos" / "personas.json"
        return PersonaManager(storage_path=db_path)
    except Exception:
        return None


@app.get("/api/personas")
def personas_list():
    """PR73 v2.91.0 — merges JSON-store personas with the Obsidian
    vault's ``<vaultPath>/Personas/*.md`` files. Obsidian is the
    source of truth: when the same persona exists in both places
    (matched by name/slug), the vault entry wins.
    """
    by_id: dict[str, dict] = {}

    # JSON store first (in-memory copy is fast, vault read may be slow)
    mgr = _get_persona_manager()
    if mgr:
        for p in mgr.list_all():
            payload = p.model_dump()
            by_id[payload["id"]] = payload

    # Obsidian vault — overwrites duplicates so the vault wins.
    try:
        from core.personas.obsidian_store import ObsidianPersonaStore
        ob_store = ObsidianPersonaStore()
        if ob_store.available:
            for p in ob_store.list_all():
                payload = p.model_dump()
                payload["_source_store"] = "obsidian"
                by_id[payload["id"]] = payload
    except Exception:
        pass

    personas = list(by_id.values())
    personas.sort(key=lambda p: p.get("name", "").lower())
    return {
        "personas": personas,
        "total": len(personas),
        "obsidian_available": _obsidian_store_available(),
    }


def _obsidian_store_available() -> bool:
    try:
        from core.personas.obsidian_store import ObsidianPersonaStore
        return ObsidianPersonaStore().available
    except Exception:
        return False


@app.get("/api/personas/usage")
def personas_usage():
    """PR77 v2.95.0 — reverse lookup: how many agents link to each
    persona. Reads every agent's YAML once, builds a
    ``{persona_id: [agent_id, ...]}`` map.

    The detail drawer + list cards use this to show "Linked to N
    agents" so the operator sees which personas are actually wired.
    """
    import yaml as _yaml
    agents = _load_agents()
    usage: dict[str, list[str]] = {}
    for agent in agents:
        yaml_file = ARKAOS_ROOT / agent.get("file", "")
        if not yaml_file.exists():
            continue
        try:
            raw = _yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        linked = raw.get("linked_personas") if isinstance(raw, dict) else None
        if not isinstance(linked, list):
            continue
        for persona_id in linked:
            if not isinstance(persona_id, str):
                continue
            usage.setdefault(persona_id, []).append(agent.get("id", ""))
    return {
        "by_persona": {
            pid: {"agent_count": len(aids), "agent_ids": aids}
            for pid, aids in usage.items()
        },
    }


@app.get("/api/personas/{persona_id}")
def persona_detail(persona_id: str):
    """PR74 v2.92.0 — detail endpoint now checks the Obsidian vault
    in addition to the JSON store, so vault-only personas (Alex
    Hormozi, Naval, etc.) resolve correctly.
    """
    # Try Obsidian first — it's the source of truth on conflicts.
    try:
        from core.personas.obsidian_store import ObsidianPersonaStore
        ob_store = ObsidianPersonaStore()
        if ob_store.available:
            for p in ob_store.list_all():
                if p.id == persona_id:
                    payload = p.model_dump()
                    payload["_source_store"] = "obsidian"
                    payload["_obsidian_path"] = str(
                        ob_store.personas_dir / f"{p.name}.md"
                    )
                    return payload
    except Exception:
        pass

    mgr = _get_persona_manager()
    if not mgr:
        return {"error": "Persona manager unavailable"}
    p = mgr.get(persona_id)
    if not p:
        return {"error": "Persona not found"}
    payload = p.model_dump()
    payload["_source_store"] = "json"
    return payload


@app.put("/api/personas/{persona_id}")
def persona_update(persona_id: str, body: dict):
    """PR74 v2.92.0 — update an existing persona. Writes to both the
    JSON store (when the persona exists there) and the Obsidian vault
    (when configured). Best-effort: a vault write failure does not
    abort the JSON-side success and vice versa.

    The persona name can change; in that case the old Obsidian file
    is left in place (operator can delete it manually) and a new one
    is created with the updated name.
    """
    from core.personas.schema import (
        Persona, PersonaDISC, PersonaEnneagram, PersonaBigFive, PersonaCommunication,
    )

    # Start from existing data so partial-update bodies don't wipe fields.
    existing = persona_detail(persona_id)
    if "error" in existing:
        return existing
    merged = {**existing, **{k: v for k, v in body.items() if v is not None}}

    name = merged.get("name", "Unknown")
    new_id = (
        merged.get("id")
        or name.lower().replace(" ", "-").replace(".", "")
    )

    updated = Persona(
        id=new_id,
        name=name,
        title=merged.get("title", ""),
        tagline=merged.get("tagline", ""),
        source=merged.get("source", name),
        disc=PersonaDISC(**(merged.get("disc", {}) or {})),
        enneagram=PersonaEnneagram(**(merged.get("enneagram", {}) or {})),
        big_five=PersonaBigFive(**(merged.get("big_five", {}) or {})),
        mbti=merged.get("mbti", "INTJ"),
        mental_models=merged.get("mental_models", []) or [],
        expertise_domains=merged.get("expertise_domains", []) or [],
        frameworks=merged.get("frameworks", []) or [],
        key_quotes=merged.get("key_quotes", []) or [],
        communication=PersonaCommunication(
            **(merged.get("communication", {}) or {}),
        ),
        bio_md=merged.get("bio_md", "") or "",
        created_at=merged.get("created_at", ""),
    )

    # JSON store — only if the persona originally lived there.
    json_written = False
    if existing.get("_source_store") != "obsidian":
        mgr = _get_persona_manager()
        if mgr:
            try:
                mgr.update(persona_id, updated.model_dump())
                json_written = True
            except Exception:
                # Fall through to create if update isn't supported.
                try:
                    mgr.create(updated)
                    json_written = True
                except Exception:
                    json_written = False

    # Obsidian — always overwrite when vault is configured.
    obsidian_path: str | None = None
    try:
        from core.personas.obsidian_store import ObsidianPersonaStore
        ob_store = ObsidianPersonaStore()
        if ob_store.available or ob_store._vault_path is not None:
            written = ob_store.write(updated)
            if written is not None:
                obsidian_path = str(written)
    except Exception:
        pass

    return {
        "id": updated.id,
        "updated": True,
        "json_written": json_written,
        "obsidian_path": obsidian_path,
    }


@app.post("/api/personas")
def persona_create(body: dict):
    mgr = _get_persona_manager()
    if not mgr:
        return {"error": "Persona manager unavailable"}

    from core.personas.schema import (
        Persona, PersonaDISC, PersonaEnneagram, PersonaBigFive, PersonaCommunication,
    )

    # Generate ID from name
    name = body.get("name", "Unknown")
    persona_id = name.lower().replace(" ", "-").replace(".", "")

    persona = Persona(
        id=persona_id,
        name=name,
        title=body.get("title", ""),
        tagline=body.get("tagline", ""),
        source=body.get("source", name),
        disc=PersonaDISC(**(body.get("disc", {}))),
        enneagram=PersonaEnneagram(**(body.get("enneagram", {}))),
        big_five=PersonaBigFive(**(body.get("big_five", {}))),
        mbti=body.get("mbti", "INTJ"),
        mental_models=body.get("mental_models", []),
        expertise_domains=body.get("expertise_domains", []),
        frameworks=body.get("frameworks", []),
        key_quotes=body.get("key_quotes", []),
        communication=PersonaCommunication(**(body.get("communication", {}))),
    )

    mgr.create(persona)

    # PR73 v2.91.0 — also write to the Obsidian vault so the persona
    # survives outside the JSON store and is browsable in Obsidian.
    # Best-effort: vault unavailable / write failure does not abort
    # the JSON-side success.
    obsidian_path: str | None = None
    try:
        from core.personas.obsidian_store import ObsidianPersonaStore
        ob_store = ObsidianPersonaStore()
        if ob_store.available or ob_store._vault_path is not None:
            written = ob_store.write(persona)
            if written is not None:
                obsidian_path = str(written)
    except Exception:
        pass

    return {"id": persona.id, "created": True, "obsidian_path": obsidian_path}


@app.post("/api/personas/{persona_id}/clone")
def persona_clone(persona_id: str, body: dict = {}):
    mgr = _get_persona_manager()
    if not mgr:
        return {"error": "Persona manager unavailable"}

    department = body.get("department", "strategy")
    tier = body.get("tier", 2)
    agents_dir = ARKAOS_ROOT / "departments" / department / "agents"

    agent_id = mgr.clone_to_agent(persona_id, department=department, tier=tier, agents_dir=str(agents_dir))
    if not agent_id:
        return {"error": "Persona not found"}

    return {"agent_id": agent_id, "department": department, "file": f"departments/{department}/agents/{agent_id}.yaml"}


@app.post("/api/agents/{agent_id}/move")
def agent_move(agent_id: str, body: dict):
    """PR84b v3.8.0 — move an agent's YAML to another department.

    Body: {"department": "<new-dept>"}
    Mutates the YAML's `department:` field AND moves the file across
    `departments/<src>/agents/` → `departments/<dst>/agents/`.

    Refuses Tier 0 (C-Suite) like the delete endpoint. Refuses unknown
    target department. Refuses overwriting an existing file at the
    destination.
    """
    if not isinstance(body, dict):
        return {"error": "body must be an object"}
    target_dept = (body.get("department") or "").strip().lower()
    if not target_dept:
        return {"error": "department is required"}
    yaml_file = _resolve_agent_yaml(agent_id)
    if yaml_file is None:
        return {"error": "Agent not found"}
    if _agent_tier_from_yaml(yaml_file) == 0:
        return {"error": "Cannot move Tier 0 (C-Suite) agents from the dashboard"}
    dest_dir = ARKAOS_ROOT / "departments" / target_dept / "agents"
    if not dest_dir.exists():
        return {"error": f"department '{target_dept}' not found"}
    dest_file = dest_dir / yaml_file.name
    if dest_file.exists():
        return {"error": f"target file already exists: {dest_file.name}"}
    try:
        if yaml_file.resolve() == dest_file.resolve():
            return {"moved": False, "id": agent_id, "yaml_path": str(yaml_file)}
    except FileNotFoundError:
        pass
    try:
        import yaml as _yaml
        raw = _yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or {}
        if isinstance(raw, dict):
            raw["department"] = target_dept
            tmp = yaml_file.with_suffix(yaml_file.suffix + ".tmp")
            tmp.write_text(
                _yaml.safe_dump(raw, sort_keys=False, allow_unicode=True, default_flow_style=False),
                encoding="utf-8",
            )
            tmp.replace(yaml_file)
        yaml_file.rename(dest_file)
        from core import trash as _trash
        trash_id = _trash.record_move(
            item_id=agent_id,
            from_path=str(yaml_file),
            to_path=str(dest_file),
        )
    except (OSError, ImportError) as exc:
        return {"error": f"move failed: {exc}"}
    return {
        "moved": True,
        "id": agent_id,
        "yaml_path": str(dest_file),
        "trash_id": trash_id,
    }


@app.delete("/api/agents/{agent_id}")
def agent_delete(agent_id: str):
    """PR83b v3.4.0 — delete an agent's YAML file.

    Refuses to delete Tier 0 (C-Suite) agents — those are governance
    fixtures and need direct YAML removal to make the intent explicit.

    Resolves the YAML location two ways:
      1. From the cached registry (covers seeded agents)
      2. By scanning departments/*/agents/<id>.yaml (covers
         freshly-created agents that aren't in the registry yet)
    """
    yaml_file = _resolve_agent_yaml(agent_id)
    if yaml_file is None:
        return {"error": "Agent not found"}
    tier = _agent_tier_from_yaml(yaml_file)
    if tier == 0:
        return {"error": "Cannot delete Tier 0 (C-Suite) agents from the dashboard"}
    try:
        from core import trash as _trash
        content = yaml_file.read_text(encoding="utf-8")
        trash_id = _trash.record_deletion(
            kind="agent-delete",
            item_id=agent_id,
            original_path=str(yaml_file),
            content=content,
        )
        yaml_file.unlink()
    except OSError as exc:
        return {"error": f"delete failed: {exc}"}
    return {
        "deleted": True,
        "id": agent_id,
        "yaml_path": str(yaml_file),
        "trash_id": trash_id,
    }


def _resolve_agent_yaml(agent_id: str) -> Optional[Path]:
    # 1. Check the cached registry first.
    for a in _load_agents():
        if a.get("id") == agent_id:
            candidate = ARKAOS_ROOT / a.get("file", "")
            if candidate.exists():
                return candidate
    # 2. Filesystem scan — covers freshly-created files.
    dept_root = ARKAOS_ROOT / "departments"
    if dept_root.exists():
        for path in dept_root.glob(f"*/agents/{agent_id}.yaml"):
            return path
    return None


def _agent_tier_from_yaml(yaml_file: Path) -> int:
    try:
        import yaml as _yaml
        raw = _yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or {}
    except Exception:
        return 99
    return int(raw.get("tier") or 99)


@app.delete("/api/personas/{persona_id}")
def persona_delete(persona_id: str):
    mgr = _get_persona_manager()
    if not mgr:
        return {"error": "Persona manager unavailable"}
    # Capture content + path BEFORE delete for trash record (best-effort)
    trash_id = None
    try:
        from core import trash as _trash
        target = mgr.get(persona_id) if hasattr(mgr, "get") else None
        if target is not None:
            import json as _json
            payload = _json.dumps(
                target if isinstance(target, dict) else target.model_dump(),
                indent=2,
            )
            store_path = getattr(mgr, "_store_path", None) or "personas.json"
            trash_id = _trash.record_deletion(
                kind="persona-delete",
                item_id=persona_id,
                original_path=str(store_path) + f"#{persona_id}",
                content=payload,
            )
    except Exception:
        pass
    if mgr.delete(persona_id):
        return {"deleted": True, "trash_id": trash_id}
    return {"error": "Persona not found"}


# --- Agent → Obsidian export (PR86c v3.17.0) ---

@app.post("/api/agents/{agent_id}/export")
def agent_export_to_vault(agent_id: str):
    """Write the agent profile as Markdown under <vault>/Agents/<id>.md."""
    detail = agent_detail(agent_id)
    if "error" in detail:
        return detail
    try:
        from core.agents.obsidian_export import (
            AgentExportError,
            export_agent_to_vault,
        )
    except Exception as exc:  # noqa: BLE001
        return {"error": f"export module unavailable: {exc}"}
    try:
        res = export_agent_to_vault(detail)
    except AgentExportError as exc:
        return {"error": str(exc)}
    return {"exported": True, "path": str(res.path), "vault_path": str(res.vault_path)}


# --- Agent gap suggestions (PR91a v3.35.0) ---

_KNOWN_DEPARTMENTS = (
    "dev", "marketing", "brand", "finance", "strategy", "ecom", "kb",
    "ops", "pm", "saas", "landing", "content", "community", "sales",
    "leadership", "org",
)


@app.get("/api/agents/suggestions")
def agents_suggestions(limit: int = 6):
    """PR91a v3.35.0 — recommend agents the operator should consider creating.

    Heuristics:
      1. Departments with zero agents at all (severity: high).
      2. Departments missing a Tier 2 specialist (severity: medium).

    Each suggestion includes ``reason`` and ``recommended_tier``. Used
    by the home page "What's missing?" card.
    """
    agents = _load_agents()
    by_dept: dict[str, dict] = {}
    for a in agents:
        dept = a.get("department") or ""
        if not dept:
            continue
        row = by_dept.setdefault(dept, {"count": 0, "tiers": set()})
        row["count"] += 1
        try:
            row["tiers"].add(int(a.get("tier") or 99))
        except (TypeError, ValueError):
            pass

    suggestions: list[dict] = []
    for dept in _KNOWN_DEPARTMENTS:
        info = by_dept.get(dept)
        if info is None or info["count"] == 0:
            suggestions.append({
                "department": dept,
                "reason": "no agents — department is empty",
                "recommended_tier": 1,
                "severity": "high",
            })
            continue
        if 2 not in info["tiers"]:
            suggestions.append({
                "department": dept,
                "reason": "no Tier 2 specialist",
                "recommended_tier": 2,
                "severity": "medium",
            })
    return {
        "suggestions": suggestions[: max(0, int(limit))],
        "total_gaps": len(suggestions),
    }


# --- Departments (PR89a v3.27.0) ---

@app.get("/api/departments")
def departments_list():
    """List every department with agent count + 30d cost summary."""
    agents = _load_agents()
    by_dept: dict[str, dict] = {}
    for a in agents:
        dept = a.get("department") or ""
        if not dept:
            continue
        row = by_dept.setdefault(dept, {
            "department": dept,
            "agent_count": 0,
            "tier_counts": {"0": 0, "1": 0, "2": 0, "3": 0},
        })
        row["agent_count"] += 1
        tier_key = str(a.get("tier") or "")
        if tier_key in row["tier_counts"]:
            row["tier_counts"][tier_key] += 1
    cost_map: dict[str, dict] = {}
    try:
        from core.runtime.llm_cost_telemetry import summarise
        s = summarise(period="month")
        for category, row in (s.by_category or {}).items():
            if not isinstance(category, str) or not category.startswith("subagent:"):
                continue
            parts = category.split(":", 2)
            dept = parts[1] if len(parts) >= 2 else "unknown"
            bucket = cost_map.setdefault(dept, {
                "calls_30d": 0,
                "cost_usd_30d": 0.0,
                "any_cost_known": False,
            })
            bucket["calls_30d"] += int(row.get("call_count", 0))
            cost = row.get("total_cost_usd")
            if isinstance(cost, (int, float)):
                bucket["cost_usd_30d"] += float(cost)
                bucket["any_cost_known"] = True
    except Exception:  # noqa: BLE001
        pass
    out: list[dict] = []
    for dept in sorted(by_dept.keys()):
        row = by_dept[dept]
        cost = cost_map.get(dept, {})
        row["calls_30d"] = cost.get("calls_30d", 0)
        row["cost_usd_30d"] = (
            round(cost.get("cost_usd_30d", 0.0), 6)
            if cost.get("any_cost_known") else None
        )
        out.append(row)
    return {"departments": out, "total": len(out)}


@app.get("/api/departments/{dept_id}")
def department_detail(dept_id: str):
    """Full department detail: agents, workflows, 30d cost."""
    dept_id = dept_id.strip().lower()
    agents = [a for a in _load_agents() if a.get("department") == dept_id]
    if not agents:
        return {"error": "Department not found or has no agents"}
    workflows: list[dict] = []
    try:
        import yaml as _yaml
        wf_dir = ARKAOS_ROOT / "departments" / dept_id / "workflows"
        if wf_dir.exists():
            for path in sorted(wf_dir.glob("*.yaml")):
                try:
                    raw = _yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                except Exception:  # noqa: BLE001
                    raw = {}
                if not isinstance(raw, dict):
                    continue
                workflows.append({
                    "id": str(raw.get("id") or path.stem),
                    "name": str(raw.get("name") or path.stem),
                    "tier": str(raw.get("tier") or ""),
                    "command": str(raw.get("command") or ""),
                    "phases_count": len(raw.get("phases") or []),
                })
    except ImportError:
        pass
    calls_30d = 0
    cost_usd_30d: Optional[float] = None
    try:
        from core.runtime.llm_cost_telemetry import summarise
        s = summarise(period="month")
        total_cost = 0.0
        any_known = False
        for category, row in (s.by_category or {}).items():
            if not isinstance(category, str) or not category.startswith("subagent:"):
                continue
            parts = category.split(":", 2)
            if len(parts) >= 2 and parts[1] == dept_id:
                calls_30d += int(row.get("call_count", 0))
                cost = row.get("total_cost_usd")
                if isinstance(cost, (int, float)):
                    total_cost += float(cost)
                    any_known = True
        cost_usd_30d = round(total_cost, 6) if any_known else None
    except Exception:  # noqa: BLE001
        pass
    return {
        "department": dept_id,
        "agents": [
            {
                "id": a.get("id"),
                "name": a.get("name"),
                "role": a.get("role"),
                "tier": a.get("tier"),
                "mbti": a.get("mbti"),
                "disc": a.get("disc"),
            }
            for a in agents
        ],
        "workflows": workflows,
        "calls_30d": calls_30d,
        "cost_usd_30d": cost_usd_30d,
    }


# --- Workflows (PR88b v3.24.0) ---

@app.get("/api/workflows/{workflow_id}/runs")
def workflow_runs(workflow_id: str, limit: int = 20):
    """PR89b v3.28.0 — list recent runs of a workflow.

    Parses the PR47 cost telemetry JSONL for rows tagged
    ``workflow:<workflow_id>`` and groups them by ``session_id``.
    Returns ``{runs: [{session_id, started_at, ended_at, duration_s,
    calls, cost_usd, tokens_in, tokens_out}]}`` sorted desc by start.

    Workflows must set ``ARKA_CALL_CATEGORY=workflow:<id>`` before
    each call for this to populate. Returns an empty list when no
    matching entries exist (the common case until orchestrators opt in).
    """
    target_category = f"workflow:{workflow_id}"
    try:
        from core.runtime.llm_cost_telemetry import _load_slice
    except Exception:
        return {"runs": []}
    entries, _ = _load_slice(None, None)
    sessions: dict[str, dict] = {}
    for entry in entries:
        if entry.get("category") != target_category:
            continue
        sid = str(entry.get("session_id") or "")
        if not sid:
            continue
        ts = entry.get("ts") or ""
        bucket = sessions.setdefault(sid, {
            "session_id": sid,
            "started_at": ts,
            "ended_at": ts,
            "calls": 0,
            "cost_usd": 0.0,
            "any_cost_known": False,
            "tokens_in": 0,
            "tokens_out": 0,
        })
        bucket["calls"] += 1
        if ts and ts < bucket["started_at"]:
            bucket["started_at"] = ts
        if ts and ts > bucket["ended_at"]:
            bucket["ended_at"] = ts
        bucket["tokens_in"] += int(entry.get("tokens_in") or 0)
        bucket["tokens_out"] += int(entry.get("tokens_out") or 0)
        cost = entry.get("estimated_cost_usd")
        if isinstance(cost, (int, float)):
            bucket["cost_usd"] += float(cost)
            bucket["any_cost_known"] = True

    runs = list(sessions.values())
    for r in runs:
        r["cost_usd"] = round(r["cost_usd"], 6) if r.pop("any_cost_known") else None
        r["duration_s"] = _iso_duration_s(r["started_at"], r["ended_at"])
    runs.sort(key=lambda r: str(r.get("started_at") or ""), reverse=True)
    return {"runs": runs[: max(0, int(limit))]}


def _iso_duration_s(start_iso: str, end_iso: str) -> Optional[int]:
    if not start_iso or not end_iso:
        return None
    try:
        from datetime import datetime
        start = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
        end = datetime.fromisoformat(end_iso.replace("Z", "+00:00"))
        return max(0, int((end - start).total_seconds()))
    except (ValueError, TypeError):
        return None


# --- Terminal command runner (PR95a v3.51.0) ---

# Allowlist of commands the dashboard terminal can run. Each entry is
# {id, label, cmd, description}. Server-side enforcement: any request
# whose `command_id` isn't in this list is rejected. No shell expansion,
# no globbing, no pipes — subprocess.run with explicit argv only.
TERMINAL_ALLOWLIST: list[dict] = [
    {
        "id": "arka-status",
        "label": "ArkaOS status",
        "cmd": ["arkaos", "status"],
        "description": "System status (version, departments, agents, projects).",
    },
    {
        "id": "git-status",
        "label": "git status",
        "cmd": ["git", "status", "--short"],
        "description": "Working tree status in short form.",
    },
    {
        "id": "git-log",
        "label": "git log (10)",
        "cmd": ["git", "log", "-10", "--oneline"],
        "description": "Most recent 10 commits.",
    },
    {
        "id": "npm-version",
        "label": "npm view arkaos version",
        "cmd": ["npm", "view", "arkaos", "version"],
        "description": "Latest published ArkaOS version on npm.",
    },
    {
        "id": "pytest-collect",
        "label": "pytest --collect-only",
        "cmd": ["python3", "-m", "pytest", "--collect-only", "-q", "tests/python/"],
        "description": "List every Python test without running.",
    },
    {
        "id": "ls",
        "label": "ls",
        "cmd": ["ls", "-la"],
        "description": "List files in the project root.",
    },
]

_TERMINAL_TIMEOUT_S = 15
_TERMINAL_MAX_OUTPUT = 20_000  # chars — both stdout and stderr capped


@app.get("/api/terminal/commands")
def terminal_commands():
    """List allowlisted commands the dashboard terminal may run."""
    return {
        "commands": [
            {"id": c["id"], "label": c["label"], "description": c["description"]}
            for c in TERMINAL_ALLOWLIST
        ],
        "total": len(TERMINAL_ALLOWLIST),
    }


@app.post("/api/terminal/exec")
def terminal_exec(body: dict):
    """PR95a v3.51.0 — run an allowlisted command and return the output.

    Body: ``{"command_id": "<id>"}``. Unknown ids are rejected.
    Returns ``{stdout, stderr, exit_code, duration_ms, command}``.
    Output is capped at ``_TERMINAL_MAX_OUTPUT`` chars per stream.
    """
    if not isinstance(body, dict):
        return {"error": "body must be an object"}
    cid = (body.get("command_id") or "").strip()
    if not cid:
        return {"error": "command_id is required"}
    entry = next((c for c in TERMINAL_ALLOWLIST if c["id"] == cid), None)
    if entry is None:
        return {"error": f"command '{cid}' is not on the allowlist"}
    import time
    started = time.monotonic()
    try:
        result = subprocess.run(
            entry["cmd"],
            cwd=str(ARKAOS_ROOT),
            capture_output=True,
            text=True,
            timeout=_TERMINAL_TIMEOUT_S,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "stdout": "",
            "stderr": f"command timed out after {_TERMINAL_TIMEOUT_S}s",
            "exit_code": -1,
            "duration_ms": int(_TERMINAL_TIMEOUT_S * 1000),
            "command": " ".join(entry["cmd"]),
        }
    except OSError as exc:
        return {
            "stdout": "",
            "stderr": f"command failed to launch: {exc}",
            "exit_code": -1,
            "duration_ms": int((time.monotonic() - started) * 1000),
            "command": " ".join(entry["cmd"]),
        }
    duration_ms = int((time.monotonic() - started) * 1000)
    return {
        "stdout": (result.stdout or "")[:_TERMINAL_MAX_OUTPUT],
        "stderr": (result.stderr or "")[:_TERMINAL_MAX_OUTPUT],
        "exit_code": result.returncode,
        "duration_ms": duration_ms,
        "command": " ".join(entry["cmd"]),
    }


@app.put("/api/workflows/{workflow_id}/yaml")
def workflow_update_yaml(workflow_id: str, body: dict):
    """PR94d v3.50.0 — overwrite a workflow's YAML file in place.

    Body: ``{"content": "<full YAML body>"}``. Validates that the
    content parses to a dict with a non-empty ``id`` key. Refuses to
    move the file (operator can't rename via this endpoint — that
    would invalidate cached references).
    """
    if not isinstance(body, dict):
        return {"error": "body must be an object"}
    content = str(body.get("content") or "")
    if not content.strip():
        return {"error": "content is required"}
    target = _resolve_workflow_yaml(workflow_id)
    if target is None:
        return {"error": "workflow not found"}
    try:
        import yaml as _yaml
        parsed = _yaml.safe_load(content)
    except Exception as exc:  # noqa: BLE001
        return {"error": f"YAML parse failed: {exc}"}
    if not isinstance(parsed, dict):
        return {"error": "YAML root must be a mapping"}
    if not parsed.get("id"):
        return {"error": "YAML must include a non-empty 'id' field"}
    try:
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(target)
    except OSError as exc:
        return {"error": f"write failed: {exc}"}
    return {"updated": True, "id": workflow_id, "file": str(target)}


def _resolve_workflow_yaml(workflow_id: str):
    """Return the YAML path for a workflow id, or None when missing."""
    try:
        import yaml as _yaml
    except ImportError:
        return None
    dept_root = ARKAOS_ROOT / "departments"
    if not dept_root.exists():
        return None
    for path in dept_root.glob("*/workflows/*.yaml"):
        try:
            raw = _yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:  # noqa: BLE001
            continue
        if not isinstance(raw, dict):
            continue
        if str(raw.get("id") or path.stem) == workflow_id:
            return path
    return None


@app.get("/api/workflows")
def workflows_list():
    """Scan departments/*/workflows/*.yaml and return metadata + content."""
    out: list[dict] = []
    dept_root = ARKAOS_ROOT / "departments"
    if not dept_root.exists():
        return {"workflows": []}
    try:
        import yaml as _yaml
    except ImportError:
        return {"workflows": [], "error": "PyYAML unavailable"}
    for path in sorted(dept_root.glob("*/workflows/*.yaml")):
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            continue
        try:
            raw = _yaml.safe_load(content) or {}
        except Exception:  # noqa: BLE001
            raw = {}
        if not isinstance(raw, dict):
            continue
        phases = raw.get("phases") if isinstance(raw.get("phases"), list) else []
        rel = path.relative_to(ARKAOS_ROOT).as_posix()
        out.append({
            "id": str(raw.get("id") or path.stem),
            "name": str(raw.get("name") or path.stem),
            "description": str(raw.get("description") or ""),
            "department": str(raw.get("department") or path.parent.parent.name),
            "tier": str(raw.get("tier") or ""),
            "command": str(raw.get("command") or ""),
            "phases_count": len(phases),
            "phases": _summarise_phases(phases),  # PR91c v3.37.0
            "file": rel,
            "content": content,
        })
    return {"workflows": out}


def _summarise_phases(phases: list) -> list[dict]:
    """PR91c v3.37.0 — distil each phase down to what the flow stepper needs.

    PR93a v3.43.0 — also surfaces the explicit ``agent_ids`` so the UI
    can render them as clickable badges.
    """
    out: list[dict] = []
    for p in phases:
        if not isinstance(p, dict):
            continue
        gate = p.get("gate") if isinstance(p.get("gate"), dict) else {}
        agents = p.get("agents") if isinstance(p.get("agents"), list) else []
        agent_ids: list[str] = []
        for a in agents:
            if isinstance(a, dict):
                aid = a.get("agent_id")
                if aid:
                    agent_ids.append(str(aid))
        out.append({
            "id": str(p.get("id") or ""),
            "name": str(p.get("name") or ""),
            "description": str(p.get("description") or ""),
            "gate_type": str(gate.get("type") or ""),
            "agent_count": len(agent_ids),
            "agent_ids": agent_ids,
        })
    return out


# --- Sidebar stats widget (PR87d v3.22.0) ---

@app.get("/api/sidebar-stats")
def sidebar_stats():
    """Compact payload for the sidebar status widget.

    Returns counts the widget actually displays — agents, personas,
    departments, today's spend. Cheaper than /api/overview/command-center
    because it skips project scanning, incidents, and quick actions.
    """
    agents = _load_agents()
    departments = {a.get("department") for a in agents if a.get("department")}
    persona_count = 0
    mgr = _get_persona_manager()
    if mgr:
        try:
            persona_count = len(mgr.list() or [])
        except Exception:
            persona_count = 0
    today_cost_usd: float | None = None
    call_count = 0
    try:
        from core.runtime.llm_cost_telemetry import summarise
        s = summarise(period="today")
        today_cost_usd = s.total_cost_usd
        call_count = s.call_count
    except Exception:
        pass
    return {
        "agents": len(agents),
        "personas": persona_count,
        "departments": len(departments),
        "today_cost_usd": today_cost_usd,
        "today_calls": call_count,
    }


# --- Favorites (PR86a v3.15.0) ---

@app.get("/api/favorites")
def favorites_list():
    from core import favorites as _fav
    return _fav.list_favorites()


@app.post("/api/favorites/{kind}/{item_id}")
def favorites_toggle(kind: str, item_id: str):
    from core import favorites as _fav
    return _fav.toggle(kind, item_id)


# --- Global search (PR85d v3.14.0) ---

@app.get("/api/search")
def global_search(q: str = "", limit: int = 20):
    """Fuzzy substring search across agents, personas, departments, commands.

    Returns a flat list of result objects with a shape the dashboard
    UCommandPalette can render directly:
      {results: [{kind, id, label, sublabel, to}]}
    """
    query = (q or "").strip().lower()
    if not query:
        return {"results": []}
    results: list[dict] = []

    # Agents
    for a in _load_agents():
        haystack = " ".join(filter(None, [
            str(a.get("name") or ""),
            str(a.get("role") or ""),
            str(a.get("department") or ""),
            str(a.get("id") or ""),
        ])).lower()
        if query in haystack:
            results.append({
                "kind": "agent",
                "id": a.get("id"),
                "label": a.get("name") or a.get("id"),
                "sublabel": f"{a.get('role') or '—'} · {a.get('department') or '—'}",
                "to": f"/agents/{a.get('id')}",
            })

    # Personas
    mgr = _get_persona_manager()
    if mgr:
        try:
            for p in (mgr.list() or []):
                haystack = " ".join(filter(None, [
                    str(p.get("name") or ""),
                    str(p.get("title") or ""),
                    str(p.get("source") or ""),
                    str(p.get("mbti") or ""),
                    str(p.get("id") or ""),
                ])).lower()
                if query in haystack:
                    results.append({
                        "kind": "persona",
                        "id": p.get("id"),
                        "label": p.get("name") or p.get("id"),
                        "sublabel": f"{p.get('title') or '—'} · {p.get('mbti') or '—'}",
                        "to": f"/personas/{p.get('id')}",
                    })
        except Exception:
            pass

    # Departments — derive distinct list from agents
    seen_depts: set[str] = set()
    for a in _load_agents():
        d = a.get("department")
        if d:
            seen_depts.add(d)
    for d in sorted(seen_depts):
        if query in d.lower():
            results.append({
                "kind": "department",
                "id": d,
                "label": d.capitalize(),
                "sublabel": "Department",
                "to": f"/agents?department={d}",
            })

    # Commands
    try:
        for c in _load_commands():
            haystack = " ".join(filter(None, [
                str(c.get("command") or ""),
                str(c.get("description") or ""),
                str(c.get("department") or ""),
            ])).lower()
            if query in haystack:
                results.append({
                    "kind": "command",
                    "id": c.get("command"),
                    "label": c.get("command"),
                    "sublabel": c.get("description") or c.get("department") or "",
                    "to": "/commands",
                })
    except Exception:
        pass

    return {"results": results[: max(0, int(limit))]}


# --- Persona import from Markdown (PR87b v3.20.0) ---

@app.post("/api/personas/import")
def personas_import(body: dict):
    """Import persona Markdown files (frontmatter + body) into the store.

    Body:
      {"files": [{"name": "Alex.md", "content": "..."}]}  # local picker
      {"urls":  ["https://example.com/raw.md", ...]}      # remote import

    Both keys are accepted; URLs are fetched server-side (PR91b
    v3.36.0) and converted into the same `{name, content}` shape
    before processing.

    Returns: {imported, failed, results: [{filename, status, id?, error?}]}
    """
    raw_files = body.get("files")
    raw_urls = body.get("urls")
    if raw_files is not None and not isinstance(raw_files, list):
        return {"error": "files must be a list"}
    if raw_urls is not None and not isinstance(raw_urls, list):
        return {"error": "urls must be a list"}
    files = list(raw_files or [])
    urls = list(raw_urls or [])
    mgr = _get_persona_manager()
    if not mgr:
        return {"error": "Persona manager unavailable"}

    from pathlib import Path as _Path

    from core.personas.obsidian_store import ObsidianPersonaStore

    # Resolve URLs into {name, content} entries.
    if urls:
        files.extend(_fetch_url_entries(urls))

    imported = 0
    failed = 0
    results: list[dict] = []
    for entry in files:
        if not isinstance(entry, dict):
            failed += 1
            results.append({"filename": "(invalid)", "status": "failed", "error": "not an object"})
            continue
        filename = str(entry.get("name") or "")
        content = str(entry.get("content") or "")
        # Carry forward URL-fetch errors so the operator sees them.
        if entry.get("fetch_error"):
            failed += 1
            results.append({
                "filename": filename, "status": "failed",
                "error": str(entry["fetch_error"]),
            })
            continue
        if not content.strip():
            failed += 1
            results.append({"filename": filename, "status": "failed", "error": "empty content"})
            continue
        fm = ObsidianPersonaStore._parse_frontmatter(content)
        if not fm or str(fm.get("type", "")).lower() != "persona":
            failed += 1
            results.append({
                "filename": filename, "status": "failed",
                "error": "missing or invalid frontmatter (type: persona required)",
            })
            continue
        try:
            persona = ObsidianPersonaStore._frontmatter_to_persona(
                fm, _Path(filename or "imported.md"),
            )
            mgr.create(persona)
            imported += 1
            results.append({"filename": filename, "status": "ok", "id": persona.id})
        except Exception as exc:  # noqa: BLE001
            failed += 1
            results.append({"filename": filename, "status": "failed", "error": str(exc)})

    return {"imported": imported, "failed": failed, "results": results}


def _fetch_url_entries(urls: list[str]) -> list[dict]:
    """Fetch each URL and return ``{name, content}`` entries. PR91b."""
    import urllib.error
    import urllib.parse
    import urllib.request
    out: list[dict] = []
    for raw in urls:
        url = str(raw or "").strip()
        if not url:
            continue
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https"):
            out.append({"name": url, "fetch_error": "scheme must be http(s)"})
            continue
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ArkaOS/persona-import"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                content = resp.read().decode("utf-8", errors="replace")
        except urllib.error.URLError as exc:
            out.append({"name": url, "fetch_error": f"fetch failed: {exc.reason}"})
            continue
        except (TimeoutError, OSError) as exc:
            out.append({"name": url, "fetch_error": f"fetch failed: {exc}"})
            continue
        # Derive a filename from the URL path.
        name = (parsed.path.rsplit("/", 1)[-1] or "imported.md").strip()
        if not name.endswith(".md"):
            name = f"{name or 'imported'}.md"
        out.append({"name": name, "content": content})
    return out


# --- Trash / Undo (PR85b v3.12.0) ---

@app.get("/api/trash")
def trash_list(limit: int = 10):
    from core import trash as _trash
    return {"entries": _trash.list_trash(limit=limit)}


@app.post("/api/trash/{trash_id}/restore")
def trash_restore(trash_id: str):
    from core import trash as _trash
    return _trash.restore(trash_id)


@app.delete("/api/trash/{trash_id}")
def trash_purge(trash_id: str):
    from core import trash as _trash
    return _trash.purge(trash_id)


@app.post("/api/personas/build")
def persona_build(body: dict):
    """PR57 v2.74.0 — AI-powered persona draft from already-indexed content.

    Body: {
        "name": "<person to model>",
        "search_query": "<optional vector search query>",
        "top_k": <optional, default 20>,
        "source_label": "<optional label, e.g. 'Alex Hormozi'>"
    }

    Returns: {persona: {...draft...}, chunks_used, provider_name}
    The draft is NOT saved — the operator reviews and calls
    POST /api/personas to persist.
    """
    name = (body.get("name") or "").strip()
    if not name:
        return {"error": "name is required"}
    store = _get_vector_store()
    if not store:
        from core.knowledge.vector_store import VectorStore
        kb_db = Path.home() / ".arkaos" / "knowledge.db"
        kb_db.parent.mkdir(parents=True, exist_ok=True)
        store = VectorStore(kb_db)
    from core.personas.builder import PersonaBuilder, PersonaBuildError
    builder = PersonaBuilder(store)
    try:
        result = builder.generate(
            name=name,
            search_query=body.get("search_query", ""),
            top_k=int(body.get("top_k", 20) or 20),
            source_label=body.get("source_label", ""),
        )
    except PersonaBuildError as exc:
        return {"error": str(exc)}
    return {
        "persona": result.persona.model_dump(),
        "chunks_used": result.chunks_used,
        "provider_name": result.provider_name,
    }


# --- Command center (PR66 v2.83.0) ---

@app.get("/api/overview/command-center")
def overview_command_center():
    """Telemetry-driven overview surfacing what the operator actually needs.

    Returns greeting, today's cost, project list with stack + last-commit
    + status, recent enforcement incidents, and suggested quick actions.
    """
    from core.profile import ProfileManager
    from core.profile.manager import parse_projects_dirs
    from core.runtime.llm_cost_telemetry import summarise

    profile = ProfileManager().read()
    today_cost = summarise(period="today")

    return {
        "greeting": {
            "name": profile.name,
            "role": profile.role,
            "company": profile.company,
            "language": profile.language,
        },
        "today_cost": {
            "total_usd": today_cost.total_cost_usd,
            "call_count": today_cost.call_count,
            "tokens_in": today_cost.total_tokens_in,
            "tokens_out": today_cost.total_tokens_out,
            "cache_hit_rate": today_cost.cache_hit_rate,
        },
        "projects": _scan_projects(parse_projects_dirs(profile.projectsDir)),
        "recent_incidents": _recent_incidents(limit=8),
        # PR84d v3.10.0 — extra command-center cards
        "top_departments_30d": _top_departments_by_cost(period="month", top_n=5),
        "recent_personas": _recent_personas(limit=5),
        "quick_actions": [
            {"command": "/arka update", "description": "Sync projects + skills"},
            {"command": "/arka costs", "description": "View detailed LLM cost breakdown"},
            {"command": "/arka conclave", "description": "Convene the personal AI advisory board"},
            {"command": "/dev review", "description": "Run a code review on the current branch"},
        ],
    }


def _top_departments_by_cost(period: str = "month", top_n: int = 5) -> list[dict]:
    """Top-N departments ranked by LLM spend over the period."""
    try:
        from core.runtime.llm_cost_telemetry import summarise, VALID_PERIODS
    except Exception:
        return []
    if period not in VALID_PERIODS:
        period = "month"
    summary = summarise(period=period)
    rows: list[dict] = []
    for category, row in (summary.by_category or {}).items():
        if not isinstance(category, str) or not category.startswith("subagent:"):
            continue
        dept = category.split(":", 1)[1] or "unknown"
        cost = row.get("total_cost_usd")
        rows.append({
            "department": dept,
            "calls": int(row.get("call_count", 0)),
            "cost_usd": float(cost) if isinstance(cost, (int, float)) else None,
            "tokens_in": int(row.get("total_tokens_in", 0)),
            "tokens_out": int(row.get("total_tokens_out", 0)),
        })
    rows.sort(key=lambda r: r["cost_usd"] or 0.0, reverse=True)
    return rows[: max(0, int(top_n))]


def _recent_personas(limit: int = 5) -> list[dict]:
    """Return the N most recently created/modified personas.

    Reads both the JSON store and the Obsidian vault; returns the
    union sorted by created_at desc (best-effort — entries without
    a timestamp sort last).
    """
    mgr = _get_persona_manager()
    if not mgr:
        return []
    try:
        personas = mgr.list() or []
    except Exception:
        return []
    def _ts(p: dict) -> str:
        return str(p.get("created_at") or p.get("_created_at") or "")
    sorted_p = sorted(personas, key=_ts, reverse=True)
    out: list[dict] = []
    for p in sorted_p[: max(0, int(limit))]:
        out.append({
            "id": p.get("id"),
            "name": p.get("name"),
            "title": p.get("title"),
            "mbti": p.get("mbti"),
            "source_store": (p.get("_source_store") or ""),
            "created_at": _ts(p) or None,
        })
    return out


def _scan_projects(projects_dirs: list[str]) -> list[dict]:
    """Read each project descriptor and enrich with last-commit info.

    Best-effort: never raises. Returns an empty list when descriptors
    or scan directories are missing.
    """
    from datetime import datetime, timezone
    descriptor_dir = Path.home() / ".arkaos" / "projects"
    if not descriptor_dir.exists():
        return []

    rows: list[dict] = []
    for entry in sorted(descriptor_dir.iterdir()):
        if entry.is_dir():
            descriptor = entry / "PROJECT.md"
        elif entry.suffix == ".md":
            descriptor = entry
        else:
            continue
        if not descriptor.exists():
            continue
        try:
            data = _parse_descriptor(descriptor)
        except Exception:
            continue
        rows.append(data)

    # Sort by last_commit_days ascending (most recently active first).
    rows.sort(key=lambda r: (
        r.get("last_commit_days") if r.get("last_commit_days") is not None else 9999,
        r.get("name", ""),
    ))
    return rows[:30]  # cap to keep payload bounded


def _parse_descriptor(path: Path) -> dict:
    """Extract frontmatter + last-commit-days from a project descriptor."""
    text = path.read_text(encoding="utf-8", errors="replace")
    fm: dict = {}
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end > 0:
            import yaml as _yaml
            try:
                fm = _yaml.safe_load(text[4:end]) or {}
            except Exception:
                fm = {}
    name = str(fm.get("name") or path.stem)
    project_path = str(fm.get("path") or "")
    stack = fm.get("stack") or []
    if not isinstance(stack, list):
        stack = [str(stack)]
    status = str(fm.get("status") or "unknown")
    ecosystem = str(fm.get("ecosystem") or "")
    last_commit_days = _last_commit_days(project_path) if project_path else None
    return {
        "name": name,
        "path": project_path,
        "stack": [str(s) for s in stack][:6],
        "status": status,
        "ecosystem": ecosystem,
        "last_commit_days": last_commit_days,
    }


def _last_commit_days(project_path: str) -> Optional[int]:
    """Return days since the last git commit, or None when unknown."""
    import os
    if not project_path or not os.path.isdir(project_path):
        return None
    git_dir = os.path.join(project_path, ".git")
    if not os.path.exists(git_dir):
        return None
    try:
        from datetime import datetime, timezone
        result = subprocess.run(
            ["git", "-C", project_path, "log", "-1", "--format=%ct"],
            capture_output=True, text=True, timeout=3, check=False,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None
        committed_at = datetime.fromtimestamp(int(result.stdout.strip()), tz=timezone.utc)
        delta = datetime.now(timezone.utc) - committed_at
        return max(0, delta.days)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


@app.get("/api/audit")
def audit_log(
    limit: int = 100,
    kind: Optional[str] = None,
    tool: Optional[str] = None,
):
    """PR90d v3.34.0 — paginated audit log of bypass/block events.

    Reads the same telemetry file as `_recent_incidents` but returns
    a larger window and accepts filter params. ``kind`` is one of
    ``"bypass"`` / ``"blocked"``. ``tool`` filters by tool name
    (Edit/Write/Bash/…).
    """
    log = Path.home() / ".arkaos" / "telemetry" / "enforcement.jsonl"
    if not log.exists():
        return {"events": [], "total": 0}
    try:
        text = log.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"events": [], "total": 0}
    events: list[dict] = []
    cap = max(0, min(int(limit), 500))
    for line in reversed(text.splitlines()):
        if len(events) >= cap:
            break
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        bypass = bool(entry.get("bypass_used"))
        allowed = entry.get("allow")
        if not bypass and allowed is not False:
            continue
        row_kind = "bypass" if bypass else "blocked"
        if kind and kind != row_kind:
            continue
        row_tool = entry.get("tool", "")
        if tool and tool != row_tool:
            continue
        events.append({
            "ts": entry.get("ts", ""),
            "tool": row_tool,
            "reason": entry.get("reason", ""),
            "cwd": entry.get("cwd", ""),
            "bypass_used": bypass,
            "kind": row_kind,
        })
    return {"events": events, "total": len(events)}


def _recent_incidents(limit: int = 8) -> list[dict]:
    """Recent enforcement / bypass events from telemetry.

    Reads the tail of ~/.arkaos/telemetry/enforcement.jsonl and keeps
    rows where the operator hit a bypass or a flow-marker block. The
    UI uses these to show "what went sideways recently".
    """
    log = Path.home() / ".arkaos" / "telemetry" / "enforcement.jsonl"
    if not log.exists():
        return []
    try:
        text = log.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    rows: list[dict] = []
    # Walk lines in reverse; stop when we've gathered `limit` matches.
    for line in reversed(text.splitlines()):
        if len(rows) >= limit:
            break
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        # Interesting events: bypass used OR allow=False (a block).
        bypass = bool(entry.get("bypass_used"))
        allowed = entry.get("allow")
        if not bypass and allowed is not False:
            continue
        rows.append({
            "ts": entry.get("ts", ""),
            "tool": entry.get("tool", ""),
            "reason": entry.get("reason", ""),
            "cwd": entry.get("cwd", ""),
            "bypass_used": bypass,
            "kind": "bypass" if bypass else "blocked",
        })
    return rows


# --- LLM Costs (PR65 v2.82.0) ---

@app.get("/api/llm-costs")
def llm_costs(period: str = "today"):
    """Aggregated LLM cost summary backed by the PR47 telemetry pipeline.

    `period` ∈ {today, week, month, all}. Returns the same shape the
    `/arka costs` CLI returns — by_provider, by_model, by_category
    (PR47), top sessions, advisories. The Budget page consumes this
    to show category-aware spend instead of the legacy
    /api/budget tokens-only view.
    """
    try:
        from core.runtime.llm_cost_telemetry import summarise, VALID_PERIODS
    except Exception as exc:  # pragma: no cover - import guard
        return {"error": f"telemetry unavailable: {exc}"}
    if period not in VALID_PERIODS:
        return {"error": f"period must be one of {list(VALID_PERIODS)}"}
    summary = summarise(period=period)
    return {
        "period": summary.period,
        "total_cost_usd": summary.total_cost_usd,
        "total_tokens_in": summary.total_tokens_in,
        "total_tokens_out": summary.total_tokens_out,
        "total_cached_tokens": summary.total_cached_tokens,
        "cache_hit_rate": summary.cache_hit_rate,
        "call_count": summary.call_count,
        "by_provider": summary.by_provider,
        "by_model": summary.by_model,
        "by_category": summary.by_category,
        "by_session": summary.by_session,
        "advisories": summary.advisories,
        "corrupt_line_count": summary.corrupt_line_count,
    }


@app.get("/api/llm-costs/export.csv")
def llm_costs_export(period: str = "month"):
    """PR91d v3.38.0 — stream the telemetry rows for the period as CSV.

    Returns ``text/csv`` with a header row + every row in the selected
    period. Period values match `summarise()`: today / week / month / all.
    """
    try:
        from core.runtime.llm_cost_telemetry import (
            VALID_PERIODS,
            _load_slice,
            _period_cutoff,
        )
    except Exception:
        return {"error": "telemetry unavailable"}
    if period not in VALID_PERIODS:
        period = "month"

    entries, _ = _load_slice(None, _period_cutoff(period, now=None))
    import csv
    import io
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "ts", "session_id", "provider", "model", "category",
        "tokens_in", "tokens_out", "cached_tokens", "estimated_cost_usd",
    ])
    for entry in entries:
        writer.writerow([
            entry.get("ts", ""),
            entry.get("session_id", ""),
            entry.get("provider", ""),
            entry.get("model", ""),
            entry.get("category", ""),
            entry.get("tokens_in", ""),
            entry.get("tokens_out", ""),
            entry.get("cached_tokens", ""),
            entry.get("estimated_cost_usd", ""),
        ])
    filename = f"arkaos-costs-{period}.csv"
    from fastapi import Response
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@app.get("/api/llm-costs/trend")
def llm_costs_trend(days: int = 7):
    """Day-by-day rolling totals from the cost telemetry.

    Returns ``{"days": [{"date": "YYYY-MM-DD", "cost_usd": x.xx,
    "tokens_in": N, "tokens_out": N, "call_count": N}]}`` so the
    Budget page can render a 7-day trend chart with @unovis/vue.
    Cap `days` to 90 to keep response size bounded.
    """
    from datetime import datetime, timedelta, timezone
    from core.runtime.llm_cost_telemetry import read_entries
    # `days or 7` would treat 0 as "use default", which contradicts the
    # documented floor-at-1 behaviour. Cast first, then clamp.
    try:
        days_int = int(days) if days is not None else 7
    except (TypeError, ValueError):
        days_int = 7
    capped_days = max(1, min(days_int, 90))
    today = datetime.now(timezone.utc).date()
    buckets: dict[str, dict] = {}
    # Seed every day so the chart shows zeros instead of gaps.
    for offset in range(capped_days):
        d = today - timedelta(days=capped_days - 1 - offset)
        buckets[d.isoformat()] = {
            "date": d.isoformat(),
            "cost_usd": 0.0,
            "cost_known": False,
            "tokens_in": 0,
            "tokens_out": 0,
            "call_count": 0,
        }
    cutoff = today - timedelta(days=capped_days - 1)
    for entry in read_entries():
        raw_ts = entry.get("ts") or ""
        if not isinstance(raw_ts, str):
            continue
        try:
            ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
        except ValueError:
            continue
        d = ts.date()
        if d < cutoff:
            continue
        key = d.isoformat()
        if key not in buckets:
            continue
        b = buckets[key]
        b["tokens_in"] += int(entry.get("tokens_in") or 0)
        b["tokens_out"] += int(entry.get("tokens_out") or 0)
        b["call_count"] += 1
        cost = entry.get("estimated_cost_usd")
        if cost is not None:
            b["cost_usd"] += float(cost)
            b["cost_known"] = True
    out_days = list(buckets.values())
    for b in out_days:
        b["cost_usd"] = round(b["cost_usd"], 6) if b.pop("cost_known") else None
    return {"days": out_days, "period_days": capped_days}


# --- Settings sections (PR63b v2.89.0): MCPs / Hooks / Plugins ---


@app.get("/api/settings/mcps")
def settings_mcps():
    """List MCP servers across user-global config + ArkaOS registry.

    Reads:
      - ``~/.claude.json::mcpServers`` (Claude Code user-global)
      - ``~/.claude/skills/arka/mcps/registry.json`` (ArkaOS registry)

    Returns a deduplicated list with each entry's name + source +
    transport (stdio / http / sse) where the config exposes it.
    """
    out: list[dict] = []
    seen: set[str] = set()

    user_global = Path.home() / ".claude.json"
    if user_global.exists():
        try:
            data = json.loads(user_global.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
        for name, cfg in (data.get("mcpServers") or {}).items():
            if not isinstance(name, str) or name in seen:
                continue
            seen.add(name)
            out.append({
                "name": name,
                "source": "user-global",
                "transport": _detect_mcp_transport(cfg),
                "command": (cfg or {}).get("command", "") if isinstance(cfg, dict) else "",
            })

    registry = Path.home() / ".claude" / "skills" / "arka" / "mcps" / "registry.json"
    if registry.exists():
        try:
            data = json.loads(registry.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
        servers = data.get("servers") if isinstance(data, dict) else None
        if isinstance(servers, dict):
            for name, cfg in servers.items():
                if not isinstance(name, str) or name in seen:
                    continue
                seen.add(name)
                out.append({
                    "name": name,
                    "source": "arkaos-registry",
                    "transport": _detect_mcp_transport(cfg),
                    "command": (cfg or {}).get("command", "") if isinstance(cfg, dict) else "",
                })
        elif isinstance(servers, list):
            for entry in servers:
                if not isinstance(entry, dict):
                    continue
                name = str(entry.get("name") or "")
                if not name or name in seen:
                    continue
                seen.add(name)
                out.append({
                    "name": name,
                    "source": "arkaos-registry",
                    "transport": _detect_mcp_transport(entry),
                    "command": entry.get("command", ""),
                })

    out.sort(key=lambda r: r["name"])
    return {"mcps": out, "total": len(out)}


def _detect_mcp_transport(cfg: object) -> str:
    """Best-effort transport sniff from an MCP server config dict."""
    if not isinstance(cfg, dict):
        return "unknown"
    if cfg.get("url"):
        return "http"
    if cfg.get("transport"):
        return str(cfg["transport"])
    if cfg.get("command"):
        return "stdio"
    return "unknown"


@app.get("/api/settings/hooks")
def settings_hooks():
    """Inspect the hooks block of ~/.claude/settings.json.

    Returns one row per hook type with command paths + timeouts so the
    operator can see at a glance which hooks are wired and which are
    missing. We never edit the file from here (Hooks ship from the
    ArkaOS installer); this is purely read-only diagnostics.
    """
    settings_file = Path.home() / ".claude" / "settings.json"
    if not settings_file.exists():
        return {"hooks": [], "settings_path": str(settings_file)}
    try:
        data = json.loads(settings_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"hooks": [], "settings_path": str(settings_file)}

    hooks_block = data.get("hooks") if isinstance(data, dict) else None
    if not isinstance(hooks_block, dict):
        return {"hooks": [], "settings_path": str(settings_file)}

    rows: list[dict] = []
    for hook_type, entries in hooks_block.items():
        if not isinstance(entries, list):
            continue
        commands: list[dict] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            inner = entry.get("hooks") if isinstance(entry, dict) else None
            if not isinstance(inner, list):
                continue
            for h in inner:
                if not isinstance(h, dict):
                    continue
                commands.append({
                    "command": str(h.get("command", ""))[:200],
                    "type": str(h.get("type", "command")),
                    "timeout": h.get("timeout"),
                })
        rows.append({
            "hook": hook_type,
            "count": len(commands),
            "commands": commands,
        })
    rows.sort(key=lambda r: r["hook"])
    hard_enforcement = bool(
        isinstance(data.get("hooks"), dict)
        and data["hooks"].get("hardEnforcement")
    )
    return {
        "hooks": rows,
        "settings_path": str(settings_file),
        "hard_enforcement": hard_enforcement,
    }


@app.get("/api/settings/plugins")
def settings_plugins():
    """List Claude Code plugins installed via ~/.claude/plugins/installed_plugins.json.

    The PR43 auto-installer + PR55 marketplace flow both touch this
    file. Format is ``{"plugins": {"<name>@<marketplace>": [entry,...]}}``.
    We flatten to one row per (name, marketplace, version).
    """
    plugins_file = Path.home() / ".claude" / "plugins" / "installed_plugins.json"
    if not plugins_file.exists():
        return {"plugins": [], "total": 0, "plugins_path": str(plugins_file)}
    try:
        data = json.loads(plugins_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"plugins": [], "total": 0, "plugins_path": str(plugins_file)}

    rows: list[dict] = []
    plugins_map = data.get("plugins") if isinstance(data, dict) else None
    if isinstance(plugins_map, dict):
        for key, entries in plugins_map.items():
            if not isinstance(entries, list):
                continue
            name, _, marketplace = str(key).partition("@")
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                rows.append({
                    "name": name,
                    "marketplace": marketplace,
                    "version": entry.get("version", ""),
                    "scope": entry.get("scope", ""),
                    "installed_at": entry.get("installedAt", ""),
                    "last_updated": entry.get("lastUpdated", ""),
                })
    rows.sort(key=lambda r: (r["marketplace"], r["name"]))
    return {
        "plugins": rows,
        "total": len(rows),
        "plugins_path": str(plugins_file),
    }


# --- Profile (PR63 v2.81.0) ---

@app.get("/api/settings/vault")
def settings_vault():
    """PR89c v3.29.0 — vault path connection test.

    Reads ``profile.vaultPath`` and reports back whether the path
    exists, whether ``Personas/`` and ``Agents/`` subdirs are present,
    and how many ``*.md`` files each contains.

    Returns ``{configured, vault_path, exists, personas: {dir, count},
    agents: {dir, count}}``.
    """
    from core.profile import ProfileManager
    profile = ProfileManager().read()
    configured = bool(profile.vaultPath)
    vault = Path(profile.vaultPath).expanduser() if configured else None
    exists = bool(vault and vault.exists() and vault.is_dir())

    def _subdir_info(name: str) -> dict:
        if not exists:
            return {"dir": "", "count": 0}
        sub = vault / name
        if not sub.exists():
            return {"dir": str(sub), "count": 0}
        try:
            count = sum(1 for _ in sub.glob("*.md"))
        except OSError:
            count = 0
        return {"dir": str(sub), "count": count}

    return {
        "configured": configured,
        "vault_path": str(vault) if vault else "",
        "exists": exists,
        "personas": _subdir_info("Personas"),
        "agents": _subdir_info("Agents"),
    }


@app.get("/api/profile")
def profile_get():
    """Return the operator profile from ~/.arkaos/profile.json.

    Always returns a profile object (default empty strings when the
    file doesn't exist yet) so the dashboard can render a setup form
    instead of an error.
    """
    from core.profile import ProfileManager
    from core.profile.manager import parse_projects_dirs
    profile = ProfileManager().read()
    payload = profile.to_dict()
    # Convenience: split projectsDir into a list for the UI.
    payload["projects_dirs_list"] = parse_projects_dirs(profile.projectsDir)
    return payload


@app.post("/api/profile")
def profile_post(body: dict):
    """Patch the operator profile.

    Only the writable fields are honoured (name, language, market,
    role, company, projectsDir, vaultPath). Unknown keys are silently
    dropped. Returns the updated profile.
    """
    if not isinstance(body, dict):
        return {"error": "body must be an object"}
    from core.profile import ProfileManager
    from core.profile.manager import parse_projects_dirs
    updated = ProfileManager().patch(body)
    payload = updated.to_dict()
    payload["projects_dirs_list"] = parse_projects_dirs(updated.projectsDir)
    return payload


# --- API Keys ---

@app.get("/api/keys")
def keys_list():
    try:
        from core.keys import list_keys
        return {"keys": list_keys()}
    except Exception:
        return {"keys": []}


@app.post("/api/keys")
def keys_set(body: dict):
    try:
        from core.keys import set_key
        name = body.get("key", "")
        value = body.get("value", "")
        if not name or not value:
            return {"error": "key and value required"}
        set_key(name, value)
        return {"set": True, "key": name}
    except Exception as e:
        return {"error": str(e)}


@app.delete("/api/keys/{key_name}")
def keys_delete(key_name: str):
    try:
        from core.keys import remove_key
        if remove_key(key_name):
            return {"deleted": True}
        return {"error": "Key not found"}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/metrics")
def metrics():
    metrics_file = Path("/tmp/arkaos-context-cache/hook-metrics.jsonl")
    if not metrics_file.exists():
        return {"entries": [], "avg_ms": 0}
    entries = []
    for line in metrics_file.read_text().strip().split("\n"):
        try:
            entries.append(json.loads(line))
        except Exception:
            continue
    avg_ms = sum(e.get("ms", 0) for e in entries) / len(entries) if entries else 0
    return {"entries": entries[-50:], "avg_ms": round(avg_ms, 1), "total_calls": len(entries)}


# --- Agent create (PR82 v3.0.0) ---

@app.post("/api/agents")
def agent_create(body: dict):
    """Create a new agent YAML file from a manual draft.

    Required body keys: name, role, department, tier.
    Optional: behavioral_dna, expertise, mental_models, communication,
    linked_personas, authority.

    Slug rule: <name-kebab>-<random-suffix> when no explicit `id` is
    given. The endpoint refuses to overwrite an existing file.
    """
    if not isinstance(body, dict):
        return {"error": "body must be an object"}
    return _do_agent_create(body)


def _do_agent_create(body: dict) -> dict:
    import re
    import uuid

    name = (body.get("name") or "").strip()
    role = (body.get("role") or "").strip()
    department = (body.get("department") or "").strip().lower()
    tier_raw = body.get("tier")
    if not name or not role or not department:
        return {"error": "name, role, and department are required"}
    try:
        tier = int(tier_raw) if tier_raw is not None else 2
    except (TypeError, ValueError):
        return {"error": "tier must be an integer"}

    dept_dir = ARKAOS_ROOT / "departments" / department / "agents"
    if not dept_dir.exists():
        return {"error": f"department '{department}' not found"}

    explicit_id = (body.get("id") or "").strip()
    if explicit_id:
        slug = _agent_slugify(explicit_id)
    else:
        slug = f"{_agent_slugify(name)}-{uuid.uuid4().hex[:6]}"
    yaml_file = dept_dir / f"{slug}.yaml"
    if yaml_file.exists():
        return {"error": f"agent with id '{slug}' already exists"}

    try:
        import yaml as _yaml
    except ImportError:
        return {"error": "PyYAML unavailable"}

    payload = _build_agent_yaml(slug, name, role, department, tier, body)
    try:
        tmp = yaml_file.with_suffix(yaml_file.suffix + ".tmp")
        tmp.write_text(
            _yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, default_flow_style=False),
            encoding="utf-8",
        )
        tmp.replace(yaml_file)
    except OSError as exc:
        return {"error": f"write failed: {exc}"}
    return {"id": slug, "created": True, "yaml_path": str(yaml_file)}


def _agent_slugify(text: str) -> str:
    import re
    cleaned = re.sub(r"[^a-z0-9-]+", "-", text.lower())
    cleaned = re.sub(r"-+", "-", cleaned).strip("-")
    return cleaned or "agent"


def _build_agent_yaml(
    slug: str, name: str, role: str, department: str, tier: int, body: dict,
) -> dict:
    """Compose the YAML payload, applying sensible defaults."""
    dna = body.get("behavioral_dna") or {}
    disc = dna.get("disc") or {}
    enneagram = dna.get("enneagram") or {}
    big_five = dna.get("big_five") or {}
    mbti_raw = dna.get("mbti")
    mbti = mbti_raw.get("type") if isinstance(mbti_raw, dict) else mbti_raw

    expertise = body.get("expertise") or {}
    mental_models = body.get("mental_models") or {}
    communication = body.get("communication") or {}
    authority = body.get("authority") or {}

    payload: dict = {
        "id": slug,
        "name": name,
        "role": role,
        "department": department,
        "tier": tier,
        "model": "opus" if tier == 0 else "sonnet",
        "behavioral_dna": {
            "disc": {
                "primary": (disc.get("primary") or "I").upper(),
                "secondary": (disc.get("secondary") or "S").upper(),
                "communication_style": disc.get("communication_style") or "",
                "under_pressure": disc.get("under_pressure") or "",
                "motivator": disc.get("motivator") or "",
            },
            "enneagram": {
                "type": int(enneagram.get("type") or 5),
                "wing": int(enneagram.get("wing") or 4),
                "core_motivation": enneagram.get("core_motivation") or "",
                "core_fear": enneagram.get("core_fear") or "",
                "subtype": enneagram.get("subtype") or "self-preservation",
            },
            "big_five": {
                "openness": int(big_five.get("openness") or 70),
                "conscientiousness": int(big_five.get("conscientiousness") or 70),
                "extraversion": int(big_five.get("extraversion") or 50),
                "agreeableness": int(big_five.get("agreeableness") or 60),
                "neuroticism": int(big_five.get("neuroticism") or 30),
            },
            "mbti": {"type": (mbti or "INTJ").upper()},
        },
        "authority": {
            "delegates_to": _agent_str_list(authority.get("delegates_to") or []),
            "escalates_to": authority.get("escalates_to") or "",
        },
        "expertise": {
            "domains": _agent_str_list(expertise.get("domains") or []),
            "frameworks": _agent_str_list(expertise.get("frameworks") or []),
            "depth": expertise.get("depth") or "advanced",
            "years_equivalent": int(expertise.get("years_equivalent") or 5),
        },
        "mental_models": {
            "primary": _agent_str_list(mental_models.get("primary") or []),
            "secondary": _agent_str_list(mental_models.get("secondary") or []),
        },
        "communication": {
            "tone": communication.get("tone") or "",
            "vocabulary_level": communication.get("vocabulary_level") or "specialist",
            "preferred_format": communication.get("preferred_format") or "",
            "language": communication.get("language") or "en",
            "avoid": _agent_str_list(communication.get("avoid") or []),
        },
        "linked_personas": _agent_str_list(body.get("linked_personas") or []),
    }
    return payload


# --- AI persona draft from description (PR83a v3.3.0) ---

@app.post("/api/personas/draft")
def personas_draft(body: dict):
    """Generate a Persona draft from a free-text description (no vector DB).

    Body: {
        "description": "...",    # min 20 chars
        "name": "Alex Carter",   # required
        "source_label": "..."    # optional
    }
    Returns: {"persona": {...}, "provider_name": "..."}

    Sibling to /api/personas/build (which requires indexed chunks). Useful
    when the operator wants a quick draft without ingesting sources first.
    The result is NOT saved — operator reviews + POSTs to /api/personas.
    """
    from core.personas.description_drafter import (
        PersonaDraftError,
        draft_persona_from_description,
    )

    description = (body.get("description") or "").strip()
    name = (body.get("name") or "").strip()
    source_label = (body.get("source_label") or "").strip()
    try:
        res = draft_persona_from_description(
            description, name=name, source_label=source_label,
        )
    except PersonaDraftError as exc:
        return {"error": str(exc)}
    return {
        "persona": res.persona.model_dump(),
        "provider_name": res.provider_name,
    }


# --- AI agent draft from description (PR82b v3.1.0) ---

@app.post("/api/agents/draft")
def agents_draft(body: dict):
    """Generate a full agent draft from a free-text description.

    Body: {
        "description": "...",   # min 20 chars
        "name": "Lucas",         # optional
        "role": "Market Analyst",# optional
        "department": "strategy",# optional
        "tier": 2                # optional, default 2
    }
    Returns: {"draft": {...behavioral_dna, expertise, mental_models,
    communication...}, "provider_name": "..."}
    """
    from core.agents.draft_builder import DraftError, draft_agent

    description = (body.get("description") or "").strip()
    try:
        tier = int(body.get("tier") or 2)
    except (TypeError, ValueError):
        tier = 2
    try:
        res = draft_agent(
            description,
            name=(body.get("name") or "").strip(),
            role=(body.get("role") or "").strip(),
            department=(body.get("department") or "").strip(),
            tier=tier,
        )
    except DraftError as exc:
        return {"error": str(exc)}
    return {"draft": res.draft, "provider_name": res.provider_name}


# --- AI single-string suggester (PR83c v3.5.0) ---

@app.post("/api/agents/suggest-string")
def agents_suggest_string(body: dict):
    """Suggest a single-string value (tone, preferred_format, language)."""
    return _do_string_suggest(body, source="agent")


@app.post("/api/personas/suggest-string")
def personas_suggest_string(body: dict):
    return _do_string_suggest(body, source="persona")


def _do_string_suggest(body: dict, *, source: str) -> dict:
    from core.agents.string_suggester import (
        StringSuggestionError,
        suggest_string_field,
    )
    field = (body.get("field") or "").strip()
    context = body.get("context") or {}
    try:
        res = suggest_string_field(field, context)
    except StringSuggestionError as exc:
        return {"error": str(exc)}
    return {"value": res.value, "provider_name": res.provider_name, "source": source}


# --- AI list-field suggester (PR81 v2.99.0) ---

@app.post("/api/agents/suggest")
def agents_suggest(body: dict):
    """Suggest list items for the agent edit drawer via LLM.

    Body: {
        "field": "mental_models" | "frameworks" | "expertise_domains",
        "context": {"name", "role", "department", "current": [...]},
        "count": <optional, default 5, max 12>
    }
    Returns: {"suggestions": [...], "provider_name": "...", "source": "agent"}
    """
    return _do_field_suggest(body, source="agent")


@app.post("/api/personas/suggest")
def personas_suggest(body: dict):
    """Suggest list items for the persona edit slideover via LLM.

    Same shape as /api/agents/suggest. `context.title` may be passed
    instead of `context.role` for personas.
    """
    return _do_field_suggest(body, source="persona")


def _do_field_suggest(body: dict, *, source: str) -> dict:
    from core.agents.field_suggester import SuggestionError, suggest_field

    field = (body.get("field") or "").strip()
    context = body.get("context") or {}
    count = body.get("count") or 5
    try:
        res = suggest_field(field, context, count=int(count))
    except SuggestionError as exc:
        return {"error": str(exc)}
    return {
        "suggestions": res.suggestions,
        "provider_name": res.provider_name,
        "source": source,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=3334)
    parser.add_argument("--host", type=str, default="127.0.0.1")
    args = parser.parse_args()

    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
