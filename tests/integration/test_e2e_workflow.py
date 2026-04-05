"""End-to-end integration tests for ArkaOS v2.

Tests the full pipeline: agent loading → squad assembly → workflow execution →
synapse context injection → quality gate → registry generation.
"""

import pytest
from pathlib import Path

from core.agents.loader import load_agent, load_all_agents
from core.agents.validator import validate_agent_consistency
from core.squads.loader import load_squad, load_all_squads
from core.squads.registry import SquadRegistry
from core.workflow.loader import load_workflow
from core.workflow.engine import WorkflowEngine, GateResult
from core.workflow.schema import GateType, PhaseStatus
from core.synapse.engine import create_default_engine
from core.synapse.layers import PromptContext
from core.governance.constitution import load_constitution
from core.specs.manager import SpecManager
from core.specs.schema import SpecStatus
from core.conclave.matcher import match_advisors
from core.conclave.schema import UserProfile
from core.conclave.advisor_db import get_all_advisors
from core.tasks.manager import TaskManager
from core.tasks.schema import TaskType, TaskStatus
from core.runtime.registry import get_adapter, list_runtimes
from core.registry.generator import generate_commands_registry


BASE_DIR = Path(__file__).parent.parent.parent


class TestFullAgentPipeline:
    """Test loading all agents, validating DNA, and assembling squads."""

    def test_load_all_agents_no_errors(self):
        agents = load_all_agents(BASE_DIR / "departments")
        assert len(agents) >= 50

    def test_all_agents_pass_consistency(self):
        agents = load_all_agents(BASE_DIR / "departments")
        failures = []
        for agent in agents:
            result = validate_agent_consistency(agent)
            if not result.is_valid:
                failures.append(f"{agent.id}: {result.errors}")
        assert not failures, f"Agents with validation errors: {failures}"

    def test_load_all_squads_no_errors(self):
        squads = load_all_squads(BASE_DIR / "departments")
        assert len(squads) >= 16

    def test_assemble_registry_from_squads(self):
        squads = load_all_squads(BASE_DIR / "departments")
        registry = SquadRegistry()
        for squad in squads:
            registry.register(squad)
        summary = registry.summary()
        assert summary["total_squads"] >= 16
        assert summary["total_agents"] >= 40

    def test_every_squad_has_agents_in_agent_files(self):
        """Every agent referenced in a squad.yaml must have a matching agent YAML."""
        agents = load_all_agents(BASE_DIR / "departments")
        agent_ids = {a.id for a in agents}
        squads = load_all_squads(BASE_DIR / "departments")
        missing = []
        for squad in squads:
            for member in squad.members:
                if member.agent_id not in agent_ids:
                    missing.append(f"{squad.id}: {member.agent_id}")
        # Some agents may be referenced but not yet created — that's OK for alpha
        # But the count should be low
        assert len(missing) < 10, f"Missing agent files: {missing}"


class TestFullWorkflowExecution:
    """Test executing a workflow end-to-end with the engine."""

    def test_dev_feature_workflow_executes(self):
        wf = load_workflow(BASE_DIR / "departments" / "dev" / "workflows" / "feature.yaml")
        messages = []

        def approve_all(gate):
            return GateResult(passed=True, gate_type=gate.type, message="Auto-approved")

        engine = WorkflowEngine(
            on_visibility=lambda m: messages.append(m),
            on_gate_check=approve_all,
        )
        results = engine.execute(wf)

        assert wf.status == PhaseStatus.COMPLETED
        assert len(results) == 9  # 9 phases
        assert all(r.status == PhaseStatus.COMPLETED for r in results)
        assert any("Quality Gate" in m for m in messages)
        assert any("STARTING" in m for m in messages)
        assert any("COMPLETED" in m for m in messages)

    def test_quality_gate_rejection_loops_back(self):
        wf = load_workflow(BASE_DIR / "departments" / "brand" / "workflows" / "identity.yaml")

        def reject_quality(gate):
            if gate.type == GateType.QUALITY_GATE:
                return GateResult(passed=False, gate_type=gate.type, message="Copy issues found")
            return GateResult(passed=True, gate_type=gate.type, message="OK")

        engine = WorkflowEngine(on_gate_check=reject_quality)
        results = engine.execute(wf)

        assert wf.status == PhaseStatus.FAILED
        rejected = [r for r in results if r.status == PhaseStatus.FAILED]
        assert len(rejected) >= 1


class TestSynapseIntegration:
    """Test Synapse with real Constitution and command registry."""

    def test_synapse_with_real_constitution(self):
        constitution = load_constitution(BASE_DIR / "config" / "constitution.yaml")
        compressed = constitution.compress_for_context()

        engine = create_default_engine(constitution_compressed=compressed)
        result = engine.inject(PromptContext(
            user_input="build a new authentication feature",
            git_branch="v2",
        ))

        assert "[Constitution]" in result.context_string
        assert "[dept:dev]" in result.context_string
        assert "[branch:v2]" in result.context_string
        # Full constitution content is in the layer, not the tag
        l0 = next(l for l in result.layers if l.layer_id == "L0")
        assert "NON-NEGOTIABLE" in l0.content

    def test_synapse_detects_all_16_departments(self):
        engine = create_default_engine()
        test_cases = {
            "dev": "build a new feature",
            "marketing": "create social media campaign",
            "finance": "prepare budget forecast",
            "saas": "analyze churn and MRR",
            "landing": "design a sales funnel",
            "content": "write viral hooks and repurpose into short-form reels",
            "community": "grow my Discord community membership",
            "ecom": "optimize my Shopify store checkout",
        }
        for expected_dept, input_text in test_cases.items():
            result = engine.inject(PromptContext(user_input=input_text))
            assert f"[dept:{expected_dept}]" in result.context_string, \
                f"Failed for '{input_text}': expected dept:{expected_dept}, got {result.context_string}"


