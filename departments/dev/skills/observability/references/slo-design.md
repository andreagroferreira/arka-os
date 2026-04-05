# SLO Design Guide — Deep Reference

> SLI/SLO/SLA framework, error budgets, burn rate alerts, and production SLO documents.

## Terminology

| Term | Definition | Owner | Example |
|------|-----------|-------|---------|
| **SLI** (Service Level Indicator) | Quantitative measure of service behavior | Engineering | Request latency p99 |
| **SLO** (Service Level Objective) | Target value for an SLI over a time window | Engineering + Product | p99 latency < 200ms over 30 days |
| **SLA** (Service Level Agreement) | Contract with consequences for missing targets | Business + Legal | 99.9% uptime or service credits |
| **Error Budget** | Allowed amount of unreliability | Engineering | 0.1% of requests can fail per month |

Relationship: SLI measures reality. SLO sets internal targets. SLA sets external commitments. SLO should always be stricter than SLA.

## Step 1: Define SLIs

### SLI Selection by Service Type

| Service Type | Primary SLI | Secondary SLIs |
|-------------|------------|----------------|
| **API / Web Service** | Availability (successful responses / total) | Latency p50/p95/p99, error rate |
| **Data Pipeline** | Freshness (time since last successful run) | Throughput, completeness |
| **Storage System** | Durability (data loss events) | Availability, latency |
| **Batch Processing** | Completion rate within deadline | Processing time, error rate |
| **Streaming** | End-to-end latency | Throughput, ordering guarantees |

### SLI Specification Template

```
SLI Name: API Availability
Definition: Proportion of valid requests served successfully
Good event: HTTP response with status code != 5xx, latency < 1000ms
Valid event: All HTTP requests excluding health checks
Measurement: Load balancer access logs
Aggregation: Rolling 30-day window
```

### Common SLI Mistakes

| Mistake | Problem | Fix |
|---------|---------|-----|
| Using server-side metrics only | Misses client-perceived failures | Measure at the edge/load balancer |
| Counting health checks | Inflates availability numbers | Exclude synthetic traffic |
| Averaging latency | Hides tail latency issues | Use percentiles (p50, p95, p99) |
| Boolean up/down | Too coarse, misses partial failures | Use request-level success ratio |
| No "valid event" filter | Includes bot traffic, attacks | Define what counts as a real request |

## Step 2: Set SLO Targets

### Target Selection Guide

| Availability | Downtime/Month | Downtime/Year | Typical Use Case |
|-------------|---------------|---------------|-----------------|
| 99% (two 9s) | 7.3 hours | 3.65 days | Internal tools, dev environments |
| 99.5% | 3.65 hours | 1.83 days | Non-critical B2B services |
| 99.9% (three 9s) | 43.8 minutes | 8.76 hours | Standard production services |
| 99.95% | 21.9 minutes | 4.38 hours | Important customer-facing services |
| 99.99% (four 9s) | 4.38 minutes | 52.6 minutes | Payment systems, auth services |
| 99.999% (five 9s) | 26.3 seconds | 5.26 minutes | Safety-critical (rarely achievable) |

### Setting Targets Checklist

- [ ] Based on current performance (set SLO at current p10 performance, not aspirational)
- [ ] Aligned with user expectations (survey or infer from behavior)
- [ ] Achievable with current architecture (do not promise what you cannot deliver)
- [ ] Stricter than SLA by at least 0.1% (buffer for reaction time)
- [ ] Different SLOs for different user segments if needed (paid vs free)
- [ ] Reviewed quarterly and adjusted based on data

## Step 3: Calculate Error Budgets

### Formula

```
Error Budget = 1 - SLO target

Example: SLO = 99.9% availability over 30 days
Error Budget = 0.1% = 0.001
Total requests/month = 10,000,000
Allowed failures = 10,000,000 * 0.001 = 10,000 failed requests
```

### Error Budget Policy

| Budget Remaining | Action |
|-----------------|--------|
| > 50% | Normal development velocity, deploy freely |
| 25-50% | Increased caution, review risky deployments |
| 10-25% | Freeze non-critical deployments, focus on reliability |
| < 10% | Emergency mode: only reliability fixes ship |
| Exhausted (0%) | Full deployment freeze until budget recovers |

### Budget Consumption Tracking

