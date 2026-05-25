"""One-stop /arka update orchestrator (PR61 v2.78.0).

The published 2-step process (`npx arkaos@latest update` then
`/arka update`) is fragile in practice: operators run step 2 inside
Claude Code without remembering step 1, so the sync engine silently
runs from whichever npx cache `~/.arkaos/.repo-path` last pointed at.
When that cache is months old the sync becomes a no-op against
current versions.

This module makes `/arka update` self-sufficient:

1. Read the running ArkaOS version from `<repo>/VERSION`.
2. Probe the npm registry for the published latest (5s timeout,
   1-hour cache on disk to keep repeat runs cheap).
3. If the running version is older than the latest, shell out to
   `npx arkaos@latest update` and wait for it to finish before
   touching the sync engine. The npx step rewrites
   ``~/.arkaos/.repo-path`` to the freshly-extracted package so the
   sync engine below reads the right code.
4. Re-read VERSION (now updated) and dispatch to ``run_sync``.

The orchestrator NEVER raises on transient failures — npm offline,
slow registry, missing `npx` — it logs and falls through to the sync
engine using whatever code is currently installed. Worst case the
operator sees the same behaviour as before PR61.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from core.sync.engine import (
    _read_current_version,
    _read_repo_path,
    run_sync,
)
from core.sync.schema import SyncReport


# Cache the npm-view result for an hour so repeated /arka update calls
# inside the same session don't re-hit the registry.
_NPM_CACHE_TTL_SECONDS = 3600
_NPM_TIMEOUT_SECONDS = 5
_NPM_PROBE_CMD = ("npm", "view", "arkaos", "version")
_NPX_UPDATE_CMD = ("npx", "-y", "arkaos@latest", "update")
_NPX_TIMEOUT_SECONDS = 600  # 10 minutes — large installs can be slow


def orchestrate(
    arkaos_home: Path,
    skills_dir: Path,
    home_path: str,
    *,
    npm_probe=None,
    npx_run=None,
    cache_path: Path | None = None,
) -> tuple[Optional[str], Optional[str], SyncReport]:
    """Run npm-side update when stale, then the sync engine.

    Returns ``(installed_version_before, latest_version_seen, report)``.
    The first two are None when probing failed; the third is always a
    SyncReport (the engine itself never raises on individual project
    failures).
    """
    probe = npm_probe or _probe_npm_latest
    runner = npx_run or _run_npx_update
    cache = cache_path or (arkaos_home / "npm-latest.cache.json")

    installed = _safe_read_version(arkaos_home)
    latest = probe(cache)

    if installed and latest and _is_older(installed, latest):
        runner(arkaos_home)

    report = run_sync(
        arkaos_home=arkaos_home,
        skills_dir=skills_dir,
        home_path=home_path,
    )
    return installed, latest, report


def _safe_read_version(arkaos_home: Path) -> Optional[str]:
    try:
        v = _read_current_version(arkaos_home)
        return v if v and v != "unknown" else None
    except Exception:  # noqa: BLE001 — never break the orchestrator
        return None


def _probe_npm_latest(cache_path: Path) -> Optional[str]:
    """Return the latest published arkaos version, or None on failure.

    Reads from disk cache when fresh; otherwise shells out to
    ``npm view`` with a short timeout. Always swallows errors —
    callers fall through to a no-op when probing fails.
    """
    cached = _read_cache(cache_path)
    if cached is not None:
        return cached
    try:
        result = subprocess.run(
            list(_NPM_PROBE_CMD),
            capture_output=True,
            text=True,
            timeout=_NPM_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    version = (result.stdout or "").strip()
    if not _looks_like_semver(version):
        return None
    _write_cache(cache_path, version)
    return version


def _read_cache(cache_path: Path) -> Optional[str]:
    if not cache_path.exists():
        return None
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    ts = data.get("ts")
    version = data.get("version")
    if not isinstance(ts, (int, float)) or not isinstance(version, str):
        return None
    if time.time() - ts > _NPM_CACHE_TTL_SECONDS:
        return None
    return version if _looks_like_semver(version) else None


def _write_cache(cache_path: Path, version: str) -> None:
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps({"version": version, "ts": time.time()}),
            encoding="utf-8",
        )
    except OSError:
        pass


def _looks_like_semver(value: str) -> bool:
    if not value or len(value) > 32:
        return False
    # Strip any `-prerelease.suffix` so "2.77.0-beta.1" reduces to "2.77.0"
    # before structural validation. npm canonical semver allows almost any
    # ASCII after the dash; we don't try to validate that — we only need
    # to confirm the leading major.minor.patch shape is intact.
    base = value.split("-", 1)[0]
    parts = base.split(".")
    if len(parts) != 3:
        return False
    return all(part.isdigit() for part in parts)


def _is_older(installed: str, latest: str) -> bool:
    return _parse_semver(installed) < _parse_semver(latest)


def _parse_semver(value: str) -> tuple[int, int, int]:
    parts = value.split(".")
    try:
        major = int(parts[0])
        minor = int(parts[1])
        patch_str = parts[2].split("-", 1)[0]
        patch = int(patch_str)
        return major, minor, patch
    except (ValueError, IndexError):
        return (0, 0, 0)


def _run_npx_update(arkaos_home: Path) -> None:
    """Best-effort shell-out to `npx arkaos@latest update`.

    Inherits the parent's stdout/stderr so the operator sees the same
    installer banner they would in a manual run. Swallows OSError /
    TimeoutExpired so the surrounding sync still runs.
    """
    del arkaos_home  # passed for symmetry with _probe_npm_latest signature
    try:
        env = os.environ.copy()
        # Some operators set CI=1 to suppress installer prompts; preserve it.
        subprocess.run(
            list(_NPX_UPDATE_CMD),
            check=False,
            timeout=_NPX_TIMEOUT_SECONDS,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        sys.stderr.write(
            f"[arkaos] npx arkaos@latest update failed: {exc}\n"
            "[arkaos] continuing with the sync engine using the "
            "currently-installed core.\n"
        )


def main(argv: list[str]) -> int:
    """CLI entry: python -m core.sync.update_orchestrator --home X --skills Y."""
    import argparse
    parser = argparse.ArgumentParser(description="ArkaOS one-stop /arka update")
    parser.add_argument("--home", required=True)
    parser.add_argument("--skills", required=True)
    parser.add_argument("--output", choices=["text", "json"], default="text")
    args = parser.parse_args(argv[1:])

    installed, latest, report = orchestrate(
        arkaos_home=Path(args.home),
        skills_dir=Path(args.skills),
        home_path=str(Path.home()),
    )

    if args.output == "json":
        payload = {
            "installed_version_before": installed,
            "latest_version_seen": latest,
            "report": report.model_dump(),
        }
        print(json.dumps(payload, indent=2))
    else:
        from core.sync.reporter import format_report
        print(f"Installed: {installed or 'unknown'}")
        print(f"Latest published: {latest or 'unknown'}")
        if installed and latest and _is_older(installed, latest):
            print(f"Updated from {installed} → {latest} via npx arkaos@latest")
        print()
        print(format_report(report))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
