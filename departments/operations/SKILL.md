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
| `/ops channel add <platform> <channel-id>` | Add messaging channel (slack, discord, whatsapp, teams) |
| `/ops channel list` | List configured messaging channels |
| `/ops channel remove <platform>` | Remove a messaging channel |
| `/ops notify <message>` | Send message to default notification channel |
| `/ops broadcast <message>` | Send message to all configured channels |

## Obsidian Output

All operations output goes to the Obsidian vault at `/Users/andreagroferreira/Documents/Personal/`:

| Content Type | Vault Path |
|-------------|-----------|
| Process docs | `WizardingCode/Operations/Processes/<name>.md` |
| Automation specs | `WizardingCode/Operations/Automations/<name>.md` |
| Client onboarding | `WizardingCode/Operations/Clients/<name>/Onboarding.md` |
| Meeting notes | `WizardingCode/Operations/Meetings/<date> <topic>.md` |
| Operational reports | `WizardingCode/Operations/Reports/<date> <type>.md` |

**Obsidian format:**
```markdown
---
type: report
department: operations
title: "<title>"
date_created: <YYYY-MM-DD>
tags:
  - "report"
  - "operations"
  - "<specific-tag>"
---
```

All files use wikilinks `[[]]` for cross-references and kebab-case tags.

## Workflows

### /ops meeting <topic>

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

### /ops automate <process>

**Step 1: Analyze Current Process**
- Ask user to describe the current manual process step by step
- Identify frequency, time spent, and pain points

**Step 2: Document Current State**
- Map all steps, decision points, and handoffs
- Identify which steps are repetitive and automatable

**Step 3: Design Automation**
- Propose automation approach (ClickUp automations, scripts, email templates, etc.)
- Identify tools and integrations needed
- Estimate time saved per occurrence

**Step 4: Create SOP in Obsidian**

**File:** `WizardingCode/Operations/Automations/<process>.md`
```markdown
---
type: automation
department: operations
title: "<process> — Automation SOP"
date_created: <YYYY-MM-DD>
status: draft
time_saved: "<estimate per occurrence>"
tags:
  - "automation"
  - "sop"
  - "<process-kebab-case>"
---

# <process> — Automation SOP

## Current Process (Before)
1. [Manual step]
2. [Manual step]

## Automated Process (After)
1. [Automated/simplified step]
2. [Automated/simplified step]

## Implementation
- **Tools:** [ClickUp, Gmail, scripts, etc.]
- **Setup steps:** [numbered list]
- **Triggers:** [what kicks off the automation]

## Estimated Impact
- Time saved per occurrence: [X min]
- Frequency: [X times/week]
- Total weekly savings: [X hours]

---
*Part of the [[WizardingCode MOC]]*
```

**Step 5: Report**
```
═══ ARKA OPS — Automation Designed ═══
Process:     <process>
Steps:       <before count> → <after count>
Time saved:  <estimate per occurrence>
Obsidian:    WizardingCode/Operations/Automations/<process>.md
═══════════════════════════════════════
```

### /ops onboard-client <name>

**Step 1: Create Client Folder in Obsidian**

Create the directory structure:
- `WizardingCode/Operations/Clients/<name>/Onboarding.md`

**Step 2: Generate Onboarding Checklist**

**File:** `WizardingCode/Operations/Clients/<name>/Onboarding.md`
```markdown
---
type: onboarding
department: operations
title: "<name> — Client Onboarding"
client: "<name>"
date_created: <YYYY-MM-DD>
status: in-progress
tags:
  - "client"
  - "onboarding"
---

# <name> — Client Onboarding

## Client Info
- **Company:** <name>
- **Contact:** [TBD]
- **Email:** [TBD]
- **Project:** [TBD]
- **Start date:** <YYYY-MM-DD>

## Onboarding Checklist

### Admin
- [ ] Contract signed
- [ ] Invoice sent (first payment)
- [ ] Add to ClickUp workspace
- [ ] Create project in ClickUp
- [ ] Share Google Drive folder

### Technical
- [ ] Collect access credentials (hosting, DNS, APIs)
- [ ] Set up project repository
- [ ] Scaffold project (`/dev scaffold`)
- [ ] Configure MCPs for project
- [ ] Create PROJECT.md

### Communication
- [ ] Welcome email sent
- [ ] Kickoff meeting scheduled
- [ ] Communication channels established
- [ ] Reporting cadence agreed

### Knowledge
- [ ] Brand guidelines collected
- [ ] Existing content/assets received
- [ ] Competitor list documented
- [ ] Project brief approved

---
*Part of the [[WizardingCode MOC]]*
```

