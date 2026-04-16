"""Tests for ForgeOrchestrator — 10-step planning flow."""

import pytest
from unittest.mock import MagicMock, patch, Mock
from pathlib import Path

from core.forge.schema import (
    ForgePlan,
    ForgeContext,
    ForgeStatus,
    ForgeTier,
    ComplexityScore,
    ComplexityDimensions,
    ExplorerLens,
    ExplorerApproach,
    CriticVerdict,
    RejectedElement,
    IdentifiedRisk,
    RiskSeverity,
    PlanPhase,
    ExecutionPath,
    ExecutionPathType,
    ForgeGovernance,
    KeyDecision,
    PhaseDeliverable,
)
from core.forge.orchestrator import (
    ForgeOrchestrator,
    ForgeDecision,
    ForgeStep,
    ForgeStatusOutput,
    ForgeHistoryEntry,
    ForgeCompareOutput,
    CONSTITUTION_PHASES,
)
from core.forge.runtime_dispatcher import (
    ForgeTaskDispatcher,
    ExplorerDispatchRequest,
    CriticDispatchRequest,
    DispatchResult,
    _tier_to_model,
)


def _make_context(prompt="test prompt"):
    return ForgeContext(
        repo="test-repo",
        branch="main",
        commit_at_forge="abc123",
        arkaos_version="2.0.0",
        prompt=prompt,
    )


def _make_complexity(tier=ForgeTier.STANDARD, score=50):
    return ComplexityScore(
        score=score,
        tier=tier,
        dimensions=ComplexityDimensions(
            scope=50, dependencies=50, ambiguity=50, risk=50, novelty=50
        ),
    )


def _make_approach(lens=ExplorerLens.PRAGMATIC):
    return ExplorerApproach(
        explorer=lens,
        summary="Test approach summary",
        key_decisions=[KeyDecision(decision="test decision", rationale="test rationale")],
        phases=[
            PhaseDeliverable(
                name="Phase 1",
                department="dev",
                agents=["developer"],
                deliverables=["deliverable 1"],
                acceptance_criteria=["criterion 1"],
            )
        ],
        estimated_total_effort="medium",
        risks=["test risk"],
        reuses_patterns=["test-pattern"],
    )


def _make_critic_verdict(estimated_phases=3):
    return CriticVerdict(
        synthesis={"approach_1": ["element 1", "element 2"]},
        rejected_elements=[RejectedElement(element="rejected element", reason="not optimal")],
        risks=[
            IdentifiedRisk(
                risk="identified risk",
                mitigation="mitigation steps",
                severity=RiskSeverity.MEDIUM,
            )
        ],
        confidence=0.75,
        estimated_phases=estimated_phases,
        estimated_departments=["dev"],
    )


def _make_plan(
    plan_id="forge-test-001",
    name="Test Plan",
    status=ForgeStatus.REVIEWING,
    tier=ForgeTier.STANDARD,
):
    ctx = _make_context()
    complexity = _make_complexity(tier=tier)
    approach = _make_approach()
    critic = _make_critic_verdict()

    return ForgePlan(
        id=plan_id,
        name=name,
        created_at="2026-01-01T00:00:00Z",
        forged_by="forge",
        version=1,
        context=ctx,
        complexity=complexity,
        approaches=[approach],
        critic=critic,
        plan_phases=[
            PlanPhase(
                name="Phase 1",
                department="dev",
                agents=["developer"],
                deliverables=["deliverable 1"],
                acceptance_criteria=["criterion 1"],
            )
        ],
        goal=ctx.prompt,
        execution_path=ExecutionPath(
            type=ExecutionPathType.WORKFLOW,
            target="test-workflow.yaml",
            departments=["dev"],
            estimated_commits=3,
        ),
        governance=ForgeGovernance(
            constitution_check="passed",
            violations=[],
            quality_gate_required=True,
            branch_strategy=f"feature/{plan_id}",
        ),
        status=status,
    )


