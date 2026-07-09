"""Prompt-surface token benchmark (v4.1 Evidence Reform open item).

Measures the UserPromptSubmit hook's injected context (additionalContext)
across a canonical prompt set, optionally comparing the working tree
against another git ref (extracted via `git archive`, no worktrees).

Token estimate: bytes / 4 — the same coarse heuristic the Synapse layers
use (`tokens_est`); good enough for a reduction ratio, not billing.

Usage:
    arka-py scripts/tools/prompt_surface_benchmark.py [--ref v4.0.2] [--json]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tarfile
import tempfile
from io import BytesIO
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

CANONICAL_PROMPTS: dict[str, str] = {
    "simple": "ok",
    "question": "como funciona o sync de projetos?",
    "code-modifying": "implementa auth no backend com testes",
    "department-routed": "cria uma campanha de marketing para o lançamento",
    "slash-command": "/dev feature user auth",
}

HOOK_REL = Path("config") / "hooks" / "user-prompt-submit.sh"


def _run_hook(tree: Path, prompt: str) -> int:
    """Return the additionalContext byte size the hook injects."""
    payload = json.dumps(
        {"prompt": prompt, "cwd": "/tmp", "session_id": "bench-1"}
    )
    proc = subprocess.run(
        ["bash", str(tree / HOOK_REL)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=30,
        env={
            "PATH": "/usr/bin:/bin:/usr/local/bin",
            "HOME": str(Path.home()),
            "ARKA_HOOK_FORCE_FALLBACK": "1",
        },
    )
    out = proc.stdout.strip()
    if not out:
        return 0
    try:
        context = json.loads(out).get("additionalContext", "")
    except json.JSONDecodeError:
        context = out
    return len(context.encode("utf-8"))


def _extract_ref(ref: str, dest: Path) -> Path:
    archive = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "archive", ref],
        capture_output=True,
        check=True,
        timeout=60,
    )
    with tarfile.open(fileobj=BytesIO(archive.stdout)) as tar:
        try:
            tar.extractall(dest, filter="data")
        except TypeError:  # Python < 3.12 has no filter param
            tar.extractall(dest)  # trusted archive: local git, no network
    return dest


def measure(tree: Path) -> dict[str, dict[str, int]]:
    results: dict[str, dict[str, int]] = {}
    for name, prompt in CANONICAL_PROMPTS.items():
        size = _run_hook(tree, prompt)
        results[name] = {"bytes": size, "tokens_est": size // 4}
    return results


def compare(ref: str) -> dict:
    with tempfile.TemporaryDirectory(prefix="arka-bench-") as tmp:
        old_tree = _extract_ref(ref, Path(tmp))
        before = measure(old_tree)
    after = measure(REPO_ROOT)
    total_before = sum(r["bytes"] for r in before.values())
    total_after = sum(r["bytes"] for r in after.values())
    reduction = (
        round(100 * (1 - total_after / total_before), 1)
        if total_before
        else 0.0
    )
    return {
        "ref": ref,
        "before": before,
        "after": after,
        "total_bytes_before": total_before,
        "total_bytes_after": total_after,
        "reduction_pct": reduction,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref", help="git ref to compare against")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    if args.ref:
        report = compare(args.ref)
    else:
        report = {"current": measure(REPO_ROOT)}

    if args.as_json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0

    if "current" in report:
        for name, row in report["current"].items():
            print(f"{name:20s} {row['bytes']:>6d} B  ~{row['tokens_est']} tok")
        return 0

    print(f"Prompt-surface benchmark: {report['ref']} -> HEAD")
    for name in CANONICAL_PROMPTS:
        b = report["before"][name]["bytes"]
        a = report["after"][name]["bytes"]
        print(f"{name:20s} {b:>6d} B -> {a:>6d} B")
    print(
        f"{'TOTAL':20s} {report['total_bytes_before']:>6d} B -> "
        f"{report['total_bytes_after']:>6d} B "
        f"({report['reduction_pct']}% reduction)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
