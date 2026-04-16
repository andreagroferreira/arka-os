"""Forge Runtime Dispatcher — multi-runtime Task tool abstraction.

Provides a unified interface for dispatching explorer and critic subagents
across all supported runtimes (Claude Code, Codex CLI, Gemini CLI, Cursor).
Each runtime gets its own dispatcher implementation.

Model routing per tier:
- shallow (≤30):  haiku  (cost-optimized, inline execution)
- standard (31-65): sonnet (balanced cost/quality)
- deep (66-85):   opus  (highest quality for complex judgment)
- super (≥86):     opus  (full synthesis, highest judgment)
"""

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from core.forge.schema import (
    ExplorerLens,
    ExplorerApproach,
    CriticVerdict,
    ForgeContext,
    ForgeTier,
    PhaseDeliverable,
    KeyDecision,
    RiskSeverity,
    RejectedElement,
    IdentifiedRisk,
)


EXPLORER_PREAMBLE = """You are an expert planning agent within ArkaOS. Your task is to produce a structured execution plan for the following prompt."""

CRITIC_PREAMBLE = """You are the Plan Critic within ArkaOS. You have received {n} independent planning approaches for the same prompt. Your job is to synthesize the best plan by combining the strongest elements from each approach."""


CONSTITUTION_RULES = """CONSTITUTION RULES (non-negotiable):
  - branch-isolation: all work on feature branches, never main
  - spec-driven: spec must exist before implementation
  - solid-clean-code: SOLID + Clean Code on all code
  - mandatory-qa: tests must pass, coverage >= 80%
  - quality-gate: Marta + Eduardo + Francisca must APPROVE before done
  - conventional-commits: all commits follow conventional commit format"""

AVAILABLE_DEPARTMENTS = "dev, ops, mkt, brand, fin, strat, pm, saas, landing, content, ecom, kb, sales, lead, community, org"

AVAILABLE_AGENTS = """dev: Paulo (lead), Gabriel (architect), Andre (backend), Diana (frontend), Bruno (security), Carlos (devops), Rita (qa), Vasco (dba)
ops: Daniel (lead), Lucas (automation)
mkt: Luna (lead), Sofia (growth), Pedro (analytics), Carla (email)
brand: Valentina (lead), Miguel (visual), Ana (copy), Joao (ux)
quality (cross-cutting): Marta (CQO), Eduardo (copy), Francisca (tech)"""

LENS_INSTRUCTIONS = {
    ExplorerLens.PRAGMATIC: """Your lens: PRAGMATIC
Question to answer: "What is the simplest thing that works?"
Principles:
  - Minimum viable approach — reuse existing patterns, avoid over-engineering
  - Maximum reuse of existing ArkaOS skills and workflows
  - Fewer phases is better — collapse where safe to do so
  - Prefer known, proven solutions over novel ones
  - Identify what can be skipped without meaningful quality loss
Be direct. Challenge gold-plating. Propose the leanest plan that still satisfies all Constitution rules.""",
    ExplorerLens.ARCHITECTURAL: """Your lens: ARCHITECTURAL
Question to answer: "What is the right way to build this for the long term?"
Principles:
  - Long-term extensibility and maintainability over short-term speed
  - Proper separation of concerns, clean boundaries
  - Identify technical debt that would be created by a simpler approach
  - Ensure observability, testability, and deployability are first-class
  - Reference DDD, SOLID, Clean Architecture where applicable
Be thorough. Do not cut corners that will create future problems.""",
    ExplorerLens.CONTRARIAN: """Your lens: CONTRARIAN
Question to answer: "What is everyone missing or assuming wrongly?"
Principles:
  - Challenge the premise of the prompt — is this the right problem to solve?
  - Surface hidden dependencies, risks, and blockers others would miss
  - Question every assumed constraint — are they real?
  - Propose an alternative framing if the original prompt is misguided
  - Identify the single biggest risk in the other approaches
Be adversarial but constructive. Your job is to stress-test assumptions, not to be contrarian for its own sake. You must still produce a valid plan.""",
}


@dataclass
class DispatchResult:
    """Result from a dispatcher call."""

    success: bool
    output: str = ""
    error: str = ""
    raw_response: str = ""


@dataclass
class ExplorerDispatchRequest:
    """Request to dispatch an explorer subagent."""

    lens: ExplorerLens
    prompt: str
    context: ForgeContext
    similar_plans: list[str] = field(default_factory=list)
    reused_patterns: list[str] = field(default_factory=list)
    model: str = "sonnet"


