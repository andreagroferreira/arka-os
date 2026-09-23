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
    6. (removed — Gate Economy PR-10: KB overlap injection now happens
       ONCE, in Synapse L3.5; the session-cache duplicate is gone)
    7. Bash-parity fallback context (L0 constitution, branch, workflow,
       forge) when the bridge degrades
    8. Token hygiene suggestions (4 checks, ported from token-hygiene.sh)
    9. Routing reminder + workflow classifier directive (one-line tags;
       the full contracts ride once per session at SessionStart)
   10. Cognitive context injection + one-shot nudges (kb-cite, meta-tag,
       closing-marker) gated by effort level
   11. additionalContext JSON output + hook metrics

Sections 8, 10 and the refine hint are budgeted — past the
``ARKA_UPS_BUDGET_MS`` deadline they are skipped and named in
``[arka:degraded]``; 1-5, 9 and 11 always run, and 7 runs unbudgeted
only when the bridge degrades.

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
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

from core.hooks._shared import (
    emit_additional_context,
    ensure_root_on_path,
    get_str,
    read_stdin_json,
    record_degraded,
    repo_path,
    resolve_arkaos_root,
    safe_session_id,
)
from core.shared.temp_paths import arkaos_temp_dir, wf_required_dir

if TYPE_CHECKING:
    from core.decisions.config import DecisionsConfig
    from core.decisions.site import Outcome, SiteCall
    from core.hooks.ups_dispatch import SkillMenu

_T = TypeVar("_T")

_CACHE_DIR = arkaos_temp_dir("arkaos-context-cache")
_CACHE_TTL = 300  # Constitution cache: 5 minutes

_L0_FALLBACK = (
    "[Constitution] NON-NEGOTIABLE: branch-isolation, security-gate, "
    "mandatory-qa, evidence-flow, arkaos-not-yes-man, excellence-mandate "
    "| QUALITY-GATE: marta-cqo, eduardo-copy, francisca-tech-ux | "
    "MUST (28) incl.: squad-routing, spec-driven, conventional-commits, "
    "test-coverage, subagent-discipline, persona-vs-artifact"
)

# Gate Economy PR-10: the FULL routing and evidence-flow contracts ride
# once per session in the SessionStart injection (_SKILL_ROUTING_CONTRACT,
# _EVIDENCE_CONTRACT) and stay in the conversation context. Repeating
# ~190 tokens of byte-identical text on EVERY turn was pure duplication;
# the per-turn line keeps only the tag (which tests and enforcers key
# on) plus a one-line pointer.
_ROUTE_REMINDER = (
    "\n[ARKA:ROUTE] Squad routing obligatory (full contract at "
    "SessionStart) — announce the squad; cite KB when "
    "[knowledge:N chunks] is present, else query Obsidian on "
    "non-trivial ArkaOS topics."
)

_WORKFLOW_DIRECTIVE = (
    "\n[ARKA:WORKFLOW-REQUIRED] CREATION/IMPLEMENTATION detected — "
    "4-gate evidence flow applies (full contract at SessionStart; "
    "source arka/skills/flow/SKILL.md). Emit [arka:gate:N]; no writes "
    "before G2 approval; trivial bypass: [arka:trivial] <reason>."
)

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

# Keep in sync with ARKA_WF_QUESTION_LEAD in _lib/workflow-classifier.sh.
# Interrogative-led prompts that end in "?" are information questions, not
# creation intent, even when they contain an action verb ("o que e que este
# projeto faz?"). Polite requests ("podes implementar X?") keep matching:
# their lead word is not interrogative.
_WF_QUESTION_LEAD_PATTERN = (
    r"(o\s+que|porqu[eê]|por\s+que|para\s+que|qual|quais|quando|onde|quem|como"
    r"|what|why|which|who|whose|when|where|how|does)"
)
_WF_QUESTION_LEAD_RE = re.compile(
    rf"^\s*{_WF_QUESTION_LEAD_PATTERN}\b", re.IGNORECASE
)

_STOPWORDS = frozenset([
    "the", "a", "an", "and", "or", "but", "if", "then", "of", "for", "to", "in", "on",
    "at", "by", "with", "from", "is", "are", "was", "were", "be", "been", "being", "do",
    "does", "did", "have", "has", "had", "this", "that", "these", "those", "it", "its",
    "as", "i", "you", "we", "they", "he", "she", "them", "my", "your", "our", "their",
    "so", "not", "no", "yes", "can", "will", "would", "could", "should", "may", "might",
    "must", "need", "want", "fix", "make", "use", "get", "set", "add", "remove"
])

