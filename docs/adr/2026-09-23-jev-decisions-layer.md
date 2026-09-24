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

The table is derived from `replay-r4/<site>.json` (`abstain_rate`, `unavailable`,
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

**Closed 2026-09-24: carry (a) is on record.** The seven `act` sites of
PR1 and PR2 were replayed at their live ceilings on 2026-09-24,
01:44–01:46 local, each with its own empty cache and breaker directory
(`replay-r7/<site>.json`). The one-question probe at 01:43 answered 20
of 20 with p50 341 ms and p90 455 ms, under the 1000 ms bar carry (a)
set. All seven runs had 0 unavailable and all seven pass:

| Site | Ceiling | n | Answered | Jev on answered | Heuristic, same cases | p50 (calls sent) | Gate |
|---|---|---|---|---|---|---|---|
| route | 1000 ms | 33 | 33 | 90.9 % | 72.7 % | 353 ms | pass, `act` |
| topic-drift | 1500 ms | 34 | 34 | 100.0 % | 64.7 % | 341 ms | pass, `act` |
| creation-intent | 1500 ms | 47 | 40 | 97.5 % | 80.0 % | 364 ms | pass, `act` (false escalations 0.0 %) |
| bash-effect | 1000 ms | 38 | 32 | 100.0 % | 50.0 % | 360 ms | pass, `act` (false escalations 0.0 %) |
| dispatch-role | 1500 ms | 32 | 32 | 100.0 % | 84.4 % | 345 ms | pass, `act` (false escalations 0.0 %) |
| subagent-discipline | 1500 ms | 32 | 25 | 100.0 % | 92.0 % | 357 ms | pass, `act` (abstain 21.9 %) |
| skill-hints | 1500 ms | 34 | 34 | 100.0 % | 17.6 % | 355 ms | pass, `act` |

These are the first measurements of bash-effect, dispatch-role,
subagent-discipline and skill-hints at their own ceilings; their PR2
rows were taken at a fixed 5 s, and the 21:25 run measured route,
topic-drift and creation-intent on an overloaded endpoint. The ordering
of the 21:25 run
held on a healthy endpoint, and the modes stand. The two runs
recorded above remain the record of what an overloaded endpoint does
to `act`. PR2 carries (b) and (c) stay open for PR5: the replay report still
does not split `unavailable` by reason, and the demotion rule still
lives in this narrative only. The no-questions change of PR3 (below)
moves no row of this table or of the PR1 and PR2 tables.

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

## PR3 — governance and quality sites (2026-09-24)

Spec: the PR3 note of 2026-09-23 in the vault (`Projects/ArkaOS/Specs/`,
Paulo's decisions 1–6). It covers eight lines of the table above (9 and
11–17): seven new sites in `core/decisions/sites/governance.py` and
`core/decisions/sites/quality.py`, plus #17, which has no site of its
own. The registry now holds 17 sites. Of the seven new ones, six are
`act` by default; qg-prescreen is `shadow`, demoted by the replay gate
below. The site
declarations (`default_mode`) and the seed (`installer/config-seed.js`)
say the same.

| Site | Call site | Heuristic | Output | Ceiling | State class | Direction |
|---|---|---|---|---|---|---|
| sycophancy | `stop._stop_context` → `_sycophancy_verdict` | `detect_sycophancy(...).is_sycophantic` | flags a turn the regex ladder passed; the signal list gains `jev` | 1200 ms | prompt | escalate-only |
| phantom-action | `stop._stop_context` → `_phantom_verdict` | `find_action_claims` and a tool_use count of 0 | fails a check that passed (`reason=phantom-action-jev`) | 1200 ms | prompt | escalate-only |
| skill-proposer | `stop._stop_context` → `skill_proposer.evaluate(repeatable=)` | the ladder: completion signal, length, `hint_count < 2` | Jev's verdict replaces the ladder when it acts and disagrees (`jev-declined`, or a proposal past the ladder) | 1200 ms | prompt | any |
| learning-signal | `stop._learning_context` (new consumer) | `detect_correction_signal` mode and leverage | `[arka:learned-rule confidence=<p> signal=<s>]` (`p`: the `signal` answer's own confidence), plus Marta's confirmation line when high-leverage | 1200 ms | prompt | any |
| ui-in-ts | `frontend_gate._jev_ui_scope` (PreToolUse) | `is_heuristic_ui_file` | `ui_scope=heuristic` (WARN-only) where the regex said "not UI" | 600 ms | diff | escalate-only |
| qg-prescreen | `core/governance/qg_prescreen.py` CLI, QG step 2.5 | none: `PRESCREEN_NEUTRAL` (`verdict=unknown`, `blocker=none`) | `[arka:qg-prescreen]` marker and `PRESCREEN.json`; advisory; `shadow` by default | 5000 ms per request, 20 s total | diff | advisory, never touches the reviewer list |
| slop-score | `evidence_checks` section `slop-score` (`slop_check.py`) | none: the baseline is no score | five 1–10 scores and a total per changed prose file; minor | 5000 ms per file, 30 s total | diff | advisory-only |

**#17 redo-risk per diff.** No new site and no new wiring in
`routing_feedback`. `record_verdict_label` copies the session's
prescreen envelope (`verdict`, `blocker`, `p`, `source`) from
`PRESCREEN.json` into each QG label (`core/evals/verdict_labels.py`), so
`qg-verdicts.jsonl` pairs the prediction with the real verdict. A skipped
prescreen lands as `source=skipped:<reason>`. L5.5 stays a pure read.

**Decision 1 — the Stop hook gets a budget first.** The runtime kills
Stop at 5 s, and the hook ran its detectors in sequence with no
deadline. `core/hooks/stop_budget.StopBudget` fixes a monotonic deadline
when `main` starts (`ARKA_STOP_BUDGET_MS`, default 3000 ms) and keeps a
500 ms reserve for the local stages that follow. The four Stop sites
travel in ONE `decide()` call, capped at `min(1200 ms, what the budget
has left)`. Below the engine's 50 ms floor (`MIN_CALL_MS`) the call never
reaches the wire, and the telemetry marks it `degraded: budget`. An `act`
site that did not reach Jev is recorded in `hook-degraded.jsonl`
(`decisions-unavailable`). The state is `stop_state`: the closing text,
the user's last message (each capped at 6000 chars between tokens) and
the mechanical tool_use count as a number. The transcript never leaves
the machine.

`_stop_context` runs on every Stop, before the WF-marker check. A turn
with the WF marker asks all four sites. Any other turn asks
learning-signal alone and sends the user's message only, because the
other three sites are consumed inside `_flow_checks`, which runs on
marker turns only. phantom-action is asked only when the count is
exactly 0; with a tool call on record, or no count, nothing is asked and
the check's fail-open verdict stands. skill-proposer is never asked when
the text carries `[arka:trivial]` or `[arka:skill-skip]`, and the bypass
marker wins inside `evaluate` whatever `repeatable` says. The
learning-signal lines ride the same Stop emission as the reviewer
notices: the hook prints one JSON object or none. Enforcement telemetry
gains a `decisions` key (`fallback_used`, `reason`, `acted_on`) only when
the stage is live; every existing field keeps its name and meaning. With
the bypass, every Stop site `off` or no key, the stage reads no config
past the kill-switch, sends nothing and the output is byte-identical.
The bounded-network rule records the Stop call in
`.claude/rules/bash-hooks.md`.

**Decision 2 — privacy by class.** A state's class names what the text
is, not the hook that carries it. Content classes (`diff`) are
fail-closed without the redaction list, whichever hook carries them;
`prompt` and `command` degrade, as PR1's egress decision allows. The
Stop sites send the operator's message and the closing text, so they
are `prompt`. ui-in-ts sends the source of the `.ts`/`.js` file being
written, qg-prescreen a diff and slop-score a prose file: all three are
content, so all three are `diff`. The first draft of PR3 gave ui-in-ts
`command`, and QG round 1 rejected it: on the default install, whose
scaffold is `{"clients": []}`, a non-UI `.ts` Write shipped source code
with client identifiers unredacted, while the same text sent as a diff
was refused. Now, with no list, `privacy.prepare_state` refuses the
ui-in-ts state before the network; the gate keeps the regex's answer
(WARN-only, no network call) and the engine records the fallback as
`reason=egress-denied:redaction-config-missing`. With a list, client
names are redacted in the code sent (`test_frontend_gate_jev.py`:
`test_no_redaction_list_never_reaches_the_network`,
`test_client_names_are_redacted_in_the_sent_code`). For the two QG
reads, `core/governance/jev_advisory` checks this before any call: under `ARKA_BYPASS_DECISIONS=1`, or with no
list (no file, or exactly `{"clients": []}`), both reads skip with
`reason=bypass` or `reason=redaction-config-missing` and make no network
call. A corrupt or unreadable list is not "missing": privacy denies that
one itself, and the caller reports the denial. Since round 7 a `diff`
state must also name a file of an allowlisted type (Decision 2c).

**Decision 2b — a catch-all under the credential detectors (operator,
2026-09-24).** PR3 sends source code for the first time, and every review
round found one more syntactic form of a credential that the precise
detectors of `core/egress/credentials.py` did not know. Round after
round: the PR2 shell forms (security review findings 23–31), then in
PR3 the lane's own review (33), Quality Gate round 1 (38, 39), round 2 (41: prefixed literals, keyword arguments, Go
assignments), round 3 (42: a name inside a quoted string, and 43, the
quadratic scan found while fixing it), round 4 (44: a quoted name
holding a dot; 45: Ruby `||=`, `[:sym] =` and a fetch block), round 5
(47: XML element text and a `.netrc` password) and the round-6 follow-up
(48: relative paths and hashed assets). A precise detector knows
the syntax around a secret, and code has more syntax than a list can
hold. After round 4 the operator decided on a structural answer ("fixes
+ camada catch-all"): a last layer that knows no syntax (finding 46),
modelled on the gitleaks `generic-api-key` rule, a keyword near a value
that looks like a secret. After round 5 the operator widened it ("XML/netrc
+ catch-all sem aspas"): two precise detectors for the shapes of finding
47, and a catch-all that also reads values without quotes. Round 6 found
five majors: a nested `<value>` child under a secret-named `name=` parent
in .NET applicationSettings and Spring, the netrc `account` token, Stripe
`sk_live_` and `rk_live_` keys absent from the vendor vocabulary while
PR3 is the first PR to send `.ts` and `.js` diffs, secrets keyed by a
file path, sent since the round-6 path-words drop (a defect the fix
introduced), and the "20 misses" numeral. They were found by Francisca
(B1, B2), Marta (M-A, M-B) and Eduardo. After round 6 the operator
decided (2026-09-24, "majors + allowlist por tipo de ficheiro") that the
majors are fixed and that the boundary of the `diff` class becomes a
suffix allowlist, with the detectors kept as defence in depth
(Decision 2c). The reason: six rounds, each with a new syntax (a subscript, a setter, a
dotted name, a Ruby block, an XML element, netrc, a nested value), and
gitleaks and trufflehog pair their detectors with path scoping.

- **When it runs.** Only when no precise detector fired on any escape
  layer, so it never changes an existing label. Its label is
  `credential catch-all`.
- **What it refuses.** A line that holds (a) a value that, once a
  leading `NAME=` or `Name: ` label, an auth scheme (`Bearer`) and
  template or format slots are set aside, has at least 10 characters
  with letters plus a digit or an ASCII symbol, and (b) a secret word
  (`password`, `token`, `secret`, `authorization`, `apikey`, …) in a
  name outside that value, not followed by a pointer word in the same
  name (`token_url`, `api.key.id`). The value is a quoted literal or,
  since round 5, a bare token of the text between the quoted literals
  (split on whitespace and on `<` and `>`). The words of a file-path
  literal or bare path token (absolute or relative, finding 48) are
  dropped from the secret-word search:
  they name the file (this closes the Laravel over-refusal of round 5).
- **Bare tokens are gated.** A bare token must also hold a digit AND a
  symbol or both letter cases, or be 20 or more characters long (a
  32-character lowercase hex key). It passes when it is a declared hash
  (`sha512-…`, `h1:…`), code glued to a name (a call, a subscript, a
  bundler's `name$1`) or a value with a secret word inside it; end
  quotes, brackets, a backslash and a diff's sign are trimmed first.
  Nothing inside a quoted literal is read as a bare token. The gate is
  there because the ungated form newly refused 111 real code and doc
  lines (50 in the repo, 14 in the sample, 47 in the Laravel
  boilerplate) against 5 with the gate.
- **What it passes.** A literal that is a whole reference, a
  placeholder, a path, a URL without userinfo, a name
  (`services.stripe.secret`), a regular expression, a call or an
  attribute, a timestamp, or text with whitespace or non-ASCII
  characters. A serialised JSON state is read by its leaves, so the JSON
  quoting of a leaf is never taken for a literal.
- **XML and `.netrc` (finding 47).** Element text (the key a tag or a
  `name=`/`key=` attribute, with CDATA, namespaces and pretty-printed
  values) and a `.netrc` password were sent by every layer, because they
  hold no quoted literal. Two precise detectors now refuse them, labels
  `credential xml element` and `netrc password`. In the same round `priv`
  became a qualifier for `key` (`privKey`); `pub` is not one.
- **Why 10 characters.** Priced by the round-4 sweep of every tracked
  and untracked text file (3,184 files, 600,763 lines) and Francisca's
  83,270 sampled added lines. At 16, the layer alone caught 44 of the
  111 rows of the review history and missed every 14-character password
  fixture (`Tr0ub4dor$3xYz`). At 10 it newly refuses 5 lines of the
  600,763, all test fixtures (two of them synthetic secrets, correctly
  refused), and 0 of the 83,270-line sample. The round-5 sweep, on the
  round-6 input tree (601,165 lines), newly refuses 7 lines against the
  round-5 input: 5 bare-token lines in docs and tests (a regex in a vendored
  test, `$30K/month` twice, a wiki link row, a test comment) and 2 netrc
  rows (the finding-36 canary fixture and the review row quoting it,
  both correct); 0 of the sample; on the Laravel boilerplate (186,459
  lines) 0 newly refused, and 41 hash-manifest lines no longer refused.
  The round-6b sweep, on the round-6b tree (601,318 lines, `credentials.py`
  `377fda65…`), newly refuses 0 lines against the round-6 input and no
  longer refuses 1 (a comment in `credentials.py`); on the sample and on
  the Laravel boilerplate, 0 newly refused and 0 no longer refused.
  The round-7 sweep, on the round-7 tree (601,974 lines, `credentials.py`
  `635eb99d…`), against the round-6b tree: in the repo 1 newly refused
  (the source line of a round-7 fixture that holds a digest's fragments)
  and 4 no longer refused (the m1 policy fixtures); on the sample 0 and
  0; on the Laravel boilerplate 2 newly refused, both the AWS
  documentation example key (a base64 literal with `/`, correctly
  refused by m2).
- **What it catches alone.** With every precise detector switched off,
  it refuses 106 of the 127 history rows (89 of 111 before the bare
  reading and the 16 rows of finding 47), raw and serialised, and
  findings 39, 41, 44 and 45 in full. The 21 it misses are pinned as
  residuals (a)–(g) in `CATCH_ALL_MISSES`, and a precise detector still
  refuses every one: (a) no secret word on the line (14 rows: shell auth
  forms, userinfo URLs), (b) a passphrase with whitespace, (c) a value
  under 10 characters, (d) a quote paired across an apostrophe, (e) a
  `{…}` run read as a slot, (f) a query credential inside a URL, (g) a
  pretty-printed element value, pinned at `prepare_state` too. Below the
  gate, a bare value such as `ENV API_TOKEN abc123def456` reaches no
  precise detector and is sent; it is pinned as a residual as well.
  Round 7 pins two more: (h), which the layer alone sends, a base64
  value read as a path or a name (39 of 2000 random 40-character keys on
  a fixed seed: 34 start with `/`, 3 read as a name, 2 hold no digit),
  and (i), which every layer sends, a hex secret keyed by a path, read as
  a hash manifest (`"auth/secret.key": "<32 hex>"` is refused by no
  detector).
- **Cost and proof.** Linear, proved by a test in CPU time: 4× the text
  (25 → 100 KB) costs at most 8× + 0.05 s on all 13 units, 2× the text
  at the 1 MB cap at most 3× + 0.05 s on three representative units, and
  one form at the cap at most `_CAP_SLOW = 4.0` CPU seconds. Measured
  worst: 0.74 s in the round-4 re-run (1.45 s under coverage), 0.81 s
  in the round-5 re-run (1.60 s under coverage). The former absolute 1 s
  wall-clock bound failed under coverage at 1.47 s. 30 of 30 mutants
  killed in the round-4 re-run, among them three quadratic first drafts,
  killed by the linear-time test (about 16× on a 4× step; the three
  drafts fail in 14–204 s); 27 of 27 in the round-5 re-run; 4 of 4 in
  the round-6b follow-up (relative paths); 14 of 14 in round 7 (11 for
  finding 49, 3 for the allowlist of Decision 2c). Under coverage, since
  round 7 (m3), the cap step runs 250 → 500 KB with a ceiling of
  `_CAP_SLOW / 2 = 2.0` CPU seconds, the same bound per character;
  without coverage it is unchanged. Measured under `--cov=core`: 12.7,
  9.5 and 5.0 s per test on the three cap-step units (500 KB under
  coverage; round 6: 21.5, 15.0 and 8.7 s). Since 2026-09-24
  (post-approval CI fix), the absolute ceilings are scaled by a machine
  factor measured once per session on the runner, capped at 4.0: the
  3.12 CI runner was about 2.3× slower than the operator's machine,
  while the ratio tests, which prove linearity, passed everywhere.
- **Round 7 (finding 49).** The round-6 majors and minors are fixed.
  (B1) `_XML_CARRY` carries a secret-named parent tag across a bounded,
  atomic gap of at most 64 characters to its `<value>` child. (B2) both
  netrc patterns read `(?:password|account)`, and `_NETRC_USAGE` sends a
  token that is a bracketed option list (a CLI usage string is not a
  password). (M-B) a path's words are dropped only when the value next
  to it is a hex digest of 32 or more characters, a declared hash, a
  path or a hashed asset; this leaves residual (i). (m1) `policy`,
  `reset`, `rule`, `rules`, `hint`, `expiry`, `min` and `max`, and their
  suffix forms, are pointer words; `password_reset_token = "<opaque>"`
  stays refused. (m2) `_CATCH_NAME_VALUE`: from 20 characters on, `/`
  and `+` separate a value's name segments only when the value also
  holds a separator outside the base64 alphabet; misses went from 107
  to 39 of 2000, pinned as residual (h). (M-A) the vendor vocabulary
  (`harness_scanner._SECRET_PATTERNS`) gains `Stripe key`
  (`[sr]k_(live|test)_`, 20 or more characters, the gitleaks
  `stripe-access-token` rule) and `Stripe webhook secret` (`whsec_`).
  The pinned Quality Gate set passes (5406 tests).

The trade-off, in one sentence: the deny side is fail-safe, because a
refused state falls back to the site's heuristic, so a false refusal
costs one Jev call, never a leak. The layer sits under the detectors as
a floor: a shape inside residuals (a)–(h), a bare value below the gate,
or a secret shaped like a relative file path (finding 48), that no
precise detector knows is still sent, and residual (i) is sent today by
every layer. For a `diff` state, Decision 2c decides first.

**Decision 2c — the `diff` class is bounded by file type (operator,
2026-09-24; security review finding 50).** Decision 2b is a floor and
cannot prove absence: six rounds each found one more syntax that binds a
secret in a config file. What leaves the machine as `diff` state is now
bounded by what the file is, as gitleaks and trufflehog scope their
detectors by path.

- **The allowlist.** `privacy.DIFF_SOURCE_SUFFIXES`, 36 suffixes:
  `.py .pyi .js .mjs .cjs .ts .tsx .jsx .vue .svelte .php .rb .go .rs
  .java .kt .swift .c .h .cc .cpp .hpp .cs .sh .bash .zsh .sql .css
  .scss .less .html .md .mdx .txt .rst .bats`, matched case-insensitive
  with `\` read as `/`. The boundary covers source code and prose, so
  slop-score's `.md`, `.mdx` and `.txt` stay in.
  Refused: config (`xml`, `properties`, `ini`, `conf`, `cfg`, `yaml`,
  `yml`, `json`, `toml`, `plist`), dotfiles and files with no suffix
  (`.netrc`, `.env`, `Dockerfile`), key material (`pem`, `key`, `crt`,
  `p12`, `jks`), lock files and binaries.
- **Enforcement point 1: `privacy.prepare_state`.** For the `diff`
  class, `_refuse_path_class` runs first, before any secret scan, and
  raises `DecisionUnavailable("egress-denied:path-class")`. The audit
  line has kind `path-class` and label `pathless` or
  `suffix-outside-allowlist`, never the path. Every file the state names
  is checked: the dict's own `path`; each file entry in a list, at the
  top level or one list below (an entry is a dict with `path`, `diff`,
  `content` or `prose`); and both sides of every `diff --git` header
  inside a diff, where an unreadable header refuses. A diff state that
  names no file is refused, a serialised JSON string included: the class
  must name its file. This check is on names only: `prepare_state` has no
  project directory and cannot resolve a link, and its module docstring
  says so and names the consumer-side check below.
- **Enforcement point 2: `qg_prescreen.run_prescreen`.** It runs
  `partition_paths(project_dir, changed)` before `git diff`: a file
  outside the list is never read, never chunked, and is listed in the
  report and `PRESCREEN.json` as
  `skipped_paths: [{path, reason: "path-class"}]`. The reviewer list is
  computed as before.
- **The resolved target is judged (round 8, finding 51).** Consumers
  that read from disk ask
  `jev_advisory.resolved_path_allowed(project_dir, name)`: true only
  when the name passes the allowlist, resolves inside the project and
  outside `.git` (`readable_inside`), the resolved file's name passes
  the allowlist too, and the file, if it exists, is a regular file with
  `st_nlink == 1` (round 9, next bullet). A missing file (a deletion, a
  dangling link) is judged on both names, since nothing is read.
  `partition_paths` uses it, so a symlink or a hard link to a refused
  class is skipped with reason `path-class`; `_untracked_diff` checks it
  again before it reads, and `slop_check.prose_text` checks it before
  either read, returning `("", "path-class")`. Hard links are refused
  for tracked and untracked files alike, because the partition runs
  before git says which is which, and a tracked symlink to a config file
  is skipped too.
- **The name is literal and the target a regular file (round 9, finding
  52).** Three layers. (1) `core/governance/literal_git.py` runs every
  git call that carries a changed-file name: `run()` calls
  `git --literal-pathspecs <args>` with `GIT_LITERAL_PATHSPECS=1` in the
  environment, so `:!x.py` names a file called `:!x.py`, never every
  file but `x.py`. `qg_prescreen._git` (so `file_diff` and the
  `ls-files` probe before `_untracked_diff`) and
  `evidence_checks._git_tracks` and `_added_lines` (so
  `slop_check.prose_text`, security-grep and the typecheck scope) go
  through it. The flag is passed as well as the variable on purpose: a
  git too old for the flag exits non-zero, and no caller reads a
  non-zero exit as a diff; the `ls-files` probe treats only exit 1 as
  untracked, so any other code returns no diff and fails closed.
  (2) `resolved_path_allowed` refuses an existing target that is not a
  regular file (`stat.S_ISREG`: a directory, a FIFO, a socket), then
  requires `st_nlink == 1`; a missing file is still judged on both
  names. (3) A literal pathspec still names a directory's contents, so
  `file_diff` returns a diff only when `literal_git.names_exactly`
  (`git diff --name-only -z base -- name`) lists exactly `[name]`, and
  `prose_text` asks the same when the tracked diff added lines, else
  `path-class`. `qg_prescreen.carry_git_headers` puts the section's
  `diff --git` line at the start of every continuation chunk, and
  `chunk_diff` reserves its room, so each chunk stays within
  `MAX_DIFF_CHARS` and `prepare_state` judges it by the file its lines
  belong to, not by the state's `path`.
- **Producers pass the path.** The prescreen calls
  `ask_chunk(…, path=name)`, slop-score passes the prose file's name,
  and ui-in-ts already carried it. The replay builds the prescreen state
  with the corpus diff's first `diff --git` path, so the corpus row for
  `.github/workflows/ci.yml` is refused, as its live counterpart would
  be skipped; the replay cache keys of qg-prescreen and slop-score
  change.
- **The detectors stay as defence in depth.** The XML, netrc and
  catch-all detectors keep running under the allowlist, because a
  source file can hold config text (an XML string in a `.cs` test, a
  heredoc in a `.sh`). Three mutants, each killed, pin the boundary:
  the allowlist emptied, a pathless state allowed, the prescreen filter
  off (part of the 14 of 14 of round 7). Round 8 adds nine mutants on
  the resolved-target check and two on the `diff --git` header sides,
  11 of 11 killed (security review, round-8 mutation table).

- **Round 7 (history).** Francisca found, and Marta reproduced, a
  bypass of the allowlist (B1): an untracked in-repo symlink with an
  allowlisted suffix (`util.py -> config.yaml`, `notes.md ->
  config.yaml`) passed `partition_paths`, `prose_files` and
  `prepare_state`, which judged the link's name, while `readable_inside`
  followed the link, so the config content left through the prescreen
  and slop-score. The same round found the residual-(i) claim of
  Decision 2b (Eduardo) and four minors: an a-side header mutant that
  survived, the scope of the `privacy.py` docstring, "1 MB units", and a
  residual listed twice in review row 49.
- **Round 8 (decision, 2026-09-24).** The boundary judges the resolved
  target, as described above (security review row 51).
- **Round 8 (history).** Francisca found, and Marta reproduced, that a
  changed-file name reached git as a pathspec (M1):
  `git diff base -- name` and `git ls-files -- name` read `:!x.py` as
  every file except `x.py`, and `resolved_path_allowed` admitted a
  directory. The prescreen's continuation chunks carried no
  `diff --git` header and were sent, and slop-score read a directory's
  config lines. The same round found two test minors (the tracked-branch
  guard of `prose_text` and the `OSError` refusal, both untested) and six
  prose minors.
- **Round 9 (decision, 2026-09-24).** Literal pathspecs on every git
  call that carries a changed-file name, through one shared helper; an
  existing target that is not a regular file is refused; `file_diff` and
  `prose_text` require git to name exactly the file asked for, and every
  chunk carries its `diff --git` line, as described above (security
  review row 52). 10 of 10 mutants killed (round-9 mutation table), the
  pinned Quality Gate set passes (5443 tests), and the round-8 repros,
  re-run, put no config content in any `file_diff`, chunk or
  `prose_text`.
- **Round 9 (fix-forward before merge).** The Quality Gate approved
  round 9; closed before merge: names split on newline only, the
  `ls-files` probe failing closed on any exit but 1, `--relative` in
  `names_exactly`, tests for a file replaced by a directory and for the
  header-carry size cap (Francisca m1-m5), and five prose minors
  (Eduardo).

Rounds 8 and 9 closed three vectors of one shape: the name judged while
something else is read (a symlink or a hard link, a pathspec, a
directory). The invariant is now that the
boundary judges the file that is read, by resolved regular-file
identity and literal name. Row 52 keeps three residuals: a deleted
directory (missing, so the names alone admit it) is caught by layer 3
only; a name git prints differently (`./a.py`) fails `names_exactly`
and loses its advisory read, fail-closed; and a file swapped for a
directory between the check and the read needs a concurrent writer.

The trade-off: a secret in an allowlisted file is still only as safe as
the detectors, a `.txt` or `.md` can hold anything, and a config file
renamed or copied under a source suffix passes the boundary. Row 51
keeps three more residuals: a link swapped between the check and the
read, a hard link on a file system that reports `st_nlink == 1`, and a
future consumer that reads from disk without `resolved_path_allowed`,
which `prepare_state` cannot catch. A false hard-link refusal costs one
advisory file. Refusing a config file costs the site its Jev answer for
that state: it falls back to its heuristic, and the prescreen reads the
files it may send.

**Decision 3 — a prescreen with no heuristic.** Jev is asked for a
verdict (`approved`, `rejected`) and a blocker class (`spellcheck`,
`tests`, `diff-review`, `security`, `lint`, `none`). A confident verdict
decides and is the only thing that can make the site abstain.
`approved` forces `blocker=none`; `rejected` keeps the class when it
clears the threshold, else `none`, and either way reports the class's
own confidence as `blocker_p`. The CLI diffs each changed file against
the merge base (an untracked file against `/dev/null`) and cuts it on
line boundaries into chunks of at most 24,000 chars, each headed
`# file: <name> part k/n` (since round 9 a continuation chunk also
carries its section's `diff --git` line), one request per chunk.
Chunks fold into a file verdict and files into the session verdict by
one rule: any `rejected` wins, with the union of its blocker classes
and the highest `p`; `approved` needs every part approved and keeps the
lowest `p`; anything else is `unknown`. The report's `reviewers` field
is always `dispatch_reviewers(compute_tier(...))`, computed from the
tier alone: LIGHT with a named reviewer gives that reviewer, anything
else gives Eduardo and Francisca. A test pins the list as identical on
every prescreen outcome. The CLI exits 0 on every path and prints one
marker line, `[arka:qg-prescreen] verdict=… blocker=… p=… blocker_p=… source=jev|neutral`
or `[arka:qg-prescreen] skipped reason=…`. `p` is the verdict's own
confidence, `blocker_p` the blocker's (`-` when unknown). In `shadow`,
the default, the line is `skipped reason=shadow`; a
`shadow verdict=…` line appears only if a shadow outcome ever carries
Jev's value, and it is a logged prediction nobody acts on.
`PRESCREEN.json` is written atomically into
`~/.arkaos/quality-gate/<session>/` and is a name the ledger owns
(`reviewer_ledger.PRESCREEN_NAME`), so retention still purges the
directory; it never enters the reviewer pool.
`departments/quality/SKILL.md` step 2.5 runs it after the tier and
before any `Agent()` dispatch, and has Marta paste the marker into each
dispatch prompt as a pointer to where to look first.

**Decision 4 — Windows parity.** `stop.ps1` runs
`core/hooks/stop_governance.DETECTORS`: the skill-proposer, sycophancy,
phantom-action and tool-loop regex detectors. `learning_detector` and
the `core.decisions` modules `stop.py` imports are recorded in
`DEFERRED_IN_PS1` with a reason each: the port has no `StopBudget`, no
decisions telemetry contract and no hook-output surface. A Windows Stop
therefore behaves as one with decisions off. sycophancy and
phantom-action are escalate-only, so Windows loses Jev's additions and
no detection. It also emits no `[arka:learned-rule]` marker, heuristic
or Jev. The parity test's scan now covers `core.decisions.*` imports as
well as `core.governance.*`.

**Decision 5 — escalate-only where a detector gates.** sycophancy,
phantom-action and ui-in-ts only tighten: Jev can add a detection the
regex missed, never clear one it made. `stop._jev_escalated` re-checks
this after the engine: it reads a Jev `True` only. ui-in-ts is asked
only for `.ts`, `.js`, `.mjs` and `.cjs` (`.tsx` and `.vue` are gated
by suffix), only where the regex said "not UI", and returns the
`heuristic` scope, which never denies, even in hard mode.
`_marker_decision` is unchanged. skill-proposer and learning-signal are
`any` because they gate nothing: one produces a proposal file, the
other a marker and a confirmation request. Neither writes memory; saving
a learned rule stays the orchestrator's decision, and Marta's when it is
high-leverage.

**Decision 6 — corpora.** The five classifier corpora come from the
parametrised cases of the detector tests plus new pt-PT cases. Cases can
now carry `context` (phantom-action `tool_uses`, ui-in-ts `path`). The
qg-prescreen corpus holds synthetic diffs labelled `[verdict, blocker]`;
the slop-score corpus holds synthetic prose labelled with five scores in
rubric order. Every corpus meets the validity floor (≥ 30 cases,
≥ 50 % pt-PT). The pt-PT share counts the `lang` tag, and a case is
tagged `pt` only when Portuguese is a full clause or a visible string in
what the site reads; English code with a Portuguese comment fragment,
or a diff with no Portuguese at all, is `en`. Diogo applied this on
2026-09-24 after QG round 1: ten qg-prescreen cases (02, 05, 08, 10, 12,
13, 14, 16, 19, 30) were retagged `en` and six pt cases added (33–38),
leaving 20 of 38 tagged `pt`; ui-in-ts kept `pt` only where the
criterion holds and gained 28 cases (33–60); learning-signal gained
case 35, the live false positive (`conitnua ja tens tudo disponivel`).
After QG round 2 he audited every remaining qg-prescreen `pt` case
against the rule (Portuguese as a full clause in a comment, a docstring
or a visible string): cases 03, 15, 18 and 32 were retagged `en`; 06,
07 and 31 were tightened to full clauses, labels unchanged; eight pt
cases were added (39–46: lint ×2, security ×3, tests ×2, diff-review
×1). The corpus now holds 46 cases, 24 of them `pt` (52.2 %).
After QG round 3 two case texts were corrected to match their labels,
ids, labels and tags unchanged: case 39's docstring now reads "Envia o
email ao destinatário pelo servidor local.", so lint (two unused
imports) is its primary defect; the new send path has no test either,
and the corpus labels lint ahead of tests when both apply, as case 40
shows. Case 36 reads "com pelo menos um ano de conta", which
matches the `>= 1` in its diff; the other 22 `pt` cases were checked
for the same text-against-label mismatch and none was found.

| Site | n | pt-PT | Asks no question | Heuristic, offline |
|---|---|---|---|---|
| sycophancy | 34 | 22 | 0 | 64.7 % |
| phantom-action | 34 | 20 | 3 (`tool_uses` > 0) | 82.4 % |
| skill-proposer | 32 | 18 | 3 (bypass marker) | 87.5 % |
| learning-signal | 35 | 22 | 0 | 82.9 % |
| ui-in-ts | 60 | 31 | 0 | 65.0 % |
| qg-prescreen | 46 | 24 | 0 | 0.0 % (neutral baseline) |
| slop-score | 33 | 22 | 0 | 0.0 % (no baseline) |

Offline replay, 2026-09-24, `ARKA_BYPASS_DECISIONS=1`, exit 0 for all
seven.

### Replay gate for the PR3 sites

`core/decisions/replay.py` gains three rules.

- The five classifier sites (sycophancy, phantom-action, skill-proposer,
  learning-signal, ui-in-ts) take the standing gate: Jev precision on
  the answered cases ≥ the heuristic's on the same cases + 5 pp, abstain
  ≤ 25 %, and false escalations ≤ 5 % on the three escalate-only sites.
  learning-signal is scored on its `signal` only.
- qg-prescreen replays against the neutral baseline, which never
  matches a label. Its gate measures Jev against the label alone: the
  precision rule reduces to Jev ≥ 5 %, and the abstain rule is the one
  that binds.
- slop-score is in `MAE_SITES`: the precision rule is replaced by the
  mean absolute error of Jev's total (5–50) against the labelled total
  on the answered cases, ≤ `MAX_SLOP_MAE = 5.0`, one point per dimension
  on average. Exact five-score agreement is still reported as
  `jev_accuracy`.

**Behaviour change: `no-questions`.** A site that chooses not to ask
(phantom-action with a tool call on record, skill-proposer on a bypass
marker) returns reason `no-questions`. The replay no longer counts that
reason as `unavailable`; the case still counts toward `abstain_rate`.
Effect on the PR1 and PR2 rows: none. No case in their ten corpora asks
an empty question set (checked with `case_state` on 2026-09-24):
subagent-discipline asks nothing only for a quality dispatch, which no
replay state sets, and skill-hints always offers `none`. Their
`unavailable` and abstain figures stand. In PR3 the rule applies to the
3 phantom-action and 3 skill-proposer cases above, which set an abstain
floor of 8.8 % and 9.4 %.

**Online replay (2026-09-24).** Each site ran at its own ceiling with
its own empty cache and breaker directory. All report JSONs live in
`~/.arkaos/quality-gate/<session>/replay-r7/`. The first pass (r7) ran
01:44–01:46 local, one file per site, `replay-r7/<site>.json`: 14
replays, the seven PR3 sites and the seven PR1/PR2 `act` sites below.
Diogo re-ran learning-signal, qg-prescreen and slop-score after changing
how their answers are read (r7b, file times ~02:07; then r7c for
qg-prescreen and slop-score and r7d for slop-score;
`replay-r7/r7b-<site>[.r7c|.r7d].json`). After QG round 1, Diogo re-ran
learning-signal, ui-in-ts and qg-prescreen on their revised corpora (r8,
~05:2x local; the probes around it gave p50 449 and 361 ms, p90 587 and
452 ms): `replay-r7/r8-learning-signal.json`,
`replay-r7/r8-qg-prescreen.json` and `replay-r7/r8-ui-in-ts.json`. His
ui-in-ts run tripped the breaker (10 unavailable); the ui-in-ts r8 row
is Paulo's clean re-run, `replay-r7/r8-ui-in-ts-clean.json`
(0 unavailable; `replay-r7/ui-in-ts-clean.json` is a byte-identical
copy). In r8, learning-signal answered case 35, the live false
positive, `none` at 0.85. After QG round 2, Diogo re-ran qg-prescreen
on the 46-case corpus (r9, file time 06:38,
`replay-r7/r9-qg-prescreen.json`), after a one-question probe
(`replay-r7/r9-probe.json`: 20 of 20 answered, p50 443 ms, p90 843 ms).
After the round-3 corrections to cases 36 and 39, Diogo re-ran
qg-prescreen on the same 46 cases (r10, file time 09:38,
`replay-r7/r10-qg-prescreen.json`), after a one-question probe
(`replay-r7/r10-probe.json`: 20 of 20 answered, p50 298 ms, p90 334 ms,
slowest 367 ms); the offline replay of the same corpus
(`replay-r7/r10-qg-prescreen-offline.json`) keeps the neutral baseline
at 0.0 %.
On 2026-09-24 the r8 reports were briefly copied over the r7 files
`replay-r7/learning-signal.json`, `qg-prescreen.json` and `ui-in-ts.json`;
all three were restored from the session scratchpad copies (`cmp`:
byte-identical) and again hold the r7 data (n 34 / 32 / 32, abstain
0.3235 / 0.4375 / 0.0625). The
one-question probe before the first pass (`replay-r7/endpoint-probe.txt`,
01:43, 20 of 20 answered) gave p50 341 ms, p90 455 ms and a slowest
answer of 816 ms; the probes of the window stayed at p50 318–341 ms and
p90 455–498 ms. Every run in the table had 0 unavailable except one:
r7c of slop-score, with 2. The r9 probe was slower (p90 843 ms), still
far under the 5000 ms ceiling, and r9 had 0 unavailable; the r10 probe
was faster than any earlier one (p90 334 ms), and r10 had 0
unavailable. So these runs measured the sites, not the endpoint.

| Site | Ceiling | n | Unavailable | Jev abstained | Answered | Jev on answered | Heuristic, same cases | MAE (total) | False escalations | p50 (calls sent) | Gate |
|---|---|---|---|---|---|---|---|---|---|---|---|
| sycophancy | 1200 ms | 34 | 0 | 3 | 31 | 100.0 % | 61.3 % | — | 0.0 % | 311 ms | pass, `act` |
| phantom-action | 1200 ms | 34 | 0 | 6 (3 no-questions) | 28 | 100.0 % | 82.1 % | — | 0.0 % | 330 ms | pass, `act` |
| skill-proposer | 1200 ms | 32 | 0 | 3 (all no-questions) | 29 | 100.0 % | 86.2 % | — | — | 338 ms | pass, `act` |
| learning-signal (r7b) | 1200 ms | 34 | 0 | 3 | 31 | 100.0 % | 80.6 % | — | — | 321 ms | pass (abstain 8.8 %) |
| learning-signal (r8) | 1200 ms | 35 | 0 | 3 | 32 | 100.0 % | 81.3 % | — | — | 339 ms | pass, `act` (abstain 8.6 %) |
| ui-in-ts | 600 ms | 32 | 0 | 2 | 30 | 100.0 % | 66.7 % | — | 0.0 % | 310 ms | pass |
| ui-in-ts (r8) | 600 ms | 60 | 0 | 1 | 59 | 100.0 % | 64.4 % | — | 0.0 % | 332 ms | pass, `act` (abstain 1.7 %) |
| qg-prescreen (r7b) | 5000 ms | 32 | 0 | 8 | 24 | 75.0 % | neutral | — | — | 302 ms | pass at the limit (abstain 25.0 %) |
| qg-prescreen (r7c) | 5000 ms | 32 | 0 | 11 | 21 | 76.2 % | neutral | — | — | 311 ms | fail (abstain 34.4 %) |
| qg-prescreen (r8) | 5000 ms | 38 | 0 | 12 | 26 | 69.2 % | neutral | — | — | 325 ms | fail (abstain 31.6 %) |
| qg-prescreen (r9) | 5000 ms | 46 | 0 | 14 | 32 | 71.9 % | neutral | — | — | 462 ms | fail (abstain 30.4 %) |
| qg-prescreen (r10) | 5000 ms | 46 | 0 | 13 | 33 | 72.7 % | neutral | — | — | 289 ms | fail (abstain 28.3 %), `shadow` |
| slop-score (r7b) | 5000 ms | 33 | 0 | 8 | 25 | 0.0 % exact | none | 2.84 | — | 314 ms | pass (abstain 24.2 %) |
| slop-score (r7c) | 5000 ms | 33 | 2 | 7 | 24 | 0.0 % exact | none | 3.00 | — | 334 ms | fail (abstain 27.3 %) |
| slop-score (r7d) | 5000 ms | 33 | 0 | 7 | 26 | 0.0 % exact | none | 2.96 | — | 306 ms | pass (abstain 21.2 %), `act` |

Same derivation as the PR2 ceiling table: abstain is (unavailable + Jev
abstained) / n, and n and the figures come from the report JSONs
named above: rows without a run label from `replay-r7/<site>.json`
(ui-in-ts: the r7 file, n 32), r7b/r7c/r7d rows from
`replay-r7/r7b-<site>[.r7c|.r7d].json`, r8 rows from
`r8-learning-signal.json`, `r8-ui-in-ts-clean.json` and
`r8-qg-prescreen.json`, the r9 row from `r9-qg-prescreen.json`, the
r10 row from `r10-qg-prescreen.json`. A
no-questions case counts as a Jev abstention here (it is not
unavailable). For qg-prescreen, "Jev on answered" is exact agreement on
the `[verdict, blocker]` pair. By language in r9 (`by_lang`), Jev was
right on 87.5 % of the answered `en` cases and 56.3 % of the answered
`pt` cases. It answered 16 of the 22 `en` cases and got 14 right, and
16 of the 24 `pt` cases and got 9 right; these counts are derived from
the two rates and the totals (23 right of 32 answered), since the tool
prints only the rates. In r10 the rates are 88.2 % `en` and 56.3 % `pt`:
15 of 17 answered `en` cases right and 9 of 16 answered `pt` cases
right (24 of 33), derived the same way. For slop-score it is exact
agreement on all five scores, which the gate does not use; the MAE of the 5–50 total
is the gate (≤ `MAX_SLOP_MAE = 5.0`).

Besides Diogo's ui-in-ts r8 run above, three runs are not in the table,
because the code they measured no longer ships (`replay-r7/slop-score.json`,
`learning-signal.json`, `qg-prescreen.json`). They are the record of why
the interpretation changed:

- **slop-score, r7: 33 of 33 abstained** (p50 384 ms, 0 unavailable).
  The site read each dimension's confidence as the probability of the
  single most likely level. Paulo diagnosed it on a cached answer:
  directness 1.58, with cells 0.28 / 0.27 / 0.24 around it. A 10-level
  rubric spreads soft prose over neighbouring levels, so no single cell
  clears the 0.60 read threshold. The rule now
  (`quality.slop_dimension`): the level is `floor(score + 0.5)` in 0..9,
  the score is level + 1, and the confidence is the probability mass
  within ±1 level (`SLOP_WINDOW = 1`: three cells, two at an edge). The
  site abstains only when the mean of the five window confidences is
  below the threshold; a per-dimension floor of 0.3 abstained on 13 of
  33 cached answers, because rhythm is spread flat on most texts.
- **learning-signal, r7: 23 answered, abstain 32.4 %, fail.** Both
  answers had to be confident. Now a confident `signal` decides alone,
  and `high_leverage` is True only when Jev says yes confidently and the
  signal is not `none`; an unsure leverage reads as False
  (`governance._learning_interpret`). It only gates Marta's confirmation
  line, never whether the rule was heard.
- **qg-prescreen, r7: 18 answered, abstain 43.8 %, fail.** Both answers
  had to be confident. Now a confident verdict decides; the blocker is
  optional and carries its own `blocker_p` (`quality._prescreen_interpret`).

**qg-prescreen ships in `shadow`.** Five of its six runs fail the
abstain rule (43.8 % on r7 with the old reading, 34.4 % on r7c, 31.6 %
on r8 over the retagged 38-case corpus, 30.4 % on r9 over the audited
46-case corpus, 28.3 % on r10 after the round-3 text corrections) and
the one that passes, r7b, sits exactly on the 25 % limit. There were
0 unavailable in all six: the abstentions are Jev's own. Under the
current reading, the verdict is not confident at the 0.75 write
threshold on 25–34 % of the corpus, and in r9 and r10 it is right far
less often on `pt` diffs than on `en` ones (56.3 % against 87.5 % in
r9, 56.3 % against 88.2 % in r10). That is a measurement of the site,
so the demotion stands under the PR2 rule. The site declares `default_mode="shadow"`
(`core/decisions/sites/quality.py`) and the seed writes `shadow`
(`installer/config-seed.js`). In shadow the engine detaches the call to
the shadow worker, which logs agreement against the neutral baseline;
the prescreen CLI has nothing to read synchronously and prints
`[arka:qg-prescreen] skipped reason=shadow`. It runs live only by
operator override (`decisions.sites.qg-prescreen: act` in
`~/.arkaos/config.json`). The shadow spool holds at most 8 pending
calls (`SPOOL_MAX_PENDING`), one per chunk: on a diff of more than 8
chunks, the chunks asked while 8 are still pending are not logged.

**slop-score stays `act`.** Two of its three runs with the current
reading pass (r7, with the old reading, abstained on all 33), with an MAE of
2.84 and 2.96 on the 5–50 total, about half a point per dimension. The
run that fails (r7c, abstain 27.3 %) is the one run of the window with
unavailable calls (2); Jev's own abstentions in it were 7 of 33 (21.2 %),
the same as r7d.

**Caveat, overfitting.** The three interpretation rules were chosen
after seeing the r7 answers on the same corpora they were then
re-measured on. The r7b/r7c/r7d numbers are therefore optimistic by an
unknown amount. PR5's relabel pass, on cases the rules have not seen,
covers it before any of these three sites is promoted or kept on this
evidence alone.

**Consumers read each answer's own confidence.** `Outcome.confidence` is
the engine's minimum across a site's answers. Two consumers printed it
as if it were one answer's: the prescreen marker's `p` and the Stop
hook's `[arka:learned-rule confidence=…]`. With an unsure blocker or an
unsure leverage (0.50), a verdict or signal Jev was sure of (0.90)
printed 0.50. Both now read their own answer from `Outcome.answers`:
`p` is the verdict's confidence and `blocker_p` is printed separately
(`-` when there is none); `confidence=` is the `signal` answer's. Tests:
`test_p_is_the_verdict_confidence_and_blocker_p_the_blockers`
(`test_qg_prescreen.py`) and
`test_the_marker_prints_the_signals_own_confidence` (`test_stop_jev.py`),
the second proved by mutation (it fails with the old read).

### Contradictions accepted

- **learning-signal is asked on every Stop.** It is the one Stop site
  consumed on every turn, so whenever a Stop site is live and a key
  exists, each Stop with a user message makes one Jev call, capped at
  1200 ms inside the 3000 ms budget. The cache absorbs repeats; the cost
  measured in PR1 is ≈ $0.00003 per call.
- **slop-score is a model's score, so it is advisory-only.** Severity is
  `minor`: a file below 35/50 gives `passed=False` as a fix-forward
  finding, never a REJECTED. It is also in
  `evidence_checks.ADVISORY_ONLY_CHECKS`, so it can neither fail the
  overall nor lift an `insufficient-evidence` report to `pass`: its pass
  is not executable evidence. It scores the lines a change added to a
  tracked prose file, or the whole untracked file, and the first 12,000
  chars when longer, and it is auto-skipped with spellcheck when no
  prose changed.
- ~~**`SLOP_BANDS` wording is pending Eduardo.**~~ **Closed
  2026-09-24:** the rubric intro and the five dimension questions are
  verbatim from `arka/skills/human-writing/SKILL.md`; the five bands per
  dimension that name the ten score levels are Diogo's wording, reviewed
  by Eduardo, QG r1–r2.
- ~~**`config/claude-agents/marta-cqo.md` is not synced with step 2.5.**~~
  **Closed 2026-09-24:** the agent definition runs the prescreen between
  the tier and the dispatch, as the skill does, with `shadow` as the
  default and the `act` override named.
- **The PR3 interpretation rules were fitted on the corpus that
  measured them** (caveat above). They stand until PR5's relabel pass.
- **The spec asked for a replay against `qg-verdicts.jsonl`.** The
  qg-prescreen and slop-score corpora are synthetic. Real labels
  accumulate from now on, through the prescreen envelope in each QG
  label.
- **The spec gave the chunk cap as 24k tokens.** The code caps a chunk
  at 24,000 chars (`MAX_DIFF_CHARS`), a stricter bound under the 32k
  state limit.

### Consequences and carries

- The Stop hook gains one bounded outbound call per turn when a Stop
  site is live and a key exists. The 5 s runtime ceiling is protected by
  the 3000 ms budget and the 500 ms reserve, not by the endpoint.
- The QG gains an advisory read before dispatch (logged in `shadow` by
  default, live by operator override) and one minor evidence section.
  Neither can change a reviewer, a verdict or the evidence floor.
- The online replay of the seven sites is on record (2026-09-24, table
  above): six pass and stay `act`; qg-prescreen fails the abstain rule
  on five of six runs and ships in `shadow`. `marta-cqo.md` is synced
  with step 2.5.
- Carried to PR5: (a) the relabel pass that tests the learning-signal,
  qg-prescreen and slop-score interpretation rules on cases they were
  not fitted on; (b) the PR5 demotion pass over all 17 registered sites,
  with the "a demotion needs a run that measured the site" rule from
  PR2; (c) promoting qg-prescreen only on a run that passes the abstain
  rule with margin, not at the limit.
- Every state now passes a credential catch-all after the precise
  detectors (Decision 2b, security review findings 46 to 49). A false
  refusal costs one Jev call, never a leak. Residuals (a)–(g) of the
  layer stay open, each covered today by a precise detector; (h) is sent
  by the layer alone, and (i) by every layer (a hex secret keyed by a
  path); a new shape inside them that no detector knows is still sent,
  as is a bare value below the gate (`ENV API_TOKEN abc123def456`), or a
  secret shaped like a relative file path (finding 48).
- A `diff` state leaves only for allowlisted source and prose suffixes
  (Decision 2c, finding 50); anything else is `egress-denied:path-class`,
  and the prescreen lists it in `skipped_paths`. Since rounds 8 and 9 a
  consumer judges the file that is read, by resolved regular-file
  identity and literal name: a symlink, a hard link or a directory that
  is not an allowlisted regular file is skipped as `path-class`, and a
  name reaches git only as a literal pathspec (findings 51 and 52).
- Open, not in this PR: the other top vendors of gitleaks (Google
  `AIza`, Twilio, SendGrid, npm) in the scanner vocabulary, and Stripe
  in `evidence_checks._SECURITY_PATTERNS` (the QG grep).
- Process defect found in round 7, carried to its own issue: the
  SubagentStop capture stored the reviewers' trailing prose without the
  `arka-qgverdict` fence, so `eduardo-copy-21` and `francisca-tech-23`
  entered the ledger with verdict `None`. Until they were re-issued as
  `eduardo-copy-22` and `francisca-tech-24`, the guard read the round-6
  blockers. Round 8 hit it again with prose written after the handback
  (`eduardo-copy-23` and `francisca-tech-25`, re-issued as
  `eduardo-copy-24` and `francisca-tech-26`), so the carried issue must
  cover the post-handback case too.

## Consequences

- Hooks gain one bounded outbound call per turn when a key exists; p95 of
  `stage_ms.decisions` is watched, and the UPS reserves 500 ms of budget
  for the bridge.
- A new data egress path exists; its safety rests on the egress policy,
  applied per state class, and on the operator's OpenRouter data settings
  (security review `docs/security/2026-09-23-jev-decisions-review.md`):
  - `prompt` and `command` state (never file content: ui-in-ts is `diff`,
    PR3 Decision 2) proceeds when the client list is truly
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
  - Secrets are refused in every class by the precise credential
    detectors and, when none of them fires, by the credential catch-all
    (PR3 Decision 2b): a keyword in a name next to a quoted literal, or
    a gated bare token, of 10 or more characters that looks like a
    secret.
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
- Closed 2026-09-24 (from the PR2 ceiling re-validation): the seven
  `act` sites of PR1 and PR2 were measured at their own ceilings on a
  healthy endpoint (probe p90 455 ms, 0 unavailable in every run) and
  all seven pass. Still open for PR5: the replay report does not split
  `unavailable` by reason (timeout, http-5xx, backoff, egress); when it
  does, the rule "a demotion needs a run that measured the site" moves
  from this narrative into the gate text and `replay.py`.
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
