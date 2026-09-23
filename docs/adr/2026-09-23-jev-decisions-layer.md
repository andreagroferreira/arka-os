# ADR: Jev typed decisions layer (`core/decisions/`)

- **Status:** accepted
- **Date:** 2026-09-23
- **Deciders:** operator (campaign GO 2026-09-23), dev squad (Paulo, Gabriel)
- **Campaign:** JEV Decisions Layer, PR1 of 5 (`feature/jev-decisions-<n>`)
- **Related:** `docs/adr/2026-07-31-egress-policy.md` (every payload passes
  it), `docs/adr/2026-07-04-evidence-flow.md` (replay reports are G3
  evidence), `.claude/rules/bash-hooks.md` (bounded network rule)

## Context

ArkaOS makes dozens of heuristic decisions per turn: keyword routing (L1),
vague-request detection, topic drift, destructive Bash detection, Forge
tier, regex detectors for sycophancy, phantom actions and learning
signals, and none at all where a pre-screen of the Quality Gate would pay.
They are "smart if-statements" written as regex ladders and fixed weights,
bilingual in name only, and they tie-break by dict order.

Jev (`typesafe/jev-1.13`, typesafe.ai) is built for exactly that shape.

**What Jev is.** A typed decision model, "System 1": it reads a `state`
(text or JSON, up to 32k tokens) and a map of questions, and answers all
of them in one parallel pass with no text generation. Three question
types: `noul` (yes/no as a 0–1 value), `choice` (one of up to 255 options,
with per-option probabilities and a confidence) and `score` (a level on a
2–10 scale, with confidence). By construction the output cannot
hallucinate prose or violate its type. Documented latency 70–500 ms.

**What Jev is not.** Not an LLM: it does not write or review code, does
not converse, and has no chat-completions surface. It does not replace a
subagent, a reviewer or any System 2 reasoning. The vendor's documented
anti-patterns are chat, generation and any free-text output.

### Transport contract (OpenRouter Decisions, alpha)

Source: docs.typesafe.ai `llms-full.txt` and the OpenRouter announcement,
retrieved during G1 on 2026-09-23, then confirmed by a live smoke test the
same day (operator key, 4 calls, all HTTP 200; see "Smoke test evidence").

- `POST https://openrouter.ai/api/alpha/decisions`, `Authorization:
  Bearer $OPENROUTER_API_KEY`. The alpha endpoint has existed since
  2026-09-15. `/chat/completions` does **not** serve this model.
- Request body:
  ```json
  {"model": "typesafe/jev-1.13",
   "state": "<text or JSON>",
   "questions": {"<key>": {"type": "noul|choice|score",
                           "instructions": "...", "criteria": "..."}}}
  ```
- Response body, as observed live:
  ```json
  {"model": "typesafe/jev-1.13-20260917",
   "answers": {"<key>": {"type": "choice", "choice": "...",
                         "probabilities": {"...": 0.8}, "confidence": 0.9}},
   "usage": {"input_tokens": 749, "output_tokens": 118, "cost": 3.1458e-05},
   "id": "gen-dec-…", "provider": "TypeSafe"}
  ```
  The model is echoed with a date suffix (`-20260917`), so a response must
  never be rejected because `model` differs from the requested alias. `id`
  and `provider` are extra top-level fields the documentation does not
  list: response models ignore unknown fields rather than fail as
  `invalid-shape`. `usage.cost` is present, so telemetry records the
  billed cost as returned and uses `pricing.py` only as a fallback.
  `choice` answers carry `choice`, `score` answers carry `score`, `noul`
  answers carry `noul`. `noul` has **no** `confidence` field.
- Limits: state ≤ 32k tokens; ≤ 255 options per `choice`; 2–10 levels per
  `score`; no documented cap on questions per request. English is the
  primary language.
- Errors: 401 (key), 422 (shape), 429 (rate), 529 (overloaded).
- Price: $0.042 per million input tokens; output is reported in
  `output_tokens` but billed at 0 (749 input tokens → `cost` 3.1458e-05,
  exactly 749 × $0.042/M). Measured: ≈ $0.00003 per 4-question call.
- `provider: {"data_collection": "deny"}` in the request body is accepted
  (HTTP 200). Its effect cannot be verified from the response.