_VAGUE_PHRASES = (
    "fix the bug", "that file", "the error",
    "esse ficheiro", "esse erro", "aquele bug",
)

_TOPIC_SHIFT_SUGGESTION = (
    "[arka:suggest] Topic shift detected — consider /clear "
    "for a fresh session."
)

_REFINE_THRESHOLD = 85
_REFINE_TEXT = (
    "the request may be vague; consider /arka refine to ask about the "
    "topic and compile a precise prompt before building."
)

# A prompt is CONCRETE (never refine-worthy) when it names a real
# target: a file (foo.py, README.md, path/to/x), a CamelCase or
# snake_case code identifier (AuthService, user_repo), or a backticked
# term. Kills the "no files → +20 constant" false positives the scorer
# alone can't distinguish (QG 2026-07-09).
# NOTE: NOT case-insensitive — the CamelCase alternation depends on real
# case (IGNORECASE would match any two-syllable lowercase word like
# "melhor" and defeat the whole carve-out).
_CONCRETE_TARGET_RE = re.compile(
    r"[\w./-]+\.[A-Za-z]{1,5}\b"        # file with a real extension
    r"|[\w-]+/[\w./-]+"                 # path segments (a/b/c)
    r"|\b[A-Z][a-z0-9]+[A-Z]\w+\b"      # CamelCase identifier
    r"|\b[a-z]+_[a-z0-9_]+\b"           # snake_case identifier
    r"|`[^`]+`"                         # backticked term
)


def _names_concrete_target(text: str) -> bool:
    return bool(_CONCRETE_TARGET_RE.search(text or ""))


# ─── Sections 1-2: migration + sync detection ────────────────────────────


def _v1_migration_notice() -> str | None:
    home = Path.home()
    # A valid v2 install manifest is the canonical signal that v2 is
    # already functional — never nag past it. This guard existed only in
    # the old native user-prompt-submit.ps1; hoisting it into the shared
    # producer makes it hold on every platform.
    if (home / ".arkaos" / "install-manifest.json").is_file():
        return None
    if (home / ".arkaos" / "migrated-from-v1").is_file():
        return None
    v1_paths = (
        home / ".claude" / "skills" / "arka-os",
        home / ".claude" / "skills" / "arkaos",
    )
    for v1_path in v1_paths:
        # Require a real v1 install, not just a directory: an orphan
        # folder holding a single bookkeeping file re-armed this notice
        # on every prompt forever, and the early-return in main() then
        # killed the whole per-prompt chain (Cross-Machine Lab, U1 —
        # reproduced identically on Linux and Windows).
        if (v1_path / "SKILL.md").is_file() or (v1_path / "skill.json").is_file():
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
    try:
        from core.synapse.kb_cache import invalidate_injected_context
        invalidate_injected_context(session_id)
    except Exception:
        pass
    # Runtime Sync PR0: graphify gained its first writer; without this the
    # marker would be permanently true once set (QG 2026-09-03, M3).
    try:
        from core.synapse.kb_cache import invalidate_graphify_query
        invalidate_graphify_query(session_id)
    except Exception:
        pass


# ─── Section 4: Synapse bridge (in-process) ──────────────────────────────


def _bridge_payload(
    user_input: str,
    session_id: str,
    cwd: str,
    route_hint: dict[str, Any] | None,
    skill_hint: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"user_input": user_input, "session_id": session_id}
    if cwd:
        # Explicit hook cwd — L9.5 scopes cross-session memory by
        # project; an unscoped search would leak across clients.
        payload["cwd"] = cwd
    if route_hint:
        # Jev route decision (acted on) — Synapse L1 prefers it over the
        # keyword count, never over an explicit /prefix.
        payload["route_hint"] = route_hint
    if skill_hint:
        # Jev skill-hints decision (acted on, registry id) — Synapse L5
        # puts it first, after the project signal.
        payload["skill_hint"] = skill_hint
    return payload


def _run_bridge(
    root: str,
    user_input: str,
    session_id: str,
    cwd: str = "",
    route_hint: dict[str, Any] | None = None,
    skill_hint: dict[str, Any] | None = None,
) -> str:
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
            payload = _bridge_payload(user_input, session_id, cwd, route_hint, skill_hint)
            output, code = module.run_bridge(payload, Path(root))
        if code == 0:
            return _bridge_text(output)
    except Exception:
        pass
    return ""


