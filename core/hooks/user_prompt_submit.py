"""UserPromptSubmit — consolidated entrypoint (PR-6 v4.1.0 hook hygiene).

Replaces the ~31 python3/jq spawn sites of the old ``user-prompt-submit.sh``
with ONE python process. The Synapse bridge (scripts/synapse-bridge.py) is
imported and called in-process via its ``run_bridge()`` function instead of
being spawned as a second interpreter.

Section order preserved exactly:
    1. V1 migration detection (short-circuit)
    2. Sync version detection ([arka:update-available])
    3. Flow marker + obsidian-query cache invalidation (invalidate_marker)
    4. Synapse bridge → 12-layer context string
    5. Workflow-state + Forge tags appended to the bridge context
    6. KB auto-inject (session cache overlap)
    7. Bash-parity fallback context (L0 constitution, branch, workflow,
       forge) when the bridge degrades
    8. Token hygiene suggestions (4 checks, ported from token-hygiene.sh)
    9. Persistent routing reminder + workflow classifier directive
   10. Cognitive context injection + one-shot nudges (kb-cite, meta-tag,
       closing-marker) gated by effort level
   11. additionalContext JSON output + hook metrics

Keep the classifier verb pattern in sync with
``config/hooks/_lib/workflow-classifier.sh`` (still the CLI entry).
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import re
import subprocess
import time
from pathlib import Path

from core.shared.temp_paths import arkaos_temp_dir
from core.hooks._shared import (
    ensure_root_on_path,
    get_str,
    read_stdin_json,
    repo_path,
    resolve_arkaos_root,
    safe_session_id,
)

_CACHE_DIR = arkaos_temp_dir("arkaos-context-cache")
_CACHE_TTL = 300  # Constitution cache: 5 minutes

_L0_FALLBACK = (
    "[Constitution] NON-NEGOTIABLE: branch-isolation, security-gate, "
    "mandatory-qa, evidence-flow, arkaos-not-yes-man, excellence-mandate "
    "| QUALITY-GATE: marta-cqo, eduardo-copy, francisca-tech-ux | "
    "MUST (28) incl.: squad-routing, spec-driven, conventional-commits, "
    "test-coverage, subagent-discipline, persona-vs-artifact"
)

_ROUTE_REMINDER = """
[ARKA:ROUTE]
EVERY response MUST route through a department squad.
NO generic assistant replies. Announce the squad before responding.
When [knowledge:N chunks] is present, cite at least one source.
If [knowledge:N chunks] is absent on a non-trivial ArkaOS topic, query Obsidian first."""

_WORKFLOW_DIRECTIVE = """
[ARKA:WORKFLOW-REQUIRED] CREATION/IMPLEMENTATION detected — the 4-gate evidence
flow applies (constitution rule evidence-flow; source arka/skills/flow/SKILL.md).
G1 CONTEXT ([arka:routing] + grounding) -> G2 PLAN (explicit approval) ->
G3 EXECUTE (real test run + exit 0 on record) -> G4 REVIEW (executable checks).
Emit [arka:gate:N] at each gate start. No writes before G2 approval.
Trivial bypass: [arka:trivial] <reason> for a single-file edit under 10 lines."""

# Keep in sync with ARKA_WF_VERB_PATTERN in _lib/workflow-classifier.sh.
_WF_VERB_PATTERN = (
    r"(criar?|crie[ms]?|cria[mr]?|adicionar?|adiciona[mr]?|implementar?"
    r"|implementa[mr]?|desenvolver?|desenvolve[mr]?|construir?"
    r"|constru[ií]a?[mr]?|fazer?|faz[ae]?[mr]?|refactor(izar?)?|corrigir?"
    r"|corrige[mr]?|consertar?|conserta[mr]?|continuar?|continua[mr]?"
    r"|forçar?|força[mr]?|colocar?|coloca[mr]?|p[oô]r|melhorar?"
    r"|melhora[mr]?|terminar?|termina[mr]?|acabar?|acaba[mr]?|publicar?"
    r"|publica[mr]?|lançar?|lança[mr]?|create[sd]?|creating|build(s|ing)?"
    r"|add(s|ed|ing)?|implement(s|ed|ing)?|develop(s|ed|ing)?"
    r"|fix(es|ed|ing)?|refactor(s|ed|ing)?|make[sd]?|making|continue[sd]?"
    r"|continuing|ship(s|ped|ping)?|merge[sd]?|merging|publish(es|ed|ing)?"
    r"|release[sd]?|releasing|deploy(s|ed|ing)?|finish(es|ed|ing)?"
    r"|improve[sd]?|improving)"
)
_WF_VERB_RE = re.compile(rf"\b{_WF_VERB_PATTERN}\b", re.IGNORECASE)

_STOPWORDS = frozenset(
    "the a an and or but if then of for to in on at by with from is are was "
    "were be been being do does did have has had this that these those it "
    "its as i you we they he she them my your our their so not no yes can "
    "will would could should may might must need want fix make use get set "
    "add remove".split()
)

_VAGUE_PHRASES = (
    "fix the bug", "that file", "the error",
    "esse ficheiro", "esse erro", "aquele bug",
)


# ─── Sections 1-2: migration + sync detection ────────────────────────────


def _v1_migration_notice() -> str | None:
    v1_paths = (
        Path.home() / ".claude" / "skills" / "arka-os",
        Path.home() / ".claude" / "skills" / "arkaos",
    )
    marker = Path.home() / ".arkaos" / "migrated-from-v1"
    for v1_path in v1_paths:
        if v1_path.is_dir() and not marker.is_file():
            return (
                f"[MIGRATION] ArkaOS v1 detected at {v1_path}. Run: npx "
                f"arkaos migrate — This will backup v1, preserve your data, "
                f"and install v2. See: "
                f"https://github.com/andreagroferreira/arka-os#install"
            )
    return None


def _sync_notice() -> str:
    repo = repo_path()
    if not repo:
        return ""
    current = ""
    version_file = Path(repo) / "VERSION"
    package_json = Path(repo) / "package.json"
    try:
        if version_file.is_file():
            current = version_file.read_text(encoding="utf-8").strip()
        elif package_json.is_file():
            current = str(
                json.loads(package_json.read_text(encoding="utf-8"))["version"]
            )
    except Exception:
        current = ""
    if not current:
        return ""
    synced = "none"
    sync_state = Path.home() / ".arkaos" / "sync-state.json"
    if sync_state.is_file():
        try:
            synced = str(
                json.loads(sync_state.read_text(encoding="utf-8"))["version"]
            )
        except Exception:
            synced = "none"
    if current != synced:
        return (
            f"[arka:update-available] ArkaOS v{current} installed "
            f"(synced: {synced}). Run /arka update to sync all projects. "
        )
    return ""


# ─── Section 3: per-turn cache invalidation ──────────────────────────────


def _invalidate_turn_caches(session_id: str) -> None:
    """invalidate_marker + invalidate_obsidian_query (new turn reset)."""
    if not session_id:
        return
    try:
        from core.workflow.marker_cache import invalidate_marker
        invalidate_marker(session_id)
    except Exception:
        pass
    try:
        # Reset only the per-turn grace flag; confirmed authorization and
        # the grace counter persist across turns (enforcer resilience).
        from core.workflow.flow_authorization import reset_turn
        reset_turn(session_id)
    except Exception:
        pass
    try:
        from core.synapse.kb_cache import invalidate_obsidian_query
        invalidate_obsidian_query(session_id)
    except Exception:
        pass


# ─── Section 4: Synapse bridge (in-process) ──────────────────────────────


def _run_bridge(root: str, user_input: str, session_id: str) -> str:
    bridge_path = Path(root) / "scripts" / "synapse-bridge.py"
    if not bridge_path.is_file() or not Path(root).is_dir():
        return ""
    try:
        spec = importlib.util.spec_from_file_location(
            "arka_synapse_bridge", bridge_path
        )
        if spec is None or spec.loader is None:
            return ""
        module = importlib.util.module_from_spec(spec)
        # The old hook piped bridge stderr to /dev/null — keep it quiet.
        with contextlib.redirect_stderr(io.StringIO()):
            spec.loader.exec_module(module)
            output, code = module.run_bridge(
                {"user_input": user_input, "session_id": session_id},
                Path(root),
            )
        if code == 0:
            return str(output.get("context_string", ""))
    except Exception:
        pass
    return ""


# ─── Section 5: workflow-state + forge tags ──────────────────────────────


def _workflow_tag() -> str:
    state_file = Path.home() / ".arkaos" / "workflow-state.json"
    if not state_file.is_file():
        return ""
    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    if not isinstance(state, dict):
        return ""
    phases = state.get("phases", {}) or {}
    workflow = str(state.get("workflow", "") or "")
    branch = str(state.get("branch", "") or "")
    violations = len(state.get("violations", []) or [])
    total = len(phases)
    completed = sum(
        1 for p in phases.values() if p.get("status") == "completed"
    )
    current = next(
        (k for k, p in phases.items() if p.get("status") == "in_progress"),
        "none",
    )
    tag = (
        f"[workflow:{workflow}] [phase:{current}] "
        f"[branch:{branch}] [violations:{violations}]"
    )
    if violations != 0:
        tag = f"WARNING: {violations} workflow violation(s). {tag}"
    return tag


def _forge_tag() -> str:
    active = Path.home() / ".arkaos" / "plans" / "active.yaml"
    if not active.is_file():
        return ""
    try:
        forge_id = active.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    forge_file = Path.home() / ".arkaos" / "plans" / f"{forge_id}.yaml"
    if not forge_file.is_file():
        return ""
    status = ""
    try:
        import yaml
        data = yaml.safe_load(forge_file.read_text(encoding="utf-8")) or {}
        status = str(data.get("status", ""))
    except Exception:
        status = ""  # yaml-less python3 → tag still appended, empty status
    return f"[forge:{forge_id}] [forge-status:{status}]"


# ─── Section 6: KB auto-inject (session cache) ───────────────────────────


def _kb_auto_inject(root: str, user_input: str) -> str:
    import hashlib

    kb_session_id = (
        os.environ.get("ARKAOS_SESSION_ID")
        or os.environ.get("CLAUDE_SESSION_ID")
        or f"bridge-{os.getpid()}"
    )
    project_hash = hashlib.md5(
        root.encode(), usedforsecurity=False
    ).hexdigest()[:12]
    cache_dir = arkaos_temp_dir(f"arkaos-kb-{project_hash}")
    if not cache_dir.is_dir():
        return ""
    try:
        from core.synapse.kb_cache import KBSessionCache
        cache = KBSessionCache(session_id=kb_session_id, project_path=root)
        results = cache.get_overlap(user_input, threshold=0.3)
    except Exception:
        return ""
    if not results:
        return ""
    snippets = []
    for r in results[:3]:
        src = r.get("source", "").split("/")[-1] if r.get("source") else ""
        txt = str(r.get("text", ""))[:200].replace("\n", " ")
        snippets.append(f"{src}: {txt}" if src else txt)
    return " | ".join(snippets)


# ─── Section 7: bash-parity fallback context ─────────────────────────────


def _l0_constitution() -> str:
    cache_file = _CACHE_DIR / "l0-constitution"
    try:
        if cache_file.is_file():
            age = time.time() - cache_file.stat().st_mtime
            if age < _CACHE_TTL:
                return cache_file.read_text(encoding="utf-8")
    except OSError:
        pass
    try:
        cache_file.write_text(_L0_FALLBACK, encoding="utf-8")
    except OSError:
        pass
    return _L0_FALLBACK


def _git_branch_tag() -> str:
    try:
        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=2,
        ).stdout.strip()
    except Exception:
        branch = ""
    if branch and branch not in ("main", "master", "dev"):
        return f"[branch:{branch}]"
    return ""


def _fallback_context() -> str:
    l0 = _l0_constitution()
    l4 = _git_branch_tag()
    l7 = ""  # Time layer intentionally skipped in fallback (cache churn).
    l8 = _workflow_tag()
    l9 = _forge_tag()
    return f"{l0} {l4} {l7} {l8} {l9}"


# ─── Section 8: token hygiene (ported from token-hygiene.sh) ─────────────


def _keywords(text: str) -> list[str]:
    tokens = re.split(r"[^a-z0-9]+", text.lower())
    return sorted({
        t for t in tokens if len(t) > 3 and t not in _STOPWORDS
    })


def _last_user_messages(transcript_path: str, n: int = 3) -> str:
    if not transcript_path or not Path(transcript_path).is_file():
        return ""
    try:
        lines = Path(transcript_path).read_text(
            encoding="utf-8", errors="replace"
        ).splitlines()[-200:]
    except OSError:
        return ""
    msgs: list[str] = []
    for line in lines:
        try:
            record = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(record, dict):
            continue
        if record.get("type") == "user" or record.get("role") == "user":
            content = record.get("content") or record.get(
                "message", {}
            ).get("content", "")
            if isinstance(content, list):
                content = " ".join(
                    p.get("text", "") for p in content if isinstance(p, dict)
                )
            msgs.append(str(content))
    return "\n".join(msgs[-n:])


def _token_hygiene(prompt: str, transcript_path: str) -> str:
    suggestions: list[str] = []

    ctx_raw = os.environ.get("CLAUDE_CONTEXT_USED", "").rstrip("%")
    if ctx_raw:
        try:
            ctx = int(ctx_raw)
            if ctx > 80:
                suggestions.append(
                    f"[arka:warn] Context at {ctx}% — /compact recommended NOW."
                )
            elif ctx > 60:
                suggestions.append(
                    f"[arka:suggest] Context at {ctx}% — consider /compact."
                )
        except ValueError:
            pass

    if prompt:
        prior = _last_user_messages(transcript_path)
        cur_kw = _keywords(prompt)[:20]
        if prior and cur_kw and len(cur_kw) > 2:
            overlap = len(set(cur_kw) & set(_keywords(prior)))
            if overlap * 100 // len(cur_kw) < 30:
                suggestions.append(
                    "[arka:suggest] Topic shift detected — consider /clear "
                    "for a fresh session."
                )

        if len(prompt) > 2000 and "```" in prompt:
            suggestions.append(
                f"[arka:suggest] Large paste detected ({len(prompt)} chars) "
                f"— consider @filepath reference for better token economy."
            )

        lower = prompt.lower()
        if any(p in lower for p in _VAGUE_PHRASES) and "@" not in prompt:
            suggestions.append(
                "[arka:suggest] Vague reference — use @path/to/file.ext "
                "for precision."
            )

    return " ".join(suggestions)


# ─── Section 9: workflow classifier ──────────────────────────────────────


def _wf_classify(text: str) -> bool:
    if not text or text[0] in ("/", "!"):
        return False
    return bool(_WF_VERB_RE.search(text))


def _wf_mark_required(session_id: str) -> None:
    if safe_session_id(session_id) is None:
        return
    marker_dir = Path(
        os.environ.get("ARKA_WF_REQUIRED_DIR", str(arkaos_temp_dir("arkaos-wf-required")))
    )
    try:
        marker_dir.mkdir(parents=True, exist_ok=True)
        (marker_dir / session_id).write_text(
            time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            encoding="utf-8",
        )
    except OSError:
        pass


# ─── Section 10: cognitive inject + one-shot nudges ──────────────────────


def _cognitive_hits(session_id: str) -> str:
    if not session_id:
        return ""
    repo = repo_path()
    if not repo or not Path(repo).is_dir():
        return ""
    try:
        from core.cognition.retrieval import format_advisory, read_context
        return format_advisory(read_context(session_id)) or ""
    except Exception:
        return ""


def _one_shot_nudge(subdir: str, session_id: str) -> str:
    """Read + delete a /tmp/<subdir>/<session>.json nudge state file."""
    nudge_file = arkaos_temp_dir(subdir) / f"{session_id}.json"
    if not nudge_file.is_file():
        return ""
    nudge = ""
    try:
        data = json.loads(nudge_file.read_text(encoding="utf-8"))
        suggestion = data.get("suggestion")
        if data.get("passed") is False and suggestion:
            nudge = f"[arka:suggest] {suggestion}"
    except (OSError, json.JSONDecodeError, ValueError):
        pass
    try:
        nudge_file.unlink(missing_ok=True)
    except OSError:
        pass
    return nudge


# ─── Section 11: metrics ─────────────────────────────────────────────────


def _log_metrics(elapsed_ms: int, user_input: str) -> None:
    if elapsed_ms <= 0:
        return
    at_mentions = len(
        re.findall(r"(?:^|\s)@[A-Za-z0-9_./-]+", user_input)
    )
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with (_CACHE_DIR / "hook-metrics.jsonl").open(
            "a", encoding="utf-8"
        ) as fh:
            fh.write(json.dumps({
                "hook": "user-prompt-submit-v2",
                "ms": elapsed_ms,
                "at_mentions": at_mentions,
            }) + "\n")
    except OSError:
        pass


# ─── Entry point ─────────────────────────────────────────────────────────


def main(stdin_json: dict | None = None, raw: str = "") -> int:
    start = time.monotonic()
    if stdin_json is None:
        stdin_json, raw = read_stdin_json()

    migration = _v1_migration_notice()
    if migration is not None:
        print(json.dumps({"additionalContext": migration}))
        return 0

    sync_notice = _sync_notice()

    root = resolve_arkaos_root()
    ensure_root_on_path(root)
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass

    user_input = get_str(stdin_json, "userInput") or get_str(
        stdin_json, "message"
    )
    session_id = get_str(stdin_json, "session_id")
    effort_level = get_str(stdin_json, "effort", "level") or os.environ.get(
        "CLAUDE_EFFORT", ""
    )
    surface_nudges = (effort_level or "high") not in ("low", "medium")

    _invalidate_turn_caches(session_id)

    if not user_input:
        user_input = raw[:2000]

    # ─── Synapse bridge + tags ───────────────────────────────────────
    python_result = _run_bridge(root, user_input, session_id)
    if python_result:
        wf_tag = _workflow_tag()
        if wf_tag:
            python_result = f"{python_result} {wf_tag}"
        forge_tag = _forge_tag()
        if forge_tag:
            python_result = f"{python_result} {forge_tag}"
        if "[knowledge:" in python_result:
            kb_content = _kb_auto_inject(root, user_input)
            if kb_content:
                python_result = f"{kb_content} {python_result}"
    else:
        python_result = _fallback_context()

    hygiene = _token_hygiene(
        user_input, get_str(stdin_json, "transcript_path")
    )

    workflow_directive = ""
    if user_input and _wf_classify(user_input):
        _wf_mark_required(session_id)
        workflow_directive = _WORKFLOW_DIRECTIVE

    context_hits = _cognitive_hits(session_id)

    kb_cite_nudge = meta_tag_nudge = closing_marker_nudge = ""
    if session_id and surface_nudges:
        kb_cite_nudge = _one_shot_nudge("arkaos-cite", session_id)
        meta_tag_nudge = _one_shot_nudge("arkaos-meta", session_id)
        closing_marker_nudge = _one_shot_nudge("arkaos-closing", session_id)

    # ─── Output (assembly order identical to the bash version) ──────
    out = (
        f"{sync_notice}{_ROUTE_REMINDER}{workflow_directive} {python_result}"
    )
    if hygiene:
        out = f"{out} {hygiene}"
    for nudge in (kb_cite_nudge, meta_tag_nudge, closing_marker_nudge):
        if nudge:
            out = f"{out}\n{nudge}"
    if context_hits:
        out = f"{out}\n{context_hits}"
    print(json.dumps({"additionalContext": out}))

    _log_metrics(int((time.monotonic() - start) * 1000), user_input)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        # Fail open with the minimal constitution context.
        print(json.dumps({"additionalContext": _L0_FALLBACK}))
        raise SystemExit(0)
