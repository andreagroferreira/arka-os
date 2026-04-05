# Multi-Agent Architecture Patterns — Deep Reference

> 5 patterns with decision criteria, anti-patterns, scaling characteristics, and failure modes.

## Pattern Decision Matrix

| Criterion | Single | Supervisor | Swarm | Hierarchical | Pipeline |
|-----------|--------|-----------|-------|-------------|----------|
| Task complexity | Low | Medium | High (emergent) | High (structured) | Medium (sequential) |
| Agents needed | 1 | 2-10 | 5-50+ | 10-100+ | 3-10 |
| Coordination overhead | None | Low | High | Medium | Low |
| Fault tolerance | None | Supervisor is SPOF | High | Medium | Low (chain breaks) |
| Debuggability | Easy | Medium | Hard | Medium | Easy |
| Latency | Lowest | Medium | Variable | Higher | Sum of stages |

## Pattern 1: Single Agent

**Structure:** One agent handles all tasks end-to-end.

```
User --> [Agent] --> Result
              |
         [Tool 1] [Tool 2] [Tool 3]
```

**When to use:**
- Task scope is narrow and well-defined
- Fewer than 5 tools needed
- No parallelism benefit
- Latency is critical

**Real-world examples:** Code review bot, customer FAQ responder, log summarizer.

**Anti-patterns:**
- Agent has 10+ tools (cognitive overload, poor tool selection)
- Agent handles both planning and execution (conflated responsibilities)
- Agent needs expertise in multiple unrelated domains

**Scaling limit:** Degrades when context window fills or tool count exceeds 5-7.

**Failure modes:**

| Failure | Symptom | Mitigation |
|---------|---------|------------|
| Context overflow | Truncated reasoning, lost instructions | Summarize intermediate results |
| Tool selection errors | Wrong tool called | Reduce tool count, improve descriptions |
| Single point of failure | Total task failure | Retry with backoff |

## Pattern 2: Supervisor (Hub-and-Spoke)

**Structure:** One coordinator delegates to specialized workers.

```
User --> [Supervisor]
            |
    +-------+-------+
    |       |       |
 [Worker] [Worker] [Worker]
```

**When to use:**
- Tasks decompose into independent subtasks
- Need centralized quality control
- Workers have distinct specializations
- 2-10 workers

**Real-world examples:** ArkaOS department leads, customer support routing, document processing with specialists (OCR agent, NLP agent, validation agent).

**Anti-patterns:**
- Supervisor does work instead of delegating (bottleneck)
- Workers communicate directly bypassing supervisor (untracked state)
- Single supervisor for 20+ workers (coordination overload)

**Scaling:** Linear with worker count until supervisor becomes bottleneck (~10-15 workers). Fix with hierarchical pattern.

**Failure modes:**

| Failure | Symptom | Mitigation |
|---------|---------|------------|
| Supervisor bottleneck | High latency, queued tasks | Add worker-level autonomy |
| Bad task decomposition | Workers receive incomplete context | Structured handoff schema |
| Worker failure | Subtask missing from result | Retry policy, fallback workers |

## Pattern 3: Swarm (Peer-to-Peer)

**Structure:** Agents communicate directly, no central coordinator.

```
[Agent A] <---> [Agent B]
    ^               ^
    |               |
    v               v
[Agent C] <---> [Agent D]
```

**When to use:**
- Problems require emergent solutions
- No single agent can plan the full solution
- High parallelism needed
- Fault tolerance is critical (no SPOF)

**Real-world examples:** Distributed code review (each agent reviews different aspects), brainstorming systems, adversarial debate architectures.

**Anti-patterns:**
- No termination condition (infinite loops)
- No shared state schema (agents talk past each other)
- All agents have identical capabilities (no specialization benefit)
- No conflict resolution mechanism (contradictory outputs)

**Scaling:** Scales well horizontally but communication complexity grows O(n^2). Use topic-based pub/sub to reduce.

**Failure modes:**

| Failure | Symptom | Mitigation |
|---------|---------|------------|
| Infinite loops | Never-ending agent conversations | Max iteration count, convergence check |
| State divergence | Agents working on stale information | Shared state with version vectors |
| Deadlock | Agents waiting on each other | Timeout-based resolution |
| Emergent chaos | Unpredictable outputs | Guardrails on each agent, output validation |

## Pattern 4: Hierarchical (Tree)

