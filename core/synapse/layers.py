"""Synapse layer definitions — the 9 context layers.

Each layer extracts a specific type of context and compresses it
for injection into the prompt. Layers are pluggable and ordered.

Layer Architecture:
  L0:   Constitution       — Compressed governance rules (TTL: 300s)
  L1:   Department         — Detected department from input (no cache)
  L2:   Agent              — Agent profile + last gotchas (TTL: 30s)
  L2.5: KBContext          — Obsidian notes relevant to prompt (no cache)
  L3:   Project            — Active project context (TTL: 30s)
  L3.5: KnowledgeRetrieval — Semantic search from vector DB (TTL: 30s)
  L4:   Branch             — Current git branch (no cache)
  L5:   Command Hints      — Matching commands from registry (TTL: 30s)
  L6:   Quality Gate       — QG status and last verdicts (TTL: 60s)
  L7:   Time               — Time-of-day signal (no cache)

Module layout (v4.21.0 split): the layer contract lives in
layers_base.py; the L2.5 KB layer and its helpers live in
layers_kb.py. Both are re-exported here so existing
`core.synapse.layers` imports keep working.
"""

import os
import re
import time
from typing import Any

from core.synapse.layers_base import Layer, LayerResult, PromptContext

__all__ = [
    "AgentLayer",
    "BranchLayer",
    "CommandHintsLayer",
    "ConstitutionLayer",
    "DepartmentLayer",
    "ForgeContextLayer",
    "KBContextLayer",
    "KnowledgeRetrievalLayer",
    "Layer",
    "LayerResult",
    "ProjectLayer",
    "PromptContext",
    "QualityGateLayer",
    "SessionContextLayer",
]


# --- L0: Constitution ---


class ConstitutionLayer(Layer):
    """L0: Compressed Constitution rules. Highest priority, longest cache."""

    def __init__(self, compressed: str = "") -> None:
        self._compressed = compressed

    @property
    def id(self) -> str:
        return "L0"

    @property
    def name(self) -> str:
        return "Constitution"

    @property
    def cache_ttl(self) -> int:
        return 300

    @property
    def priority(self) -> int:
        return 0

    def set_compressed(self, compressed: str) -> None:
        self._compressed = compressed

    def compute(self, ctx: PromptContext) -> LayerResult:
        start = time.time()
        content = self._compressed
        ms = int((time.time() - start) * 1000)
        return LayerResult(
            layer_id=self.id,
            tag="[Constitution]",
            content=content,
            tokens_est=len(content.split()),
            compute_ms=ms,
            cached=False,
        )


# --- L1: Department Detection ---

