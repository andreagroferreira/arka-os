"""QG and gate-judge verdicts as free eval labels.

Every Quality Gate review produces a structured ``QGVerdict`` and every
gate judge (Interaction Reform PR2) a ``JudgeVerdict``. Persisting them
turns each review into a labeled example — the training/eval signal the
E2E audit called "labels gratuitos". Two corpora, one module:
``qg-verdicts.jsonl`` and ``judge-verdicts.jsonl``. Append-only JSONL,
same conventions as the other ``~/.arkaos/telemetry`` writers: never
raises, fcntl advisory lock via ``llm_cost_telemetry._locked_append``
(reviews run as parallel subagents and verdict lines far exceed
atomic-write sizes, so unlocked appends could interleave and corrupt
the corpus), ``ARKA_QG_LABELS_PATH`` / ``ARKA_JUDGE_LABELS_PATH``
overrides for tests.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.governance.judge import JudgeVerdict
from core.governance.qg_verdict import QGVerdict
from core.runtime.llm_cost_telemetry import _locked_append

DEFAULT_LABELS_PATH = (
    Path.home() / ".arkaos" / "telemetry" / "qg-verdicts.jsonl"
)
DEFAULT_JUDGE_LABELS_PATH = (
    Path.home() / ".arkaos" / "telemetry" / "judge-verdicts.jsonl"
)


def _labels_path() -> Path:
    override = os.environ.get("ARKA_QG_LABELS_PATH", "").strip()
    return Path(override) if override else DEFAULT_LABELS_PATH


def _judge_labels_path() -> Path:
    override = os.environ.get("ARKA_JUDGE_LABELS_PATH", "").strip()
    return Path(override) if override else DEFAULT_JUDGE_LABELS_PATH


def record_verdict_label(
    verdict: QGVerdict,
    deliverable: str = "",
    department: str = "",
    eval_task_id: str = "",
    session_id: str = "",
) -> None:
    """Append one labeled QG example. Never raises (telemetry contract)."""
    try:
        entry: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "deliverable": str(deliverable or ""),
            "department": str(department or ""),
            "eval_task_id": str(eval_task_id or ""),
            "session_id": str(session_id or ""),
            **verdict.model_dump(),
        }
        with _locked_append(_labels_path()) as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001 — telemetry must never raise
        return


def record_judge_label(
    verdict: JudgeVerdict,
    deliverable: str = "",
    department: str = "",
    session_id: str = "",
) -> None:
    """Append one labeled gate-judge example. Never raises."""
    try:
        entry: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "deliverable": str(deliverable or ""),
            "department": str(department or ""),
            "session_id": str(session_id or ""),
            **verdict.model_dump(),
        }
        with _locked_append(_judge_labels_path()) as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001 — telemetry must never raise
        return


def load_verdict_labels(path: Path | None = None) -> list[dict[str, Any]]:
    """Read all labeled QG examples; malformed lines are skipped."""
    return _load_jsonl(path or _labels_path())


def load_judge_labels(path: Path | None = None) -> list[dict[str, Any]]:
    """Read all labeled gate-judge examples; malformed lines are skipped."""
    return _load_jsonl(path or _judge_labels_path())


def _load_jsonl(target: Path) -> list[dict[str, Any]]:
    if not target.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in target.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out
