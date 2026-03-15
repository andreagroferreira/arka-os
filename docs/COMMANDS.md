# ARKA OS — Command Reference

Every command available in ARKA OS, organized by department. This is your cheat sheet.

---

## How Commands Work

ARKA OS has two types of commands:

1. **Terminal commands** — Run these in your regular terminal (outside Claude Code). They start with `arka`.
2. **Department commands** — Run these inside Claude Code (after typing `arka` to start a session). They start with a `/` prefix.

---

## Terminal Commands

Run these directly in your terminal:

| Command | What It Does |
|---------|-------------|
| `arka` | Start ARKA OS (opens Claude Code with everything loaded) |
| `arka --version` | Show the installed version number |
| `arka update` | Update ARKA OS to the latest version |
| `arka skill install <url>` | Install an external skill from GitHub |
| `arka skill list` | Show all installed external skills |
| `arka skill remove <name>` | Uninstall an external skill |
| `arka skill update <name>` | Update an external skill to its latest version |
| `arka skill create <name>` | Create a new skill project from the template |

---

## System Commands — `/arka`

Core system commands for managing ARKA OS itself.

| Command | What It Does | Example |
|---------|-------------|---------|
| `/arka help` | Show all commands from every department | `/arka help` |
| `/arka standup` | Daily summary of projects, tasks, meetings, and emails | `/arka standup` |
| `/arka status` | Show system status — version, departments, integrations, skills | `/arka status` |
| `/arka monitor` | Check for updates to your tech stack and dependencies | `/arka monitor` |
| `/arka onboard <project>` | Set up a new project with context files and Obsidian page | `/arka onboard client-website` |

---

## Development — `/dev`

Build software. Your development team: Marco (CTO), Andre (Senior Developer), Rita (QA), Carlos (DevOps).

### Project Scaffolding

| Command | What It Does | Example |
|---------|-------------|---------|
| `/dev scaffold laravel <name>` | Create a Laravel 11 project | `/dev scaffold laravel my-api` |
| `/dev scaffold nuxt-saas <name>` | Create a Nuxt 3 SaaS dashboard | `/dev scaffold nuxt-saas my-dashboard` |
| `/dev scaffold nuxt-landing <name>` | Create a Nuxt 3 landing page | `/dev scaffold nuxt-landing product-page` |
| `/dev scaffold nuxt-docs <name>` | Create a Nuxt 3 documentation site | `/dev scaffold nuxt-docs api-docs` |
| `/dev scaffold vue-saas <name>` | Create a Vue 3 SaaS dashboard | `/dev scaffold vue-saas admin-panel` |
| `/dev scaffold vue-landing <name>` | Create a Vue 3 landing page | `/dev scaffold vue-landing company-site` |
| `/dev scaffold full-stack <name>` | Create a Laravel + Nuxt full-stack project | `/dev scaffold full-stack my-app` |
| `/dev scaffold react <name>` | Create a React project | `/dev scaffold react my-react-app` |
| `/dev scaffold nextjs <name>` | Create a Next.js project | `/dev scaffold nextjs my-nextjs-app` |

### Development Workflow

Commands that modify code (`feature`, `api`, `debug`, `refactor`, `db`) automatically run inside a **git worktree** — an isolated branch and working directory. This keeps your main branch clean. After the work is done, you can review, create a PR, or merge.

| Command | What It Does | Worktree? | Example |
|---------|-------------|:---------:|---------|
| `/dev feature <description>` | Implement a new feature | Yes | `/dev feature "add user registration"` |
| `/dev api <spec>` | Generate API endpoints + tests + docs | Yes | `/dev api "payments endpoints"` |
| `/dev debug <issue>` | Diagnose and fix a bug | Yes | `/dev debug "login returns 500"` |
| `/dev refactor <target>` | Refactor code with quality gates | Yes | `/dev refactor "controllers"` |
| `/dev db <description>` | Database schema + migrations | Yes | `/dev db "add user roles table"` |
| `/dev review` | Get a code review from the CTO | No | `/dev review` |
| `/dev test` | Run tests and get a quality report | No | `/dev test` |
| `/dev deploy <environment>` | Deploy to staging or production | No | `/dev deploy staging` |
| `/dev docs` | Generate technical documentation | No | `/dev docs` |
| `/dev stack-check` | Check for dependency updates | No | `/dev stack-check` |

**Branch naming:** Features and APIs use `feature/`, bug fixes use `fix/`, refactors use `refactor/`.

### Integration Management

