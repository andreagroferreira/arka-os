"""ArkaOS — programmatic MCP tools server (F2-3, Claude Code reform).

Where ``arka-prompts`` exposes department commands as PROMPTS, this
server exposes the core engine as TOOLS: KB vector search, workflow
state, Quality Gate queue, validated recipes, session memory and
telemetry summaries — grounded in the real ``core/`` APIs, never
re-implemented here.

Honesty contract (the explicit anti-pattern is claude-flow's fabricated
fallbacks): a tool whose backing store is absent returns
``{"available": false, "reason": ...}`` — real emptiness, never invented
data. Retrieval results carry their provenance labels
(``semantic`` / ``keyword-degraded``) untouched.

Write tools (workflow_update_phase, qg_submit) are DISABLED unless
``ARKA_TOOLS_WRITE=1`` — v1 ships read-first; mutation is an explicit
operator opt-in. ``qg_verdict`` is deliberately NOT exposed: a Quality
Gate verdict emitted by the same model doing the work defeats the whole
point of an INDEPENDENT gate (arkaos-not-yes-man). Verdicts stay with
the human/CQO reviewer path, never a self-service tool.

Usage: ``uv run server.py`` (deployed to ~/.claude/skills/arka/mcp-tools).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP


def _resolve_repo() -> str:
    env = os.environ.get("ARKA_OS", "")
    if env and (Path(env) / "core").is_dir():
        return env
    repo_file = Path.home() / ".arkaos" / ".repo-path"
    try:
        candidate = repo_file.read_text(encoding="utf-8").strip()
        if candidate and (Path(candidate) / "core").is_dir():
            return candidate
    except OSError:
        pass
    return ""


_REPO = _resolve_repo()
if _REPO:
    sys.path.insert(0, _REPO)

mcp = FastMCP(
    "arka-tools",
    instructions=(
        "ArkaOS programmatic tools: kb_search (vector KB, honest degraded"
        " labels), workflow_get/update_phase, Quality Gate queue"
        " (qg_pending/status/submit — NO verdict tool: gate independence),"
        " recipes_search/recipe_get, session_memory_search (project scope"
        " required), telemetry_summary, forge_plan, routing_scores. Write"
        " tools require ARKA_TOOLS_WRITE=1."
    ),
)

_UNAVAILABLE = {"available": False}


def _unavailable(reason: str) -> dict[str, Any]:
    """Honest emptiness — never fabricated data (anti-claude-flow)."""
    return {**_UNAVAILABLE, "reason": reason}


def _writes_enabled() -> bool:
    return os.environ.get("ARKA_TOOLS_WRITE", "").strip() == "1"


def _writes_disabled_error() -> dict[str, Any]:
    return _unavailable(
        "write tools are disabled — set ARKA_TOOLS_WRITE=1 in the MCP"
        " server env to enable (v1 ships read-first)"
    )


@mcp.tool()
def kb_search(query: str, top_k: int = 5) -> dict[str, Any]:
    """Search the ArkaOS knowledge base (vector store at ~/.arkaos/knowledge.db).

    Results carry their retrieval provenance: 'semantic' (real similarity
    score) or 'keyword-degraded' (substring match, score=None) — never
    faked.
    """
    if not _REPO:
        return _unavailable("ArkaOS repo not resolvable (~/.arkaos/.repo-path)")
    db_path = Path.home() / ".arkaos" / "knowledge.db"
    if not db_path.is_file():
        return _unavailable("knowledge.db not found — run /arka index first")
    from core.knowledge.vector_store import VectorStore

    results = VectorStore(db_path).search(query, top_k=top_k)
    return {"available": True, "results": results, "count": len(results)}


@mcp.tool()
def workflow_get() -> dict[str, Any]:
    """Current workflow state (phases, branch, violations) or none-active."""
    if not _REPO:
        return _unavailable("ArkaOS repo not resolvable")
    from core.workflow.state import get_state

    state = get_state()
    if not state:
        return {"available": True, "active": False}
    return {"available": True, "active": True, "state": state}


@mcp.tool()
def workflow_update_phase(
    phase: str, status: str, artifact: str = ""
) -> dict[str, Any]:
    """WRITE (gated): set a workflow phase status (pending/in_progress/
    completed/skipped), optionally attaching an evidence artifact path."""
    if not _writes_enabled():
        return _writes_disabled_error()
    if not _REPO:
        return _unavailable("ArkaOS repo not resolvable")
    from core.workflow.state import update_phase

    try:
        state = update_phase(phase, status, artifact or None)
    except ValueError as exc:
        return _unavailable(str(exc))
    return {"available": True, "state": state}


@mcp.tool()
def qg_pending(reviewer: str = "") -> dict[str, Any]:
    """Quality Gate submissions awaiting review (optionally per reviewer)."""
    if not _REPO:
        return _unavailable("ArkaOS repo not resolvable")
    from core.governance.quality_api import list_pending

    pending = list_pending(reviewer or None)
    return {"available": True, "pending": pending, "count": len(pending)}


@mcp.tool()
def qg_status(submission_id: str) -> dict[str, Any]:
    """One Quality Gate submission by id, with its verdict history."""
    if not _REPO:
        return _unavailable("ArkaOS repo not resolvable")
    from core.governance.quality_api import query

    record = query(submission_id)
    if record is None:
        return _unavailable(f"no QG submission with id {submission_id!r}")
    return {"available": True, "submission": record}


@mcp.tool()
def qg_submit(
    title: str, description: str, deliverable_type: str, submitter: str
) -> dict[str, Any]:
    """WRITE (gated): submit a deliverable to the Quality Gate queue."""
    if not _writes_enabled():
        return _writes_disabled_error()
    if not _REPO:
        return _unavailable("ArkaOS repo not resolvable")
    from core.governance.quality_api import submit

    record = submit(
        title=title,
        description=description,
        deliverable_type=deliverable_type,
        submitter=submitter,
    )
    return {"available": True, "submission": record}


# NOTE: qg_verdict is intentionally NOT a tool. A verdict emitted by the
# same model doing the work is not an independent gate — it is a
# rubber stamp. Verdicts stay with the CQO/human reviewer path.


@mcp.tool()
def recipes_search(keywords: str = "", stack: str = "") -> dict[str, Any]:
    """QG-approved validated recipes matching keywords and/or stack.

    Read-only by design — recipe capture stays operator-confirmed
    (confidentiality contract of core/knowledge/recipes.py).
    """
    if not _REPO:
        return _unavailable("ArkaOS repo not resolvable")
    from core.knowledge.recipes import list_recipes

    wanted_kw = {w.strip().lower() for w in keywords.split(",") if w.strip()}
    wanted_stack = {s.strip().lower() for s in stack.split(",") if s.strip()}
    matches = []
    for recipe in list_recipes():
        recipe_kw = {k.lower() for k in recipe.feature_keywords}
        recipe_stack = {s.lower() for s in recipe.stack}
        if wanted_kw and not (wanted_kw & recipe_kw):
            continue
        if wanted_stack and not (wanted_stack & recipe_stack):
            continue
        matches.append({
            "slug": recipe.slug, "name": recipe.name,
            "problem": recipe.problem, "stack": recipe.stack,
            "path": f"~/.arkaos/recipes/{recipe.slug}/",
        })
    return {"available": True, "recipes": matches, "count": len(matches)}


@mcp.tool()
def recipe_get(slug: str) -> dict[str, Any]:
    """Full detail of one validated recipe (files, AC, apply notes)."""
    if not _REPO:
        return _unavailable("ArkaOS repo not resolvable")
    from core.knowledge.recipes import load_recipe

    recipe = load_recipe(slug)
    if recipe is None:
        return _unavailable(f"no recipe with slug {slug!r}")
    return {"available": True, "recipe": recipe.model_dump()}


@mcp.tool()
def session_memory_search(query: str, project: str) -> dict[str, Any]:
    """Cross-session turn memory for ONE project (scope is REQUIRED —
    an unscoped search would leak one client's turns into another's
    context; v2.18.0 confidentiality precedent). Labels are honest:
    keyword-degraded results carry score=None."""
    if not _REPO:
        return _unavailable("ArkaOS repo not resolvable")
    if not project.strip():
        return _unavailable("project scope is required — never searches globally")
    from core.memory.semantic_store import SessionMemoryStore, default_db_path

    if not default_db_path().is_file():
        return _unavailable("session-memory.db not found (no turns captured yet)")
    from core.memory.semantic_store import neutralize_summary

    hits = SessionMemoryStore().keyword_search(query, project.strip(), top_k=5)
    # WHITELIST the model-visible surface to the canonical read-path's
    # minimal shape (session_memory_layer.py L9.5) — keyword_search dumps
    # the whole ~14-field record, and cwd/file_paths are attacker-stored
    # free text NOT constrained by the project scope. Every free-text
    # field is neutralized (OWASP LLM01): a stored [arka:design]/newline
    # must never reach the model able to forge a gate marker.
    results = [
        {
            "summary": neutralize_summary(hit.get("summary", "")),
            "project_name": neutralize_summary(hit.get("project_name", "")),
            "ts": hit.get("ts", ""),
            "score": hit.get("score"),
            "retrieval": hit.get("retrieval", ""),
        }
        for hit in hits
    ]
    return {"available": True, "results": results, "count": len(results)}


@mcp.tool()
def telemetry_summary(period: str = "today") -> dict[str, Any]:
    """Enforcement + LLM-cost telemetry rollups (today/week/month/all)."""
    if not _REPO:
        return _unavailable("ArkaOS repo not resolvable")
    out: dict[str, Any] = {"available": True}
    try:
        from core.governance.enforcement_telemetry import summarise as enf
        out["enforcement"] = enf(period).__dict__
    except Exception as exc:
        out["enforcement"] = _unavailable(f"enforcement summary failed: {exc}")
    try:
        from core.runtime.llm_cost_telemetry import summarise as cost
        out["llm_cost"] = cost(period).__dict__
    except Exception as exc:
        out["llm_cost"] = _unavailable(f"cost summary failed: {exc}")
    return out


@mcp.tool()
def forge_plan() -> dict[str, Any]:
    """The active Forge plan (name, status, phases) or none-active."""
    if not _REPO:
        return _unavailable("ArkaOS repo not resolvable")
    from core.forge.persistence import get_active_plan

    plan = get_active_plan()
    if plan is None:
        return {"available": True, "active": False}
    return {
        "available": True, "active": True,
        "name": getattr(plan, "name", ""),
        "status": getattr(plan, "status", ""),
        "phases": len(getattr(plan, "plan_phases", []) or []),
    }


@mcp.tool()
def routing_scores() -> dict[str, Any]:
    """Per-department QG approval evidence (routing-scores.json, F1-B1) —
    the citable counts behind [arka:redo-risk]."""
    if not _REPO:
        return _unavailable("ArkaOS repo not resolvable")
    from core.governance.routing_feedback import load_scores

    scores = load_scores()
    if scores is None:
        return _unavailable(
            "routing-scores.json absent/invalid — run"
            " core.governance.routing_feedback_cli rebuild"
        )
    return {"available": True, **scores.model_dump()}


if __name__ == "__main__":
    mcp.run()
