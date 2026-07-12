"""Gate manifest generator — the single source the Node fast-path trusts.

F2-6 (hook fast-path): ``config/hooks/pre-tool-use.cjs`` and
``post-tool-use.cjs`` short-circuit the trivial hook decisions in ~18ms
p50 (measured — the Node startup floor is ~10ms on the reference
machine) instead of spawning the 82-96ms bash->Python chain on every
tool call.
The shims decide from ``config/gate-manifest.json`` ONLY — never from
constants of their own — and this module is the only writer of that
file: every value is imported from the real gate modules at generation
time (precedent: ``scripts/tools/docs_stats.py`` + its consistency
test; hand-typed copies are how the v4.3.2 drift happened).

Regenerate after touching any source constant:

    python -m core.hooks.gate_manifest

``tests/python/test_gate_manifest_parity.py`` fails when the committed
manifest drifts from these imports, and executes the embedded corpora
against the REAL Python functions; ``tests/installer/gate-manifest.test.js``
executes the same corpora against the Node engine. Drift on either side
breaks the build.

Scope contract: the manifest carries ONLY what the shims consume. The
shims have no deny path — they fast-allow a closed, corpus-proven set
or delegate to the Python chain — so gate internals that always
delegate (specialist globs, frontend markers, plan approval) stay out.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from pathlib import Path

_SCHEMA_VERSION = 1

# Python-only regex constructs that would compile differently (or not at
# all) under JavaScript's RegExp. The generator refuses to export any
# pattern containing them — porting is a conscious decision, not a
# silent one.
_JS_INCOMPATIBLE = ("(?P", "(?#", "(?(", "\\A", "\\Z")


def _js_pattern(compiled: re.Pattern) -> dict:
    """Export a compiled Python regex as a {py, js, flags} entry."""
    pattern = compiled.pattern
    for construct in _JS_INCOMPATIBLE:
        if construct in pattern:
            raise ValueError(
                f"regex {pattern!r} uses {construct!r} — not portable to "
                f"JS; port it consciously before exporting"
            )
    flags = "i" if compiled.flags & re.IGNORECASE else ""
    return {"py": pattern, "js": pattern, "flags": flags}


def _relative_to_home(path: Path) -> str:
    return str(path.relative_to(Path.home()))


def _bash_corpus() -> list[dict]:
    """Golden Bash classifications. ``expect`` is asserted against the
    REAL ``bash_is_effect`` by the pytest side; the node:test side
    asserts the engine returns ``engine_expect`` (defaults to
    ``expect``). ``engine_expect`` may only ever be MORE conservative
    ("effect" where Python says "discovery" — the engine delegates and
    Python re-classifies); the node suite enforces that one-sidedness
    structurally. The corpus cannot drift alone."""
    cases: list[tuple] = [
        ("git status", "discovery"),
        ("git log --oneline -5", "discovery"),
        ("git commit -m 'x'", "effect"),
        ("git push origin master", "effect"),
        ("ls -la /tmp", "discovery"),
        ("echo hello", "discovery"),
        ("echo hello > out.txt", "effect"),
        ("cat f.txt | grep needle", "discovery"),
        ("FOO=1 BAR=2 grep -r needle .", "discovery"),
        ("FOO=1 rm -rf /tmp/x", "effect"),
        ("rsync -av --dry-run a/ b/", "effect"),
        ("unknowncmd --version", "effect"),
        ("python3 -m pytest tests/", "discovery"),
        ("npm run build", "discovery"),
        ("npm install lodash", "effect"),
        ("docker ps", "discovery"),
        ("docker build -t x .", "effect"),
        ("kill -9 12345", "effect"),
        ("sed -i '' -e s/a/b/ f", "effect"),
        ("curl -s https://example.com", "discovery"),
        ("grep 'a > b' file.txt", "effect"),  # redirect regex sees quotes
        ("", "discovery"),
        ("   ", "discovery"),
        ("touch marker", "effect"),
        ("mkdir -p build", "effect"),
        # QG B1 (redo 1) — whitespace-class boundary. U+FEFF is NOT
        # whitespace to Python (isspace()=False, re \s no-match): the
        # token "FOO=1<U+FEFF>grep" stays glued → unknown → EFFECT. JS
        # \s/trim/split disagree, so the engine carries an explicit
        # non-ASCII-whitespace guard that forces EFFECT (delegation).
        ("FOO=1\ufeffgrep needle file", "effect"),
        ("FOO=1\ufeffFOO=2\ufeffgrep x", "effect"),
        ("FOO=1 \ufeff grep x", "effect"),
        # NBSP IS whitespace to both sides, so Python classifies this
        # discovery — but the engine's guard still forces EFFECT
        # (delegate), the allowed conservative direction.
        ("FOO=1\u00a0grep x", "discovery", "effect"),
    ]
    rows = []
    for case in cases:
        row = {"cmd": case[0], "expect": case[1]}
        if len(case) > 2:
            row["engine_expect"] = case[2]
        rows.append(row)
    return rows


def _pre_tool_corpus() -> list[dict]:
    """Golden PreToolUse routing: fast_allow vs delegate per tool name."""
    cases = [
        ("Read", "fast_allow"),
        ("Grep", "fast_allow"),
        ("Glob", "fast_allow"),
        ("TodoWrite", "fast_allow"),
        ("ExitPlanMode", "fast_allow"),
        ("Agent", "fast_allow"),
        ("mcp__obsidian__search_notes", "fast_allow"),
        ("mcp__supabase__list_tables", "fast_allow"),
        ("", "fast_allow"),
        ("WebSearch", "delegate"),
        ("WebFetch", "delegate"),
        ("mcp__context7__query-docs", "delegate"),
        ("mcp__firecrawl__firecrawl_scrape", "delegate"),
        ("Write", "delegate"),
        ("Edit", "delegate"),
        ("MultiEdit", "delegate"),
        ("NotebookEdit", "delegate"),
        ("Task", "delegate"),
        ("Skill", "delegate"),
    ]
    return [{"tool": tool, "expect": expect} for tool, expect in cases]


def _session_id_corpus() -> list[dict]:
    cases = [
        ("abc-123", True),
        ("a.b_c-D9", True),
        ("a" * 128, True),
        ("a" * 129, False),
        (".", False),
        ("..", False),
        ("...", False),
        ("a/../b", False),
        ("a b", False),
        ("", False),
        ("sessão", False),
    ]
    return [{"sid": sid, "expect": expect} for sid, expect in cases]


def _error_trigger_corpus() -> list[dict]:
    cases = [
        ("Error: something broke", True),
        ("fatal: not a git repository", True),
        ("2 tests failed", True),
        ("ENOENT: no such file", True),
        ("panic: runtime error", True),
        ("all 14 tests passed", False),
        ("ok", False),
        ("", False),
    ]
    return [{"output": output, "expect": expect} for output, expect in cases]


def _tool_sets() -> dict:
    from core.hooks import pre_tool_use
    from core.workflow import flow_enforcer, research_gate

    if pre_tool_use._FLOW_GATED_TOOLS != flow_enforcer.EFFECT_TOOLS_ALWAYS | {"Bash"}:
        raise ValueError(
            "pre_tool_use._FLOW_GATED_TOOLS no longer equals "
            "flow_enforcer.EFFECT_TOOLS_ALWAYS + Bash — re-derive the "
            "shim decision table before regenerating"
        )
    return {
        "flow_gated": sorted(pre_tool_use._FLOW_GATED_TOOLS),
        "effect_always": sorted(flow_enforcer.EFFECT_TOOLS_ALWAYS),
        "research_external": sorted(research_gate.RESEARCH_EXTERNAL_TOOLS),
        "post_delegate_always": ["Agent", "ExitPlanMode", "Task"],
    }


def _bash_classifier() -> dict:
    from core.workflow import flow_enforcer

    return {
        "discovery_first_tokens": sorted(flow_enforcer._BASH_DISCOVERY_FIRST),
        "effect_patterns": [
            _js_pattern(p) for p in flow_enforcer._BASH_EFFECT_PATTERNS
        ],
        "eval_order": "blacklist-then-whitelist",
        "strip_var_prefix": True,
        "unknown_first_token": "effect",
    }


def _telemetry_contract() -> dict:
    from core.workflow import flow_enforcer, research_gate

    kb_template = asdict(
        research_gate.Decision(allow=True, reason="tool-not-gated")
    )
    flow_template = asdict(
        flow_enforcer.Decision(allow=True, reason="tool-not-gated")
    )
    return {
        # datetime.now(timezone.utc).isoformat() — microseconds, +00:00
        # offset. The Node side emits the same shape (ms padded to 6
        # digits); parity test asserts datetime.fromisoformat parses it.
        "ts_format": "python-utc-isoformat",
        "kb_first_prefix_keys": ["ts", "session_id", "tool"],
        "kb_first_template": kb_template,
        "enforcement_prefix_keys": ["ts", "session_id", "tool", "cwd"],
        "enforcement_template": flow_template,
        "mcp_keys": ["ts", "server", "tool", "session"],
        "mcp_prefix": "mcp__",
    }


def _flags_and_budget() -> dict:
    from core.workflow import flow_enforcer

    if not flow_enforcer.CONFIG_PATH.name == "config.json":
        raise ValueError("flow_enforcer.CONFIG_PATH moved — update manifest")
    return {
        "hardEnforcement": {
            "path": ["hooks", "hardEnforcement"],
            # flow_enforcer._feature_flag_on: missing file → False,
            # corrupt JSON → False, value coerced with PYTHON truthiness
            # ("false" string is ON, [] and {} are OFF — JS Boolean()
            # disagrees on the last two; engine.cjs pythonTruthy() pins it).
            "on_missing_file": False,
            "on_corrupt": False,
            "coercion": "python-truthy",
        },
        "budget": {
            "section": "budget",
            "cap_keys": ["hardCapUsd", "dailyCapUsd"],
            # cost_governor semantics (cost_governor.py:68-86,126-131):
            # missing/corrupt config → {} → no-cap → allow with zero
            # reads/writes; a cap is ACTIVE only when float(value) > 0.
            "on_missing_file": "no-cap",
            "on_corrupt": "no-cap",
            "active_when": "float(value) > 0",
        },
    }


def _state_and_paths() -> dict:
    from core.shared.temp_paths import arkaos_temp_dir
    from core.workflow import flow_authorization, flow_enforcer, research_gate
    from core.runtime import mcp_telemetry

    auth_dir = arkaos_temp_dir("arkaos-flow-auth")
    if str(auth_dir.parent) != "/tmp":  # pragma: no cover — POSIX only
        raise ValueError("manifest generation is POSIX-only (tmp base)")
    return {
        "state_dirs": {
            "tmp_base_posix": "/tmp",
            "flow_auth_dirname": auth_dir.name,
            "flow_auth_file": "{sid}.json",
            "flow_auth_env_override": "ARKA_FLOW_AUTH_DIR",
        },
        "home_paths": {
            "config": ".arkaos/config.json",
            "telemetry_kb_first": _relative_to_home(research_gate.TELEMETRY_PATH),
            "telemetry_enforcement": _relative_to_home(
                flow_enforcer.TELEMETRY_PATH
            ),
            "telemetry_mcp": _relative_to_home(mcp_telemetry.DEFAULT_PATH),
        },
        "numbers": {
            "assistant_window": flow_enforcer.ASSISTANT_WINDOW,
            "grace_cap": flow_authorization.GRACE_CAP,
            "auth_ttl_seconds": flow_authorization.DEFAULT_TTL_SECONDS,
        },
    }


def build_manifest() -> dict:
    """Assemble the manifest from the real gate constants (import-time)."""
    from core.hooks import post_tool_use, pre_tool_use  # noqa: F401
    from core.shared import safe_session_id as ssid

    state = _state_and_paths()
    if pre_tool_use._ASSISTANT_WINDOW != state["numbers"]["assistant_window"]:
        raise ValueError("ASSISTANT_WINDOW diverged between hook and enforcer")
    return {
        "schema_version": _SCHEMA_VERSION,
        "platform": "posix",
        "source_modules": [
            "core.hooks.post_tool_use",
            "core.hooks.pre_tool_use",
            "core.runtime.cost_governor",
            "core.runtime.mcp_telemetry",
            "core.shared.safe_session_id",
            "core.shared.temp_paths",
            "core.workflow.flow_authorization",
            "core.workflow.flow_enforcer",
            "core.workflow.research_gate",
        ],
        "tools": _tool_sets(),
        "bash": _bash_classifier(),
        "post": {
            "error_trigger": _js_pattern(post_tool_use._ERROR_TRIGGER_RE),
            "success_exit_codes": ["0", ""],
        },
        "session_id": {
            **_js_pattern(ssid.SAFE_SESSION_ID_RE),
            "reject_dot_only": True,
        },
        "flags": _flags_and_budget(),
        "telemetry": _telemetry_contract(),
        **state,
        "io_contract": {
            "pre": {"allow_stdout": "", "fail_open_exit": 0},
            "post": {"success_stdout": "{}", "fail_open_stdout": "{}",
                     "fail_open_exit": 0},
        },
        "env": {
            "kill_switch": "ARKA_HOOK_FASTPATH",
            "kill_switch_off_value": "0",
        },
        "corpora": {
            "bash": _bash_corpus(),
            "pre_tools": _pre_tool_corpus(),
            "session_ids": _session_id_corpus(),
            "error_trigger": _error_trigger_corpus(),
        },
    }


def manifest_path() -> Path:
    # Sibling of the .cjs shims (config/hooks/) so the __dirname
    # resolution works identically in-repo and deployed — the shims
    # never resolve ARKAOS_ROOT (design R7).
    return (
        Path(__file__).resolve().parents[2]
        / "config" / "hooks" / "gate-manifest.json"
    )


def render() -> str:
    return json.dumps(build_manifest(), indent=2, sort_keys=True) + "\n"


def main() -> int:
    path = manifest_path()
    path.write_text(render(), encoding="utf-8")
    print(f"gate-manifest written: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