def _bridge_text(output: dict[str, Any]) -> str:
    parts = [str(output.get("context_string", ""))]
    # Full-text blocks follow the compact tag line. A tag such as
    # `[kb-context:5 +graph]` announces an injection; without these
    # the announcement was all the model ever received.
    blocks = output.get("content_blocks") or []
    if isinstance(blocks, list):
        parts.extend(str(b) for b in blocks if b)
    return "\n".join(p for p in parts if p)


# ─── Section 5: workflow-state + forge tags ──────────────────────────────


def _workflow_tag() -> str:
    # QG round 1, B1: resolve the state the way the writer does — the
    # hardcoded legacy path silenced this tag when the tracker moved.
    try:
        from core.workflow.state import get_state

        state = get_state()
    except Exception:
        return ""
    if not isinstance(state, dict):
        return ""
    phases = state.get("phases", {}) or {}
    workflow = str(state.get("workflow", "") or "")
    branch = str(state.get("branch", "") or "")
    violations = len(state.get("violations", []) or [])
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
    with contextlib.suppress(OSError):
        cache_file.write_text(_L0_FALLBACK, encoding="utf-8")
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
    return "\n".join(_recent_user_messages(transcript_path, n))


def _recent_user_messages(transcript_path: str, n: int = 3) -> list[str]:
    """The last ``n`` user messages of the transcript (oldest first)."""
    if not transcript_path or not Path(transcript_path).is_file():
        return []
    try:
        lines = Path(transcript_path).read_text(
            encoding="utf-8", errors="replace"
        ).splitlines()[-200:]
    except OSError:
        return []
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
    return msgs[-n:]


def keyword_topic_shift(prompt: str, prior: str) -> bool:
    """Topic-drift heuristic: < 30 % keyword overlap with ``prior``.

    Needs ``prior`` and more than two keywords in ``prompt``; else False.
    """
    cur_kw = _keywords(prompt)[:20]
    if not (prior and cur_kw and len(cur_kw) > 2):
        return False
    overlap = len(set(cur_kw) & set(_keywords(prior)))
    return overlap * 100 // len(cur_kw) < 30


def _context_usage_suggestion() -> str:
    ctx_raw = os.environ.get("CLAUDE_CONTEXT_USED", "").rstrip("%")
    if not ctx_raw:
        return ""
    try:
        ctx = int(ctx_raw)
    except ValueError:
        return ""
    if ctx > 80:
        return f"[arka:warn] Context at {ctx}% — /compact recommended NOW."
    if ctx > 60:
        return f"[arka:suggest] Context at {ctx}% — consider /compact."
    return ""


def _token_hygiene(
    prompt: str, transcript_path: str, topic_shift: bool | None = None
) -> str:
    # topic_shift: the decisions stage's outcome; None → keyword heuristic.
    suggestions: list[str] = []
    context_usage = _context_usage_suggestion()
    if context_usage:
        suggestions.append(context_usage)

    if prompt:
        if topic_shift is None:
            prior = _last_user_messages(transcript_path)
            topic_shift = keyword_topic_shift(prompt, prior)
        if topic_shift:
            suggestions.append(_TOPIC_SHIFT_SUGGESTION)

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
    stripped = text.strip()
    if stripped.endswith("?") and _WF_QUESTION_LEAD_RE.match(stripped):
        return False
    return bool(_WF_VERB_RE.search(text))


def _wf_mark_required(session_id: str) -> None:
    if safe_session_id(session_id) is None:
        return
    marker_dir = wf_required_dir()
    try:
        marker_dir.mkdir(parents=True, exist_ok=True)
        (marker_dir / session_id).write_text(
            time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            encoding="utf-8",
        )
    except OSError:
        pass


def _refine_hint(user_input: str, outcome: Outcome | None = None) -> str:
    """Interaction Reform PR5 — a vague code-modifying request is a
    signal to refine the prompt (ask about the topic) BEFORE the
    workflow. SUGGESTION only; /do decides. Not a slash command.

    Calibration (QG 2026-07-09): the scorer's +20 "no files" branch is
    a constant in the hook context (the hook never has files), so 70 is
    the floor for ANY short prompt. Two guards keep clear asks out — a
    higher threshold (85, above that constant) AND a concrete-target
    carve-out applied by the caller: a prompt that names a file or a
    code identifier ("fix the typo in README.md", "add a test to
    AuthService") is specific, never refine-worthy.

    JEV Decisions PR1: when the ``refine`` site acted on Jev, its
    answer replaces the score (``source=jev``); else the score decides.
    """
    if outcome is not None and outcome.acted_on == "jev":
        return _jev_refine_hint(outcome) if outcome.value else ""
    try:
        from core.forge.complexity import score_prompt_ambiguity
        score = score_prompt_ambiguity(user_input)
        if score >= _REFINE_THRESHOLD:
            return f"[arka:refine-suggested] score={score}/100 — {_REFINE_TEXT}"
    except Exception:
        pass
    return ""


