---
name: bottleneck-find
description: >
  Identifies the system constraint with Goldratt's Theory of Constraints and applies the
  5 Focusing Steps (identify, exploit, subordinate, elevate, repeat) into a resolution
  plan with metrics. TRIGGER: "onde está o gargalo", "bottleneck", "work keeps piling up",
  "o processo está lento", "find the constraint", "/ops bottleneck <area>". SKIP:
  waste elimination across a whole value stream -> ops/lean-audit (7-wastes sweep, not a
  single-constraint hunt); defining the metrics that expose queues -> ops/metrics-dashboard.
---

# Bottleneck Analysis

> **Agent:** Daniel (Ops Lead) | **Framework:** Theory of Constraints (Eliyahu Goldratt)

## 5 Focusing Steps

### 1. IDENTIFY the Constraint
- Where does work pile up?
- Which step has the longest wait time?
- What's everyone always waiting for?

### 2. EXPLOIT the Constraint
- Maximize the bottleneck's output WITHOUT investing
- Ensure it never sits idle (buffer work before it)
- Remove non-essential tasks from the bottleneck

### 3. SUBORDINATE Everything Else
- Adjust all other steps to the bottleneck's pace
- Don't produce faster upstream (creates inventory)
- Feed the bottleneck at exactly its capacity

### 4. ELEVATE the Constraint
- NOW invest to increase bottleneck capacity
- Add people, tools, automation
- Only after exploit + subordinate

### 5. REPEAT
- The bottleneck will move. Find the new one.
- Never let inertia become the constraint

## Common Bottlenecks

| Department | Typical Bottleneck | Fix |
|------------|-------------------|-----|
| Dev | Code review | Pair reviews, async reviews, auto-approve for small PRs |
| Marketing | Content creation | Batch production, AI assist, repurposing |
| Sales | Proposal writing | Templates, proposal automation |
| Support | Tier 1 triage | AI classification, self-service docs |
| Operations | Approvals | Delegation matrix, auto-approve thresholds |

## Output → Bottleneck identified + 5-step resolution plan with metrics
