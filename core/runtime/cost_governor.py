"""CostGovernor — enforceable, opt-in budget caps over LLM cost telemetry.

Extends ADR-011 ("token budgets are informational, not restrictive")
WITHOUT revoking it: when no cap is configured in `~/.arkaos/config.json`
the governor always allows (advisory stance preserved). Operators opt in
via:

    {"budget": {"hardCapUsd": 20.0, "dailyCapUsd": 50.0, "hardDeny": false}}

- `budget.hardCapUsd`  — per-session cap (matched on `session_id`)
- `budget.dailyCapUsd` — cap over today's total spend
- `budget.hardDeny`    — when true, an exceeded cap DENIES (hook exit 2);
                          default false = WARN-only (never blocks)

Spend is read from `core.runtime.llm_cost_telemetry`: daily totals via
`summarise(period="today")`, session totals by summing that session's
rows (the summary's `by_session` list is top-10-capped, so a direct sum
is the correct per-session aggregate). Missing telemetry, missing config
or unparsable values NEVER block — the governor fails open.

CLI:  python -m core.runtime.cost_governor <session_id> [--json]
Exit: 0 allow / 3 deny.

ADR: docs/adr/2026-07-04-cost-governor.md
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from core.runtime.llm_cost_telemetry import read_entries, summarise


DEFAULT_CONFIG_PATH = Path.home() / ".arkaos" / "config.json"


@dataclass(frozen=True)
class GovernorDecision:
    """Outcome of one budget check."""

    allow: bool
    reason: str
    spent_usd: float
    cap_usd: float | None
    hard_deny: bool = False

    @property
    def exceeded(self) -> bool:
        return self.reason.endswith("cap-exceeded")

    def to_warning(self) -> str:
        """WARN string for hook additionalContext/stderr; "" when under cap."""
        if not self.exceeded or self.cap_usd is None:
            return ""
        return (
            f"[arka:warn] budget cap exceeded "
            f"(${self.spent_usd:.2f} of ${self.cap_usd:.2f}) — {self.reason}"
        )


# ─── Config ───────────────────────────────────────────────────────────


def _read_budget_config(config_path: Path | None) -> dict[str, Any]:
    path = config_path or DEFAULT_CONFIG_PATH
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    budget = data.get("budget")
    return budget if isinstance(budget, dict) else {}


def _as_cap(raw: Any) -> float | None:
    """Parse a cap value; absent/null/non-positive/invalid → no cap."""
    if raw is None:
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


# ─── Spend aggregation (fails open) ───────────────────────────────────


def _session_spend(session_id: str, telemetry_path: Path | None) -> float:
    total = 0.0
    for entry in read_entries(telemetry_path):
        if str(entry.get("session_id") or "") != session_id:
            continue
        cost = entry.get("estimated_cost_usd")
        if cost is None:
            continue
        try:
            total += float(cost)
        except (TypeError, ValueError):
            continue
    return total


def _today_spend(telemetry_path: Path | None) -> float:
    summary = summarise(period="today", path=telemetry_path)
    return float(summary.total_cost_usd or 0.0)


# ─── Public check ─────────────────────────────────────────────────────


def check(
    session_id: str,
    config_path: Path | None = None,
    telemetry_path: Path | None = None,
) -> GovernorDecision:
    """Evaluate the configured caps against recorded spend.

    No caps configured → allow ("no-cap"). Telemetry unreadable →
    allow ("telemetry-unavailable") — never block on missing data.
    Exceeded cap → allow with warning unless `budget.hardDeny` is true.
    """
    budget = _read_budget_config(config_path)
    session_cap = _as_cap(budget.get("hardCapUsd"))
    daily_cap = _as_cap(budget.get("dailyCapUsd"))
    hard_deny = bool(budget.get("hardDeny", False))
    if session_cap is None and daily_cap is None:
        return GovernorDecision(True, "no-cap", 0.0, None)

    try:
        session_spent = _session_spend(str(session_id or ""), telemetry_path)
        today_spent = _today_spend(telemetry_path)
    except Exception:  # noqa: BLE001 — fail open, per ADR
        return GovernorDecision(True, "telemetry-unavailable", 0.0, None)

    if session_cap is not None and session_spent > session_cap:
        return GovernorDecision(
            allow=not hard_deny, reason="session-cap-exceeded",
            spent_usd=round(session_spent, 6), cap_usd=session_cap,
            hard_deny=hard_deny,
        )
    if daily_cap is not None and today_spent > daily_cap:
        return GovernorDecision(
            allow=not hard_deny, reason="daily-cap-exceeded",
            spent_usd=round(today_spent, 6), cap_usd=daily_cap,
            hard_deny=hard_deny,
        )
    return GovernorDecision(
        allow=True, reason="under-cap",
        spent_usd=round(session_spent, 6),
        cap_usd=session_cap if session_cap is not None else daily_cap,
        hard_deny=hard_deny,
    )


# ─── CLI ──────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m core.runtime.cost_governor",
        description="Check session/daily budget caps. Exit 0 allow, 3 deny.",
    )
    parser.add_argument("session_id", help="session id to check")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    decision = check(args.session_id)
    if args.as_json:
        print(json.dumps(asdict(decision)))
    else:
        cap = f"${decision.cap_usd:.2f}" if decision.cap_usd is not None else "none"
        verdict = "ALLOW" if decision.allow else "DENY"
        print(
            f"{verdict} {decision.reason} "
            f"(spent ${decision.spent_usd:.2f}, cap {cap})"
        )
    return 0 if decision.allow else 3


if __name__ == "__main__":  # pragma: no cover — thin CLI shim
    raise SystemExit(main())