class MockDispatcher(ForgeTaskDispatcher):
    """Mock dispatcher for testing — returns predictable results."""

    def __init__(self):
        super().__init__()
        self.explorer_calls = []
        self.critic_calls = []

    def dispatch_explorer(self, request: ExplorerDispatchRequest) -> DispatchResult:
        self.explorer_calls.append(request)
        return DispatchResult(
            success=True,
            raw_response=self._mock_explorer_output(request.lens),
            output="mock explorer output",
        )

    def dispatch_critic(self, request: CriticDispatchRequest) -> DispatchResult:
        self.critic_calls.append(request)
        return DispatchResult(
            success=True,
            raw_response=self._mock_critic_output(),
            output="mock critic output",
        )

    def _mock_explorer_output(self, lens: ExplorerLens) -> str:
        return f"""EXPLORER: {lens.value}
SUMMARY: Mock approach summary for {lens.value} lens
KEY_DECISIONS:
  - decision: test decision
    rationale: test rationale
PHASES:
  - name: Phase 1
    department: dev
    agents: [developer]
    deliverables: [deliverable 1]
    acceptance_criteria: [criterion 1]
    depends_on: []
"""

    def _mock_critic_output(self) -> str:
        return """CONFIDENCE: 0.75
SYNTHESIS:
  approach_1: [element 1, element 2]
REJECTED:
  - element: rejected element
    reason: not optimal
RISKS:
  - risk: identified risk
    severity: medium
    mitigation: mitigation steps
FINAL_PHASES:
  - name: Phase 1
    department: dev
    agents: [developer]
    deliverables: [deliverable 1]
    acceptance_criteria: [criterion 1]
    depends_on: []
"""


# =============================================================================
# TestForgeOrchestrator — Basic
# =============================================================================


class TestForgeOrchestratorInit:
    def test_default_dispatcher_is_claude_code(self):
        with patch("core.forge.orchestrator.ClaudeCodeForgeDispatcher") as mock:
            orch = ForgeOrchestrator()
            mock.assert_called_once()

    def test_custom_dispatcher(self):
        mock_dispatcher = MockDispatcher()
        orch = ForgeOrchestrator(dispatcher=mock_dispatcher)
        assert orch._dispatcher is mock_dispatcher

    def test_initial_state_no_plan(self):
        orch = ForgeOrchestrator()
        assert orch._current_plan is None
        assert orch._current_step is None


class TestForgeOrchestratorState:
    def test_current_step_initially_none(self):
        orch = ForgeOrchestrator()
        assert orch._current_step is None

    def test_current_plan_initially_none(self):
        orch = ForgeOrchestrator()
        assert orch._current_plan is None


# =============================================================================
# TestForgeSteps — Individual Step Methods
# =============================================================================


class TestStep1SnapshotContext:
    def test_collects_git_info(self):
        orch = ForgeOrchestrator()
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                Mock(stdout=Mock(strip=lambda: "abc123")),
                Mock(stdout=Mock(strip=lambda: "main")),
                Mock(stdout=Mock(strip=lambda: "git@github.com:test/repo.git")),
            ]
            orch._step1_snapshot_context("test prompt")

            assert orch._forge_context is not None
            assert orch._forge_context.prompt == "test prompt"
            assert orch._forge_context.commit_at_forge == "abc123"
            assert orch._forge_context.branch == "main"

    def test_handles_missing_git(self):
        import subprocess

        orch = ForgeOrchestrator()
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, "git")
            orch._step1_snapshot_context("test prompt")

            assert orch._forge_context.commit_at_forge == "unknown"
            assert orch._forge_context.branch == "unknown"


class TestStep2ObsidianCheck:
    def test_loads_patterns(self):
        orch = ForgeOrchestrator()
        orch._forge_context = _make_context()
        with patch("core.forge.orchestrator.load_patterns") as mock_load:
            mock_load.return_value = [
                {"name": "pattern1", "tags": ["dev"]},
                {"name": "pattern2", "tags": ["mkt"]},
            ]
            orch._step2_obsidian_check()

            assert orch._reused_patterns == ["pattern1"]

    def test_handles_load_errors(self):
        orch = ForgeOrchestrator()
        orch._forge_context = _make_context()
        with patch("core.forge.orchestrator.load_patterns") as mock_load:
            mock_load.side_effect = Exception("load error")
            orch._step2_obsidian_check()

            assert orch._reused_patterns == []


class TestStep3Complexity:
    def test_calls_analyze_complexity(self):
        orch = ForgeOrchestrator()
        orch._forge_context = _make_context()
        orch._similar_plans = []
        orch._reused_patterns = []

        with patch("core.forge.orchestrator.analyze_complexity") as mock_analyze:
            mock_result = _make_complexity()
            mock_analyze.return_value = mock_result

            orch._step3_complexity()

            mock_analyze.assert_called_once()
            assert orch._complexity is mock_result


