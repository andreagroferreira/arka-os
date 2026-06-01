# 11 · Benchmarks

← [Home](Home.md) · Related: [Competitive Analysis](12-Competitive-Analysis.md) · [Benefits & ROI](13-Benefits-ROI.md)

Every number here is **measured**, not asserted. Regenerate them yourself:

```bash
python scripts/bench/run.py --runs 50
```

That writes `benchmarks/results.json` (machine-readable) and
`benchmarks/results.md` (this data). Timings are machine-relative; routing
accuracy and handoff size are deterministic and will reproduce exactly.

> **Honesty note.** Earlier documentation claimed Synapse injection runs in
> "<1ms". That was never true for the full engine — it described a single
> cached layer, not end-to-end injection. The real measured figures are below.
> ArkaOS documents what it measures.

Reference environment for the numbers shown: Python 3.13, macOS arm64. Your
machine will differ; the methodology will not.

---

## 1. Synapse context injection

The Synapse engine runs **12 layers** on every prompt. Measured over 50 runs,
engine-only (no vector store attached — see the note below):

| Metric | Cold (cache cleared each run) | Warm (cached) |
|---|---|---|
| p50 | **~84 ms** | **~83 ms** |
| mean | ~85 ms | ~85 ms |
| min | ~81 ms | — |
| max | ~100 ms | — |

A representative injection computes 8 layers, skips 4 (skipping is normal —
layers that don't apply to the prompt are cheap no-ops), and injects ~11 tokens
of context.

**Why warm ≈ cold.** The cacheable layers (Constitution, Agent) are a minority
of total compute. Most of the cost is in the layers that must run fresh every
prompt (department detection, branch, command hints), so warming the cache
saves only a few milliseconds. Individual cached layers are genuinely
sub-millisecond; the *engine total* is not.

**Engine-only vs. end-to-end.** These figures measure the engine without a
vector store. With knowledge retrieval (L3.5) attached, end-to-end injection
through the hook bridge is higher — on the order of a few hundred milliseconds —
because it includes a real KB search. Both are honest; they measure different
things. The number that matters for "does this slow me down" is the end-to-end
one, and at a few hundred ms it is imperceptible next to model latency.

## 2. Subagent handoff cost

When the orchestrator hands a task to a specialist, it passes a compacted
**handoff artifact** instead of the full conversation. Measured size of a
representative artifact (a realistic billing-feature task with files,
constraints, and quality criteria):

| Metric | Value |
|---|---|
| Measured artifact | **82 word-tokens** (660 characters) |
| Previously documented claim | 379 |

"Word-tokens" is a whitespace-split estimate, not a BPE tokenizer count (BPE
would be roughly 1.3x higher, so ~105 tokens). Either way, the handoff is
small: a specialist starts work with a tight, purpose-built brief rather than
the entire history. The old "~379" figure was an over-estimate and has been
corrected here.

## 3. Routing accuracy

The `DepartmentLayer` routes a request to a department by keyword detection.
Measured on a fixed 12-prompt labelled set:

**10 / 12 = 83.3%**

| Prompt | Expected | Detected | Correct |
|---|---|---|:--:|
| fix the authentication bug in the login controller | dev | dev | yes |
| refactor the payment service and add unit tests | dev | dev | yes |
| create a go-to-market plan for our new SaaS | saas | strategy | no |
| design a brand identity with logo and color palette | brand | brand | yes |
| write viral content hooks for our TikTok channel | content | marketing | no |
| build a high-converting landing page funnel | landing | landing | yes |
| audit our online store conversion rate | ecom | ecom | yes |
| model our Q3 budget and cash flow forecast | finance | finance | yes |
| run a competitive analysis with Porter's Five Forces | strategy | strategy | yes |
| plan the next sprint and groom the backlog | pm | pm | yes |
| set up an SEO and paid ads growth campaign | marketing | marketing | yes |
| automate our client onboarding with an SOP | ops | ops | yes |

**The two misses are honest and instructive.** "Go-to-market plan for a SaaS"
routed to Strategy rather than SaaS — defensible, since GTM is a strategy
concern. "Viral content hooks for TikTok" routed to Marketing rather than
Content — the keyword overlap between the two departments is real. Keyword
routing is the first pass; the `/do` orchestrator and explicit prefixes
(`/saas`, `/content`) resolve the ambiguous cases. This is why ArkaOS offers
both natural-language routing and explicit commands.

## How to extend the benchmark set

The harness lives in `scripts/bench/`:

- `harness.py` — the three measurements (`bench_synapse_latency`,
  `bench_subagent_handoff`, `bench_routing_accuracy`)
- `run.py` — runs them and writes results
- Add prompts to `_ROUTING_SET` in `harness.py` to grow the routing benchmark.

Tests in `tests/python/test_bench.py` assert the structural contracts and the
deterministic parts (routing accuracy, handoff size) so the harness can't
silently rot.

---

Related: [Competitive Analysis](12-Competitive-Analysis.md) puts these
capabilities next to other tools; [Benefits & ROI](13-Benefits-ROI.md)
translates them into value with stated assumptions.
