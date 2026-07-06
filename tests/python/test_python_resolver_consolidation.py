"""Locking test: one Python interpreter resolver, consumed everywhere.

ArkaOS runs on the ~/.arkaos/venv interpreter (it has pyyaml/pydantic). A
bare `python`/`python3` on PATH may lack those deps and silently degrade
every hook and gate — the failure that broke `/arka update` when the
session's `python` had no yaml.

The single source of truth is `config/hooks/_lib/arka_python.sh` (shell
side) mirroring `installer/python-resolver.js` (JS side), plus the
`bin/arka-py` shim that SKILL.md commands invoke. This test fails CI if a
hook, the state reader, or an agent-facing SKILL regresses to a bare
interpreter invocation.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_BASH = shutil.which("bash") or "/bin/bash"

# Shell files that must resolve Python through ARKA_PY, never bare.
_HOOK_GLOBS = ["config/hooks/*.sh"]
_EXTRA_SHELL = ["core/workflow/state_reader.sh"]

# The resolver library itself legitimately names candidate interpreters.
_RESOLVER_LIB = _ROOT / "config" / "hooks" / "_lib" / "arka_python.sh"

# Agent-facing / operational docs the orchestrator or operator executes
# verbatim. Explicit allow-list — archival records (CHANGELOG, docs/adr,
# docs/superpowers, dated plans) intentionally keep the bare `python -m`
# form and must NOT be matched here.
_SKILL_GLOBS = [
    "CLAUDE.md",
    "README.md",
    "arka/SKILL.md",
    "arka/skills/**/SKILL.md",
    "config/claude-agents/*.md",
    "departments/*/SKILL.md",
    "departments/**/skills/**/SKILL.md",
    "departments/**/skills/**/references/*.md",
    "wiki/*.md",
]

# A line that RUNS python as an interpreter: `python -c`, `python3 -m`,
# `| python3`, `python3 "...".py`, heredoc `python3 - <<`. Case-sensitive
# lowercase, so PYTHONPATH / ARKAOS_PYTHON never match. A leading boundary
# that is not word/path/quote char avoids `arka_python`, `.../bin/python`.
_BARE_PY = re.compile(r'(?:^|[^\w./"$-])python3?(?:\s|$|["\'])')


def _iter_files(globs):
    for pattern in globs:
        yield from _ROOT.glob(pattern)


def _is_code_comment(line: str) -> bool:
    return line.lstrip().startswith("#")


def test_shared_resolver_exists_and_exports_arka_py():
    assert _RESOLVER_LIB.exists(), "config/hooks/_lib/arka_python.sh missing"
    body = _RESOLVER_LIB.read_text(encoding="utf-8")
    assert "arka_resolve_python()" in body, "resolver function not defined"
    assert "export ARKA_PY" in body, "resolver must export ARKA_PY"


def test_arka_py_shim_exists_and_is_executable():
    shim = _ROOT / "bin" / "arka-py"
    assert shim.exists(), "bin/arka-py shim missing"
    assert os.access(shim, os.X_OK), "bin/arka-py must be executable"
    body = shim.read_text(encoding="utf-8")
    assert "arka_python.sh" in body, "shim must source the shared resolver"


def test_hooks_never_invoke_bare_python():
    offenders: list[str] = []
    files = list(_iter_files(_HOOK_GLOBS)) + [_ROOT / p for p in _EXTRA_SHELL]
    for path in files:
        if not path.exists() or path.resolve() == _RESOLVER_LIB.resolve():
            continue
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if _is_code_comment(line):
                continue
            if "ARKA_PY" in line or "arka_resolve_python" in line:
                continue
            if _BARE_PY.search(line):
                offenders.append(f"{path.relative_to(_ROOT)}:{n}: {line.strip()}")
    assert not offenders, (
        "Bare python invocation in a hook — route through $ARKA_PY "
        "(source config/hooks/_lib/arka_python.sh):\n" + "\n".join(offenders)
    )


def test_agent_facing_skills_use_arka_py_not_bare_python():
    offenders: list[str] = []
    pat = re.compile(r'(?:^|[^\w./-])python3? -m core')
    for path in _iter_files(_SKILL_GLOBS):
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if pat.search(line):
                offenders.append(f"{path.relative_to(_ROOT)}:{n}: {line.strip()}")
    assert not offenders, (
        "Agent-facing SKILL invokes a bare `python -m core` — use "
        "`~/.arkaos/bin/arka-py -m core...` so the agent hits the ArkaOS "
        "interpreter:\n" + "\n".join(offenders)
    )


# Governance / operator-facing config that instructs how to run the core CLIs.
# constitution.yaml is the highest-authority live doc — every NON-NEGOTIABLE
# rule defers to it, so a bare-python invocation there (e.g. the Quality Gate's
# own evidence engine) is the worst place for the failure mode to survive.
_GOVERNANCE_GLOBS = [
    "config/constitution.yaml",
    "docs/examples/*.yaml",
    "scripts/**/*.py",
]


def test_governance_and_scripts_use_arka_py_not_bare_python():
    offenders: list[str] = []
    pat = re.compile(r'(?:^|[^\w./-])python3? -m core')
    for path in _iter_files(_GOVERNANCE_GLOBS):
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if pat.search(line):
                offenders.append(f"{path.relative_to(_ROOT)}:{n}: {line.strip()}")
    assert not offenders, (
        "Governance/operator instruction invokes a bare `python -m core` — use "
        "`~/.arkaos/bin/arka-py -m core...`:\n" + "\n".join(offenders)
    )


# ── set -e regression (blocker: bash 3.2.57 aborted mid-source) ───────────

def test_resolver_assignment_is_guarded_against_errexit():
    """The ARKA_PY assignment must carry `|| true`. arka_resolve_python
    returns 1 on the last-resort fallback, and under `set -e` a failing
    command substitution in an assignment aborts the sourcing file — a
    silent crash in the exact degraded path this resolver exists to handle.
    """
    body = _RESOLVER_LIB.read_text(encoding="utf-8")
    assert re.search(r'ARKA_PY="\$\(arka_resolve_python\)"\s*\|\|\s*true', body), (
        "arka_python.sh must guard: ARKA_PY=\"$(arka_resolve_python)\" || true"
    )


@pytest.mark.skipif(not Path(_BASH).exists(), reason="bash unavailable")
def test_sourcing_resolver_survives_errexit():
    """Sourcing the resolver under `set -euo pipefail` must always reach past
    the source line, whether resolution succeeds or hits the return-1
    fallback. This is the runtime check the static grep could not make."""
    script = f'set -euo pipefail; . "{_RESOLVER_LIB}"; echo "REACHED:${{ARKA_PY}}"'
    # Fake HOME forces the no-venv path so the fallback branch is exercised.
    result = subprocess.run(
        [_BASH, "-c", script],
        capture_output=True, text=True,
        env={"HOME": "/nonexistent-arka-resolver-test", "PATH": os.environ.get("PATH", "/usr/bin:/bin")},
    )
    assert result.returncode == 0, f"source aborted under set -e: {result.stderr}"
    assert "REACHED:" in result.stdout


# ── Windows parity ────────────────────────────────────────────────────────

def test_windows_shim_and_resolver_exist():
    for rel in ("config/hooks/_lib/arka_python.ps1", "bin/arka-py.ps1", "bin/arka-py.cmd"):
        assert (_ROOT / rel).exists(), f"missing Windows counterpart: {rel}"


# ── npm packaging (v4.3.2 regression: shims never reached npm installs) ──
# package.json `files` only shipped `bin/arkaos`, so the installer's
# existsSync() on bin/arka-py* and bin/arka-claude* silently skipped the
# shim deploy on every published install — the exact multi-user failure
# the resolver consolidation exists to fix.

_REQUIRED_IN_TARBALL = [
    "bin/arka-py",
    "bin/arka-py.ps1",
    "bin/arka-py.cmd",
    "bin/arka-claude",
    "bin/arka-claude.ps1",
    "bin/arka-claude.cmd",
    "config/hooks/_lib/arka_python.sh",
    "config/hooks/_lib/arka_python.ps1",
]


def _npm_files_cover(rel: str, entries: list[str]) -> bool:
    for entry in entries:
        clean = entry.rstrip("/")
        if rel == clean or rel.startswith(clean + "/"):
            return True
    return False


def test_npm_files_whitelist_ships_shims_and_resolver():
    pkg = json.loads((_ROOT / "package.json").read_text(encoding="utf-8"))
    entries = pkg.get("files", [])
    missing = [r for r in _REQUIRED_IN_TARBALL if not _npm_files_cover(r, entries)]
    assert not missing, (
        "package.json `files` does not ship interpreter shims/resolver — "
        "npm installs silently skip the shim deploy:\n" + "\n".join(missing)
    )


def test_update_flow_deploys_hook_lib():
    """Both installer flows (fresh install and update) must deploy
    config/hooks/_lib/ through the single shared helper, or updated
    installs keep hooks that source a resolver which was never deployed
    to ~/.arkaos/config/hooks/_lib/ — the v4.3.2 drift regression."""
    helper = (_ROOT / "installer" / "hook-lib.js").read_text(encoding="utf-8")
    assert re.search(
        r"cpSync\(\s*srcLibDir\s*,\s*destLibDir\s*,\s*\{\s*recursive:\s*true", helper
    ), "installer/hook-lib.js must copy _lib recursively (cpSync srcLibDir -> destLibDir)"
    for flow in ("update.js", "index.js"):
        body = (_ROOT / "installer" / flow).read_text(encoding="utf-8")
        assert re.search(r"\bcopyHookLib\(", body), (
            f"installer/{flow} does not call copyHookLib() — the shared "
            "resolver does not reach ~/.arkaos on that flow"
        )


def test_windows_flow_hooks_use_shared_resolver():
    """pre-tool-use.ps1 / stop.ps1 must resolve through the shared PS resolver,
    not a bare `Get-Command python3` (which ignores the venv and skips the
    yaml check) — the same regression the Unix side eliminates."""
    offenders: list[str] = []
    for rel in ("config/hooks/pre-tool-use.ps1", "config/hooks/stop.ps1"):
        path = _ROOT / rel
        if not path.exists():
            continue
        body = path.read_text(encoding="utf-8")
        if "arka_python.ps1" not in body:
            offenders.append(f"{rel}: does not source _lib/arka_python.ps1")
        if re.search(r"Get-Command python3 -ErrorAction", body):
            offenders.append(f"{rel}: still resolves bare python3 first")
    assert not offenders, "\n".join(offenders)