@dataclass
class CriticDispatchRequest:
    """Request to dispatch a critic subagent."""

    original_prompt: str
    approaches: list[ExplorerApproach]
    model: str = "sonnet"


def _tier_to_model(tier: ForgeTier) -> str:
    """Map tier to default model."""
    mapping = {
        ForgeTier.SHALLOW: "haiku",
        ForgeTier.STANDARD: "sonnet",
        ForgeTier.DEEP: "opus",
    }
    return mapping.get(tier, "sonnet")


def _build_explorer_prompt(req: ExplorerDispatchRequest) -> str:
    """Build the full prompt for an explorer subagent."""
    parts = [
        EXPLORER_PREAMBLE,
        "",
        f"PROMPT: {req.prompt}",
        "",
        "REPO CONTEXT:",
        f"  Repo: {req.context.repo}",
        f"  Branch: {req.context.branch}",
        f"  Commit: {req.context.commit_at_forge}",
        f"  ArkaOS: {req.context.arkaos_version}",
        "",
        "OBSIDIAN KNOWLEDGE:",
        f"  Similar plans found: {', '.join(req.similar_plans) if req.similar_plans else 'none'}",
        f"  Reusable patterns: {', '.join(req.reused_patterns) if req.reused_patterns else 'none'}",
        "",
        CONSTITUTION_RULES,
        "",
        f"AVAILABLE DEPARTMENTS: {AVAILABLE_DEPARTMENTS}",
        "",
        f"AVAILABLE AGENTS:\n{AVAILABLE_AGENTS}",
        "",
        LENS_INSTRUCTIONS[req.lens],
        "",
        "Your output MUST follow this exact format:",
        "EXPLORER: <your lens name>",
        "SUMMARY: <2-3 sentences>",
        "KEY_DECISIONS:",
        "  - decision: <what>",
        "    rationale: <why>",
        "PHASES:",
        "  - name: <phase name>",
        "    department: <dept>",
        "    agents: [<names>]",
        "    deliverables: [<items>]",
        "    acceptance_criteria: [<items>]",
        "    depends_on: [<phase names>]",
    ]
    return "\n".join(parts)


def _build_critic_prompt(req: CriticDispatchRequest) -> str:
    """Build the full prompt for a critic subagent."""
    approach_texts = []
    for i, approach in enumerate(req.approaches, 1):
        decisions = "\n".join(
            f"    - decision: {d.decision}\n      rationale: {d.rationale}"
            for d in approach.key_decisions
        )
        phases = "\n".join(
            f"  - name: {p.name}\n    department: {p.department}\n    agents: {p.agents}\n    deliverables: {p.deliverables}\n    acceptance_criteria: {p.acceptance_criteria}\n    depends_on: {p.depends_on}"
            for p in approach.phases
        )
        text = f"""APPROACH {i} ({approach.explorer.value}):
Summary: {approach.summary}
Key Decisions:
{decisions}
Phases:
{phases}"""
        approach_texts.append(text)

    parts = [
        CRITIC_PREAMBLE.format(n=len(req.approaches)),
        "",
        f"PROMPT: {req.original_prompt}",
        "",
        "APPROACHES:",
        "\n---\n".join(approach_texts),
        "",
        "RULES:",
        "  - You MUST adopt the best elements from multiple approaches (do not just pick one)",
        "  - You MUST reject at least 1 element with a clear reason",
        "  - You MUST identify at least 1 risk in the final plan",
        "  - Confidence score must reflect genuine uncertainty (do not always output 0.9)",
        "  - The final phase list MUST include a Quality Gate phase as the penultimate step",
        "  - The final phase list MUST include an Obsidian persistence phase as the last step",
        "  - All Constitution rules apply to the final plan",
        "",
        "Your output MUST follow this exact format:",
        "CONFIDENCE: <0.0-1.0>",
        "SYNTHESIS:",
        "  approach_1: [<adopted elements from approach 1>]",
        "  approach_2: [<adopted elements from approach 2>]",
        "  approach_3: [<adopted elements from approach 3, if applicable>]",
        "REJECTED:",
        "  - element: <what>",
        "    reason: <why>",
        "RISKS:",
        "  - risk: <description>",
        "    severity: high|medium|low",
        "    mitigation: <how to address>",
        "FINAL_PHASES:",
        "  - name: <phase name>",
        "    department: <dept>",
        "    agents: [<names>]",
        "    deliverables: [<items>]",
        "    acceptance_criteria: [<items>]",
        "    depends_on: [<phase names>]",
    ]
    return "\n".join(parts)


