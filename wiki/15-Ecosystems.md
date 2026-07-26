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

When you `cd` into a project directory, the **CwdChanged hook** fires. It reads `~/.arkaos/ecosystems.json`, matches the new working directory against the registered project names to resolve the ecosystem slug, and surfaces a system message naming the ecosystem and its dedicated command. The system message is the whole delivery on this event — the ecosystem is announced once, to you. On the next prompt, the Synapse layers that read the cwd refresh: the git branch tag (feature branches only — it stays quiet on main, master, and dev), the graph context, the knowledge retrieval, and the cross-session memory scoped to the directory. You don't type anything to be located — ArkaOS already knows where it is.

**Example — opening the ClientRetail frontend:**

```bash
cd ~/Work/client-retail-frontend
```

The hook surfaces:

```
[arka:project-context] Ecosystem: ClientRetail (client_retail) | Stack: nuxt | Use /arka-client_retail for dedicated squad routing.
```

From there:
- `/arka-client_retail` loads the full squad context on demand.
- Your next prompts carry the feature-branch tag, the graph context, the knowledge retrieval, and the cross-session memory scoped to this directory.

Compare this to an unregistered project: the hook reports the detected stack with an `/arka onboard` suggestion — or emits nothing at all when the directory carries no recognizable stack markers and no project descriptor (a lone descriptor still surfaces its path).

---

## Knowledge that compounds

When work is completed in any project inside an ecosystem, the Auto-Documentor (part of the [Intelligence Loop](07-Intelligence-Loop.md)) writes it back to Obsidian with ecosystem tags. The relator then creates `[[wikilinks]]` between related notes across projects.

**Example chain for ClientRetail:**

```
client-retail-api/auth-pattern.md
  ↔ client-retail-frontend/auth-composable.md
  ↔ client-retail-admin/session-handling.md
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
   Exponential backoff with jitter is a validated pattern from client-retail-api.
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
| `client-retail-api` | Laravel 11 + PostgreSQL | Backend API, order management |
| `client-retail-frontend` | Nuxt 4 + TypeScript | Customer-facing storefront |
| `client-retail-admin` | Nuxt 4 + TypeScript | Internal admin panel |
| `client-retail-docs` | Markdown/VitePress | Developer and integration docs |

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

Create (or edit) `~/.arkaos/projects/client-retail-api.md` with the
fields below. The file name must match the project **directory** name
— the CwdChanged hook looks up `<basename of cwd>.md`:

```yaml
---
name: client-retail-api
path: /Users/you/Work/client-retail-api
ecosystem: client_retail
stack: laravel
---
```

`path` is mandatory and must be absolute — descriptor discovery skips
any file without it. Repeat for each project in the ecosystem.

### Step 3 — Define the ecosystem registry entry

Add an entry to `~/.arkaos/ecosystems.json` (note the top-level
`"ecosystems"` wrapper — every consumer reads it):

```json
{
  "ecosystems": {
    "client_retail": {
      "name": "ClientRetail",
      "domain_tags": ["ecommerce", "laravel", "nuxt"],
      "projects": [
        "client-retail-api",
        "client-retail-frontend",
        "client-retail-admin",
        "client-retail-docs"
      ],
      "project_paths": {
        "client-retail-api": "/Users/you/Work/client-retail-api",
        "client-retail-frontend": "/Users/you/Work/client-retail-frontend",
        "client-retail-admin": "/Users/you/Work/client-retail-admin",
        "client-retail-docs": "/Users/you/Work/client-retail-docs"
      },
      "squad": {
        "lead": "paulo",
        "specialists": ["backend-dev", "frontend-dev", "cro-specialist"]
      }
    }
  }
}
```

The two keys have separate roles. `projects` entries are matched as
substrings of the new working directory, so register the **directory
names** exactly as they appear on disk — they drive `cd` detection
only. `project_paths` makes an ecosystem's projects discoverable to
`/arka update` sync **by path** — sync also picks up `~/.arkaos/projects/`
descriptors and scanned project directories, so list a project here to
guarantee it is found regardless of descriptor state. Use **absolute
paths** — discovery does not expand `~`.

### Step 4 — Sync

```bash
/arka update
```

This syncs the registry, validates all project descriptors, and confirms the CwdChanged hook is active.

### Step 5 — Verify

```bash
cd ~/Work/client-retail-api
# Open your AI tool — the hook surfaces:
# [arka:project-context] Ecosystem: ClientRetail (client_retail) | Stack: laravel | Use /arka-client_retail for dedicated squad routing.
```

---

## Ecosystem vs. plain project

| Capability | Plain project | Ecosystem |
|---|---|---|
| Stack auto-detected | Yes | Yes |
| System message on `cd` | Detected stack only | Ecosystem + stack + dedicated squad command |
| Knowledge base | Project-scoped | Ecosystem-scoped (cross-project links) |
| Dedicated squad | No | Yes — same agents across all projects |
| Overnight insights | Generic | Scoped to the ecosystem's domain |
| Pattern cross-pollination | No | Yes — validated patterns shared across projects |
| Compliance tags (GDPR, ISO) | Manual | Inherited by all projects in the ecosystem |

For a single personal project, a plain `.arkaos.json` is sufficient. For any engagement involving more than one repository, an ecosystem gives you compounding returns on every session.

---

Related: [06 · Cognitive Layer](06-Cognitive-Layer.md) · [07 · Intelligence Loop](07-Intelligence-Loop.md) · [04 · Departments](04-Departments/README.md) · [14 · Use Cases](14-Use-Cases.md) · [Home](Home.md)