DEPARTMENT_PATTERNS: dict[str, str] = {
    "dev": (
        r"\b("
        r"build|code|feature|deploy|test|review|scaffold|"
        r"debug|refactor|api|migration|stack|implement|fix|"
        r"bug)\b"
    ),
    "marketing": (
        r"\b("
        r"social|content|campaign|post|instagram|linkedin|"
        r"twitter|tiktok|seo|marketing|ads|email.?campaign|"
        r"growth|viral)\b"
    ),
    "finance": (
        r"\b("
        r"budget|invoice|revenue|forecast|profit|loss|roi|"
        r"margin|cash.?flow|financial|invest|valuation|"
        r"pricing)\b"
    ),
    "ecom": (
        r"\b("
        r"store|product|shop|shopify|ecommerce|catalog|"
        r"inventory|cart|checkout|pricing|marketplace)\b"
    ),
    "strategy": (
        r"\b("
        r"strategy|brainstorm|market|swot|competitors?|"
        r"roadmap|pivot|growth|porter|blue.?ocean|"
        r"positioning)\b"
    ),
    "ops": r"\b(task|automate|meeting|workflow|process|schedule|sop|integration|zapier|n8n)\b",
    "kb": r"\b(learn|persona|knowledge|youtube|transcribe|article|research|zettelkasten|note)\b",
    "brand": (
        r"\b("
        r"brand|logo|colors|palette|mockup|photoshoot|brand.?identity|"
        r"brand.?guide|mood.?board|naming|visual.?design|motion|ux|ui|"
        r"wireframe)\b"
    ),
    "saas": r"\b(saas|micro.?saas|plg|freemium|churn|mrr|arr|subscription|onboarding|metrics)\b",
    "landing": (
        r"\b("
        r"landing|funnel|copy|headline|offer|launch|"
        r"affiliate|webinar|conversion|sales.?page)\b"
    ),
    "community": (
        r"\b("
        r"community|group|membership|discord|"
        r"telegram|skool|circle|gamification|"
        r"engagement)\b"
    ),
    "content": r"\b(viral|hook|script|repurpose|youtube|tiktok|reels|shorts|newsletter|creator)\b",
    "pm": r"\b(sprint|backlog|standup|retro|scrum|kanban|story|estimate|roadmap|agile)\b",
    "lead": (
        r"\b("
        r"leadership|delegation|1on1|feedback|"
        r"culture|hiring|performance.?review|"
        r"team.?build)\b"
    ),
    "sales": (
        r"\b("
        r"pipeline|proposal|discovery.?call|objection|negotiate|"
        r"deal|close|prospect|spin|challenger|cold.?email|"
        r"outreach)\b"
    ),
    "org": (
        r"\b("
        r"org.?design|hiring.?plan|onboarding|remote|"
        r"meeting.?optimize|compensation|"
        r"decision.?framework)\b"
    ),
}


class DepartmentLayer(Layer):
    """L1: Detect department from user input via keyword matching."""

    @property
    def id(self) -> str:
        return "L1"

    @property
    def name(self) -> str:
        return "Department"

    @property
    def input_sensitive(self) -> bool:
        return True

    @property
    def priority(self) -> int:
        return 10

    def compute(self, ctx: PromptContext) -> LayerResult:
        start = time.time()
        text = ctx.user_input.lower()

        # Check for explicit command prefix first
        # Use [-\w] to handle hyphenated commands like /arka-do
        prefix_match = re.match(r"^/([-\w]+)\s", text)
        if prefix_match:
            prefix = prefix_match.group(1)
            dept_map = {
                "dev": "dev",
                "mkt": "marketing",
                "fin": "finance",
                "strat": "strategy",
                "ops": "ops",
                "ecom": "ecom",
                "kb": "kb",
                "brand": "brand",
                "saas": "saas",
                "landing": "landing",
                "community": "community",
                "content": "content",
                "pm": "pm",
                "lead": "lead",
                "sales": "sales",
                "org": "org",
                "do": "orchestrator",
                "arka-do": "orchestrator",
            }
            if prefix in dept_map:
                dept = dept_map[prefix]
                ms = int((time.time() - start) * 1000)
                if dept == "orchestrator":
                    return LayerResult(
                        layer_id=self.id,
                        tag="",
                        content="",
                        tokens_est=0,
                        compute_ms=ms,
                        cached=False,
                    )
                return LayerResult(
                    layer_id=self.id,
                    tag=f"[dept:{dept}]",
                    content=dept,
                    tokens_est=1,
                    compute_ms=ms,
                    cached=False,
                )

        # Pattern matching on input text
        scores: dict[str, int] = {}
        for dept, pattern in DEPARTMENT_PATTERNS.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                scores[dept] = len(matches)

        dept = max(scores, key=scores.get) if scores else ""
        tag = f"[dept:{dept}]" if dept else ""

        ms = int((time.time() - start) * 1000)
        return LayerResult(
            layer_id=self.id,
            tag=tag,
            content=dept,
            tokens_est=1,
            compute_ms=ms,
            cached=False,
        )


# --- L2: Agent Context ---


