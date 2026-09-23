"""Decision engine — one bounded call per turn for every active site.

:func:`decide` never raises. Paths:

* every site ``off`` (or bypass / disabled) → heuristics, no disk, no network;
* no transport (no key) → heuristics, no disk, no network;
* every live site ``shadow`` → detached worker (``shadow.py``), heuristics now;
* any site ``act`` → ONE synchronous call carrying the questions of every
  live site (keys ``<site>__<question>``), capped by the smallest ceiling.

Each live path writes one telemetry line per site. Unavailability of any
kind (``DecisionUnavailable.reason``) lands in ``Outcome.reason`` and the
caller acts on its heuristic.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace

from core.decisions import cache
from core.decisions.backoff import blocked
from core.decisions.client import DecisionUnavailable, post_decision
from core.decisions.config import (
    DecisionsConfig,
    Mode,
    load_decisions_config,
    site_mode,
    site_timeout_ms,
    threshold_for,
)
from core.decisions.models import Answer, DecisionRequest, DecisionResponse, Question, State
from core.decisions.privacy import prepare_state, strictest_state_class
from core.decisions.registry import SITES
from core.decisions.shadow import spawn_shadow
from core.decisions.site import Outcome, Site, SiteCall, answer_confidence, valid_answers
from core.decisions.telemetry import (
    DecisionRecord,
    call_cost_usd,
    record,
    record_call_cost,
    state_sha16,
)
from core.decisions.transport import Transport, resolve_transport

MIN_CALL_MS = 50  # below this the call cannot finish: skip it ("deadline")

RunResult = tuple[DecisionResponse | None, str, int]


@dataclass(frozen=True)
class CallMeta:
    """What every telemetry line of one call shares."""

    call_id: str
    session_id: str
    state_sha16: str
    transport: Transport
    latency_ms: int
    reason: str


def question_key(site_name: str, question: str) -> str:
    """Wire key ``<site>__<question>`` (hyphens → underscores)."""
    return f"{site_name.replace('-', '_')}__{question}"


def active(cfg: DecisionsConfig | None = None) -> bool:
    """True when at least one registered site is live AND a transport exists."""
    cfg = cfg or load_decisions_config()
    if not any(site_mode(cfg, site) != "off" for site in SITES.values()):
        return False
    return resolve_transport(cfg) is not None


def build_request(calls: Sequence[SiteCall], state: State, model: str) -> DecisionRequest:
    """One request holding every question of every call."""
    questions: dict[str, Question] = {}
    for call in calls:
        for name, question in call.site.questions().items():
            questions[question_key(call.site.name, name)] = question
    return DecisionRequest(model=model, state=state, questions=questions)


def decide(
    calls: Sequence[SiteCall],
    state: State,
    *,
    session_id: str,
    timeout_ms: int | None = None,
    cfg: DecisionsConfig | None = None,
    model: str | None = None,
) -> dict[str, Outcome]:
    """Outcome per site name. Never raises: internal errors → heuristics.

    ``model`` is the ``decisions.model`` of ``models.yaml`` (alias or id);
    None keeps the transport default.
    """
    try:
        return _decide(calls, state, session_id, timeout_ms, cfg, model)
    except Exception as exc:
        return _heuristics(calls, {}, f"internal:{type(exc).__name__}")


def _decide(
    calls: Sequence[SiteCall],
    state: State,
    session_id: str,
    timeout_ms: int | None,
    cfg: DecisionsConfig | None,
    model: str | None = None,
) -> dict[str, Outcome]:
    cfg = cfg or load_decisions_config()
    modes: dict[str, Mode] = {c.site.name: site_mode(cfg, c.site) for c in calls}
    live = [c for c in calls if modes[c.site.name] != "off"]
    if not live:
        return _heuristics(calls, modes, "off")
    transport = resolve_transport(cfg, model=model)
    if transport is None:
        return _heuristics(calls, modes, "no-transport")
    if all(modes[c.site.name] == "shadow" for c in live):
        spawn_shadow(live, state, session_id)
        return _heuristics(calls, modes, "shadow")
    timeout = _effective_timeout_ms(cfg, live, modes, timeout_ms)
    outcomes = _heuristics(calls, modes, "off")
    outcomes.update(run_and_record(
        live, state, modes=modes, cfg=cfg, transport=transport,
        session_id=session_id, timeout_s=timeout / 1000,
    ))
    return outcomes


def _heuristics(
    calls: Sequence[SiteCall], modes: Mapping[str, Mode], reason: str
) -> dict[str, Outcome]:
    return {
        c.site.name: Outcome(
            value=c.heuristic, heuristic=c.heuristic, jev=None, confidence=None,
            mode=modes.get(c.site.name, "off"), acted_on="heuristic", reason=reason,
        )
        for c in calls
    }


def _effective_timeout_ms(
    cfg: DecisionsConfig,
    live: Sequence[SiteCall],
    modes: Mapping[str, Mode],
    timeout_ms: int | None,
) -> int:
    base = cfg.hook_timeout_ms if timeout_ms is None else timeout_ms
    ceilings = [site_timeout_ms(cfg, c.site) for c in live if modes[c.site.name] == "act"]
    return min([base, *ceilings])


def run_and_record(
    calls: Sequence[SiteCall],
    state: State,
    *,
    modes: Mapping[str, Mode],
    cfg: DecisionsConfig,
    transport: Transport,
    session_id: str,
    timeout_s: float,
) -> dict[str, Outcome]:
    """One call for ``calls``, resolved per site and written to telemetry."""
    if timeout_s * 1000 < MIN_CALL_MS:
        response, reason, latency = None, "deadline", 0
    else:
        response, reason, latency = run_sync(
            calls, state, transport=transport, cfg=cfg,
            timeout_s=timeout_s, session_id=session_id,
        )
    outcomes = {
        c.site.name: resolve(c, response, modes[c.site.name], threshold_for(cfg, c.site), reason)
        for c in calls
    }
    meta = CallMeta(uuid.uuid4().hex[:12], session_id, state_sha16(state),
                    transport, latency, reason)
    record_outcomes(calls, outcomes, response, meta)
    return outcomes


def run_sync(
    calls: Sequence[SiteCall],
    state: State,
    *,
    transport: Transport,
    cfg: DecisionsConfig,
    timeout_s: float,
    session_id: str = "",
) -> RunResult:
    """backoff → privacy → cache → POST → cache.put. ``(response|None, reason, ms)``."""
    cause = blocked()
    if cause is not None:
        # The trip's cause rides along ("backoff:http-401") so telemetry and
        # /arka decisions say WHY the breaker is open, not just that it is.
        return None, f"backoff:{cause}", 0
    start = time.monotonic()
    try:
        return _fetch(calls, state, transport, cfg, timeout_s, session_id)
    except DecisionUnavailable as exc:
        return None, exc.reason, int((time.monotonic() - start) * 1000)


def _fetch(
    calls: Sequence[SiteCall],
    state: State,
    transport: Transport,
    cfg: DecisionsConfig,
    timeout_s: float,
    session_id: str,
) -> RunResult:
    redact = cfg.redact_clients and any(c.site.redact_default for c in calls)
    # The strictest class governs a mixed call (a diff site keeps the whole
    # request fail-closed); session_id scopes the once-per-session notice.
    prepared = prepare_state(
        state, redact=redact, session_id=session_id,
        state_class=strictest_state_class(c.site.state_class for c in calls),
    )
    request = build_request(calls, prepared, transport.model)
    key = cache.cache_key(transport.model, prepared, request.questions)
    hit = cache.get(key, cfg.cache_ttl_seconds)
    if hit is not None:
        return hit, "cache-hit", 0
    response, latency_ms = post_decision(transport, request, timeout_s)
    cache.put(key, response)
    record_call_cost(session_id, transport, response.usage)
    return response, "ok", latency_ms


def site_answers(site_name: str, response: DecisionResponse) -> dict[str, Answer]:
    """This site's answers, keyed by bare question name."""
    prefix = question_key(site_name, "")
    return {
        key[len(prefix):]: answer
        for key, answer in response.answers.items()
        if key.startswith(prefix)
    }