```
Daily budget = Error Budget / 30
Burn rate = actual_errors / expected_daily_budget

Burn rate = 1.0: consuming budget exactly as planned
Burn rate > 1.0: consuming faster than sustainable
Burn rate = 10.0: will exhaust 30-day budget in 3 days
```

## Step 4: Configure Burn Rate Alerts

### Multi-Window Burn Rate Alerting

| Alert | Burn Rate | Long Window | Short Window | Severity | Budget Consumed |
|-------|-----------|-------------|-------------|----------|-----------------|
| **Page (SEV1)** | 14.4x | 1 hour | 5 min | Critical | 2% in 1h |
| **Page (SEV2)** | 6x | 6 hours | 30 min | High | 5% in 6h |
| **Ticket** | 3x | 3 days | 6 hours | Medium | 10% in 3d |
| **Ticket** | 1x | 30 days | 3 days | Low | Budget tracking |

### Why Multi-Window?

- **Long window** prevents alerting on brief spikes (high precision)
- **Short window** catches sudden onset (low detection time)
- Both conditions must be true simultaneously to fire

### Alert Configuration Example (Prometheus)

```yaml
# SEV1: 14.4x burn rate over 1h, confirmed by 5min window
- alert: SLOBurnRateCritical
  expr: |
    (
      sum(rate(http_requests_total{code=~"5.."}[1h]))
      / sum(rate(http_requests_total[1h]))
    ) > (14.4 * 0.001)
    AND
    (
      sum(rate(http_requests_total{code=~"5.."}[5m]))
      / sum(rate(http_requests_total[5m]))
    ) > (14.4 * 0.001)
  for: 2m
  labels:
    severity: critical
  annotations:
    summary: "High error burn rate - SEV1"
    budget_impact: "Will exhaust 30-day error budget in 50 hours"
```

## Step 5: Document the SLO

### SLO Document Template

```markdown
# SLO: {Service Name} - {SLI Name}

| Field | Value |
|-------|-------|
| Service | {service name} |
| Owner | {team name} |
| SLI | {definition} |
| SLO Target | {percentage} over {window} |
| SLA (if applicable) | {percentage} with {consequence} |
| Error Budget | {number} per {period} |
| Measurement Source | {logs / metrics / synthetic} |
| Dashboard | {link} |
| Alert Runbook | {link} |

## SLI Definition
Good event: {definition}
Valid event: {definition}
Exclusions: {health checks, synthetic monitoring, etc.}

## Error Budget Policy
{Copy from error budget policy table, customized for this service}

## Review Schedule
- Weekly: error budget consumption in standup
- Monthly: SLO performance review
- Quarterly: SLO target adjustment if needed
```

## Common Mistakes

| Mistake | Why It Hurts | Fix |
|---------|-------------|-----|
| SLO = 100% | Zero error budget, no deployments possible | Start at 99.9%, adjust based on data |
| SLO set without measurement | Cannot track compliance | Implement SLI measurement first |
| Same SLO for all services | Over-invests in non-critical, under-invests in critical | Tier services, different SLOs per tier |
| No error budget policy | SLO exists but nobody acts on it | Define actions per budget threshold |
| Alerting on SLI instead of burn rate | Too noisy (brief spikes trigger) | Use multi-window burn rate alerts |
| SLO not reviewed | Target drifts from reality | Quarterly review cadence |
| SLA stricter than SLO | No reaction time before breach | SLO should be 0.1-0.5% stricter than SLA |
| Too many SLOs per service | Focus diluted, alert fatigue | 1-3 SLOs per service maximum |

## SLO Maturity Model

| Level | Characteristics | Next Step |
|-------|----------------|-----------|
| **0 - None** | No SLIs or SLOs defined | Define 1 SLI per critical service |
| **1 - Measured** | SLIs exist, dashboards built | Set SLO targets based on current performance |
| **2 - Targeted** | SLOs set, error budgets calculated | Implement burn rate alerts |
| **3 - Alerted** | Multi-window burn rate alerts active | Define error budget policy |
| **4 - Managed** | Error budget drives deployment decisions | Automate deployment freeze on budget exhaustion |
| **5 - Optimized** | SLOs reviewed quarterly, drive architecture decisions | Tie SLOs to business KPIs |
