---
name: arka-human-writing
description: >
  Human-writing standard, constitution MUST rule (Constitution rule #8, reviewed
  by Eduardo, Copy Director Tier 0) — bans AI-sounding patterns and
  enforces natural language, tone matching, and flawless orthography
  across ALL ArkaOS output; violation aborts the operation.
  TRIGGER: load BEFORE writing any prose a human will read or ship —
  copy, reports, documentation, emails, social posts, landing pages,
  PR descriptions, client deliverables, analyses; user words "escreve",
  "redige", "texto", "copy", "artigo", "email", "post", "write",
  "draft", "reescreve isto", "soa a IA", "sounds like AI", "make it
  sound human". Applies automatically to every department, agent, and
  output type — don't skip because the text looks short.
  SKIP: code-only diffs with no user-facing prose (identifiers and
  syntax are not prose); the final APPROVED/REJECTED copy verdict —
  arka-quality (Quality Gate, Eduardo) wins there; this skill is the
  standard applied WHILE writing, not the review that judges it.
---

# Human Writing Standard — ARKA OS Core Skill

All text produced by ARKA OS must read as if written by a skilled human professional. Constitution MUST rule #8 — violation aborts the operation.

## Scope

Applies to every agent, every department, every output: Obsidian docs, terminal responses, social posts, email drafts, blog articles, landing page copy, code comments, PR descriptions, client deliverables.

## Rules

### 1. No Dashes as Sentence Connectors

Never use em-dashes (—), en-dashes (–), or hyphens (-) to join clauses. Use commas, semicolons, colons, periods, or conjunctions.

**Allowed:** Compound adjectives (well-known, open-source), technical terms (CI/CD, key-value), numeric ranges (2024-2025).

### 2. Language Tone and Idioms

Match the target language's natural register. Portuguese: use Portuguese idioms, not translated English constructs. English: natural rhythm, avoid overly formal constructions.

### 3. Perfect Accentuation and Spelling

Zero tolerance for orthographic errors. Portuguese: ação, é, três, começar. When uncertain, verify before outputting.

### 4. Varied Sentence Structure

Mix short and long sentences. Avoid starting consecutive sentences with the same word. Use transitions naturally.

### 5. Forbidden AI Patterns

**Forbidden phrases:** "Let's dive in", "Here's a breakdown", "In conclusion", "It's worth noting", "At the end of the day", "Moving forward", "Game-changer", "Unlock the potential", etc.

**Forbidden words:** leverage → use | utilize → use | streamline → simplify | robust → reliable | seamless → smooth | empower → enable

Full list with alternatives: `references/forbidden-patterns.md`

### 6. Concrete Over Abstract

Specific facts, numbers, examples over vague statements. "Reduced load from 3.2s to 0.8s" beats "significantly improved performance."

### 7. Active Voice by Default

Use active voice unless subject is genuinely unknown. "The team implemented the feature" beats "The feature was implemented by the team."

## Enforcement

Constitution L0 injection · Self-critique phase before delivery · Cross-department application. Agents who violate must revise before delivering.