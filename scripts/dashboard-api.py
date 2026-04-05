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
    allow_methods=["GET"],
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
    agents = _load_agents()
    for a in agents:
        if a.get("id") == agent_id:
            return a
    return {"error": "Agent not found"}


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
        return {"tiers": []}
    return {"tiers": [mgr.get_summary(tier=t).model_dump() for t in range(4)]}


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