def _jev_refine_hint(outcome: Outcome) -> str:
    from core.decisions.sites.prompt import REFINE_GAPS

    vague = outcome.answers.get("vague")
    missing = outcome.answers.get("missing")
    p = _fmt_p(vague.noul if vague is not None else None)
    # Allowlist, never the raw answer: Jev's text reaches the model.
    choice = missing.choice if missing is not None else None
    gap = choice if choice in REFINE_GAPS else "unknown"
    return f"[arka:refine-suggested] source=jev p={p} missing={gap} — {_REFINE_TEXT}"


_SAFE_TOKEN_RE = re.compile(r"[a-z0-9_-]{1,32}")
_SAFE_REASON_RE = re.compile(r"[a-z0-9_:.-]{1,48}")


def _safe_token(value: object, pattern: re.Pattern[str] = _SAFE_TOKEN_RE) -> str:
    """``value`` when it is a short plain token, else ``unknown``.

    Every marker field derived from a decision goes through here (or an
    allowlist): a Jev answer is untrusted text, and a newline in it would
    forge a line such as ``[ARKA:...]`` in the model's context.
    """
    if isinstance(value, str) and pattern.fullmatch(value):
        return value
    return "unknown"


def _fmt_p(value: object) -> str:
    """A probability we format ourselves (0.00-1.00), else ``n/a``."""
    if isinstance(value, int | float) and not isinstance(value, bool) and 0 <= value <= 1:
        return f"{value:.2f}"
    return "n/a"


def _refine_heuristic(user_input: str) -> bool:
    """The score half of the refine hint, as the ``refine`` site's heuristic."""
    try:
        from core.forge.complexity import score_prompt_ambiguity
        return score_prompt_ambiguity(user_input) >= _REFINE_THRESHOLD
    except Exception:
        return False


def _workflow_section(
    user_input: str, session_id: str, budget: _Budget, outcomes: Mapping[str, Outcome]
) -> tuple[str, str]:
    """(workflow directive, refine hint). ``creation-intent`` is
    escalate-only, so its outcome can add the directive, never drop it."""
    creation = outcomes.get("creation-intent")
    if creation is not None:
        required = bool(creation.value)
    else:
        required = bool(user_input) and _wf_classify(user_input)
    if not required:
        return "", ""
    _wf_mark_required(session_id)
    refine_hint = ""
    if (
        not user_input.strip().startswith("/")
        and not _names_concrete_target(user_input)
    ):
        refine_hint = budget.run("refine-score", lambda: _refine_hint(
            user_input, outcomes.get("refine")
        ))
    return _WORKFLOW_DIRECTIVE, refine_hint


# ─── Section 3.5: typed decisions (JEV Decisions Layer PR1) ──────────────

_DECISIONS_HOOK = "user-prompt-submit"
# The sites this stage asks (PR1's four prompt sites + PR2's three
# dispatch sites). ``_decisions_live`` scopes the liveness check to them,
# so a live bash-effect or Forge site never wakes this stage.
UPS_SITE_NAMES: tuple[str, ...] = (
    "topic-drift", "refine", "creation-intent", "route",
    "dispatch-role", "subagent-discipline", "skill-hints",
)
# Outcome reasons that mean Jev was reachable (answered, abstained,
# was overruled, or was never asked). Anything else on an ``act`` site is
# an unavailability, recorded in hook-degraded.jsonl.
_JEV_REACHED = frozenset({"jev", "abstain", "downgrade-blocked", "shadow", "off"})


