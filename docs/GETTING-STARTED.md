# Getting Started with ArkaOS

ArkaOS is an operating system for AI agent teams. 65 agents across 17 departments handle everything from writing code to building brands to planning finances. You talk in plain language, ArkaOS routes to the right team.

This guide gets you running in 5 minutes with real examples for developers, marketers, and founders.

## Quick Install (3 Steps)

### Step 1: Install ArkaOS

```bash
npx arkaos install
```

ArkaOS auto-detects your AI runtime (Claude Code, Codex CLI, Gemini CLI, or Cursor). To force a specific runtime:

```bash
npx arkaos install --runtime claude-code
```

### Step 2: Verify

```bash
npx arkaos doctor
```

You should see:

```
[PASS] Python 3.11+ found (3.12.4)
[PASS] Node.js 18+ found (20.11.0)
[PASS] ArkaOS installed at ~/.arkaos
[PASS] Hooks configured for claude-code
[PASS] Synapse engine responsive (74ms)
[PASS] Knowledge DB initialized
[PASS] 65 agents loaded
[PASS] 244 skills validated
[PASS] 24 workflows registered
All checks passed.
```

### Step 3: Set Up API Keys (Optional)

If you want knowledge base features (YouTube transcription, embeddings):

```bash
npx arkaos keys set OPENAI_API_KEY sk-proj-...
npx arkaos keys set ANTHROPIC_API_KEY sk-ant-...
```

Keys are stored encrypted at `~/.arkaos/keys.enc`. ArkaOS never sends keys to external services beyond the configured providers.

## Your First Session: Developer Fixing a Bug

Here is what a real session looks like. You open your terminal in a Laravel project and type:

```
The login form throws a 500 error when the email field is empty.
Fix this and add proper validation.
```

ArkaOS detects this is a development task. The Synapse engine injects context about your project (Laravel, PHP 8.3, your branch, your recent files). Paulo, the Tech Lead, takes over:

```
[DEV] Paulo (Tech Lead) routing to: Andre (Senior Backend Dev)

I've analyzed the issue. The LoginController@store method doesn't
validate the email field before passing it to the Auth facade.

Plan:
1. Add StoreLoginRequest with email/password validation rules
2. Update LoginController to use the Form Request
3. Add error response formatting for JSON clients
4. Write feature test for empty email scenario

Proceed? [Y/n]
```

You confirm, and Andre (that is the backend agent, yes, named after the creator) writes the fix, runs the tests, and the Quality Gate reviews everything before you see the final output.

## Your First Session: Marketer Creating a Campaign

You are planning an email launch for a new product. You type:

```
/mkt email-sequence "SaaS project management tool launching next month,
targeting startup founders, $29/month"
```

Luna, the Marketing Lead, assigns the work:

```
[MKT] Luna (Marketing Lead) building email sequence

Product: SaaS project management tool ($29/mo)
Audience: Startup founders
Framework: 6-email launch sequence (Brunson + AIDA)

Generating:
  1. Teaser email (curiosity hook)
  2. Problem agitation email
  3. Solution reveal email
  4. Social proof email
  5. Objection handling email
  6. Launch day email (urgency + CTA)

Each email includes: subject line (3 variants), preview text,
body copy, CTA button text.
```

The output lands in your Obsidian vault at `Marketing/Email-Sequences/saas-pm-tool-launch.md`, fully formatted and ready to paste into your email platform.

## Your First Session: Founder Validating a SaaS Idea

You have an idea but want to validate before building. You type:

```
/saas validate-idea "An AI tool that generates unit tests from
code comments. $19/mo for indie devs, $99/mo for teams."
```

Tiago, the SaaS Strategist, runs a structured validation:

```
[SAAS] Tiago (SaaS Strategist) starting validation

Running 5-point validation:
  1. Market sizing (TAM/SAM/SOM)
  2. Competitor analysis (existing solutions)
  3. Unit economics ($19 solo / $99 team)
  4. Technical feasibility assessment
  5. Go-to-market fit score

Results:

MARKET SIZE
  TAM: $4.2B (developer tools)
  SAM: $380M (AI testing tools)
  SOM: $3.8M (indie + small team segment)

COMPETITORS FOUND: 3 direct, 7 adjacent
  - CodiumAI (funded, freemium, broader scope)
  - Diffblue (enterprise, Java only)
  - Tabnine test generation (feature, not product)

UNIT ECONOMICS
  Solo plan: LTV $228 (12mo avg), CAC target < $57
  Team plan: LTV $1,188, CAC target < $297
  Verdict: Viable if CAC stays under $50 via content/PLG

OVERALL SCORE: 72/100 — Proceed with caution
  Strengths: Clear niche, good unit economics
  Risks: Well-funded competitors, narrow moat
  Recommendation: Build MVP for Python first, validate with
  100 beta users before expanding languages.
```

## Dashboard Setup

The dashboard gives you a visual interface for browsing agents, monitoring tasks, and managing your knowledge base.

