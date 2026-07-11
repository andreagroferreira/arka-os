"""CLI for the routing feedback aggregator (F1-B1).

Usage:
    python3 -m core.governance.routing_feedback_cli rebuild
    python3 -m core.governance.routing_feedback_cli show
"""

from __future__ import annotations

import sys

from core.governance.routing_feedback import load_scores, rebuild, scores_path


def _show() -> int:
    scores = load_scores()
    if scores is None:
        print(f"no routing scores at {scores_path()} — run: rebuild")
        return 1
    print(f"routing scores @ {scores.computed_at} (window {scores.window_days}d)")
    print(f"sources: {', '.join(scores.sources)}")
    for score in scores.scores:
        blockers = ", ".join(score.top_blocker_patterns) or "-"
        print(
            f"  {score.department}: {score.approvals}/{score.samples} approved"
            f" (smoothed {score.smoothed_approval:.2f}),"
            f" judge {score.judge_passes}P/{score.judge_revises}R,"
            f" redos {score.redo_count}, top blockers: {blockers}"
        )
    if not scores.scores:
        print("  (no attributable verdicts in window)")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    command = args[0] if args else "show"
    if command == "rebuild":
        result = rebuild()
        print(f"rebuilt {scores_path()} — {len(result.scores)} department(s)")
        return 0
    if command == "show":
        return _show()
    print("usage: python3 -m core.governance.routing_feedback_cli rebuild|show")
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
