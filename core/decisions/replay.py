"""Replay harness — the evidence gate for moving a site between modes.

Runs a labelled corpus (``config/decisions/corpora/<site>.jsonl``) through
the site's heuristic and, online, through Jev. Gate (online):

* Jev precision on the cases it answers ≥ heuristic precision on the SAME
  cases + 5 pp;
* abstain rate (abstain + unavailable) ≤ 25 %;
* escalate-only sites: false escalations ≤ 5 % of the cases where the
  heuristic was already right.

Corpus validity (both modes): ≥ 30 cases, ≥ 50 % pt-PT, and every
``expected`` of the site's type (:data:`EXPECTED`: bool, a department, a
role, a tier, a department list, a registry command id, a learning signal,
a ``[verdict, blocker]`` pair or five 1-10 slop scores). ``--offline``
scores the heuristic only and passes on a valid corpus.

Sites whose value is not the corpus label compare through :data:`LABELS`
(forge-complexity: dimensions → tier; forge-departments: order-free set;
learning-signal: the ``signal``; qg-prescreen: ``[verdict, blocker]``;
slop-score: the five scores in rubric order).

Two PR3 sites have no heuristic, so "Jev vs heuristic" is not their gate:

* ``qg-prescreen`` replays against the neutral ``{"verdict": "unknown"}``
  baseline, which never matches a label: the report measures Jev against
  the real label only (the precision rule reduces to Jev ≥ 5 %, the
  abstain rule is what binds).
* ``slop-score`` (:data:`MAE_SITES`): the precision rule is replaced by
  the mean absolute error of Jev's TOTAL (5-50) against the labelled total
  on the answered cases, ``mean_abs_error`` ≤ :data:`MAX_SLOP_MAE`; exact
  five-score agreement is still reported as ``jev_accuracy``.

Cases may carry ``context``: the site inputs the live call site has
besides the text (phantom-action ``tool_uses``, ui-in-ts ``path``).
Exit codes: 0 pass, 1 fail, 2 usage.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field, replace
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, StrictBool, StrictInt, ValidationError

from core.decisions.config import (
    DecisionsConfig,
    load_decisions_config,
    site_timeout_ms,
    threshold_for,
)
from core.decisions.engine import resolve, run_sync
from core.decisions.models import State
from core.decisions.paths import repo_root
from core.decisions.registry import SITES
from core.decisions.site import Outcome, Site, SiteCall
from core.decisions.sites import governance as gov
from core.decisions.sites import quality
from core.decisions.sites.command import command_state
from core.decisions.sites.dispatch import skill_state
from core.decisions.sites.forge import forge_state
from core.decisions.sites.prompt import prompt_state
from core.decisions.telemetry import REPLAY_COST_CATEGORY, REPLAY_SESSION_ID, call_cost_usd
from core.decisions.transport import Transport, resolve_transport

# dispatch-role and subagent-discipline: the keyword baselines the UPS hook
# ships as those sites' heuristics — replayed as the SAME functions.
from core.hooks.ups_dispatch import keyword_dispatch_role, keyword_needs_isolation

MIN_CASES = 30
MIN_PT_SHARE = 0.5
MARGIN = 0.05
MAX_ABSTAIN = 0.25
MAX_FALSE_ESCALATION = 0.05
MAX_SLOP_MAE = 5.0  # of a 5-50 total: one point per dimension on average
MAE_SITES = frozenset({"slop-score"})

Gate = Literal["pass", "fail", "offline"]


class ReplayCase(BaseModel):
    """One labelled prompt."""

    model_config = ConfigDict(extra="forbid")

    id: str
    lang: Literal["pt", "en"]
    prompt: str
    prior: list[str] = []
    context: dict[str, StrictInt | str] = {}
    expected: StrictBool | str | list[str] | list[StrictInt]


@dataclass
class ReplayReport:
    """Scores and gate verdict for one site's corpus."""

    site: str
    cases: int
    pt_share: float
    heuristic_accuracy: float
    jev_accuracy: float | None = None
    heuristic_on_answered: float | None = None
    act_accuracy: float | None = None
    abstain_rate: float | None = None
    false_escalation_rate: float | None = None
    # MAE_SITES only: mean |Jev total - labelled total| on the answered cases.
    mean_abs_error: float | None = None
    unavailable: int = 0
    # G3 evidence: median latency of the calls that really went out
    # (cache hits and an open breaker excluded) and their summed cost.
    # None whenever nothing was measured (offline, or every answer from
    # the cache), so "not measured" never reads as "0 ms measured".
    p50_latency_ms: int | None = None
    cost_usd: float | None = None
    # The per-call ceiling of an online run: the site's own ceiling (what
    # the live call site uses) unless ``--timeout-ms`` overrides it.
    timeout_ms: int | None = None
    # Online only: cases whose site asked a question (a designed
    # "no-questions" is not asked) and, of those, calls that reached the
    # endpoint. ``replay_report`` counts a run only when enough reached.
    asked: int | None = None
    reached: int | None = None
    by_lang: dict[str, dict[str, float | None]] = field(default_factory=dict)
    gate: Gate = "offline"
    failures: list[str] = field(default_factory=list)


