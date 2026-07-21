---
name: arka-human-writing
description: >
  Human-writing standard, constitution MUST rule #8 (reviewed by
  Eduardo, Copy Director Tier 0) — bans AI-sounding patterns and
  enforces natural language, tone matching, and flawless orthography
  across ALL ArkaOS output; violation aborts the operation.
  TRIGGER: load BEFORE writing any prose a human will read —
  copy, reports, docs, emails, posts, landing pages, PR descriptions,
  client deliverables; "escreve", "redige", "texto", "copy", "artigo",
  "email", "post", "write", "draft", "reescreve isto", "soa a IA",
  "sounds like AI", "make it sound human" — don't skip because the
  text looks short.
  SKIP: code-only diffs with no user-facing prose; the APPROVED/REJECTED
  copy verdict — arka-quality (Quality Gate, Eduardo) wins
  (standard applies WHILE writing, the review judges after).
metadata:
  origin: community
  source: https://github.com/coreyhaines31/marketingskills
  license: MIT
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

Portuguese output has its own AI-tell catalogue: `references/pt-pt-anti-slop.md`.

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

### 8. No Formulaic Structures

Structural patterns are stronger AI tells than any single word: they
survive synonym swaps. Banned: binary contrasts ("not X, it's Y"),
negative listing, dramatic fragmentation, rhetorical setups ("What if I
told you..."), false agency (inanimate nouns doing human verbs: "the data
tells us", "the decision emerges"; name the human), narrator-from-a-distance,
Wh-word sentence openers, and lazy extremes (every/always/never doing
vague work). Full catalogue with fixes: `references/structural-patterns.md`.
Phrase-level companions (throat-clearing openers, emphasis crutches,
meta-commentary, vague declaratives): `references/anti-slop-phrases.md`.

## Self-Editing Before Delivery

The rules above govern how to write. This section governs how to review your
own prose before it ships, which is where most AI-tells get caught. Run a
focused pass per dimension instead of one vague read. After each pass,
recheck the earlier ones so a fix does not reintroduce an old problem.

### The Seven Sweeps

A sequential editing method for high-stakes prose (landing pages, launch
emails, sales pages). Each sweep looks for one thing:

1. **Clarity:** can the reader understand it? Cut confusing structures, unclear pronouns, insider jargon, and buried points.
2. **Voice and tone:** does it sound consistent? Catch drift from casual to corporate, mixed references, and accidental mood shifts.
3. **So what:** does every claim answer "why should I care?" Bridge each feature to a benefit the reader wants.
4. **Prove it:** is every claim supported? Replace "trusted by thousands" and "industry-leading" with named proof, numbers, and specifics.
5. **Specificity:** is it concrete? Swap vague verbs for numbers, timeframes, and examples. "Save 4 hours a week" beats "save time."
6. **Heightened emotion:** does it make the reader feel something? Make the pain and the desired outcome vivid without manipulation.
7. **Zero risk:** is every barrier to action removed near the CTA? Answer objections, add trust signals, and state the next step plainly.

For a final QA pass, work the full checklist in
[references/checklist.md](references/checklist.md).

### Quick-Pass Checks

When a full seven-sweep review is not warranted, run these faster checks.

**Cut these words:** very, really, extremely, incredibly (weak intensifiers);
just, actually, basically (filler); "in order to" (use "to"); "that" when it
adds nothing; "things" and "stuff" (too vague).

**Watch for:** adverbs (cut by default; one survives only if deleting it
changes the meaning), passive voice (switch to active per Rule 7), and
nominalizations (turn the noun back into a verb, so "make a decision"
becomes "decide").

**Structural sweep (Rule 8):** no Wh-word sentence openers; no "not X,
it's Y" contrasts; name the human behind inanimate verbs (false agency);
cut throat-clearing openers ("Here's the thing:", "It turns out"); rewrite
anything that sounds like a pull-quote; default to two list items, a third
must earn its place; vary paragraph endings instead of closing every one
punchily.

**Sentence level:** one idea per sentence, varied length, important
information first, no more than three conjunctions, usually under 25 words.

**Paragraph level:** one topic per paragraph, 2 to 4 sentences for web,
strong opening sentences, and enough white space to stay scannable.

### Slop Score

A fast quantitative gate, complement to the Seven Sweeps. Rate the draft
1 to 10 on each dimension; below 35/50, revise before delivering.

| Dimension | Question |
|-----------|----------|
| Directness | Statements or announcements? |
| Rhythm | Varied or metronomic? |
| Trust | Respects reader intelligence? |
| Authenticity | Sounds human? |
| Density | Anything cuttable? |

Eduardo (Quality Gate) applies the same rubric to changed copy: below
35/50 on COPY-scope prose is a blocker.

## Plain-English Alternatives

Rule 5 already bans the worst AI words and maps their replacements. Extend it
with these common offenders:

| Weak or complex | Plain |
|-----------------|-------|
| Implement | Set up |
| Facilitate | Help |
| Innovative | New |
| Cutting-edge | New, modern |

The full substitution list lives in
[references/plain-english-alternatives.md](references/plain-english-alternatives.md).

## Refreshing Existing Content

Prose decays. Stats go stale, examples age, and brand voice drifts across
edits by different hands. When traffic is declining, data is old, or the
product has changed, refresh rather than rewrite. The refresh checklist, the
refresh-versus-rewrite matrix, and a cadence guide are in
[references/content-refresh.md](references/content-refresh.md).

## Enforcement

Constitution L0 injection · Self-critique phase before delivery · Cross-department application. Agents who violate must revise before delivering.