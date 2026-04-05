---
name: dev/agent-workflow
description: >
  Design production-grade multi-agent workflows with pattern selection,
  handoff contracts, failure handling, and cost/context controls.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent]
---

# Agent Workflow — `/dev agent-workflow <workflow>`

> **Agent:** Paulo (Dev Lead) | **Framework:** Workflow Orchestration Patterns

## Workflow Pattern Map

| Pattern | Shape | When to Use |
|---------|-------|------------|
| **Sequential** | A -> B -> C | Strict step-by-step dependency chain |
| **Parallel** | Fan-out / Fan-in | Independent subtasks, merge results |
| **Router** | Dispatch by intent | Type-based routing with fallback |
| **Orchestrator** | Planner + specialists | Complex tasks with dynamic dependencies |
| **Evaluator** | Generator + gate loop | Quality validation with retry cycles |

## When to Use Multi-Agent Workflows

- [ ] A single prompt is insufficient for the task complexity
- [ ] You need specialist agents with explicit boundaries
- [ ] You want deterministic workflow structure before implementation
- [ ] You need validation loops for quality or safety gates

If none are checked, a single well-structured prompt is likely enough.

## Handoff Contract Design

Every edge between agents must define:

| Field | Description | Example |
|-------|------------|---------|
| `source_agent` | Who produces the output | `researcher` |
| `target_agent` | Who consumes the output | `writer` |
| `payload_schema` | Typed fields in the handoff | `{ summary: string, sources: url[] }` |
| `max_tokens` | Context budget for this handoff | `2000` |
| `validation` | Output check before handoff | `schema_valid && length > 100` |
| `timeout_ms` | Max wait before failure | `30000` |
| `retry_policy` | Retry count and backoff | `{ max: 3, backoff: "exponential" }` |

## Design Process

1. **Select pattern** based on dependency shape and risk profile
2. **Define agents** -- one clear responsibility per agent
3. **Map edges** -- handoff contracts for every connection
4. **Add gates** -- validation checks between stages
5. **Set budgets** -- token limits, timeouts, cost ceilings per step
6. **Plan failures** -- retry, fallback, and circuit breaker per edge
7. **Dry-run** with small context budgets before scaling

## Common Pitfalls

| Pitfall | Fix |
|---------|-----|
| Over-orchestrating simple tasks | Start with the smallest pattern that works |
| Missing timeout/retry policies | Every external call needs both |
| Passing full upstream context | Send only targeted artifacts in handoffs |
| Ignoring per-step cost accumulation | Set and enforce token budgets per edge |
| No intermediate validation | Validate outputs before fan-in synthesis |
| Rigid patterns for dynamic tasks | Use orchestrator pattern for variable workflows |

## Best Practices

1. Start with the smallest pattern that satisfies requirements
2. Keep handoff payloads explicit and bounded
3. Validate intermediate outputs before fan-in synthesis
4. Enforce budget and timeout limits in every step
5. Log every handoff for observability and debugging
6. Use idempotent operations where possible for safe retries

## Proactive Triggers

Surface these issues WITHOUT being asked:

- Sequential workflow with independent steps → suggest parallelization
- No timeout on agent handoffs → flag hanging workflow risk
- Missing fallback path in router pattern → flag dead-end risk

## Output

```markdown
## Workflow Design: <Workflow Name>

### Pattern
- **Selected:** <pattern>
- **Rationale:** <why this pattern>

### Agents
| Agent | Responsibility | Input | Output |
|-------|---------------|-------|--------|
| ... | ... | ... | ... |

### Flow
```
<ASCII or Mermaid diagram of workflow>
```

### Handoff Contracts
| Edge | Payload | Budget | Timeout | Retry |
|------|---------|--------|---------|-------|
| A -> B | ... | ... | ... | ... |

### Failure Strategy
- **Retry:** <policy>
- **Fallback:** <degradation plan>
- **Circuit breaker:** <threshold>

### Cost Estimate
- Tokens per run: ~<X>
- Estimated cost: ~$<X>
```
