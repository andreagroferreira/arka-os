"""core.egress.audit rotation — capped, one kept generation, never a gate.

Security review PR2, finding 8: ``audit.jsonl`` grew without bound. The
audit is fail-closed (no audit, no egress), so rotation must be pure
housekeeping: a rotation that fails or raises may never turn an ALLOW
into a denial. Fixture client identifiers are synthetic.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from core.egress import audit
from core.egress.policy import evaluate

NOW = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)
REPO = Path(__file__).resolve().parents[2]
CAP = 1024


@pytest.fixture
def small_cap(monkeypatch):
    monkeypatch.setattr(audit, "AUDIT_MAX_BYTES", CAP)
    return CAP


def _prefill(path: Path, size: int) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    total = 0
    n = 0
    while total <= size:
        line = json.dumps({"prefill": n, "pad": "p" * 80}) + "\n"
        lines.append(line)
        total += len(line)
        n += 1
    data = "".join(lines).encode("utf-8")
    path.write_bytes(data)
    os.chmod(path, 0o600)
    return data


def _lines(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]


def _evaluate(tmp_path: Path, text: str = "harmless text"):
    cfg = tmp_path / "redaction-clients.json"
    cfg.write_text(json.dumps({"clients": ["acme-alpha"]}), encoding="utf-8")
    return evaluate(
        text, "notebooklm", config_path=cfg, home=tmp_path / "home",
        allowlist_path=tmp_path / "allow.json",
        audit_path=tmp_path / "egress" / "audit.jsonl", now=NOW,
    )


def test_cap_is_ten_megabytes():
    assert audit.AUDIT_MAX_BYTES == 10 * 1024 * 1024


def test_oversized_file_rotates_exactly_once(tmp_path, small_cap):
    # Kills: dropping the rotation call (no .1, the prefill stays current).
    path = tmp_path / "egress" / "audit.jsonl"
    prefill = _prefill(path, small_cap)
    assert audit.record({"n": 1}, path, NOW)
    assert audit.record({"n": 2}, path, NOW)
    kept = path.with_name("audit.jsonl.1")
    assert kept.read_bytes() == prefill
    assert [e["n"] for e in _lines(path)] == [1, 2]
    assert all("rotation" not in e for e in _lines(path))


def test_under_cap_never_rotates(tmp_path, small_cap):
    path = tmp_path / "egress" / "audit.jsonl"
    for n in range(3):
        assert audit.record({"n": n}, path, NOW)
    assert not path.with_name("audit.jsonl.1").exists()
    assert len(_lines(path)) == 3


def test_rotated_and_fresh_files_stay_private(tmp_path, small_cap):
    path = tmp_path / "egress" / "audit.jsonl"
    _prefill(path, small_cap)
    assert audit.record({"n": 1}, path, NOW)
    for target in (path, path.with_name("audit.jsonl.1")):
        assert stat.S_IMODE(target.stat().st_mode) == 0o600


def test_rotation_crash_does_not_deny_egress(tmp_path, small_cap, monkeypatch):
    # Kills: calling rotate_if_oversized outside the suppress (the raise
    # reaches record's broad catch, record returns False, the ALLOW flips).
    def boom(*_a, **_k):
        raise RuntimeError("rotation exploded")

    monkeypatch.setattr(audit, "rotate_if_oversized", boom)
    path = tmp_path / "egress" / "audit.jsonl"
    _prefill(path, small_cap)
    decision = _evaluate(tmp_path)
    assert decision.allowed and decision.audited
    last = _lines(path)[-1]
    assert last["allowed"] is True
    assert last["rotation"] == audit.ROTATION_FAILED


def test_refused_rename_does_not_deny_egress(tmp_path, small_cap, monkeypatch):
    # The shared helper swallows the OSError; the size check notices.
    # Kills: dropping the post-rotation size check (no "rotation" marker).
    def refuse(*_a, **_k):
        raise PermissionError("read-only directory")

    monkeypatch.setattr(os, "replace", refuse)
    path = tmp_path / "egress" / "audit.jsonl"
    prefill = _prefill(path, small_cap)
    decision = _evaluate(tmp_path)
    assert decision.allowed and decision.audited
    assert path.read_bytes().startswith(prefill)  # kept writing in place
    assert _lines(path)[-1]["rotation"] == audit.ROTATION_FAILED
    assert not path.with_name("audit.jsonl.1").exists()


def test_rotation_failure_still_fails_closed_when_write_fails(
    tmp_path, small_cap, monkeypatch
):
    # Rotation leniency must not leak into the write: a refused append
    # still flips the ALLOW to denied.
    monkeypatch.setattr(audit, "rotate_if_oversized", lambda *a, **k: False)
    real_open = os.open

    def no_append(path, flags, *args):
        if str(path).endswith("audit.jsonl"):
            raise OSError("disk full")
        return real_open(path, flags, *args)

    monkeypatch.setattr(os, "open", no_append)
    decision = _evaluate(tmp_path)
    assert not decision.allowed
    assert [f.kind for f in decision.findings] == ["audit-unavailable"]


_CHILD = """
import sys, time
from pathlib import Path
from core.egress import audit
audit.AUDIT_MAX_BYTES = int(sys.argv[1])
path = Path(sys.argv[2])
tag = sys.argv[3]
go = path.with_name("go")
deadline = time.monotonic() + 30
while not go.exists() and time.monotonic() < deadline:
    time.sleep(0.001)
for n in range(int(sys.argv[4])):
    assert audit.record({"writer": tag, "n": n}, path)
"""


WRITERS = ("a", "b", "c", "d")


@pytest.mark.parametrize("trial", range(3))
def test_concurrent_processes_lose_no_line(tmp_path, trial):
    # Every writer is released at once onto the oversized file; the
    # shared flock lets one rotate and the others stand down. New lines
    # stay under the cap, so exactly one rotation is legitimate and
    # every line must survive (an unlocked rotator replaces .1 twice).
    cap, per_writer = 4096, 6
    path = tmp_path / f"t{trial}" / "audit.jsonl"
    prefill = _prefill(path, cap)
    procs = [
        subprocess.Popen(
            [sys.executable, "-c", _CHILD, str(cap), str(path), tag, str(per_writer)],
            cwd=REPO,
        )
        for tag in WRITERS
    ]
    path.with_name("go").touch()
    assert [p.wait(timeout=60) for p in procs] == [0] * len(WRITERS)
    kept = path.with_name("audit.jsonl.1")
    entries = _lines(kept) + _lines(path)
    written = sorted((e["writer"], e["n"]) for e in entries if "writer" in e)
    expected = sorted((t, n) for t in WRITERS for n in range(per_writer))
    assert written == expected
    assert kept.read_bytes().startswith(prefill)
    assert sum("prefill" in e for e in entries) == prefill.count(b"\n")
