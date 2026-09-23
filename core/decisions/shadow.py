"""Shadow mode: Jev is asked off the hot path, the heuristic acts.

:func:`spawn_shadow` spools the call (0600, capped at
:data:`SPOOL_MAX_PENDING`) and detaches a worker — same pattern as
``core/hooks/stop.py`` (``Popen(start_new_session=True)``), so the hook
pays zero network latency. The worker (:func:`main`) asks Jev with
a 5 s ceiling, records telemetry with ``agree``, deletes its spool in
``finally`` and sweeps spools older than an hour.
"""

from __future__ import annotations

import contextlib
import json
import os
import subprocess
import sys
import time
import uuid
from collections.abc import Sequence
from pathlib import Path

from core.decisions.backoff import ensure_private_dir
from core.decisions.models import State
from core.decisions.paths import repo_root, spool_dir
from core.decisions.site import SiteCall

SPOOL_MAX_PENDING = 8
STALE_SPOOL_S = 3600.0
SHADOW_TIMEOUT_S = 5.0


def spawn_shadow(calls: Sequence[SiteCall], state: State, session_id: str) -> bool:
    """Spool and detach; False when the spool is full or anything fails."""
    if not calls:
        return False
    try:
        spool = spool_dir()
        # The spool holds the state in clear for seconds: every directory
        # created on the way is 0700, the spool itself always (QG r1 m3).
        ensure_private_dir(spool)
        os.chmod(spool, 0o700)
        # Workers sweep on exit, but a killed worker leaves its spool
        # behind: without this, 8 orphans disable shadow mode for good.
        sweep_stale()
        if len(list(spool.glob("*.json"))) >= SPOOL_MAX_PENDING:
            return False
        path = _write_spool(spool, calls, state, session_id)
    except (OSError, TypeError, ValueError):
        return False
    return _launch(path)


def _write_spool(spool: Path, calls: Sequence[SiteCall], state: State, session_id: str) -> Path:
    payload = {
        "session_id": session_id,
        "state": state,
        "sites": [{"name": c.site.name, "heuristic": c.heuristic} for c in calls],
        "created": time.time(),
    }
    data = json.dumps(payload, ensure_ascii=False, default=str)
    path = spool / f"{uuid.uuid4().hex}.json"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(data)
    return path


def _launch(path: Path) -> bool:
    try:
        subprocess.Popen(
            [sys.executable, "-m", "core.decisions.shadow", str(path)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env={**os.environ, "PYTHONPATH": str(repo_root())},
            start_new_session=True,
        )
    except (OSError, ValueError):
        with contextlib.suppress(OSError):
            path.unlink()
        return False
    return True


def _in_spool(path: Path) -> bool:
    try:
        return path.resolve().parent == spool_dir().resolve()
    except OSError:
        return False


def _run_spool(path: Path) -> None:
    from core.decisions.config import load_decisions_config
    from core.decisions.engine import run_and_record
    from core.decisions.registry import SITES
    from core.decisions.transport import configured_model, resolve_transport

    payload = json.loads(path.read_text(encoding="utf-8"))
    calls = [
        SiteCall(SITES[s["name"]], s.get("heuristic"))
        for s in payload.get("sites", []) if s.get("name") in SITES
    ]
    cfg = load_decisions_config()
    transport = resolve_transport(cfg, model=configured_model())
    if not calls or transport is None:
        return
    run_and_record(
        calls, payload.get("state", ""), modes={c.site.name: "shadow" for c in calls},
        cfg=cfg, transport=transport, session_id=str(payload.get("session_id", "")),
        timeout_s=SHADOW_TIMEOUT_S,
    )


def sweep_stale(now: float | None = None) -> int:
    """Delete spools older than :data:`STALE_SPOOL_S`; count removed."""
    ref = time.time() if now is None else now
    removed = 0
    for spool in spool_dir().glob("*.json"):
        with contextlib.suppress(OSError):
            if ref - spool.stat().st_mtime > STALE_SPOOL_S:
                spool.unlink()
                removed += 1
    return removed


def main(argv: list[str] | None = None) -> int:
    """Worker entry: ``python -m core.decisions.shadow <spool.json>``."""
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1:
        return 2
    path = Path(args[0])
    if not _in_spool(path):
        return 2
    try:
        _run_spool(path)
    except Exception:
        pass  # detached worker: nothing to report to
    finally:
        with contextlib.suppress(OSError):
            path.unlink()
        sweep_stale()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
