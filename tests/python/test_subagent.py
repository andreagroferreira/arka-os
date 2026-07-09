"""Tests for the subagent handoff artifact."""

from core.runtime.subagent import HandoffArtifact


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
