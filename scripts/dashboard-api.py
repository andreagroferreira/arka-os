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

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="ArkaOS Dashboard API", version="2.0.3")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3333", "http://localhost:3000"],
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
        except Exception:
            pass

    return base


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


@app.post("/api/knowledge/ingest")
def knowledge_ingest(body: dict):
    """Ingest content into the knowledge base. Runs in background."""
    import threading

    source = body.get("source", "")
    source_type = body.get("type", "")
    if not source:
        return {"error": "source is required"}

    task_mgr = _get_task_manager()
    store = _get_vector_store()
    if not store:
        # Create store if it doesn't exist
        from core.knowledge.vector_store import VectorStore
        kb_db = Path.home() / ".arkaos" / "knowledge.db"
        kb_db.parent.mkdir(parents=True, exist_ok=True)
        store = VectorStore(kb_db)

    from core.knowledge.ingest import IngestEngine, detect_source_type
    if not source_type:
        source_type = detect_source_type(source)

    # Create task
    from core.tasks.schema import TaskType
    task = task_mgr.create(
        title=f"Ingest {source_type}: {source[:80]}",
        task_type=TaskType.KB_INDEX,
        description=source,
        department="kb",
    )

    def run_ingest():
        engine = IngestEngine(store)
        def on_progress(pct, msg):
            task_mgr.update_progress(task.id, pct, msg)
        try:
            task_mgr.start(task.id)
            result = engine.ingest(source, source_type, on_progress=on_progress)
            if result.success:
                task_mgr.complete(task.id, output={
                    "chunks_created": result.chunks_created,
                    "text_length": result.text_length,
                    "title": result.title,
                })
            else:
                task_mgr.fail(task.id, result.error)
        except Exception as e:
            task_mgr.fail(task.id, str(e))

    thread = threading.Thread(target=run_ingest, daemon=True)
    thread.start()

    return {"task_id": task.id, "source_type": source_type, "status": "queued"}


@app.get("/api/tasks/{task_id}")
def task_detail(task_id: str):
    """Get a single task by ID."""
    mgr = _get_task_manager()
    if not mgr:
        return {"error": "Task manager unavailable"}
    task = mgr.get(task_id)
    if not task:
        return {"error": "Task not found"}
    return task.model_dump()


@app.get("/api/knowledge/stats")
def knowledge_stats():
    store = _get_vector_store()
    if not store:
        return {"total_chunks": 0, "total_files": 0, "vss_available": False, "indexed": False}
    stats = store.get_stats()
    stats["indexed"] = stats["total_chunks"] > 0
    return stats


@app.get("/api/knowledge/search")
def knowledge_search(q: str = Query(...), top_k: int = Query(5)):
    store = _get_vector_store()
    if not store:
        return {"results": [], "query": q}
    results = store.search(q, top_k=min(top_k, 20))
    return {"results": results, "query": q, "total": len(results)}


@app.get("/api/health")
def health():
    checks = []
    arkaos_home = Path.home() / ".arkaos"

    def check(name, condition, fix=""):
        checks.append({"name": name, "passed": condition, "fix": fix})

    check("install_dir", arkaos_home.exists(), "Run: npx arkaos install")
    check("manifest", (arkaos_home / "install-manifest.json").exists(), "Run: npx arkaos install")
    check("constitution", (ARKAOS_ROOT / "config" / "constitution.yaml").exists())
    check("agents_registry", (ARKAOS_ROOT / "knowledge" / "agents-registry-v2.json").exists())
    check("commands_registry", (ARKAOS_ROOT / "knowledge" / "commands-registry-v2.json").exists())
    check("hooks_dir", (arkaos_home / "config" / "hooks").exists(), "Run: npx arkaos install")

    try:
        subprocess.run(["python3", "--version"], capture_output=True, timeout=2)
        check("python", True)
    except Exception:
        check("python", False, "Install Python 3.11+")

    check("knowledge_db", (arkaos_home / "knowledge.db").exists(), "Run: npx arkaos index")

    passed = sum(1 for c in checks if c["passed"])
    return {"checks": checks, "passed": passed, "total": len(checks), "healthy": passed == len(checks)}


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
    mgr = _get_persona_manager()
    if not mgr:
        return {"personas": [], "total": 0}
    personas = mgr.list_all()
    return {"personas": [p.model_dump() for p in personas], "total": len(personas)}


@app.get("/api/personas/{persona_id}")
def persona_detail(persona_id: str):
    mgr = _get_persona_manager()
    if not mgr:
        return {"error": "Persona manager unavailable"}
    p = mgr.get(persona_id)
    if not p:
        return {"error": "Persona not found"}
    return p.model_dump()


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
    return {"id": persona.id, "created": True}


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


@app.delete("/api/personas/{persona_id}")
def persona_delete(persona_id: str):
    mgr = _get_persona_manager()
    if not mgr:
        return {"error": "Persona manager unavailable"}
    if mgr.delete(persona_id):
        return {"deleted": True}
    return {"error": "Persona not found"}


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


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=3334)
    parser.add_argument("--host", type=str, default="127.0.0.1")
    args = parser.parse_args()

    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
