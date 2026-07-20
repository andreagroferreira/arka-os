"""Synapse layer base classes — LayerResult, PromptContext, Layer.

Extracted from layers.py (v4.21.0 split) so both layers.py and
layers_kb.py can import the contract without a circular dependency.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


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
    def input_sensitive(self) -> bool:
        """True when compute() depends on ctx.user_input.

        Input-sensitive layers get the prompt hashed into their cache
        key — without it, a cached result from one prompt is served for
        a DIFFERENT prompt within the TTL window (found 2026-07-09: L5
        served 'hello' hints for an explicit '/dev feature' command,
        defeating its own slash-suppression rule).
        """
        return False

    @property
    def emits_block(self) -> bool:
        """True when ``content`` is a self-describing full-text block.

        OPT-IN, and deliberately so. The engine forwards ``content`` to the
        model only for layers that declare this. Inferring it from
        ``content != tag`` looked equivalent and was not: most layers set
        ``content`` to their tag's VALUE (``dev``, ``active``,
        ``feat/plan-canvas``), so every prompt gained stray unlabeled lines
        carrying nothing the tag had not already said (QG review).

        A block must stand alone: it names itself (``[arka:kb-context]``,
        ``[arka:graph-remote unverified]``) and is meaningful without the tag.
        """
        return False

    @property
    def session_sensitive(self) -> bool:
        """True when compute() has per-session side effects or output.

        Session-sensitive layers get ctx.extra['session_id'] added to
        their cache key — without it, a cache hit from one session
        suppresses compute() for a concurrent session in the same cwd,
        skipping that session's side effects (found 2026-07-09: L3.5's
        KBSessionCache.store() never ran for the second session, so its
        KB-injected state and overlap markers belonged to the first).
        """
        return False

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
