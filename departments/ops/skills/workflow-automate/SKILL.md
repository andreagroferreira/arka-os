---
name: ops/workflow-automate
description: >
  Design workflow automations using n8n, Zapier, or Make.
  Selects the right platform, designs the flow, handles errors.
allowed-tools: [Read, Write, Edit, Agent, WebFetch]
---

<!-- arka:kb-first-prefix begin -->
## KB-First Research (non-negotiable)

Before any external research (Context7, WebSearch, WebFetch, Firecrawl):

1. Call `mcp__obsidian__search_notes` on the query first.
2. Cite relevant hits with `[[wikilinks]]` or explicitly declare a KB gap.
3. Only after (1) and (2) may external tools run.

The Synapse L2.5 layer pre-injects top KB matches on every user prompt;
treat them as your default source. External research supplements, it
does not replace the vault.
<!-- arka:kb-first-prefix end -->

# Workflow Automation — `/ops workflow <process>`

> **Agent:** Tomas A. (Automation Engineer) | **Framework:** Automation Design Patterns

## Platform Selection

| Factor | Zapier | Make | n8n |
|--------|--------|------|-----|
| Ease | Easiest | Medium | Technical |
| Cost | $69+/mo | $9+/mo | Free (self-hosted) |
| AI-native | Limited | Moderate | 70+ LangChain nodes |
| Self-hosted | No | No | Yes |
| Best for | Simple triggers | Complex logic | AI workflows, privacy |

## Design Patterns

1. **Trigger-Action:** Event → Single action
2. **Multi-Step Pipeline:** Event → Step 1 → Step 2 → ... → Step N
3. **Conditional Branch:** Event → [Condition?] → Path A or Path B
4. **Loop & Batch:** For each item → Action → Next item
5. **Scheduled:** Cron → Action → Report
6. **Webhook Listener:** External event → Parse → Process → Respond
7. **AI-Augmented:** Input → AI classify/extract → Action based on AI output

## Error Handling (mandatory)
- Retry logic with exponential backoff (3 retries default)
- Dead letter queue for permanent failures
- Alert notification on failure (Slack/email)
- Idempotency: safe to retry without duplicates

## Browser Steps

Follow the [Browser Integration Pattern](/arka) for availability checking.

- [BROWSER] Open the relevant web tools (Gmail, Google Calendar, ClickUp, N8N) to verify automation results
- [BROWSER] Test the automated workflow end-to-end by triggering it and watching the result in the browser
- [BROWSER] Verify notifications and emails arrive correctly

## Computer Use Steps

Follow the [Computer Use Availability Check](/arka) for availability checking.

- [COMPUTER] Open desktop apps (Slack, Notion, calendar apps) to verify automation results

## Scheduling ⏰

```
/loop 15m check N8N workflow executions, flag any failures in the last hour
/schedule hourly — monitor all active automations and report error rate
```

## Output → Workflow diagram + platform config + error handling spec