class TestStep4ConfirmTier:
    def test_returns_complexity_tier(self):
        orch = ForgeOrchestrator()
        orch._complexity = _make_complexity(tier=ForgeTier.DEEP)

        tier = orch._step4_confirm_tier()

        assert tier == ForgeTier.DEEP
        assert orch._confirmed_tier == ForgeTier.DEEP

    def test_set_tier_overrides(self):
        orch = ForgeOrchestrator()
        orch._confirmed_tier = ForgeTier.SHALLOW

        orch.set_tier(ForgeTier.DEEP)

        assert orch._confirmed_tier == ForgeTier.DEEP


class TestStep5LaunchExplorers:
    def test_launches_single_explorer_for_shallow(self):
        mock_dispatcher = MockDispatcher()
        orch = ForgeOrchestrator(dispatcher=mock_dispatcher)
        orch._confirmed_tier = ForgeTier.SHALLOW
        orch._forge_context = _make_context()
        orch._similar_plans = []
        orch._reused_patterns = []

        orch._step5_launch_explorers()

        assert len(mock_dispatcher.explorer_calls) == 1
        assert mock_dispatcher.explorer_calls[0].lens == ExplorerLens.PRAGMATIC

    def test_launches_two_explorers_for_standard(self):
        mock_dispatcher = MockDispatcher()
        orch = ForgeOrchestrator(dispatcher=mock_dispatcher)
        orch._confirmed_tier = ForgeTier.STANDARD
        orch._forge_context = _make_context()
        orch._similar_plans = []
        orch._reused_patterns = []

        orch._step5_launch_explorers()

        assert len(mock_dispatcher.explorer_calls) == 2
        lenses = {c.lens for c in mock_dispatcher.explorer_calls}
        assert ExplorerLens.PRAGMATIC in lenses
        assert ExplorerLens.ARCHITECTURAL in lenses

    def test_launches_three_explorers_for_deep(self):
        mock_dispatcher = MockDispatcher()
        orch = ForgeOrchestrator(dispatcher=mock_dispatcher)
        orch._confirmed_tier = ForgeTier.DEEP
        orch._forge_context = _make_context()
        orch._similar_plans = []
        orch._reused_patterns = []

        orch._step5_launch_explorers()

        assert len(mock_dispatcher.explorer_calls) == 3
        lenses = {c.lens for c in mock_dispatcher.explorer_calls}
        assert ExplorerLens.PRAGMATIC in lenses
        assert ExplorerLens.ARCHITECTURAL in lenses
        assert ExplorerLens.CONTRARIAN in lenses

    def test_handles_dispatcher_exception(self):
        mock_dispatcher = MagicMock(spec=ForgeTaskDispatcher)
        mock_dispatcher.dispatch_explorer_and_parse.side_effect = Exception("dispatch error")

        orch = ForgeOrchestrator(dispatcher=mock_dispatcher)
        orch._confirmed_tier = ForgeTier.SHALLOW
        orch._forge_context = _make_context()
        orch._similar_plans = []
        orch._reused_patterns = []

        orch._step5_launch_explorers()

        assert orch._approaches == []


class TestStep6CriticSynthesis:
    def test_calls_dispatcher_critic(self):
        mock_dispatcher = MockDispatcher()
        orch = ForgeOrchestrator(dispatcher=mock_dispatcher)
        orch._forge_context = _make_context()
        orch._approaches = [_make_approach()]
        orch._confirmed_tier = ForgeTier.STANDARD

        orch._step6_critic_synthesis()

        assert len(mock_dispatcher.critic_calls) == 1
        assert mock_dispatcher.critic_calls[0].original_prompt == orch._forge_context.prompt

    def test_fallback_on_critic_error(self):
        mock_dispatcher = MagicMock(spec=ForgeTaskDispatcher)
        mock_dispatcher.dispatch_critic_and_parse.side_effect = Exception("critic error")

        orch = ForgeOrchestrator(dispatcher=mock_dispatcher)
        orch._forge_context = _make_context()
        orch._approaches = [_make_approach()]
        orch._confirmed_tier = ForgeTier.STANDARD

        orch._step6_critic_synthesis()

        assert orch._critic_verdict is not None
        assert orch._critic_verdict.confidence == 0.5

    def test_revision_request_appended(self):
        mock_dispatcher = MockDispatcher()
        orch = ForgeOrchestrator(dispatcher=mock_dispatcher)
        orch._forge_context = _make_context()
        orch._approaches = [_make_approach()]
        orch._confirmed_tier = ForgeTier.STANDARD

        orch._step6_critic_synthesis(revision_request="add more tests")

        assert "revision_request" in orch._critic_verdict.synthesis