# --- heuristics: the SAME pure functions the live call sites run ------------

def _heuristic_topic_drift(case: ReplayCase) -> bool:
    from core.hooks.user_prompt_submit import keyword_topic_shift

    return keyword_topic_shift(case.prompt, "\n".join(case.prior))


def _heuristic_refine(case: ReplayCase) -> bool:
    from core.hooks.user_prompt_submit import (
        _names_concrete_target,
        _refine_heuristic,
        _wf_classify,
    )

    text = case.prompt
    if not _wf_classify(text) or text.strip().startswith("/"):
        return False
    return not _names_concrete_target(text) and _refine_heuristic(text)


def _heuristic_creation(case: ReplayCase) -> bool:
    from core.hooks.user_prompt_submit import _wf_classify

    return _wf_classify(case.prompt)


def _heuristic_route(case: ReplayCase) -> str:
    from core.synapse.layers import keyword_department

    return keyword_department(case.prompt) or ""


def _heuristic_bash_effect(case: ReplayCase) -> bool:
    from core.workflow.flow_enforcer import bash_is_effect

    return bash_is_effect(case.prompt)


def forge_estimates(prompt: str) -> tuple[list[str], list[str]]:
    """``(affected_files, departments)`` exactly as Forge step 3 estimates them.

    Both estimators are ``ForgeOrchestrator`` methods that read no instance
    state, so a bare instance (no ``__init__``, no dispatcher) runs the
    real code without its side effects.
    """
    from core.forge.orchestrator import ForgeOrchestrator

    bare = ForgeOrchestrator.__new__(ForgeOrchestrator)
    return bare._estimate_affected_files(prompt), bare._estimate_departments(prompt)


def _heuristic_forge_departments(case: ReplayCase) -> list[str]:
    return sorted(forge_estimates(case.prompt)[1])


def _heuristic_forge_complexity(case: ReplayCase) -> dict[str, int]:
    # No similar plans / reused patterns: replay has no plan history, so
    # novelty scores as the heuristic's maximum (90) on every case.
    from core.forge.complexity import score_dimensions

    files, departments = forge_estimates(case.prompt)
    return score_dimensions(case.prompt, files, departments, [], []).model_dump()


@lru_cache(maxsize=1)
def registry_commands() -> tuple[dict[str, object], ...]:
    """``knowledge/commands-registry.json`` commands (read once)."""
    path = repo_root() / "knowledge" / "commands-registry.json"
    return tuple(json.loads(path.read_text(encoding="utf-8"))["commands"])


def skill_candidates_for(prompt: str, dept: str | None = None) -> list[dict[str, str]]:
    """The skill-hints menu, built by the SAME function the UPS hook uses
    (``core.synapse.command_menu.skill_hint_candidates``): top-20 keyword
    commands + the routed department's commands, capped at 60.

    ``dept`` is the department the route site settled on; None falls back
    to the L1 keyword route, which is what the hook uses when the route
    site does not act.
    """
    from core.synapse.command_menu import skill_hint_candidates
    from core.synapse.layers import keyword_department

    routed = (keyword_department(prompt) or "") if dept is None else dept
    return skill_hint_candidates(registry_commands(), prompt, routed)


