# ArkaOS Benchmarks

Contributor guide to the benchmark harness: what each measurement covers, how to run it, what is deterministic, and how to extend the routing set.

For the published numbers that accompany a release see [../wiki/11-Benchmarks.md](../wiki/11-Benchmarks.md). That page is generated; this one explains the methodology behind it.

---

## What is Measured

The harness (`scripts/bench/harness.py`) runs three independent benchmarks via `run_all()`. Each is accessible individually for debugging.

### 1. Synapse Injection Latency — `bench_synapse_latency`

Measures the end-to-end cost of running the Synapse engine once, from calling `engine.inject(ctx)` to receiving a `SynapseResult`. The engine-under-test is created with `create_default_engine()` and no vector store, so L3.5 (KnowledgeRetrieval) and L2.5 (KBContext) are registered but return empty results immediately.

Two measurement series are taken:

- **Cold**: Before each run the cache is fully cleared with `engine.clear_cache()`. Every layer that can compute computes from scratch.
- **Warm**: One priming call is made before the series. Layers with `cache_ttl > 0` serve from cache; uncacheable layers still recompute every time.

The small delta between cold and warm is expected. Only a subset of the 12 registered layers have `cache_ttl > 0` (L0: 300s, L2: 30s, L5: 30s, L6: 60s, L7: 3600s, L7.5: 60s). Layers without TTL — L1, L2.5, L2.6, L4, L8, L9 — recompute unconditionally and dominate total cost.

The test context (`PromptContext`) is fixed:
- `user_input`: `"fix the authentication bug in the login controller"`
- `cwd`: `/tmp/project`
- `git_branch`: `feat/auth`
- `project_name`: `demo`
- `project_stack`: `laravel 11`
- `active_agent`: `backend-dev`

The `injection_profile` field in the result records how many layers were computed (non-empty result), how many were skipped (empty result), and the estimated token count of the combined context string.

**Timing note:** results are machine-relative. The same code on Apple Silicon M-series runs materially faster than on x86\_64 Linux. The numbers are not comparable across environments; regenerate on your machine before citing them.

### 2. Subagent Handoff Size — `bench_subagent_handoff`

Instantiates a representative `HandoffArtifact` (defined in `core/runtime/subagent.py`) with realistic fields, then measures:

- `measured_tokens`: `len(artifact.to_prompt().split())` — a whitespace-split word count, not a BPE tokenizer count. BPE counts will differ, typically by 10–20% for English prose.
- `prompt_chars`: `len(artifact.to_prompt())` — byte count of the serialised prompt string.
- `documented_claim`: hardcoded `379` — the token claim stated in `subagent.py`'s module docstring.

The benchmark does not assert that `measured_tokens == documented_claim`. The docstring claim predates the `HandoffArtifact` field set. The current measured value (82 word-tokens, 660 chars for the standard representative artifact) is deterministic — it depends only on the hardcoded strings in `harness.py::bench_subagent_handoff`, not on wall-clock time or environment.

**This benchmark is fully deterministic.** Running it twice on the same codebase produces identical numbers.

### 3. Routing Accuracy — `bench_routing_accuracy`

Tests the `DepartmentLayer` (Synapse L1) keyword detector against a fixed labelled prompt set of 12 entries defined in `harness.py::_ROUTING_SET`.

Each entry is `(prompt_string, expected_department_slug)`. The layer's `compute(PromptContext(user_input=prompt))` is called and `result.content` is compared against the expected slug.

The output reports:
- Total prompts in the set.
- Number correct.
- `accuracy_pct` (rounded to one decimal place).
- Per-prompt detail table with expected, detected, and a boolean match flag.

**This benchmark is fully deterministic.** Two successive runs on the same code always produce the same `accuracy_pct`. The set is intentionally small (12 items) and covers one representative prompt per department plus the two known failure cases (SaaS/strategy overlap, content/marketing overlap).

---

## Running the Benchmarks

### Full run (writes output files)

```bash
python scripts/bench/run.py
```

Default: 50 latency samples. Writes:

- `benchmarks/results.json` — machine-readable JSON with environment metadata and all three result objects.
- `benchmarks/results.md` — human-readable Markdown table, the source for `wiki/11-Benchmarks.md`.

### Custom sample count

```bash
python scripts/bench/run.py --runs 100
```

More samples improve the stability of `p50` and `mean` for the latency benchmark. 50 is the default and sufficient for most CI use.

### Print only, no file writes

```bash
python scripts/bench/run.py --runs 30 --no-write
```

Prints JSON to stdout followed by the Markdown table. Useful for quick local checks without dirtying `benchmarks/`.

### Run a single benchmark

```python
from scripts.bench import harness

# Latency only (10 runs)
print(harness.bench_synapse_latency(runs=10))

# Handoff size (deterministic, runs argument ignored)
print(harness.bench_subagent_handoff())

# Routing accuracy (deterministic)
print(harness.bench_routing_accuracy())
```

---

## Output Format

`benchmarks/results.json` has the structure:

