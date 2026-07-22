---
name: dev/diagram
description: >
  Turn a spec, plan, or system description into an interactive diagram the
  user opens in a browser — one self-contained HTML file, five typed modes
  (architecture, workflow, sequence, dataflow, lifecycle). The agent authors
  a JSON IR, a vendored zero-dependency Node CLI validates it against JSON
  Schemas, renders it, runs semantic gates (clean-flow/clean-label), and
  emits a sha256 receipt. TRIGGER: "diagrama", "desenha a arquitetura",
  "mostra-me visualmente", "visual da spec", "quero ver o fluxo", "diagram
  this", "/dev diagram"; the Visual Spec Companion step in dev/spec; the
  Forge visual-companion option for MEDIUM/HIGH plans. SKIP: DECIDING or
  evaluating the architecture itself -> dev/architecture-design (this
  skill only draws the result); database ERDs -> dev/db-schema (Mermaid
  ERD); page wireframes/sitemaps -> brand/wireframe and
  landing/page-architect; data charts and dashboards -> the dataviz
  skill; the Forge complexity radar -> the Forge's built-in companion
  (core/forge/renderer.py).
allowed-tools: [Read, Write, Bash, AskUserQuestion]
metadata:
  origin: community
  source: https://github.com/tt-a1i/archify
  license: MIT
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` (and
> `mcp__graphify__query_graph` when configured) and cite `[[wikilinks]]`
> or graph nodes — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# /diagram — visual output for specs, plans, and systems

> **Agent:** Gabriel (Architect) + Paulo (Tech Lead) | **Framework:** Typed JSON IR, JSON Schema 2020-12, semantic layout gates

The user should SEE what will be built before it is built. This skill turns
a described system into a single self-contained HTML diagram (~530KB) with
theme switching, focused exploration, guided views, and PNG/SVG/WebM export
— no runtime dependencies, no telemetry. The only external reference is an
async Google Fonts stylesheet (JetBrains Mono) that degrades to system
monospace offline.

Absorbed from `tt-a1i/archify` v2.11.0 (MIT; portions Cocoon AI) and
maintained natively by ArkaOS. The upstream engine lives verbatim under
`vendor/`; you author the IR, the CLI does everything else. NEVER hand-edit
the generated HTML — fix the IR and re-deliver.

## Resolve `SKILL_DIR` (before any command)

Set `SKILL_DIR` to the absolute path of the directory containing THIS
SKILL.md (your harness showed it when you Read this file). Guard once:

```bash
[ -f "$SKILL_DIR/vendor/bin/archify.mjs" ] || { echo "archify.mjs not under $SKILL_DIR" >&2; exit 1; }
```

## Step 0 — preflight (silent on success)

```bash
command -v node >/dev/null && node -e 'process.exit(+process.versions.node.split(".")[0] >= 18 ? 0 : 1)'
```

Non-zero → stop and tell the user plainly: this skill needs Node.js >= 18
(`brew install node` on macOS, https://nodejs.org elsewhere). There is no
auto-install. When in doubt about the vendor payload itself, run
`node "$SKILL_DIR/vendor/bin/archify.mjs" doctor`.

## Step 1 — choose the diagram type

| Type | Best for | IR collections |
|------|----------|----------------|
| `architecture` | components, services, storage, trust boundaries | `components` + `connections` |
| `workflow` | CI/CD, approvals, tool calls, runbooks, plan phases | `nodes` (in `lanes`/`cols`) + `edges` |
| `sequence` | API calls, cache fallback, auth handshakes, async traces | `participants` + `messages` |
| `dataflow` | pipelines, lineage, PII paths, consumers | `nodes` + `flows` |
| `lifecycle` | states, retries, waits, terminal outcomes | `states` + `transitions` |

Unsure? Ask the recommender — it returns a bounded recipe:

```bash
node "$SKILL_DIR/vendor/bin/archify.mjs" guide "<one-line description of the situation>"
```

`examples` lists the 10 bundled sample IRs (`vendor/examples/*.json`) —
Read the one closest to your case as a structural reference.

## Step 2 — author the IR

Write `<slug>.<type>.json` to `/tmp` (or the session scratchpad). Every IR
needs `schema_version: 1`, `diagram_type: "<type>"`, and `meta.title`;
`meta` also takes `subtitle`, `visual_preset` (`classic|signal-flow|
blueprint`), `views` (max 5 guided views), and `animation: "trace"` (motion
is opt-in — leave it off unless asked). Keep one bounded view: 8–12 core
nodes, one primary path, supporting detail in `cards` instead of extra
edges.

For per-mode layout rules (lanes/cols, pinning, sequence ordering,
architecture `pos` grid), Read ONLY the relevant mode section of the
upstream deep guide at `$SKILL_DIR/vendor/SKILL.md` — do not load all 61KB.

Validate before delivering; error messages carry the offending node
`id`/`label` so you can fix the IR surgically:

```bash
node "$SKILL_DIR/vendor/bin/archify.mjs" validate <type> /tmp/<slug>.<type>.json --json
```

## Step 3 — deliver

```bash
node "$SKILL_DIR/vendor/bin/archify.mjs" deliver <type> /tmp/<slug>.<type>.json \
  /tmp/diagram-<slug>.html --json --open --quality standard
```

Deliver renders to a staging file, runs the artifact checks, atomically
renames on pass, and emits a JSON receipt. `--open` opens the artifact
natively; on a headless/remote session drop `--open` and reuse the Forge
Step 6a convention instead (`python -m http.server 0 --directory /tmp`,
then `open http://localhost:<port>/diagram-<slug>.html`). Use
`--quality showcase` only when the user asks for a presentation-grade
artifact — it fails on dense-but-legal topologies that `standard` accepts.

## Step 4 — read the receipt, report honestly

Parse the receipt JSON. On success report: artifact path,
`validation.checksPassed`/`checkCount`, `compositionProfile`/`Status`, and
`artifact.sha256`. On failure the receipt carries `ok: false`, a `stage`,
and the failing check — fix the IR accordingly and re-deliver. Two common
gates: **clean-flow** (an edge crossing an unrelated node is always a hard
failure — reroute or move the node) and **clean-label** (label mask too
close to another route — nudge the label or spread lanes).

## Step 5 — persistence (optional)

The HTML is an ephemeral deliverable in `/tmp`. When the diagram belongs to
a durable deliverable (a spec, a Forge plan, an SOP):

- save the IR JSON (small, regenerable source of truth) to the vault next
  to the note, e.g. `Projects/<name>/Specs/visuals/SPEC-<slug>.<type>.json`;
- record the artifact in the note's frontmatter `visuals:` list as
  `{type, ir, html, sha256}`;
- copy the HTML itself into the vault only when the user asks.

Ask before writing to the vault when the user did not request persistence.

## Output template

```
Diagram: <type> — <title>
IR:       /tmp/<slug>.<type>.json
Artifact: /tmp/diagram-<slug>.html  (sha256 <first-12>)
Checks:   <checksPassed>/<checkCount> passed · composition <status>
Opened:   <natively | http://localhost:<port>/… | not opened (reason)>
```

## Failure modes

- Node missing or < 18 → stop with the install hint; never degrade to
  ASCII art silently — say the visual companion is unavailable and why.
- `validate` fails → fix the IR at the reported `id`/`label`; re-validate.
- `deliver` fails a gate → the previous artifact (if any) is untouched;
  fix the IR, never the HTML.
- Dense topology keeps failing `showcase` → deliver with `standard` and
  say so; `standard` keeps renderable-but-dense layouts as warnings.

## Security

Local-only: the CLI spawns only `node` subprocesses; the generated HTML
makes no network calls (no fetch/eval/telemetry) except the optional
Google Fonts stylesheet, and the footer link (when present) carries only
the diagram type — never the title, graph, or source. Receipts include the
artifact sha256 for integrity. Vendored engine: `vendor/` (bin, renderers,
schemas, recipes, template, examples, test) — byte-identical to upstream
v2.11.0 except trims listed in `docs/THIRD-PARTY-NOTICES.md`.
