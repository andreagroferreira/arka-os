"""Tests for the Subagent Pattern."""

import pytest

from core.agents.schema import (
    Agent, BehavioralDNA, DISCProfile, DISCType,
    EnneagramProfile, EnneagramType, BigFiveProfile,
    MBTIProfile, MBTIType, Authority,
)
from core.runtime.subagent import (
    SubagentDispatcher, HandoffArtifact, SubagentResult, SubagentStatus,
)


def make_test_agent(id: str = "cto-marco", tier: int = 0) -> Agent:
    return Agent(
        id=id, name="Marco", role="CTO", department="dev", tier=tier,
        behavioral_dna=BehavioralDNA(
            disc=DISCProfile(primary=DISCType.D, secondary=DISCType.C),
            enneagram=EnneagramProfile(type=EnneagramType.INVESTIGATOR, wing=6),
            big_five=BigFiveProfile(openness=78, conscientiousness=85, extraversion=35, agreeableness=40, neuroticism=25),
            mbti=MBTIProfile(type=MBTIType.INTJ),
        ),
    )


class TestHandoffArtifact:
    def test_create_handoff(self):
        artifact = HandoffArtifact(
            task_id="task-1",
            task_description="Review architecture for auth module",
            agent_id="cto-marco",
            agent_role="CTO",
            agent_disc="Driver-Analyst",
            department="dev",
        )
        assert artifact.task_id == "task-1"
        assert artifact.agent_id == "cto-marco"

    def test_to_prompt_contains_key_info(self):
        artifact = HandoffArtifact(
            task_id="task-1",
            task_description="Design auth system",
            agent_id="architect-gabriel",
            agent_role="Software Architect",
            agent_disc="Analyst-Driver",
            department="dev",
            relevant_files=["src/auth/", "docs/spec.md"],
            context_summary="User wants OAuth2 + JWT",
            constraints=["Must use existing User model", "No breaking changes"],
            expected_output="ADR document in markdown",
            quality_criteria=["SOLID compliant", "No over-engineering"],
        )
        prompt = artifact.to_prompt()
        assert "Design auth system" in prompt
        assert "architect-gabriel" in prompt
        assert "src/auth/" in prompt
        assert "OAuth2" in prompt
        assert "Must use existing User model" in prompt
        assert "ADR document" in prompt
        assert "SOLID" in prompt

    def test_estimated_tokens_under_500(self):
        artifact = HandoffArtifact(
            task_id="task-1",
            task_description="Simple task",
            agent_id="dev-1",
            agent_role="Developer",
            agent_disc="D+C",
            department="dev",
            context_summary="Brief context",
            expected_output="Code",
        )
        assert artifact.estimated_tokens < 500

    def test_empty_optional_fields(self):
        artifact = HandoffArtifact(
            task_id="task-1",
            task_description="Task",
            agent_id="dev-1",
            agent_role="Dev",
            agent_disc="D+C",
            department="dev",
        )
        prompt = artifact.to_prompt()
        assert "Context" not in prompt  # No context_summary
        assert "Relevant Files" not in prompt  # No files


class TestSubagentResult:
    def test_create_result(self):
        result = SubagentResult(
            task_id="task-1",
            agent_id="cto-marco",
            status=SubagentStatus.COMPLETED,
            output="Architecture approved. ADR written.",
        )
        assert result.status == SubagentStatus.COMPLETED

    def test_summary_truncation(self):
        long_output = " ".join(["word"] * 500)
        result = SubagentResult(
            task_id="task-1",
            agent_id="dev-1",
            status=SubagentStatus.COMPLETED,
            output=long_output,
        )
        summary = result.to_summary(max_tokens=100)
        assert len(summary.split()) <= 101  # 100 words + "..."
        assert summary.endswith("...")

    def test_short_output_not_truncated(self):
        result = SubagentResult(
            task_id="task-1",
            agent_id="dev-1",
            status=SubagentStatus.COMPLETED,
            output="Done",
        )
        assert result.to_summary() == "Done"


