---
name: performance-audit
description: >
  Performance audit against Google/industry budgets: Core Web Vitals (LCP,
  INP, CLS), API latency percentiles, database query analysis (EXPLAIN
  ANALYZE, N+1, indexes), caching strategy, and infrastructure (CDN,
  compression) — outputs prioritized fixes. TRIGGER: "performance audit", "o
  site está lento", "core web vitals", "lighthouse", "API lenta", "queries
  lentas", "/dev performance". SKIP: iterative measure-fix-remeasure work on
  one bottleneck -> dev/performance-profiler (deep-dive; this is the broad
  audit); SLO and alerting design -> dev/observability.
---

# Performance Audit

> **Agent:** Carlos (DevOps) + Vasco (DBA)
> **Standards:** Core Web Vitals (Google), SLO best practices

## Performance Targets

### Frontend (Core Web Vitals)
| Metric | Target | What |
|--------|--------|------|
| LCP | < 2.5s | Largest Contentful Paint |
| INP | < 200ms | Interaction to Next Paint |
| CLS | < 0.1 | Cumulative Layout Shift |
| JS Bundle | < 300KB gzipped | Total JavaScript |
| First Load | < 1.5s on 3G | Time to usable |

### Backend (API)
| Metric | Target |
|--------|--------|
| p50 latency | < 100ms |
| p95 latency | < 500ms |
| p99 latency | < 1000ms |
| Error rate | < 0.1% |

### Database
| Metric | Target |
|--------|--------|
| Query p95 | < 50ms |
| N+1 queries | 0 |
| Missing indexes | 0 on queried columns |
| Connection pool | Properly sized |

## Audit Steps

1. **Frontend:** Lighthouse audit, bundle analysis, CWV measurement
2. **API:** Response time profiling per endpoint, error rate check
3. **Database:** `EXPLAIN ANALYZE` on slow queries, index review, N+1 detection
4. **Caching:** Cache hit rates, TTL appropriateness, stale data risk
5. **Infrastructure:** CDN coverage, compression (gzip/brotli), HTTP/2

## Output: Performance Report with actionable fixes and priority ranking