def _prompt_decisions(
    user_input: str, transcript_path: str, session_id: str, budget: _Budget
) -> dict[str, Outcome]:
    """Jev outcomes for the four prompt sites, or {}.

    Inactive (every site off, bypass, or no key) → {} with no stage
    recorded, so the turn is byte-identical to one without the layer.
    Past the deadline the stage is skipped and named in [arka:degraded].
    Never raises: an internal error is recorded and yields {}.
    """
    try:
        from core.decisions.config import load_decisions_config

        cfg = load_decisions_config()
        if not user_input or not _decisions_live(cfg):
            return {}
        result = budget.run("decisions", lambda: _decide_prompt(
            user_input, transcript_path, session_id, budget, cfg
        ))
    except Exception as exc:
        record_degraded(_DECISIONS_HOOK, "decisions-internal", type(exc).__name__)
        return {}
    return result if isinstance(result, dict) else {}


def _decisions_live(cfg: Any) -> bool:
    """``engine.active(cfg, names=UPS_SITE_NAMES)`` without importing the
    engine (~35 ms of imports a keyless turn would otherwise pay). Parity
    pinned by test."""
    from core.decisions.config import site_mode
    from core.decisions.registry import SITES
    from core.decisions.transport import resolve_transport

    sites = [SITES[name] for name in UPS_SITE_NAMES if name in SITES]
    if not any(site_mode(cfg, site) != "off" for site in sites):
        return False
    return resolve_transport(cfg) is not None


def _decide_prompt(
    user_input: str,
    transcript_path: str,
    session_id: str,
    budget: _Budget,
    cfg: DecisionsConfig,
) -> dict[str, Outcome]:
    from core.decisions.engine import decide
    from core.decisions.sites.prompt import prompt_state
    from core.decisions.transport import configured_model
    from core.hooks import ups_dispatch

    prior = _recent_user_messages(transcript_path)
    menu = ups_dispatch.build_skill_menu(user_input, resolve_arkaos_root())
    calls = _prompt_site_calls(user_input, prior) + ups_dispatch.skill_calls(menu)
    if not calls:
        return {}
    model = configured_model()
    state = ups_dispatch.turn_state(
        prompt_state(user_input, prior), user_input, menu.candidates if menu else [])
    outcomes = decide(
        calls, state, session_id=session_id,
        timeout_ms=budget.remaining_ms(cfg.hook_timeout_ms), model=model,
    )
    _repair_skill_hint(outcomes, menu, session_id, budget, cfg, model)
    _record_unavailable(outcomes)
    return outcomes


def _repair_skill_hint(
    outcomes: dict[str, Outcome],
    menu: SkillMenu | None,
    session_id: str,
    budget: _Budget,
    cfg: DecisionsConfig,
    model: str | None,
) -> None:
    """Re-ask skill-hints, once, with the menu of the department Jev
    routed to (``ups_dispatch.repair_dept`` says when). Bounded by what is
    left of the same budget; the second call stays in the ``decisions``
    stage, so the skip list never changes."""
    from core.decisions.config import site_mode
    from core.decisions.engine import decide
    from core.decisions.site import SiteCall
    from core.decisions.sites.dispatch import SKILL_HINT, skill_state
    from core.hooks import ups_dispatch

    dept = ups_dispatch.repair_dept(outcomes, menu, site_mode(cfg, SKILL_HINT) == "act")
    candidates = menu.for_dept(dept) if dept and menu else []
    if not menu or not candidates or candidates == menu.candidates:
        return
    repaired = decide(
        [SiteCall(SKILL_HINT, menu.heuristic)], skill_state(menu.prompt, candidates),
        session_id=session_id, timeout_ms=budget.remaining_ms(cfg.hook_timeout_ms), model=model,
    )
    outcomes["skill-hints"] = repaired["skill-hints"]


def _prompt_site_calls(user_input: str, prior: list[str]) -> list[SiteCall]:
    """One SiteCall per site whose precondition holds, each carrying the
    heuristic value the hook would act on without Jev."""
    from core.decisions.site import SiteCall
    from core.decisions.sites.prompt import CREATION_INTENT, REFINE, ROUTE, TOPIC_DRIFT
    from core.hooks.ups_dispatch import dispatch_site_calls
    from core.synapse.layers import keyword_department, prefix_department

    calls: list[SiteCall] = []
    if prior:
        shifted = keyword_topic_shift(user_input, "\n".join(prior))
        calls.append(SiteCall(TOPIC_DRIFT, shifted))
    if user_input.lstrip()[:1] not in ("/", "!"):
        creation = _wf_classify(user_input)
        calls.append(SiteCall(CREATION_INTENT, creation))
        if creation and not _names_concrete_target(user_input):
            calls.append(SiteCall(REFINE, _refine_heuristic(user_input)))
        calls.extend(dispatch_site_calls(user_input))
    if prefix_department(user_input) is None:
        calls.append(SiteCall(ROUTE, keyword_department(user_input) or ""))
    return calls


