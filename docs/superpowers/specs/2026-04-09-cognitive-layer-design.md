# ArkaOS Cognitive Layer — Design Spec

**Date:** 2026-04-09
**Author:** Platform Team (Product Owner + Core Engineer + Skill Architect)
**Status:** Approved
**Version:** 1.0

## Overview

The Cognitive Layer adds three human-like cognitive capabilities to ArkaOS:

| Capability | Human Analogy | ArkaOS Feature |
|------------|---------------|----------------|
| **Long-term Memory** | Learn from experience | Institutional Memory (dual-write) |
| **Sleep/Dream** | Consolidate memories at night | Dreaming (nightly self-critique) |
| **Curiosity** | Stay current and informed | Research (adaptive daily intelligence) |

These three systems work together in a 24-hour cycle: raw capture during the day, consolidation and self-critique at 02:00, proactive research at 05:00, and intelligent briefing when the user starts the next day.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Storage strategy | Dual-write (Obsidian + Vector DB) | Redundancy — human-readable (Obsidian) + machine-searchable (Vector DB) |
| Scheduler | Python cross-platform daemon | Must work on macOS, Linux, Windows without OS-specific code paths |
| Research scope | Adaptive per user | Inferred from active projects, stacks, domains, business context |
| Memory capture | Raw during day, curated at night | Dreaming curates — avoids noise during active sessions |
| Nightly execution | 2 separate sessions | Dreaming at 02:00, Research at 05:00 — independent, fault-isolated |
| Claude permissions | `--dangerously-skip-permissions` | Full access for browser, web, file read/write — rules in prompt, not tool restrictions |

## 1. Architecture — Core Structure

New first-class layer in ArkaOS core, alongside Synapse, Workflow Engine, and Squad Framework.

```
core/cognition/
├── __init__.py
├── memory/                # Dual-write engine
│   ├── writer.py          # Unified interface: write() → Obsidian + Vector DB
│   ├── obsidian.py        # Obsidian writer (markdown, frontmatter, linking)
│   ├── vector.py          # Vector DB writer (reuses core/knowledge/vector_store.py)
│   └── schemas.py         # Pydantic models for memory entries
├── capture/               # Raw capture during sessions
│   ├── collector.py       # Hook integration — captures session events
│   └── store.py           # SQLite store for raw captures (~/.arkaos/captures.db)
├── dreaming/              # Nightly consolidation
│   ├── dreamer.py         # Orchestrator: review day, categorize, consolidate
│   ├── curator.py         # Filter noise, rank by value, merge duplicates
│   └── compiler.py        # Generate final knowledge entries (dual-write)
├── research/              # Adaptive research
│   ├── profiler.py        # Infer user's research profile from context
│   ├── researcher.py      # Research orchestrator per topic
│   └── digest.py          # Generate intelligence briefing (dual-write)
└── scheduler/             # Cross-platform scheduler
    ├── daemon.py           # Scheduler loop (Python, cross-platform)
    ├── platform.py         # Auto-install as system service (launchd/systemd/taskscheduler)
    └── schedules.yaml      # Schedule configuration
```

### Key Principle

`memory/writer.py` is the **single interface** — any component that wants to persist knowledge calls `writer.write()` and dual-write happens transparently. Dreaming and Research are consumers of this interface.

## 2. Institutional Memory — Dual-Write Engine

### 2.1 Daily Flow (Raw Capture)

During each Claude Code session, the `PreCompact` hook captures:

| Data | Source | Example |
|------|--------|---------|
| Technical decisions | Conversation | "Used Sanctum for auth in this project" |
| Implemented solutions | Git diff | "Migration with soft deletes + observer" |
| Discovered patterns | Code | "This project uses Repository pattern" |
| Errors and fixes | Tool output | "CORS fix: trusted_proxies + middleware" |
| Configurations | Files | "Redis queue driver, Horizon dashboard" |

Raw captures go to `~/.arkaos/captures.db` (SQLite):

```python
class RawCapture(BaseModel):
    id: str                    # UUID
    timestamp: datetime
    session_id: str            # Claude Code session
    project_path: str
    project_name: str
    category: str              # decision|solution|pattern|error|config
    content: str               # Raw text
    context: dict              # Metadata (stack, files touched, etc.)
```

### 2.2 Nightly Flow (Curated Dual-Write)

Dreaming reads raw captures and produces curated **Knowledge Entries**:

