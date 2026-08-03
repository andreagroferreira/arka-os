---
name: research-deep
description: >
  Heavy-research ladder over the operator's own knowledge: Obsidian
  vault first (cite or declare the gap), then the operator's NotebookLM
  notebook through the egress-guarded chokepoint, then open web for
  whatever gap remains — ending in a synthesis note written back to the
  vault with provenance frontmatter (egress_decision, degraded).
  TRIGGER: "research deep", "pesquisa profunda", "pergunta ao
  NotebookLM", "usa o notebook", "deep dive com as minhas fontes",
  "/kb research-deep <question>". SKIP: general fan-out research whose
  deliverable is a cited KB note -> arka-research (5 parallel external
  searchers; this skill is depth over the operator's OWN corpus);
  defining a research question and its method from scratch ->
  kb/research-plan (owns the 5-step methodology; this skill executes a
  source ladder against an already-framed question);
  library/framework evaluation -> dev research (Lucas); a named
  competitor -> kb/competitive-intel.
metadata:
  origin: arkaos
---

# Research Deep

> **Agent:** Clara (Knowledge Director) | **Framework:** KB-first ladder (Obsidian → NotebookLM → web)

## What It Does

Answers a hard question by climbing four rungs in order — three that
research, one that writes back — asking the cheapest and most-trusted
source first. Each rung either answers, or narrows the gap the next rung
has to fill. The output is a synthesis note written back to the Obsidian
vault with provenance frontmatter, so the next run starts from a fuller
vault.

NotebookLM is reached EXCLUSIVELY through the `core.kb.nlm_client`
chokepoint — the egress guard (deny-by-default policy, client-identifier
redaction, salted audit trail) screens every payload before anything
leaves the machine. Never invoke the `notebooklm` binary directly, and
never install or vendor `notebooklm-py` from this skill: when the tool
is absent the chokepoint says so and the ladder continues.

## Rung 1 — Obsidian (mandatory, never skipped)

1. `mcp__obsidian__search_notes` on the question and its key terms
   (plus `mcp__graphify__query_graph` when configured).
2. Read the hits that matter. Cite them as `[[wikilinks]]` in the
   synthesis.
3. Decide honestly: answered, partially answered (name the residual
   gap), or gap. Only a named gap justifies the next rung.

## Rung 2 — NotebookLM (chokepoint-only, degradation never blocks)

Preflight once per session:

```bash
~/.arkaos/bin/arka-py - <<'PY'
from core.kb.nlm_client import check
r = check()
print("ok" if r.ok else r.marker)
PY
```

Then ask. **Never interpolate the question into the command.** A research
question routinely carries backticks, `$`, quotes and `$HOME`, and a
shell that expands them executes the question instead of asking it (and
`$HOME` expansion alone manufactures a false confidentiality denial).
The heredoc below is quoted (`<<'PY'`), so the shell passes it through
untouched.

The scratch path is fixed — `$HOME/.arkaos/tmp/research-deep-gap.txt` —
so no agent-chosen path reaches the program either. Write the gap there
with the Write tool (absolute path, expand `$HOME` yourself; create the
directory first if your runtime's write primitive does not), then:

```bash
~/.arkaos/bin/arka-py - <<'PY'
from pathlib import Path
from core.kb.nlm_client import send
gap_file = Path.home() / ".arkaos" / "tmp" / "research-deep-gap.txt"
gap = gap_file.read_text()
gap_file.unlink()   # one gap per ask: a stale read fails loudly instead
r = send(gap, action="ask", output_format="markdown")
print(r.stdout if r.ok else r.marker)
PY
```

A `FileNotFoundError` here means the Write did not land — write the gap
again rather than re-running the ask, which would otherwise have sent
the previous session's question.

Reading the result — the contract is `NotebookLMResult`:

| Field | Meaning |
|---|---|
| `ok=True` | `r.stdout` is the answer; cite it as `NotebookLM (notebook)` |
| `ok=False, denied=True` | the egress guard refused the payload (e.g. client identifiers survived redaction) — do NOT rephrase-and-retry to evade it; record the marker and move on |
| `ok=False, degraded=True` | tool absent, timeout, or unusable run — record the marker and move on |

Branch on `ok`, never on `degraded` alone (a denied payload is not a
success path). When `ok` is False, put the marker line —
`[arka:source-skipped] notebooklm (<reason>)` — on record in your reply
AND in the synthesis note, then continue to rung 3. A broken or refused
upstream narrows the ladder; it never blocks it. Other actions in
`ALLOWED_ACTIONS`: `report` and `mindmap` (same result contract), and
`add-source`, which pushes a text INTO the notebook — see the optional
step in rung 4.

If the preflight says the tool is missing and the operator wants it,
the install is THEIR command, not this skill's:
`uv tool install 'notebooklm-py[browser]'`.

## Rung 3 — Open web (only for the residual gap)

`WebSearch` / `WebFetch` scoped to what rungs 1-2 could not answer.
Prefer primary sources; carry URLs into the synthesis. If rung 2 was
denied, remember the payload was refused for a confidentiality reason —
do not paste the same refused content into a web search either.

## Rung 4 — Write-back (always, even on partial answers)

Write the synthesis note to the vault via `mcp__obsidian__write_note`
(fallback: Write into the vault path), with provenance frontmatter:

```markdown
---
title: <question, short>
type: research-note
skill: kb/research-deep
date: <YYYY-MM-DD>
provenance:
  rungs_used: [obsidian, notebooklm, web]   # the rungs that ran
  egress_decision: ok        # ok | denied | degraded | not-attempted
  egress_reason: ""          # NotebookLMResult.reason when not ok
  degraded: false            # NotebookLMResult.degraded
  payload_sha256: "<hex>"    # see the note below — set on denial too
sources:
  - "[[<vault note>]]"
  - "NotebookLM (notebook)"
  - "<url>"
---

<synthesis: what is known, what each rung contributed, what remains open>
```

Field mapping, exactly:

- `degraded`, `egress_reason` and `payload_sha256` are copied from
  `NotebookLMResult.degraded`, `.reason` and `.payload_sha256`.
- `egress_decision` names whichever of `ok` / `denied` / `degraded` the
  result carries, or `not-attempted` when rung 2 never ran — never
  inferred from the answer text.
- `payload_sha256` is populated on a DENIAL too (the guard digests what
  it refused), so record it whenever the field is non-empty and let
  `egress_decision: denied` say that nothing left the machine.

Optionally feed the notebook back: when the synthesis is worth keeping
in NotebookLM, send it with `action="add-source"` through the same
quoted-heredoc pattern as rung 2 (same guard, same result contract).

Link related notes with `[[wikilinks]]` so the graph face of the KB
benefits too.

## Output

One Obsidian note per run — the synthesis, its `[[wikilinks]]` and URL
sources, and the provenance frontmatter above (`rungs_used`,
`egress_decision`, `egress_reason`, `degraded`, `payload_sha256`). Plus,
in the reply itself, the `[arka:source-skipped]` marker for every rung
that could not answer.

## Guardrails

- Chokepoint-only: any path to NotebookLM other than
  `core.kb.nlm_client` is a campaign-decision violation (egress
  fail-closed, 2026-07-26; contract:
  `.arkaos/specs/notebooklm-chokepoint.yaml`).
- Never interpolate research text into a shell command, and never
  interpolate a chosen path into the program — quoted heredoc plus the
  fixed scratch path, always.
- A `denied` result is a confidentiality signal, not an obstacle —
  evading it through rephrasing, chunking, or the web is forbidden.
- Rungs that did not run are not listed in `rungs_used`, and markers for
  skipped sources appear in the note body.
