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
"""

import json
import os
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Any


@dataclass
class LayerResult:
    """Result from computing a single layer."""

    layer_id: str
    tag: str  # e.g., "[dept:dev]"
    content: str  # Full content for this layer
    tokens_est: int  # Estimated token count
    compute_ms: int  # Time to compute in milliseconds
    cached: bool  # Whether this was served from cache


@dataclass
class PromptContext:
    """Input context for layer computation."""

    user_input: str = ""
    cwd: str = ""
    git_branch: str = ""
    project_name: str = ""
    project_stack: str = ""
    active_agent: str = ""
    runtime_id: str = "claude-code"
    extra: dict[str, Any] = None

    def __post_init__(self) -> None:
        if self.extra is None:
            self.extra = {}


class Layer(ABC):
    """Abstract base class for a Synapse context layer."""

    @property
    @abstractmethod
    def id(self) -> str:
        """Unique layer identifier (e.g., 'L0', 'L1')."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name."""

    @property
    def cache_ttl(self) -> int:
        """Cache TTL in seconds. 0 = no caching."""
        return 0

    @property
    def priority(self) -> int:
        """Layer priority (lower = computed first)."""
        return 50

    @abstractmethod
    def compute(self, ctx: PromptContext) -> LayerResult:
        """Compute this layer's context.

        Args:
            ctx: The prompt context with user input and environment.

        Returns:
            LayerResult with the computed context.
        """


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
    "dev": r"\b(build|code|feature|deploy|test|review|scaffold|debug|refactor|api|migration|stack|implement|fix|bug)\b",
    "marketing": r"\b(social|content|campaign|post|instagram|linkedin|twitter|tiktok|seo|marketing|ads|email.?campaign|growth|viral)\b",
    "finance": r"\b(budget|invoice|revenue|forecast|profit|loss|roi|margin|cash.?flow|financial|invest|valuation|pricing)\b",
    "ecom": r"\b(store|product|shop|shopify|ecommerce|catalog|inventory|cart|checkout|pricing|marketplace)\b",
    "strategy": r"\b(strategy|brainstorm|market|swot|competitors?|roadmap|pivot|growth|porter|blue.?ocean|positioning)\b",
    "ops": r"\b(task|automate|meeting|workflow|process|schedule|sop|integration|zapier|n8n)\b",
    "kb": r"\b(learn|persona|knowledge|youtube|transcribe|article|research|zettelkasten|note)\b",
    "brand": r"\b(brand|logo|colors|palette|mockup|photoshoot|brand.?identity|brand.?guide|mood.?board|naming|visual.?design|motion|ux|ui|wireframe)\b",
    "saas": r"\b(saas|micro.?saas|plg|freemium|churn|mrr|arr|subscription|onboarding|metrics)\b",
    "landing": r"\b(landing|funnel|copy|headline|offer|launch|affiliate|webinar|conversion|sales.?page)\b",
    "community": r"\b(community|group|membership|discord|telegram|skool|circle|gamification|engagement)\b",
    "content": r"\b(viral|hook|script|repurpose|youtube|tiktok|reels|shorts|newsletter|creator)\b",
    "pm": r"\b(sprint|backlog|standup|retro|scrum|kanban|story|estimate|roadmap|agile)\b",
    "lead": r"\b(leadership|delegation|1on1|feedback|culture|hiring|performance.?review|team.?build)\b",
    "sales": r"\b(pipeline|proposal|discovery.?call|objection|negotiate|deal|close|prospect|spin|challenger|cold.?email|outreach)\b",
    "org": r"\b(org.?design|hiring.?plan|onboarding|remote|meeting.?optimize|compensation|decision.?framework)\b",
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
        if branch in ("main", "master", "dev", ""):
            tag = ""
        else:
            tag = f"[branch:{branch}]"

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


class CommandHintsLayer(Layer):
    """L5: Matching commands from the registry for non-explicit requests."""

    def __init__(self, commands: list[dict] | None = None) -> None:
        self._commands = commands or []

    @property
    def id(self) -> str:
        return "L5"

    @property
    def name(self) -> str:
        return "CommandHints"

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

        # Score commands by keyword match
        scored = []
        for cmd in self._commands:
            keywords = cmd.get("keywords", [])
            score = sum(1 for kw in keywords if kw.lower() in text)
            if score > 0:
                scored.append((score, cmd.get("command", "")))

        scored.sort(reverse=True)
        hints = [cmd for _, cmd in scored[:2]]

        tags = " ".join(f"[hint:{h}]" for h in hints)
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
            from core.governance.quality_api import list_pending, list_approved

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


# --- L7: Time Signal ---


