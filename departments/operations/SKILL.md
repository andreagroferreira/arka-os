---
name: ops
description: >
  Operations department. Automations, task management, email, calendar, invoicing,
  routine processes. Integrates with ClickUp, Gmail, Calendar MCPs.
  Use when user says "ops", "tasks", "email", "calendar", "automate", "invoice".
allowed-tools: Read, Grep, Glob, Bash, WebFetch, Write
---

# Operations Department — ARKA OS

Company operations, automations, and routine process management.

## Commands

| Command | Description |
|---------|-------------|
| `/ops tasks` | View and manage tasks (via ClickUp MCP) |
| `/ops email <type>` | Send/draft emails (via Gmail MCP) |
| `/ops calendar` | View schedule (via Google Calendar MCP) |
| `/ops meeting <topic>` | Schedule and prepare meeting |
| `/ops invoice <client>` | Generate invoice (via InvoiceExpress MCP) |
| `/ops automate <process>` | Create automation for routine process |
| `/ops report <type>` | Operational reports (weekly, monthly) |
| `/ops onboard-client <name>` | New client onboarding checklist |
| `/ops standup` | Daily standup summary |

## MCP Integrations

| MCP | Used For |
|-----|----------|
| ClickUp | Task management, project tracking |
| Gmail | Email drafts and communication |
| Google Calendar | Scheduling, meetings, deadlines |
| InvoiceExpress | Invoicing and billing |
| Google Drive | Document management |