class AgentLayer(Layer):
    """L2: Active agent profile and recent gotchas."""

    def __init__(self, agents_registry: dict[str, dict] | None = None) -> None:
        self._registry = agents_registry or {}

    @property
    def id(self) -> str:
        return "L2"

    @property
    def name(self) -> str:
        return "Agent"

    @property
    def cache_ttl(self) -> int:
        return 30

    @property
    def priority(self) -> int:
        return 20

    def compute(self, ctx: PromptContext) -> LayerResult:
        start = time.time()
        agent_id = ctx.active_agent
        if not agent_id:
            ms = int((time.time() - start) * 1000)
            return LayerResult(
                layer_id=self.id,
                tag="",
                content="",
                tokens_est=0,
                compute_ms=ms,
                cached=False,
            )

        agent = self._registry.get(agent_id, {})
        disc = agent.get("disc", "")
        tag = f"[agent:{agent_id} disc:{disc}]"

        ms = int((time.time() - start) * 1000)
        return LayerResult(
            layer_id=self.id,
            tag=tag,
            content=agent_id,
            tokens_est=3,
            compute_ms=ms,
            cached=False,
        )


# --- L3: Project Context ---


class ProjectLayer(Layer):
    """L3: Active project name and stack."""

    @property
    def id(self) -> str:
        return "L3"

    @property
    def name(self) -> str:
        return "Project"

    @property
    def cache_ttl(self) -> int:
        return 30

    @property
    def priority(self) -> int:
        return 30

    def compute(self, ctx: PromptContext) -> LayerResult:
        start = time.time()
        parts = []
        if ctx.project_name:
            parts.append(f"project:{ctx.project_name}")
        if ctx.project_stack:
            parts.append(f"stack:{ctx.project_stack}")

        tag = f"[{' '.join(parts)}]" if parts else ""
        ms = int((time.time() - start) * 1000)
        return LayerResult(
            layer_id=self.id,
            tag=tag,
            content=ctx.project_name or "",
            tokens_est=len(parts),
            compute_ms=ms,
            cached=False,
        )


# --- L4: Git Branch ---


class BranchLayer(Layer):
    """L4: Current git branch (hidden for main/master/dev)."""

    @property
    def id(self) -> str:
        return "L4"

    @property
    def name(self) -> str:
        return "Branch"

    @property
    def priority(self) -> int:
        return 40

    def compute(self, ctx: PromptContext) -> LayerResult:
        start = time.time()
        branch = ctx.git_branch
        # Hide main/master/dev branches
        tag = "" if branch in ("main", "master", "dev", "") else f"[branch:{branch}]"

        ms = int((time.time() - start) * 1000)
        return LayerResult(
            layer_id=self.id,
            tag=tag,
            content=branch,
            tokens_est=1 if tag else 0,
            compute_ms=ms,
            cached=False,
        )


# --- L5: Command Hints ---


# PR-A4: department slug -> deployed hub-skill directory. Both slug
# vocabularies reach this layer — the registry department field (which
# says "leadership") and the command-prefix slugs (which say "lead") —
# and both must resolve. Registry values need no key: identity already
# yields the right hub (leadership -> arka-leadership). The keys exist
# for the four prefix slugs whose hub directory differs (mkt, fin,
# strat, lead — the same alias set
# tests/python/test_skill_routing_integrity.py pins) plus the two
# orchestrator entries ("arka" and "do" both belong to the main
# orchestrator skill; /do is the universal router in arka/SKILL.md).
# An unknown department falls back to the identity form — a
# wrong-but-plausible hint beats a crashed layer.
_DEPT_HUB_EXCEPTIONS = {
    "mkt": "arka-marketing",
    "fin": "arka-finance",
    "strat": "arka-strategy",
    "lead": "arka-leadership",
    "arka": "arka",
    "do": "arka",
}


def _hub_skill(department: str) -> str:
    return _DEPT_HUB_EXCEPTIONS.get(department, f"arka-{department}")


