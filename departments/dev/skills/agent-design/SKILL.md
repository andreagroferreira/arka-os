---
name: dev/agent-design
description: >
  Design multi-agent architectures with role definitions, communication patterns,
  tool schemas, guardrails, and evaluation frameworks.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent]
---

# Agent Design — `/dev agent-design <system>`

> **Agent:** Paulo (Dev Lead) | **Framework:** Multi-Agent Architecture Patterns

## Architecture Patterns

| Pattern | When to Use | Tradeoff |
|---------|------------|----------|
| **Single Agent** | Simple, focused tasks with clear boundaries | Easy to debug, but no scalability |
| **Supervisor** | Hierarchical decomposition, centralized control | Clear command chain, but supervisor bottleneck |
| **Swarm** | Distributed problem-solving, peer-to-peer | High parallelism, but hard to predict |
| **Pipeline** | Sequential processing with specialized stages | Clear data flow, but rigid ordering |
| **Hierarchical** | Complex systems with organizational layers | Natural org mapping, but communication overhead |

## Agent Role Definition Checklist

For each agent, define:

- [ ] **Identity** -- name, purpose statement, core competencies
- [ ] **Responsibilities** -- primary tasks, decision boundaries, success criteria
- [ ] **Capabilities** -- required tools, knowledge domains, processing limits
- [ ] **Interfaces** -- input/output formats, communication protocols
- [ ] **Constraints** -- security boundaries, resource limits, operational guidelines

## Agent Archetypes

| Archetype | Purpose | Key Behavior |
|-----------|---------|-------------|
| **Coordinator** | Orchestrate workflows, allocate resources | High-level decisions, conflict resolution |
| **Specialist** | Deep expertise in one domain | High-quality output, narrow scope, clear handoffs |
| **Interface** | Handle external interactions | Protocol translation, auth management |
| **Monitor** | System health and compliance | Metrics, anomaly detection, audit trails |

## Tool Design Principles

| Principle | Rule |
|-----------|------|
| Input validation | Strong typing, required vs optional params |
| Output consistency | Standardized response format, structured errors |
| Idempotency | Safe reads, repeatable writes, version tracking |
| Error handling | Graceful degradation, exponential backoff, circuit breakers |

## Communication Patterns

| Pattern | Mechanism | Best For |
|---------|-----------|----------|
| **Message Passing** | Async queues, pub/sub, broadcast | Decoupled agents, high throughput |
| **Shared State** | Central store, eventual consistency | Read-heavy workloads, collaborative knowledge |
| **Event-Driven** | Event sourcing, stream processing | Audit trails, real-time reactivity |

## Guardrails and Safety

| Layer | Controls |
|-------|----------|
| **Input** | Schema enforcement, content filtering, rate limiting, auth |
| **Output** | Content moderation, consistency validation, audit logging |
| **Human-in-the-Loop** | Approval workflows, escalation triggers, override mechanisms |

## Memory Patterns

| Type | Purpose | Strategy |
|------|---------|----------|
| **Short-term** | Current task context | Context windows, session state, caching |
| **Long-term** | Persistent knowledge | Durable storage, experience replay, consolidation |
| **Shared** | Cross-agent learning | Synchronized access, permission-based partitioning |

## Failure Handling

- [ ] **Retry** -- exponential backoff with jitter, max attempts, transient vs permanent classification
- [ ] **Fallback** -- graceful degradation, alternative approaches, safe defaults
- [ ] **Circuit breaker** -- failure rate monitoring, open/closed/half-open states, cascading prevention

## Design Process

1. Requirements analysis -- goals, constraints, scale
2. Pattern selection -- choose architecture from table above
3. Agent design -- define roles using checklist
4. Tool architecture -- design schemas with error handling
5. Communication design -- select message patterns
6. Safety implementation -- build guardrails per layer
7. Evaluation planning -- define success metrics
8. Deployment strategy -- plan scaling and failure handling

## Proactive Triggers

Surface these issues WITHOUT being asked:

- Single agent handling 5+ tools → suggest supervisor pattern
- No error recovery in agent design → flag resilience gap
- Agent with filesystem + network access → flag security boundary risk

## Output

```markdown
## Agent System Design: <System Name>

### Architecture
- **Pattern:** <selected pattern>
- **Rationale:** <why this pattern fits>

### Agents
| Agent | Role | Tools | Interfaces |
|-------|------|-------|-----------|
| ... | ... | ... | ... |

### Communication
- **Pattern:** <message passing / shared state / event-driven>
- **Handoff contract:** <fields passed between agents>

### Guardrails
- **Input:** <validation rules>
- **Output:** <filtering rules>
- **Human gates:** <approval checkpoints>

### Evaluation Metrics
- Task success rate target: >X%
- Latency budget: <Xms per stage>
- Cost ceiling: <$ per task>
```