class TestStep7ConstitutionEnforcement:
    def test_adds_branch_phase_when_missing(self):
        orch = ForgeOrchestrator()
        orch._critic_verdict = _make_critic_verdict(estimated_phases=2)
        orch._confirmed_tier = ForgeTier.STANDARD
        orch._enforced_phases = []

        orch._step7_enforce_constitution()

        branch_phases = [p for p in orch._enforced_phases if "branch" in p.name.lower()]
        assert len(branch_phases) == 1

    def test_adds_spec_phase_for_non_shallow(self):
        orch = ForgeOrchestrator()
        orch._critic_verdict = _make_critic_verdict(estimated_phases=2)
        orch._confirmed_tier = ForgeTier.STANDARD
        orch._enforced_phases = []

        orch._step7_enforce_constitution()

        spec_phases = [p for p in orch._enforced_phases if "spec" in p.name.lower()]
        assert len(spec_phases) == 1

    def test_no_spec_phase_for_shallow(self):
        orch = ForgeOrchestrator()
        orch._critic_verdict = _make_critic_verdict(estimated_phases=1)
        orch._confirmed_tier = ForgeTier.SHALLOW
        orch._enforced_phases = []

        orch._step7_enforce_constitution()

        spec_phases = [p for p in orch._enforced_phases if "spec" in p.name.lower()]
        assert len(spec_phases) == 0

    def test_adds_quality_gate_phase(self):
        orch = ForgeOrchestrator()
        orch._critic_verdict = _make_critic_verdict(estimated_phases=2)
        orch._confirmed_tier = ForgeTier.STANDARD
        orch._enforced_phases = []

        orch._step7_enforce_constitution()

        qg_phases = [p for p in orch._enforced_phases if "quality" in p.name.lower()]
        assert len(qg_phases) == 1

    def test_adds_obsidian_phase(self):
        orch = ForgeOrchestrator()
        orch._critic_verdict = _make_critic_verdict(estimated_phases=2)
        orch._confirmed_tier = ForgeTier.STANDARD
        orch._enforced_phases = []

        orch._step7_enforce_constitution()

        obsidian_phases = [p for p in orch._enforced_phases if "obsidian" in p.name.lower()]
        assert len(obsidian_phases) == 1


class TestStep8BuildPlan:
    def test_creates_forge_plan(self):
        orch = ForgeOrchestrator()
        _setup_orchestrator(orch)

        orch._step8_build_plan()

        assert orch._current_plan is not None
        assert orch._current_plan.status == ForgeStatus.REVIEWING

    def test_plan_has_id(self):
        orch = ForgeOrchestrator()
        _setup_orchestrator(orch)

        orch._step8_build_plan()

        assert orch._current_plan.id.startswith("forge-")

    def test_plan_has_phases(self):
        orch = ForgeOrchestrator()
        _setup_orchestrator(orch)

        orch._step8_build_plan()

        assert len(orch._current_plan.plan_phases) > 0

    def test_plan_has_governance(self):
        orch = ForgeOrchestrator()
        _setup_orchestrator(orch)

        orch._step8_build_plan()

        assert orch._current_plan.governance is not None
        assert orch._current_plan.governance.quality_gate_required is True


def _setup_orchestrator(orch: ForgeOrchestrator):
    """Helper to set up all required orchestrator state."""
    orch._forge_context = _make_context()
    orch._similar_plans = []
    orch._reused_patterns = []
    orch._complexity = _make_complexity()
    orch._confirmed_tier = ForgeTier.STANDARD
    orch._approaches = [_make_approach()]
    orch._critic_verdict = _make_critic_verdict()
    orch._enforced_phases = []


# =============================================================================
# TestForgeCommands — forge(), resume(), status(), history(), show(), compare(), patterns(), cancel()
# =============================================================================