```json
{
  "environment": {
    "python": "3.13.13",
    "platform": "macOS-26.5-arm64-arm-64bit-Mach-O",
    "machine": "arm64"
  },
  "results": {
    "synapse_latency": {
      "layer_count": 12,
      "cold_ms": {"runs": 50, "min": 80.695, "p50": 83.995, "mean": 85.38, "max": 100.422},
      "warm_ms": {"runs": 50, "min": 80.219, "p50": 83.225, "mean": 84.515, "max": 98.064},
      "injection_profile": {"layers_computed": 8, "layers_skipped": 4, "tokens_injected": 11}
    },
    "subagent_handoff": {
      "documented_claim": 379,
      "measured_tokens": 82,
      "prompt_chars": 660
    },
    "routing_accuracy": {
      "total": 12,
      "correct": 10,
      "accuracy_pct": 83.3,
      "details": [...]
    }
  }
}
```

`benchmarks/results.md` renders the same data as Markdown tables. Commit both files together when regenerating so the wiki source stays in sync with the JSON.

---

## Current Published Results

Measured on Python 3.13.13, macOS 26.5, arm64 (Apple Silicon). **Timings are machine-relative and will differ on your hardware.**

| Benchmark | Value |
|---|---|
| Synapse registered layers | 12 |
| Cold injection p50 | 83.995 ms |
| Cold injection mean | 85.38 ms |
| Cold injection min/max | 80.695 / 100.422 ms (50 runs) |
| Warm injection p50 | 83.225 ms |
| Layers computed (representative) | 8 of 12 |
| Tokens injected (representative) | 11 word-tokens |
| Handoff measured tokens | 82 word-tokens (660 chars) |
| Handoff documented claim | 379 tokens |
| Routing accuracy | 83.3% (10/12) |

The 82 vs 379 gap on handoff size reflects the compact fields of the standard test artifact. Production handoffs with longer `context_summary` and more `constraints` will produce higher counts.

The two routing misses are known: "create a go-to-market plan for our new SaaS" routes to `strategy` (Porter/growth keywords dominate) and "write viral content hooks for our TikTok channel" routes to `marketing` (TikTok appears in the marketing pattern). These are intentional limitations of keyword counting — see Extending the Routing Set below.

---

## Deterministic vs Machine-Relative

| Benchmark | Deterministic | Notes |
|---|---|---|
| Synapse cold latency | No | Depends on CPU, Python interpreter, OS scheduler |
| Synapse warm latency | No | Depends on CPU, Python interpreter, OS scheduler |
| Injection profile (layers/tokens) | Yes | Fixed prompt and engine config |
| Subagent handoff tokens | Yes | Fixed strings in harness.py |
| Subagent handoff chars | Yes | Fixed strings in harness.py |
| Routing accuracy % | Yes | Fixed prompt set and deterministic regex |
| Routing per-prompt detail | Yes | Fixed prompt set and deterministic regex |

When comparing results across machines or Python versions, only use the deterministic values. Regenerate timings on the target machine.

---

## Extending the Routing Set

`_ROUTING_SET` in `scripts/bench/harness.py` is the authoritative labelled prompt set. To add cases:

1. Open `scripts/bench/harness.py` and find `_ROUTING_SET`.
2. Append a tuple: `("your prompt here", "expected_department_slug")`.
3. Department slugs must match the keys in `core/synapse/layers.py::DEPARTMENT_PATTERNS`: `dev`, `marketing`, `finance`, `ecom`, `strategy`, `ops`, `kb`, `brand`, `saas`, `landing`, `community`, `content`, `pm`, `lead`, `sales`, `org`.
4. Run `python scripts/bench/run.py` and verify the new case appears in the results table.
5. If you are also updating `DEPARTMENT_PATTERNS` to fix a miss, update the set in the same commit so the accuracy number reflects the new patterns.

The set is not exhaustive — it covers one representative case per department and the two known conflict zones. Adding adversarial cases (prompts that should route to department X but share keywords with department Y) is encouraged.

---

## Test Suite

`tests/python/test_bench.py` covers the harness contracts without asserting specific timing numbers:

| Test | What it checks |
|---|---|
| `test_percentiles_summary` | `_percentiles` returns correct keys and values |
| `test_synapse_latency_contract` | Result has `layer_count >= 8`, correct bucket keys, non-negative min |
| `test_subagent_handoff_is_measured` | `measured_tokens > 0`, `prompt_chars > 0`, `documented_claim == 379` |
| `test_routing_accuracy_is_deterministic` | Two successive calls return the same `accuracy_pct` |
| `test_run_all_combines_sections` | `run_all()` returns all three keys |
| `test_render_markdown_includes_all_sections` | Markdown output contains all three section headings |

Run with:

```bash
pytest tests/python/test_bench.py -v
```

No fixtures are required beyond a standard Python environment with `core/` importable.

---

Related: [CORE-ENGINE.md](CORE-ENGINE.md) | [ARCHITECTURE.md](ARCHITECTURE.md) | [../wiki/11-Benchmarks.md](../wiki/11-Benchmarks.md)
