# 02 · Core Concepts

← [Getting Started](01-Getting-Started.md) · [Home](Home.md) · Next: [The 13-Phase Flow →](03-The-13-Phase-Flow.md)

Five ideas explain almost everything about how ArkaOS behaves: **departments**,
**agents**, **tiers**, **behavioral DNA**, and the **constitution**. Understand
these and the rest of the system reads naturally.

---

## 1. Departments and squads

A **department** is a permanent team for one business domain — Development,
Brand, Finance, and so on. There are 17 of them (including the cross-cutting
Quality Gate). Each has a **lead agent** who receives the work and orchestrates
the specialists below.

A **squad** is a working team. Two kinds:

- **Department squad** — the permanent lead + specialists for a domain.
- **Project squad** — an ad-hoc, cross-department team assembled for one task.
  Example: "launch a campaign" pulls Ines (Landing), Luna (Marketing),
  Valentina (Brand), and Ricardo (E-Commerce) into one squad.

This is a **matrix structure**: agents belong to a home department but can be
borrowed into project squads. (One agent, `cro-specialist`, is even
permanently shared by E-Commerce and Landing — which is why the repo has 82
agent files but 81 unique agents.)

See [Departments](04-Departments/) for the full roster.

## 2. Agents

An **agent** is a specialist with a name, a role, a department, a set of
frameworks it applies, and a complete behavioral profile. Agents are defined in
YAML at `departments/<dept>/agents/<name>.yaml` and validated by a schema (see
[docs/AGENT-SCHEMA.md](../docs/AGENT-SCHEMA.md)).

Agents are not generic prompts. Paulo (Tech Lead) reasons with Clean
Architecture and DORA metrics; Helena (CFO) reasons with DCF and unit
economics; Tomas (Strategist) reasons with Porter's Five Forces and Blue Ocean.
The framework is part of the agent.

## 3. Tiers

Every agent sits at one of four authority tiers, inspired by flat,
mission-driven org structures (SpaceX, Google, Anthropic):

| Tier | Role | Count | Authority |
|---|---|---|---|
| **0** | C-Suite | 6 | Veto, approve architecture/budget, block release/delivery |
| **1** | Squad Leads | 18 | Orchestrate their squad, decide within their domain, delegate |
| **2** | Specialists | 55 | Implement, review, recommend |
| **3** | Support | 3 | Research, document, validate |

The **C-Suite** (Tier 0) is Marco (CTO), Helena (CFO), Sofia (COO),
Marta (CQO), Eduardo (Copy Director), and Francisca (Tech & UX Director). They
hold veto power and are pulled in whenever a request is strategic,
cross-department, security-sensitive, or financial.

## 4. Behavioral DNA

Every agent carries a profile from four psychological frameworks. It is not
cosmetic — it shapes how agents collaborate, what they prioritize, and how they
push back on each other.

| Framework | What it defines | Example (Paulo, Tech Lead) |
|---|---|---|
| **DISC** | Communication style | D: 85, I: 60, S: 40, C: 75 |
| **Enneagram** | Core motivation and fear | Type 5w6 (Investigator) |
| **Big Five (OCEAN)** | Trait levels, 0–100 | O:88 C:92 E:55 A:65 N:22 |
| **MBTI** | Information processing | INTJ |

A high-D agent pushes for speed; a high-C agent insists on thoroughness. The
productive tension between them is intentional — it produces better outcomes
than a single agreeable assistant. ArkaOS is explicitly **not a yes-man**: when
you're factually or mathematically wrong, it pushes back with evidence and
reference-company citations.

## 5. The constitution

ArkaOS is governed by a constitution (`config/constitution.yaml`) with four
enforcement levels:

| Level | Count | Meaning |
|---|---|---|
| **NON-NEGOTIABLE** | 25 | Hard rules. Cannot be bypassed by any task, runtime, or convenience. |
| **QUALITY GATE** | — | Marta (CQO) + Eduardo + Francisca review every workflow. Binary verdict. |
| **MUST** | 11 | Strong defaults — conventional commits, ≥80% coverage, model routing, etc. |
| **SHOULD** | 8 | Recommended — research-first, self-critique, KB contribution, etc. |

Some non-negotiables you'll feel immediately: **squad-routing** (every request
goes through a department), **mandatory-flow** (the 13-phase flow runs on every
non-trivial request), **mandatory-qa** (nothing ships without the Quality Gate),
**spec-driven** (no code without an approved spec), and **arkaos-not-yes-man**.

---

## How they fit together

```
Constitution governs everything
        |
Department routes the request to a lead (Tier 1)
        |
Lead assembles a squad of specialists (Tier 2/3), each with behavioral DNA
        |
C-Suite (Tier 0) reviews when strategic / cross-dept / security / financial
        |
Quality Gate (Marta + Eduardo + Francisca) approves before delivery
```

Next: [The 13-Phase Flow](03-The-13-Phase-Flow.md) shows this in motion, step
by step.