# Project-shape signals: a cwd carrying ANY of these file groups (every
# file in a group present) forces the command's hint regardless of the
# prompt text — "working inside a HyperFrames project" is a route.
PROJECT_SIGNALS: dict[str, tuple[tuple[str, ...], ...]] = {
    "content-hyperframes": (
        ("hyperframes.json",),
        ("BRIEF.md", "STORYBOARD.md"),
    ),
}

# The score slot exists only so signal entries share the
# (score, command, department) tuple shape of _score_commands. Nothing
# sorts on it in the merge path: _hint_tag and compute discard the score,
# and precedence comes from _merge_hints concatenating signal entries
# before the keyword ones.
_SIGNAL_SCORE = 10_000


def _hint_department(cmd: dict) -> str:
    """Department for the hint's hub skill.

    Falls back to the command prefix ("/dev feature" -> "dev",
    "/arka-do" -> "arka") for registry entries that predate the
    department field — an approximate hub beats no hint.
    """
    dept = str(cmd.get("department", ""))
    if dept:
        return dept
    prefix = str(cmd.get("command", "")).lstrip("/").split(" ")[0]
    return prefix.split("-")[0]


def _group_present(cwd: str, group: tuple[str, ...]) -> bool:
    """True when EVERY file of the group sits directly in ``cwd``."""
    return all(os.path.isfile(os.path.join(cwd, name)) for name in group)


def _project_signal_ids(cwd: str) -> list[str]:
    """Registry command ids whose project shape matches the hook cwd.

    Looks at ``cwd`` itself only — no parent walk — and never raises:
    ``PromptContext.cwd`` is typed ``str``, and for str input the
    ``os.path`` predicates (``isdir``/``isfile``) are exception-free —
    they swallow OSError and ValueError internally — so an empty cwd, a
    directory that does not exist, or an unreadable path yields no signal
    and L5 degrades to plain keyword scoring. No try/except is needed.
    """
    if not cwd or not os.path.isdir(cwd):
        return []
    return [
        cmd_id
        for cmd_id, groups in PROJECT_SIGNALS.items()
        if any(_group_present(cwd, group) for group in groups)
    ]


def _signal_commands(
    commands: list[dict[str, Any]], ids: list[str]
) -> list[tuple[int, str, str]]:
    """Scored tuples for the signalled ids, shaped like _score_commands.

    An id the registry does not carry is skipped in silence: a signal
    may only surface a command that actually exists, never invent one.
    """
    wanted = set(ids)
    return [
        (_SIGNAL_SCORE, cmd.get("command", ""), _hint_department(cmd))
        for cmd in commands
        if cmd.get("id") in wanted
    ]


def _merge_hints(
    signal: list[tuple[int, str, str]],
    keyword: list[tuple[int, str, str]],
) -> list[tuple[int, str, str]]:
    """Signal hints first, keyword hints after, de-duped by command text."""
    seen: set[str] = set()
    merged: list[tuple[int, str, str]] = []
    for entry in [*signal, *keyword]:
        if entry[1] in seen:
            continue
        seen.add(entry[1])
        merged.append(entry)
    return merged


def _score_commands(
    commands: list[dict[str, Any]], text: str
) -> list[tuple[int, str, str]]:
    """Keyword-score the registry commands against the prompt text,
    best score first; zero-score commands never qualify."""
    scored = []
    for cmd in commands:
        keywords = cmd.get("keywords", [])
        score = sum(1 for kw in keywords if kw.lower() in text)
        if score > 0:
            scored.append((
                score,
                cmd.get("command", ""),
                _hint_department(cmd),
            ))
    scored.sort(reverse=True)
    return scored


def _hint_tag(top: list[tuple[int, str, str]]) -> str:
    """Render the imperative hint tag for the top-scored commands.

    EACH hint pairs the command with ITS OWN department's hub — the
    top-2 can legitimately span two departments ("standup color
    palette" matches /brand colors AND /pm story on the live registry),
    and a hint whose hub belongs to the other command is a dead
    instruction (QG A4, Francisca B1).
    """
    return " ".join(
        f"[arka:skill-hint] Skill({_hub_skill(dept)}) -> {command}"
        for _, command, dept in top
    )