class TestForgeCommand:
    def test_forge_returns_plan(self):
        mock_dispatcher = MockDispatcher()
        orch = ForgeOrchestrator(dispatcher=mock_dispatcher)

        plan = orch.forge("build auth module")

        assert plan is not None
        assert isinstance(plan, ForgePlan)
        assert plan.status == ForgeStatus.REVIEWING

    def test_forge_sets_current_plan(self):
        mock_dispatcher = MockDispatcher()
        orch = ForgeOrchestrator(dispatcher=mock_dispatcher)

        plan = orch.forge("build auth module")

        assert orch._current_plan is plan

    def test_forge_runs_all_steps(self):
        mock_dispatcher = MockDispatcher()
        orch = ForgeOrchestrator(dispatcher=mock_dispatcher)

        with (
            patch.object(orch, "_step1_snapshot_context") as s1,
            patch.object(orch, "_step2_obsidian_check") as s2,
            patch.object(orch, "_step3_complexity") as s3,
            patch.object(orch, "_step4_confirm_tier") as s4,
            patch.object(orch, "_step5_launch_explorers") as s5,
            patch.object(orch, "_step6_critic_synthesis") as s6,
            patch.object(orch, "_step7_enforce_constitution") as s7,
            patch.object(orch, "_step8_build_plan") as s8,
            patch.object(orch, "_step9_render") as s9,
        ):
            orch.forge("test")

            s1.assert_called_once()
            s2.assert_called_once()
            s3.assert_called_once()
            s4.assert_called_once()
            s5.assert_called_once()
            s6.assert_called_once()
            s7.assert_called_once()
            s8.assert_called_once()
            s9.assert_called_once()


class TestResumeCommand:
    def test_resume_returns_none_when_no_active(self):
        orch = ForgeOrchestrator()
        with patch("core.forge.orchestrator.get_active_plan") as mock_get:
            mock_get.return_value = None

            result = orch.resume()

            assert result is None

    def test_resume_returns_active_plan(self):
        mock_plan = _make_plan()
        orch = ForgeOrchestrator()
        with patch("core.forge.orchestrator.get_active_plan") as mock_get:
            mock_get.return_value = mock_plan

            result = orch.resume()

            assert result is mock_plan
            assert orch._current_plan is mock_plan


class TestStatusCommand:
    def test_status_returns_none_when_no_plan(self):
        orch = ForgeOrchestrator()
        with patch("core.forge.orchestrator.get_active_plan") as mock_get:
            mock_get.return_value = None

            result = orch.status()

            assert result is None

    def test_status_returns_status_output(self):
        mock_plan = _make_plan()
        orch = ForgeOrchestrator()
        orch._current_plan = mock_plan

        result = orch.status()

        assert result is not None
        assert result.plan_id == mock_plan.id
        assert result.name == mock_plan.name
        assert result.status == mock_plan.status
        assert result.tier == mock_plan.complexity.tier

    def test_status_extracts_departments(self):
        plan = _make_plan()
        plan.plan_phases = [
            PlanPhase(name="Phase 1", department="dev"),
            PlanPhase(name="Phase 2", department="mkt"),
        ]
        orch = ForgeOrchestrator()
        orch._current_plan = plan

        result = orch.status()

        assert "dev" in result.departments
        assert "mkt" in result.departments


class TestHistoryCommand:
    def test_history_returns_empty_list(self):
        orch = ForgeOrchestrator()
        with patch("core.forge.orchestrator.list_plans") as mock_list:
            mock_list.return_value = []

            result = orch.history()

            assert result == []

    def test_history_returns_entries(self):
        orch = ForgeOrchestrator()
        with patch("core.forge.orchestrator.list_plans") as mock_list:
            mock_list.return_value = [
                {
                    "id": "forge-001",
                    "name": "Plan 1",
                    "status": "completed",
                    "complexity": {"tier": "standard"},
                    "critic": {"confidence": 0.8},
                    "created_at": "2026-01-01T00:00:00Z",
                }
            ]

            result = orch.history()

            assert len(result) == 1
            assert result[0].plan_id == "forge-001"


class TestShowCommand:
    def test_show_returns_none_for_missing_plan(self):
        orch = ForgeOrchestrator()
        with patch("core.forge.orchestrator.load_plan") as mock_load:
            mock_load.return_value = None

            result = orch.show("missing-id")

            assert result is None

    def test_show_returns_plan_and_sets_current(self):
        mock_plan = _make_plan()
        orch = ForgeOrchestrator()
        with patch("core.forge.orchestrator.load_plan") as mock_load:
            mock_load.return_value = mock_plan

            result = orch.show("forge-test-001")

            assert result is mock_plan
            assert orch._current_plan is mock_plan


class TestCompareCommand:
    def test_compare_returns_none_if_left_missing(self):
        orch = ForgeOrchestrator()
        with patch("core.forge.orchestrator.load_plan") as mock_load:
            mock_load.side_effect = [None, _make_plan()]

            result = orch.compare("missing", "forge-test-001")

            assert result is None

    def test_compare_returns_none_if_right_missing(self):
        orch = ForgeOrchestrator()
        with patch("core.forge.orchestrator.load_plan") as mock_load:
            mock_load.side_effect = [_make_plan(), None]

            result = orch.compare("forge-001", "missing")

            assert result is None

    def test_compare_returns_compare_output(self):
        left = _make_plan("left-id", "Left Plan")
        right = _make_plan("right-id", "Right Plan")
        orch = ForgeOrchestrator()
        with patch("core.forge.orchestrator.load_plan") as mock_load:
            mock_load.side_effect = [left, right]

            result = orch.compare("left-id", "right-id")

            assert result is not None
            assert result.left.plan_id == "left-id"
            assert result.right.plan_id == "right-id"


