"""Conclave Profiler — Extract user behavioral DNA via structured questions.

Uses targeted questions to determine the user's DISC, Enneagram, Big Five,
and MBTI profiles. The profiler produces a UserProfile that the matcher
uses to assemble a personalized Conclave board.

Design: Each framework has 4-6 questions. Total profiling takes ~20 questions.
Questions are multiple-choice to make scoring deterministic.
"""

from dataclasses import dataclass, field
from core.agents.schema import (
    BehavioralDNA, DISCProfile, DISCType,
    EnneagramProfile, EnneagramType,
    BigFiveProfile, MBTIProfile, MBTIType,
)
from core.conclave.schema import UserProfile


@dataclass
class ProfileQuestion:
    """A single profiling question with scored options."""
    id: str
    framework: str           # disc, enneagram, big_five, mbti
    question: str
    options: list[dict]      # [{label, scores: {dimension: value}}]


@dataclass
class ProfilingSession:
    """Tracks answers during a profiling session."""
    answers: dict[str, str] = field(default_factory=dict)
    scores: dict[str, float] = field(default_factory=dict)


# --- DISC Questions (4 questions) ---

DISC_QUESTIONS = [
    ProfileQuestion(
        id="disc-1", framework="disc",
        question="When facing a new challenge at work, you tend to:",
        options=[
            {"label": "Take charge immediately and push for quick results", "scores": {"D": 3}},
            {"label": "Rally the team with enthusiasm and brainstorm together", "scores": {"I": 3}},
            {"label": "Carefully plan your approach before acting", "scores": {"C": 3}},
            {"label": "Consider how it affects the team and build consensus", "scores": {"S": 3}},
        ],
    ),
    ProfileQuestion(
        id="disc-2", framework="disc",
        question="In meetings, you are most likely to:",
        options=[
            {"label": "Drive the agenda and make decisions quickly", "scores": {"D": 3}},
            {"label": "Energize the room with ideas and stories", "scores": {"I": 3}},
            {"label": "Listen carefully and ensure everyone's input is heard", "scores": {"S": 3}},
            {"label": "Focus on data, details, and logical analysis", "scores": {"C": 3}},
        ],
    ),
    ProfileQuestion(
        id="disc-3", framework="disc",
        question="When someone disagrees with you, you typically:",
        options=[
            {"label": "State your position firmly and defend it with facts", "scores": {"D": 2, "C": 1}},
            {"label": "Use persuasion and charm to bring them around", "scores": {"I": 2, "D": 1}},
            {"label": "Seek compromise and try to maintain harmony", "scores": {"S": 2, "I": 1}},
            {"label": "Analyze both sides objectively before responding", "scores": {"C": 2, "S": 1}},
        ],
    ),
    ProfileQuestion(
        id="disc-4", framework="disc",
        question="Your biggest fear at work is:",
        options=[
            {"label": "Losing control or being taken advantage of", "scores": {"D": 3}},
            {"label": "Being rejected or losing social approval", "scores": {"I": 3}},
            {"label": "Sudden change or losing stability", "scores": {"S": 3}},
            {"label": "Being wrong or producing low-quality work", "scores": {"C": 3}},
        ],
    ),
]

# --- Enneagram Questions (6 questions — triads first, then type) ---