def valid_site_answers(site: Site, response: DecisionResponse) -> dict[str, Answer]:
    """This site's answers with every off-menu choice dropped.

    The ONLY answers that leave the engine (``Outcome.answers``, the
    telemetry line): a choice outside the offered options is untrusted
    text and must survive neither on disk nor in the hook's context.
    """
    return valid_answers(site.questions(), site_answers(site.name, response))


def resolve(
    call: SiteCall,
    response: DecisionResponse | None,
    mode: Mode,
    threshold: float,
    reason: str = "ok",
) -> Outcome:
    """Turn the response into this site's Outcome (mode and direction applied)."""
    h = call.heuristic
    if response is None:
        return Outcome(h, h, None, None, mode, "heuristic", reason)
    answers = valid_site_answers(call.site, response)
    return replace(_judge(call, answers, mode, threshold), answers=answers)


def _judge(
    call: SiteCall, answers: dict[str, Answer], mode: Mode, threshold: float
) -> Outcome:
    h = call.heuristic
    jev = call.site.interpret(answers, threshold)
    confidence = _min_confidence(answers)
    if jev is None:
        return Outcome(h, h, None, confidence, mode, "heuristic", "abstain")
    if mode != "act":
        return Outcome(h, h, jev, confidence, mode, "heuristic", "shadow")
    return _apply_direction(call, jev, confidence, mode)


