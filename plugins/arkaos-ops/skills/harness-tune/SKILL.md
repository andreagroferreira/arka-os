---
name: harness-tune
description: >
  Telemetry-driven tuning of the ArkaOS harness itself: reads the
  recorded usage (MCP call telemetry, LLM cost lines, skill-budget
  report, curated-mode leftovers) and proposes the cuts and switches
  the data supports — MCP servers nothing called, skill surface beyond
  the context budget, department packs installed but idle. Propose-only;
  the operator applies. TRIGGER: "/ops harness-tune", "tune my setup",
  "otimiza o meu harness", "o que posso cortar?", "porque está o
  contexto tão cheio?", "que MCPs não uso?". SKIP: install health ->
  the doctor (npx arkaos doctor) wins; cost VISIBILITY without action
  -> /arka costs wins; business-process bottlenecks ->
  ops/bottleneck-find wins.
metadata:
  origin: arkaos
---

# Harness Tune

> **Agent:** Daniel (Operations Lead) | **Framework:** Usage-evidence pruning, propose-only changes

Every MCP server registered, every skill deployed, every pack installed
pays rent in the scarcest currency the harness has — context — whether
it gets used or not. The bill arrives silently, every single turn. This
skill reads the meters before proposing anything: a recommendation that
is not backed by a telemetry line is an opinion, and opinions do not
get to delete configuration.

## Read the meters

| Meter | Source | Answers |
|---|---|---|
| MCP usage | `~/.arkaos/telemetry/mcp-usage.jsonl` (aggregate: `core.runtime.mcp_telemetry`) | which servers were actually called, when last |
| LLM cost | `core.runtime.llm_cost_telemetry` summaries | which sessions burn, cache hit rate |
| Skill surface | skill-budget linter + `skills-mode.json` + manifest | deployed vs curated cut, leftovers on a curated machine |
| Enforcement | `core.governance.enforcement_telemetry` | gates that fire often (candidates for tuning, not removal) |

A meter that has no data is reported as "no data", never extrapolated —
two days of telemetry cannot justify removing anything.

## Propose (never apply)

For each finding, the proposal names the evidence, the change, the
saving, and the reversal:

- MCP server with zero calls in the observation window → propose
  removing it from the project `.mcp.json` files that carry it; note
  the one-line restore.
- Curated-mode machine carrying plugin-eligible leftovers → propose the
  pack-by-pack install path instead (the doctor's skills-surface check
  names them).
- Full-mode machine using two departments → propose curated + the two
  packs.
- A gate firing constantly with high compliance → nothing to remove;
  flag as healthy enforcement, not noise. Tuning never trades
  governance for tokens.

Hard line: user-added MCPs and project-specific servers are proposed
for removal ONLY on zero usage, and always labeled as user-added —
the harness does not know why the operator installed them, so the
proposal says that too.

## Output

```markdown
## Harness Tune Report — {date}

**Observation window:** {days}d of telemetry ({lines} events)

| # | Evidence | Proposal | Saves | Restore |
|---|---|---|---|---|
| 1 | {server}: 0 calls in {n}d | remove from {k} projects | {context/startup} | {one-liner} |

**No-data meters:** {list, or none}
**Healthy, untouched:** {enforcement surfaces left alone, and why}
**Apply:** every change above is a diff the operator runs — nothing was changed by this audit.
```
