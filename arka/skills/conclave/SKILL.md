---
name: arka-conclave
description: >
  The Conclave — Personal AI Advisory Board. 20 real-world advisor personas
  matched to your behavioral DNA. 5 aligned (think like you) + 5 contrarian
  (challenge your blind spots). Profiling via 17 structured questions.
allowed-tools: [Read, Write, Edit, Bash, Agent, AskUserQuestion]
---

# The Conclave — `/arka conclave`

> Your personal board of AI advisors. Each one based on a real person,
> with codified mental models, thinking styles, and decision frameworks.

## Commands

| Command | Description |
|---------|-------------|
| `/arka conclave` | Start profiling (first time) or view your board |
| `/arka conclave profile` | Re-run the 17-question DNA profiling |
| `/arka conclave view` | Display your current advisory board |
| `/arka conclave ask "<question>"` | Ask all 10 advisors a question |
| `/arka conclave advisor <name>` | Deep dive on one advisor's mental models |
| `/arka conclave debate "<topic>"` | Watch your advisors debate a topic |
| `/arka conclave aligned` | Show only your 5 aligned advisors |
| `/arka conclave contrarian` | Show only your 5 contrarian advisors |

## First Run: DNA Profiling

When the user runs `/arka conclave` for the first time (no profile exists):

### Step 1: Welcome
```
Welcome to The Conclave — your personal AI advisory board.

I'll ask you 17 questions to understand how you think, decide, and lead.
This takes about 5 minutes. Your answers determine which advisors match
your thinking style and which ones will challenge your blind spots.

Ready? Let's begin.
```

### Step 2: Ask Questions (one at a time)

Use AskUserQuestion tool for each question. Present the options clearly.
Group by framework with brief context:

**Questions 1-4: How you ACT (DISC)**
- These reveal your behavioral style in work situations

**Questions 5-8: What DRIVES you (Enneagram)**
- These reveal your core motivations and fears

**Questions 9-13: Your TRAITS (Big Five)**
- These reveal your personality on 5 continuous scales

**Questions 14-17: How you THINK (MBTI)**
- These reveal how you process information and decide

### Step 3: Score and Build Profile

After all 17 answers:

1. Load `core.conclave.profiler` module
2. Create `ProfilingSession`, process each answer
3. Call `build_profile_from_session()` to get `UserProfile`
4. Call `match_advisors()` to assemble the board
5. Save profile to `~/.arkaos/conclave-profile.json`

### Step 4: Present the Board

Display the board using this format:

```markdown
## Your Behavioral DNA

| Framework | Result | Meaning |
|-----------|--------|---------|
| DISC | D+C (Driver-Analyst) | Direct, data-driven, results-focused |
| Enneagram | 5w6 (The Investigator) | Seeks competence, fears being incapable |
| Big Five | O:78 C:85 E:35 A:40 N:25 | Curious, disciplined, introverted, direct, calm |
| MBTI | INTJ (The Architect) | Strategic vision + efficient execution |

## Your Advisory Board

### ALIGNED — Think Like You (amplify your strengths)

**1. Charlie Munger** — Vice Chairman, Berkshire Hathaway
   Match: 96% | DNA: C+D, 5w6, ISTJ
   Models: Inversion, Latticework, Circle of Competence
   "What's the downside? Am I treating the symptom or the disease?"

**2. Ray Dalio** — Founder, Bridgewater Associates
   Match: 94% | DNA: D+C, 5w6, INTJ
   Models: Principles-Based Decisions, Radical Transparency
   "What is the principle? Is this based on data or opinion?"

[... 3 more aligned ...]

### CONTRARIAN — Challenge Your Blind Spots

**1. Simon Sinek** — Author, Start With Why
   Match: 35% | DNA: I+S, 2w1, ENFJ
   Challenge: You focus on WHAT and HOW. Simon forces you to ask WHY.
   "What's the WHY? Will people follow because they want to?"

**2. Brene Brown** — Research Professor
   Match: 38% | DNA: I+S, 4w3, ENFP
   Challenge: You value control and competence. Brene values vulnerability.
   "Am I being brave enough to be vulnerable?"

[... 3 more contrarian ...]
```

