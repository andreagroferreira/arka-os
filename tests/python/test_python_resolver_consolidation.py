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
        env={
            "HOME": "/nonexistent-arka-resolver-test",
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        },
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


_NPM = shutil.which("npm")


# Bins deliberately kept OUT of the published tarball. Maintainer-only,
# not referenced by installer/ or any runtime path. Excluded by omission
# from the package.json `files` whitelist (npm's files array is the sole
# allow-list — .npmignore cannot trim a whitelisted set). Empty since the
# M2 consolidation retired bin/arka-registry-gen (the generator is now
# core/registry/generator.py, shipped with core/).
_TARBALL_BIN_DENYLIST: set[str] = set()


@pytest.mark.skipif(_NPM is None, reason="npm unavailable")
def test_npm_pack_ships_shims_and_omits_maintainer_tool():
    """Empirical tarball check (stronger than reading package.json): the
    real `npm pack` output must contain every interpreter shim/resolver
    and must omit the maintainer-only bins."""
    out = subprocess.run(
        [_NPM, "pack", "--dry-run", "--json"],
        cwd=_ROOT, capture_output=True, text=True, timeout=180,
    )
    assert out.returncode == 0, f"npm pack failed: {out.stderr}"
    files = {f["path"] for f in json.loads(out.stdout)[0]["files"]}
    missing = [r for r in _REQUIRED_IN_TARBALL if r not in files]
    assert not missing, "npm pack tarball missing shims/resolver:\n" + "\n".join(missing)
    for denied in _TARBALL_BIN_DENYLIST:
        assert denied not in files, (
            f"{denied} (maintainer-only) leaked into the published tarball — "
            "it must stay out of the package.json `files` whitelist"
        )


