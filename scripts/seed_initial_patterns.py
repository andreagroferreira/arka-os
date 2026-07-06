"""One-shot seeder for the ArkaOS Pattern Library.

Populates `~/.arkaos/patterns/cards.jsonl` with the four patterns
shipped in PR1–PR3.5 of the Squad Intelligence Upgrade so the library
starts with real day-1 data instead of waiting for the operator to
record patterns manually.

Idempotent: re-running replaces same-id entries (the recorder dedups).

Usage:
    python -m scripts.seed_initial_patterns
"""

from __future__ import annotations

from datetime import datetime, timezone

from core.knowledge.pattern_cards import PatternCard, record_pattern


def _ts(year: int, month: int, day: int) -> str:
    return datetime(year, month, day, tzinfo=timezone.utc).isoformat()


_INITIAL_PATTERNS: list[PatternCard] = [
    PatternCard(
        id="force-specialist-dispatch",
        name="Force Specialist Dispatch",
        feature_keywords=[
            "specialist", "dispatch", "ownership", "file-glob", "owner",
            "agent", "persona", "pretooluse", "hook", "enforcement",
        ],
        description=(
            "PreToolUse hook that blocks Tier-1 squad leads from writing "
            "to specialist-owned files unless they dispatch the specialist "
            "via the Agent tool first."
        ),
        stack=["python", "bash", "powershell", "hook", "constitution", "governance"],
        files=[
            "core/workflow/specialist_enforcer.py",
            "config/agent-ownership.yaml",
            "config/hooks/pre-tool-use.sh",
            "config/hooks/pre-tool-use.ps1",
        ],
        acceptance_criteria=[
            "BLOCK lead writes on specialist-owned files",
            "Bypass via [arka:specialist-bypass <reason>] (non-empty reason)",
            "Telemetry to ~/.arkaos/telemetry/specialist-dispatch.jsonl",
            "Path-traversal safe via safe_session_id",
            "Feature flag hooks.specialistEnforcement defaults off",
        ],
        edge_cases=[
            "Subagent transcripts isolated from parent — negative gate only",
            "Bypass marker scope strict: last assistant message only",
            "C-Suite + lead_allowed cross-cutting paths always pass",
        ],
        references=[
            "https://github.com/andreagroferreira/arka-os/pull/204",
            "docs/adr/2026-05-28-specialist-dispatch-subagent-blindspot.md",
        ],
        projects_using=["arkaos"],
        created_at=_ts(2026, 5, 28),
        last_updated=_ts(2026, 5, 28),
    ),
    PatternCard(
        id="dashboard-venv-doctor",
        name="Dashboard venv-doctor",
        feature_keywords=[
            "venv", "dashboard", "python", "broken", "symlink", "repair",
            "doctor", "homebrew", "rotation", "fail-fast",
        ],
        description=(
            "Detects broken venv symlinks (typical after Homebrew Python "
            "patch rotations) and auto-repairs via `python -m venv --clear`. "
            "Dashboard launcher scripts fail-fast with actionable remediation."
        ),
        stack=["nodejs", "bash", "powershell", "installer"],
        files=[
            "installer/python-resolver.js",
            "installer/doctor.js",
            "scripts/start-dashboard.sh",
            "scripts/start-dashboard.ps1",
        ],
        acceptance_criteria=[
            "lstat-based broken-symlink detection (existsSync follows links)",
            "--clear recreate + post-repair re-diagnose",
            "Dashboard never falls back to ambient python3",
            "npx arkaos doctor --fix auto-repairs in place",
        ],
        edge_cases=[
            "Homebrew patch-version rotation (3.13.X -> 3.13.Y)",
            "sqlite-vec optional with graceful degradation",
        ],
        references=[
            "https://github.com/andreagroferreira/arka-os/pull/205",
        ],
        projects_using=["arkaos"],
        created_at=_ts(2026, 5, 28),
        last_updated=_ts(2026, 5, 28),
    ),
    PatternCard(
        id="agent-experience-persistence",
        name="Agent Experience persistence (QG learning loop)",
        feature_keywords=[
            "experience", "learning", "loop", "qg", "rejected", "persistence",
            "memory", "agent", "quality-gate", "verdict",
        ],
        description=(
            "REJECTED Quality Gate verdicts persist as Experience records on "
            "the failing agent's log. Synapse layer L2.6 surfaces past "
            "lessons when the same agent is dispatched again."
        ),
        stack=["python", "synapse", "governance", "constitution", "jsonl"],
        files=[
            "core/governance/agent_experiences.py",
            "core/governance/cqo_experience_recorder.py",
            "core/synapse/agent_experiences_layer.py",
            "core/governance/agent_experiences_cli.py",
        ],
        acceptance_criteria=[
            "Append-only JSONL with path-safe agent_id (CWE-22)",
            "Verdict parser: APPROVED, REJECTED, UNKNOWN",
            "Blockers parsed with B/M/N labels (./:/ space separators)",
            "Multiple patterns surface in registry order (not first-match-wins)",
        ],
        edge_cases=[
            "Inline mid-paragraph blockers are NOT extracted (anchored regex)",
            "Pattern field is list[str] for multi-category failures",
        ],
        references=[
            "https://github.com/andreagroferreira/arka-os/pull/206",
        ],
        projects_using=["arkaos"],
        created_at=_ts(2026, 5, 28),
        last_updated=_ts(2026, 5, 28),
    ),
    PatternCard(
        id="qg-experience-loop-wiring",
        name="QG Experience Loop Wiring",
        feature_keywords=[
            "posttooluse", "hook", "auto-record", "wiring", "integration",
            "loop", "reviewing", "cqo",
        ],
        description=(
            "PostToolUse hook auto-detects Agent calls with subagent_type=cqo "
            "returning REJECTED, parses [arka:reviewing <agent_id>], invokes "
            "record_from_verdict. Synapse L2.6 registered in engine."
        ),
        stack=["bash", "python", "synapse", "hook"],
        files=[
            "config/hooks/post-tool-use.sh",
            "core/synapse/engine.py",
        ],
        acceptance_criteria=[
            "[arka:reviewing <agent_id>] marker in CQO dispatch prompt",
            "Auto-record on REJECTED verdict via PostToolUse hook",
            "Path-traversal-safe by double boundary (shell + Python)",
            "Never blocks the hook",
        ],
        edge_cases=[
            "subagent_type exact 'cqo' (no sub-reviewer variants yet)",
            "Idempotent: same output processed twice writes two records",
        ],
        references=[
            "https://github.com/andreagroferreira/arka-os/pull/207",
        ],
        projects_using=["arkaos"],
        created_at=_ts(2026, 5, 28),
        last_updated=_ts(2026, 5, 28),
    ),
]


def main() -> int:
    for card in _INITIAL_PATTERNS:
        record_pattern(card)
    print(f"Seeded {len(_INITIAL_PATTERNS)} pattern cards.")
    print("Inspect: ~/.arkaos/bin/arka-py -m core.knowledge.pattern_cards_cli list")
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys
    sys.exit(main())