def _record_unavailable(outcomes: Mapping[str, Outcome]) -> None:
    reasons = sorted({
        o.reason for o in outcomes.values()
        if o.mode == "act" and o.reason not in _JEV_REACHED
    })
    if reasons:
        record_degraded(_DECISIONS_HOOK, "decisions-unavailable", ",".join(reasons))


def _known_dept(value: object) -> str | None:
    from core.synapse.layers import DEPARTMENT_PATTERNS

    return value if isinstance(value, str) and value in DEPARTMENT_PATTERNS else None


def _route_hint(outcomes: Mapping[str, Outcome]) -> dict[str, Any] | None:
    """The bridge's ``route_hint`` when the route site acted on a KNOWN dept."""
    route = outcomes.get("route")
    if route is None or route.acted_on != "jev":
        return None
    dept = _known_dept(route.value)
    return {"dept": dept, "p": route.confidence, "source": "jev"} if dept else None


def _route_marker(outcomes: Mapping[str, Outcome]) -> str:
    """``[arka:route-confidence]`` for an ``act`` route site; "" otherwise
    (shadow and off never change the output). Fields are allowlisted."""
    route = outcomes.get("route")
    if route is None or route.mode != "act":
        return ""
    dept = _known_dept(route.value) if route.acted_on == "jev" else None
    if dept:
        return f"[arka:route-confidence] dept={dept} p={_fmt_p(route.confidence)} source=jev"
    if route.acted_on == "jev":
        reason = "jev-none" if route.value == "" else "jev-invalid"
    else:
        reason = _safe_token(route.reason, _SAFE_REASON_RE)
    fallback = _known_dept(route.heuristic) or "none"
    return f"[arka:route-confidence] dept={fallback} source=keyword reason={reason}"


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
    with contextlib.suppress(OSError):
        nudge_file.unlink(missing_ok=True)
    return nudge


# ─── Section 11: metrics ─────────────────────────────────────────────────


def _log_metrics(
    elapsed_ms: int, user_input: str, budget: _Budget | None = None
) -> None:
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
            row = {
                "hook": "user-prompt-submit-v2",
                "ms": elapsed_ms,
                "at_mentions": at_mentions,
            }
            if budget is not None:
                row["degraded"] = budget.skipped
                row["stage_ms"] = budget.stage_ms
            fh.write(json.dumps(row) + "\n")
    except OSError:
        pass


# ─── Deadline budget (PR-A3) ─────────────────────────────────────────────


_BUDGET_RESERVE_MS = 500


class _Budget:
    """Monotonic deadline for the per-turn hook (PR-A3).

    The runtime kills UserPromptSubmit at its timeout and the turn
    loses all hook-injected context (8 hook_cancelled on record at the
    former 10s ceiling, raised to 20s here). Degrading is strictly
    better: once the deadline passes, the budgeted optional stages
    (token-hygiene, refine-score, cognitive-hits, nudges)
    are skipped, the assembled context ships, and the turn carries
    [arka:degraded] so the cut is visible. The Synapse bridge is never skipped — it is the core the
    other stages decorate — and the tag/plan-approval work around it
    is not budgeted. A recorded skip means the stage was not
    EVALUATED, not that content was lost: a skipped stage might have
    produced nothing anyway. Budget via ARKA_UPS_BUDGET_MS (default
    6000 ms).
    """

    def __init__(self, start: float) -> None:
        try:
            budget_ms = int(os.environ.get("ARKA_UPS_BUDGET_MS", "6000"))
        except ValueError:
            budget_ms = 6000
        self.deadline = start + budget_ms / 1000.0
        self.skipped: list[str] = []
        self.stage_ms: dict[str, int] = {}

    def time(self, stage: str, fn: Callable[[], _T]) -> _T:
        """Run a stage unconditionally, recording its duration."""
        t0 = time.monotonic()
        result = fn()
        self.stage_ms[stage] = int((time.monotonic() - t0) * 1000)
        return result

    def run(self, stage: str, fn: Callable[[], _T]) -> _T | str:
        """Run an optional stage inside the budget, or record the skip
        (a skipped stage returns "")."""
        if time.monotonic() > self.deadline:
            self.skipped.append(stage)
            return ""
        return self.time(stage, fn)

    def remaining_ms(self, cap: int) -> int:
        """Milliseconds a network stage may spend: at most ``cap``, and
        never the last 500 ms reserved for the stages that follow."""
        left = int((self.deadline - time.monotonic()) * 1000) - _BUDGET_RESERVE_MS
        return max(0, min(cap, left))

    def over(self, stage: str) -> bool:
        """True when the deadline has passed; records the skip when it
        has."""
        if time.monotonic() > self.deadline:
            self.skipped.append(stage)
            return True
        return False

    def marker(self) -> str:
        # The names, not a count: "layers=N" reads as Synapse layers
        # (the budget never cuts one — the bridge is never skipped), and
        # a bare number would hide WHICH work was cut. Self-describing
        # at no cost.
        if not self.skipped:
            return ""
        return (
            f"\n[arka:degraded] skipped={','.join(self.skipped)}"
            f" reason=budget"
        )


