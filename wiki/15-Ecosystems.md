# 15 · Ecosystems

← [Home](Home.md)

An ecosystem in ArkaOS is a named group of related client projects that share a dedicated squad, automatic context loading, and compounding knowledge. Instead of treating each repository as an isolated workspace, ArkaOS treats connected projects as one coherent client engagement.

---

## Contents

- [What an ecosystem is](#what-an-ecosystem-is)
- [How context loads automatically](#how-context-loads-automatically)
- [Knowledge that compounds](#knowledge-that-compounds)
- [Overnight insights per ecosystem](#overnight-insights-per-ecosystem)
- [Example ecosystems](#example-ecosystems)
- [Setting up an ecosystem](#setting-up-an-ecosystem)
- [Ecosystem vs. plain project](#ecosystem-vs-plain-project)

---

## What an ecosystem is

A plain project has one directory and one `.arkaos.json`. An ecosystem groups multiple related projects under a shared identity:

- A **dedicated squad** — the same specialist agents are assigned to every project in the ecosystem, so they accumulate context across the work.
- A **project registry** at `~/.arkaos/projects/` with one descriptor per project, linked to the ecosystem name.
- A **shared knowledge space** in Obsidian — all notes from all projects in the ecosystem are filed under the same vault subtree and linked bidirectionally.
- A **domain tag** that the Cognitive Layer uses to scope Dreaming and Research to what matters for that client.

Each ecosystem is identified by a slug:

```
client_retail       → 4 projects (API, frontend, admin, docs)
client_commerce     → 2 projects (supplier sync, Shopify theme)
client_fashion      → 6 projects (CRM, store, API, migration, analytics, mobile)
client_energy       → 3 projects (portal, API, analytics)
```

---

## How context loads automatically

When you `cd` into a project directory, the **CwdChanged hook** fires. It reads the project's `.arkaos.json`, resolves the ecosystem slug, and injects a context block before your next turn. You don't type anything — ArkaOS already knows where it is.

**Example — opening the ClientRetail frontend:**

```bash
cd ~/Work/client-retail-frontend
```

Next prompt, Synapse's Layer 2 (project context) and Layer 3 (ecosystem context) are populated:

```
[arka:context] ecosystem=client_retail project=frontend stack=Nuxt4/TypeScript
[arka:context] related: client_retail_api (Laravel 11), client_retail_admin (Nuxt4)
[arka:context] kb=14 notes loaded (patterns, ADRs, prior decisions)
[arka:context] pending insights=2 (from last Dreaming run)
```

The agent now knows:
- This is a Nuxt 4 / TypeScript frontend.
- The backend API is in a sibling project (`client_retail_api`).
- Fourteen knowledge-base notes are already loaded — no re-explaining needed.
- Two overnight reflections are waiting.

Compare this to starting fresh with no `.arkaos.json`: the agent knows only what it can infer from the files in the directory.

---

## Knowledge that compounds

When work is completed in any project inside an ecosystem, the Auto-Documentor (part of the [Intelligence Loop](07-Intelligence-Loop.md)) writes it back to Obsidian with ecosystem tags. The relator then creates `[[wikilinks]]` between related notes across projects.

**Example chain for ClientRetail:**

```
client_retail_api/auth-pattern.md
  ↔ client_retail_frontend/auth-composable.md
  ↔ client_retail_admin/session-handling.md
```

The next time any agent in the ClientRetail ecosystem touches authentication, all three notes are in context before it starts. A solution developed in the API project informs the frontend implementation automatically.

This is different from copy-pasting documentation by hand. The vault grows relationally — every session adds nodes and edges to a graph specific to that ecosystem.

**Confidence scoring:**

| Maturity | Threshold | Effect |
|---|---|---|
| Emerging pattern | Observed once | Available in KB search |
| Established pattern | Observed 2 times | Surfaced proactively by Synapse |
| Validated pattern | Observed 3+ times | Cited as recommendation; agents default to it |

A pattern validated in `client_fashion` can cross-pollinate to `client_retail` if both ecosystems share a domain tag (e.g., `ecommerce`).

---

## Overnight insights per ecosystem

The Cognitive Layer runs two scheduled jobs every night:

| Job | Time | What it produces |
|---|---|---|
| **Dreaming** | 02:00 | Self-critique, pattern detection, anti-pattern flagging, strategic reflection |
| **Research** | 05:00 | Stack updates, domain news, competitor moves relevant to each ecosystem |

Insights are scoped by ecosystem. ClientEnergy gets infrastructure and compliance intelligence; ClientFashion gets e-commerce, pricing, and Shopify-related updates. An insight for ClientRetail is never surfaced in ClientEnergy's briefing.

**Example — morning briefing when you open a ClientFashion project:**

```
Pending reflections from Dreaming (ClientFashion):

1. [technical] Product sync retry — improve
   Current fixed-interval retry can cause thundering herd under load.
   Exponential backoff with jitter is a validated pattern from client_retail_api.
   Want me to apply it?

2. [business] Offer structure — review
   The pricing table does not account for volume tiers.
   B2B stores with >500 SKUs typically need a different tier model.

Intelligence Briefing (ClientFashion) — stack:
ACTION REQUIRED:
- Shopify breaking change in Webhooks API v2026-04 affects your sync worker.
  Upgrade deadline: 2026-07-01.

OPPORTUNITIES:
- New Shopify bulk product API could reduce sync time significantly.
  Similar to improvement already applied in client_commerce.
```

You see only what is relevant to the project you opened.

---

## Example ecosystems

### ClientRetail — 4 projects

A mid-market retailer running a custom e-commerce stack.

| Project | Stack | Role |
|---|---|---|
| `client_retail_api` | Laravel 11 + PostgreSQL | Backend API, order management |
| `client_retail_frontend` | Nuxt 4 + TypeScript | Customer-facing storefront |
| `client_retail_admin` | Nuxt 4 + TypeScript | Internal admin panel |
| `client_retail_docs` | Markdown/VitePress | Developer and integration docs |

Shared squad: Paulo (Tech Lead), a backend specialist, a frontend specialist, Ricardo (E-Commerce Lead) for store optimization work.

Shared knowledge: RFM segmentation model, product taxonomy decisions, checkout CRO experiments (results stored and cross-referenced).

---

### ClientCommerce — 2 projects

A supplier marketplace with Shopify as the sales channel.

| Project | Stack | Role |
|---|---|---|
| `client_commerce_sync` | Python + FastAPI | Supplier data ingestion and sync |
| `client_commerce_theme` | Shopify Liquid + Alpine | Custom storefront theme |

Overnight Research focuses on Shopify API changelogs, supplier EDI standards, and e-commerce pricing trends.

---

### ClientFashion — 6 projects

A fashion brand running a full digital stack across CRM, e-commerce, and analytics.

| Project | Stack | Role |
|---|---|---|
| `client_fashion_api` | Laravel 11 | Core API and business logic |
| `client_fashion_store` | Nuxt 4 | Customer storefront |
| `client_fashion_crm` | Laravel + Filament | Internal CRM |
| `client_fashion_migration` | Python | Legacy data migration tooling |
| `client_fashion_analytics` | Python + dbt | Data warehouse and reporting |
| `client_fashion_mobile` | React Native | Mobile app |

At 6 projects, cross-project context injection is particularly valuable. A schema decision made in `client_fashion_api` is visible to agents in `client_fashion_crm` and `client_fashion_analytics` before they start work.

---

### ClientEnergy — 3 projects

A regulated energy company with compliance requirements.

| Project | Stack | Role |
|---|---|---|
| `client_energy_portal` | Nuxt 4 | Customer self-service portal |
| `client_energy_api` | Laravel 11 | Backend API and meter data |
| `client_energy_analytics` | Python + Metabase | Usage analytics and billing |

The squad includes Daniel (Operations Lead) as a permanent member, because compliance obligations (GDPR, ISO 27001) are recurrent across all three projects. Research is scoped to energy-sector regulation and data privacy updates.

---

## Setting up an ecosystem

### Step 1 — Initialize each project

In each project directory:

```bash
cd ~/Work/client-retail-api
npx arkaos init
```

The installer detects your stack and creates `.arkaos.json`.

### Step 2 — Link projects to an ecosystem

Edit `~/.arkaos/projects/client_retail_api.md` (created by `init`) and add the ecosystem field:

```yaml
---
slug: client_retail_api
ecosystem: client_retail
stack: laravel
---
```

Repeat for each project in the ecosystem. Or pass the flag at init time:

```bash
npx arkaos init --ecosystem client_retail
```

### Step 3 — Define the ecosystem registry entry

Add an entry to `~/.arkaos/ecosystems.json`:

```json
{
  "client_retail": {
    "display_name": "ClientRetail",
    "domain_tags": ["ecommerce", "laravel", "nuxt"],
    "projects": [
      "client_retail_api",
      "client_retail_frontend",
      "client_retail_admin",
      "client_retail_docs"
    ],
    "squad": {
      "lead": "paulo",
      "specialists": ["backend-dev", "frontend-dev", "cro-specialist"]
    }
  }
}
```

### Step 4 — Sync

```bash
/arka update
```

This syncs the registry, validates all project descriptors, and confirms the CwdChanged hook is active.

### Step 5 — Verify

```bash
cd ~/Work/client-retail-api
# Open your AI tool — you should see [arka:context] ecosystem=client_retail
```

---

## Ecosystem vs. plain project

| Capability | Plain project | Ecosystem |
|---|---|---|
| Stack auto-detected | Yes | Yes |
| Context injected on `cd` | Project only | Project + all sibling projects |
| Knowledge base | Project-scoped | Ecosystem-scoped (cross-project links) |
| Dedicated squad | No | Yes — same agents across all projects |
| Overnight insights | Generic | Scoped to the ecosystem's domain |
| Pattern cross-pollination | No | Yes — validated patterns shared across projects |
| Compliance tags (GDPR, ISO) | Manual | Inherited by all projects in the ecosystem |

For a single personal project, a plain `.arkaos.json` is sufficient. For any engagement involving more than one repository, an ecosystem gives you compounding returns on every session.

---

Related: [06 · Cognitive Layer](06-Cognitive-Layer.md) · [07 · Intelligence Loop](07-Intelligence-Loop.md) · [04 · Departments](04-Departments/README.md) · [14 · Use Cases](14-Use-Cases.md) · [Home](Home.md)