```python
class KnowledgeEntry(BaseModel):
    id: str
    title: str                 # "Laravel Sanctum Auth Setup"
    category: str              # pattern|anti_pattern|solution|architecture|config|lesson|improvement
    tags: list[str]            # ["laravel", "auth", "sanctum", "api"]
    stacks: list[str]          # ["laravel", "php"]
    content: str               # Formatted markdown
    source_project: str        # Origin project
    applicable_to: str         # "any" | "laravel" | "vue+nuxt" etc.
    confidence: float          # 0-1, grows with reuse
    times_used: int            # Increments when reused
    created_at: datetime
    updated_at: datetime
```

The `applicable_to` field is crucial — it's what allows the system to know that when auth is requested in a new Laravel project, there's already a validated solution from another project.

The `confidence` field starts at 0.5 and increases each time the same solution is successfully applied in another project. Knowledge reused 3+ times becomes a "validated pattern".

### 2.3 Dual-Write Targets

**Obsidian** — Creates/updates note in:

```
WizardingCode Internal/ArkaOS/Knowledge Base/
├── Patterns/              # Solutions that work
├── Anti-Patterns/         # Errors to avoid
├── Solutions/             # Specific fixes
├── Architecture/          # Structural decisions
├── Lessons/               # Daily learnings
├── Self-Critique/         # Honest self-evaluation
└── Improvements/          # "Next time..."
```

Each note has YAML frontmatter with all KnowledgeEntry fields, readable markdown content, and backlinks to related projects.

**Vector DB** — Embeds content via existing `core/knowledge/embedder.py` and stores in SQLite-VSS. Enables semantic search — when working on a project and needing "how did we do API auth", vector search finds the entry even with different wording.

### 2.4 Query Integration

When working on a project and context suggests similar prior work:

```
Synapse L1 (keyword) → detects topic
    → Vector DB semantic search
    → Match with KnowledgeEntry (confidence > 0.5)
    → Inject in context: "Prior knowledge found: [title] (confidence: 85%, used 3x)"
```

## 3. Dreaming — Reflective Consciousness

Runs daily at 02:00. A headless Claude Code session executing a 7-phase pipeline.

### 3.1 Pipeline

```
Phase 1: Total Collection
    ├── Raw captures from the day (~/.arkaos/captures.db)
    ├── Git log + diffs from ALL active projects (last 24h)
    ├── claude-mem complete timeline for the day
    ├── Claude Code sessions (what was requested, what was done)
    └── Errors found, retries, abandoned approaches

Phase 2: Critical Analysis
    ├── For each task of the day, evaluate:
    │   ├── "Did I do this the best possible way?"
    │   ├── "Was there a simpler approach?"
    │   ├── "Did I repeat an error I should already know to avoid?"
    │   ├── "Does the code follow the project's patterns?"
    │   └── "How long did it take vs how long should it have taken?"
    ├── Classify each decision:
    │   ├── Good decision — document as validated pattern
    │   ├── Acceptable but improvable — document better alternative
    │   └── Error — document what went wrong and why
    └── Output: learnings list with severity

Phase 3: Recurring Pattern Detection
    ├── Compare today's errors with previous errors (vector search)
    │   └── If same error type > 2x → create "Anti-Pattern" entry
    ├── Compare today's solutions with previous solutions
    │   └── If same pattern > 2x → promote to "Validated Pattern"
    ├── Detect inconsistencies between projects
    │   └── "In Rockport used X, in ClubeFashion used Y for same problem"
    └── Output: patterns, anti-patterns, inconsistencies

Phase 4: Curation and Consolidation
    ├── Group into Knowledge Entries
    ├── Merge with existing knowledge
    ├── Create "Lessons Learned" entries
    │   └── "Never do X because Y" with real context
    ├── Create "Self-Improvement" entries
    │   └── "Next time asked for Z, do A instead of B"
    └── Output: categorized KnowledgeEntries

Phase 5: Dual-Write
    ├── writer.write() for each entry
    └── Categories in Obsidian (Patterns, Anti-Patterns, Solutions,
        Architecture, Lessons, Self-Critique, Improvements)

Phase 6: Report + Evolution Metrics
    ├── Daily report in Obsidian (Dreaming/YYYY-MM-DD.md)
    ├── Quality score for the day (0-100)
    ├── Trending: improving or repeating errors?
    ├── Top 3 things learned today
    ├── Top 3 things done wrong and how to avoid
    └── Comparison with previous days (evolution)

Phase 7: Strategic Reflection (Proactive Insights)
    ├── For each project worked on today:
    │   ├── Review ALL decisions made
    │   ├── Question with business perspective:
    │   │   ├── "Does this solution serve the end user or just the dev?"
    │   │   ├── "Did we consider all business edge cases?"
    │   │   ├── "Is there an approach that generates more revenue/conversion?"
    │   │   └── "What do competitors do here?"
    │   ├── Cross-reference with Research (if available):
    │   │   └── "Saw that Shopify launched X — does it affect this decision?"
    │   ├── Generate Actionable Insights
    │   └── Dual-write insights
    └── Output: ProjectInsights per project
```