def replay_route(case: ReplayCase) -> str | None:
    """The route the skill-hints replay assumes: the expected command's department.

    The replay scores the skill-hints site on its own job (pick the command
    from the menu), with the route taken as correct; the route site has its
    own replay (90.9 % on 2026-09-23), and end-to-end coverage in the hook
    is bounded by it. A case whose expected answer is "no command" keeps
    the keyword route (None).
    """
    from core.synapse.command_menu import command_department

    for command in registry_commands():
        if command.get("id") == case.expected:
            return command_department(command) or None
    return None


def _heuristic_skill_hint(case: ReplayCase) -> str:
    # The live L5 hint is keyword-only: the routed-department fill of the
    # menu never becomes a hint by itself.
    from core.synapse.layers import _score_commands

    top = _score_commands(list(registry_commands()), case.prompt.lower())
    ids = {str(c.get("command", "")): str(c["id"]) for c in reversed(registry_commands())}
    return ids.get(top[0][1], "") if top else ""


def _heuristic_phantom(case: ReplayCase) -> bool:
    return gov.heuristic_unbacked_effect(case.prompt, case.context.get("tool_uses"))


def _heuristic_ui(case: ReplayCase) -> bool:
    return gov.heuristic_ui_code(str(case.context.get("path", "")), case.prompt)


HEURISTICS: dict[str, Callable[[ReplayCase], object]] = {
    "topic-drift": _heuristic_topic_drift,
    "refine": _heuristic_refine,
    "creation-intent": _heuristic_creation,
    "route": _heuristic_route,
    "bash-effect": _heuristic_bash_effect,
    "forge-departments": _heuristic_forge_departments,
    "forge-complexity": _heuristic_forge_complexity,
    "skill-hints": _heuristic_skill_hint,
    "dispatch-role": lambda case: keyword_dispatch_role(case.prompt),
    "subagent-discipline": lambda case: keyword_needs_isolation(case.prompt),
    "sycophancy": lambda case: gov.heuristic_sycophantic(case.prompt),
    "phantom-action": _heuristic_phantom,
    "skill-proposer": lambda case: gov.heuristic_repeatable_capability(case.prompt),
    "learning-signal": lambda case: gov.heuristic_learning_signal(case.prompt),
    "ui-in-ts": _heuristic_ui,
    "qg-prescreen": lambda case: quality.prescreen_heuristic(),
    "slop-score": lambda case: None,  # no slop heuristic exists in code
}


def _forge_case_state(case: ReplayCase) -> State:
    files, departments = forge_estimates(case.prompt)
    return forge_state(case.prompt, files, departments)


def _sycophancy_state(case: ReplayCase) -> State:
    return gov.stop_state(case.prompt, user_message=case.prior[-1] if case.prior else "")


def _phantom_state(case: ReplayCase) -> State:
    tool_uses = case.context.get("tool_uses")
    return gov.stop_state(case.prompt, tool_uses=tool_uses if isinstance(tool_uses, int) else None)


_GIT_B_PATH = re.compile(r"^diff --git a/\S+ b/(\S+)$", re.M)


def _diff_path(diff: str) -> str:
    """The file a corpus diff names first ('' when none: privacy then refuses it)."""
    m = _GIT_B_PATH.search(diff)
    return m.group(1) if m else ""


STATES: dict[str, Callable[[ReplayCase], State]] = {
    "bash-effect": lambda case: command_state(case.prompt),
    "forge-departments": _forge_case_state,
    "forge-complexity": _forge_case_state,
    "skill-hints": lambda case: skill_state(
        case.prompt, skill_candidates_for(case.prompt, replay_route(case))),
    "sycophancy": _sycophancy_state,
    "phantom-action": _phantom_state,
    "skill-proposer": lambda case: gov.stop_state(case.prompt),
    "learning-signal": lambda case: gov.stop_state("", user_message=case.prompt),
    "ui-in-ts": lambda case: gov.ui_state(str(case.context.get("path", "")), case.prompt),
    "qg-prescreen": lambda case: quality.diff_state(case.prompt, _diff_path(case.prompt)),
    # A corpus row is prose, as the live site's .md/.mdx/.txt files are.
    "slop-score": lambda case: quality.prose_state(case.prompt, f"{case.id}.md"),
}


