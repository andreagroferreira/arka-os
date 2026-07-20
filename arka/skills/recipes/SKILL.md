---
name: arka-recipes
description: >
  Validated recipe library — QG-approved feature builds captured with
  their reference files, reused across projects instead of re-derived
  from docs. Lists, shows, and applies recipes (Laravel login, payment
  integration, standard UI patterns…).
  TRIGGER: "/arka recipes", "que receitas temos", "apply the <x> recipe",
  "reusa a receita", "há uma receita para isto?", "recipe for <feature>".
  SKIP: capturing a NEW recipe from an approved deliverable -> the
  Quality Gate skill step 7 proposes it; short reusable text hints ->
  the Pattern Library (record_pattern); planning a task -> arka-forge.
allowed-tools: [Read, Bash]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` (and
> `mcp__graphify__query_graph` when configured) and cite `[[wikilinks]]`
> or graph nodes — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# /arka recipes — reuse validated feature builds

A recipe is a QG-approved feature captured with its reference files
(`~/.arkaos/recipes/<slug>/{RECIPE.md, recipe.json, files/}`). Where a
pattern card is a text hint, a recipe is proven code to adapt — so
"Laravel login" is a known, validated build, not a from-scratch
re-derivation. Synapse L7.6 auto-injects matching recipes as
`[recipes:N]` on every prompt; these commands drive them explicitly.

## Commands

| Command | Description |
|---------|-------------|
| `/arka recipes list` | List captured recipes (slug · stack · name). |
| `/arka recipes show <slug>` | Print a recipe's full metadata (recipe.json). |
| `/arka recipes apply <slug>` | Read RECIPE.md + files/ as prior art and adapt to the current project through the normal 4-gate flow. |

Backed by `core.knowledge.recipes_cli`:

    arka-py -m core.knowledge.recipes_cli list
    arka-py -m core.knowledge.recipes_cli show <slug>

## Applying a recipe (never copy-paste blind)

`apply <slug>` is prior-art-driven adaptation, not a code dump:

1. Read `~/.arkaos/recipes/<slug>/RECIPE.md` (problem, approach,
   decisions) and the files under `files/`.
2. Read `recipe.json` `apply_notes` — the recorded per-project
   adaptation contract (namespaces, models, config to swap).
3. Enter the normal flow: Gate 2 presents a plan that maps the recipe
   onto THIS project's stack and conventions; the user approves it like
   any other build. The recipe informs the plan; it does not bypass the
   gates.
4. Implement, run the recipe's acceptance criteria as the test floor,
   pass the Quality Gate.

## Capture is elsewhere

New recipes are proposed by the Quality Gate (step 7) on an APPROVED
reusable feature and captured fail-closed (every field sanitized,
refused without a redaction config). This skill only consumes them.

## Related

- Pattern Library (Synapse L7.5) — short reusable text hints.
- `arka-dev-spec` / `/dev feature` — the flow an `apply` runs through.
- `arka-forge` — planning when the adaptation is complex.