class TimeLayer(Layer):
    """L7: Time-of-day signal for context-aware behavior."""

    @property
    def id(self) -> str:
        return "L7"

    @property
    def name(self) -> str:
        return "Time"

    @property
    def cache_ttl(self) -> int:
        # 1 hour — time-of-day period only changes at 5/12/18 boundaries.
        # Cache bucket drift of up to 1h is acceptable for a low-signal tag
        # and dramatically improves prompt-cache hit rate.
        return 3600

    @property
    def priority(self) -> int:
        return 70

    def compute(self, ctx: PromptContext) -> LayerResult:
        start = time.time()
        import datetime

        hour = datetime.datetime.now().hour
        if 5 <= hour < 12:
            period = "morning"
        elif 12 <= hour < 18:
            period = "afternoon"
        else:
            period = "evening"

        tag = f"[time:{period}]"
        ms = int((time.time() - start) * 1000)
        return LayerResult(
            layer_id=self.id,
            tag=tag,
            content=period,
            tokens_est=1,
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
    def cache_ttl(self) -> int:
        return 30

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

        content = " | ".join(parts)
        chunk_count = len(snippets) + (len(overlapping) if overlapping else 0)
        tag = f"[knowledge:{chunk_count} chunks]"
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
            for source, elements in plan.critic.synthesis.items():
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

        lines = content.split("\n")
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

_WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:\|[^\]]+)?\]\]")
_FRONTMATTER_RE = re.compile(r"^---\n.*?\n---\n", re.DOTALL)
_KB_CONFIG_PATH = Path.home() / ".arkaos" / "config.json"
# Cap fallback-note scanning to avoid O(vault size) blow-ups on large
# Obsidian vaults. The cap is above any realistic top-N retrieval need
# (Jaccard ranks the top few notes; scanning 2000 sorted-by-name first
# is plenty — see `_load_fallback_notes`) while still bounding worst-case latency.
_MAX_FALLBACK_NOTES = 2000
_KB_STOPWORDS: frozenset[str] = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for", "of",
    "with", "by", "from", "as", "is", "was", "are", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "should", "could",
    "may", "might", "must", "can", "this", "that", "these", "those", "it", "its",
    "about", "into", "over", "under", "up", "down", "out", "than", "then", "so",
    "if", "because", "while", "where", "when", "what", "which", "who", "whom",
    "how", "why", "all", "some", "any", "no", "not", "very", "just", "also",
})