| Command | What It Does | Example |
|---------|-------------|---------|
| `/dev mcp apply <profile>` | Apply an integration profile to the current project | `/dev mcp apply laravel` |
| `/dev mcp add <name>` | Add a single integration to the current project | `/dev mcp add sentry` |
| `/dev mcp list` | Show all available integrations | `/dev mcp list` |
| `/dev mcp status` | Show which integrations are active in the current project | `/dev mcp status` |

### External Skills (inside Claude Code)

| Command | What It Does | Example |
|---------|-------------|---------|
| `/dev skill install <url>` | Install a skill from GitHub | `/dev skill install https://github.com/user/skill` |
| `/dev skill list` | List installed external skills | `/dev skill list` |
| `/dev skill remove <name>` | Uninstall a skill | `/dev skill remove geo-seo` |
| `/dev skill create <name>` | Create a new skill from the template | `/dev skill create my-skill` |

---

## Marketing — `/mkt`

Create marketing content. Your team member: Luna (Content Creator).

| Command | What It Does | Example |
|---------|-------------|---------|
| `/mkt social <platform> <topic>` | Generate social media posts for a specific platform | `/mkt social instagram "product launch"` |
| `/mkt calendar <period>` | Create a content calendar | `/mkt calendar "March 2026"` |
| `/mkt reels <topic>` | Script short-form video (Reels, TikTok, Shorts) | `/mkt reels "5 coding tips"` |
| `/mkt email <type> <topic>` | Write email sequences | `/mkt email welcome "new subscribers"` |
| `/mkt landing <product>` | Create landing page copy | `/mkt landing "online course"` |
| `/mkt ads <platform> <product>` | Write ad copy | `/mkt ads facebook "SaaS tool"` |
| `/mkt affiliate <analysis>` | Analyze affiliate marketing opportunities | `/mkt affiliate "tech products"` |
| `/mkt blog <topic>` | Write a blog article | `/mkt blog "remote work tips"` |
| `/mkt copy-analysis <url>` | Analyze existing copy and suggest improvements | `/mkt copy-analysis "https://example.com"` |
| `/mkt brand-guide` | Create or update brand guidelines | `/mkt brand-guide` |
| `/mkt audit` | Run a complete marketing audit | `/mkt audit` |

---

## E-commerce — `/ecom`

Manage and grow online stores. Your team member: Ricardo (E-commerce Manager).

| Command | What It Does | Example |
|---------|-------------|---------|
| `/ecom audit <store-url>` | Full store audit — UX, SEO, performance, content, conversion | `/ecom audit "https://mystore.com"` |
| `/ecom product <listing>` | Optimize a product listing (title, description, images, SEO) | `/ecom product "wireless headphones"` |
| `/ecom pricing <product>` | Analyze pricing and recommend strategy | `/ecom pricing "premium plan"` |
| `/ecom competitors <niche>` | Run competitive analysis for your niche | `/ecom competitors "organic skincare"` |
| `/ecom launch <product>` | Create a complete product launch plan | `/ecom launch "new sneaker line"` |
| `/ecom ads <product>` | Create ad campaigns for products | `/ecom ads "summer collection"` |
| `/ecom email-flows` | Design automated email sequences (welcome, abandoned cart, etc.) | `/ecom email-flows` |
| `/ecom report` | Generate e-commerce performance report | `/ecom report` |

---

## Finance — `/fin`

Manage money. Your team member: Helena (CFO).

| Command | What It Does | Example |
|---------|-------------|---------|
| `/fin report <type>` | Generate financial reports | `/fin report monthly` |
| `/fin forecast <period>` | Create revenue and expense forecasts | `/fin forecast "Q2 2026"` |
| `/fin budget <project>` | Build a budget for a project or the company | `/fin budget "mobile app development"` |
| `/fin negotiate <context>` | Prepare negotiation strategy with talking points | `/fin negotiate "office lease renewal"` |
| `/fin pitch <context>` | Prepare investor pitch with financial projections | `/fin pitch "Series A fundraise"` |
| `/fin analysis <topic>` | Run financial analysis | `/fin analysis "hiring vs outsourcing"` |
| `/fin investment <opportunity>` | Analyze an investment opportunity | `/fin investment "commercial real estate"` |
| `/fin portfolio` | Review investment portfolio | `/fin portfolio` |
| `/fin invoice <client>` | Generate an invoice | `/fin invoice "Acme Corp"` |

---

## Operations — `/ops`

Run the business day-to-day. Your team member: Sofia (COO).

### Tasks & Communication

