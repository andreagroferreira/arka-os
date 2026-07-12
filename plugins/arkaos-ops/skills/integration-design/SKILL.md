---
name: integration-design
description: >
  Designs system-to-system integrations via API, webhook, or iPaaS platform, producing a
  spec with data flow diagram, error handling, and monitoring. TRIGGER: "integra o
  sistema X com Y", "connect these two systems", "liga o CRM ao ERP", "integration
  between", "webhook design", "/ops integration <systems>". SKIP: designing the API
  contract itself -> dev/api-design (endpoint design, not cross-system wiring); building
  the flow on an already-chosen platform -> ops/n8n-flow or ops/zapier-flow.
---

# Integration Design

> **Agent:** Tomas A. (Automation Engineer) | **Framework:** iPaaS Architecture + API Patterns

## What It Does

Integration design: connect systems via API, webhook, or iPaaS platform.

## Output

Integration spec with data flow diagram, error handling, and monitoring
