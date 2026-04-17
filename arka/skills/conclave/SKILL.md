---
name: arka-conclave
description: >
  The Conclave — Personal AI Advisory Board. 20 real-world advisor personas
  matched to your behavioral DNA. 5 aligned (think like you) + 5 contrarian
  (challenge your blind spots). Profiling via 17 structured questions.
allowed-tools: [Read, Write, Edit, Bash, Agent, AskUserQuestion]
---

# The Conclave — `/arka conclave`

Your personal board of AI advisors. Each based on a real person with codified mental models, thinking styles, and decision frameworks.

## Commands

| Command | Description |
|---------|-------------|
| `/arka conclave` | Start profiling (first time) or view board |
| `/arka conclave profile` | Re-run 17-question DNA profiling |
| `/arka conclave view` | Display your current advisory board |
| `/arka conclave ask "<question>"` | Ask all 10 advisors a question |
| `/arka conclave advisor <name>` | Deep dive on one advisor's mental models |
| `/arka conclave debate "<topic>"` | Watch advisors debate a topic |
| `/arka conclave aligned` | Show only your 5 aligned advisors |
| `/arka conclave contrarian` | Show only your 5 contrarian advisors |

## First Run: DNA Profiling

When `/arka conclave` runs first time (no profile):

**Step 1: Welcome** — explain 5-min profiling, ask if ready.

**Step 2: Ask 17 Questions** — one at a time via `AskUserQuestion`:

| # | Framework | Reveals |
|---|-----------|---------|
| 1-4 | DISC | How you ACT in work situations |
| 5-8 | Enneagram | What DRIVES you (core motivations/fears) |
| 9-13 | Big Five | Your personality on 5 continuous scales |
| 14-17 | MBTI | How you THINK and process decisions |

**Step 3: Score and Build Profile**

1. Load `core.conclave.profiler` module
2. Create `ProfilingSession`, process each answer
3. Call `build_profile_from_session()` → `UserProfile`
4. Call `match_advisors()` → assemble the board
5. Save to `~/.arkaos/conclave-profile.json`

**Step 4: Present the Board** — show user's DNA (DISC, Enneagram, Big Five, MBTI) + 5 aligned + 5 contrarian advisors with match %, mental models, and signature questions.

## Ask Command: `/arka conclave ask "<question>"`

1. Load `~/.arkaos/conclave-profile.json`
2. For each of 10 advisors, generate response **in character** (3-5 sentences, their mental models, their questions)
3. Aligned first, then contrarian
4. End with synthesis: where they agree/disagree + what to consider

**System prompt approach per advisor:**

```
You are {name}, {title}. You think using: {mental_models}.
Your style: {communication_style}. Your framework: {decision_framework}.
Respond in 3-5 sentences as {name} would. Be specific. Channel their actual thinking.
```

## Advisor Deep Dive: `/arka conclave advisor <name>`

Full advisor profile: all 4 DNA frameworks, mental models with key questions, communication style, decision framework, sources, why matched (aligned/contrarian, score, dimension comparison).

## Debate: `/arka conclave debate "<topic>"`

1. Present topic to all 10 advisors
2. Each gives 2-3 sentence take
3. Identify disagreements between aligned and contrarian groups
4. Structured output: opening positions → key disagreements → synthesis

## Profile Persistence

- Profile: `~/.arkaos/conclave-profile.json`
- Re-profile: `/arka conclave profile` overwrites existing
- Auto-loaded on subsequent calls

## The 20 Advisors

| # | Name | DNA | Specialty |
|---|------|-----|-----------|
| 1 | Charlie Munger | C+D, 5w6, ISTJ | Inversion, mental models |
| 2 | Ray Dalio | D+C, 5w6, INTJ | Principles, radical transparency |
| 3 | Naval Ravikant | C+D, 5w6, INTP | Leverage, first principles |
| 4 | Elon Musk | D+C, 8w7, INTJ | First principles physics, 10x |
| 5 | Steve Jobs | D+I, 3w4, ENTJ | Simplicity, taste, A-players |
| 6 | Simon Sinek | I+S, 2w1, ENFJ | Golden Circle, purpose |
| 7 | Brene Brown | I+S, 4w3, ENFP | Vulnerability, courage |
| 8 | Peter Drucker | C+S, 1w9, INTJ | Effectiveness, MBO |
| 9 | Jeff Bezos | D+C, 3w2, ENTJ | Day 1, working backwards |
| 10 | Derek Sivers | S+C, 9w1, INFP | Hell Yeah or No, simplicity |
| 11 | Nassim Taleb | D+C, 8w7, INTJ | Antifragility, barbell |
| 12 | Seth Godin | I+C, 7w6, ENFP | Purple Cow, permission |
| 13 | Patrick Lencioni | I+S, 2w1, ENFJ | Five Dysfunctions, trust |
| 14 | Warren Buffett | S+C, 5w6, ISTJ | Circle of competence, moats |
| 15 | Reed Hastings | D+I, 7w8, ENTJ | Talent density, freedom |
| 16 | Marty Cagan | C+I, 1w2, INTJ | Empowered teams, discovery |
| 17 | Alex Hormozi | D+C, 8w7, ENTJ | Value equation, Grand Slam |
| 18 | April Dunford | C+I, 5w6, INTP | Positioning, 5 components |
| 19 | James Clear | S+C, 1w9, INFJ | Atomic Habits, systems |
| 20 | Tim Ferriss | D+I, 7w8, ENTP | Fear-setting, 80/20 |

Full details + challenge dimensions: `references/advisors.md`

## Advisor Response Examples

**Charlie Munger (aligned):** "What's the downside? Am I treating the symptom or the disease?"

**Simon Sinek (contrarian):** "What's the WHY? Will people follow because they want to, or because they have to?"

**Ray Dalio (aligned):** "What is the principle here? Is this based on data or opinion?"

**Brene Brown (contrarian):** "Am I being brave enough to be vulnerable here?"