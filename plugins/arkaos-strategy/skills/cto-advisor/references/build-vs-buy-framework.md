# Build vs Buy Decision Framework — Deep Reference

> Companion to `cto-advisor/SKILL.md`. Evaluation criteria, TCO templates, risk matrices, and decision trees.

## Decision Tree

```
START: Does this capability differentiate us from competitors?
  YES --> Is the domain well-understood (low technical uncertainty)?
    YES --> BUILD (core IP, known problem)
    NO  --> BUILD with PROTOTYPE first (validate feasibility before committing)
  NO  --> Does a vendor solution meet >= 70% of requirements?
    YES --> Is vendor lock-in risk acceptable?
      YES --> BUY
      NO  --> BUY with ABSTRACTION LAYER (wrap vendor behind interface)
    NO  --> Is this a temporary need (< 18 months)?
      YES --> BUY cheapest option, plan to revisit
      NO  --> BUILD (no vendor fits, long-term need)
```

## Evaluation Criteria Matrix

| Criterion | Weight | Score 1 (Buy) | Score 5 | Score 9 (Build) |
|-----------|--------|---------------|---------|-----------------|
| **Core IP relevance** | 30% | Commodity (auth, email) | Supporting feature | Core differentiator |
| **3-year TCO** | 25% | Buy is 3x cheaper | Comparable | Build is 3x cheaper |
| **Migration risk** | 20% | Easy to switch vendors | Moderate effort | Vendor lock-in is severe |
| **Vendor stability** | 15% | Profitable, public company | Funded startup | Pre-revenue, single founder |
| **Integration effort** | 10% | Drop-in, < 1 week | 2-4 weeks | > 2 months custom work |

### Scoring Template

```markdown
## Build vs Buy: [Capability Name]

| Criterion | Weight | Build Score | Buy Score | Build Weighted | Buy Weighted |
|-----------|--------|:-----------:|:---------:|:--------------:|:------------:|
| Core IP relevance | 30% | _ /9 | _ /9 | _ | _ |
| 3-year TCO | 25% | _ /9 | _ /9 | _ | _ |
| Migration risk | 20% | _ /9 | _ /9 | _ | _ |
| Vendor stability | 15% | _ /9 | _ /9 | _ | _ |
| Integration effort | 10% | _ /9 | _ /9 | _ | _ |
| **TOTAL** | 100% | | | **_** | **_** |

Decision: [BUILD / BUY] — [one-sentence rationale]
```

## Total Cost of Ownership (TCO) — 3-Year Template

### Build TCO

| Cost Category | Year 1 | Year 2 | Year 3 | 3-Year Total |
|---------------|--------|--------|--------|-------------|
| Design and architecture | $ | - | - | $ |
| Development (engineer-months x rate) | $ | $ | $ | $ |
| Infrastructure (hosting, CI/CD) | $ | $ | $ | $ |
| Testing and QA | $ | $ | $ | $ |
| Maintenance (bugs, patches, upgrades) | - | $ | $ | $ |
| On-call and incident response | - | $ | $ | $ |
| Documentation and training | $ | $ | $ | $ |
| Opportunity cost (what else could team build?) | $ | $ | $ | $ |
| **Subtotal** | **$** | **$** | **$** | **$** |

### Buy TCO

| Cost Category | Year 1 | Year 2 | Year 3 | 3-Year Total |
|---------------|--------|--------|--------|-------------|
| License or subscription | $ | $ | $ | $ |
| Implementation and setup | $ | - | - | $ |
| Integration development | $ | $ | $ | $ |
| Data migration | $ | - | - | $ |
| Training (team onboarding) | $ | $ | $ | $ |
| Customization and workarounds | $ | $ | $ | $ |
| Vendor support tier | $ | $ | $ | $ |
| Price increase risk (estimate 10-15%/yr) | - | $ | $ | $ |
| Exit cost (migration away if needed) | - | - | $ | $ |
| **Subtotal** | **$** | **$** | **$** | **$** |

### Hidden Costs Checklist

| Often Missed | Applies to | Typical Impact |
|-------------|-----------|---------------|
| Onboarding new engineers to custom system | Build | 2-4 weeks per hire |
| Vendor API rate limits forcing architecture changes | Buy | 1-3 months rework |
| Security patching and compliance for custom code | Build | 10-20% of dev time |
| Vendor sunset or acquisition (forced migration) | Buy | 3-12 months disruption |
| Feature requests blocked by vendor roadmap | Buy | Lost revenue or workarounds |
| Scaling custom infrastructure beyond initial design | Build | Major refactor |

## Risk Matrix

### Build Risks

