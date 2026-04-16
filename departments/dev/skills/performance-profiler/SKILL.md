---
name: dev/performance-profiler
description: >
  Performance profiling with bottleneck identification, before/after measurement,
  optimization checklists, and load testing guidance.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent]
---

# Performance Profiler — `/dev performance-profiler`

> **Agent:** Andre (Backend Dev) | **Framework:** DORA, Web Vitals, APM Best Practices

## Golden Rule: Measure First

```
WRONG: "I think the N+1 query is slow, let me fix it"
RIGHT: Profile -> confirm bottleneck -> fix -> measure again -> verify improvement
```

## Profiling Workflow

| Step | Action | Output |
|------|--------|--------|
| 1 | Establish baseline | P50, P95, P99 latency + RPS + error rate + memory |
| 2 | Identify bottleneck | Flamegraph, slow query log, or heap snapshot |
| 3 | Apply single fix | One change at a time to isolate causation |
| 4 | Re-measure | Same conditions as baseline |
| 5 | Compare delta | Before/after table with % improvement |
| 6 | Document | Before/after in PR description |

## Quick Wins Checklist

### Database
- [ ] Missing indexes on WHERE / ORDER BY columns
- [ ] N+1 queries (check query count per request)
- [ ] SELECT * when only 2-3 columns needed
- [ ] No LIMIT on unbounded queries
- [ ] Missing connection pool (new connection per request)

### Backend
- [ ] Sync I/O in hot path (readFileSync, blocking calls)
- [ ] JSON parse/stringify of large objects in loops
- [ ] Missing caching for expensive computations
- [ ] No compression (gzip/brotli) on responses
- [ ] Serial awaits that could be parallel (Promise.all)

### Frontend Bundle
- [ ] Moment.js -> dayjs or date-fns
- [ ] Full lodash -> individual imports
- [ ] Static imports of heavy components -> dynamic imports
- [ ] Images not optimized or not using next/image
- [ ] No code splitting on routes

### API
- [ ] No pagination on list endpoints
- [ ] No Cache-Control headers
- [ ] Fetching related data in loop instead of JOIN / eager load
- [ ] Missing HTTP/2 or CDN coverage

## Profiling Tools by Stack

| Stack | CPU | Memory | Database | Load Test |
|-------|-----|--------|----------|-----------|
| Node.js | `--prof` + flamegraph | `--inspect` heap snapshot | `EXPLAIN ANALYZE` | k6 |
| Python | py-spy flamegraph | tracemalloc | `EXPLAIN ANALYZE` | locust |
| Go | pprof CPU profile | pprof heap | `EXPLAIN ANALYZE` | k6 |
| PHP/Laravel | Clockwork / Telescope | Blackfire | `EXPLAIN ANALYZE` | Artillery |

## Performance Budgets

| Metric | Budget | Enforcement |
|--------|--------|-------------|
| P95 API latency | < 200ms | CI gate with k6 |
| P99 API latency | < 1000ms | Alerting threshold |
| DB queries per request | < 10 | N+1 detection in tests |
| JS bundle (gzipped) | < 300KB | Webpack budget plugin |
| First load (3G) | < 1.5s | Lighthouse CI |

## Common Pitfalls

| Pitfall | Why It Fails |
|---------|-------------|
| Optimizing without measuring | You fix the wrong thing |
| Testing with dev data | 10 rows vs millions = different bottlenecks |
| Ignoring P99 | P50 looks fine while P99 is catastrophic |
| Premature optimization | Fix correctness first, then performance |
| Not re-measuring after fix | Cannot verify improvement without delta |
| Load testing production | Use staging with production-size data |

## Proactive Triggers

Surface these issues WITHOUT being asked:

- N+1 query detected → flag database performance
- Bundle size >500KB → flag load time impact
- No CDN for static assets → flag latency for global users

## Output

```markdown
## Performance Profile: <Target>
### Baseline: | Metric | Value | Budget | Status |
### Root Cause: [what profiler revealed]
### Fix Applied: [what changed]
### After: | Metric | Before | After | Delta |
### Recommendations: | Priority | Action | Expected Impact |
```