class TestPatternsCommand:
    def test_patterns_calls_load_patterns(self):
        orch = ForgeOrchestrator()
        with patch("core.forge.orchestrator.load_patterns") as mock_load:
            mock_load.return_value = [{"name": "p1"}, {"name": "p2"}]

            result = orch.patterns()

            mock_load.assert_called_once()
            assert len(result) == 2


class TestCancelCommand:
    def test_cancel_returns_false_when_no_plan(self):
        orch = ForgeOrchestrator()
        with patch("core.forge.orchestrator.get_active_plan") as mock_get:
            mock_get.return_value = None

            result = orch.cancel()

            assert result is False

    def test_cancel_returns_true_and_updates_status(self):
        mock_plan = _make_plan(status=ForgeStatus.REVIEWING)
        orch = ForgeOrchestrator()
        orch._current_plan = mock_plan

        with (
            patch("core.forge.orchestrator.save_plan") as mock_save,
            patch("core.forge.orchestrator.clear_active_plan") as mock_clear,
        ):
            result = orch.cancel()

            assert result is True
            assert mock_plan.status == ForgeStatus.CANCELLED
            mock_save.assert_called_once_with(mock_plan)
            mock_clear.assert_called_once()


# =============================================================================
# TestForgeDecisions — approve(), revise(), companion(), detail(), quit()
# =============================================================================


class TestApproveDecision:
    def test_approve_requires_active_plan(self):
        orch = ForgeOrchestrator()

        with pytest.raises(RuntimeError, match="No active forge plan"):
            orch.approve()

    def test_approve_runs_step9_and_step10(self):
        mock_plan = _make_plan()
        orch = ForgeOrchestrator()
        orch._current_plan = mock_plan

        with (
            patch.object(orch, "_step9_handoff") as s9,
            patch.object(orch, "_step10_persist") as s10,
        ):
            result = orch.approve()

            s9.assert_called_once()
            s10.assert_called_once()
            assert result is mock_plan

    def test_approve_sets_status_to_approved(self):
        mock_plan = _make_plan(status=ForgeStatus.REVIEWING)
        orch = ForgeOrchestrator()
        orch._current_plan = mock_plan

        with patch.object(orch, "_step10_persist"):
            orch.approve()

            assert mock_plan.status == ForgeStatus.APPROVED


class TestReviseDecision:
    def test_revise_requires_active_plan(self):
        orch = ForgeOrchestrator()

        with pytest.raises(RuntimeError, match="No active forge plan"):
            orch.revise("add tests")

    def test_revise_caps_at_5_revisions(self):
        mock_plan = _make_plan()
        mock_plan.version = 6
        orch = ForgeOrchestrator()
        orch._current_plan = mock_plan

        with pytest.raises(RuntimeError, match="Maximum 5 revisions"):
            orch.revise("add tests")

    def test_revise_runs_critic_and_build(self):
        mock_plan = _make_plan()
        orch = ForgeOrchestrator()
        orch._current_plan = mock_plan

        with (
            patch.object(orch, "_step6_critic_synthesis") as s6,
            patch.object(orch, "_step7_enforce_constitution") as s7,
            patch.object(orch, "_step8_build_plan") as s8,
        ):
            orch.revise("add more tests")

            s6.assert_called_once_with(revision_request="add more tests")
            s7.assert_called_once()
            s8.assert_called_once()


class TestCompanionDecision:
    def test_companion_requires_active_plan(self):
        orch = ForgeOrchestrator()

        with pytest.raises(RuntimeError, match="No active forge plan"):
            orch.companion()

    def test_companion_returns_html_path(self):
        mock_plan = _make_plan()
        orch = ForgeOrchestrator()
        orch._current_plan = mock_plan

        with patch("core.forge.orchestrator.render_html") as mock_render:
            mock_render.return_value = "<html>test</html>"
            path = orch.companion()

            assert path.startswith("/tmp/forge-")


