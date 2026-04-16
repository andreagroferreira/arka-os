"""Forge Orchestrator — 10-step planning flow implementation.

Coordinates the full Forge planning flow:
1. Context snapshot (git info)
2. Obsidian knowledge check (patterns/plans)
3. Complexity analysis
4. Explorer dispatch (1-3 based on tier)
5. Critic synthesis
6. Constitution enforcement
7. Render plan
8. Handoff preparation
9. Persistence

User interaction (Approve/Revise/Companion/Detail/Quit) is handled
by the caller (Claude Code session) via method calls on this orchestrator.
"""

import hashlib
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

from core.forge.schema import (
    ForgeContext,
    ForgePlan,
    ForgeStatus,
    ForgeTier,
    ComplexityScore,
    ComplexityDimensions,
    ExplorerLens,
    ExplorerApproach,
    CriticVerdict,
    PlanPhase,
    ExecutionPath,
    ForgeGovernance,
)
from core.forge.complexity import analyze_complexity
from core.forge.persistence import (
    save_plan,
    load_plan,
    list_plans,
    get_active_plan,
    set_active_plan,
    clear_active_plan,
    export_to_obsidian,
    extract_patterns,
    load_patterns,
)
from core.forge.handoff import (
    select_execution_path,
    check_repo_drift,
    generate_workflow_yaml,
)
from core.forge.renderer import (
    render_terminal,
    render_complexity,
    render_critic_summary,
    render_plan_overview,
    render_html,
    should_suggest_companion,
)
from core.forge.runtime_dispatcher import (
    ForgeTaskDispatcher,
    ClaudeCodeForgeDispatcher,
    ExplorerDispatchRequest,
    CriticDispatchRequest,
    _tier_to_model,
)


CONSTITUTION_PHASES = [
    "Create feature branch",
    "Write specification",
    "Quality Gate",
    "Persist to Obsidian",
]


@dataclass
class ForgeStep:
    """Current step in the forge flow."""

    step_number: int
    step_name: str
    description: str


class ForgeDecision(str, Enum):
    APPROVE = "approve"
    REVISE = "revise"
    COMPANION = "companion"
    DETAIL = "detail"
    QUIT = "quit"


@dataclass
class ForgeStatusOutput:
    """Output from a forge status check."""

    plan_id: str
    name: str
    status: ForgeStatus
    tier: ForgeTier
    score: int
    confidence: float
    n_phases: int
    departments: list[str]
    created_at: str
    revision_count: int


@dataclass
class ForgeHistoryEntry:
    """Entry in forge history listing."""

    plan_id: str
    name: str
    status: ForgeStatus
    tier: ForgeTier
    confidence: float
    created_date: str


@dataclass
class ForgeCompareOutput:
    """Output from comparing two plans."""

    left: ForgeStatusOutput
    right: ForgeStatusOutput
    left_phases: list[PlanPhase]
    right_phases: list[PlanPhase]


