---
name: dev/mcp-builder
description: >
  Build production-ready MCP servers from API contracts. Scaffold from OpenAPI,
  validate tool manifests, design auth and versioning strategies.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent]
---

# MCP Builder — `/dev mcp-builder <api>`

> **Agent:** Andre (Backend Dev) | **Framework:** MCP Server Architecture

## What This Does

Builds MCP (Model Context Protocol) servers that expose APIs as typed tools for LLM agents. Converts OpenAPI specs into MCP tool definitions with scaffolded server code.

Note: For managing/applying existing MCP servers to projects, use `/dev mcp` instead.

## Build Process

1. Start from a valid OpenAPI spec (or define tools manually)
2. Generate tool manifest + starter server code
3. Review naming, descriptions, and auth strategy
4. Add endpoint-specific runtime logic
5. Validate with strict mode before publishing
6. Deploy with versioning and backward compatibility

## Runtime Selection

| Runtime | When to Choose | Strength |
|---------|---------------|----------|
| **Python** | Data pipelines, backend-heavy teams | Fast iteration, rich ecosystem |
| **TypeScript** | JS stacks, frontend/backend contract reuse | Shared types, tighter integration |

## Tool Design Rules

| Rule | Correct | Wrong |
|------|---------|-------|
| Naming | `list_invoices`, `create_user` | `get__v1__users___id` |
| Scope | One task intent per tool | Mega-tools with mode flags |
| Descriptions | Verb-first, explain intent and result | Missing or generic |
| Required fields | Explicitly typed, all required marked | Ambiguous optional-only schemas |
| Destructive ops | Include confirmation parameter | No guard on deletes |
| Errors | Structured `{ code, message, details }` | Opaque error strings |

## Auth and Safety

- [ ] Secrets in environment variables, never in tool schemas
- [ ] Explicit allowlist for outbound hosts
- [ ] Structured error responses for agent recovery
- [ ] Destructive actions require confirmation inputs
- [ ] Rate limiting on high-cost tools
- [ ] Request timeouts on all external calls
- [ ] Secrets and auth headers redacted from logs

## Versioning Strategy

| Action | Rule |
|--------|------|
| Non-breaking change | Additive fields only |
| Rename tool | Never rename in-place, create new tool ID |
| Breaking behavior | New tool ID with changelog entry |
| Deprecation | Mark deprecated, maintain for one release window |

## Quality Gate Checklist

Before publishing a manifest:

- [ ] Every tool has a clear verb-first name
- [ ] Every tool description explains intent and expected result
- [ ] Every required field is explicitly typed
- [ ] Destructive actions include confirmation parameters
- [ ] Error payload format is consistent across all tools
- [ ] Validator returns zero errors in strict mode

## Testing Strategy

| Level | What to Test |
|-------|-------------|
| **Unit** | OpenAPI operation -> MCP tool schema transformation |
| **Contract** | Snapshot `tool_manifest.json`, review diffs in PR |
| **Integration** | Call tool handlers against staging API |
| **Resilience** | Simulate 4xx/5xx upstream errors, verify structured responses |

## Architecture Decision: Single vs Split Servers

| Approach | Pros | Cons |
|----------|------|------|
| **Single MCP server** | Easiest operations | Broader blast radius |
| **Split domain servers** | Cleaner ownership, safer boundaries | More infra to manage |

## Proactive Triggers

Surface these issues WITHOUT being asked:

- Tool returning >10KB per call → flag context window waste
- No input validation on tool params → flag injection risk
- Missing error schema → flag poor client experience

## Output

```markdown
## MCP Server: <Server Name>

### Tools
| Tool | Description | Params | Returns |
|------|------------|--------|---------|
| ... | ... | ... | ... |

### Auth
- **Strategy:** <env vars / OAuth / API key>
- **Outbound hosts:** <allowlist>

### Versioning
- **Current:** v<X>
- **Compatibility:** <backward-compatible since vX>

### Deployment
- **Runtime:** <Python / TypeScript>
- **Transport:** <stdio / HTTP>
```