class TestSubagentDispatcher:
    def test_create_handoff_from_agent(self):
        dispatcher = SubagentDispatcher()
        agent = make_test_agent()
        artifact = dispatcher.create_handoff(
            agent=agent,
            task_description="Review code for auth module",
            relevant_files=["src/auth.py"],
        )
        assert artifact.agent_id == "cto-marco"
        assert artifact.agent_disc == "Driver-Analyst"
        assert artifact.department == "dev"
        assert "src/auth.py" in artifact.relevant_files
        assert len(artifact.quality_criteria) >= 2

    def test_task_ids_increment(self):
        dispatcher = SubagentDispatcher()
        agent = make_test_agent()
        a1 = dispatcher.create_handoff(agent, "Task 1")
        a2 = dispatcher.create_handoff(agent, "Task 2")
        assert a1.task_id != a2.task_id

    def test_pending_count(self):
        dispatcher = SubagentDispatcher()
        agent = make_test_agent()
        dispatcher.create_handoff(agent, "Task 1")
        dispatcher.create_handoff(agent, "Task 2")
        assert dispatcher.pending_count == 2

    def test_record_result_clears_pending(self):
        dispatcher = SubagentDispatcher()
        agent = make_test_agent()
        artifact = dispatcher.create_handoff(agent, "Task 1")

        result = SubagentResult(
            task_id=artifact.task_id,
            agent_id=agent.id,
            status=SubagentStatus.COMPLETED,
            output="Done",
        )
        dispatcher.record_result(result)

        assert dispatcher.pending_count == 0
        assert dispatcher.completed_count == 1

    def test_get_result(self):
        dispatcher = SubagentDispatcher()
        agent = make_test_agent()
        artifact = dispatcher.create_handoff(agent, "Task 1")

        result = SubagentResult(
            task_id=artifact.task_id,
            agent_id=agent.id,
            status=SubagentStatus.COMPLETED,
            output="All tests pass",
        )
        dispatcher.record_result(result)

        retrieved = dispatcher.get_result(artifact.task_id)
        assert retrieved is not None
        assert retrieved.output == "All tests pass"

    def test_orchestrator_context_usage(self):
        dispatcher = SubagentDispatcher()
        agent = make_test_agent()
        dispatcher.create_handoff(agent, "Task 1", context_summary="Brief context")

        usage = dispatcher.orchestrator_context_usage()
        assert usage["dispatch_tokens"] > 0
        assert usage["tasks_dispatched"] == 1
        # Orchestrator should use minimal context
        assert usage["total_orchestrator_tokens"] < 500

    def test_multiple_subagents_parallel(self):
        """Simulate dispatching multiple subagents for parallel execution."""
        dispatcher = SubagentDispatcher()
        backend = make_test_agent("backend-andre", tier=2)
        frontend = make_test_agent("frontend-diana", tier=2)

        a1 = dispatcher.create_handoff(backend, "Implement auth API", relevant_files=["src/api/"])
        a2 = dispatcher.create_handoff(frontend, "Build login form", relevant_files=["src/components/"])

        assert dispatcher.pending_count == 2

        # Both complete
        dispatcher.record_result(SubagentResult(
            task_id=a1.task_id, agent_id=backend.id,
            status=SubagentStatus.COMPLETED, output="API implemented",
        ))
        dispatcher.record_result(SubagentResult(
            task_id=a2.task_id, agent_id=frontend.id,
            status=SubagentStatus.COMPLETED, output="Login form built",
        ))

        assert dispatcher.pending_count == 0
        assert dispatcher.completed_count == 2
        results = dispatcher.get_all_results()
        assert all(r.status == SubagentStatus.COMPLETED for r in results)

    def test_tier0_has_enterprise_quality_criteria(self):
        dispatcher = SubagentDispatcher()
        agent = make_test_agent(tier=0)
        artifact = dispatcher.create_handoff(agent, "Review architecture")
        assert any("Enterprise" in q for q in artifact.quality_criteria)

    def test_tier2_no_enterprise_criteria(self):
        dispatcher = SubagentDispatcher()
        agent = make_test_agent(tier=2)
        artifact = dispatcher.create_handoff(agent, "Write tests")
        assert not any("Enterprise" in q for q in artifact.quality_criteria)