class CommandHintsLayer(Layer):
    """L5: Matching commands from the registry for non-explicit requests.

    PR-A4: hints are IMPERATIVE — `[arka:skill-hint] Skill(arka-dev) ->
    /dev feature <description>` names the exact tool call that fulfils
    the route. The old `[hint:/cmd]` form was declarative and routinely
    ignored: the model announced the squad in prose and the skill's
    content never entered context.

    Beyond the prompt words, the layer routes by PROJECT SHAPE: when the
    hook cwd carries the files that identify a project kind
    (``PROJECT_SIGNALS`` — e.g. a HyperFrames video-as-code project ships
    ``hyperframes.json``, or ``BRIEF.md`` + ``STORYBOARD.md``), that
    command is hinted even when the prompt matches no keyword. An
    operator standing inside such a project asks "render the intro" or
    "muda o segundo plano" — vocabulary the registry cannot enumerate —
    and keyword-only scoring left the specialist route silent while the
    generic assistant answered. Signal hints lead the merged list and the
    top-2 cap still holds, so a signal costs at most one keyword slot.
    """

    def __init__(self, commands: list[dict] | None = None) -> None:
        self._commands = commands or []

    @property
    def id(self) -> str:
        return "L5"

    @property
    def name(self) -> str:
        return "CommandHints"

    @property
    def input_sensitive(self) -> bool:
        return True

    @property
    def cache_ttl(self) -> int:
        return 30

    @property
    def priority(self) -> int:
        return 50

    def compute(self, ctx: PromptContext) -> LayerResult:
        start = time.time()
        text = ctx.user_input.lower()

        # Skip if already an explicit command — EXCEPT /arka-do which needs hints
        # /do-style commands should still get command hints for sub-commands
        if text.startswith("/") and not text.startswith("/arka-do"):
            ms = int((time.time() - start) * 1000)
            return LayerResult(
                layer_id=self.id,
                tag="",
                content="",
                tokens_est=0,
                compute_ms=ms,
                cached=False,
            )

        signal = _signal_commands(
            self._commands, _project_signal_ids(ctx.cwd)
        )
        top = _merge_hints(
            signal, _score_commands(self._commands, text)
        )[:2]
        hints = [command for _, command, _ in top]

        tags = _hint_tag(top)
        ms = int((time.time() - start) * 1000)
        return LayerResult(
            layer_id=self.id,
            tag=tags,
            content=" ".join(hints),
            tokens_est=len(hints) * 2,
            compute_ms=ms,
            cached=False,
        )


# --- L6: Quality Gate Status ---


class QualityGateLayer(Layer):
    """L6: Current quality gate status and recent verdicts."""

    @property
    def id(self) -> str:
        return "L6"

    @property
    def name(self) -> str:
        return "QualityGate"

    @property
    def cache_ttl(self) -> int:
        return 60

    @property
    def priority(self) -> int:
        return 60

    def compute(self, ctx: PromptContext) -> LayerResult:
        start = time.time()
        try:
            from core.governance.quality_api import list_approved, list_pending

            pending = list_pending()
            approved = list_approved(limit=3)
        except Exception:
            pending = []
            approved = []

        parts = []
        if pending:
            parts.append(f"{len(pending)} pending")
            titles = [p.get("title", "")[:30] for p in pending[:2]]
            parts.append(f"pending: {'; '.join(titles)}")
        if approved:
            parts.append(f"recent approved: {len(approved)}")

        tag = "[qg:active]"
        content = " | ".join(parts) if parts else "active"
        tokens = len(content.split())

        ms = int((time.time() - start) * 1000)
        return LayerResult(
            layer_id=self.id,
            tag=tag,
            content=content,
            tokens_est=tokens,
            compute_ms=ms,
            cached=False,
        )


# --- L3.5: Knowledge Retrieval ---


