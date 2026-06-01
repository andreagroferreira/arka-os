# Matrix Squads — Missions & Transversal

> Autonomy by Missions, not Departments. Agents keep their home department;
> they are **borrowed** into outcome-owning mission squads and transversal
> platform/enabling squads. KB-grounded in
> [[Autonomia Por Missões (Não Departamentos)]] (Grove/Nubank), Team Topologies
> (Skelton & Pais) and Empowered (Cagan).

## Why
Department silos optimise local metrics; high-performance orgs organise around
**outcomes**. This matrix overlay sits on top of the 17 departments without
moving anyone — it composes existing agents into squads that own an end-to-end
result, with **shared metrics** rather than departmental hand-offs.

## Mission squads (stream-aligned, `squad_type: project`)
Each owns a customer-lifecycle outcome end-to-end with one shared metric.

| Squad | Outcome | Shared metric | Lead |
|---|---|---|---|
| `mission-acquire` | stranger → qualified lead (SQL) | qualified leads/mo, MQL→SQL | Luna (mkt) |
| `mission-activate` | new customer → activated quick-win (48-72h) | time-to-first-value, activation rate | Patricia (CS) |
| `mission-retain` | retain & expand (NRR > 100%) | NRR, churn | Vicente (RevOps) |
| `mission-recover` | win back churned | win-back rate, reactivated revenue | Catarina (Lifecycle) |

## Transversal squads
Available to every department — the org-wide platforms/enablers.

| Squad | Type | Owns | Lead |
|---|---|---|---|
| `transversal-revops` | platform | unified revenue engine (shared metrics, one funnel) | Vicente |
| `transversal-people-org` | enabling | leadership, culture, talent density, org design, OKR alignment | Rodrigo |
| `transversal-governance` | platform/enabling | decision quality, cadence, RACI, premortem, succession | Afonso |

## How they load
`core.squads.loader.load_matrix_squads("squads/")` discovers
`squads/missions/*.yaml` and `squads/transversal/*.yaml`. Like department
squads (`departments/*/squad.yaml`), they are data loaded on demand. Every
member `agent_id` is cross-checked against the agent roster by
`tests/python/test_matrix_squads.py` — a squad can never reference a ghost agent.

## Quality gate
Mission squads set `quality_gate_required: true` (they ship customer-facing
outcomes). Transversal squads set `false` — they are platforms/enablers, not
delivery squads, so the Quality Gate runs on the work they *enable*, not on the
squad itself.

## Matrix rule
Members are `borrowed: true` with `source_department` set — they remain in
their home department squad. A single agent can serve in several missions
(e.g. Patricia leads Activate and serves in Retain/Recover/RevOps). This is the
intended matrix behaviour, not duplication.

## Next (deferred)
- Wire mission/transversal squads into the orchestrator so `/do` can assemble
  the right mission for a request.
- Rituals as skills/hooks (OKR cadence, premortem/postmortem, Leaky-Bucket gate,
  VoC loop, weekly discovery) — PR-4.
