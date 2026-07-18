"""Deterministic lint evidence at turn end (warn-only detached worker).

The Stop hook enqueues this module DETACHED (the ``turn_capture``
pattern) — none of this cost lands on the hook's 5s budget. The worker
scopes ``core.governance.evidence_checks`` to the files actually
changed (merge-base diff + working tree untracked), appends one JSONL
line per run to ``~/.arkaos/telemetry/stop-lint.jsonl`` and coalesces
repeat runs while the tree fingerprint is unchanged.

WARN mode only: results are telemetry plus an owner-only tmp-state
file; nothing blocks. Promotion to a blocking surface is gated on
clean telemetry (the frontend-gate rollout pattern, ADR
2026-04-17-binding-flow-enforcement).

Config (``~/.arkaos/config.json``):
    hooks.stopLint           absent/"warn" -> warn | false/"off" -> off
    hooks.stopLintTypecheck  true adds the typecheck check. Default
                             false: typecheck has no scoped mode in the
                             engine (a scoped mypy would silently weaken
                             the same check the Quality Gate runs), so
                             the project-wide run is opt-in.
Env kill-switch: ``ARKA_STOP_LINT=0``.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.governance.evidence_checks import (
    EvidenceReport,
    _diff_base,
    run_evidence_checks,
)
from core.shared.safe_session_id import safe_session_id
from core.shared.temp_paths import arkaos_temp_dir

TELEMETRY_PATH: Path = Path.home() / ".arkaos" / "telemetry" / "stop-lint.jsonl"
CONFIG_PATH: Path = Path.home() / ".arkaos" / "config.json"
_STATE_SUBDIR = "arkaos-stop-lint"
_RESULT_SUBDIR = "arkaos-stop-lint-result"
_GIT_TIMEOUT = 10
_SUMMARY_CHARS = 200


def mode(config_path: Path | None = None) -> str:
    """Resolve the stop-lint mode: ``"off"`` or ``"warn"`` (default)."""
    if os.environ.get("ARKA_STOP_LINT", "").strip() == "0":
        return "off"
    raw = _hooks_config(config_path).get("stopLint", "warn")
    if raw is False or (isinstance(raw, str) and raw.lower() == "off"):
        return "off"
    return "warn"


def _hooks_config(config_path: Path | None) -> dict[str, Any]:
    path = config_path or CONFIG_PATH
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    hooks = data.get("hooks") if isinstance(data, dict) else None
    return hooks if isinstance(hooks, dict) else {}


def _typecheck_enabled(config_path: Path | None) -> bool:
    return bool(_hooks_config(config_path).get("stopLintTypecheck", False))


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True,
            timeout=_GIT_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def changed_files(project_dir: Path) -> list[str]:
    """Repo-relative files changed vs the merge-base, plus untracked."""
    try:
        base = _diff_base(project_dir)
    except (OSError, subprocess.TimeoutExpired):
        base = None
    if base is None:
        return []
    out: list[str] = []
    diff = _git(["diff", "--name-only", base], project_dir)
    if diff is not None and diff.returncode == 0:
        out.extend(f.strip() for f in diff.stdout.splitlines() if f.strip())
    status = _git(["status", "--porcelain"], project_dir)
    if status is not None and status.returncode == 0:
        out.extend(
            line[3:].strip()
            for line in status.stdout.splitlines()
            if line.startswith("??") and line[3:].strip()
        )
    seen: set[str] = set()
    return [f for f in out if not (f in seen or seen.add(f))]


def _fingerprint(project_dir: Path) -> str | None:
    head = _git(["rev-parse", "HEAD"], project_dir)
    status = _git(["status", "--porcelain"], project_dir)
    if head is None or head.returncode != 0 or status is None:
        return None
    digest = hashlib.sha1()
    digest.update(head.stdout.strip().encode("utf-8"))
    # Porcelain alone only says WHICH files are dirty — editing an
    # already-dirty file leaves it unchanged. Fold in mtime+size so
    # content edits re-arm the worker.
    for line in sorted(status.stdout.splitlines()):
        digest.update(line.encode("utf-8", "replace"))
        digest.update(_stat_token(project_dir / line[3:].strip()))
    return digest.hexdigest()


def _stat_token(path: Path) -> bytes:
    try:
        st = path.stat()
    except OSError:
        return b"|gone"
    return f"|{st.st_mtime_ns}:{st.st_size}".encode("ascii")


def _state_file(project_dir: Path) -> Path:
    key = hashlib.sha1(
        str(project_dir.resolve()).encode("utf-8")
    ).hexdigest()[:16]
    return arkaos_temp_dir(_STATE_SUBDIR) / f"{key}.json"


def _seen_fingerprint(state_file: Path) -> str | None:
    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    value = data.get("fingerprint") if isinstance(data, dict) else None
    return value if isinstance(value, str) else None


def _remember_fingerprint(state_file: Path, fingerprint: str) -> None:
    prev_umask = os.umask(0o077)
    try:
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(
            json.dumps({"fingerprint": fingerprint}), encoding="utf-8"
        )
    except OSError:
        pass
    finally:
        os.umask(prev_umask)


def _check_fields(report: EvidenceReport) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for result in report.results:
        fields[f"{result.check}_ran"] = result.ran
        fields[f"{result.check}_passed"] = result.passed
        fields[f"{result.check}_command"] = result.command
        fields[f"{result.check}_summary"] = result.summary[:_SUMMARY_CHARS]
    return fields


def _run_checks(
    project_dir: Path, changed: list[str], config_path: Path | None,
) -> dict[str, Any]:
    if not changed:
        return {
            "overall": "skipped",
            "would_block": False,
            "skip_reason": "no-changed-files",
        }
    checks = ["lint"]
    if _typecheck_enabled(config_path):
        checks.append("typecheck")
    report = run_evidence_checks(
        project_dir, changed_files=changed, checks=checks
    )
    fields = _check_fields(report)
    fields["overall"] = report.overall
    fields["would_block"] = report.overall == "fail"
    return fields


def _append_telemetry(entry: dict[str, Any], telemetry_path: Path) -> None:
    try:
        telemetry_path.parent.mkdir(parents=True, exist_ok=True)
        with telemetry_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
    except OSError:
        pass


def _write_result_state(session_id: str, entry: dict[str, Any]) -> None:
    sid = safe_session_id(session_id)
    if not sid:
        return
    prev_umask = os.umask(0o077)
    try:
        result_dir = arkaos_temp_dir(_RESULT_SUBDIR)
        result_dir.mkdir(parents=True, exist_ok=True)
        (result_dir / f"{sid}.json").write_text(
            json.dumps(entry), encoding="utf-8"
        )
    except OSError:
        pass
    finally:
        os.umask(prev_umask)


def run(
    project_dir: Path,
    session_id: str = "",
    *,
    config_path: Path | None = None,
    telemetry_path: Path | None = None,
) -> int:
    """Run the scoped batch once per tree fingerprint; append telemetry."""
    project_dir = Path(project_dir)
    if mode(config_path) == "off" or not project_dir.is_dir():
        return 0
    fingerprint = _fingerprint(project_dir)
    state_file = _state_file(project_dir)
    if fingerprint is not None and fingerprint == _seen_fingerprint(state_file):
        return 0
    started = time.monotonic()
    changed = changed_files(project_dir)
    entry = _run_checks(project_dir, changed, config_path)
    entry.update(
        ts=datetime.now(UTC).isoformat(),
        session_id=session_id,
        project_dir=str(project_dir),
        event="stop-lint",
        mode="warn",
        changed_count=len(changed),
        duration_ms=round((time.monotonic() - started) * 1000),
    )
    _append_telemetry(entry, telemetry_path or TELEMETRY_PATH)
    _write_result_state(session_id, entry)
    if fingerprint is not None:
        _remember_fingerprint(state_file, fingerprint)
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI: ``python -m core.governance.stop_lint <project_dir> [sid]``."""
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        return 0
    try:
        return run(Path(args[0]), args[1] if len(args) > 1 else "")
    except Exception:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