def _parse_explorer_output(raw: str, lens: ExplorerLens) -> ExplorerApproach:
    """Parse structured text output from an explorer subagent."""
    explorer_match = re.search(r"EXPLORER:\s*(\w+)", raw)
    summary_match = re.search(r"SUMMARY:\s*(.+?)(?=KEY_DECISIONS:|$)", raw, re.DOTALL)
    key_decisions = []
    for match in re.finditer(
        r"-\s*decision:\s*(.+?)\n\s*rationale:\s*(.+?)(?=\n\s*-\s*decision:|\nPHASES:|$)",
        raw,
        re.DOTALL,
    ):
        key_decisions.append(
            KeyDecision(decision=match.group(1).strip(), rationale=match.group(2).strip())
        )

    phases = []
    phase_blocks = re.split(r"(?=^\s*-\s*name:)", raw, flags=re.MULTILINE)
    for block in phase_blocks[1:]:
        name_match = re.search(r"name:\s*(.+?)(?=\n|$)", block)
        dept_match = re.search(r"department:\s*(\w+)", block)
        agents_match = re.findall(r"agents:\s*\[(.+?)\]", block)
        deliverables_match = re.findall(r"deliverables:\s*\[(.+?)\]", block)
        criteria_match = re.findall(r"acceptance_criteria:\s*\[(.+?)\]", block)
        depends_match = re.findall(r"depends_on:\s*\[(.+?)\]", block)
        if name_match and dept_match:
            phases.append(
                PhaseDeliverable(
                    name=name_match.group(1).strip(),
                    deliverables=[d.strip() for d in deliverables_match],
                    agents=[a.strip() for a in agents_match],
                    acceptance_criteria=[c.strip() for c in criteria_match],
                    depends_on=[d.strip() for d in depends_match],
                )
            )

    return ExplorerApproach(
        explorer=lens,
        summary=summary_match.group(1).strip() if summary_match else "",
        key_decisions=key_decisions,
        phases=phases,
    )


def _parse_critic_output(raw: str) -> CriticVerdict:
    """Parse structured text output from a critic subagent."""
    confidence_match = re.search(r"CONFIDENCE:\s*([\d.]+)", raw)
    confidence = float(confidence_match.group(1)) if confidence_match else 0.0

    synthesis = {}
    synthesis_section = re.search(r"SYNTHESIS:(.+?)(?=REJECTED:|$)", raw, re.DOTALL)
    if synthesis_section:
        for approach_match in re.finditer(
            r"(\w+):\s*\[(.+?)\]", synthesis_section.group(1), re.DOTALL
        ):
            items = [i.strip() for i in approach_match.group(2).split(",") if i.strip()]
            synthesis[approach_match.group(1)] = items

    rejected = []
    for match in re.finditer(
        r"-\s*element:\s*(.+?)\n\s*reason:\s*(.+?)(?=\n\s*-\s*element:|\nRISKS:|$)", raw, re.DOTALL
    ):
        rejected.append(
            RejectedElement(element=match.group(1).strip(), reason=match.group(2).strip())
        )

    risks = []
    for match in re.finditer(
        r"-\s*risk:\s*(.+?)\n\s*severity:\s*(\w+)\n\s*mitigation:\s*(.+?)(?=\n\s*-\s*risk:|$)",
        raw,
        re.DOTALL,
    ):
        severity_str = match.group(2).strip().lower()
        severity = (
            RiskSeverity.HIGH
            if severity_str == "high"
            else RiskSeverity.MEDIUM
            if severity_str == "medium"
            else RiskSeverity.LOW
        )
        risks.append(
            IdentifiedRisk(
                risk=match.group(1).strip(), mitigation=match.group(3).strip(), severity=severity
            )
        )

    phases = []
    phase_section = re.search(r"FINAL_PHASES:(.+?)$", raw, re.DOTALL)
    if phase_section:
        for match in re.finditer(
            r"-\s*name:\s*(.+?)\n\s*department:\s*(\w+)\n\s*agents:\s*\[(.+?)\]\n\s*deliverables:\s*\[(.+?)\]\n\s*acceptance_criteria:\s*\[(.+?)\]\n\s*depends_on:\s*\[(.+?)\]",
            phase_section.group(1),
            re.DOTALL,
        ):
            phases.append(
                PhaseDeliverable(
                    name=match.group(1).strip(),
                    deliverables=[d.strip() for d in match.group(4).split(",") if d.strip()],
                    agents=[a.strip() for a in match.group(3).split(",") if a.strip()],
                    acceptance_criteria=[c.strip() for c in match.group(5).split(",") if c.strip()],
                    depends_on=[d.strip() for d in match.group(6).split(",") if d.strip()],
                )
            )

    return CriticVerdict(
        synthesis=synthesis,
        rejected_elements=rejected,
        risks=risks,
        confidence=confidence,
        estimated_phases=len(phases),
    )


