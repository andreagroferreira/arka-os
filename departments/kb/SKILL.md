---
name: arka-kb
description: >
  Knowledge Management & Research department. Zettelkasten, BASB, research methodology,
  persona building, Obsidian vault curation. Enabling team that feeds all other departments.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

# Knowledge Management & Research — ArkaOS v2

> **Squad Lead:** Clara (Knowledge Director) | **Agents:** 3 | **Topology:** Enabling

## Commands

| Command | Description | Tier |
|---------|-------------|------|
| `/kb learn <url>` | Ingest content (YouTube, article, PDF) into KB | Enterprise |
| `/kb research <topic>` | Research plan and execution with source evaluation | Focused |
| `/kb ai-research <topic>` | AI-augmented research (Elicit, Perplexity, Claude) | Focused |
| `/kb persona <name>` | Build or view a persona from the KB | Enterprise |
| `/kb moc <cluster>` | Create/update Map of Content | Specialist |
| `/kb zettelkasten <note>` | Process a note through Zettelkasten workflow | Specialist |
| `/kb para-review` | PARA organization review cycle | Specialist |
| `/kb evaluate <source>` | Source evaluation using CRAAP test | Specialist |
| `/kb taxonomy` | Taxonomy and tagging management | Specialist |
| `/kb review` | Knowledge freshness review (90-day cycle) | Specialist |
| `/kb search <query>` | Search the knowledge base | Specialist |
| `/kb intel <competitor>` | Competitive intelligence research | Focused |

## Squad

| Agent | Tier | DISC | Specialty |
|-------|------|------|-----------|
| **Clara** | 1 | S+C | Knowledge strategy, taxonomy, quality |
| **Francisco** | 2 | C+I | Research execution, source evaluation, CI |
| **Helena C.** | 2 | S+C | Vault maintenance, Zettelkasten, MOCs, linking |

## Frameworks: Zettelkasten (Luhmann), BASB/CODE/PARA (Forte), SECI Model (Nonaka/Takeuchi), LYT/MOCs (Milo), Progressive Summarization, CRAAP Test, Research Methodology

## Model Selection

When dispatching subagent work via the Task tool, include the `model` parameter from the target agent's YAML `model:` field:

- Agent YAMLs at `departments/*/agents/*.yaml` have `model: opus | sonnet | haiku`
- Quality Gate dispatch (Marta/Eduardo/Francisca) ALWAYS uses `model: opus` — NON-NEGOTIABLE
- Default to `sonnet` if the agent YAML has no `model` field
- Mechanical tasks (commit messages, routing, keyword extraction) use `model: haiku`

Example Task tool call:

    Task(description="...", subagent_type="general-purpose", model="sonnet", prompt="...")
