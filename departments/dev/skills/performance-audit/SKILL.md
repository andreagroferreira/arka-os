---
name: dev/performance-audit
description: >
  Performance audit covering Core Web Vitals, API latency, database queries,
  and caching strategy. Targets and budgets based on Google/industry standards.
allowed-tools: [Read, Bash, Grep, Glob, Agent, WebFetch]
---

<!-- arka:kb-first-prefix begin -->
## KB-First Research (non-negotiable)

Before any external research (Context7, WebSearch, WebFetch, Firecrawl):

1. Call `mcp__obsidian__search_notes` on the query first.
2. Cite relevant hits with `[[wikilinks]]` or explicitly declare a KB gap.
3. Only after (1) and (2) may external tools run.

The Synapse L2.5 layer pre-injects top KB matches on every user prompt;
treat them as your default source. External research supplements, it
does not replace the vault.
<!-- arka:kb-first-prefix end -->

# Performance Audit — `/dev performance <target>`

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