def case_state(site: str, case: ReplayCase) -> State:
    """The state the live call site would send for this case."""
    builder = STATES.get(site)
    return builder(case) if builder else prompt_state(case.prompt, case.prior)


# --- corpus labels -----------------------------------------------------------

TIERS = frozenset({"SHALLOW", "STANDARD", "DEEP"})


def _is_department(value: object) -> bool:
    from core.synapse.layers import DEPARTMENT_PATTERNS

    return isinstance(value, str) and value in DEPARTMENT_PATTERNS


def _is_department_list(value: object) -> bool:
    return (isinstance(value, list) and 1 <= len(value) <= 4
            and len(set(value)) == len(value) and all(_is_department(v) for v in value))


def _is_role(value: object) -> bool:
    from core.runtime.model_router import ROLE_DESCRIPTIONS

    return isinstance(value, str) and value in ROLE_DESCRIPTIONS


def _is_command_id(value: object) -> bool:
    return isinstance(value, str) and value in {c.get("id") for c in registry_commands()}


def _is_bool(value: object) -> bool:
    return isinstance(value, bool)


def _is_prescreen_label(value: object) -> bool:
    """``[verdict, blocker]``: approved pairs with none, rejected with a real class."""
    if not (isinstance(value, list) and len(value) == 2):
        return False
    pair: list[object] = value
    verdict, blocker = pair
    if verdict == "approved":
        return blocker == quality.NO_BLOCKER
    return verdict == "rejected" and blocker in set(quality.BLOCKERS) - {quality.NO_BLOCKER}


def _is_slop_label(value: object) -> bool:
    """Five ints in 1..10, rubric order."""
    return (isinstance(value, list) and len(value) == len(quality.SLOP_DIMENSIONS)
            and all(isinstance(v, int) and not isinstance(v, bool)
                    and 1 <= v <= quality.SLOP_LEVELS for v in value))


EXPECTED: dict[str, Callable[[object], bool]] = {
    "topic-drift": _is_bool, "refine": _is_bool, "creation-intent": _is_bool,
    "bash-effect": _is_bool, "subagent-discipline": _is_bool,
    "route": lambda v: v == "" or _is_department(v),
    "dispatch-role": _is_role,
    "forge-complexity": lambda v: isinstance(v, str) and v in TIERS,
    "forge-departments": _is_department_list,
    "skill-hints": _is_command_id,
    "sycophancy": _is_bool, "phantom-action": _is_bool, "skill-proposer": _is_bool,
    "ui-in-ts": _is_bool,
    "learning-signal": lambda v: isinstance(v, str) and v in gov.LEARNING_SIGNALS,
    "qg-prescreen": _is_prescreen_label,
    "slop-score": _is_slop_label,
}


def complexity_tier(value: object) -> object:
    """Dimensions (0-100 each) → ``SHALLOW|STANDARD|DEEP`` with the Forge's weights."""
    if not isinstance(value, dict):
        return value
    from core.forge.complexity import calculate_weighted_score, determine_tier
    from core.forge.schema import ComplexityDimensions

    tier = determine_tier(calculate_weighted_score(ComplexityDimensions(**value)))
    return tier.value.upper()


def _department_set(value: object) -> object:
    return sorted(value) if isinstance(value, list) else value


def _learning_label(value: object) -> object:
    return value.get("signal") if isinstance(value, dict) else value


def _prescreen_label(value: object) -> object:
    if not isinstance(value, dict):
        return value
    return [value.get("verdict"), value.get("blocker")]


def _slop_label(value: object) -> object:
    if not isinstance(value, dict):
        return value
    return [value.get(d) for d in quality.SLOP_DIMENSIONS]


LABELS: dict[str, Callable[[object], object]] = {
    "forge-complexity": complexity_tier,
    "forge-departments": _department_set,
    "learning-signal": _learning_label,
    "qg-prescreen": _prescreen_label,
    "slop-score": _slop_label,
}


def default_corpus_path(site: str) -> Path:
    """``config/decisions/corpora/<site>.jsonl`` in this checkout."""
    return repo_root() / "config" / "decisions" / "corpora" / f"{site}.jsonl"