class KnowledgeRetrievalLayer(Layer):
    """L3.5: Semantic knowledge retrieval from vector DB.

    Searches the local vector store for chunks relevant to the user's
    input and injects them as context. Gracefully skips if vector store
    is unavailable or empty.
    """

    def __init__(
        self, vector_store: Any = None, max_chunks: int = 3, max_tokens: int = 400
    ) -> None:
        self._store = vector_store
        self._max_chunks = max_chunks
        self._max_tokens = max_tokens

    @property
    def id(self) -> str:
        return "L3.5"

    @property
    def name(self) -> str:
        return "KnowledgeRetrieval"

    @property
    def input_sensitive(self) -> bool:
        return True

    @property
    def session_sensitive(self) -> bool:
        return True

    @property
    def cache_ttl(self) -> int:
        return 30

    @property
    def emits_block(self) -> bool:
        """The retrieved chunks are a real block, not the tag's value.

        `[knowledge:N chunks]` makes a QUANTIFIED claim about content the
        model never received before the content channel existed — the
        loudest unbacked claim in the tag line (QG review). Opting in
        delivers what the tag advertises.
        """
        return True

    @property
    def priority(self) -> int:
        return 35

    def compute(self, ctx: PromptContext) -> LayerResult:
        start = time.time()

        if not self._store or not ctx.user_input:
            return LayerResult(
                layer_id=self.id,
                tag="",
                content="",
                tokens_est=0,
                compute_ms=0,
                cached=False,
            )

        try:
            results = self._store.search(ctx.user_input, top_k=self._max_chunks)
        except Exception:
            return LayerResult(
                layer_id=self.id,
                tag="",
                content="",
                tokens_est=0,
                compute_ms=0,
                cached=False,
            )

        if not results:
            ms = int((time.time() - start) * 1000)
            return LayerResult(
                layer_id=self.id,
                tag="",
                content="",
                tokens_est=0,
                compute_ms=ms,
                cached=False,
            )

        session_id = ctx.extra.get("session_id", "default") if ctx.extra else "default"
        project_path = ctx.cwd or None

        overlapping: list[dict] = []
        try:
            from core.synapse.kb_cache import KBSessionCache

            cache = KBSessionCache(session_id=session_id, project_path=project_path)
            cache.store(ctx.user_input, results)
            overlapping = cache.get_overlap(ctx.user_input, threshold=0.3)
        except Exception:
            pass

        snippets = []
        total_tokens = 0
        for r in results:
            text = r["text"][:200].replace("\n", " ").strip()
            tokens = len(text.split())
            if total_tokens + tokens > self._max_tokens:
                break
            source = r.get("source", "").split("/")[-1] if r.get("source") else ""
            snippet = f"{source}: {text}" if source else text
            snippets.append(snippet)
            total_tokens += tokens

        if not snippets and not overlapping:
            ms = int((time.time() - start) * 1000)
            return LayerResult(
                layer_id=self.id,
                tag="",
                content="",
                tokens_est=0,
                compute_ms=ms,
                cached=False,
            )

        parts: list[str] = []
        if overlapping:
            for o in overlapping[:2]:
                text = o.get("text", "")[:200].replace("\n", " ").strip()
                src = o.get("source", "").split("/")[-1] if o.get("source") else ""
                parts.append(f"[cached] {src}: {text}" if src else f"[cached] {text}")
        parts.extend(snippets)

        # Self-naming, because the content channel delivers this verbatim to
        # the model: an unlabelled `[cached] file.md: …` fragment would read
        # as stray text (the exact defect the opt-in channel exists to avoid).
        content = f"[arka:knowledge] {' | '.join(parts)}" if parts else ""
        chunk_count = len(snippets) + (len(overlapping) if overlapping else 0)
        # RAG honesty (PR-3 v4.1): keyword-degraded results must never be
        # presented as semantic similarity — label the tag explicitly.
        degraded = any(r.get("retrieval") == "keyword-degraded" for r in results)
        tag = f"[knowledge:{chunk_count} chunks]"
        if degraded:
            tag = f"[knowledge:{chunk_count} chunks degraded=keyword]"
        ms = int((time.time() - start) * 1000)
        tokens_est = len(content.split())

        return LayerResult(
            layer_id=self.id,
            tag=tag,
            content=content,
            tokens_est=tokens_est,
            compute_ms=ms,
            cached=False,
        )


