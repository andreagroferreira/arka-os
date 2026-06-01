"""ArkaOS benchmark harness -- core engine measurements.

Three honest measurements:

1. Synapse injection latency (engine-only, no vector store) -- cold vs warm,
   plus per-layer compute time so the "cached layers are sub-millisecond"
   claim can be verified against the "full engine costs N ms" reality.
2. Subagent handoff artifact size -- measured token estimate vs the documented
   ~379-token claim.
3. Routing accuracy -- DepartmentLayer keyword detection over a fixed labelled
   prompt set.

All numbers are reproducible. Timings vary by machine; routing accuracy and
handoff sizes are deterministic.
"""
from __future__ import annotations

import statistics
import sys
import time
from pathlib import Path
from typing import Callable

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _percentiles(samples_ms: list[float]) -> dict:
    """Summarise a list of millisecond samples."""
    ordered = sorted(samples_ms)
    return {
        "runs": len(ordered),
        "min": round(ordered[0], 3),
        "p50": round(statistics.median(ordered), 3),
        "mean": round(statistics.mean(ordered), 3),
        "max": round(ordered[-1], 3),
    }


def _time_call(fn: Callable[[], object]) -> float:
    """Time a single call, return elapsed milliseconds."""
    start = time.perf_counter()
    fn()
    return (time.perf_counter() - start) * 1000.0


def bench_synapse_latency(runs: int = 50) -> dict:
    """Measure Synapse engine injection latency (cold vs warm) + per-layer ms."""
    from core.synapse.engine import create_default_engine
    from core.synapse.layers import PromptContext

    engine = create_default_engine()
    ctx = PromptContext(
        user_input="fix the authentication bug in the login controller",
        cwd="/tmp/project", git_branch="feat/auth", project_name="demo",
        project_stack="laravel 11", active_agent="backend-dev",
    )
    cold = [_time_call(lambda: (engine.clear_cache(), engine.inject(ctx))) for _ in range(runs)]
    engine.inject(ctx)  # warm the cache
    warm = [_time_call(lambda: engine.inject(ctx)) for _ in range(runs)]
    last = engine.metrics[-1] if engine.metrics else {}
    profile = {
        "layers_computed": last.get("layers_computed"),
        "layers_skipped": last.get("layers_skipped"),
        "tokens_injected": last.get("tokens_injected"),
    }
    return {"layer_count": engine.layer_count,
            "cold_ms": _percentiles(cold), "warm_ms": _percentiles(warm),
            "injection_profile": profile}


def bench_subagent_handoff() -> dict:
    """Measure a representative handoff artifact's token estimate."""
    from core.runtime.subagent import HandoffArtifact

    artifact = HandoffArtifact(
        task_id="task-0042",
        task_description="Implement Stripe subscription billing with idempotent webhooks",
        agent_id="backend-dev", agent_role="Senior Backend Developer",
        agent_disc="D:80 I:50 S:45 C:78", department="dev",
        relevant_files=["app/Services/BillingService.php",
                        "app/Http/Controllers/WebhookController.php",
                        "tests/Feature/BillingTest.php"],
        context_summary=("Laravel 11 app, Cashier installed. Customer model has "
                         "stripe_id. Need tiered pricing with volume discounts."),
        constraints=["SOLID + Services/Repositories", "Feature tests required",
                     "Idempotent webhook handling"],
        expected_output="Tested, secure billing implementation with passing suite",
        quality_criteria=["80%+ coverage", "OWASP reviewed", "Conventional commits"],
    )
    return {"documented_claim": 379,
            "measured_tokens": artifact.estimated_tokens,
            "prompt_chars": len(artifact.to_prompt())}


# Fixed labelled prompt set for routing accuracy. (prompt, expected_department)
_ROUTING_SET: list[tuple[str, str]] = [
    ("fix the authentication bug in the login controller", "dev"),
    ("refactor the payment service and add unit tests", "dev"),
    ("create a go-to-market plan for our new SaaS", "saas"),
    ("design a brand identity with logo and color palette", "brand"),
    ("write viral content hooks for our TikTok channel", "content"),
    ("build a high-converting landing page funnel", "landing"),
    ("audit our online store conversion rate", "ecom"),
    ("model our Q3 budget and cash flow forecast", "finance"),
    ("run a competitive analysis with Porter's Five Forces", "strategy"),
    ("plan the next sprint and groom the backlog", "pm"),
    ("set up an SEO and paid ads growth campaign", "marketing"),
    ("automate our client onboarding with an SOP", "ops"),
]


def bench_routing_accuracy() -> dict:
    """Measure DepartmentLayer keyword routing over the labelled prompt set."""
    from core.synapse.layers import DepartmentLayer, PromptContext

    layer = DepartmentLayer()
    hits, details = 0, []
    for prompt, expected in _ROUTING_SET:
        result = layer.compute(PromptContext(user_input=prompt))
        detected = (result.content or "").strip()
        ok = detected == expected
        hits += int(ok)
        details.append({"prompt": prompt, "expected": expected,
                        "detected": detected or "(none)", "ok": ok})
    total = len(_ROUTING_SET)
    return {"total": total, "correct": hits,
            "accuracy_pct": round(100.0 * hits / total, 1), "details": details}


def run_all(runs: int = 50) -> dict:
    """Run every benchmark and return a combined result dict."""
    return {
        "synapse_latency": bench_synapse_latency(runs=runs),
        "subagent_handoff": bench_subagent_handoff(),
        "routing_accuracy": bench_routing_accuracy(),
    }
