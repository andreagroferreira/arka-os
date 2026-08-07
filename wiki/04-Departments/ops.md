# Operations

← [Departments index](README.md) · [Home](../Home.md)

> **Prefix:** `/ops` · **Lead:** Daniel (Tier 1) · **Agents:** 3 · **Skills:** 24

The Operations department owns process efficiency, automation infrastructure, compliance readiness, and documentation standards. Daniel leads with Theory of Constraints and Lean Thinking as primary lenses — every engagement starts by finding the constraint, not optimizing everything uniformly. The squad can design n8n and Zapier workflows, run lean audits, produce SOPs, and take a product through GDPR, ISO 27001, or SOC 2 readiness.

With 23 skills, Operations carries one of the largest command surfaces in the system (after Development and Marketing). It covers daily workflow automation at one end and regulatory compliance audit preparation at the other. The automation-first principle is applied consistently: if a process is repeatable, it should be automated before being documented.

## Command surface

| Commands | Skills | Agents |
| --- | --- | --- |
| 25 | 24 | 3 |

**Commands** (25 via `/arka`):

| Command | What it does |
| --- | --- |
| `/arka update` | Full sync — run engine, dispatch AI subagent for skills, write state, report |
| `/ops automate <process>` | Create automation for routine process |
| `/ops bottleneck <area>` | Theory of Constraints bottleneck analysis |
| `/ops broadcast <message>` | Send to all configured channels |
| `/ops calendar` | View schedule (Google Calendar MCP) |
| `/ops channel add <platform> <channel-id>` | Add messaging channel |
| `/ops channel list` | List configured messaging channels |
| `/ops channel remove <platform>` | Remove a messaging channel |
| `/ops dashboard <area>` | Operational metrics dashboard |
| `/ops email <type>` | Send/draft emails (Gmail MCP) |
| `/ops gtd-setup` | GTD + PARA personal productivity setup |
| `/ops integration <systems>` | Integration design (API, webhook, iPaaS) |
| ... | 13 more — full list in [docs/COMMANDS.md](../../docs/COMMANDS.md) |

**Skills** (24 — 23 sub-skills plus the `/ops` hub):

| Skill | What it does |
| --- | --- |
| `bottleneck-find` | Identifies the system constraint with Goldratt's Theory of Constraints and applies the 5 Focusing Steps (id... |
| `dashboard-build` | Designs an operational dashboard with Lean Analytics and OMTM: metric selection, targets, data sources, ale... |
| `gdpr-compliance` | GDPR compliance assessment with data mapping, DPIA generation, breach response planning (72-hour notificati... |
| `github-ops` | Drives git and GitHub operations under the branch-isolation and evidence rules — isolated branch, staging b... |
| `gtd-setup` | Sets up a personal productivity system combining GTD (capture, clarify, organize, reflect, engage) with PAR... |
| `harness-tune` | Telemetry-driven tuning of the ArkaOS harness itself: reads the recorded usage (MCP call telemetry, LLM cos... |
| `hookify` | Compiles a repeated correction into a deterministic hook: identify the behavior that keeps being corrected... |
| `integration-design` | Designs system-to-system integrations via API, webhook, or iPaaS platform, producing a spec with data flow... |
| `iso27001` | ISO 27001 ISMS implementation: scope, Annex A control mapping, Statement of Applicability, risk treatment p... |
| `lean-audit` | Runs a Lean audit: maps the value stream, identifies the 7 wastes, and calculates waste-elimination ROI int... |
| `metrics-dashboard` | Defines the operational metrics system — throughput, lead time, error rate, SLAs — producing a spec with th... |
| `n8n-flow` | Designs n8n workflows — AI/LangChain nodes, webhooks, branching, error handling — and validates deployed fl... |
| `operations` | Operations department orchestrator (Sofia COO squad): ClickUp tasks, Gmail email drafting, Google Calendar... |
| `ops-hub` | Operations & Automation department. Process optimization, workflow automation, SOPs, bottleneck analysis, i... |
| `quality-management` | Designs and assesses a quality management system per ISO 9001:2015 — QMS phases (PDCA), quality KPIs, inter... |
| `risk-management` | Enterprise risk identification, assessment (5x5 matrix), treatment, and monitoring using ISO 31000 and COSO... |
| `session-retro` | Post-session friction analysis over the actual transcript: finds the corrections the operator made more tha... |
| `soc2-compliance` | SOC 2 Type I/II readiness assessment: Trust Services Criteria mapping, control matrix generation, evidence... |
| `sop-create` | Creates a Standard Operating Procedure: numbered steps, RACI roles, tools, exceptions, and review cycle, fo... |
| `terminal-ops` | Runs shell operations the evidence-first way — every command's exit code and real output are captured and c... |
| `update` | ArkaOS project sync orchestrator: detects what changed in core since the last sync and updates ecosystem sk... |
| `workflow-automate` | Designs workflow automations end to end: selects the right platform (n8n, Zapier, or Make), applies the mat... |
| `workspace-audit` | Sweeps every repository in the workspace for the entropy that accumulates between projects: dirty working t... |
| `zapier-flow` | Designs Zapier workflows: trigger selection, multi-step actions, filters, and error notifications, delivere... |

## The squad

| Agent | Role | Tier |
|---|---|---|
| Daniel | Operations Lead | 1 |
| Tomas A. | Automation Engineer | 2 |
| Isabel | Documentation Writer | 3 |

## Frameworks

- Theory of Constraints (Goldratt) — 5 Focusing Steps to identify and exploit the system constraint
- Lean Thinking (Womack) — 7 wastes identification and value stream mapping
- GTD / PARA (Allen / Forte) — capture, clarify, organize, reflect, engage; area/project/resource/archive
- Kaizen — continuous improvement cycles with measurable deltas
- ISO 31000 — enterprise risk identification, assessment, and treatment
- COSO ERM — control framework for cross-department risk monitoring
- ISO 27001 — ISMS control mapping and certification readiness
- SOC 2 Trust Services Criteria — evidence collection and audit preparation
- GDPR — data mapping, DPIA generation, and breach response planning
- ISO 9001 — quality management system design and internal audit

## What you can ask for

- "Find the bottleneck slowing our delivery pipeline" — `/ops bottleneck-find`
- "Design an n8n workflow to automate our lead intake process" — `/ops n8n-flow`
- "Create a Zapier automation for invoice reconciliation" — `/ops zapier-flow`
- "Write an SOP for our customer onboarding process" — `/ops sop-create`
- "Run a lean audit on our support workflow and quantify waste" — `/ops lean-audit`
- "Assess our GDPR compliance and generate a DPIA" — `/ops gdpr-compliance`
- "Prepare us for ISO 27001 certification — map controls and gaps" — `/ops iso27001`
- "Build a SOC 2 readiness report with control matrix" — `/ops soc2-compliance`
- "Design an integration between our CRM and billing system" — `/ops integration-design`
- "Set up a GTD + PARA system for the team" — `/ops gtd-setup`

## When to use it

Operations belongs in any conversation about process inefficiency, automation opportunities, compliance deadlines, or operational documentation. It is also the right entry point when you need a risk register, an operational metrics dashboard, or a quality management system built from scratch.

---

Related: [Core Concepts](../02-Core-Concepts.md) · [The Evidence Flow (4 Gates)](../03-The-13-Phase-Flow.md) · [Quality Gate](../10-Quality-Gate.md)