def _apply_direction(
    call: SiteCall, jev: object, confidence: float | None, mode: Mode
) -> Outcome:
    site, h = call.site, call.heuristic
    if site.direction == "escalate_only" and jev != h:
        check = site.is_escalation
        if check is None or not check(jev, h):
            return Outcome(h, h, jev, confidence, mode, "heuristic", "downgrade-blocked")
    return Outcome(jev, h, jev, confidence, mode, "jev", "jev")


def _min_confidence(answers: Mapping[str, Answer]) -> float | None:
    values = [c for c in (answer_confidence(a) for a in answers.values()) if c is not None]
    return round(min(values), 4) if values else None


def _compact(answers: Mapping[str, Answer]) -> dict[str, dict[str, object]]:
    out: dict[str, dict[str, object]] = {}
    for name, a in answers.items():
        value = a.choice if a.choice is not None else a.noul if a.noul is not None else a.score
        out[name] = {"v": value, "c": answer_confidence(a)}
    return out


def record_outcomes(
    calls: Sequence[SiteCall],
    outcomes: Mapping[str, Outcome],
    response: DecisionResponse | None,
    meta: CallMeta,
) -> None:
    """One telemetry line per site; cost and tokens split across sites."""
    share = max(1, len(calls))
    fresh = response is not None and meta.reason == "ok"
    cost = call_cost_usd(meta.transport, response.usage) if fresh and response else None
    tokens = response.usage.input_tokens // share if fresh and response else 0
    for call in calls:
        out = outcomes[call.site.name]
        record(_record_for(call, out, response, meta, cost, share, tokens))


def _record_for(
    call: SiteCall,
    out: Outcome,
    response: DecisionResponse | None,
    meta: CallMeta,
    cost: float | None,
    share: int,
    tokens: int,
) -> DecisionRecord:
    answers = valid_site_answers(call.site, response) if response is not None else {}
    return DecisionRecord(
        session_id=meta.session_id, site=call.site.name, mode=out.mode,
        call_id=meta.call_id, question_keys=sorted(call.site.questions()),
        answers=_compact(answers), confidence=out.confidence,
        latency_ms=meta.latency_ms, input_tokens=tokens,
        cost_usd=round(cost / share, 10) if cost is not None else 0.0,
        transport=meta.transport.name,
        model=(response.model if response is not None and response.model else meta.transport.model),
        fallback_used=out.jev is None, reason=out.reason,
        heuristic_result=out.heuristic, jev_result=out.jev,
        agree=(out.jev == out.heuristic) if out.jev is not None else None,
        acted_on=out.acted_on, state_sha16=meta.state_sha16,
        cache_hit=meta.reason == "cache-hit",
    )