```bash
npx arkaos dashboard
```

Opens at **http://localhost:3333**. The dashboard has 8 pages:

| Page | What You See |
|------|-------------|
| **Overview** | Agent count, skill count, active tasks, budget usage, system health |
| **Agents** | Browse all 65 agents with full behavioral DNA profiles (DISC, Enneagram, MBTI, Big Five) |
| **Commands** | Search all 244+ skills across 17 departments with usage examples |
| **Budget** | Token usage breakdown by department and tier, spending trends |
| **Tasks** | Active and completed background tasks (knowledge ingestion, analysis jobs) |
| **Knowledge** | Manage your indexed knowledge base, trigger new ingestions |
| **Personas** | Create custom personas, clone them as ArkaOS agents |
| **Health** | System checks, hook performance, Synapse layer timing |

The backend runs on port 3334 (FastAPI). The frontend is Nuxt 4 on port 3333.

## Knowledge Base Setup

ArkaOS has a vector database for semantic search. Index your Obsidian vault and other sources so agents can reference your notes, research, and documentation during tasks.

### Index Your Vault

```bash
npx arkaos index
```

This scans your Obsidian vault, chunks the content, generates embeddings, and stores them in the local vector DB (sqlite-vss). First run takes 1-2 minutes depending on vault size.

### Ingest Other Sources

Through the dashboard or API, you can ingest:

- **YouTube videos** -- downloads audio, transcribes with Whisper, indexes the transcript
- **PDFs** -- extracts text, chunks, and indexes
- **Web pages** -- fetches content, strips boilerplate, indexes
- **Audio files** -- transcribes and indexes

```bash
# Via API
curl -X POST http://localhost:3334/api/knowledge/ingest \
  -H "Content-Type: application/json" \
  -d '{"source": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "type": "youtube"}'
```

### Search Your Knowledge

```bash
npx arkaos search "authentication best practices"
```

Agents automatically search your knowledge base during tasks via Synapse layer L3.5. You do not need to manually search -- it happens behind the scenes.

## Project Initialization

When working on a specific codebase, initialize ArkaOS in that directory:

```bash
cd your-project
npx arkaos init
```

ArkaOS auto-detects your stack (Laravel, Nuxt, Next.js, React, Vue, Python, Go, Rust) and creates `.arkaos.json`:

```json
{
  "project": "your-project",
  "stack": {
    "framework": "laravel",
    "language": "php",
    "version": "11.x"
  },
  "department_defaults": {
    "dev": true,
    "ops": true
  }
}
```

This config feeds into Synapse layer L3, so agents always know your project context.

## Troubleshooting

### "Synapse engine not responsive"

The Python core might not be installed correctly:

```bash
cd ~/.arkaos
pip install -r requirements.txt
npx arkaos doctor
```

### "No agents loaded"

Check that agent YAML files exist:

```bash
ls ~/.arkaos/departments/dev/agents/
```

If empty, reinstall:

```bash
npx arkaos install --force
```

### "Hook not firing"

Verify hooks are registered for your runtime:

```bash
# For Claude Code, check settings
cat ~/.claude/settings.json | grep arkaos
```

Hooks should reference `user-prompt-submit-v2.sh`, `post-tool-use-v2.sh`, and `pre-compact-v2.sh`.

### "Knowledge search returns no results"

You need to index first:

```bash
npx arkaos index
```

If already indexed, check the DB:

```bash
curl http://localhost:3334/api/knowledge/stats
```

### Dashboard won't start

Make sure ports 3333 and 3334 are free:

```bash
lsof -i :3333
lsof -i :3334
```

Kill any conflicting processes and retry.

## Updating

```bash
npx arkaos update
```

Updates core, agents, skills, and workflows. Your configuration and knowledge base are preserved.

## Migrating from v1

If you used ArkaOS v1 (the bash-only version):

```bash
npx arkaos migrate
```

See [MIGRATION-V1-V2.md](MIGRATION-V1-V2.md) for the full migration guide.

## What You Get

| Component | Count |
|-----------|-------|
| Agents | 65 across 17 departments |
| Skills | 244+ backed by enterprise frameworks |
| Workflows | 24 with mandatory quality gates |
| Synapse layers | 9 for context injection |
| Dashboard pages | 8 for monitoring and management |
| Python CLI tools | 8 for quantitative analysis |
| Tests | 1836 (pytest) |

## Next Steps

- [COMMANDS.md](COMMANDS.md) -- every command with real examples
- [DEPARTMENTS.md](DEPARTMENTS.md) -- what each department does and when to use it
- [USE-CASES.md](USE-CASES.md) -- real scenarios organized by role
- [ARCHITECTURE.md](ARCHITECTURE.md) -- how the engine works under the hood
- [SKILL-STANDARD.md](SKILL-STANDARD.md) -- create your own skills
- [API.md](API.md) -- dashboard API reference
- [PERSONAS.md](PERSONAS.md) -- custom persona creation