class TestDetailDecision:
    def test_detail_returns_none_with_no_plan(self):
        orch = ForgeOrchestrator()

        result = orch.detail(1)

        assert result is None

    def test_detail_returns_none_for_invalid_phase(self):
        mock_plan = _make_plan()
        orch = ForgeOrchestrator()
        orch._current_plan = mock_plan

        result = orch.detail(99)

        assert result is None

    def test_detail_returns_phase_detail(self):
        mock_plan = _make_plan()
        orch = ForgeOrchestrator()
        orch._current_plan = mock_plan

        result = orch.detail(1)

        assert "Phase 1" in result
        assert "dev" in result


class TestQuitDecision:
    def test_quit_requires_active_plan(self):
        orch = ForgeOrchestrator()

        with pytest.raises(RuntimeError, match="No active forge plan"):
            orch.quit()

    def test_quit_sets_status_to_draft(self):
        mock_plan = _make_plan(status=ForgeStatus.REVIEWING)
        orch = ForgeOrchestrator()
        orch._current_plan = mock_plan

        with (
            patch("core.forge.orchestrator.save_plan") as mock_save,
            patch("core.forge.orchestrator.clear_active_plan") as mock_clear,
        ):
            orch.quit()

            assert mock_plan.status == ForgeStatus.DRAFT
            mock_save.assert_called_once()
            mock_clear.assert_called_once()


# =============================================================================
# TestRenderOutput
# =============================================================================


class TestRenderOutput:
    def test_render_returns_no_plan_message(self):
        orch = ForgeOrchestrator()

        result = orch.render()

        assert result == "No active forge plan."

    def test_render_calls_render_terminal(self):
        mock_plan = _make_plan()
        orch = ForgeOrchestrator()
        orch._current_plan = mock_plan

        with patch("core.forge.orchestrator.render_terminal") as mock_render:
            mock_render.return_value = "rendered output"
            result = orch.render()

            mock_render.assert_called_once_with(mock_plan)
            assert result == "rendered output"

    def test_render_complexity_empty_without_plan(self):
        orch = ForgeOrchestrator()

        result = orch.render_complexity()

        assert result == ""

    def test_render_complexity_calls_render_function(self):
        mock_plan = _make_plan()
        orch = ForgeOrchestrator()
        orch._current_plan = mock_plan

        with patch("core.forge.orchestrator.render_complexity") as mock_render:
            mock_render.return_value = "complexity output"
            result = orch.render_complexity()

            mock_render.assert_called_once_with(mock_plan.complexity)


# =============================================================================
# TestConstitutionEnforcement
# =============================================================================


class TestConstitutionEnforcement:
    def test_enforces_all_constitution_phases(self):
        """Verify all 4 constitution phases are added when missing."""
        orch = ForgeOrchestrator()
        orch._critic_verdict = _make_critic_verdict(estimated_phases=1)
        orch._confirmed_tier = ForgeTier.STANDARD
        orch._enforced_phases = []

        orch._step7_enforce_constitution()

        phase_names_lower = [p.name.lower() for p in orch._enforced_phases]
        assert any("branch" in n for n in phase_names_lower)
        assert any("spec" in n for n in phase_names_lower)
        assert any("quality" in n for n in phase_names_lower)
        assert any("obsidian" in n for n in phase_names_lower)

    def test_constitution_phases_constant(self):
        assert "Create feature branch" in CONSTITUTION_PHASES
        assert "Write specification" in CONSTITUTION_PHASES
        assert "Quality Gate" in CONSTITUTION_PHASES
        assert "Persist to Obsidian" in CONSTITUTION_PHASES


# =============================================================================
# TestModelRouting
# =============================================================================


class TestModelRouting:
    def test_shallow_maps_to_haiku(self):
        assert _tier_to_model(ForgeTier.SHALLOW) == "haiku"

    def test_standard_maps_to_sonnet(self):
        assert _tier_to_model(ForgeTier.STANDARD) == "sonnet"

    def test_deep_maps_to_opus(self):
        assert _tier_to_model(ForgeTier.DEEP) == "opus"


# =============================================================================
# TestForgeStep Dataclass
# =============================================================================


class TestForgeStepDataclass:
    def test_forge_step_creation(self):
        step = ForgeStep(
            step_number=1,
            step_name="snapshot_context",
            description="Collect git context",
        )

        assert step.step_number == 1
        assert step.step_name == "snapshot_context"
        assert step.description == "Collect git context"


# =============================================================================
# TestOutputDataclasses
# =============================================================================


