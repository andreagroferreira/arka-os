#!/usr/bin/env python3
"""Synapse Bridge — standalone script for hook integration.

Reads JSON from stdin, runs the 8-layer Synapse engine, outputs JSON to stdout.
Loads constitution, agent registry, and command registry automatically.

Usage:
    echo '{"user_input":"validate my saas idea"}' | python3 scripts/synapse-bridge.py
    echo '{}' | python3 scripts/synapse-bridge.py --layers-only

Exit codes: 0 = success, 1 = degraded (partial layers), 2 = error
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Resolve ArkaOS root from environment or script location
ARKAOS_ROOT = Path(os.environ.get("ARKAOS_ROOT", Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(ARKAOS_ROOT))


def load_constitution(root: Path) -> str:
    """Load and compress constitution rules."""
    config_path = root / "config" / "constitution.yaml"
    if not config_path.exists():
        return ""
    try:
        from core.governance.constitution import load_constitution as _load

        const = _load(str(config_path))
        parts = []
        for level_name in ("non_negotiable", "quality_gate", "must", "should"):
            level = getattr(const, level_name, None)
            if level and hasattr(level, "rules"):
                ids = [r.id for r in level.rules]
                if ids:
                    parts.append(f"{level_name.upper()}: {', '.join(ids)}")
        return " | ".join(parts) if parts else ""
    except Exception:
        return ""


def load_agents_registry(root: Path) -> dict:
    """Load agents registry JSON."""
    path = root / "knowledge" / "agents-registry-v2.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
        agents = {}
        for agent in data.get("agents", []):
            agent_id = agent.get("id", "")
            if agent_id:
                agents[agent_id] = agent
        return agents
    except Exception:
        return {}


def load_commands_registry(root: Path) -> list:
    """Load commands registry JSON."""
    path = root / "knowledge" / "commands-registry-v2.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
        return data.get("commands", [])
    except Exception:
        return []


def main() -> int:
    parser = argparse.ArgumentParser(description="Synapse Bridge — context injection for hooks")
    parser.add_argument(
        "--layers-only",
        action="store_true",
        help="Output layer breakdown instead of context string",
    )
    parser.add_argument("--root", type=str, default=str(ARKAOS_ROOT), help="ArkaOS root directory")
    args = parser.parse_args()

    root = Path(args.root)
    start = time.time()

    # Read input from stdin
    try:
        raw = sys.stdin.read().strip()
        input_data = json.loads(raw) if raw else {}
    except (json.JSONDecodeError, Exception):
        input_data = {}

    # Extract context fields
    user_input = input_data.get("user_input", "")
    if not user_input:
        # Claude Code hook format: the full input is the user message
        user_input = raw if raw and not raw.startswith("{") else ""

    # Load registries
    constitution = load_constitution(root)
    agents = load_agents_registry(root)
    commands = load_commands_registry(root)

    # Load vector store (optional — graceful if unavailable)
    vector_store = None
    kb_db = Path(os.environ.get("ARKAOS_KNOWLEDGE_DB", Path.home() / ".arkaos" / "knowledge.db"))
    if kb_db.exists():
        try:
            from core.knowledge.vector_store import VectorStore

            vector_store = VectorStore(kb_db)
        except Exception:
            pass

    # Build engine
    try:
        from core.synapse.engine import create_default_engine
        from core.synapse.layers import PromptContext

        engine = create_default_engine(
            constitution_compressed=constitution,
            commands=commands,
            agents_registry=agents,
            vector_store=vector_store,
        )

        # Build context
        import subprocess

        try:
            branch = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                timeout=2,
                cwd=input_data.get("cwd", os.getcwd()),
            ).stdout.strip()
        except Exception:
            branch = ""

        session_id = (
            input_data.get("session_id")
            or os.environ.get("ARKAOS_SESSION_ID", "")
            or os.environ.get("CLAUDE_SESSION_ID", "")
            or f"bridge-{os.getpid()}"
        )

        ctx = PromptContext(
            user_input=user_input,
            cwd=input_data.get("cwd", os.getcwd()),
            git_branch=branch,
            project_name=input_data.get("project_name", ""),
            project_stack=input_data.get("project_stack", ""),
            active_agent=input_data.get("active_agent", ""),
            runtime_id=input_data.get("runtime_id", "claude-code"),
            extra={"session_id": session_id},
        )

        result = engine.inject(ctx)
        total_ms = int((time.time() - start) * 1000)

        # Record token usage in budget tracker
        try:
            from core.budget.manager import BudgetManager

            budget_mgr = BudgetManager(storage_path=Path.home() / ".arkaos" / "budget-usage.json")
            # Extract department from result layers
            dept = ""
            for lr in result.layers:
                if lr.layer_id == "L1" and lr.tag:
                    dept = lr.tag.replace("[dept:", "").replace("]", "")
                    break
            budget_mgr.record_usage(
                agent_id=ctx.active_agent or "system",
                tokens=result.total_tokens_est,
                tier=2,
                department=dept,
                description="synapse-context-injection",
            )
        except Exception:
            pass  # Never block on budget tracking

        if args.layers_only:
            output = {
                "context_string": result.context_string,
                "layers": [
                    {
                        "id": lr.layer_id,
                        "tag": lr.tag,
                        "tokens": lr.tokens_est,
                        "cached": lr.cached,
                        "ms": lr.compute_ms,
                    }
                    for lr in result.layers
                ],
                "total_ms": total_ms,
                "total_tokens": result.total_tokens_est,
                "cache_stats": result.cache_stats,
                "layers_skipped": result.layers_skipped,
            }
        else:
            output = {"context_string": result.context_string, "total_ms": total_ms}

        print(json.dumps(output))
        return 0

    except ImportError as e:
        # Python dependencies not available — output minimal context
        sys.stderr.write(f"synapse-bridge: import error: {e}\n")
        print(json.dumps({"context_string": "", "error": str(e)}))
        return 1

    except Exception as e:
        sys.stderr.write(f"synapse-bridge: error: {e}\n")
        print(json.dumps({"context_string": "", "error": str(e)}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
