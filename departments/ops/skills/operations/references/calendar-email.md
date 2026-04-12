# arka-operations — Calendar & Email

Referenced from SKILL.md. Read only when needed.

## /ops meeting <topic>

**Step 1: Check Calendar**
- Use Google Calendar MCP to check availability for the next 3 business days
- Identify possible time slots

**Step 2: Prepare Agenda**
- Ask user for meeting participants, duration, and key discussion points
- Draft a structured agenda with time allocations per topic

**Step 3: Create Meeting Note in Obsidian**

**File:** `WizardingCode/Operations/Meetings/<YYYY-MM-DD> <topic>.md`
```markdown
---
type: meeting
department: operations
title: "<topic>"
date_created: <YYYY-MM-DD>
participants:
  - "<name>"
tags:
  - "meeting"
  - "<topic-kebab-case>"
---

# <topic>

## Agenda
1. [Topic] — [time allocation]
2. [Topic] — [time allocation]

## Notes
[To be filled during/after meeting]

## Action Items
- [ ] [Action] — Owner: [name] — Due: [date]

## Decisions Made
- [Decision and rationale]

---
*Part of the [[WizardingCode MOC]]*
```

**Step 4: Report**
```
═══ ARKA OPS — Meeting Prepared ═══
Topic:       <topic>
Date:        <suggested date/time>
Participants: <list>
Obsidian:    WizardingCode/Operations/Meetings/<date> <topic>.md
════════════════════════════════════
```

## /ops email <type>

Use Gmail MCP to draft/send emails. Common types: welcome, kickoff, follow-up, invoice-reminder, proposal.

Flow:
1. Clarify type, recipient(s), subject, context
2. Draft via Gmail MCP (professional tone, Eduardo-reviewed copy)
3. Self-critique: accuracy, tone, errors
4. Quality Gate review before send
5. Send or save as draft per user preference

## /ops calendar

Use Google Calendar MCP to display schedule. Default view: today + next 3 business days. Highlight conflicts and free slots.
