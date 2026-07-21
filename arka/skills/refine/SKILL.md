---
name: arka-refine
description: >
  Prompt refiner for vague or domain-unfamiliar requests — turns a rough
  ask into a high-quality English prompt for the workflow by asking
  targeted questions first. For users who cannot phrase a clear brief in
  a domain they do not command (UI/design, infra, data modelling).
  TRIGGER: "/arka refine", "refina o prompt", "ajuda-me a pedir",
  "não sei explicar o que quero", and any vague request the /do
  orchestrator routes here (hook marker "[arka:refine-suggested]").
  SKIP: the request is already specific with clear scope and acceptance
  criteria -> /do dispatches directly; multi-agent planning of a known
  task -> arka-forge; requirements spec for code -> arka-dev-spec.
allowed-tools: [Read, AskUserQuestion, Skill]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` (and
> `mcp__graphify__query_graph` when configured) and cite `[[wikilinks]]`
> or graph nodes — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# /arka refine — turn a rough ask into a quality prompt

A vague request produces a vague build. This skill closes the gap by
asking about the TOPIC before any work starts, then compiling a precise
English prompt the workflow can execute. It exists for the case the
operator named: *"I don't understand UI/design, so I can never write an
input clear enough to build the right thing."*

## When it runs

- Explicitly: the user types `/arka refine <rough idea>`.
- Automatically: the `/do` orchestrator routes a vague request here
  BEFORE the department, or the UserPromptSubmit hook injects
  `[arka:refine-suggested] score=N` for a vague ask (high ambiguity and
  no concrete target named). Interposition is a suggestion — announce it
  and proceed only if refinement genuinely helps; a clear ask goes
  straight to `/do`.

## The refinement loop (conversation, not a form)

1. **Identify the topic and the domain.** Name what is being built and
   which domain expertise it needs (frontend/design, data, infra, copy…).
2. **Ask ONE substantive question per turn.** Open dialogue, never a
   multiple-choice menu as a substitute for conversation. Each question
   teaches while it asks — in a domain the user does not command, carry
   the vocabulary so they can answer:
   - **UI/design:** load `frontend-design` / `ui-ux-pro-max` first. Ask
     in their terms — visual tone (minimal / editorial / brutalist),
     density, a named benchmark to match ("closer to Linear or to
     Notion?"), light/dark, the one screen that matters most.
   - Other domains: mirror the same pattern with that field's vocabulary.
3. **Stop at ~5 questions.** Enough to remove ambiguity, not an
   interrogation. If the user says "just decide", pick sensible defaults
   and state them as assumptions.
4. **Compile the final prompt IN ENGLISH.** Show it in a fenced block:
   objective, scope, explicit non-goals, the named benchmark, acceptance
   criteria, and stack/constraints gathered. English is the workflow's
   working language regardless of the conversation language.
5. **Dispatch only after an explicit OK.** On approval, hand the compiled
   prompt to `/do` — which enters the normal 4-gate flow (the compiled
   prompt is the Gate-2 input; approval of the refinement is not approval
   of the eventual plan).

## Guardrails

- Never invent requirements the user did not confirm; a stated assumption
  is fine, a fabricated constraint is not.
- Never skip straight to building — the deliverable of THIS skill is the
  prompt, not the feature.
- Be critical: if the request is technically wrong or would ship a worse
  product, challenge it here (pushback protocol, `arkaos-not-yes-man`)
  before compiling.
- **Redesign asks have hard boundaries.** When the rough idea is
  "redesign X", the compiled prompt states them explicitly: preserve
  routes, information architecture, and copy INTENT — the visual layer is
  the scope; a full rebuild (structure or content changes) requires its
  own explicit confirmation, never rides along silently. The visual loop
  after dispatch belongs to `brand/design-review` (slop gates + register
  discipline in its `references/`).

## Related

- `frontend-design`, `ui-ux-pro-max` — design vocabulary for UI prompts.
- `/do` — receives the compiled prompt and routes it.
- `arka-dev-spec` — when the refined ask needs a full code spec at Gate 2.
- `arka-forge` — when the refined ask needs multi-agent planning.
