"""Synapse layer definitions — the 8 context layers.

Each layer extracts a specific type of context and compresses it
for injection into the prompt. Layers are pluggable and ordered.

Layer Architecture:
  L0: Constitution  — Compressed governance rules (TTL: 300s)
  L1: Department    — Detected department from input (no cache)
  L2: Agent         — Agent profile + last gotchas (TTL: 30s)
  L3: Project       — Active project context (TTL: 30s)
  L4: Branch        — Current git branch (no cache)
  L5: Command Hints — Matching commands from registry (TTL: 30s)
  L6: Quality Gate  — QG status and last verdicts (TTL: 60s)
  L7: Time          — Time-of-day signal (no cache)
"""

import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Any


@dataclass
class LayerResult:
    """Result from computing a single layer."""
    layer_id: str
    tag: str         # e.g., "[dept:dev]"
    content: str     # Full content for this layer
    tokens_est: int  # Estimated token count
    compute_ms: int  # Time to compute in milliseconds
    cached: bool     # Whether this was served from cache


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
    "strategy": r"\b(strategy|brainstorm|market|swot|competitor|roadmap|pivot|growth|porter|blue.?ocean|positioning)\b",
    "ops": r"\b(task|automate|meeting|workflow|process|schedule|sop|integration|zapier|n8n)\b",
    "kb": r"\b(learn|persona|knowledge|youtube|transcribe|article|research|zettelkasten|note)\b",
    "brand": r"\b(brand|logo|colors|palette|mockup|photoshoot|brand.?identity|brand.?guide|mood.?board|naming|visual.?design|motion|ux|ui|wireframe)\b",
    "saas": r"\b(saas|micro.?saas|plg|freemium|churn|mrr|arr|subscription|onboarding|metrics)\b",
    "landing": r"\b(landing|funnel|copy|headline|offer|launch|affiliate|webinar|conversion|sales.?page)\b",
    "community": r"\b(community|group|membership|discord|telegram|skool|circle|gamification|engagement)\b",
    "content": r"\b(viral|hook|script|repurpose|youtube|tiktok|reels|shorts|newsletter|creator)\b",
    "pm": r"\b(sprint|backlog|standup|retro|scrum|kanban|story|estimate|roadmap|agile)\b",
    "lead": r"\b(leadership|delegation|1on1|feedback|culture|hiring|performance.?review|team.?build)\b",
    "sales": r"\b(pipeline|proposal|discovery.?call|objection|negotiate|deal|close|prospect|spin|challenger)\b",
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
        prefix_match = re.match(r"^/(\w+)\s", text)
        if prefix_match:
            prefix = prefix_match.group(1)
            dept_map = {
                "dev": "dev", "mkt": "marketing", "fin": "finance",
                "strat": "strategy", "ops": "ops", "ecom": "ecom",
                "kb": "kb", "brand": "brand", "saas": "saas",
                "landing": "landing", "community": "community",
                "content": "content", "pm": "pm", "lead": "lead",
                "sales": "sales", "org": "org",
            }
            if prefix in dept_map:
                dept = dept_map[prefix]
                ms = int((time.time() - start) * 1000)
                return LayerResult(
                    layer_id=self.id, tag=f"[dept:{dept}]",
                    content=dept, tokens_est=1, compute_ms=ms, cached=False,
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
            layer_id=self.id, tag=tag, content=dept,
            tokens_est=1, compute_ms=ms, cached=False,
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
                layer_id=self.id, tag="", content="",
                tokens_est=0, compute_ms=ms, cached=False,
            )

        agent = self._registry.get(agent_id, {})
        disc = agent.get("disc", "")
        tag = f"[agent:{agent_id} disc:{disc}]"

        ms = int((time.time() - start) * 1000)
        return LayerResult(
            layer_id=self.id, tag=tag, content=agent_id,
            tokens_est=3, compute_ms=ms, cached=False,
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
            layer_id=self.id, tag=tag, content=ctx.project_name or "",
            tokens_est=len(parts), compute_ms=ms, cached=False,
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
            layer_id=self.id, tag=tag, content=branch,
            tokens_est=1 if tag else 0, compute_ms=ms, cached=False,
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

        # Skip if already an explicit command
        if text.startswith("/"):
            ms = int((time.time() - start) * 1000)
            return LayerResult(
                layer_id=self.id, tag="", content="",
                tokens_est=0, compute_ms=ms, cached=False,
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
            layer_id=self.id, tag=tags, content=" ".join(hints),
            tokens_est=len(hints) * 2, compute_ms=ms, cached=False,
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
        # Quality Gate status is contextual — loaded from governance engine
        tag = "[qg:active]"
        ms = int((time.time() - start) * 1000)
        return LayerResult(
            layer_id=self.id, tag=tag, content="active",
            tokens_est=1, compute_ms=ms, cached=False,
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
            layer_id=self.id, tag=tag, content=period,
            tokens_est=1, compute_ms=ms, cached=False,
        )