def load_corpus(site: str, path: Path | None = None) -> list[ReplayCase]:
    """Parse a JSONL corpus; ValueError names the first bad line."""
    source = path or default_corpus_path(site)
    check = EXPECTED.get(site)
    cases: list[ReplayCase] = []
    for number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            case = ReplayCase.model_validate(json.loads(line))
        except (ValueError, ValidationError) as exc:
            raise ValueError(f"{source}:{number}: {exc}") from exc
        if check is not None and not check(case.expected):
            raise ValueError(f"{source}:{number}: expected {case.expected!r} is not a {site} label")
        cases.append(case)
    return cases


# --- scoring -----------------------------------------------------------------

Row = tuple[ReplayCase, object, Outcome | None]


def _labelled(site: str, rows: Sequence[Row]) -> list[Row]:
    label = LABELS.get(site)
    if label is None:
        return list(rows)
    # Both sides go through the label: a department list is compared as a
    # set, so the corpus order must not matter either.
    return [(case.model_copy(update={"expected": label(case.expected)}), label(h),
             _label_outcome(label, out)) for case, h, out in rows]


def _label_outcome(label: Callable[[object], object], out: Outcome | None) -> Outcome | None:
    if out is None:
        return None
    jev = None if out.jev is None else label(out.jev)
    return replace(out, value=label(out.value), heuristic=label(out.heuristic), jev=jev)


def _rate(hits: int, total: int) -> float | None:
    return round(hits / total, 4) if total else None


def _accuracy(rows: Sequence[Row], pick: Callable[[Row], object]) -> float | None:
    return _rate(sum(1 for r in rows if pick(r) == r[0].expected), len(rows))


def _answered(rows: Sequence[Row]) -> list[Row]:
    return [r for r in rows if r[2] is not None and r[2].jev is not None]


def _false_escalation(site: Site, rows: Sequence[Row]) -> float | None:
    if site.direction != "escalate_only":
        return None
    at_risk = [r for r in rows if r[1] == r[0].expected]
    wrong = [r for r in at_risk if r[2] is not None and r[2].acted_on == "jev"
             and r[2].value != r[0].expected]
    return _rate(len(wrong), len(at_risk))


def _by_lang(rows: Sequence[Row], online: bool) -> dict[str, dict[str, float | None]]:
    out: dict[str, dict[str, float | None]] = {}
    for lang in sorted({r[0].lang for r in rows}):
        subset = [r for r in rows if r[0].lang == lang]
        entry = {"cases": float(len(subset)), "heuristic": _accuracy(subset, lambda r: r[1])}
        if online:
            entry["jev"] = _accuracy(_answered(subset), lambda r: r[2].jev if r[2] else None)
        out[lang] = entry
    return out


def _base_report(site: Site, rows: Sequence[Row]) -> ReplayReport:
    pt = sum(1 for r in rows if r[0].lang == "pt")
    return ReplayReport(
        site=site.name, cases=len(rows), pt_share=_rate(pt, len(rows)) or 0.0,
        heuristic_accuracy=_accuracy(rows, lambda r: r[1]) or 0.0,
    )


def _online_scores(site: Site, rows: Sequence[Row], report: ReplayReport) -> None:
    answered = _answered(rows)
    report.jev_accuracy = _accuracy(answered, lambda r: r[2].jev if r[2] else None)
    report.heuristic_on_answered = _accuracy(answered, lambda r: r[1])
    report.act_accuracy = _accuracy(rows, lambda r: r[2].value if r[2] else r[1])
    report.abstain_rate = _rate(len(rows) - len(answered), len(rows))
    report.false_escalation_rate = _false_escalation(site, rows)
    if site.name in MAE_SITES:
        report.mean_abs_error = _mean_abs_error(answered)
    # "no-questions" is a site choosing not to ask (phantom-action with tools on
    # record, a skill bypass marker): an abstain by design, not an outage.
    report.unavailable = sum(1 for r in rows if r[2] is None or r[2].reason not in
                             ("jev", "abstain", "shadow", "downgrade-blocked", "no-questions"))


def _total(value: object) -> int | None:
    if not isinstance(value, list) or not all(isinstance(v, int) for v in value):
        return None
    return sum(value)