### 3.2 Actionable Insight Model

```python
class ActionableInsight(BaseModel):
    id: str
    project: str               # "fovory"
    trigger: str               # "dreaming" | "research"
    date_generated: datetime
    category: str              # "business" | "technical" | "ux" | "strategy"
    severity: str              # "rethink" | "improve" | "consider"
    title: str                 # "Offer model missing key conversion fields"
    description: str           # Complete analysis of the problem
    recommendation: str        # What to do concretely
    context: str               # What led to this insight
    status: str                # "pending" | "presented" | "accepted" | "dismissed"
    presented_at: datetime | None
```

### 3.3 Insight Storage

`~/.arkaos/insights.db` — Dedicated SQLite for pending insights. Separate from knowledge base because they have a different lifecycle — they are **temporary and actionable**, not permanent knowledge.

### 3.4 Insight Presentation

When user enters a project (via `cd` or ecosystem command), the `CwdChanged` hook checks for pending insights:

```
CwdChanged detects project "fovory"
    → Query insights.db WHERE project="fovory" AND status="pending"
    → If insights exist:
        → Inject into session context via Synapse
```

User sees on project open:

```
Reflexoes pendentes do Dreaming (2026-04-09):

1. [business] Offer model — repensar
   O modelo de offers nao considera quantidade minima por SKU
   nem pricing tiers por volume. Recomendo adicionar antes de
   ir para producao.

2. [technical] Sync retry — melhorar
   Backoff fixo pode causar thundering herd. Usar exponential
   backoff com jitter (padrao validado do Rockport).

Queres que desenvolva algum destes pontos?
```

### 3.5 Insight Lifecycle

```
Generated (dreaming/research)
    → pending
        → Presented when user opens project
            → presented
                → User accepts → accepted → generates task or implements
                → User dismisses → dismissed → feedback to dreaming
                    (learns this type of insight is not valued)
```

The `dismissed` status is important — if the user dismisses many insights of a certain type, Dreaming learns not to generate them. **The system adapts to what the user values.**

### 3.6 Execution Rules

```markdown
# Embedded in dreaming.md prompt

## ALLOWED
- Read any file from any project
- Read git logs and diffs
- Search the web (WebSearch, Firecrawl)
- Write to Obsidian vault
- Write to ~/.arkaos/ (captures, insights, logs)
- Use browser for research
- Read online documentation

## PROHIBITED
- npm install, composer require, pip install (zero installations)
- git commit, git push (zero code changes)
- Create/modify code files in projects
- Execute migrations or destructive commands
- Send emails, messages, or communications
- Access production APIs
```

### 3.7 Failure Handling

| Scenario | Behavior |
|----------|----------|
| Session fails mid-run | Raw captures remain intact, next night reprocesses |
| No captures for the day | Phase 1 detects empty day, generates "no activity" report, exits |
| Vector DB unavailable | Write only to Obsidian, flag for retry next night |
| Obsidian vault not mounted | Write only to vector DB, flag for retry |
| Duplicate detected | Merge with existing entry, increment confidence |

## 4. Research — Proactive Intelligence

Runs daily at 05:00. Independent session from Dreaming.

### 4.1 Research Profile (Adaptive)

`profiler.py` analyzes user context and generates a **Research Profile**:

```python
class ResearchProfile(BaseModel):
    stacks: list[str]              # Inferred from active projects
    domains: list[str]             # Inferred from project types
    tools: list[str]               # Tools in use
    business_interests: list[str]  # Inferred from user type
    competitors: list[str]         # Relevant competitors
    topics: list[ResearchTopic]    # Concrete research topics
```

The profile is **adaptive per user** — inferred from active projects, stacks, domains, and accumulated memories. A user with one Laravel e-commerce project gets focused research. A power user like the ArkaOS owner gets full-spectrum intelligence.

### 4.2 Example Profile (ArkaOS Owner)