@pytest.mark.skipif(_NPM is None, reason="npm unavailable")
def test_npm_pack_ships_every_first_party_bin():
    """Guard against the #234 forgotten-shim class the explicit `files`
    enumeration reintroduces: every tracked bin/ file except the known
    maintainer-only denylist MUST reach the tarball. A new first-party
    shim added to bin/ without a matching `files` entry fails here."""
    ls = subprocess.run(
        ["git", "ls-files", "bin/"],
        cwd=_ROOT, capture_output=True, text=True, timeout=30,
    )
    assert ls.returncode == 0, f"git ls-files failed: {ls.stderr}"
    tracked = ls.stdout.split()
    assert tracked, "git ls-files bin/ returned nothing — guard would be vacuous"
    expected = {b for b in tracked if b and b not in _TARBALL_BIN_DENYLIST}
    out = subprocess.run(
        [_NPM, "pack", "--dry-run", "--json"],
        cwd=_ROOT, capture_output=True, text=True, timeout=180,
    )
    assert out.returncode == 0, f"npm pack failed: {out.stderr}"
    files = {f["path"] for f in json.loads(out.stdout)[0]["files"]}
    missing = sorted(expected - files)
    assert not missing, (
        "first-party bin(s) missing from the tarball — add them to the "
        "package.json `files` whitelist (or the denylist if maintainer-only):\n"
        + "\n".join(missing)
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


def test_ps1_interpreter_probes_skip_store_aliases():
    r"""No PowerShell hook may select an interpreter out of WindowsApps.

    %LOCALAPPDATA%\Microsoft\WindowsApps holds zero-length App Execution
    Aliases. On a default Windows install `python3.exe` there is the Python
    install manager, and *running* it downloads and installs a full CPython
    into the current working directory. A hook's cwd is the user's project,
    so one probe drops a ~3700-file Python/ tree and a
    python_install_<timestamp>.log into their repo — reproduced on Windows
    10 with install manager 26.3.

    Every candidate list that feeds Get-Command must therefore exclude the
    alias directory, and must try `python` before `python3` (on Windows the
    former is the real interpreter and the latter usually just the alias).
    """
    offenders: list[str] = []
    # Both PowerShell spellings of a candidate list: the bare comma form
    # (`in 'python','py'`) and the array form (`in @("python", "py")`).
    # arka_python.ps1 uses the latter, and it is the probe that actually
    # *executes* each candidate, so missing it would defeat the test.
    candidate_list = re.compile(
        r"foreach\s*\(\s*\$\w+\s+in\s+@?\(?\s*"
        r"((?:[\"'](?:python3?|py)[\"']\s*,?\s*)+)\)?",
        re.IGNORECASE,
    )
    for path in sorted((_ROOT / "config" / "hooks").rglob("*.ps1")):
        body = path.read_text(encoding="utf-8")
        rel = path.relative_to(_ROOT).as_posix()
        for match in candidate_list.finditer(body):
            names = re.findall(r"[\"']([^\"']+)[\"']", match.group(1))
            if names and names[0] == "python3":
                offenders.append(
                    f"{rel}: probes 'python3' first — on Windows that is the "
                    "Store alias, not an interpreter"
                )
            # The guard must apply to the command this loop resolves: either
            # inline in the block, or via the shared Test-StoreAlias helper
            # (arka_python.ps1 extracts it, which is the better shape and
            # must not be penalised by an in-block-only check).
            window = body[match.start():match.start() + 600]
            if "WindowsApps" not in window and "Test-StoreAlias" not in window:
                offenders.append(
                    f"{rel}: interpreter probe does not exclude "
                    "\\Microsoft\\WindowsApps\\; running a Store alias "
                    "installs CPython into the hook's cwd"
                )
    assert not offenders, "\n".join(offenders)


def test_shell_resolver_skips_store_aliases_and_knows_windows_venv():
    """The bash twin has the same exposure under Git Bash on Windows.

    `command -v python3` there resolves to the WindowsApps alias exactly as
    Get-Command does, and arka_python.sh *runs* every candidate to check
    `import yaml`. Worse, its venv candidates were bin/python only, so on
    Windows the venv never matched and the PATH probe was always reached.
    """
    body = _RESOLVER_LIB.read_text(encoding="utf-8")
    offenders: list[str] = []

    if "Scripts/python.exe" not in body:
        offenders.append(
            "arka_python.sh does not know the Windows venv layout "
            "(Scripts/python.exe), so Git Bash always falls through to the "
            "PATH probe"
        )
    if "indows" not in body or "pps" not in body:
        offenders.append(
            "arka_python.sh does not filter Microsoft Store App Execution "
            "Aliases; running one installs CPython into the hook's cwd"
        )
    # `python` must stay behind python3 and the absolute paths: promoting it
    # would change which interpreter POSIX boxes resolve to.
    probe = re.search(r"for cand in ((?:[^\n;]*?python[^\n;]*?))(?:;|\n)", body)
    if probe:
        names = probe.group(1).split()
        if names and names[0] == "python":
            offenders.append(
                "arka_python.sh probes bare `python` first; on POSIX that can "
                "select Python 2 where python3 is meant"
            )
    assert not offenders, "\n".join(offenders)


# ── The last resort: the branch the alias filter did not cover ────────────
#
# Both twins filtered the Store alias out of the PROBE and then handed it
# straight back from the fallback -- .sh returned the bare name "python",
# .ps1 returned the literal string "python". The two tests above read the
# candidate LISTS only, so that path was invisible to them and the defect
# the PR exists to prevent shipped inside the fix. These execute it.
#
# Why the fallback must return NOTHING rather than a name: every caller
# gates on the value's existence -- `command -v "$ARKA_PY"` in bash,
# `-and $env:ARKA_PY` in PowerShell -- and an alias stub PASSES both. The
# file is real; it is the Python install manager, not an interpreter. Only
# an empty value degrades the hook instead of downloading a CPython into
# whatever directory the hook happened to run in.

_PS_LIB = _ROOT / "config" / "hooks" / "_lib" / "arka_python.ps1"
_PWSH = shutil.which("pwsh") or shutil.which("powershell")


def _winsim(tmp_path: Path, alias_names: tuple[str, ...], real_names: tuple[str, ...]):
    """Build a fake PATH: an alias dir, and optionally a real-binary dir.

    Every stub appends its own name to a log when run, so a test can prove
    not merely that the resolver declined an alias but that nothing ever
    executed one -- executing it is the entire harm.
    """
    log = tmp_path / "executed.log"
    alias_dir = tmp_path / "Local" / "Microsoft" / "WindowsApps"
    real_dir = tmp_path / "bin"
    for directory, names in ((alias_dir, alias_names), (real_dir, real_names)):
        directory.mkdir(parents=True, exist_ok=True)
        for name in names:
            stub = directory / name
            stub.write_text(
                f'#!/bin/sh\nprintf "%s\\n" "{name}" >> "{log}"\nexit 0\n',
                encoding="utf-8",
            )
            stub.chmod(0o755)
    return f"{alias_dir}:{real_dir}", log


@pytest.mark.skipif(not Path(_BASH).exists(), reason="bash unavailable")
@pytest.mark.parametrize(
    "alias_names,real_names,expected",
    [
        # Stock Windows box, no real Python: BOTH names are aliases, so the
        # only safe answer is no answer.
        (("python", "python3"), (), ""),
        # Windows box that HAS an interpreter: python3 is the alias, python
        # is the real thing -- that is why `python` is the fallback name.
        (("python3",), ("python",), "python"),
        # POSIX: no alias anywhere. The documented `python3` contract is
        # unchanged, which is the whole point of not widening this branch.
        ((), ("python3",), "python3"),
    ],
    ids=["both-aliases", "python-is-real", "posix-unchanged"],
)
def test_shell_last_resort_never_hands_back_a_store_alias(
    tmp_path, alias_names, real_names, expected
):
    path, log = _winsim(tmp_path, alias_names, real_names)
    # Source under the ambient PATH (the probe at the bottom of the lib
    # needs a working interpreter), THEN clear the log and switch to the
    # simulated PATH, so what the log records is this function alone.
    script = (
        f'. "{_RESOLVER_LIB}" || true\n'
        f': > "{log}"\n'
        f'PATH="{path}"\n'
        f"arka_python_last_resort\n"
    )
    result = subprocess.run(
        [_BASH, "-c", script], capture_output=True, text=True,
        env={"HOME": str(tmp_path / "home"), "PATH": os.environ.get("PATH", "/usr/bin:/bin")},
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == expected, (
        f"last resort returned {result.stdout.strip()!r}, expected {expected!r} "
        f"(aliases={alias_names}, real={real_names})"
    )
    assert log.read_text(encoding="utf-8") == "", (
        "the last resort executed a candidate; running a Store alias is the "
        f"side effect this whole guard exists to prevent (ran: {log.read_text()!r})"
    )


def test_resolver_fallbacks_are_not_unconditional_names():
    """Static pin for the exact shape of the defect, in both twins.

    Runs everywhere, including where pwsh is absent -- the executed tests
    below skip there, and a guard that only holds on a developer laptop is
    not a guard.
    """
    ps_body = _PS_LIB.read_text(encoding="utf-8")
    assert not re.search(r"return\s+\"python3?\"\s*$", ps_body, re.MULTILINE), (
        "arka_python.ps1 returns a bare interpreter NAME with no alias "
        "check; on a stock Windows box that name IS the Store alias, and "
        "every caller's `-and $env:ARKA_PY` guard treats it as usable"
    )
    assert "Get-ArkaPythonLastResort" in ps_body
    sh_body = _RESOLVER_LIB.read_text(encoding="utf-8")
    assert "arka_python_last_resort" in sh_body

    # The fix must not simply move the trap: these two consumers turned an
    # empty ARKA_PY straight back into a runnable bare name.
    shim = (_ROOT / "bin" / "arka-py.ps1").read_text(encoding="utf-8")
    assert not re.search(r'ARKA_PY\s*=\s*"python3?"', shim), (
        "bin/arka-py.ps1 reassigns a bare interpreter name when ARKA_PY is "
        "empty, which is precisely the value the resolver uses to say "
        "'every candidate is an alias'"
    )
    reader = (_ROOT / "core" / "workflow" / "state_reader.sh").read_text(encoding="utf-8")
    assert "${ARKA_PY:=" not in reader, (
        "state_reader.sh uses := , which overwrites a deliberately EMPTY "
        "ARKA_PY with python3 -- the alias itself on a stock Windows box. "
        "Use ${ARKA_PY=python3} so only an UNSET variable is defaulted."
    )


@pytest.mark.skipif(_PWSH is None, reason="PowerShell unavailable")
def test_ps_store_alias_predicate_executes_correctly():
    """Test-StoreAlias, actually run, against literal Windows paths.

    No filesystem needed: the predicate takes a path string, so the one
    piece of Windows behaviour that matters here is testable anywhere a
    PowerShell exists.
    """
    script = (
        f'. "{_PS_LIB}"\n'
        r"foreach ($p in @('C:\Users\d\AppData\Local\Microsoft\WindowsApps\python3.exe',"
        r" 'C:\Python313\python.exe', '')) {"
        " if (Test-StoreAlias $p) { 'ALIAS' } else { 'NOT' } }\n"
    )
    out = subprocess.run(
        [_PWSH, "-NoProfile", "-Command", script],
        capture_output=True, text=True,
    )
    assert out.returncode == 0, out.stderr
    assert out.stdout.split() == ["ALIAS", "NOT", "NOT"], out.stdout


@pytest.mark.skipif(_PWSH is None, reason="PowerShell unavailable")
@pytest.mark.parametrize(
    "name,stub_alias,expect_empty",
    [
        # The defect's own branch: the predicate says "alias", so the
        # function must yield '' and not a runnable name. Get-Command
        # cannot produce a WindowsApps path on POSIX, so the predicate --
        # verified against a literal alias path in the test above -- is
        # stubbed. What is under test is the WIRING: that the last resort
        # consults it at all, and that a positive answer wins.
        ("sh", True, True),
        # Real interpreter, real predicate: hand it back.
        ("sh", False, False),
        # Nothing resolves at all: nothing to hand back.
        ("no-such-binary-zzz", False, True),
    ],
    ids=["alias-yields-empty", "real-is-returned", "absent-yields-empty"],
)
def test_ps_last_resort_never_hands_back_a_store_alias(name, stub_alias, expect_empty):
    override = (
        "function Test-StoreAlias { param([string]$Path) return $true }\n"
        if stub_alias else ""
    )
    script = (
        f'. "{_PS_LIB}"\n{override}'
        f"$r = Get-ArkaPythonLastResort -Name '{name}'\n"
        'if (-not $r) { "EMPTY" } else { "VALUE[$r]" }\n'
    )
    out = subprocess.run(
        [_PWSH, "-NoProfile", "-Command", script],
        capture_output=True, text=True,
    )
    assert out.returncode == 0, out.stderr
    got = out.stdout.strip()
    if expect_empty:
        assert got == "EMPTY", f"expected no value, got {got!r}"
    else:
        assert got.startswith("VALUE[") and name in got, got
