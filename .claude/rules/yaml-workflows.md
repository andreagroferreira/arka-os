---
paths:
  - "departments/*/workflows/*.yaml"
---

# Workflow YAML Rules

- Every workflow must include a Quality Gate phase
- Standard phase order: Context Loading, Analysis & Planning, Plan Presentation & Approval, Execution, Quality Gate, Documentation
- Parallel execution only for independent agents (no shared state)
- User approval gates between key phases (NON-NEGOTIABLE)
- Each phase must specify: agent(s), inputs, outputs, success criteria
