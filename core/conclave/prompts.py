"""Conclave prompts — system prompts that make advisors respond in character."""

from core.conclave.schema import Advisor


def build_advisor_prompt(advisor: Advisor, question: str) -> str:
    """Build a system prompt that makes an AI respond as this advisor.

    The prompt channels the advisor's thinking style, mental models,
    and communication patterns.
    """
    models_text = "\n".join(
        f"- {m.name}: {m.question}" for m in advisor.mental_models
    )
    questions_text = "\n".join(f'- "{q}"' for q in advisor.key_questions)

    return f"""You are {advisor.name}, {advisor.title}.

Your mental models:
{models_text}

Your key questions:
{questions_text}

Communication style: {advisor.communication_style}
Decision framework: {advisor.decision_framework}

Respond to the following question as {advisor.name} would. Use your mental models.
Be specific to THIS situation, not generic. 3-5 sentences maximum.
Channel {advisor.name}'s actual thinking and vocabulary.

Question: {question}"""


def build_debate_prompt(advisors: list[Advisor], topic: str) -> str:
    """Build a prompt for an advisor debate on a topic."""
    advisor_list = "\n".join(
        f"- {a.name} ({a.title}): {a.communication_style}" for a in advisors
    )

    return f"""You are moderating a debate between these advisors:

{advisor_list}

Topic: {topic}

For EACH advisor, write 2-3 sentences from their perspective using their known
mental models and communication style. Then identify:
1. Where the aligned advisors agree
2. Where the contrarian advisors push back
3. The key tension the user should consider

Keep each advisor's voice distinct and authentic."""


def build_ask_all_prompt(advisors: list[Advisor], question: str) -> str:
    """Build a prompt that channels all advisors responding to one question."""
    sections = []

    for advisor in advisors:
        models = ", ".join(m.name for m in advisor.mental_models[:2])
        sections.append(
            f"**{advisor.name}** ({advisor.advisor_type.value}) — "
            f"Uses: {models}. Style: {advisor.communication_style}"
        )

    advisor_context = "\n".join(sections)

    return f"""The user asked their Conclave advisory board: "{question}"

Advisors on the board:
{advisor_context}

For each advisor, write a 2-3 sentence response that channels their specific
thinking style and mental models. Use their actual vocabulary and frameworks.
Make each response distinct. End with a brief synthesis of where they agree
and where they diverge."""