class ForgeTaskDispatcher(ABC):
    """Abstract base for Forge Task tool dispatchers.

    Each runtime (Claude Code, Codex, Gemini CLI, Cursor) implements
    this interface to dispatch explorer and critic subagents.
    """

    @abstractmethod
    def dispatch_explorer(self, request: ExplorerDispatchRequest) -> DispatchResult:
        """Dispatch an explorer subagent via Task tool.

        Args:
            request: Explorer dispatch request with lens, prompt, context

        Returns:
            DispatchResult with raw response text from the subagent
        """

    @abstractmethod
    def dispatch_critic(self, request: CriticDispatchRequest) -> DispatchResult:
        """Dispatch a critic subagent via Task tool.

        Args:
            request: Critic dispatch request with approaches and prompt

        Returns:
            DispatchResult with raw response text from the subagent
        """

    def dispatch_explorer_and_parse(self, request: ExplorerDispatchRequest) -> ExplorerApproach:
        """Dispatch an explorer and parse its structured output."""
        result = self.dispatch_explorer(request)
        if not result.success:
            raise RuntimeError(f"Explorer dispatch failed: {result.error}")
        return _parse_explorer_output(result.raw_response, request.lens)

    def dispatch_critic_and_parse(self, request: CriticDispatchRequest) -> CriticVerdict:
        """Dispatch a critic and parse its structured output."""
        result = self.dispatch_critic(request)
        if not result.success:
            raise RuntimeError(f"Critic dispatch failed: {result.error}")
        return _parse_critic_output(result.raw_response)


class ClaudeCodeForgeDispatcher(ForgeTaskDispatcher):
    """Claude Code implementation using the Task tool with model parameter.

    Claude Code supports the Agent tool with model routing:
    - haiku: fast, cost-optimized
    - sonnet: balanced
    - opus: highest capability
    """

    def dispatch_explorer(self, request: ExplorerDispatchRequest) -> DispatchResult:
        """Dispatch explorer using Claude Code's Agent tool."""
        prompt = _build_explorer_prompt(request)
        raw_response = self._call_agent(prompt, model=request.model, agent_type="explorer")
        return DispatchResult(success=True, raw_response=raw_response, output=raw_response)

    def dispatch_critic(self, request: CriticDispatchRequest) -> DispatchResult:
        """Dispatch critic using Claude Code's Agent tool."""
        prompt = _build_critic_prompt(request)
        raw_response = self._call_agent(prompt, model=request.model, agent_type="critic")
        return DispatchResult(success=True, raw_response=raw_response, output=raw_response)

    def _call_agent(
        self,
        prompt: str,
        model: str,
        agent_type: str,
        timeout: int = 120,
    ) -> str:
        """Call the Claude Code Agent tool.

        This method should be overridden in tests to mock the actual
        Task tool call. The real implementation uses the Agent tool
        from Claude Code's toolkit.
        """
        from agentTool import Agent  # type: ignore

        task_result = Agent(
            prompt=prompt,
            model=model,
            task_type=agent_type,
        )
        return task_result.output


def create_dispatcher(runtime: str | None = None) -> ForgeTaskDispatcher:
    """Create the appropriate dispatcher for the current runtime.

    Args:
        runtime: Runtime identifier. If None, auto-detected.

    Returns:
        ForgeTaskDispatcher instance for the runtime
    """
    if runtime is None:
        runtime = _detect_runtime()

    dispatchers = {
        "claude-code": ClaudeCodeForgeDispatcher,
        "claude": ClaudeCodeForgeDispatcher,
    }

    dispatcher_class = dispatchers.get(runtime, ClaudeCodeForgeDispatcher)
    return dispatcher_class()


def _detect_runtime() -> str:
    """Auto-detect the current runtime environment."""
    import os

    if os.environ.get("ARKAOS_RUNTIME"):
        return os.environ["ARKAOS_RUNTIME"]

    try:
        import claude

        return "claude-code"
    except ImportError:
        pass

    return "claude-code"
