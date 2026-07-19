---
id: ADR-2026-07-19-arkaos-runtime-pivot
title: Runtime Pivot — the six §10 decisions, closed
status: accepted
date: 2026-07-19
deciders: Andre Groferreira (owner), Tomas (Strategy), Marco (CTO), Helena (CFO)
related:
  - docs/strategy/2026-05-27-arkaos-runtime-strategy.md
  - docs/strategy/2026-05-27-arkaos-runtime-swot-viability.md
  - docs/adr/2026-07-04-cost-governor.md
  - docs/adr/2026-04-20-llm-agnostic.md
  - core/runtime/gateway/
---

# ADR — Runtime Pivot: the six §10 decisions, closed

## Status

Accepted — 2026-07-19. Closes the six decisions the runtime strategy
left formally open in §10 (2026-05-27) and unblocks the §11 sequence.
The strategy document's status moves from draft to decided with this
ADR as its record.

## Context

The 2026-05-27 strategy proposed evolving ArkaOS from a skill inside a
single host into a standalone multi-provider agent-OS runtime with BYOK
and enforceable cost governance, and ended with six operator decisions
(§10: A licensing, B first revenue segment, C provider-layer depth,
D CostGovernor enforcement, E Web UI timing, F naming). The companion
SWOT (viability 62/100) gated any advance on three bottlenecks:
co-founder/hire, paid design partners pre-MVP, and a public GitHub
community.

The formal pivot ADR promised by §11 was never written; the pivot
advanced piecemeal instead. By decision time, practice had already
answered two of the six: the CostGovernor shipped opt-in (ADR
2026-07-04) and a single-user Web dashboard shipped and passed the
Quality Gate. This ADR records the operator's decisions of 2026-07-19
(taken in block over the decision brief of 2026-07-18) — four new
decisions and two ratifications of shipped practice.

## Decisions

| § | Decision | Choice | Kind |
|---|---|---|---|
| A | Licensing | **A2 — open-core**: core OSS, enterprise features closed | decided 2026-07-19 |
| B | First revenue segment | **B2 — ICP-2 small teams as paid design partners, pre-MVP** | decided 2026-07-19 |
| C | Provider layer | **C1 consolidated — LiteLLM as the meta-provider**, keeping the existing direct Anthropic path; direct providers added only on measured caching/latency wins | decided 2026-07-19 |
| D | CostGovernor enforcement | **D2 — enforcement opt-in by config** | ratification (shipped, ADR 2026-07-04) |
| E | Web Control UI | **E2 — single-user Web UI** | ratification (shipped dashboard) |
| F | Naming | **F5 — "ArkaOS", no suffix**; the pivot is version narrative, not brand narrative | decided 2026-07-19 |

## Rationale (per decision)

- **A2** aligns the licensing line with the security wedge already in
  flight: the scanner ships open for distribution, verification and
  enterprise surfaces are the paid layer. A1 removes every non-hosted
  revenue path; A3 undermines the public-community bottleneck the SWOT
  itself gates on.
- **B2** is simultaneously the decision and the viability test: the
  SWOT's second bottleneck is paid design partners pre-MVP. B1 validates
  usage but not willingness to pay; B3 requires compliance surface that
  does not exist.
- **C1** ratifies the shipped direction — the gateway is already
  LiteLLM-based with mixed and local-only modes — and rejects
  speculative provider engineering: a direct top-5 provider is added
  only when cost telemetry shows a measurable win.
- **D2/E2** are ratifications, recorded with their real dates: practice
  decided them before this document did, and pretending otherwise would
  falsify the record.
- **F5** keeps one brand over a 30K-user install base and npm equity; a
  post-traction rename fragments recognition against larger-audience
  competitors. The "Core"/"Cloud" split (F3) stays available later if a
  hosted tier ships — it is compatible with A2 and requires no decision
  today.

## Consequences

Unblocked by this ADR (not executed by it):

1. Phase-3 migration roadmap, with ICP-2 requirements driving the MVP
   cut.
2. Design-partner recruitment (5 paid, per B2) — also SWOT bottleneck 2.
3. Public manifesto.

Constraints reaffirmed: the SWOT advance-only-if gates remain in force —
this ADR closes decisions, not viability. Any future change to A–F
supersedes this record through a new ADR, never by editing it.