| Command | What It Does | Example |
|---------|-------------|---------|
| `/ops tasks` | View and manage tasks | `/ops tasks` |
| `/ops email <type>` | Draft a professional email | `/ops email follow-up "project status"` |
| `/ops calendar` | View upcoming events and meetings | `/ops calendar` |
| `/ops meeting <topic>` | Prepare meeting agenda and materials | `/ops meeting "quarterly review"` |
| `/ops standup` | Run a daily standup review | `/ops standup` |

### Business Operations

| Command | What It Does | Example |
|---------|-------------|---------|
| `/ops invoice <client>` | Generate and send invoices | `/ops invoice "Client Co"` |
| `/ops automate <process>` | Design a process automation | `/ops automate "client onboarding"` |
| `/ops report` | Generate operational report | `/ops report` |
| `/ops onboard <client>` | Create client onboarding workflow | `/ops onboard "New Client Inc"` |

### Messaging Channels

| Command | What It Does | Example |
|---------|-------------|---------|
| `/ops channel add <platform> <id>` | Add a messaging channel | `/ops channel add slack C0123456789` |
| `/ops channel list` | Show all configured channels | `/ops channel list` |
| `/ops channel remove <platform>` | Remove a messaging channel | `/ops channel remove discord` |
| `/ops notify <message>` | Send message to default channel | `/ops notify "Deploy complete"` |
| `/ops broadcast <message>` | Send message to all channels | `/ops broadcast "System maintenance at 10pm"` |

---

## Strategy — `/strat`

Plan and analyze. Your team member: Tomas (Chief Strategist).

| Command | What It Does | Example |
|---------|-------------|---------|
| `/strat brainstorm <topic>` | Structured brainstorm from 5 perspectives | `/strat brainstorm "enter European market"` |
| `/strat market <industry>` | Full market analysis with sizing | `/strat market "edtech in Portugal"` |
| `/strat prospect <criteria>` | Find and analyze potential clients | `/strat prospect "SaaS companies, 10-50 employees"` |
| `/strat compete <competitor>` | Competitive intelligence report | `/strat compete "Competitor Inc"` |
| `/strat swot <business>` | SWOT analysis | `/strat swot "our mobile app"` |
| `/strat evaluate <idea>` | Evaluate a business idea | `/strat evaluate "AI writing assistant"` |
| `/strat pivot <context>` | Analyze strategic pivot options | `/strat pivot "from B2C to B2B"` |
| `/strat roadmap <product>` | Create a product or business roadmap | `/strat roadmap "SaaS platform"` |
| `/strat trends <industry>` | Analyze industry trends | `/strat trends "artificial intelligence"` |

---

## Knowledge Base — `/kb`

Learn and build expertise. Your team member: Clara (Knowledge Curator).

| Command | What It Does | Example |
|---------|-------------|---------|
| `/kb learn <source>` | Learn from a YouTube video, article, or text | `/kb learn "https://youtube.com/watch?v=..."` |
| `/kb search <query>` | Search your knowledge base | `/kb search "marketing funnels"` |
| `/kb persona list` | List all expert personas in your vault | `/kb persona list` |
| `/kb persona <name>` | View a specific persona's full profile | `/kb persona "Seth Godin"` |
| `/kb topic <name>` | View or create a topic page | `/kb topic "content marketing"` |
| `/kb generate <persona> <topic>` | Generate content in a persona's style | `/kb generate "Seth Godin" "email marketing"` |

### How Learning Works

When you use `/kb learn` with a YouTube video:
1. The video is downloaded and the audio is extracted
2. The audio is transcribed to text
3. Five AI analysts process the transcript simultaneously — extracting strategies, frameworks, voice patterns, philosophy, and key quotes
4. A persona profile is created (or updated) in your Obsidian vault
5. The raw transcript is saved for reference

For articles and text, the content is analyzed directly without the download step.

---

## Quick Reference

The most useful commands at a glance:

| I want to... | Command |
|-------------|---------|
| See all commands | `/arka help` |
| Start a new project | `/dev scaffold <type> <name>` |
| Get a code review | `/dev review` |
| Write social media posts | `/mkt social <platform> <topic>` |
| Audit an online store | `/ecom audit <url>` |
| Get a financial report | `/fin report <type>` |
| Manage tasks | `/ops tasks` |
| Brainstorm strategy | `/strat brainstorm <topic>` |
| Learn from content | `/kb learn <source>` |
| Send a message | `/ops notify <message>` |
| Update ARKA OS | `arka update` (in terminal) |