ENNEAGRAM_QUESTIONS = [
    ProfileQuestion(
        id="enn-1", framework="enneagram",
        question="Which statement resonates most with you?",
        options=[
            {"label": "I need to be competent and knowledgeable", "scores": {"e5": 3, "e6": 1}},
            {"label": "I need to be successful and admired", "scores": {"e3": 3, "e2": 1}},
            {"label": "I need to be in control and strong", "scores": {"e8": 3, "e1": 1}},
        ],
    ),
    ProfileQuestion(
        id="enn-2", framework="enneagram",
        question="Under stress, you tend to:",
        options=[
            {"label": "Withdraw and analyze the situation alone", "scores": {"e5": 3, "e4": 1}},
            {"label": "Become more busy and action-oriented", "scores": {"e3": 2, "e7": 2}},
            {"label": "Worry more and seek reassurance from trusted people", "scores": {"e6": 3}},
            {"label": "Become more controlling or confrontational", "scores": {"e8": 2, "e1": 2}},
        ],
    ),
    ProfileQuestion(
        id="enn-3", framework="enneagram",
        question="What drives your decisions most?",
        options=[
            {"label": "Doing what's right and maintaining high standards", "scores": {"e1": 3}},
            {"label": "Helping others and building relationships", "scores": {"e2": 3}},
            {"label": "Achieving goals and being the best", "scores": {"e3": 3}},
            {"label": "Understanding deeply and mastering my domain", "scores": {"e5": 3}},
        ],
    ),
    ProfileQuestion(
        id="enn-4", framework="enneagram",
        question="Which describes your inner world?",
        options=[
            {"label": "I seek freedom, variety, and new experiences", "scores": {"e7": 3}},
            {"label": "I seek authenticity and deep self-expression", "scores": {"e4": 3}},
            {"label": "I seek peace, harmony, and avoiding conflict", "scores": {"e9": 3}},
            {"label": "I seek security, loyalty, and preparedness", "scores": {"e6": 3}},
        ],
    ),
]

# --- Big Five Questions (5 questions, one per trait) ---

BIG_FIVE_QUESTIONS = [
    ProfileQuestion(
        id="bf-o", framework="big_five",
        question="When it comes to new ideas and experiences:",
        options=[
            {"label": "I actively seek novel approaches and creative solutions", "scores": {"openness": 85}},
            {"label": "I'm open to new things but prefer some familiarity", "scores": {"openness": 60}},
            {"label": "I prefer proven methods and practical approaches", "scores": {"openness": 35}},
        ],
    ),
    ProfileQuestion(
        id="bf-c", framework="big_five",
        question="How would you describe your work style?",
        options=[
            {"label": "Highly organized, disciplined, and detail-oriented", "scores": {"conscientiousness": 85}},
            {"label": "Reasonably organized with some flexibility", "scores": {"conscientiousness": 60}},
            {"label": "Spontaneous and adaptable, I figure things out as I go", "scores": {"conscientiousness": 35}},
        ],
    ),
    ProfileQuestion(
        id="bf-e", framework="big_five",
        question="In social situations:",
        options=[
            {"label": "I'm energized by people and love being the center of conversation", "scores": {"extraversion": 85}},
            {"label": "I enjoy socializing but also value alone time", "scores": {"extraversion": 55}},
            {"label": "I prefer small groups or working alone, large groups drain me", "scores": {"extraversion": 25}},
        ],
    ),
    ProfileQuestion(
        id="bf-a", framework="big_five",
        question="When making business decisions:",
        options=[
            {"label": "I prioritize people's feelings and building consensus", "scores": {"agreeableness": 80}},
            {"label": "I balance people's needs with practical outcomes", "scores": {"agreeableness": 55}},
            {"label": "I focus on results even if it means tough conversations", "scores": {"agreeableness": 30}},
        ],
    ),
    ProfileQuestion(
        id="bf-n", framework="big_five",
        question="How do you handle pressure and setbacks?",
        options=[
            {"label": "I stay calm and composed, rarely rattled", "scores": {"neuroticism": 20}},
            {"label": "I feel the pressure but manage it well", "scores": {"neuroticism": 45}},
            {"label": "I feel things intensely and it takes time to rebalance", "scores": {"neuroticism": 75}},
        ],
    ),
]

# --- MBTI Questions (4 questions, one per dichotomy) ---

MBTI_QUESTIONS = [
    ProfileQuestion(
        id="mbti-ei", framework="mbti",
        question="You recharge your energy by:",
        options=[
            {"label": "Spending time with others, discussing ideas and socializing", "scores": {"E": 3}},
            {"label": "Spending time alone, reflecting and processing internally", "scores": {"I": 3}},
        ],
    ),
    ProfileQuestion(
        id="mbti-sn", framework="mbti",
        question="You prefer to focus on:",
        options=[
            {"label": "Concrete facts, details, and what's real right now", "scores": {"S": 3}},
            {"label": "Patterns, possibilities, and what could be in the future", "scores": {"N": 3}},
        ],
    ),
    ProfileQuestion(
        id="mbti-tf", framework="mbti",
        question="When making important decisions, you rely more on:",
        options=[
            {"label": "Logic, analysis, and objective criteria", "scores": {"T": 3}},
            {"label": "Values, impact on people, and what feels right", "scores": {"F": 3}},
        ],
    ),
    ProfileQuestion(
        id="mbti-jp", framework="mbti",
        question="You prefer your work environment to be:",
        options=[
            {"label": "Structured, planned, and decisive — I like closure", "scores": {"J": 3}},
            {"label": "Flexible, open-ended, and adaptable — I like options", "scores": {"P": 3}},
        ],
    ),
]


