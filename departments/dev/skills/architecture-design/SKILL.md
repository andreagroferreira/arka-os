---
name: dev/architecture-design
description: >
  Design system architecture using Clean Architecture, Hexagonal, or DDD patterns.
  Produces an ADR (Architecture Decision Record) saved to Obsidian.
allowed-tools: [Read, Write, Edit, Grep, Glob, Agent, WebFetch]
---

# Architecture Design — `/dev architecture <system>`

> **Agent:** Gabriel (Architect) | **Approver:** Marco (CTO)
> **Frameworks:** Clean Architecture, Hexagonal, DDD, Vertical Slice

## Workflow

### Step 1: Context Loading
- Read PROJECT.md and existing architecture
- Scan current codebase structure
- Identify existing patterns and conventions

### Step 2: Requirements Gathering
- Ask user: What system/feature needs architecture?
- Clarify: Scale requirements, team size, tech constraints
- Identify: Domain boundaries, data flows, external integrations

### Step 3: Architecture Design
Apply the appropriate pattern:

**Clean Architecture** (default for most systems):
```
Domain (entities, value objects) → no dependencies
Application (use cases) → depends on Domain
Interface Adapters (controllers, gateways) → depends on Application
Frameworks (DB, HTTP, UI) → depends on Interface Adapters
```

**Hexagonal** (when many external integrations):
```
Ports (interfaces defined by domain)
Adapters (implementations for each external system)
```

**DDD Strategic** (when complex domain):
```
Bounded Contexts → Context Map → Aggregates → Domain Events
```

### Step 4: ADR Document

```markdown
---
type: adr
title: "ADR-NNN: <Decision Title>"
status: proposed
date: YYYY-MM-DD
tags: [architecture, <domain>]
---

# ADR-NNN: <Decision Title>

## Context
What is the situation that requires a decision?

## Decision
What is the architecture we chose?

## Alternatives Considered
What else did we consider and why did we reject it?

## Data Flow
How does data move through the system?

## API Contracts
Key interfaces between components.

## Schema Changes
Database changes needed.

## Consequences
What are the trade-offs of this decision?

## Security Considerations
Security implications and mitigations.
```

### Step 5: CTO Review
- Marco reviews the ADR
- Approves or requests changes
- ADR saved to Obsidian: `Projects/<name>/Architecture/ADR-<NNN>.md`