# --- L8: Forge Context ---


class ForgeContextLayer(Layer):
    """L8: Active forge plan context — decisions, risks, rejected approaches."""

    @property
    def id(self) -> str:
        return "L8"

    @property
    def name(self) -> str:
        return "ForgeContext"

    @property
    def cache_ttl(self) -> int:
        return 0

    @property
    def priority(self) -> int:
        return 80

    def compute(self, ctx: PromptContext) -> LayerResult:
        start = time.time()
        try:
            from core.forge.persistence import get_active_plan

            plan = get_active_plan()
        except Exception:
            plan = None
        if plan is None:
            return LayerResult(
                layer_id=self.id, tag="", content="", tokens_est=0, compute_ms=0, cached=False
            )
        tag = f"[forge:{plan.id}]"
        parts = [f"Forge plan: {plan.id} ({plan.status.value})"]
        if plan.critic.confidence > 0:
            decisions = []
            for _source, elements in plan.critic.synthesis.items():
                decisions.extend(elements)
            if decisions:
                parts.append(f"Decisions: {'; '.join(decisions[:5])}")
            rejected = [r.element for r in plan.critic.rejected_elements]
            if rejected:
                parts.append(f"Rejected: {'; '.join(rejected[:3])}")
            risks = [r.risk for r in plan.critic.risks]
            if risks:
                parts.append(f"Risks: {'; '.join(risks[:3])}")
        content = " | ".join(parts)
        ms = int((time.time() - start) * 1000)
        return LayerResult(
            layer_id=self.id,
            tag=tag,
            content=content,
            tokens_est=len(content.split()),
            compute_ms=ms,
            cached=False,
        )


# --- L9: Session Memory Context ---


class SessionContextLayer(Layer):
    """L9: Restored session context from memory store.

    Provides context from previous sessions via build_resume_context().
    Shows workflow position, pending items, and violations.
    """

    @property
    def id(self) -> str:
        return "L9"

    @property
    def name(self) -> str:
        return "SessionMemory"

    @property
    def cache_ttl(self) -> int:
        return 0

    @property
    def priority(self) -> int:
        return 90

    def compute(self, ctx: PromptContext) -> LayerResult:
        start = time.time()
        try:
            from core.memory.rehydrator import build_resume_context

            content = build_resume_context()
        except Exception:
            content = ""

        if not content:
            return LayerResult(
                layer_id=self.id, tag="", content="", tokens_est=0, compute_ms=0, cached=False
            )

        tag = "[session:resume]"
        tokens = len(content.split())

        ms = int((time.time() - start) * 1000)
        return LayerResult(
            layer_id=self.id,
            tag=tag,
            content=content,
            tokens_est=tokens,
            compute_ms=ms,
            cached=False,
        )

# --- L2.5: KB Context (Obsidian) -------------------------------------------
# Lives in core/synapse/layers_kb.py (v4.21.0 split). Re-exported here so
# `core.synapse.layers` import paths and helper references keep working.

from core.synapse.layers_kb import (  # noqa: E402,F401
    _KB_CONFIG_PATH,
    _MAX_FALLBACK_NOTES,
    KBContextLayer,
    _apply_grounding_policy,
    _build_note_entry,
    _extract_excerpt,
    _extract_note_body,
    _extract_title,
    _extract_wikilinks,
    _format_kb_block,
    _frontmatter_marks_inferred,
    _hit_is_inferred,
    _jaccard,
    _jaccard_fallback,
    _l25_feature_flag_on,
    _load_fallback_notes,
    _note_from_vector_hit,
    _tokenize_for_jaccard,
    _vector_search,
)