class ForgeOrchestrator:
    """Main Forge orchestrator class.

    Implements the 10-step planning flow. Stateful — maintains
    the current plan being worked on.

    Usage:
        orch = ForgeOrchestrator()
        plan = orch.forge("build user auth module")
        print(orch.render())
        # User decides: orch.approve() or orch.revise("add tests")
    """

    def __init__(self, dispatcher: Optional[ForgeTaskDispatcher] = None):
        """Initialize orchestrator.

        Args:
            dispatcher: Task dispatcher for subagent dispatch.
                       Defaults to ClaudeCodeForgeDispatcher.
        """
        self._dispatcher = dispatcher or ClaudeCodeForgeDispatcher()
        self._current_plan: Optional[ForgePlan] = None
        self._current_step: Optional[ForgeStep] = None

    # -------------------------------------------------------------------------
    # Main Commands
    # -------------------------------------------------------------------------

    def forge(self, prompt: str) -> ForgePlan:
        """Execute the full forge flow for a prompt.

        Runs steps 1-7 (through rendering). User decision (approve/revise/etc)
        is handled by separate method calls.

        Args:
            prompt: The user's request to plan

        Returns:
            ForgePlan ready for user decision
        """
        self._step1_snapshot_context(prompt)
        self._step2_obsidian_check()
        self._step3_complexity()
        self._step4_confirm_tier()
        self._step5_launch_explorers()
        self._step6_critic_synthesis()
        self._step7_enforce_constitution()
        self._step8_build_plan()
        self._step9_render()
        return self._current_plan

    def resume(self) -> Optional[ForgePlan]:
        """Resume the active forge plan.

        Returns:
            Active plan if exists, None otherwise
        """
        active = get_active_plan()
        if active is None:
            return None
        self._current_plan = active
        return active

    def status(self) -> Optional[ForgeStatusOutput]:
        """Get status of the active plan.

        Returns:
            ForgeStatusOutput if active plan exists, None otherwise
        """
        if self._current_plan is None:
            self._current_plan = get_active_plan()
        if self._current_plan is None:
            return None

        plan = self._current_plan
        depts = list({p.department for p in plan.plan_phases})
        return ForgeStatusOutput(
            plan_id=plan.id,
            name=plan.name,
            status=plan.status,
            tier=plan.complexity.tier,
            score=plan.complexity.score,
            confidence=plan.critic.confidence,
            n_phases=len(plan.plan_phases),
            departments=depts,
            created_at=plan.created_at,
            revision_count=plan.version - 1,
        )

    def history(self, limit: int = 20) -> list[ForgeHistoryEntry]:
        """List past forge plans.

        Args:
            limit: Maximum number to return

        Returns:
            List of ForgeHistoryEntry
        """
        plans = list_plans()
        entries = []
        for p in plans[:limit]:
            entries.append(
                ForgeHistoryEntry(
                    plan_id=p["id"],
                    name=p["name"],
                    status=ForgeStatus(p.get("status", "draft")),
                    tier=ForgeTier(p.get("complexity", {}).get("tier", "shallow")),
                    confidence=p.get("critic", {}).get("confidence", 0.0),
                    created_date=p.get("created_at", "")[:10],
                )
            )
        return entries

    def show(self, plan_id: str) -> Optional[ForgePlan]:
        """Load and return a specific plan by ID.

        Args:
            plan_id: Plan ID to load

        Returns:
            ForgePlan if found, None otherwise
        """
        plan = load_plan(plan_id)
        if plan:
            self._current_plan = plan
        return plan

    def compare(self, id1: str, id2: str) -> Optional[ForgeCompareOutput]:
        """Compare two plans side by side.

        Args:
            id1: Left plan ID
            id2: Right plan ID

        Returns:
            ForgeCompareOutput if both found, None otherwise
        """
        left = load_plan(id1)
        right = load_plan(id2)
        if not left or not right:
            return None

        return ForgeCompareOutput(
            left=self._plan_to_status(left),
            right=self._plan_to_status(right),
            left_phases=left.plan_phases,
            right_phases=right.plan_phases,
        )

    def patterns(self) -> list[dict]:
        """List reusable patterns from past plans.

        Returns:
            List of pattern dicts
        """
        return load_patterns()

    def cancel(self) -> bool:
        """Cancel the active plan.

        Returns:
            True if cancelled, False if no active plan
        """
        if self._current_plan is None:
            self._current_plan = get_active_plan()
        if self._current_plan is None:
            return False

        self._current_plan.status = ForgeStatus.CANCELLED
        save_plan(self._current_plan)
        clear_active_plan()
        return True

    # -------------------------------------------------------------------------
    # User Decision Handlers
    # -------------------------------------------------------------------------

    def approve(self) -> ForgePlan:
        """Handle user Approve decision.

        Runs steps 9-10: handoff and persist.

        Returns:
            Approved ForgePlan
        """
        if self._current_plan is None:
            raise RuntimeError("No active forge plan. Run forge() first.")

        self._step9_handoff()
        self._step10_persist()
        return self._current_plan

    def revise(self, revision_text: str) -> ForgePlan:
        """Handle user Revise decision.

        Re-runs critic only (not explorers), capped at 5 revisions.

        Args:
            revision_text: User's revision request

        Returns:
            Updated ForgePlan
        """
        if self._current_plan is None:
            raise RuntimeError("No active forge plan. Run forge() first.")

        plan = self._current_plan
        if plan.version > 5:
            raise RuntimeError("Maximum 5 revisions exceeded.")

        self._step6_critic_synthesis(revision_request=revision_text)
        self._step7_enforce_constitution()
        self._step8_build_plan()
        return self._current_plan

    def companion(self) -> str:
        """Generate HTML visual companion.

        Returns:
            Path to HTML file
        """
        if self._current_plan is None:
            raise RuntimeError("No active forge plan.")

        html = render_html(self._current_plan)
        path = f"/tmp/forge-{self._current_plan.id}.html"
        Path(path).write_text(html, encoding="utf-8")
        return path

    def detail(self, phase_index: int) -> Optional[str]:
        """Get detail for a specific phase.

        Args:
            phase_index: 1-based phase number

        Returns:
            Detailed string for the phase, or None if not found
        """
        if self._current_plan is None:
            return None
        if phase_index < 1 or phase_index > len(self._current_plan.plan_phases):
            return None

        phase = self._current_plan.plan_phases[phase_index - 1]
        lines = [
            f"Phase {phase_index}: {phase.name}",
            f"Department: {phase.department}",
            f"Agents: {', '.join(phase.agents) if phase.agents else 'none'}",
            "",
            "Deliverables:",
        ]
        for d in phase.deliverables or []:
            lines.append(f"  - {d}")
        lines.extend(["", "Acceptance Criteria:"])
        for c in phase.acceptance_criteria or []:
            lines.append(f"  - {c}")
        if phase.depends_on:
            lines.extend(["", f"Depends on: {', '.join(phase.depends_on)}"])
        return "\n".join(lines)

    def quit(self) -> ForgePlan:
        """Handle user Quit decision.

        Saves as draft and clears active.

        Returns:
            Draft ForgePlan
        """
        if self._current_plan is None:
            raise RuntimeError("No active forge plan.")

        self._current_plan.status = ForgeStatus.DRAFT
        save_plan(self._current_plan)
        clear_active_plan()
        return self._current_plan

    # -------------------------------------------------------------------------
    # Render Output
    # -------------------------------------------------------------------------

    def render(self) -> str:
        """Render current plan for terminal display.

        Returns:
            Terminal-formatted string
        """
        if self._current_plan is None:
            return "No active forge plan."
        return render_terminal(self._current_plan)

    def render_complexity(self) -> str:
        """Render complexity analysis.

        Returns:
            Complexity analysis string
        """
        if self._current_plan is None:
            return ""
        return render_complexity(self._current_plan.complexity)

    def _step9_render(self) -> None:
        """Step 9: Render the plan for user review."""
        if self._current_plan is None:
            return
        self._rendered_output = render_terminal(self._current_plan)

    # -------------------------------------------------------------------------
    # Internal Steps
    # -------------------------------------------------------------------------

    def _step1_snapshot_context(self, prompt: str) -> None:
        """Step 1: Collect git context."""
        try:
            git_rev = subprocess.run(
                ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
            )
            commit = git_rev.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            commit = "unknown"

        try:
            git_branch = subprocess.run(
                ["git", "branch", "--show-current"], capture_output=True, text=True, check=True
            )
            branch = git_branch.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            branch = "unknown"

        try:
            git_remote = subprocess.run(
                ["git", "remote", "get-url", "origin"], capture_output=True, text=True
            )
            repo = git_remote.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            repo = Path.cwd().name

        version_file = Path(__file__).parent.parent.parent / "VERSION"
        version = version_file.read_text().strip() if version_file.exists() else "unknown"

        self._forge_context = ForgeContext(
            repo=repo,
            branch=branch,
            commit_at_forge=commit,
            arkaos_version=version,
            prompt=prompt,
        )

    def _step2_obsidian_check(self) -> None:
        """Step 2: Check Obsidian for similar plans and patterns."""
        self._similar_plans: list[str] = []
        self._reused_patterns: list[str] = []

        try:
            patterns = load_patterns()
            for p in patterns:
                if any(kw in p.get("tags", []) for kw in ["dev", "forge"]):
                    self._reused_patterns.append(p.get("name", ""))
        except Exception:
            pass

    def _step3_complexity(self) -> None:
        """Step 3: Analyze complexity."""
        prompt = self._forge_context.prompt
        affected_files = self._estimate_affected_files(prompt)
        departments = self._estimate_departments(prompt)

        result = analyze_complexity(
            prompt=prompt,
            affected_files=affected_files,
            departments=departments,
            similar_plans=self._similar_plans,
            reused_patterns=self._reused_patterns,
        )
        self._complexity = result

    def _step4_confirm_tier(self) -> ForgeTier:
        """Step 4: Confirm tier (returns current tier, caller handles user input).

        Returns:
            Confirmed ForgeTier
        """
        self._confirmed_tier = self._complexity.tier
        return self._confirmed_tier

    def set_tier(self, tier: ForgeTier) -> None:
        """Override the confirmed tier (after user override request).

        Args:
            tier: New tier to use
        """
        self._confirmed_tier = tier

    def _step5_launch_explorers(self) -> None:
        """Step 5: Launch explorer subagents in parallel."""
        tier = self._confirmed_tier
        lens_map = {
            ForgeTier.SHALLOW: [ExplorerLens.PRAGMATIC],
            ForgeTier.STANDARD: [ExplorerLens.PRAGMATIC, ExplorerLens.ARCHITECTURAL],
            ForgeTier.DEEP: [
                ExplorerLens.PRAGMATIC,
                ExplorerLens.ARCHITECTURAL,
                ExplorerLens.CONTRARIAN,
            ],
        }
        lenses = lens_map.get(tier, [ExplorerLens.PRAGMATIC])
        model = _tier_to_model(tier)

        self._approaches: list[ExplorerApproach] = []
        requests = [
            ExplorerDispatchRequest(
                lens=lens,
                prompt=self._forge_context.prompt,
                context=self._forge_context,
                similar_plans=self._similar_plans,
                reused_patterns=self._reused_patterns,
                model=model,
            )
            for lens in lenses
        ]

        for req in requests:
            try:
                approach = self._dispatcher.dispatch_explorer_and_parse(req)
                self._approaches.append(approach)
            except Exception as e:
                pass

    def _step6_critic_synthesis(self, revision_request: Optional[str] = None) -> None:
        """Step 6: Launch critic subagent for synthesis.

        Args:
            revision_request: Optional revision text from user
        """
        model = _tier_to_model(self._confirmed_tier)
        critic_req = CriticDispatchRequest(
            original_prompt=self._forge_context.prompt,
            approaches=self._approaches,
            model=model,
        )

        try:
            self._critic_verdict = self._dispatcher.dispatch_critic_and_parse(critic_req)
        except Exception:
            self._critic_verdict = CriticVerdict(
                synthesis={"approach_1": [a.summary for a in self._approaches]},
                rejected_elements=[],
                risks=[],
                confidence=0.5,
                estimated_phases=len(self._approaches[0].phases) if self._approaches else 3,
            )

        if revision_request:
            self._critic_verdict.synthesis["revision_request"] = [revision_request]

    def _step7_enforce_constitution(self) -> None:
        """Step 7: Enforce Constitution rules - add missing phases."""
        self._enforced_phases: list[PlanPhase] = []
        phase_names = [p.name.lower() for p in self._final_phases_from_critic()]

        has_branch = any("branch" in n or "feature" in n for n in phase_names)
        has_spec = any("spec" in n or "specification" in n for n in phase_names)
        has_qg = any("quality" in n or "gate" in n or "qg" in n for n in phase_names)
        has_obsidian = any("obsidian" in n or "persist" in n or "persist" in n for n in phase_names)

        enforced = []
        if not has_branch:
            enforced.append(
                PlanPhase(
                    name="Create feature branch",
                    department="dev",
                    agents=["developer"],
                    deliverables=["feature/forge-xyz branch created"],
                    acceptance_criteria=["git branch created from main"],
                )
            )
        if not has_spec and self._confirmed_tier != ForgeTier.SHALLOW:
            enforced.append(
                PlanPhase(
                    name="Write specification",
                    department="dev",
                    agents=["architect"],
                    deliverables=["SPEC.md created"],
                    acceptance_criteria=["spec approved"],
                )
            )
        if not has_qg:
            enforced.append(
                PlanPhase(
                    name="Quality Gate",
                    department="quality",
                    agents=["cqo"],
                    deliverables=["QA review completed"],
                    acceptance_criteria=["Marta APPROVED"],
                )
            )
        if not has_obsidian:
            enforced.append(
                PlanPhase(
                    name="Persist to Obsidian",
                    department="kb",
                    agents=["knowledge-curator"],
                    deliverables=["plan archived in Obsidian"],
                    acceptance_criteria=["Obsidian note created"],
                )
            )

        self._enforced_phases = enforced

    def _step8_build_plan(self) -> None:
        """Step 8: Build the ForgePlan object."""
        plan_id = self._generate_plan_id(self._forge_context.prompt)
        execution_path = select_execution_path(self._final_phases_from_critic())

        self._current_plan = ForgePlan(
            id=plan_id,
            name=self._forge_context.prompt[:60],
            created_at=datetime.now(timezone.utc).isoformat(),
            forged_by="forge",
            version=1,
            context=self._forge_context,
            complexity=self._complexity,
            approaches=self._approaches,
            critic=self._critic_verdict,
            plan_phases=self._final_phases_from_critic(),
            goal=self._forge_context.prompt,
            execution_path=execution_path,
            governance=ForgeGovernance(
                constitution_check="passed",
                quality_gate_required=True,
                branch_strategy=f"feature/{plan_id}",
            ),
            status=ForgeStatus.REVIEWING,
        )

    def _step9_handoff(self) -> None:
        """Step 9: Handoff - check drift, select execution path."""
        drift = check_repo_drift(self._current_plan.context.commit_at_forge)
        self._drift = drift

        if drift["changed"]:
            pass

        self._current_plan.status = ForgeStatus.APPROVED
        self._current_plan.approved_at = datetime.now(timezone.utc).isoformat()

        exec_path = select_execution_path(self._current_plan.plan_phases)
        self._current_plan.execution_path = exec_path

    def _step10_persist(self) -> None:
        """Step 10: Persist plan to YAML and Obsidian."""
        save_plan(self._current_plan)
        set_active_plan(self._current_plan.id)

        try:
            export_to_obsidian(self._current_plan)
        except Exception:
            pass

        try:
            patterns = extract_patterns(self._current_plan)
            if patterns:
                pass
        except Exception:
            pass

    def _final_phases_from_critic(self) -> list[PlanPhase]:
        """Build final phases list from critic verdict + constitution enforcement."""
        phases = []
        for i, p in enumerate(range(self._critic_verdict.estimated_phases or 3)):
            phases.append(
                PlanPhase(
                    name=f"Phase {i + 1}",
                    department="dev",
                )
            )

        for ep in self._enforced_phases:
            phases.append(ep)

        return phases

    def _generate_plan_id(self, prompt: str) -> str:
        """Generate a forge plan ID."""
        date = datetime.now(timezone.utc).strftime("%Y%m%d")
        suffix = hashlib.md5(prompt.encode()).hexdigest()[:4]
        return f"forge-{date}-{suffix}"

    def _estimate_affected_files(self, prompt: str) -> list[str]:
        """Estimate affected files from prompt keywords."""
        keywords = {
            "auth": ["auth/", "middleware/auth.py"],
            "db": ["core/db/", "models/"],
            "api": ["routes/", "controllers/"],
            "test": ["tests/"],
            "config": ["config/", ".env"],
        }
        files = []
        lower = prompt.lower()
        for kw, paths in keywords.items():
            if kw in lower:
                files.extend(paths)
        return files

    def _estimate_departments(self, prompt: str) -> list[str]:
        """Estimate departments from prompt keywords."""
        keywords = {
            "dev": ["dev"],
            "marketing": ["mkt", "marketing", "content"],
            "brand": ["brand", "design"],
            "sales": ["sales"],
            "ops": ["ops", "operations"],
        }
        depts = []
        lower = prompt.lower()
        for kw, depts_list in keywords.items():
            if kw in lower:
                depts.extend(depts_list)
        return list(set(depts)) or ["dev"]

    def _plan_to_status(self, plan: ForgePlan) -> ForgeStatusOutput:
        """Convert ForgePlan to ForgeStatusOutput."""
        depts = list({p.department for p in plan.plan_phases})
        return ForgeStatusOutput(
            plan_id=plan.id,
            name=plan.name,
            status=plan.status,
            tier=plan.complexity.tier,
            score=plan.complexity.score,
            confidence=plan.critic.confidence,
            n_phases=len(plan.plan_phases),
            departments=depts,
            created_at=plan.created_at,
            revision_count=plan.version - 1,
        )
