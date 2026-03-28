---
name: human-writing
description: >
  NON-NEGOTIABLE core writing quality gate. Enforces human-like writing across ALL ARKA OS output.
  Every text, copy, report, documentation, email, social post, and analysis must follow these rules.
  No AI-sounding patterns. Natural language with proper punctuation, tone matching, and flawless
  orthography. Applied automatically to all departments, all agents, all output types.
  This is a Constitution rule (NON-NEGOTIABLE #8) — violation aborts the operation.
---

# Human Writing Standard — ARKA OS Core Skill

All text produced by ARKA OS must read as if written by a skilled human professional. This is not a guideline; it is a NON-NEGOTIABLE rule enforced by the Constitution.

## Scope

This skill applies to **every agent**, **every department**, and **every output type**:
- Obsidian documents (reports, analyses, specs, ADRs)
- Terminal responses and summaries
- Social media posts, captions, stories
- Email drafts and templates
- Blog articles and landing page copy
- Code comments and commit messages
- PR descriptions and documentation
- Client-facing deliverables

## Rules

### 1. No Dashes as Sentence Connectors

Never use em-dashes (—), en-dashes (–), or hyphens (-) to join clauses or as sentence connectors. Use commas, semicolons, colons, periods, or conjunctions instead.

**Allowed exceptions:**
- Compound adjectives: "well-known", "open-source", "pre-commit"
- Technical terms: "CI/CD", "key-value", "x-axis"
- Numeric ranges: "2024-2025", "pages 10-15"

| Bad | Good |
|-----|------|
| The system is fast — it handles 10k requests/s | The system is fast. It handles 10k requests per second. |
| We need three things — speed, reliability, and cost | We need three things: speed, reliability, and cost. |
| The API failed — the token had expired | The API failed because the token had expired. |
| Users can choose dark mode — or stay with light | Users can choose dark mode, or stay with light. |

### 2. Language Tone and Idioms

Match the target language's natural register and idiomatic expressions. Never produce translated-sounding text.

**Portuguese:** Use Portuguese idioms, sentence rhythm, and phrasing. Do not translate English constructs literally.

| Bad (translated English) | Good (natural Portuguese) |
|--------------------------|---------------------------|
| "Isso é um jogo-mudador" | "Isto muda completamente o panorama" |
| "No fim do dia" (literal) | "Em última análise" / "Na prática" |
| "Nós estamos excitados para anunciar" | "Temos o prazer de anunciar" |

**English:** Use natural English rhythm. Avoid overly formal or stiff constructions when the context is conversational.

### 3. Perfect Accentuation and Spelling

Zero tolerance for orthographic errors. Every accent, cedilla, tilde, and diacritic must be correct.

**Portuguese examples:**
- ação (not acção or acao)
- é, está, será (accents on stressed syllables)
- informação, coração, posição (ção endings)
- três, através, português (circumflex and acute)
- começar, preço, serviço (cedilla)

**General:** When uncertain about spelling in any language, verify before outputting. An orthographic error in a client deliverable damages credibility.

### 4. Varied Sentence Structure

Mix short and long sentences. Avoid starting consecutive sentences with the same word. Use transitions naturally, not as formulaic connectors.

| Bad (repetitive) | Good (varied) |
|-------------------|---------------|
| "The API supports pagination. The API also supports filtering. The API returns JSON." | "The API supports pagination and filtering, returning results as JSON." |
| "We analyzed the data. We found three patterns. We recommend action." | "Our analysis revealed three patterns. Based on these findings, we recommend immediate action." |

### 5. Forbidden AI Patterns

These phrases and words signal AI-generated text. Never use them:

**Forbidden phrases:**
- "Let's dive in" / "Let's explore"
- "Here's a breakdown" / "Here's what you need to know"
- "In conclusion" / "To summarize"
- "It's worth noting" / "It's important to note"
- "At the end of the day"
- "Moving forward"
- "That being said"
- "Without further ado"
- "Game-changer"
- "Take it to the next level"
- "Unlock the potential"
- "In today's fast-paced world"

**Forbidden words (use alternatives):**
| Forbidden | Use Instead |
|-----------|-------------|
| leverage | use, apply, build on |
| utilize | use |
| streamline | simplify, speed up, reduce steps |
| robust | reliable, solid, thorough |
| seamless | smooth, effortless, uninterrupted |
| cutting-edge | modern, current, recent |
| empower | enable, support, give tools |
| synergy | collaboration, combined effect |
| holistic | complete, full, comprehensive |
| actionable insights | practical recommendations |

### 6. Concrete Over Abstract

Prefer specific facts, numbers, and examples over vague qualitative statements.

| Bad (vague) | Good (concrete) |
|-------------|-----------------|
| "Significantly improved performance" | "Reduced page load from 3.2s to 0.8s" |
| "Many users reported issues" | "47 users reported login failures in the last 24 hours" |
| "The solution is highly scalable" | "The solution handles up to 50k concurrent connections on a single instance" |

### 7. Active Voice by Default

Use active voice unless the subject is genuinely unknown or unimportant.

| Bad (passive) | Good (active) |
|---------------|---------------|
| "The feature was implemented by the team" | "The team implemented the feature" |
| "Errors are logged by the system" | "The system logs errors" |
| "The report will be generated" | "The system generates the report" |

**Acceptable passive:** "The server was compromised at 03:00 UTC" (attacker unknown).

## Enforcement

This skill is enforced through:
1. **Constitution L0 injection** — `human-writing` appears in every prompt's NON-NEGOTIABLE list
2. **Self-critique phase** — Agents review their own output against these rules before delivery
3. **Cross-department application** — Every department SKILL.md inherits this standard

Agents who produce text that violates these rules must revise before delivering output.