def _l25_feature_flag_on() -> bool:
    if os.environ.get("ARKA_BYPASS_L25", "").strip() == "1":
        return False
    if not _KB_CONFIG_PATH.exists():
        return True
    try:
        data = json.loads(_KB_CONFIG_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return True
    synapse_cfg = data.get("synapse") or {}
    return bool(synapse_cfg.get("l25KbContext", True))


def _tokenize_for_jaccard(text: str) -> set[str]:
    if not text:
        return set()
    words = re.findall(r"[a-zA-Z0-9]{3,}", text.lower())
    return {w for w in words if w not in _KB_STOPWORDS}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _extract_note_body(raw: str) -> str:
    return _FRONTMATTER_RE.sub("", raw, count=1).lstrip()


def _extract_title(raw: str, fallback: str) -> str:
    body = _extract_note_body(raw)
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip() or fallback
        if stripped:
            return fallback
    return fallback


def _extract_excerpt(raw: str, max_lines: int = 2) -> str:
    body = _extract_note_body(raw)
    lines: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        lines.append(stripped)
        if len(lines) >= max_lines:
            break
    return " ".join(lines)[:240]


def _extract_wikilinks(raw: str, limit: int = 3) -> list[str]:
    body = _extract_note_body(raw)
    seen: list[str] = []
    for match in _WIKILINK_RE.finditer(body):
        target = match.group(1).strip()
        if target and target not in seen:
            seen.append(target)
        if len(seen) >= limit:
            break
    return seen


def _format_kb_block(notes: list[dict]) -> str:
    lines: list[str] = [
        f"[arka:kb-context] O teu cérebro (Obsidian) tem {len(notes)} "
        f"nota{'s' if len(notes) != 1 else ''} relevante{'s' if len(notes) != 1 else ''} "
        f"para este pedido:",
        "",
    ]
    for note in notes:
        title = note.get("title", "")
        path = note.get("path", "")
        excerpt = note.get("excerpt", "")
        relates = note.get("relates", []) or []
        lines.append(f"- [[{title}]] (path: `{path}`)")
        if excerpt:
            lines.append(f"  Excerto: {excerpt}")
        if relates:
            rel = ", ".join(f"[[{r}]]" for r in relates)
            lines.append(f"  Relacionada: {rel}")
        lines.append("")
    lines.append(
        "Consulta-as antes de ir a Context7/Web. Se preencherem o pedido, "
        "usa-as e cita. Se tiverem lacuna, investiga externamente e "
        "documenta de volta."
    )
    return "\n".join(lines).strip()


def _vector_search(store: Any, prompt: str, top_k: int) -> list[dict]:
    if store is None:
        return []
    try:
        return list(store.search(prompt, top_k=top_k)) or []
    except Exception:
        return []


def _jaccard_fallback(
    prompt: str, notes: list[dict], top_k: int, threshold: float
) -> list[dict]:
    prompt_tokens = _tokenize_for_jaccard(prompt)
    scored: list[tuple[float, dict]] = []
    for note in notes:
        title_tokens = _tokenize_for_jaccard(note.get("title", ""))
        score = _jaccard(prompt_tokens, title_tokens)
        if score >= threshold:
            scored.append((score, note))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [n for _, n in scored[:top_k]]


def _load_fallback_notes(vault_path: Optional[Path]) -> list[dict]:
    if vault_path is None or not vault_path.exists() or not vault_path.is_dir():
        return []
    notes: list[dict] = []
    for md in sorted(vault_path.rglob("*.md")):
        if len(notes) >= _MAX_FALLBACK_NOTES:
            break
        try:
            raw = md.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        notes.append(
            {
                "title": _extract_title(raw, md.stem),
                "path": str(md),
                "raw": raw,
            }
        )
    return notes


def _build_note_entry(raw: str, title: str, path: str, score: float) -> dict:
    return {
        "title": title,
        "path": path,
        "excerpt": _extract_excerpt(raw),
        "relates": _extract_wikilinks(raw),
        "score": float(score),
    }


def _note_from_vector_hit(hit: dict) -> dict:
    source = hit.get("source", "") or ""
    raw = hit.get("text", "") or ""
    title = hit.get("heading") or Path(source).stem or "note"
    score_val = hit.get("score", 0.0) or 0.0
    return _build_note_entry(raw, str(title), str(source), float(score_val))


class KBContextLayer(Layer):
    """L2.5: Obsidian KB context injection before the model thinks.

    Design (see plan ``2026-04-20-intelligence-v2.md``):
      1. Semantic search the user prompt against the vector store.
      2. If store empty or embedder unavailable, fall back to Jaccard
         keyword similarity against cached note titles.
      3. Keep notes with similarity ≥ ``min_similarity`` (default 0.5),
         up to ``max_notes``.
      4. Format as ``[arka:kb-context]`` block with title, path, 2-line
         excerpt, and top 3 wikilinks per note.
      5. Call ``record_obsidian_query`` so research_gate (Task #6) can
         verify KB-first was respected this turn.

    Feature flag: ``synapse.l25KbContext`` in ``~/.arkaos/config.json``
    (default ``true``). ``ARKA_BYPASS_L25=1`` env disables for debugging.
    """

    def __init__(
        self,
        vector_store: Any = None,
        vault_path: Optional[str] = None,
        max_notes: int = 5,
        min_similarity: float = 0.5,
    ) -> None:
        self._store = vector_store
        self._vault_path = Path(vault_path) if vault_path else None
        self._max_notes = max_notes
        self._min_similarity = min_similarity

    @property
    def id(self) -> str:
        return "L2.5"

    @property
    def name(self) -> str:
        return "KBContext"

    @property
    def cache_ttl(self) -> int:
        return 0

    @property
    def priority(self) -> int:
        return 25

    def _empty(self, start: float) -> LayerResult:
        ms = int((time.time() - start) * 1000)
        return LayerResult(
            layer_id=self.id, tag="", content="", tokens_est=0, compute_ms=ms, cached=False
        )

    def _session_id(self, ctx: PromptContext) -> str:
        return ctx.extra.get("session_id", "") if ctx.extra else ""

    def _record(self, ctx: PromptContext, hit_count: int) -> None:
        session_id = self._session_id(ctx)
        if not session_id:
            return
        try:
            from core.synapse.kb_cache import record_obsidian_query

            record_obsidian_query(session_id, ctx.user_input, hit_count)
        except Exception:
            pass

    def _retrieve(self, prompt: str) -> list[dict]:
        hits = _vector_search(self._store, prompt, top_k=self._max_notes * 2)
        notes: list[dict] = []
        for h in hits:
            score = float(h.get("score", 0.0) or 0.0)
            if score < self._min_similarity:
                continue
            notes.append(_note_from_vector_hit(h))
            if len(notes) >= self._max_notes:
                break
        if notes:
            return notes
        candidates = _load_fallback_notes(self._vault_path)
        if not candidates:
            return []
        picked = _jaccard_fallback(
            prompt, candidates, self._max_notes, self._min_similarity
        )
        return [
            _build_note_entry(n["raw"], n["title"], n["path"], 0.0)
            for n in picked
        ]

    def build(self, prompt: str) -> Optional[str]:
        """Public entrypoint — returns the formatted block or None."""
        if not prompt or not _l25_feature_flag_on():
            return None
        notes = self._retrieve(prompt[:2000])
        if not notes:
            return None
        return _format_kb_block(notes[: self._max_notes])

    def compute(self, ctx: PromptContext) -> LayerResult:
        start = time.time()
        if not ctx.user_input or not _l25_feature_flag_on():
            return self._empty(start)
        try:
            notes = self._retrieve(ctx.user_input[:2000])
        except Exception:
            return self._empty(start)
        self._record(ctx, len(notes))
        if not notes:
            return self._empty(start)
        block = _format_kb_block(notes[: self._max_notes])
        ms = int((time.time() - start) * 1000)
        return LayerResult(
            layer_id=self.id,
            tag=f"[kb-context:{len(notes)}]",
            content=block,
            tokens_est=len(block.split()),
            compute_ms=ms,
            cached=False,
        )