def _nudges_pending(session_id: str) -> bool:
    """True when at least one one-shot nudge file awaits this session.

    The id reaches this gate straight from stdin, and it becomes a
    filesystem path: "../<dir>/victim" read a file the hook does not
    own into the model context and then unlinked it (CWE-22, reproduced
    2026-07-28). This gate now refuses anything ``safe_session_id``
    would refuse, which also stops the three reads it guards.
    """
    if safe_session_id(session_id) is None:
        return False
    return any(
        (arkaos_temp_dir(subdir) / f"{session_id}.json").is_file()
        for subdir in ("arkaos-cite", "arkaos-meta", "arkaos-closing")
    )


def _bridge_context(
    root: str,
    user_input: str,
    session_id: str,
    cwd: str,
    budget: _Budget,
    outcomes: Mapping[str, Outcome] | None = None,
) -> str:
    """Synapse bridge output decorated with tags, or the fallback, plus
    the ``[arka:route-confidence]`` line when the route site acts."""
    outcomes = outcomes or {}
    # Positional on purpose: tests stub _run_bridge with ``lambda *a``.
    python_result = budget.time("bridge", lambda: _run_bridge(
        root, user_input, session_id, cwd, _route_hint(outcomes),
        _skill_hint(root, outcomes),
    ))
    context = _decorate(python_result) if python_result else _fallback_context()
    markers = _decision_markers(outcomes)
    return f"{context}\n{markers}" if markers else context


def _skill_hint(root: str, outcomes: Mapping[str, Outcome]) -> dict[str, Any] | None:
    """The bridge's ``skill_hint`` when skill-hints acted on a registry id."""
    if "skill-hints" not in outcomes:
        return None
    from core.hooks.ups_dispatch import load_commands, skill_hint_payload

    return skill_hint_payload(outcomes, load_commands(root))


def _decision_markers(outcomes: Mapping[str, Outcome]) -> str:
    """The route, dispatch-role and subagent-discipline lines, in that
    order; each is "" unless its ``act`` site has something to say."""
    lines = [_route_marker(outcomes)]
    if outcomes:
        from core.hooks.ups_dispatch import discipline_marker, dispatch_role_marker

        lines += [dispatch_role_marker(outcomes, _fmt_p), discipline_marker(outcomes, _fmt_p)]
    return "\n".join(line for line in lines if line)


def _decorate(python_result: str) -> str:
    """Workflow-state + Forge tags appended to the bridge context."""
    wf_tag = _workflow_tag()
    if wf_tag:
        python_result = f"{python_result} {wf_tag}"
    forge_tag = _forge_tag()
    if forge_tag:
        python_result = f"{python_result} {forge_tag}"
    # Gate Economy PR-10: the KB overlap snippets are already injected
    # by Synapse L3.5 (same KBSessionCache.get_overlap, same threshold,
    # same turn) — the former _kb_auto_inject prepended the identical
    # ~150 tokens a second time. One injection point remains: L3.5.
    return python_result


def _classify_plan_reply(session_id: str, user_input: str) -> None:
    """Interaction Reform PR3 — when the previous turn ended at Gate 2
    (plan on the table), classify THIS message as approval/rejection.
    UserPromptSubmit runs before the turn's tool calls, so the token is
    visible to the PreToolUse enforcer with no marker-invisibility
    problem. Never blocks the hook, and is never budgeted — approval
    state is enforcement semantics, not decoration.
    """
    try:
        from core.workflow import plan_approval
        if session_id and user_input and plan_approval.is_presented(session_id):
            verdict = plan_approval.classify_reply(
                user_input, has_creation_verb=_wf_classify(user_input)
            )
            if verdict == "approve":
                plan_approval.mark_approved(
                    session_id, source="text", excerpt=user_input
                )
            elif verdict == "reject":
                plan_approval.mark_rejected(session_id)
    except Exception:
        pass


