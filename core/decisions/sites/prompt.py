"""The four UserPromptSubmit sites (#1-#4 of the JEV campaign).

* ``topic-drift`` — is the new prompt a different task? (read)
* ``refine`` — is the request too vague to build from? (read)
* ``creation-intent`` — does the prompt ask to create/change? (write,
  escalate-only: Jev may turn a missed directive into a workflow,
  never switch the evidence flow off)
* ``route`` — which department owns the prompt? (write)

Questions are in English (Jev's primary language) with an explicit
pt-PT preamble. ROUTE's options derive from
``core.synapse.layers.DEPARTMENT_PATTERNS`` so a new department is never
missing from the question.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from core.decisions.models import Answer, Question, QuestionType
from core.decisions.site import LANGUAGE_PREAMBLE, Site, interpret_choice, interpret_noul
from core.synapse.layers import DEPARTMENT_PATTERNS

NO_DEPARTMENT = "none"
REFINE_GAPS: dict[str, str] = {
    "target": "It does not say WHAT to change (no file, component, page or artefact).",
    "scope": "It does not bound HOW MUCH to change (size, boundaries, what is out).",
    "acceptance": "It does not say how to tell it is DONE (behaviour, criteria, tests).",
    "none": "Nothing essential is missing.",
}

# Eduardo's wording (QG PR1 carry): the two clauses are exact complements
# over the same three items, so no prompt satisfies both. The old "NO if it
# names what to change and the intended result" overlapped the YES clause
# for a prompt with a target and a scope but no success criterion.
REFINE_CHECKLIST = (
    "Check three items: a concrete target (WHAT to change: a file, component, page "
    "or artefact), a bounded scope (HOW MUCH to change), and a success criterion "
    "(how to tell it is DONE: the intended behaviour or result). An item counts as "
    "present when it is stated, even briefly, or unmistakably implied (\"fix the "
    "failing login test\" states its own success criterion). Answer YES when at "
    "least one of the three items is missing; answer NO only when all three are "
    "present."
)

# One line per department, from the CLAUDE.md department table.
DEPARTMENT_DESCRIPTIONS: dict[str, str] = {
    "dev": "Software development: code, features, bugs, APIs, tests, deploys, architecture.",
    "marketing": "Marketing & growth: campaigns, SEO, social media, ads, email marketing.",
    "finance": "Finance & investment: budgets, forecasts, pricing math, valuation, cash flow.",
    "ecom": "E-commerce: online stores, Shopify, catalogue, checkout, marketplaces.",
    "strategy": "Strategy & innovation: market analysis, competitors, positioning, roadmaps.",
    "ops": "Operations & automation: processes, SOPs, n8n/Zapier workflows, integrations.",
    "kb": "Knowledge management: research, notes, personas, Obsidian vault, transcripts.",
    "brand": "Brand & design: identity, logos, palettes, UX/UI, mockups, design systems.",
    "saas": "SaaS & micro-SaaS: subscriptions, PLG, churn, MRR, onboarding metrics.",
    "landing": "Landing pages & funnels: sales pages, offers, headlines, conversion copy.",
    "community": "Communities & groups: Discord, Skool, memberships, engagement, gamification.",
    "content": "Content & viralization: hooks, scripts, short-form video, repurposing.",
    "pm": "Project management: sprints, backlog, stories, estimates, agile rituals.",
    "lead": "Leadership & people: team health, feedback, hiring, performance, culture.",
    "sales": "Sales & negotiation: pipeline, proposals, prospecting, objections, deals.",
    "org": "Organization & teams: org design, compensation, remote work, team structure.",
}


def _instructions(body: str) -> str:
    return f"{LANGUAGE_PREAMBLE} {body}"


def prompt_state(prompt: str, prior: str | Sequence[str] = "") -> dict[str, Any]:
    """The state every prompt site reads: the new prompt + recent user messages."""
    recent = [prior] if isinstance(prior, str) else list(prior)
    return {
        "prompt": prompt,
        "recent_user_messages": [m for m in recent if m and m.strip()],
    }


# --- topic-drift -------------------------------------------------------------

def _topic_drift_questions() -> dict[str, Question]:
    return {"topic_shift": Question(type=QuestionType.NOUL, instructions=_instructions(
        "The state holds the user's new prompt and their recent messages in this "
        "session. Answer yes when the new prompt starts a different, unrelated task "
        "that a fresh session would serve better. Answer no when it continues, "
        "refines, corrects or follows up the same work, or when there are no recent "
        "messages."
    ))}


def _topic_drift_interpret(answers: dict[str, Answer], threshold: float) -> bool | None:
    return interpret_noul(answers.get("topic_shift"), threshold)


TOPIC_DRIFT = Site(
    name="topic-drift", questions=_topic_drift_questions,
    interpret=_topic_drift_interpret, risk="read",
    state_class="prompt",
)


# --- refine ------------------------------------------------------------------

def _refine_questions() -> dict[str, Question]:
    return {
        "vague": Question(type=QuestionType.NOUL, instructions=_instructions(
            "The prompt asks an AI coding assistant to build or change something. "
            f"{REFINE_CHECKLIST}"
        )),
        "missing": Question(type=QuestionType.CHOICE, instructions=_instructions(
            "Which essential piece of information is most clearly missing from the "
            "prompt?"
        ), criteria=dict(REFINE_GAPS)),
    }


def _refine_interpret(answers: dict[str, Answer], threshold: float) -> bool | None:
    vague = interpret_noul(answers.get("vague"), threshold)
    if vague is not None:
        return vague
    gap = interpret_choice(answers.get("missing"), threshold)
    return None if gap is None else gap != "none"


# Demoted to shadow on 2026-09-23 by the replay gate (Jev 60.6 % vs
# heuristic 90.9 %, n=34); PR5 relabels the corpus before any promotion.
REFINE = Site(
    name="refine", questions=_refine_questions, interpret=_refine_interpret, risk="read",
    default_mode="shadow",
    state_class="prompt",
)


# --- creation-intent ---------------------------------------------------------

def _creation_questions() -> dict[str, Question]:
    return {"creation_intent": Question(type=QuestionType.NOUL, instructions=_instructions(
        "Answer yes when the prompt directs the assistant to create, build, change, "
        "fix, continue, ship, publish, merge or deploy something (work that will "
        "modify files, code, content or releases), including polite requests such as "
        "'can you implement X?'. Answer no for questions seeking information or "
        "explanation, greetings, thanks, or slash/shell commands."
    ))}


def _creation_interpret(answers: dict[str, Answer], threshold: float) -> bool | None:
    return interpret_noul(answers.get("creation_intent"), threshold)


CREATION_INTENT = Site(
    name="creation-intent", questions=_creation_questions,
    interpret=_creation_interpret, risk="write", direction="escalate_only",
    is_escalation=lambda jev, heur: jev is True and heur is False,
    state_class="prompt",
)


# --- route -------------------------------------------------------------------

def route_options() -> dict[str, str]:
    """Every department key of L1 plus ``none``, each with one description."""
    options = {
        dept: DEPARTMENT_DESCRIPTIONS.get(dept, f"The '{dept}' department.")
        for dept in DEPARTMENT_PATTERNS
    }
    options[NO_DEPARTMENT] = "No single department fits (chit-chat, meta, or unclear)."
    return options


def _route_questions() -> dict[str, Question]:
    return {"department": Question(type=QuestionType.CHOICE, instructions=_instructions(
        "Which ArkaOS department should own this prompt? Pick the department whose "
        "work the prompt asks for, judged by intent rather than keywords."
    ), criteria=route_options())}


def _route_interpret(answers: dict[str, Answer], threshold: float) -> str | None:
    choice = interpret_choice(answers.get("department"), threshold)
    if choice is None:
        return None
    return "" if choice == NO_DEPARTMENT else choice


ROUTE = Site(
    name="route", questions=_route_questions, interpret=_route_interpret, risk="write",
    timeout_ms=1000,
    state_class="prompt",
)

PROMPT_SITES: tuple[Site, ...] = (TOPIC_DRIFT, REFINE, CREATION_INTENT, ROUTE)
