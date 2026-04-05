"""Conclave display — format boards and profiles for output."""

from core.conclave.schema import UserProfile, Advisor, ConclaveBoard


def format_dna_summary(user: UserProfile) -> str:
    """Format the user's behavioral DNA as a markdown table."""
    dna = user.behavioral_dna
    disc = f"{dna.disc.primary.value}+{dna.disc.secondary.value} ({dna.disc.label})"
    enn = dna.enneagram.label
    bf = (f"O:{dna.big_five.openness} C:{dna.big_five.conscientiousness} "
          f"E:{dna.big_five.extraversion} A:{dna.big_five.agreeableness} "
          f"N:{dna.big_five.neuroticism}")
    mbti = dna.mbti.type.value

    return (
        "## Your Behavioral DNA\n\n"
        "| Framework | Result |\n"
        "|-----------|--------|\n"
        f"| DISC | {disc} |\n"
        f"| Enneagram | {enn} |\n"
        f"| Big Five | {bf} |\n"
        f"| MBTI | {mbti} |\n"
    )


def format_advisor_card(advisor: Advisor, rank: int) -> str:
    """Format a single advisor as a card."""
    disc = f"{advisor.behavioral_dna.disc.primary.value}+{advisor.behavioral_dna.disc.secondary.value}"
    enn = advisor.behavioral_dna.enneagram.label
    mbti = advisor.behavioral_dna.mbti.type.value

    models = ", ".join(m.name for m in advisor.mental_models[:3])
    questions = advisor.key_questions[0] if advisor.key_questions else ""

    lines = [
        f"**{rank}. {advisor.name}** — {advisor.title}",
        f"   {advisor.why_selected}",
        f"   DNA: {disc}, {enn}, {mbti}",
        f"   Models: {models}",
    ]
    if questions:
        lines.append(f'   "{questions}"')
    return "\n".join(lines)


def format_board(board: ConclaveBoard) -> str:
    """Format the complete Conclave board as markdown."""
    parts = [format_dna_summary(board.user)]

    parts.append("\n## Your Advisory Board\n")

    parts.append("### ALIGNED — Think Like You\n")
    for i, advisor in enumerate(board.aligned, 1):
        parts.append(format_advisor_card(advisor, i))
        parts.append("")

    parts.append("\n### CONTRARIAN — Challenge Your Blind Spots\n")
    for i, advisor in enumerate(board.contrarian, 1):
        parts.append(format_advisor_card(advisor, i))
        parts.append("")

    return "\n".join(parts)


def format_advisor_detail(advisor: Advisor) -> str:
    """Format a deep dive on a single advisor."""
    dna = advisor.behavioral_dna
    disc = f"{dna.disc.primary.value}+{dna.disc.secondary.value} ({dna.disc.label})"

    lines = [
        f"# {advisor.name} — {advisor.title}\n",
        f"**Type:** {advisor.advisor_type.value}",
        f"**Match reason:** {advisor.why_selected}\n",
        "## Behavioral DNA\n",
        f"- DISC: {disc}",
        f"- Enneagram: {dna.enneagram.label}",
        f"- MBTI: {dna.mbti.type.value}",
        f"- Big Five: O:{dna.big_five.openness} C:{dna.big_five.conscientiousness} "
        f"E:{dna.big_five.extraversion} A:{dna.big_five.agreeableness} N:{dna.big_five.neuroticism}\n",
        "## Mental Models\n",
    ]

    for m in advisor.mental_models:
        lines.append(f"**{m.name}**")
        if m.question:
            lines.append(f"  Question: {m.question}")
        lines.append("")

    if advisor.key_questions:
        lines.append("## Key Questions\n")
        for q in advisor.key_questions:
            lines.append(f'- "{q}"')
        lines.append("")

    lines.append(f"**Communication style:** {advisor.communication_style}")
    lines.append(f"**Decision framework:** {advisor.decision_framework}\n")

    if advisor.sources:
        lines.append("## Sources\n")
        for s in advisor.sources:
            lines.append(f"- {s}")

    return "\n".join(lines)
