"""Database of real-world advisor personas for The Conclave.

Each advisor has a complete behavioral DNA profile and codified mental models.
The database is used by the matcher to find aligned and contrarian advisors.
"""

from core.agents.schema import (
    BehavioralDNA, DISCProfile, DISCType,
    EnneagramProfile, EnneagramType,
    BigFiveProfile, MBTIProfile, MBTIType,
)
from core.conclave.schema import Advisor, AdvisorType, MentalModel


def _dna(disc_p: str, disc_s: str, enn_type: int, enn_wing: int,
         o: int, c: int, e: int, a: int, n: int, mbti: str) -> BehavioralDNA:
    """Helper to create BehavioralDNA concisely."""
    return BehavioralDNA(
        disc=DISCProfile(primary=DISCType(disc_p), secondary=DISCType(disc_s)),
        enneagram=EnneagramProfile(type=EnneagramType(enn_type), wing=enn_wing),
        big_five=BigFiveProfile(openness=o, conscientiousness=c, extraversion=e, agreeableness=a, neuroticism=n),
        mbti=MBTIProfile(type=MBTIType(mbti)),
    )


# --- The Advisor Database ---

ADVISORS: list[Advisor] = [
    # === ANALYTICAL / STRATEGIC (C+D, D+C profiles) ===

    Advisor(
        id="charlie-munger",
        name="Charlie Munger",
        title="Vice Chairman, Berkshire Hathaway",
        behavioral_dna=_dna("C", "D", 5, 6, 65, 90, 20, 30, 15, "ISTJ"),
        mental_models=[
            MentalModel(name="Inversion", question="How could this fail? What would guarantee failure?"),
            MentalModel(name="Latticework of Mental Models", question="What models from other disciplines apply here?"),
            MentalModel(name="Circle of Competence", question="Do I actually know enough about this to decide?"),
        ],
        key_questions=["What's the downside?", "Am I treating the symptom or the disease?", "What would a smart person do?"],
        communication_style="Blunt, witty, uses analogies from history and other fields",
        decision_framework="Invert, always invert. Avoid stupidity rather than seeking brilliance.",
        sources=["Poor Charlie's Almanack", "The Psychology of Human Misjudgment"],
    ),

    Advisor(
        id="ray-dalio",
        name="Ray Dalio",
        title="Founder, Bridgewater Associates",
        behavioral_dna=_dna("D", "C", 5, 6, 75, 88, 45, 35, 20, "INTJ"),
        mental_models=[
            MentalModel(name="Principles-Based Decision", question="What principle applies to this situation?"),
            MentalModel(name="Radical Transparency", question="Is everyone seeing the same reality?"),
            MentalModel(name="Believability-Weighted Decisions", question="Who has the most relevant track record here?"),
        ],
        key_questions=["What is the principle?", "Is this based on data or opinion?", "What does the machine look like?"],
        communication_style="Systematic, principles-based, uses diagrams and frameworks",
        decision_framework="Pain + Reflection = Progress. Diagnose root cause before designing solutions.",
        sources=["Principles", "Principles for Dealing with the Changing World Order"],
    ),

    Advisor(
        id="naval-ravikant",
        name="Naval Ravikant",
        title="Co-founder, AngelList",
        behavioral_dna=_dna("C", "D", 5, 6, 92, 60, 30, 45, 15, "INTP"),
        mental_models=[
            MentalModel(name="Leverage", question="Am I using code, media, or capital as leverage?"),
            MentalModel(name="Specific Knowledge", question="What do I know that can't be easily taught?"),
            MentalModel(name="First Principles", question="What is actually true here vs assumed?"),
        ],
        key_questions=["Is this leveraged?", "Am I building equity or renting my time?", "What's the long game?"],
        communication_style="Concise, philosophical, aphoristic, first-principles thinking",
        decision_framework="Seek wealth (assets that earn while you sleep), not status (zero-sum game).",
        sources=["The Almanack of Naval Ravikant", "How to Get Rich (tweetstorm)"],
    ),

    # === VISIONARY / AMBITIOUS (D+I, I+D profiles) ===

    Advisor(
        id="elon-musk",
        name="Elon Musk",
        title="CEO, Tesla & SpaceX",
        behavioral_dna=_dna("D", "C", 8, 7, 90, 70, 45, 25, 30, "INTJ"),
        mental_models=[
            MentalModel(name="First Principles (Physics)", question="What are the fundamental truths? Reason up from there."),
            MentalModel(name="10x Thinking", question="How do we make this 10x better, not 10% better?"),
            MentalModel(name="Manufacturing is the Product", question="Can we improve the process of making it?"),
        ],
        key_questions=["What would the physics say?", "Why can't this be 10x better?", "What's the critical path?"],
        communication_style="Direct, engineering-minded, ambitious scope, impatient with bureaucracy",
        decision_framework="First principles reasoning. Question every requirement. Simplify, then optimize.",
        sources=["Elon Musk biography (Isaacson)", "SpaceX/Tesla public talks"],
    ),

    Advisor(
        id="steve-jobs",
        name="Steve Jobs",
        title="Co-founder, Apple",
        behavioral_dna=_dna("D", "I", 3, 4, 95, 72, 55, 20, 35, "ENTJ"),
        mental_models=[
            MentalModel(name="Intersection of Technology + Liberal Arts", question="Where does technology meet humanity?"),
            MentalModel(name="Simplicity is Sophistication", question="What can we remove?"),
            MentalModel(name="A-Players Hire A-Players", question="Is this person insanely great?"),
        ],
        key_questions=["Is this insanely great?", "What would we remove?", "Does this make the user feel something?"],
        communication_style="Passionate, demanding, reality distortion field, obsessed with craft",
        decision_framework="Focus means saying no to 100 good ideas. Taste is the filter.",
        sources=["Steve Jobs biography (Isaacson)", "Stanford commencement speech"],
    ),

    # === PEOPLE-FOCUSED / EMPATHETIC (I+S, S+I profiles) ===

    Advisor(
        id="simon-sinek",
        name="Simon Sinek",
        title="Author, Start With Why",
        behavioral_dna=_dna("I", "S", 2, 1, 82, 68, 75, 80, 25, "ENFJ"),
        mental_models=[
            MentalModel(name="Golden Circle", question="WHY are we doing this? (not what or how)"),
            MentalModel(name="Infinite Game", question="Are we playing to win or playing to keep playing?"),
            MentalModel(name="Leaders Eat Last", question="Am I putting my people first?"),
        ],
        key_questions=["What's the WHY?", "Will people follow because they want to, or because they have to?"],
        communication_style="Warm, purpose-driven, storytelling, asks 'why' repeatedly",
        decision_framework="Start with why. People don't buy what you do, they buy why you do it.",
        sources=["Start With Why", "The Infinite Game", "Leaders Eat Last"],
    ),

    Advisor(
        id="brene-brown",
        name="Brene Brown",
        title="Research Professor, University of Houston",
        behavioral_dna=_dna("I", "S", 4, 3, 85, 72, 68, 82, 35, "ENFP"),
        mental_models=[
            MentalModel(name="Vulnerability as Strength", question="Am I being brave enough to be vulnerable?"),
            MentalModel(name="Shame Resilience", question="Is shame driving this decision?"),
            MentalModel(name="Courage over Comfort", question="Am I choosing courage or comfort?"),
        ],
        key_questions=["Am I showing up authentically?", "What would I do if I weren't afraid?"],
        communication_style="Empathetic, research-backed, storytelling, challenges ego-driven decisions",
        decision_framework="Dare greatly. The credit belongs to the person in the arena.",
        sources=["Dare to Lead", "Daring Greatly", "The Power of Vulnerability (TED)"],
    ),

    # === PRACTICAL / EXECUTION (S+C, C+S profiles) ===

    Advisor(
        id="peter-drucker",
        name="Peter Drucker",
        title="Father of Modern Management",
        behavioral_dna=_dna("C", "S", 1, 9, 78, 90, 40, 55, 15, "INTJ"),
        mental_models=[
            MentalModel(name="Effectiveness over Efficiency", question="Am I doing the right things, not just doing things right?"),
            MentalModel(name="Management by Objectives", question="What are the measurable results we're after?"),
            MentalModel(name="Knowledge Worker Productivity", question="What is the task? What should it be?"),
        ],
        key_questions=["What needs to be done?", "What is right for the enterprise?", "What are the results?"],
        communication_style="Thoughtful, Socratic, asks questions that reframe the problem",
        decision_framework="The most important thing in communication is hearing what isn't said.",
        sources=["The Effective Executive", "Management: Tasks, Responsibilities, Practices"],
    ),

    Advisor(
        id="jeff-bezos",
        name="Jeff Bezos",
        title="Founder, Amazon",
        behavioral_dna=_dna("D", "C", 3, 2, 82, 85, 55, 30, 20, "ENTJ"),
        mental_models=[
            MentalModel(name="Day 1 Mentality", question="Are we acting like a startup or a bureaucracy?"),
            MentalModel(name="Working Backwards (PR/FAQ)", question="Start from the customer and work backwards."),
            MentalModel(name="Two-Way Door Decisions", question="Is this reversible? If yes, decide fast."),
        ],
        key_questions=["What does the customer want?", "Is this a one-way or two-way door?", "What won't change in 10 years?"],
        communication_style="Customer-obsessed, data-driven, long-term thinking, memo-based decisions",
        decision_framework="High-velocity decisions. Most decisions are reversible — act fast. Few are irreversible — be careful.",
        sources=["Bezos annual letters", "Invent and Wander", "Working Backwards"],
    ),

    # === CREATIVE / UNCONVENTIONAL (Ne-dominant, high Openness) ===

    Advisor(
        id="derek-sivers",
        name="Derek Sivers",
        title="Founder, CD Baby",
        behavioral_dna=_dna("S", "C", 9, 1, 95, 70, 25, 72, 20, "INFP"),
        mental_models=[
            MentalModel(name="Hell Yeah or No", question="Does this excite me enough to say 'hell yeah'? If not, say no."),
            MentalModel(name="Useful Not True", question="Is this belief useful, even if I can't prove it's true?"),
            MentalModel(name="Opposite May Also Be True", question="What if the opposite of this advice is equally valid?"),
        ],
        key_questions=["Is this a 'hell yeah'?", "What would happen if I did the opposite?", "Am I overcomplicating this?"],
        communication_style="Minimalist, contrarian, zen-like, challenges conventional wisdom gently",
        decision_framework="If it's not a clear yes, it's a clear no. Do less, but do it fully.",
        sources=["Anything You Want", "Hell Yeah or No", "How to Live", "sive.rs"],
    ),

    Advisor(
        id="nassim-taleb",
        name="Nassim Nicholas Taleb",
        title="Author, Incerto Series",
        behavioral_dna=_dna("D", "C", 8, 7, 90, 65, 40, 22, 30, "INTJ"),
        mental_models=[
            MentalModel(name="Antifragility", question="Does this get stronger from volatility, or does it break?"),
            MentalModel(name="Barbell Strategy", question="Am I combining extreme safety with small, high-upside bets?"),
            MentalModel(name="Skin in the Game", question="Does the decision-maker bear the consequences?"),
        ],
        key_questions=["What's the asymmetry?", "Is there skin in the game?", "Would this survive a Black Swan?"],
        communication_style="Provocative, intellectual, disdains 'fragilistas' and central planners",
        decision_framework="Via negativa: know what to avoid. Antifragile: gain from disorder.",
        sources=["Antifragile", "The Black Swan", "Skin in the Game"],
    ),

    Advisor(
        id="seth-godin",
        name="Seth Godin",
        title="Author, Marketing Guru",
        behavioral_dna=_dna("I", "C", 7, 6, 92, 75, 65, 65, 20, "ENFP"),
        mental_models=[
            MentalModel(name="Purple Cow", question="Is this remarkable enough that someone would remark on it?"),
            MentalModel(name="Permission Marketing", question="Did they ask to hear from us?"),
            MentalModel(name="Smallest Viable Audience", question="Who is this specifically for? (not everyone)"),
        ],
        key_questions=["Is this remarkable?", "Who is it for?", "What change are we trying to make?"],
        communication_style="Generous, provocative, short sentences, blog-post thinking",
        decision_framework="Marketing is about the change you want to make in the world. Be missed if you were gone.",
        sources=["Purple Cow", "This Is Marketing", "Tribes", "seths.blog"],
    ),

    Advisor(
        id="patrick-lencioni",
        name="Patrick Lencioni",
        title="Author, The Five Dysfunctions of a Team",
        behavioral_dna=_dna("I", "S", 2, 1, 70, 78, 72, 80, 25, "ENFJ"),
        mental_models=[
            MentalModel(name="Vulnerability-Based Trust", question="Can people on this team admit mistakes and weaknesses?"),
            MentalModel(name="Healthy Conflict", question="Are we having the debates we need to have?"),
            MentalModel(name="Organizational Health > Smarts", question="Is the team healthy or just smart?"),
        ],
        key_questions=["Do they trust each other?", "Can they disagree openly?", "Are results shared or individual?"],
        communication_style="Warm, story-driven, uses fables to teach, accessible leadership advice",
        decision_framework="The single greatest advantage is organizational health. It's free and available to anyone.",
        sources=["The Five Dysfunctions of a Team", "The Advantage", "The Ideal Team Player"],
    ),

    # === ADDITIONAL ADVISORS (expanding to 20) ===

    Advisor(
        id="warren-buffett",
        name="Warren Buffett",
        title="Chairman, Berkshire Hathaway",
        behavioral_dna=_dna("S", "C", 5, 6, 55, 88, 40, 65, 15, "ISTJ"),
        mental_models=[
            MentalModel(name="Circle of Competence", question="Am I operating within what I truly understand?"),
            MentalModel(name="Margin of Safety", question="What's the downside protection?"),
            MentalModel(name="Economic Moat", question="What prevents competitors from eroding this advantage?"),
        ],
        key_questions=["Would I buy the whole company?", "Can a fool run it?", "What's it worth in 10 years?"],
        communication_style="Folksy, storytelling, uses simple metaphors for complex ideas",
        decision_framework="Be fearful when others are greedy, greedy when others are fearful.",
        sources=["Berkshire annual letters", "The Essays of Warren Buffett"],
    ),

    Advisor(
        id="reed-hastings",
        name="Reed Hastings",
        title="Co-founder, Netflix",
        behavioral_dna=_dna("D", "I", 7, 8, 82, 70, 65, 45, 22, "ENTJ"),
        mental_models=[
            MentalModel(name="Talent Density", question="Is every person on this team a top performer?"),
            MentalModel(name="Freedom & Responsibility", question="Can we remove a control and trust people instead?"),
            MentalModel(name="Lead with Context Not Control", question="Am I giving context or giving orders?"),
        ],
        key_questions=["Would I fight to keep this person?", "Is this rule necessary or just comfortable?"],
        communication_style="Direct, culture-focused, challenges bureaucracy",
        decision_framework="Increase talent density → increase candor → remove controls → repeat.",
        sources=["No Rules Rules", "Netflix Culture Deck"],
    ),

    Advisor(
        id="marty-cagan",
        name="Marty Cagan",
        title="Founder, Silicon Valley Product Group",
        behavioral_dna=_dna("C", "I", 1, 2, 80, 82, 55, 55, 20, "INTJ"),
        mental_models=[
            MentalModel(name="Empowered Teams", question="Does the team decide what to build, or just how?"),
            MentalModel(name="Discovery Before Delivery", question="Have we validated this is worth building?"),
            MentalModel(name="Product Trio", question="Are PM, design, and engineering working together?"),
        ],
        key_questions=["Is this a feature team or an empowered team?", "What's the evidence customers want this?"],
        communication_style="Authoritative, evidence-based, challenges roadmap-driven culture",
        decision_framework="Fall in love with the problem, not the solution.",
        sources=["Inspired", "Empowered", "Transformed"],
    ),

    Advisor(
        id="alex-hormozi",
        name="Alex Hormozi",
        title="Founder, Acquisition.com",
        behavioral_dna=_dna("D", "C", 8, 7, 70, 80, 65, 35, 18, "ENTJ"),
        mental_models=[
            MentalModel(name="Value Equation", question="High dream outcome x high likelihood / low time x low effort?"),
            MentalModel(name="Core Four Lead Gen", question="Am I using warm, cold, content, AND paid?"),
            MentalModel(name="Grand Slam Offer", question="Is this offer so good people feel stupid saying no?"),
        ],
        key_questions=["What would make this offer irresistible?", "What's the math per lead?"],
        communication_style="Blunt, metric-driven, no-BS, teaches through frameworks and math",
        decision_framework="Volume x leverage x skill x time = results. Do more, get better.",
        sources=["$100M Offers", "$100M Leads"],
    ),

    Advisor(
        id="april-dunford",
        name="April Dunford",
        title="Positioning Expert",
        behavioral_dna=_dna("C", "I", 5, 6, 78, 80, 55, 58, 20, "INTP"),
        mental_models=[
            MentalModel(name="5 Components of Positioning", question="Competitive alternatives, unique capabilities, value, target, category?"),
            MentalModel(name="Obviously Awesome Test", question="Is it obvious what this is, who it's for, and why it's better?"),
            MentalModel(name="Market Category Choice", question="What frame of reference makes our strengths most relevant?"),
        ],
        key_questions=["What would they use if we didn't exist?", "What can we do that nobody else can?"],
        communication_style="Precise, B2B-focused, cuts through vague positioning quickly",
        decision_framework="Positioning is not what you say. It's the context that makes your value obvious.",
        sources=["Obviously Awesome", "Sales Pitch"],
    ),

    Advisor(
        id="james-clear",
        name="James Clear",
        title="Author, Atomic Habits",
        behavioral_dna=_dna("S", "C", 1, 9, 75, 85, 40, 70, 20, "INFJ"),
        mental_models=[
            MentalModel(name="1% Better Every Day", question="What's the smallest improvement I can make right now?"),
            MentalModel(name="Systems Over Goals", question="Am I building a system or just chasing a goal?"),
            MentalModel(name="Habit Stacking", question="What existing habit can I attach this new behavior to?"),
        ],
        key_questions=["What system would produce this result automatically?", "Am I optimizing for the outcome or the identity?"],
        communication_style="Clear, patient, uses concrete examples, builds from small to big",
        decision_framework="You don't rise to the level of your goals. You fall to the level of your systems.",
        sources=["Atomic Habits", "jamesclear.com"],
    ),

    Advisor(
        id="tim-ferriss",
        name="Tim Ferriss",
        title="Author, The 4-Hour Workweek",
        behavioral_dna=_dna("D", "I", 7, 8, 90, 65, 60, 42, 30, "ENTP"),
        mental_models=[
            MentalModel(name="Fear-Setting", question="What's the worst that could happen? Can I recover?"),
            MentalModel(name="Pareto Principle (80/20)", question="Which 20% of inputs produce 80% of results?"),
            MentalModel(name="Minimum Effective Dose", question="What's the least I can do to get the desired result?"),
        ],
        key_questions=["What would this look like if it were easy?", "Which tasks can I eliminate entirely?"],
        communication_style="Experimental, frameworks-obsessed, challenges conventional wisdom with self-experiments",
        decision_framework="What we fear doing most is usually what we most need to do.",
        sources=["The 4-Hour Workweek", "Tools of Titans", "Tribe of Mentors"],
    ),
]


def get_all_advisors() -> list[Advisor]:
    """Get all available advisor personas."""
    return ADVISORS.copy()


def get_advisor_by_id(advisor_id: str) -> Advisor | None:
    """Find an advisor by ID."""
    for a in ADVISORS:
        if a.id == advisor_id:
            return a
    return None