def get_all_questions() -> list[ProfileQuestion]:
    """Get all profiling questions in order."""
    return DISC_QUESTIONS + ENNEAGRAM_QUESTIONS + BIG_FIVE_QUESTIONS + MBTI_QUESTIONS


def score_disc(session: ProfilingSession) -> tuple[DISCType, DISCType]:
    """Score DISC from session answers. Returns (primary, secondary)."""
    totals = {"D": 0, "I": 0, "S": 0, "C": 0}
    for key, val in session.scores.items():
        if key in totals:
            totals[key] += val
    ranked = sorted(totals.items(), key=lambda x: x[1], reverse=True)
    primary = DISCType(ranked[0][0])
    secondary = DISCType(ranked[1][0]) if ranked[1][0] != ranked[0][0] else DISCType(ranked[2][0])
    return primary, secondary


def score_enneagram(session: ProfilingSession) -> tuple[int, int]:
    """Score Enneagram from session. Returns (type, wing)."""
    totals = {i: 0 for i in range(1, 10)}
    for key, val in session.scores.items():
        if key.startswith("e") and key[1:].isdigit():
            totals[int(key[1:])] += val
    ranked = sorted(totals.items(), key=lambda x: x[1], reverse=True)
    enn_type = ranked[0][0]
    # Wing must be adjacent
    wing_a = enn_type - 1 if enn_type > 1 else 9
    wing_b = enn_type + 1 if enn_type < 9 else 1
    wing = wing_a if totals.get(wing_a, 0) >= totals.get(wing_b, 0) else wing_b
    return enn_type, wing


def score_big_five(session: ProfilingSession) -> BigFiveProfile:
    """Score Big Five from session."""
    return BigFiveProfile(
        openness=int(session.scores.get("openness", 50)),
        conscientiousness=int(session.scores.get("conscientiousness", 50)),
        extraversion=int(session.scores.get("extraversion", 50)),
        agreeableness=int(session.scores.get("agreeableness", 50)),
        neuroticism=int(session.scores.get("neuroticism", 50)),
    )


def score_mbti(session: ProfilingSession) -> MBTIType:
    """Score MBTI from session."""
    ei = "E" if session.scores.get("E", 0) >= session.scores.get("I", 0) else "I"
    sn = "S" if session.scores.get("S", 0) >= session.scores.get("N", 0) else "N"
    tf = "T" if session.scores.get("T", 0) >= session.scores.get("F", 0) else "F"
    jp = "J" if session.scores.get("J", 0) >= session.scores.get("P", 0) else "P"
    return MBTIType(f"{ei}{sn}{tf}{jp}")


def process_answer(session: ProfilingSession, question: ProfileQuestion, option_index: int) -> None:
    """Process a single answer and accumulate scores."""
    if 0 <= option_index < len(question.options):
        option = question.options[option_index]
        session.answers[question.id] = option["label"]
        for dimension, value in option.get("scores", {}).items():
            session.scores[dimension] = session.scores.get(dimension, 0) + value


def build_profile_from_session(
    session: ProfilingSession,
    name: str = "",
    company: str = "",
    role: str = "",
) -> UserProfile:
    """Build a complete UserProfile from a scoring session."""
    disc_primary, disc_secondary = score_disc(session)
    enn_type, enn_wing = score_enneagram(session)
    big_five = score_big_five(session)
    mbti_type = score_mbti(session)

    dna = BehavioralDNA(
        disc=DISCProfile(primary=disc_primary, secondary=disc_secondary),
        enneagram=EnneagramProfile(type=EnneagramType(enn_type), wing=enn_wing),
        big_five=big_five,
        mbti=MBTIProfile(type=mbti_type),
    )

    return UserProfile(
        name=name,
        company=company,
        role=role,
        behavioral_dna=dna,
    )