## Ask Command: `/arka conclave ask "<question>"`

When the user asks a question to the board:

1. Load the saved ConclaveBoard
2. For each of the 10 advisors, generate a response **in character**:
   - Use the advisor's communication style
   - Apply their mental models to the question
   - Ask their key questions
   - Keep each response to 3-5 sentences
3. Present aligned responses first, then contrarian
4. End with a synthesis: "Where they agree, where they disagree, and what you should consider"

### Advisor Response Template

For each advisor, use this system prompt approach:

```
You are {name}, {title}. You think using these mental models:
{mental_models}

Your communication style: {communication_style}
Your decision framework: {decision_framework}

When asked a question, respond in 3-5 sentences as {name} would.
Use your mental models. Ask your key questions. Be specific to THIS situation.
Do NOT be generic. Channel {name}'s actual thinking.
```

## Advisor Deep Dive: `/arka conclave advisor <name>`

Show the full advisor profile:
- Behavioral DNA (all 4 frameworks)
- All mental models with descriptions and key questions
- Communication style
- Decision framework
- Sources (books, talks)
- Why they were matched (aligned or contrarian, score, dimension comparison)

## Debate: `/arka conclave debate "<topic>"`

1. Present the topic to all 10 advisors
2. Each advisor gives their 2-3 sentence take
3. Identify disagreements between aligned and contrarian groups
4. Present the debate as a structured discussion:
   - Opening positions (each advisor)
   - Key disagreements (which advisors clash and why)
   - Synthesis (what the user should take from both sides)

## Profile Persistence

- Save: `~/.arkaos/conclave-profile.json`
- Contains: UserProfile (DNA) + ConclaveBoard (matched advisors)
- Re-profile: `/arka conclave profile` overwrites existing
- Profile is loaded automatically on subsequent `/arka conclave` calls

## The 20 Advisors

| # | Name | DNA | Specialty |
|---|------|-----|-----------|
| 1 | Charlie Munger | C+D, 5w6, ISTJ | Inversion, mental models, competence |
| 2 | Ray Dalio | D+C, 5w6, INTJ | Principles, transparency, systems |
| 3 | Naval Ravikant | C+D, 5w6, INTP | Leverage, specific knowledge, first principles |
| 4 | Elon Musk | D+C, 8w7, INTJ | First principles (physics), 10x thinking |
| 5 | Steve Jobs | D+I, 3w4, ENTJ | Simplicity, taste, A-players |
| 6 | Simon Sinek | I+S, 2w1, ENFJ | Golden Circle, purpose, infinite game |
| 7 | Brene Brown | I+S, 4w3, ENFP | Vulnerability, courage, shame resilience |
| 8 | Peter Drucker | C+S, 1w9, INTJ | Effectiveness, MBO, knowledge workers |
| 9 | Jeff Bezos | D+C, 3w2, ENTJ | Day 1, working backwards, two-way doors |
| 10 | Derek Sivers | S+C, 9w1, INFP | Hell Yeah or No, opposites, simplicity |
| 11 | Nassim Taleb | D+C, 8w7, INTJ | Antifragility, barbell, skin in the game |
| 12 | Seth Godin | I+C, 7w6, ENFP | Purple Cow, permission, smallest audience |
| 13 | Patrick Lencioni | I+S, 2w1, ENFJ | Five Dysfunctions, trust, healthy conflict |
| 14 | Warren Buffett | S+C, 5w6, ISTJ | Circle of competence, margin of safety, moats |
| 15 | Reed Hastings | D+I, 7w8, ENTJ | Talent density, freedom, context not control |
| 16 | Marty Cagan | C+I, 1w2, INTJ | Empowered teams, discovery before delivery |
| 17 | Alex Hormozi | D+C, 8w7, ENTJ | Value equation, Grand Slam Offer, Core Four |
| 18 | April Dunford | C+I, 5w6, INTP | Positioning, 5 components, Obviously Awesome |
| 19 | James Clear | S+C, 1w9, INFJ | Atomic Habits, systems over goals, 1% better |
| 20 | Tim Ferriss | D+I, 7w8, ENTP | Fear-setting, 80/20, minimum effective dose |
