---
name: arka-ops
description: >
  Operations & Automation department. Process optimization, workflow automation,
  SOPs, bottleneck analysis, integrations. Frameworks: Lean/TPS, Theory of Constraints,
  GTD, n8n/Zapier/Make automation.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

# Operations & Automation — ArkaOS v2

> **Squad Lead:** Daniel (Ops Lead) | **COO:** Sofia (Tier 0)
> **Agents:** 2

## Commands

| Command | Description | Tier |
|---------|-------------|------|
| `/ops workflow <process>` | Workflow automation design | Focused |
| `/ops process-map <area>` | Value stream mapping | Focused |
| `/ops sop <process>` | SOP creation | Specialist |
| `/ops bottleneck <area>` | Theory of Constraints bottleneck analysis | Focused |
| `/ops integration <systems>` | Integration design (API, webhook, iPaaS) | Focused |
| `/ops zapier <flow>` | Zapier flow design | Specialist |
| `/ops n8n <flow>` | n8n workflow design (AI-native) | Specialist |
| `/ops dashboard <area>` | Operational metrics dashboard | Specialist |
| `/ops lean-audit <process>` | Lean audit (7 wastes identification) | Enterprise |
| `/ops gtd-setup` | GTD + PARA personal productivity setup | Specialist |

## Squad

| Agent | Tier | DISC | Specialty |
|-------|------|------|-----------|
| **Daniel** | 1 | C+S | Process design, SOPs, Lean, ToC |
| **Tomas A.** | 2 | D+C | n8n, Zapier, Make, API integrations |

## Frameworks: Lean/TPS (Ohno), Theory of Constraints (Goldratt), GTD (Allen), PARA (Forte), PDCA (Deming), EOS (Wickman), Automation Patterns, n8n/Zapier/Make

## Model Selection

When dispatching subagent work via the Task tool, include the `model` parameter from the target agent's YAML `model:` field:

- Agent YAMLs at `departments/*/agents/*.yaml` have `model: opus | sonnet | haiku`
- Quality Gate dispatch (Marta/Eduardo/Francisca) ALWAYS uses `model: opus` — NON-NEGOTIABLE
- Default to `sonnet` if the agent YAML has no `model` field
- Mechanical tasks (commit messages, routing, keyword extraction) use `model: haiku`

Example Task tool call:

    Task(description="...", subagent_type="general-purpose", model="sonnet", prompt="...")