```yaml
stacks:
  - Laravel (10+, 11, 12 — releases, packages, security)
  - Nuxt 3/4 (migration guides, new features)
  - Vue 3 (ecosystem, Pinia, VueUse)
  - Python (Pydantic, FastAPI, AI libs)
  - React/Next.js (App Router, Server Components)
  - Node.js/Bun (runtime updates)

domains:
  - E-commerce (Shopify, marketplace trends, conversion)
  - Energy sector (EDP, smart grid, regulation)
  - Media/Streaming (ZugaTV, content delivery)
  - AI/ML (LLM updates, agent frameworks, fine-tuning)
  - Fashion retail (ClubeFashion, CRM, loyalty)

tools:
  - Claude Code (releases, new features, SDK updates)
  - ComfyUI (nodes, workflows, models)
  - Anthropic API (new capabilities, pricing)
  - Shopify (API changes, app ecosystem)

business:
  - AI agent market (competitors, funding, trends)
  - Micro-SaaS opportunities
  - WizardingCode positioning
  - Revenue opportunities

competitors:
  - Cursor, Windsurf, Cline, Aider (AI coding)
  - CrewAI, AutoGen, LangGraph (agent frameworks)
  - Devin, Factory, Cognition (AI dev agents)
```

### 4.3 Research Pipeline

```
Phase 1: Profile Update
    ├── Re-read active projects and stacks
    ├── Check for new projects or stacks since yesterday
    └── Regenerate topic list if context changed

Phase 2: Research by Topic (parallelizable)
    ├── For each topic, use Firecrawl + WebSearch:
    │   ├── Official release notes (GitHub releases, changelogs)
    │   ├── Relevant blog posts (Laravel News, Vue blog, etc.)
    │   ├── Security advisories (npm, composer, pip)
    │   ├── Community discussions (Reddit, HN, Discord)
    │   ├── YouTube (new tutorials, conferences)
    │   └── Competitor updates (product launches, funding)
    └── Output: raw findings per topic

Phase 3: Relevance Filtering
    ├── Classify each finding:
    │   ├── URGENT — security patch, breaking change
    │   ├── IMPORTANT — relevant new feature, opportunity
    │   ├── INFORMATIVE — trend, interesting article
    │   └── NOISE — not relevant, already known
    └── Discard noise, sort by impact

Phase 4: Learning (THE DIFFERENTIATOR)
    ├── For each relevant finding:
    │   ├── Read and understand (not just list)
    │   ├── Relate to active projects
    │   │   └── "Nuxt 4 migration path → affects ZugaTV and Rockport"
    │   ├── Identify concrete actions
    │   │   └── "Laravel 12 deprecates X → check ClubeFashion and Fovory"
    │   └── Create KnowledgeEntry with application context
    └── Dual-write everything learned

Phase 5: Cross-reference with Dreaming
    ├── Read tonight's Dreaming insights
    ├── Reinforce or add context to existing insights
    │   └── "Dreaming flagged offer model gaps + Research found
    │        Shopify B2B best practices → stronger recommendation"
    └── Generate new insights from research findings

Phase 6: Daily Intelligence Briefing
    ├── Generate report in Obsidian:
    │   WizardingCode Internal/ArkaOS/Research/YYYY-MM-DD.md
    ├── Sections:
    │   ├── ACTION REQUIRED (security, breaking changes)
    │   ├── OPPORTUNITIES (features, market)
    │   ├── LEARNINGS (trends, insights)
    │   └── COMPETITOR WATCH
    └── Flag urgent items for next session presentation
```

### 4.4 Execution Rules

Same as Dreaming — full `--dangerously-skip-permissions` access with prompt-level restrictions (read and write knowledge only, never install or modify code).

## 5. Scheduler — Cross-Platform Daemon

### 5.1 Architecture

```python
class ArkaScheduler:
    schedules: list[Schedule]     # Loaded from schedules.yaml
    platform: PlatformAdapter     # macOS/Linux/Windows
    lock: FileLock                # Single instance only
    log: RotatingFileLog          # ~/.arkaos/logs/scheduler.log

    def run(self):
        # Acquire lock (prevent duplicates)
        # Load schedules
        # Loop: check every minute if any schedule should run
        # Execute via subprocess:
        #   claude -p "$(cat <prompt_file>)" --dangerously-skip-permissions
```

### 5.2 Schedule Configuration