def _collect_nudges(
    session_id: str, surface_nudges: bool, budget: _Budget
) -> tuple[str, str, str]:
    """(kb-cite, meta-tag, closing-marker) one-shot nudges.

    over() only runs when a nudge file actually exists: one-shot nudges
    are empty on most turns, and recording a skip for work that had
    nothing to do would inflate the degraded telemetry the 6000 ms
    default will be judged on.
    """
    if not (
        session_id and surface_nudges and _nudges_pending(session_id)
        and not budget.over("nudges")
    ):
        return "", "", ""
    return (
        _one_shot_nudge("arkaos-cite", session_id),
        _one_shot_nudge("arkaos-meta", session_id),
        _one_shot_nudge("arkaos-closing", session_id),
    )


def _assemble_output(
    sync_notice: str,
    workflow_directive: str,
    python_result: str,
    hygiene: str,
    refine_hint: str,
    nudges: tuple[str, str, str],
    context_hits: str,
    budget: _Budget,
) -> str:
    """Assembly order identical to the bash version."""
    out = (
        f"{sync_notice}{_ROUTE_REMINDER}{workflow_directive} {python_result}"
    )
    if hygiene:
        out = f"{out} {hygiene}"
    if refine_hint:
        out = f"{out}\n{refine_hint}"
    for nudge in nudges:
        if nudge:
            out = f"{out}\n{nudge}"
    if context_hits:
        out = f"{out}\n{context_hits}"
    return f"{out}{budget.marker()}"


# ─── Entry point ─────────────────────────────────────────────────────────


def main(stdin_json: dict | None = None, raw: str = "") -> int:
    start = time.monotonic()
    if stdin_json is None:
        stdin_json, raw = read_stdin_json()

    migration = _v1_migration_notice()
    if migration is not None:
        emit_additional_context("UserPromptSubmit", migration)
        return 0

    sync_notice = _sync_notice()

    root = resolve_arkaos_root()
    ensure_root_on_path(root)
    with contextlib.suppress(OSError):
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # Claude Code sends the user's text under "prompt" (UserPromptSubmit
    # hook schema); "userInput"/"message" cover other runtimes. Missing
    # "prompt" here meant the raw JSON line fell through as user_input,
    # so L1/L5/L2.5 computed on JSON garbage every turn (found 2026-07-09
    # by the un-swallowed orchestrator bats test).
    user_input = (
        get_str(stdin_json, "prompt")
        or get_str(stdin_json, "userInput")
        or get_str(stdin_json, "message")
    )
    session_id = get_str(stdin_json, "session_id")
    effort_level = get_str(stdin_json, "effort", "level") or os.environ.get(
        "CLAUDE_EFFORT", ""
    )
    surface_nudges = (effort_level or "high") not in ("low", "medium")

    _invalidate_turn_caches(session_id)

    if not user_input:
        user_input = raw[:2000]

    budget = _Budget(start)
    transcript_path = get_str(stdin_json, "transcript_path")

    # Before the bridge: an acted route decision must reach Synapse L1.
    outcomes = _prompt_decisions(user_input, transcript_path, session_id, budget)
    python_result = _bridge_context(
        root, user_input, session_id, get_str(stdin_json, "cwd"), budget,
        outcomes,
    )

    drift = outcomes.get("topic-drift")
    hygiene = budget.run("token-hygiene", lambda: _token_hygiene(
        user_input, transcript_path, None if drift is None else bool(drift.value)
    ))

    workflow_directive, refine_hint = _workflow_section(
        user_input, session_id, budget, outcomes
    )

    # Enforcement semantics stay on the regex (_wf_classify), never Jev.
    _classify_plan_reply(session_id, user_input)

    context_hits = budget.run(
        "cognitive-hits", lambda: _cognitive_hits(session_id)
    )

    out = _assemble_output(
        sync_notice, workflow_directive, python_result, hygiene,
        refine_hint, _collect_nudges(session_id, surface_nudges, budget),
        context_hits, budget,
    )
    emit_additional_context("UserPromptSubmit", out)

    _log_metrics(int((time.monotonic() - start) * 1000), user_input, budget)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        # Fail open with the minimal constitution context.
        emit_additional_context("UserPromptSubmit", _L0_FALLBACK)
        raise SystemExit(0) from None
