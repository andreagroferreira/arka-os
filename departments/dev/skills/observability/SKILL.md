---
name: dev/observability
description: >
  Design observability strategies: SLI/SLO frameworks, golden signals, structured logging, distributed tracing, alerting, and dashboards.
allowed-tools: [Read, Bash, Grep, Glob, Agent]
---

# Observability Design — `/dev observability`

> **Agent:** Paulo (Dev Lead) | **Framework:** Google SRE (SLI/SLO), Golden Signals, RED/USE Methods

## Three Pillars Assessment

| Pillar | Key Questions | Tools |
|--------|--------------|-------|
| **Metrics** | Golden signals covered? RED for services, USE for resources? | Prometheus, Datadog |
| **Logs** | Structured JSON? Correlation IDs? Appropriate levels? | ELK, Loki |
| **Traces** | Distributed tracing enabled? Sampling strategy defined? | Jaeger, Zipkin, OpenTelemetry |

## SLI/SLO Design Checklist

- [ ] Define SLIs per service (latency p50/p95/p99, error rate, throughput)
- [ ] Set SLO targets based on user experience (e.g., 99.9% availability)
- [ ] Calculate error budgets (100% - SLO = budget)
- [ ] Configure multi-window burn rate alerts (1h/6h fast, 3d slow)
- [ ] Document SLA commitments (if customer-facing)

## Golden Signals Matrix

| Signal | What to Measure | Alert Threshold |
|--------|----------------|-----------------|
| **Latency** | p50, p95, p99 response time | p99 > 2x baseline for 5min |
| **Traffic** | Requests/sec, active sessions | Drop > 50% in 5min |
| **Errors** | 5xx rate, exception rate | Error rate > 1% for 5min |
| **Saturation** | CPU, memory, queue depth, connections | > 80% utilization for 10min |

## Structured Logging Standard

```json
{
  "timestamp": "ISO8601",
  "level": "info|warn|error|debug",
  "service": "service-name",
  "trace_id": "uuid",
  "span_id": "uuid",
  "message": "Human-readable description",
  "context": { "user_id": "123", "action": "checkout" }
}
```

**Log level rules:**
- `ERROR` -- Requires immediate attention, action needed
- `WARN` -- Unexpected but handled, review needed
- `INFO` -- Business events (user signup, order placed)
- `DEBUG` -- Development only, never in production

## Alert Design Rules

| Rule | Rationale |
|------|-----------|
| Every alert must be actionable | No alert without a runbook |
| Use hysteresis (different fire/resolve thresholds) | Prevents alert flapping |
| Group related alerts | Reduces notification fatigue |
| Suppress dependent alerts during known outages | Focus on root cause |
| Review alert precision monthly | Target > 90% actionable rate |

## Dashboard Hierarchy

1. **Executive** -- SLO status, error budgets, uptime (5 panels max)
2. **Service Overview** -- Golden signals per service (7 panels max)
3. **Component Detail** -- Per-instance metrics, logs, traces (drill-down)
4. **Debug** -- Full metrics, ad-hoc exploration

## Cost Optimization

- Tiered metric retention (7d full resolution, 90d downsampled, 1y aggregated)
- Log sampling for high-throughput services (keep 100% errors, sample 10% info)
- Tail-based trace sampling (keep slow/error traces, sample healthy ones)
- Monitor cardinality -- alert on metrics exceeding 10K unique label combinations

## Proactive Triggers

Surface these issues WITHOUT being asked:

- Error rate SLO undefined → flag blind alerting
- Logs without correlation ID → flag debugging nightmare
- No dashboard for critical paths → flag invisible failures

## Output

```markdown
## Observability Design: <project>

### Service Inventory
| Service | SLI | SLO Target | Current |
|---------|-----|------------|---------|

### Logging
- Format: [structured JSON / plaintext -- recommendation]
- Missing correlation IDs: [list]
- Level misuse: [list]

### Metrics & Alerts
- Golden signals coverage: [X/4 per service]
- Alert rules: [count] ([actionable %])
- Missing alerts: [list]

### Tracing
- Instrumented services: [X/Y]
- Sampling strategy: [head/tail/adaptive]

### Dashboard Plan
- [Executive | Service | Component] dashboards needed

### Recommendations (priority order)
1. [Most impactful improvement]
2. [Next priority]
3. [Next priority]
```

## References

- [slo-design.md](references/slo-design.md) — SLI/SLO/SLA framework, error budget calculations, and burn rate alert configuration