```yaml
# ~/.arkaos/schedules.yaml
schedules:
  dreaming:
    command: "dreaming"
    prompt_file: "~/.arkaos/cognition/prompts/dreaming.md"
    time: "02:00"
    timezone: "auto"          # Detect from system
    enabled: true
    retry_on_fail: true
    max_retries: 2
    timeout_minutes: 60

  research:
    command: "research"
    prompt_file: "~/.arkaos/cognition/prompts/research.md"
    time: "05:00"
    timezone: "auto"
    enabled: true
    retry_on_fail: true
    max_retries: 2
    timeout_minutes: 90

  # Extensible — users can add their own
```

### 5.3 Platform Adapters

```python
class PlatformAdapter(ABC):
    @abstractmethod
    def install_service(self) -> bool: ...
    @abstractmethod
    def uninstall_service(self) -> bool: ...
    @abstractmethod
    def is_running(self) -> bool: ...
    @abstractmethod
    def start(self) -> bool: ...
    @abstractmethod
    def stop(self) -> bool: ...

class MacOSAdapter(PlatformAdapter):
    # ~/Library/LaunchAgents/com.arkaos.scheduler.plist
    # launchctl load/unload

class LinuxAdapter(PlatformAdapter):
    # ~/.config/systemd/user/arkaos-scheduler.service
    # systemctl --user enable/start/stop

class WindowsAdapter(PlatformAdapter):
    # schtasks /create with daily trigger
    # Or pythonw.exe as background process
```

### 5.4 Installer Integration

`npx arkaos install` gains a new step:

```
npx arkaos install
  Hooks configured
  Skills deployed
  Scheduler installed              <-- NEW
    macOS: LaunchAgent registered
    Linux: systemd user service enabled
    Windows: Scheduled task created
  Scheduler will run dreaming at 02:00 and research at 05:00
```

### 5.5 CLI Management

```bash
arkaos scheduler status       # State, next runs, last logs
arkaos scheduler start        # Start manually
arkaos scheduler stop         # Stop
arkaos scheduler run dreaming # Execute immediately (for debug/test)
arkaos scheduler run research # Execute immediately
arkaos scheduler logs         # View recent logs
arkaos scheduler edit         # Open schedules.yaml in editor
```

### 5.6 File Structure

```
~/.arkaos/
├── logs/
│   ├── scheduler.log              # Daemon activity
│   ├── dreaming/
│   │   ├── YYYY-MM-DD.log         # Full session output
│   │   └── YYYY-MM-DD.json        # Structured metrics
│   └── research/
│       ├── YYYY-MM-DD.log
│       └── YYYY-MM-DD.json
├── cognition/
│   ├── prompts/
│   │   ├── dreaming.md            # Complete Dreaming prompt
│   │   └── research.md            # Complete Research prompt
│   └── profiles/
│       └── research-profile.yaml  # Inferred user profile
├── captures.db                    # Raw captures of the day
├── insights.db                    # Actionable pending insights
└── schedules.yaml                 # Schedule configuration
```

### 5.7 Security

| Risk | Mitigation |
|------|------------|
| Claude session with full permissions | Rules in prompt — read/write knowledge only, never install or modify code |
| Scheduler runs as user | Never root/admin, always user-level service |
| Injectable prompts | Prompts are local files, not external input |
| Credentials | Scheduler stores no tokens — uses existing Claude CLI auth |
| Runaway sessions | `timeout_minutes` kills session if exceeded |

## 6. Integration — 24-Hour Cycle