def _mean_abs_error(answered: Sequence[Row]) -> float | None:
    """Mean |Jev total - labelled total| over the answered rows (5-list labels)."""
    errors = []
    for case, _, out in answered:
        jev, want = _total(out.jev if out else None), _total(case.expected)
        if jev is not None and want is not None:
            errors.append(abs(jev - want))
    return round(statistics.fmean(errors), 4) if errors else None


def _corpus_failures(report: ReplayReport) -> list[str]:
    failures = []
    if report.cases < MIN_CASES:
        failures.append(f"corpus has {report.cases} cases (< {MIN_CASES})")
    if report.pt_share < MIN_PT_SHARE:
        failures.append(f"pt-PT share {report.pt_share:.0%} (< {MIN_PT_SHARE:.0%})")
    return failures


def _precision_failures(report: ReplayReport) -> list[str]:
    jev, base = report.jev_accuracy, report.heuristic_on_answered
    if jev is None or base is None:
        return ["Jev answered no case"]
    if report.site in MAE_SITES:
        mae = report.mean_abs_error
        if mae is None or mae > MAX_SLOP_MAE:
            return [f"mean absolute error {mae} > {MAX_SLOP_MAE} (total, 5-50)"]
        return []
    if jev < base + MARGIN:
        return [f"Jev precision {jev:.1%} < heuristic {base:.1%} + {MARGIN:.0%}"]
    return []


def _gate_failures(report: ReplayReport) -> list[str]:
    failures = _precision_failures(report)
    if report.abstain_rate is not None and report.abstain_rate > MAX_ABSTAIN:
        failures.append(f"abstain {report.abstain_rate:.1%} > {MAX_ABSTAIN:.0%}")
    fe = report.false_escalation_rate
    if fe is not None and fe > MAX_FALSE_ESCALATION:
        failures.append(f"false escalation {fe:.1%} > {MAX_FALSE_ESCALATION:.0%}")
    return failures


# Reasons decided on this machine, before any byte left it.
LOCAL_REASONS = frozenset({"cache-hit", "no-questions", "deadline", "backoff", "egress-denied"})


def reached_endpoint(reason: str) -> bool:
    """True when the call went to the endpoint (answered, timed out or erred there)."""
    return reason.split(":", 1)[0] not in LOCAL_REASONS


@dataclass(frozen=True)
class CallSample:
    """What one replay call cost: latency when it went out, and USD."""

    latency_ms: int | None
    cost_usd: float
    reached: bool = False
    asked: bool = True


def _ask(
    site: Site,
    case: ReplayCase,
    heuristic: object,
    transport: Transport,
    cfg: DecisionsConfig,
    timeout_ms: int,
) -> tuple[Outcome, CallSample]:
    call = SiteCall(site, heuristic)
    state = case_state(site.name, case)
    response, reason, latency = run_sync(
        [call], state, transport=transport,
        cfg=cfg, timeout_s=timeout_ms / 1000, session_id=REPLAY_SESSION_ID,
        cost_category=REPLAY_COST_CATEGORY,
    )
    outcome = resolve(call, response, "act", threshold_for(cfg, site), reason, state=state)
    went_out = reason != "cache-hit" and not reason.startswith("backoff")
    fresh = reason == "ok" and response is not None
    cost = (call_cost_usd(transport, response.usage) or 0.0) if fresh and response else 0.0
    sample = CallSample(latency if went_out else None, cost,
                        reached=reached_endpoint(reason), asked=reason != "no-questions")
    return outcome, sample


def _call_scores(samples: Sequence[CallSample], report: ReplayReport) -> None:
    report.asked = sum(1 for s in samples if s.asked)
    report.reached = sum(1 for s in samples if s.asked and s.reached)
    latencies = [s.latency_ms for s in samples if s.latency_ms is not None]
    if not latencies:
        report.p50_latency_ms = report.cost_usd = None
        return
    report.p50_latency_ms = int(statistics.median(latencies))
    report.cost_usd = round(sum(s.cost_usd for s in samples), 10)


def _score_cases(
    site: Site,
    cases: Sequence[ReplayCase],
    transport: Transport | None,
    cfg: DecisionsConfig,
    ceiling_ms: int,
) -> tuple[list[Row], list[CallSample]]:
    """The heuristic for every case and, with a transport, Jev's outcome."""
    heuristic = HEURISTICS[site.name]
    rows: list[Row] = []
    samples: list[CallSample] = []
    for case in cases:
        h = heuristic(case)
        outcome = None
        if transport is not None:
            outcome, sample = _ask(site, case, h, transport, cfg, ceiling_ms)
            samples.append(sample)
        rows.append((case, h, outcome))
    return rows, samples