- Vendor confidence bands: > 0.9 act, 0.5–0.9 flag, < 0.5 human; the
  threshold rises with the risk of the decision.

### Smoke test evidence (2026-09-23)

Four live calls against `POST /api/alpha/decisions`, all HTTP 200.

| Probe | Result |
|---|---|
| `noul` semantics | P(yes) confirmed: topic shift 0.96 on an obvious shift vs 0.06 on an obvious continuation |
| Latency | 282–589 ms end to end, 4 questions, ≈ 750 input tokens |
| Cost | ≈ $0.00003 per call, output billed at 0 |
| pt-PT route: "prepara o email de lançamento" | marketing, p 0.80, confidence 0.77 |
| pt-PT route: a question about a test | dev, p 1.0 |
| pt-PT: "corrige aquilo" | route none, p 0.79; vagueness score level 3, p 0.95 |
| `provider.data_collection: deny` | accepted; effect not observable |

The measured latency sits inside the 1.5 s hook ceiling. The route cap
is 1000 ms: live telemetry on 2026-09-23 measured 462–589 ms per call,
and three calls were cut on `timeout` at 638 ms under the former 600 ms
cap, so 600 ms was cutting real calls. 1000 ms clears every call measured
so far. bash-effect moved to 1000 ms on 2026-09-23 after its first
telemetry: replay p50 910 ms, and 2 of 4 live calls cut at 606 ms. Both
rely on the cache and on fallback when the cap is hit.

### Operator decisions (2026-09-23)

1. **Transport: OpenRouter only** (`OPENROUTER_API_KEY`, alpha endpoint).
   No direct typesafe.ai transport, no LiteLLM route.
2. **All 22 sites in this campaign.**
3. **Jev mandatory everywhere**, `act` by default, for cost and quality.

### Recorded dissent (`arkaos-not-yes-man`) and how the design absorbs it

| Objection | Absorption |
|---|---|
| "Mandatory" cannot mean "no fallback". Hooks must exit 0; Synapse targets < 100 ms; an alpha endpoint returning 429/529 must not stop a turn. | Mandatory = every site in `act` by default and Jev consulted on every decision. The current heuristic is the **unavailability** fallback only, every fallback is counted, and a circuit breaker opens on 401/429/529. Remote feature-flag services are run the same way: the flag is mandatory, the service serving it is not a single point of failure. |
| The cost reduction is concentrated in 5 sites, not 22. | Telemetry measures #7 forge-complexity, #10 dispatch-role, #11 qg-prescreen, #18 dreaming-critic and #22 subagent-discipline separately; the other 17 are justified by precision, not cost. |
| pt-PT accuracy is unmeasured. | Each site logs Jev-vs-heuristic agreement; the replay harness is G3 evidence per PR; a site that loses to its heuristic on its corpus is demoted to `shadow` (gate below). |
| 22 sites in one PR will not pass this house's Quality Gate (dev redo-risk 0.15; the Gate Economy campaign shipped 3 defects introduced by fixes). | "All now" is delivered as a continuous campaign of 5 chained PRs without pauses (PR1 foundation + prompt sites, PR2 command + Forge, PR3 governance, PR4 cognition, PR5 consolidation), one release at the end. |
| Diffs, prompts and transcripts leave the machine for a third party. | Egress is mandatory: `core/egress/policy.evaluate(text, "decisions:jev")` runs before any send, and a denial is a fallback, not an error. The OpenRouter account's no-training / no-logging policy for paid models is an operator prerequisite. |

## Decision

Add `core/decisions/`, a **System 1 layer under the System 2 agents**,
with one stdlib (`urllib`) client against the OpenRouter Decisions
endpoint. Sites consult it through `decide(calls, state, *, session_id,
timeout_ms=None, cfg=None, model=None) -> dict[str, Outcome]`, which
never raises; `model` is `decisions.model` from `models.yaml`
(`transport.configured_model()`), None keeping the default.

### Invariants