class TestForgeStatusOutput:
    def test_status_output_creation(self):
        output = ForgeStatusOutput(
            plan_id="forge-001",
            name="Test Plan",
            status=ForgeStatus.REVIEWING,
            tier=ForgeTier.STANDARD,
            score=55,
            confidence=0.75,
            n_phases=4,
            departments=["dev", "mkt"],
            created_at="2026-01-01T00:00:00Z",
            revision_count=1,
        )

        assert output.plan_id == "forge-001"
        assert output.status == ForgeStatus.REVIEWING


class TestForgeHistoryEntry:
    def test_history_entry_creation(self):
        entry = ForgeHistoryEntry(
            plan_id="forge-001",
            name="Test Plan",
            status=ForgeStatus.COMPLETED,
            tier=ForgeTier.DEEP,
            confidence=0.9,
            created_date="2026-01-01",
        )

        assert entry.plan_id == "forge-001"
        assert entry.confidence == 0.9


class TestForgeCompareOutput:
    def test_compare_output_creation(self):
        left_plan = _make_plan("left", "Left")
        right_plan = _make_plan("right", "Right")

        output = ForgeCompareOutput(
            left=ForgeStatusOutput(
                plan_id="left",
                name="Left",
                status=ForgeStatus.COMPLETED,
                tier=ForgeTier.STANDARD,
                score=50,
                confidence=0.7,
                n_phases=3,
                departments=["dev"],
                created_at="",
                revision_count=0,
            ),
            right=ForgeStatusOutput(
                plan_id="right",
                name="Right",
                status=ForgeStatus.COMPLETED,
                tier=ForgeTier.DEEP,
                score=75,
                confidence=0.85,
                n_phases=5,
                departments=["dev", "mkt"],
                created_at="",
                revision_count=2,
            ),
            left_phases=[PlanPhase(name="Phase 1", department="dev")],
            right_phases=[PlanPhase(name="Phase 1", department="dev")],
        )

        assert output.left.plan_id == "left"
        assert output.right.plan_id == "right"


# =============================================================================
# TestInternalHelpers
# =============================================================================


class TestGeneratePlanId:
    def test_id_format(self):
        orch = ForgeOrchestrator()
        orch._forge_context = _make_context("test prompt")

        plan_id = orch._generate_plan_id("test prompt")

        assert plan_id.startswith("forge-")
        assert len(plan_id) > len("forge-")

    def test_id_is_deterministic(self):
        orch = ForgeOrchestrator()
        orch._forge_context = _make_context("same prompt")

        id1 = orch._generate_plan_id("same prompt")
        id2 = orch._generate_plan_id("same prompt")

        assert id1 == id2


class TestEstimateAffectedFiles:
    def test_estimates_auth_files(self):
        orch = ForgeOrchestrator()
        files = orch._estimate_affected_files("add user authentication")

        assert "auth/" in files or "middleware/auth.py" in files

    def test_estimates_db_files(self):
        orch = ForgeOrchestrator()
        files = orch._estimate_affected_files("add db migration")

        assert "core/db/" in files or "models/" in files

    def test_returns_empty_for_unknown(self):
        orch = ForgeOrchestrator()
        files = orch._estimate_affected_files("random request")

        assert files == []


class TestEstimateDepartments:
    def test_estimates_dev(self):
        orch = ForgeOrchestrator()
        depts = orch._estimate_departments("implement feature")

        assert "dev" in depts

    def test_estimates_marketing(self):
        orch = ForgeOrchestrator()
        depts = orch._estimate_departments("marketing campaign")

        assert "mkt" in depts or "marketing" in depts

    def test_defaults_to_dev(self):
        orch = ForgeOrchestrator()
        depts = orch._estimate_departments("unknown")

        assert "dev" in depts


class TestFinalPhasesFromCritic:
    def test_builds_phases_from_critic_verdict(self):
        orch = ForgeOrchestrator()
        orch._critic_verdict = _make_critic_verdict(estimated_phases=3)
        orch._enforced_phases = [
            PlanPhase(name="Quality Gate", department="quality"),
        ]

        phases = orch._final_phases_from_critic()

        assert len(phases) == 4


# =============================================================================
# TestForgeDecision Enum
# =============================================================================


class TestForgeDecisionEnum:
    def test_approve_value(self):
        assert ForgeDecision.APPROVE == "approve"

    def test_revise_value(self):
        assert ForgeDecision.REVISE == "revise"

    def test_companion_value(self):
        assert ForgeDecision.COMPANION == "companion"

    def test_detail_value(self):
        assert ForgeDecision.DETAIL == "detail"

    def test_quit_value(self):
        assert ForgeDecision.QUIT == "quit"
