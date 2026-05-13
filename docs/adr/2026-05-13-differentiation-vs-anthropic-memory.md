---
title: Differentiation strategy if Anthropic ships a competing memory layer
date: 2026-05-13
status: accepted
deciders: André + Tomas (Strategy) + Marco (CTO) + Sofia (COO) + Marta (CQO)
tags: [adr, strategy, anthropic, differentiation, cognitive-layer, north-star]
---

# ADR — Differentiation vs Anthropic memory layer

## Status

Accepted (2026-05-13 Conclave Phase 3, Decision 4).

## Context

Anthropic already ships memory features on claude.ai and is likely to
extend them to Claude Code within 6–12 months. Probability assessed as
**high** by the Conclave. If Anthropic ships a competing memory layer
that is free, zero-config, and integrated directly into Claude Code,
roughly **70 % of ArkaOS users could disable our cognitive retrieval
and use the upstream feature** (Marta's risk read).

This ADR fixes the differentiation strategy **before** Anthropic
announces, so that when they do, the response is a paste-ready
positioning rather than a panicked rewrite.

## Decision

ArkaOS's cognitive layer differentiates on **three structural axes**
that Anthropic cannot easily neutralise without rewriting their own
product economics. We commit to keeping each axis defensible and
loudly visible in our brand surface.

### Pillar 1 — Local-only

ArkaOS Local runs the entire cognitive stack on the user's machine
(Ollama + sqlite-vec + Obsidian vault, per the north-star ADR
`2026-05-13-arkaos-local-personal-agi.md`). Anthropic is cloud-native;
*"your data never leaves your machine"* is structurally ours, not
theirs. Privacy regulation tailwinds (EU AI Act, EU Data Act, US state
laws) compound the advantage over time.

### Pillar 2 — Vault-integrated

ArkaOS reads from and writes to the user's Obsidian vault — their
own organised knowledge base — and uses that as the substrate for
retrieval and dreaming. Anthropic does not, and almost certainly will
not, touch the vault. Their memory layer can only see what passes
through Claude conversations; ours sees everything the user has ever
written, decided, or planned.

### Pillar 3 — Multi-runtime

ArkaOS is runtime-agnostic. The same cognitive layer powers Claude
Code, Codex, Gemini CLI, and Cursor. Anthropic only serves Claude.
Any user who runs even one non-Anthropic workflow keeps ArkaOS in
play.

## Response playbook when Anthropic ships

1. **Within 24 hours of announcement**, publish a blog post and pinned
   tweet using the three pillars above as the spine. The differentiation
   is structural, not reactive — we own the framing.
2. **Update homepage hero** to lead with privacy framing: *"Your AI
   memory should not be SaaS."*
3. **Update `arka doctor`** to inform users that Anthropic memory is
   active *and* explain that ArkaOS continues to add local + vault +
   cross-runtime value on top.
4. **Do not match feature parity for the sake of parity.** Anthropic
   memory and ArkaOS cognitive layer are different products. Trying to
   reproduce their UX inside ArkaOS dilutes the structural advantage.

## Indicators that this ADR has aged poorly (re-open trigger)

- Anthropic ships a local-only Claude Code memory mode.
  *(They will not — contradicts business model — but if they do, re-open.)*
- Anthropic adds first-class Obsidian vault integration.
  *(They will not — too niche for their roadmap.)*
- Anthropic acquires Cursor or strikes exclusive deals that effectively
  make Claude the only mainstream IDE runtime.
  *(Watch quarterly.)*

If any of the three above happen, this ADR is re-opened and the
Conclave reconvenes within 7 days.

## Cross-references

- North-star: `docs/adr/2026-05-13-cognitive-layer-pivot-to-hooks.md`
  (the architectural decision that made local-only viable)
- Strategy doc: `~/.arkaos/plans/2026-05-13-arkaos-local-personal-agi-strategy.md`
- Memory: `[[project_arkaos_local_personal_agi]]`
- Conclave Phase 3 session: 2026-05-13 evening