**Step 3: Create ClickUp Tasks**
- Use ClickUp MCP to create a task list mirroring the onboarding checklist
- Assign due dates based on a 2-week onboarding timeline

**Step 4: Report**
```
═══ ARKA OPS — Client Onboarding Created ═══
Client:      <name>
Checklist:   <count> items
ClickUp:     Tasks created
Obsidian:    WizardingCode/Operations/Clients/<name>/Onboarding.md
═════════════════════════════════════════════
```

### /ops standup

**Step 1: Scan Active Projects**
- Read `projects/` directory for active project context
- Check each PROJECT.md for recent updates

**Step 2: Check ClickUp**
- Use ClickUp MCP to get tasks due today and overdue tasks
- Get tasks completed yesterday

**Step 3: Check Calendar**
- Use Google Calendar MCP to get today's meetings and deadlines

**Step 4: Generate Standup Report**

**Output (display, not saved):**
```
═══ ARKA OPS — Daily Standup ═══
Date: <YYYY-MM-DD>

📋 Tasks Due Today
- [Task 1] — [project]
- [Task 2] — [project]

⚠️  Overdue
- [Task] — [days overdue] — [project]

✅ Completed Yesterday
- [Task 1] — [project]
- [Task 2] — [project]

📅 Today's Calendar
- [HH:MM] [Meeting/Event]
- [HH:MM] [Meeting/Event]

🔥 Blockers
- [Any identified blockers]

═════════════════════════════════
```

### /ops channel add <platform> <channel-id>

**Supported platforms:** `slack`, `discord`, `whatsapp`, `teams`

1. Read `knowledge/channels-config.json`
2. Add entry: `"<platform>": { "channel_id": "<channel-id>", "added": "<date>" }`
3. If no default notification channel exists, set this as the default
4. Write updated config back
5. Confirm: "Channel added. Use `/ops notify` to send messages."

### /ops channel list

1. Read `knowledge/channels-config.json`
2. Display all configured channels with their platform and channel ID
3. Mark the default notification channel with `[DEFAULT]`

### /ops channel remove <platform>

1. Read `knowledge/channels-config.json`
2. Remove the specified platform entry
3. If the removed channel was the default, clear the default
4. Write updated config back

### /ops notify <message>

1. Read `knowledge/channels-config.json` → get default notification channel
2. If no default set, warn and list available channels
3. Use the appropriate MCP (Slack, Discord, WhatsApp, or Teams) to send the message
4. Confirm delivery

### /ops broadcast <message>

1. Read `knowledge/channels-config.json` → get all configured channels
2. For each channel, use the appropriate MCP to send the message
3. Report delivery status per channel

## MCP Integrations

| MCP | Used For |
|-----|----------|
| ClickUp | Task management, project tracking |
| Gmail | Email drafts and communication |
| Google Calendar | Scheduling, meetings, deadlines |
| InvoiceExpress | Invoicing and billing |
| Google Drive | Document management |
| Slack | Slack messaging (via comms profile) |
| Discord | Discord messaging (via comms profile) |
| WhatsApp | WhatsApp Business messaging (via comms profile) |
| Teams | Microsoft Teams messaging (via comms profile) |

---
*All output: `WizardingCode/Operations/` — Part of the [[WizardingCode MOC]]*