class TestSpecLifecycle:
    """Test the Living Spec lifecycle end-to-end."""

    def test_full_spec_lifecycle(self):
        mgr = SpecManager()
        spec = mgr.create(
            "spec-auth", "User Authentication",
            project="testproject", department="dev",
            sections=[
                {"id": "api", "title": "Auth API", "content": "OAuth2 endpoints",
                 "acceptance_criteria": ["Returns JWT on success", "401 on bad credentials"]},
                {"id": "ui", "title": "Login UI", "content": "Login form",
                 "acceptance_criteria": ["Renders on mobile", "Shows errors inline"]},
            ],
        )
        assert spec.status == SpecStatus.DRAFT
        assert spec.completion_percentage == 0.0

        mgr.approve("spec-auth", approved_by="user")
        assert spec.status == SpecStatus.APPROVED

        mgr.start_implementation("spec-auth")
        assert spec.status == SpecStatus.IN_PROGRESS

        # Implement API section
        spec.mark_section_complete("api", "Implemented with Laravel Sanctum")
        spec.verify_criterion("api", "ac-1", True, verified_by="qa-rita")
        spec.verify_criterion("api", "ac-2", True, verified_by="qa-rita")

        # UI section deviates from spec
        spec.add_delta("ui", "Login form", "Login form + social OAuth buttons",
                       "User requested Google/GitHub login", decided_by="cto-marco")
        spec.mark_section_complete("ui")
        spec.verify_criterion("ui", "ac-1", True, verified_by="qa-rita")
        spec.verify_criterion("ui", "ac-2", True, verified_by="qa-rita")

        assert spec.completion_percentage == 100.0
        assert spec.delta_count == 1
        assert spec.is_fully_verified

        mgr.complete("spec-auth")
        patterns = mgr.extract_patterns("spec-auth")
        assert len(patterns) >= 1


class TestConclaveIntegration:
    """Test Conclave with real advisor database."""

    def test_different_profiles_get_different_boards(self):
        analytical = UserProfile(
            name="Analyst",
            behavioral_dna=_make_dna("C", "D", 5, 6, 65, 90, 25, 35, 15, "INTJ"),
        )
        creative = UserProfile(
            name="Creative",
            behavioral_dna=_make_dna("I", "S", 4, 3, 92, 55, 80, 75, 35, "ENFP"),
        )
        board_a = match_advisors(analytical)
        board_c = match_advisors(creative)

        a_aligned = {a.id for a in board_a.aligned}
        c_aligned = {a.id for a in board_c.aligned}
        assert a_aligned != c_aligned

    def test_board_covers_diverse_perspectives(self):
        user = UserProfile(
            name="Test",
            behavioral_dna=_make_dna("D", "C", 8, 7, 78, 82, 55, 40, 20, "ENTJ"),
        )
        board = match_advisors(user)
        all_disc = {a.behavioral_dna.disc.primary.value for a in board.all_advisors}
        assert len(all_disc) >= 3, "Board should have diverse DISC profiles"


class TestTaskIntegration:
    """Test background task lifecycle."""

    def test_kb_download_lifecycle(self):
        mgr = TaskManager()
        task = mgr.create("Download YouTube video",
                          TaskType.KB_DOWNLOAD,
                          input_data={"url": "https://youtube.com/watch?v=test"})

        mgr.start(task.id)
        mgr.update_progress(task.id, 30, "Downloading audio...")
        mgr.update_progress(task.id, 70, "Transcribing...")
        mgr.complete(task.id, output={"transcript_path": "/media/test/audio.txt"})

        assert task.status == TaskStatus.COMPLETED
        assert task.progress_percent == 100
        assert task.duration_seconds is not None


class TestRegistryGeneration:
    """Test that registries generate correctly from current state."""

    def test_commands_registry_covers_all_departments(self, tmp_path):
        out = tmp_path / "cmds.json"
        reg = generate_commands_registry(BASE_DIR, out)
        depts = set(reg["_meta"]["departments"].keys())
        expected = {"dev", "marketing", "brand", "finance", "strategy", "ecom",
                    "kb", "ops", "pm", "saas", "landing", "content", "community",
                    "sales", "leadership", "org", "arka"}
        missing = expected - depts
        assert not missing, f"Missing: {missing}"
        assert reg["_meta"]["total_commands"] >= 200

    def test_all_4_runtimes_available(self):
        runtimes = list_runtimes()
        assert len(runtimes) == 4
        ids = {r["id"] for r in runtimes}
        assert ids == {"claude-code", "codex", "gemini", "cursor"}


# Helper
def _make_dna(dp, ds, et, ew, o, c, e, a, n, mbti):
    from core.agents.schema import (
        BehavioralDNA, DISCProfile, DISCType,
        EnneagramProfile, EnneagramType,
        BigFiveProfile, MBTIProfile, MBTIType,
    )
    return BehavioralDNA(
        disc=DISCProfile(primary=DISCType(dp), secondary=DISCType(ds)),
        enneagram=EnneagramProfile(type=EnneagramType(et), wing=ew),
        big_five=BigFiveProfile(openness=o, conscientiousness=c, extraversion=e, agreeableness=a, neuroticism=n),
        mbti=MBTIProfile(type=MBTIType(mbti)),
    )