def replay(
    site: str,
    cases: Sequence[ReplayCase],
    *,
    transport: Transport | None,
    offline: bool = False,
    timeout_ms: int | None = None,
    cfg: DecisionsConfig | None = None,
) -> ReplayReport:
    """Score ``cases`` for ``site``; offline (or no transport) = heuristic only.

    Each online call is capped at ``timeout_ms``, else at the site's own
    ceiling: the replay cuts a call where the live site would. ``cfg``
    defaults to the operator's config (its thresholds are what ships);
    ``replay_report`` passes a copy with the answer cache off.
    """
    target = SITES[site]
    online = not offline and transport is not None
    cfg = cfg or load_decisions_config()
    ceiling = timeout_ms or site_timeout_ms(cfg, target)
    rows, samples = _score_cases(target, cases, transport if online else None, cfg, ceiling)
    rows = _labelled(site, rows)
    report = _base_report(target, rows)
    report.by_lang = _by_lang(rows, online)
    if online:
        report.timeout_ms = ceiling
        _online_scores(target, rows, report)
        _call_scores(samples, report)
    report.failures = _corpus_failures(report) + (_gate_failures(report) if online else [])
    report.gate = "fail" if report.failures else ("pass" if online else "offline")
    return report


def _call_line(report: ReplayReport) -> str:
    if report.abstain_rate is None:  # set only by an online run
        return "- p50 latency / cost: not measured (offline)"
    if report.p50_latency_ms is None or report.cost_usd is None:
        return "- p50 latency / cost: not measured (all cache hits)"
    return f"- p50 latency: {report.p50_latency_ms} ms; cost: ${report.cost_usd:.6f}"


def _render(report: ReplayReport) -> str:
    lines = [f"# Replay — {report.site} ({report.gate})",
             f"- cases: {report.cases} (pt-PT {report.pt_share:.0%})",
             f"- heuristic accuracy: {report.heuristic_accuracy:.1%}"]
    if report.jev_accuracy is not None:
        lines += [f"- Jev precision (answered): {report.jev_accuracy:.1%} vs heuristic "
                  f"{(report.heuristic_on_answered or 0):.1%} on the same cases",
                  f"- act accuracy: {(report.act_accuracy or 0):.1%}",
                  f"- abstain: {(report.abstain_rate or 0):.1%} (unavailable {report.unavailable})"]
    lines.append(_call_line(report))
    if report.false_escalation_rate is not None:
        lines.append(f"- false escalation: {report.false_escalation_rate:.1%}")
    if report.mean_abs_error is not None:
        lines.append(f"- mean absolute error (total, 5-50): {report.mean_abs_error}")
    for lang, scores in report.by_lang.items():
        lines.append(f"- {lang}: " + ", ".join(f"{k}={v}" for k, v in scores.items()))
    lines += [f"- FAIL: {f}" for f in report.failures]
    return "\n".join(lines)


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m core.decisions.replay")
    parser.add_argument("--site", required=True, choices=sorted(SITES))
    parser.add_argument("--corpus", type=Path, default=None)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--timeout-ms", type=int, default=None,
                        help="per-call ceiling (default: the site's own timeout_ms)")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI: exit 0 pass/offline-valid, 1 gate failed, 2 usage error."""
    try:
        ns = _parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2
    try:
        cases = load_corpus(ns.site, ns.corpus)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    transport = None if ns.offline else resolve_transport(load_decisions_config())
    if not ns.offline and transport is None:
        print("error: no transport (set OPENROUTER_API_KEY) — or pass --offline", file=sys.stderr)
        return 2
    report = replay(ns.site, cases, transport=transport, offline=ns.offline,
                    timeout_ms=ns.timeout_ms)
    print(json.dumps(asdict(report), ensure_ascii=False, indent=2) if ns.json else _render(report))
    return 0 if report.gate != "fail" else 1


if __name__ == "__main__":
    raise SystemExit(main())