```
09:00 --- User opens terminal --------------------------------
  |
  |  SessionStart hook:
  |    +-- Logo ArkaOS + greeting
  |    +-- Check pending insights from Dreaming
  |    |   "3 pending reflections for Fovory"
  |    +-- Check urgent alerts from Research
  |        "Laravel security patch -- affects 3 projects"
  |
09:05 --- User works -----------------------------------------
  |
  |  During each session:
  |    +-- PreCompact hook -> raw capture to captures.db
  |    +-- CwdChanged hook -> present project insights
  |    +-- Normal work with all departments
  |
  |  When entering project with insights:
  |    "Pending reflections from Dreaming:
  |     1. [business] Offer model -- rethink fields
  |     2. [technical] Sync retry -- use exponential backoff
  |     Want me to elaborate?"
  |
  |  User responds:
  |    +-- "yes, #1" -> insight.status = accepted -> executes
  |    +-- "not relevant" -> insight.status = dismissed -> learns
  |    +-- (ignores) -> keeps pending for next session
  |
19:00 --- User closes terminal --------------------------------
  |
  |  Last captures processed
  |
02:00 --- DREAMING --------------------------------------------
  |
  |  Headless Claude Code session:
  |    Phase 1: Collect everything from the day
  |    Phase 2: Critical analysis (what was done well/poorly)
  |    Phase 3: Detect recurring patterns
  |    Phase 4: Curate -> Knowledge Entries
  |    Phase 5: Dual-write (Obsidian + Vector DB)
  |    Phase 6: Report + evolution metrics
  |    Phase 7: Strategic reflection -> Actionable Insights
  |
  |  Output:
  |    Obsidian: Knowledge Base/ (patterns, anti-patterns, lessons)
  |    Obsidian: Dreaming/YYYY-MM-DD.md (report)
  |    Vector DB: embeddings of everything
  |    insights.db: actionable insights per project
  |    Log: ~/.arkaos/logs/dreaming/YYYY-MM-DD.log
  |
05:00 --- RESEARCH --------------------------------------------
  |
  |  Headless Claude Code session:
  |    Phase 1: Update research profile
  |    Phase 2: Research all topics (web, GitHub, blogs)
  |    Phase 3: Filter by relevance and urgency
  |    Phase 4: Learn (read, understand, relate)
  |    Phase 5: Cross-reference with Dreaming insights
  |    Phase 6: Intelligence Briefing
  |
  |  Output:
  |    Obsidian: Research/YYYY-MM-DD.md (briefing)
  |    Vector DB: new knowledge indexed
  |    insights.db: new insights (security, opportunities)
  |    Log: ~/.arkaos/logs/research/YYYY-MM-DD.log
  |
09:00 --- Next day -- User opens terminal ----------------------
  |
  |  ArkaOS is smarter than yesterday.
  |  Knows things it didn't know.
  |  Has formed opinions on yesterday's decisions.
  |  Has alerts about urgent matters.
  |  Ready.
```

## 7. Evolution Over Time

```
Week 1:   Knowledge Base nearly empty. Generic insights.
Week 4:   ~100 Knowledge Entries. Starts detecting patterns.
Month 3:  ~500 entries. Knows patterns of all projects.
          "We've done this 5x, the validated pattern is X."
Month 6:  ~1500 entries. Calibrated self-critique.
          Almost never repeats errors. High-value insights.
Year 1:   Complete institutional knowledge base.
          ArkaOS knows as much about the projects as the user.
          Any new project benefits from EVERYTHING learned.
```

## 8. Obsidian Output Structure

```
WizardingCode Internal/ArkaOS/
├── Knowledge Base/
│   ├── Patterns/              # Validated solutions
│   ├── Anti-Patterns/         # Errors to avoid
│   ├── Solutions/             # Specific fixes
│   ├── Architecture/          # Structural decisions
│   ├── Lessons/               # Daily learnings
│   ├── Self-Critique/         # Honest self-evaluation
│   └── Improvements/          # "Next time..."
├── Dreaming/
│   ├── 2026-04-09.md          # Daily dreaming reports
│   └── ...
├── Research/
│   ├── 2026-04-09.md          # Daily intelligence briefings
│   └── ...
├── Roadmap.md
├── Releases/
└── Audits/
```

## 9. Dependencies

| Component | Dependency | Status |
|-----------|-----------|--------|
| Vector DB | `core/knowledge/vector_store.py` (SQLite-VSS) | Exists |
| Embedder | `core/knowledge/embedder.py` | Exists |
| Obsidian | MCP integration via .mcp.json | Exists |
| Web Research | Firecrawl MCP + WebSearch | Exists |
| Hooks | `config/hooks/` (5 hooks) | Exists — needs extension |
| claude-mem | Timeline, observations | Exists |
| Claude CLI | `claude -p` headless mode | Exists |
| Schedule lib | Python `schedule` package | New dependency |

## 10. Scope Boundaries

### In Scope
- `core/cognition/` Python module (memory, capture, dreaming, research, scheduler)
- Prompt files for Dreaming and Research sessions
- Hook extensions (PreCompact for capture, CwdChanged for insights)
- Platform adapters (macOS, Linux, Windows)
- Installer integration
- CLI commands (`arkaos scheduler *`)
- Obsidian output structure
- SQLite databases (captures.db, insights.db)

### Out of Scope
- Dashboard UI for Cognitive Layer (future — v3)
- Real-time streaming of Dreaming/Research progress (future)
- Multi-user / team knowledge sharing (future)
- Custom research sources beyond web (future — RSS, API feeds)
- Automated code fixes from insights (insights recommend, human decides)