**Structure:** Multiple levels of supervisors forming an organizational tree.

```
            [Executive]
           /           \
    [Manager A]     [Manager B]
    /    \           /    \
[W1]  [W2]      [W3]  [W4]
```

**When to use:**
- Large-scale systems with 10+ agents
- Natural organizational decomposition (departments, teams)
- Different abstraction levels needed (strategy vs execution)
- Need both autonomy and oversight

**Real-world examples:** ArkaOS full system (CTO > Leads > Specialists), enterprise workflow automation, large codebase refactoring.

**Anti-patterns:**
- Too many hierarchy levels (>3 for most systems, latency compounds)
- Managers that just pass messages (no value-add at each level)
- No skip-level communication for urgent issues
- Rigid hierarchy when tasks cross organizational boundaries

**Scaling:** Best for large systems. Add branches, not depth. Keep depth at 2-3 levels maximum.

**Failure modes:**

| Failure | Symptom | Mitigation |
|---------|---------|------------|
| Communication overhead | Slow responses, garbled context | Structured handoff contracts |
| Middle management bloat | Layers that add latency without value | Audit each level's contribution |
| Cross-branch coordination | Tasks that need agents from different branches | Ad-hoc squads, matrix overlay |
| Cascade failure | Manager failure kills entire branch | Fallback managers, worker autonomy |

## Pattern 5: Pipeline (Sequential Chain)

**Structure:** Agents process data in a fixed sequence.

```
[Input] --> [Stage 1] --> [Stage 2] --> [Stage 3] --> [Output]
             Extract       Transform      Validate
```

**When to use:**
- Processing has a natural sequential order
- Each stage has a clear input/output contract
- Stages are independently testable
- Data transformation workflows

**Real-world examples:** RAG pipeline (chunk > embed > retrieve > rerank > generate), CI/CD pipeline, content moderation (detect > classify > action).

**Anti-patterns:**
- Stage needs output from a non-adjacent stage (breaks linearity)
- Stages are tightly coupled (can not test independently)
- No error handling between stages (silent failures propagate)
- Pipeline too long (>7 stages, latency compounds)

**Scaling:** Scale individual stages independently. Bottleneck is the slowest stage. Use queues between stages for buffering.

**Failure modes:**

| Failure | Symptom | Mitigation |
|---------|---------|------------|
| Stage failure | Pipeline halts | Dead letter queue, skip with default |
| Bottleneck stage | Throughput limited by slowest stage | Scale that stage, add parallelism |
| Schema mismatch | Stage receives unexpected input format | Strict contracts, validation between stages |
| Error propagation | Bad output from stage N corrupts N+1 | Validation gates between stages |

## Pattern Selection Checklist

Use this checklist to narrow down the right pattern:

- [ ] How many distinct agent roles are needed? (1 = Single, 2-10 = Supervisor, 10+ = Hierarchical)
- [ ] Is the workflow sequential or parallel? (Sequential = Pipeline, Parallel = Supervisor/Swarm)
- [ ] Is there a natural coordinator? (Yes = Supervisor, No = Swarm)
- [ ] How important is fault tolerance? (Critical = Swarm, Standard = Supervisor)
- [ ] What is the latency budget? (Tight = Single/Pipeline, Flexible = Hierarchical)
- [ ] How debuggable must the system be? (High = Pipeline/Single, Medium = Supervisor)

## Hybrid Patterns

Most production systems combine patterns:

| Hybrid | Structure | Example |
|--------|-----------|---------|
| **Supervisor + Pipeline** | Supervisor delegates to pipelines | ArkaOS workflow phases |
| **Hierarchical + Swarm** | Tree structure with peer collaboration at leaf level | Department leads + specialist brainstorming |
| **Pipeline + Supervisor** | Pipeline stages contain supervisor-worker teams | ETL where transform stage has multiple workers |

## Token Handoff Cost

| Pattern | Tokens per Handoff | Handoffs per Task | Total Overhead |
|---------|-------------------|-------------------|----------------|
| Single | 0 | 0 | 0 |
| Supervisor | 200-500 | 2-5 | 400-2500 |
| Pipeline | 300-800 | N stages | 300N-800N |
| Hierarchical | 200-500 | 2-3 per level | 400-1500 per level |
| Swarm | 100-300 | Unpredictable | High variance |

Rule of thumb: If total handoff overhead exceeds 30% of useful work tokens, simplify the architecture.