| Risk | Probability | Impact | Mitigation |
|------|:-----------:|:------:|-----------|
| Underestimated scope (2-3x initial estimate) | High | High | Prototype first, time-box Phase 1 |
| Key engineer leaves | Medium | High | Document architecture, pair programming |
| Technical debt accumulates | High | Medium | Allocate 20% capacity for maintenance |
| Security vulnerabilities in custom code | Medium | High | Security review, penetration testing |
| Feature creep beyond original scope | High | Medium | Strict ADR governance, MVP discipline |

### Buy Risks

| Risk | Probability | Impact | Mitigation |
|------|:-----------:|:------:|-----------|
| Vendor increases price significantly | Medium | Medium | Contract with price caps, evaluate alternatives |
| Vendor gets acquired or shuts down | Low | Critical | Data export plan, abstraction layer |
| Vendor roadmap diverges from your needs | Medium | High | Evaluate vendor responsiveness, contract SLAs |
| Data portability limitations | Medium | High | Test data export before committing |
| Vendor outage affects your availability | Medium | High | SLA with credits, failover plan |
| Compliance requirements vendor cannot meet | Low | Critical | Verify certifications before purchase |

## Vendor Assessment Checklist

### Must-Have (Dealbreakers)

- [ ] Meets >= 70% of functional requirements
- [ ] API available for integration (no manual-only workflows)
- [ ] Data export capability (no vendor lock-in on data)
- [ ] Compliance certifications you need (SOC 2, GDPR, HIPAA)
- [ ] Uptime SLA >= 99.9% with credits
- [ ] Security practices documented (encryption, access controls)

### Should-Have (Differentiators)

- [ ] Active development (releases in last 90 days)
- [ ] Community or ecosystem (plugins, integrations, forums)
- [ ] Transparent pricing (no "contact sales" for basic tier)
- [ ] Multi-region availability
- [ ] SSO/SAML support
- [ ] Audit logs and admin controls
- [ ] Sandbox/staging environment available

### Red Flags

| Signal | Risk | Action |
|--------|------|--------|
| No public pricing | Enterprise lock-in | Get written pricing with caps |
| No data export feature | Vendor lock-in | Negotiate contractual export rights |
| Single founder, no funding | Business continuity | Escrow agreement for source code |
| No SOC 2 or equivalent | Security gaps | Assess if your compliance requires it |
| API is an afterthought (limited, poorly documented) | Integration pain | Build POC before committing |
| Customer success requires professional services | Hidden cost | Factor into TCO |

## Migration Cost Estimation

### From Build to Buy

| Phase | Effort | Duration |
|-------|--------|----------|
| Vendor evaluation and POC | 1-2 engineers, 2-4 weeks | 1 month |
| Data migration planning and scripting | 1-2 engineers, 2-4 weeks | 1 month |
| Integration development | 2-3 engineers, 4-8 weeks | 2 months |
| Testing and validation | 1-2 engineers, 2-4 weeks | 1 month |
| Cutover and decommission | 1 engineer, 1-2 weeks | 2 weeks |
| **Total** | **5-10 engineer-months** | **4-6 months** |

### From Buy to Build

| Phase | Effort | Duration |
|-------|--------|----------|
| Requirements from vendor feature usage | 1 engineer, 2 weeks | 2 weeks |
| Architecture and design | 1-2 engineers, 2-4 weeks | 1 month |
| Core development (MVP) | 2-4 engineers, 8-16 weeks | 3-4 months |
| Data migration from vendor | 1-2 engineers, 2-4 weeks | 1 month |
| Feature parity (remaining 30%) | 2-3 engineers, 4-8 weeks | 2 months |
| **Total** | **10-20 engineer-months** | **6-9 months** |

## Decision Anti-Patterns

| Anti-Pattern | Why It Fails | Better Approach |
|-------------|-------------|-----------------|
| "We can build it in a weekend" | Maintenance is 80% of lifetime cost | Estimate with 3x multiplier for Year 2-3 |
| "Vendor X is too expensive" | Compare to full build cost, not just license | Calculate 3-year TCO for both |
| "Not invented here" (always build) | Team builds commodity features | Build only what differentiates |
| "Just buy everything" (always buy) | Death by a thousand subscriptions | Own your core IP |
| "Let's build now, buy later" | Migration cost is often higher than starting with buy | Decide once, commit for 2+ years |
| Committee decision with no owner | Endless evaluation, no decision | Assign single decision owner with deadline |

## Hybrid Strategy: Buy + Extend

Sometimes the best answer is neither pure build nor pure buy:

| Pattern | When | Example |
|---------|------|---------|
| Buy + API integration | Core vendor, custom workflows | Stripe + custom billing logic |
| Buy + plugin/extension | Vendor supports extensibility | Shopify + custom app |
| Buy + abstraction layer | Hedge against vendor lock-in | Interface over any email provider |
| Buy + custom UI | Vendor backend, your UX | Headless CMS + custom frontend |
| Open source + self-host | Need control, community does heavy lifting | PostgreSQL, Redis, Grafana |