1. **Not an `LLMProvider`, not a Model Fabric role.** `LLMProvider` is
   text → text (`core/runtime/llm_provider.py`); Jev returns typed
   answers. `config/models.yaml` gains a separate top-level `decisions:`
   block (`transport`, `model`) parsed by `DecisionsModelConfig`, whose
   validators coerce bad values to defaults so a typo never discards the
   whole file (`model_router._read_yaml` returns `None` on any
   `ValueError`).
2. **Never synchronous inside a Synapse layer.** The UPS hook runs a
   `decisions` stage *before* the Synapse bridge and hands the layers a
   precomputed hint (`route_hint`); layers read, they never call out.
   Layer-side caches (#8, #20) are filled by detached workers only.
3. **Never replaces subagents or the Quality Gate.** The QG pre-screen
   (#11) is mandatory but advisory: it never removes a reviewer from the
   dispatch list (`mandatory-qa`). The dispatch-role site (#10) never
   demotes a quality role to `mechanical`.
4. **Escalate-only on governance and destructive sites** (#3, #5, #9,
   #13, #15): Jev may tighten a decision, never loosen one the heuristic
   made.
5. **Always a fallback.** Transport, shape, timeout, egress-denial and
   breaker-open all raise `DecisionUnavailable(reason)` internally; the
   site uses its heuristic (or a no-op where none exists), the reason is
   logged and the hook records `[arka:degraded]`.
6. **Bounded network.** ≤ 1.5 s hard timeout in hooks (1000 ms for route;
   1000 ms for bash-effect since 2026-09-23), 3–5 s in Forge, QG and cognition. The route
   cap sits above what was measured on 2026-09-23: live calls between
   462 and 589 ms, three calls cut at 638 ms under the former 600 ms
   cap, and a p50 of 334 ms over one refine replay run (n = 34). No p95
   is claimed yet; it comes from `stage_ms.decisions` once enough turns
   are on record. Skipped once the hook budget deadline passes; cached; fails open. Recorded in
   `.claude/rules/bash-hooks.md` with Graphify L2.5 as precedent.
7. **Stateless cache.** Key = sha256(model + redacted state + questions),
   24 h TTL; the cache stores answers, never state.
8. **Visible cost.** Every call is appended to
   `~/.arkaos/telemetry/decisions.jsonl` and recorded with
   `record_cost(category="decision")`; `pricing.py` gains a
   `typesafe/jev-1.13` row; `/arka status` gains a Decisions (24h) section
   and `/arka decisions [period]` reports per site.
9. **One call per UPS turn.** The questions of all active prompt sites
   travel in one request (answered in parallel), keyed `<site>__<q>`.
   One bounded exception since PR2: the skill-hints repair call (see
   "PR2" below), inside the same `decisions` stage and budget.

### Modes and thresholds

Per-site modes in `~/.arkaos/config.json` (seeded by the installer, never
overwriting an operator value): `act` (default: bounded synchronous call,
Jev drives the site), `shadow` (detached worker, heuristic drives,
agreement logged, zero hook latency), `off`. Global kill-switch
`ARKA_BYPASS_DECISIONS=1`; no `OPENROUTER_API_KEY` means the stage is not
registered and output is byte-identical to today. Default confidence
thresholds by risk: read 0.60, write 0.75, destructive 0.90.

### The 22 sites

| # | Site | Location today | Heuristic today | Jev question | Risk / direction | PR |
|---|---|---|---|---|---|---|
| 1 | topic-drift | `core/hooks/user_prompt_submit.py` | keyword overlap < 30 % | noul | read | 1 |
| 2 | refine (vague request) | `core/forge/complexity.py`, UPS | additive score ≥ 85 + carve-out | noul + choice {target, scope, acceptance, none} | read | 1 |
| 3 | creation-intent | UPS | bilingual regex, unbudgeted | noul | write, escalate-only | 1 |
| 4 | route (L1) | `core/synapse/layers.py` | regex counts, tie by dict order | choice: 16 departments + none | write (0.70) | 1 |
| 5 | bash-effect | `core/workflow/flow_enforcer.py` | regex blacklist + whitelist | noul `requires_gating` (one question; PR2) | destructive, escalate-only | 2 |
| 6 | forge-departments | `core/forge/orchestrator.py` | 5 keywords | choice; the set of departments with p ≥ 0.20, cap 4; no keyword union | read | 2 |
| 7 | forge-complexity | `core/forge/complexity.py` | fixed weights over regex | 5× score (10 levels → 0–100) | read | 2 |
| 8 | skill-hints (L5) | `core/synapse/layers.py` | substring count | choice top-2, precomputed | read | 2 |
| 9 | ui-in-ts (frontend gate) | `core/workflow/frontend_gate.py` | content regex, WARN-only | noul | write, escalate-only | 3 |
| 10 | dispatch-role | `core/runtime/model_router.py` | manual | choice over the 7 roles | write; never quality → mechanical | 2 |
| 11 | qg-prescreen | between `qg_tier` and the QG dispatch | none | choice verdict + choice blocker | advisory; never skips reviewers | 3 |
| 12 | slop-score | human-writing skill (prose only) | none in code | 5× score 1–10 → `slop-score` evidence section | minor | 3 |
| 13 | sycophancy | `core/governance/sycophancy_detector.py` | regex ladder | noul | write, escalate-only | 3 |
| 14 | learning-signal | `core/governance/learning_detector.py` | 3 regex families | choice {explicit, implicit, none} | write | 3 |
| 15 | phantom-action | `core/governance/phantom_action_check.py` | verb + object regex | noul | write, escalate-only | 3 |
| 16 | skill-proposer | `core/governance/skill_proposer.py` | `hint_count < 2` | noul | read | 3 |
| 17 | redo-risk per diff | `core/governance/routing_feedback.py` | per-department prior | fed by #11 | — | 3 |
| 18 | dreaming-critic | `core/cognition/dreaming.py` | 20-token LLM call + substring | choice {valuable, noise} (0.75) | read; unavailable = reject | 4 |
| 19 | reorganizer-category | `core/cognition/reorganizer.py` | name prefix | choice {pattern, anti-pattern, lesson} | read | 4 |
| 20 | recipe-rerank | `core/synapse/recipe_layer.py` | overlap × decay | relevance score, precomputed; never in the layer | read | 4 |
| 21 | kb-near-duplicate | none | — | noul at ingestion | read | 4 |
| 22 | subagent-discipline | `config/constitution.yaml` (narrative only) | none | noul "needs isolated context"; quality exempt | read | 2 |

Deliberately out of scope (mechanical by design): QG LIGHT/FULL tier,
gate-marker extraction, the ownership table, KB confidence bucketing and
the Forge's affected-file estimate (Jev cannot see the repository).

### Gate shadow → act

`act` is the default, and it must keep earning it. The replay harness
(`core/decisions/replay.py`) runs each site over its corpus
(`config/decisions/corpora/<site>.jsonl`, ≥ 50 % pt-PT, no client names)
and reports Jev vs heuristic precision, split by language. The report is
G3 evidence for the PR that ships the site. A site fails the replay gate,
and is demoted to shadow by Quality Gate decision with the report on
disk, when its Jev precision on the cases it answers is below the
heuristic's precision on the same cases + 5 pp, when its abstain rate
exceeds 25 %, or (escalate-only sites) when false escalations exceed 5 %
of the cases the heuristic already got right. The decision is never made
by opinion. PR5 reruns the replay across all 22 sites and applies the
demotions.

PR1 replay (online, 2026-09-23). Precision on the cases Jev answered,
Jev vs the heuristic on the same cases:

| Site | Corpus n | Answered | Jev | Heuristic | Result |
|---|---|---|---|---|---|
| topic-drift | 34 | 32 | 100.0 % | 65.6 % | pass, `act` |
| creation-intent | 47 | 40 | 97.5 % | 80.0 % | pass, `act` (false escalations 0.0 %) |
| route | 33 | 33 | 90.9 % | 72.7 % | pass, `act` |
| refine | 34 | 33 | 60.6 % | 90.9 % | fail, demoted to `shadow` |

`refine` demoted to shadow on 2026-09-23 (replay: Jev 60.6 % vs
heuristic 90.9 %, n = 34). Caveat: the refine corpus was seeded from the
heuristic's own unit tests, which favours the heuristic; PR5 relabels it
independently before any promotion.

## PR2 — command, Forge and dispatch sites (2026-09-23)

Spec: the PR2 note of 2026-09-23 in the vault (`Projects/ArkaOS/Specs/`,
Paulo's decisions 1–5). Six sites; four `act` by default, the two Forge
sites `shadow` (demoted by the replay gate, below):

| Site | Call site | Heuristic | Output |
|---|---|---|---|
| bash-effect | `flow_enforcer._bash_effect_with_jev` (from `_evaluate_gate`) | `bash_is_effect` | escalate-only: a discovery command may become gated, never the reverse |
| forge-departments | `core/forge/jev_sites.decide_departments` (step 3) | `_estimate_departments` | the Jev set (p ≥ 0.20, cap 4, no keyword union) when it acts; `shadow` since 2026-09-23 |
| forge-complexity | `core/forge/jev_sites.decide_dimensions` (step 3) | `score_dimensions` | five 0–100 scores into `analyze_complexity(dimensions=)`; weights and `determine_tier` untouched; `shadow` since 2026-09-23 |
| dispatch-role | UPS `decisions` stage | `keyword_dispatch_role` | `[arka:dispatch-role] role=<r> p=<p> source=jev\|heuristic`; never quality → economy |
| subagent-discipline | UPS `decisions` stage | `keyword_needs_isolation` | `[arka:subagent-discipline] isolate=yes\|no p=<p> source=jev`; quality dispatches ask nothing |
| skill-hints | UPS `decisions` stage → bridge `skill_hint` → L5 | L5 top-1 keyword command | L5 ranks the hinted registry id first, after a project signal |

**Decision 1 — the Node fast-path stays as it is.** `engine.cjs::decidePre()`
fast-allows discovery commands (~18 ms) without starting Python; asking
Jev there would make the shim delegate every discovery command
(the majority per turn, +300–600 ms each) for a marginal gain: the
whitelist is ~40 read-only tokens and anything unknown is already
default-deny. PR2 therefore consults Jev **only on the Python path**
(commands that reach `flow_enforcer`: effect commands, or discovery
commands while a budget is active or the fast-path is off), under a
1000 ms ceiling the hook enforces itself (an operator `timeoutMs` cannot
raise it). Every Bash line `flow_enforcer` writes to
`~/.arkaos/telemetry/enforcement.jsonl` carries `bash_path: "python"`;
the Node fast-path renders the manifest template, where it stays `""`.
PR5 decides the shim's delegation on those two counts, not on opinion.

**Skill-hints menu.** Jev never sees the 308 commands (the endpoint
caps a choice at 255 options). `core/synapse/command_menu.skill_hint_candidates`
— the one builder the hook and the replay share — returns the top-20
L5 keyword commands, then every command of the routed department,
de-duplicated and capped at 60 (+ `none`), descriptions cut to 160
characters. The routed department is the L1 keyword route in the turn's
single call. When the Jev route moves the prompt to another department
and that first menu yielded no command (not asked, `none`, or unsure),
the stage makes **one** repair call for skill-hints alone over the new
department's menu, bounded by what is left of the same budget; an
unanswered skill question is never repaired. Menu coverage on the
skill-hints corpus: 58.8 % (20/34) with the keyword route, 100 % (34/34)
with the right route. The replay scores the site with the route taken as
correct (`replay_route`: the expected command's department) — it
measures the site's own job; end-to-end coverage is bounded by the route
site (90.9 % in PR1's replay).

**Forge budget (decision 3).** The Forge had no latency primitive.
`core/forge/budget.ForgeBudget` is a monotonic deadline (5 s per step 3)
and `remaining_ms(cap=3000)` bounds each call; the two sites run in
sequence (the complexity question sees the departments the first call
settled on), so the second call gets `min(3000, what is left)`. No call
leaves without a deadline; any fallback keeps the keyword estimates and
the Forge scores exactly as before.

**Two weak baselines, on record.** The replay's offline numbers for the
heuristics Jev replaces: forge-complexity puts all 32 corpus cases
in STANDARD (37.5 % accuracy, the share of STANDARD labels), and
skill-hints' L5 top-1 keyword command is right in 17.6 % of 34 cases.
Beating them is not evidence of quality on its own; the gate still
compares Jev against the heuristic on the same cases + 5 pp.

PR2 replay (online, 2026-09-23). skill-hints with the keyword route only
(no repair): Jev 62.5 % (20 of 32 answered), act accuracy 58.8 % (20 of 34).

| Site | Corpus n | Answered | Jev | Heuristic | Result |
|---|---|---|---|---|---|
| bash-effect | 38 | 33 | 100.0 % | 48.5 % | pass, `act` (abstain 13.2 %, false escalations 0.0 %) |
| forge-departments | 34 | 24 | 70.8 % | 16.7 % | fail (abstain 29.4 % at the 3000 ms ceiling), demoted to `shadow` |
| forge-complexity | 32 | 3 | 66.7 % | 33.3 % | fail (abstain 90.6 %), demoted to `shadow` |
| dispatch-role | 32 | 32 | 100.0 % | 84.4 % | pass, `act` (abstain 0.0 %, false escalations 0.0 %) |
| subagent-discipline | 32 | 25 | 96.0 % | 88.0 % | pass, `act` (abstain 21.9 %) |
| skill-hints | 34 | 34 | 100.0 % | 17.6 % | pass, `act` |

Online replay by Rita on 2026-09-23 with an empty cache; heuristic
accuracy is measured on the same answered cases. forge-departments,
forge-complexity and dispatch-role were re-run 2026-09-23 after the
question/corpus edits, each with its own empty cache and breaker
directory (`ARKA_DECISIONS_CACHE_DIR`); unavailable calls count as
abstentions: 2 timeouts for forge-complexity, none for dispatch-role.

Those runs capped every call at a fixed 5 s, above the ceilings the live
sites use. forge-departments was therefore re-run once more at the
Forge's real 3000 ms per-call cap (`--timeout-ms 3000`, own cache and
breaker): 6 of 34 calls were cut at 3 s, abstain rose to 29.4 % (> 25 %),
and the site failed the gate although Jev was right on 70.8 % of the 24
cases it answered vs the keyword estimate's 16.7 % (p50 561 ms). What
follows from the ceiling: the question is right more often than the
heuristic, but too slow for the budget, so forge-departments ships in
`shadow` and the Forge keeps its keyword estimate; promotion waits for a
call that fits 3 s. Since this run the replay caps each call at the
site's own `timeout_ms` by default (`--timeout-ms` overrides it), so a
replay measures the call the live site would make. The bash-effect,
dispatch-role, subagent-discipline and skill-hints rows above were
measured at the fixed 5 s and are not yet re-validated at their own
ceilings (1000 ms and 1500 ms). The skill-hints row carries a caveat:
`replay_route` builds the menu from the expected command's department,
so the replay accuracy is an isolated upper bound, not the live routing
condition.

**Ceiling re-validation: not on record after two attempts.** Two re-runs
on 2026-09-23 tried to measure the live sites at their own ceilings, and
both measured the endpoint, not the sites. The first, on the four PR2
`act` sites above, hit an overloaded endpoint (HTTP 529, then the
breaker). The second ran at ~21:25 local on route, topic-drift,
creation-intent, refine and forge-departments, each with its own empty
cache and breaker directory and `--timeout-ms` at the site's live
ceiling, on a machine at load average 6.8 on 16 cores. bash-effect,
dispatch-role, subagent-discipline and skill-hints were not in it.

| Site | Ceiling | n | Unavailable | Jev abstained | Answered | Jev on answered | Heuristic, same cases | p50 (calls sent) | Gate |
|---|---|---|---|---|---|---|---|---|---|
| route | 1000 ms | 33 | 14 | 0 | 19 | 89.5 % | 73.7 % | 557 ms | fail (abstain 42.4 %) |
| topic-drift | 1500 ms | 34 | 27 | 0 | 7 | 100.0 % | 85.7 % | 1114 ms | fail (abstain 79.4 %) |
| creation-intent | 1500 ms | 47 | 40 | 2 | 5 | 80.0 % | 80.0 % | 1501 ms | fail (abstain 89.4 %; precision below +5 pp on 5 cases; false escalations 0.0 %) |
| refine | 1500 ms | 34 | 20 | 0 | 14 | 57.1 % | 85.7 % | 712 ms | fail (abstain 58.8 %; precision below the heuristic, consistent with the PR1 demotion) |
| forge-departments | 3000 ms | 34 | 26 | 1 | 7 | 71.4 % | 14.3 % | 504 ms | fail (abstain 79.4 %) |

Abstain is (unavailable + Jev abstained) / n. The report's `abstain_rate`
covers both; `unavailable` counts only the cases no call answered, so Jev
abstained = abstain_rate × n − unavailable.
Derived from `replay-r4/<site>.json` (`abstain_rate`, `unavailable`,
`jev_accuracy`, `heuristic_on_answered`, `p50_latency_ms`, `timeout_ms`,
`gate`; n is the sum of `by_lang.*.cases`).

In all five runs the breaker opened on three consecutive timeouts
(`backoff-<site>.json`: `{"reason": "timeout"}`), and the remaining cases
were counted unavailable (`backoff:timeout`) without a call. Three
probes of the endpoint in the same 25 minutes, one-question payload and
an 8 s client timeout: at 21:33, 29 of 30 answered (1 timeout), p50
2588 ms, p90 3560 ms, 12 under 1000 ms; at 21:43, 20 of 20, p50 649 ms,
p90 4553 ms, 13 under 1000 ms; at 21:46, 15 of 20 (5 timeouts), p50
354 ms, p90 4362 ms, 9 under 1000 ms. About half answered under
1000 ms (34 of 70); the p90 sat between 3.5 and 4.6 s and the slowest
answer took 6.7 s. At 13:40 the same day the smoke test got answers
in 282–589 ms. On the cases Jev did answer, the ordering matched the
PR1 and PR2 replays for every site: Jev above the heuristic on route,
topic-drift and forge-departments, below it on refine, and
creation-intent inconclusive on 5 answered cases.

Modes are therefore unchanged and rest on the PR1 and PR2 measurements
above. The abstain gate measures availability at a point in time; the
precision gate measures quality. A demotion needs a run that measured
the site, not an endpoint outage, and neither re-run was one. Under an
endpoint in this state, `act` costs this: each hook call waits up to its
ceiling, three consecutive timeouts open the breaker for 60 s, the
heuristic answers meanwhile, and every fallback is counted
(`reason=timeout` in the hook tag, `backoff:timeout` in the replay).
That is the designed degradation, bounded by the UPS budget. The
session showed it live: the UserPromptSubmit hook emitted
`[arka:route-confidence] dept=ops source=keyword reason=timeout` at 21:45
and `dept=dev p=0.93 source=jev` at 21:47.

Carried to PR5: (a) re-validate the seven `act` sites at their ceilings
on a day the one-question probe's p90 sits under 1000 ms, before the
PR5 demotion pass; (b) split `unavailable` in the replay report by
reason (timeout, http-5xx, backoff, egress), so a run can tell an
endpoint outage from a Jev abstention. Today it cannot: this record had
to lean on `backoff-<site>.json` and an external probe; (c) when (b)
lands, write the rule "a demotion needs a run that measured the site"
into the gate text itself (the shadow → act gate paragraph above and
`replay.py`). Today it lives only in this narrative.

`forge-complexity` demoted to shadow on 2026-09-23 by the replay gate
(re-run: Jev 66.7 % vs heuristic 33.3 % on the 3 cases it answered,
abstain 90.6 %, n = 32). With the threshold at zero (measured on the
first run only) the tier accuracy was 43.8 % vs 37.5 %: the weakness is
in the answers, not the threshold.
PR5 relabels the corpus before any promotion. The site stays
registered; it runs in `act` only by operator override
(`decisions.sites.forge-complexity: act` in `~/.arkaos/config.json`),
and in shadow the Forge scores with `score_dimensions` exactly as
before. The same holds for forge-departments
(`decisions.sites.forge-departments: act`).

## Consequences

- Hooks gain one bounded outbound call per turn when a key exists; p95 of
  `stage_ms.decisions` is watched, and the UPS reserves 500 ms of budget
  for the bridge.
- A new data egress path exists; its safety rests on the egress policy,
  applied per state class, and on the operator's OpenRouter data settings
  (security review `docs/security/2026-09-23-jev-decisions-review.md`):
  - `prompt` and `command` state proceeds when the client list is truly
    ABSENT (no file, or exactly `{"clients": []}`): secrets are still
    refused, home paths normalised, the override is written to the egress
    audit (no audit, no send), and the gap is noted once per session in
    `decisions.jsonl` (`site=egress-notice`,
    `reason=redaction-config-missing`). A user with no list has no third
    party to protect; failing closed there only disabled the feature.
  - `diff` and `transcript` state (and any unknown class) stays
    fail-closed without a list, and so does a list that is corrupt,
    unreadable, mis-shaped or a dangling symlink: the operator has a list
    we cannot read, and degrading would ship client names in clear. A
    mixed call is judged by its strictest class
    (`strictest_state_class`), so one diff site keeps the whole request
    fail-closed.
  - The OpenRouter key rides as an unredirected header, and a response
    whose final URL differs from the request is refused
    (`reason=redirected`): urllib used to copy `Authorization` to the
    `Location` host on a 301/302/303, including a downgrade to `http://`.
- `decisions.jsonl` is 0600 and its `state_sha16` is an HMAC keyed by a
  per-install salt (`~/.arkaos/cache/decisions/telemetry.salt`, 0600):
  short prompts are low-entropy, and an unsalted digest confirms a guess.
- A test fixture sets `ARKA_BYPASS_DECISIONS=1` and removes
  `OPENROUTER_API_KEY` suite-wide, because hook tests spawn subprocesses
  that inherit the environment.
- Every heuristic remains in the codebase as a pure function, reachable
  as the fallback and as the replay baseline. Nothing is deleted.
- Open for PR5 (from the PR2 ceiling re-validation): the seven `act`
  sites are not yet measured at their own ceilings on a healthy endpoint
  (re-run when the one-question probe's p90 is under 1000 ms, before the
  demotion pass), and the replay report does not split `unavailable` by
  reason (timeout, http-5xx, backoff, egress); when it does, the rule
  "a demotion needs a run that measured the site" moves from this
  narrative into the gate text and `replay.py`.
- Operator prerequisites: `npx arkaos keys set OPENROUTER_API_KEY <key>`
  and disabling training/logging for paid models on the OpenRouter
  account.

## Alternatives considered

- **Treat Jev as a Model Fabric role / `LLMProvider`** — rejected: the
  provider interface is text → text; forcing typed answers through it
  would reintroduce parsing, the failure mode Jev removes.
- **Route through the LiteLLM gateway** — rejected: the gateway serves
  Anthropic and Ollama chat routes, and the decisions endpoint is not a
  chat route.
- **A small local classifier instead** — rejected for now: no labelled
  corpus exists yet (PR1 builds the first one), and it would violate the
  operator's single-transport decision. The replay corpora keep the
  option open.
- **Shadow by default, promote on evidence** — rejected by the operator
  (`act` by default); absorbed through the demotion gate above.
- **Call Jev from inside Synapse layers** — rejected: network I/O in the
  < 100 ms hot path; the precomputed hint achieves the same effect.
- **One PR for all 22 sites** — rejected: see recorded dissent.

## Open risks

1. ~~**`noul` semantics.**~~ **Closed 2026-09-23:** `noul` is P(yes)
   (0.96 vs 0.06 on an obvious yes/no pair in the smoke test). A unit test
   keeps `interpret_noul` pinned to that reading.
2. **Alpha endpoint.** The shape may change; an unexpected body raises
   `invalid-shape` and falls back.
3. **pt-PT accuracy (open).** Three live pt-PT probes behaved correctly
   (see smoke test evidence), but three cases are not a corpus. Still
   measured per language in replay, with per-site demotion.
4. **UPS latency in `act`.** Up to 1.5 s before the bridge; `remaining_ms`
   reserves 500 ms and the circuit breaker cuts repeated timeouts.
5. **QG chunking.** A FULL-tier QG context (~51k tokens) exceeds the 32k
   state limit; the pre-screen chunks per file and caps hunks.
6. **Data-policy flag (partially closed).** The endpoint accepts
   `provider: {"data_collection": "deny"}` (HTTP 200), so the client
   sends it on every call. Whether it takes effect cannot be observed in
   the response, so the account-level no-training / no-logging policy
   remains the floor and an operator prerequisite. `zdr` was not probed.
