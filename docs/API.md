# ArkaOS API Reference

Complete reference for the dashboard API, Python CLI tools, and the Synapse bridge. The dashboard API runs on `localhost:3334` when you start the dashboard with `npx arkaos dashboard`.

## Dashboard API

All endpoints return JSON. No authentication required (local only).

### System Overview

```bash
curl http://localhost:3334/api/overview
```

```json
{
  "agents": 65,
  "departments": 17,
  "skills": 244,
  "workflows": 24,
  "budget": {
    "total_tokens_today": 847320,
    "limit_today": 5000000,
    "utilization_pct": 16.9
  },
  "tasks": {
    "active": 2,
    "completed": 47,
    "failed": 1
  },
  "knowledge": {
    "documents": 847,
    "chunks": 12340,
    "db_size_mb": 4.2
  }
}
```

### Agents

**List all agents:**

```bash
curl http://localhost:3334/api/agents
```

```json
{
  "agents": [
    {
      "id": "tech-lead-paulo",
      "name": "Paulo",
      "role": "Tech Lead",
      "department": "dev",
      "tier": 1,
      "disc": "C+D",
      "enneagram": "1w2",
      "mbti": "ISTJ",
      "big_five": {"O": 55, "C": 92, "E": 38, "A": 65, "N": 22}
    }
  ],
  "total": 65
}
```

**Filter by department:**

```bash
curl http://localhost:3334/api/agents?dept=dev
```

Returns only agents in the dev department (10 agents).

**Get single agent with full behavioral DNA:**

```bash
curl http://localhost:3334/api/agents/architect-gabriel
```

```json
{
  "id": "architect-gabriel",
  "name": "Gabriel",
  "role": "Software Architect",
  "department": "dev",
  "tier": 2,
  "disc": {
    "primary": "C",
    "secondary": "D",
    "style": "Analyst-Driver",
    "communication": "Structured, data-driven, prefers written specs",
    "under_pressure": "Becomes more careful, requests more data"
  },
  "enneagram": {
    "type": 5,
    "wing": 6,
    "core_motivation": "To understand and master systems",
    "core_fear": "Being incompetent or overwhelmed"
  },
  "mbti": {
    "type": "INTJ",
    "functions": ["Ni", "Te", "Fi", "Se"]
  },
  "big_five": {
    "openness": 78,
    "conscientiousness": 88,
    "extraversion": 25,
    "agreeableness": 52,
    "neuroticism": 18
  },
  "skills": ["architecture-design", "api-design", "db-design", "ddd-model"]
}
```

### Commands

**List all commands:**

```bash
curl http://localhost:3334/api/commands
```

```json
{
  "commands": [
    {
      "name": "dev/feature",
      "department": "dev",
      "description": "Full enterprise workflow for implementing a new feature",
      "agent": "tech-lead-paulo",
      "usage": "/dev feature \"description\""
    }
  ],
  "total": 244
}
```

**Filter by department and search:**

```bash
curl "http://localhost:3334/api/commands?dept=mkt&q=email"
```

Returns commands in the marketing department matching "email".

### Budget

**Budget summary:**

```bash
curl http://localhost:3334/api/budget
```

```json
{
  "tiers": {
    "tier_0": {"label": "C-Suite", "used": 125000, "limit": 1000000, "pct": 12.5},
    "tier_1": {"label": "Squad Leads", "used": 340000, "limit": 2000000, "pct": 17.0},
    "tier_2": {"label": "Specialists", "used": 382320, "limit": 1500000, "pct": 25.5},
    "tier_3": {"label": "Support", "used": 0, "limit": 500000, "pct": 0.0}
  },
  "departments": [
    {"dept": "dev", "used": 412000, "pct_of_total": 48.6},
    {"dept": "marketing", "used": 98000, "pct_of_total": 11.6},
    {"dept": "brand", "used": 73000, "pct_of_total": 8.6}
  ],
  "total_used": 847320,
  "total_limit": 5000000,
  "reset_at": "2026-04-06T00:00:00Z"
}
```

**Single tier:**

```bash
curl http://localhost:3334/api/budget/tier_0
```

### Tasks

**List all tasks:**

```bash
curl http://localhost:3334/api/tasks
```

```json
{
  "tasks": [
    {
      "id": "task-0042",
      "type": "knowledge_ingest",
      "source": "https://youtube.com/watch?v=abc123",
      "status": "completed",
      "progress": 100,
      "result": {"chunks": 47, "duration_s": 124},
      "created_at": "2026-04-05T14:22:00Z",
      "completed_at": "2026-04-05T14:24:04Z"
    }
  ],
  "total": 50
}
```

**Filter by status:**

```bash
curl http://localhost:3334/api/tasks?status=active
```

**Get active tasks only:**

```bash
curl http://localhost:3334/api/tasks/active
```

**Get single task (useful for polling ingestion progress):**

```bash
curl http://localhost:3334/api/tasks/task-0042
```

### Knowledge Base

**Knowledge stats:**

```bash
curl http://localhost:3334/api/knowledge/stats
```

```json
{
  "documents": 847,
  "chunks": 12340,
  "db_size_mb": 4.2,
  "last_indexed": "2026-04-05T10:30:00Z",
  "sources": {
    "obsidian": 812,
    "youtube": 18,
    "pdf": 12,
    "web": 5
  }
}
```

**Semantic search:**

```bash
curl "http://localhost:3334/api/knowledge/search?q=authentication%20patterns%20laravel"
```

```json
{
  "results": [
    {
      "content": "Laravel Sanctum provides token-based authentication for SPAs and simple APIs...",
      "source": "Development/Laravel/Authentication.md",
      "score": 0.89,
      "chunk_id": "chunk-4821"
    },
    {
      "content": "For multi-tenant apps, scope tokens to the tenant using middleware...",
      "source": "Development/Laravel/Multi-Tenancy.md",
      "score": 0.82,
      "chunk_id": "chunk-7103"
    }
  ],
  "query": "authentication patterns laravel",
  "total": 5,
  "search_ms": 34
}
```

**Ingest content:**

```bash
# YouTube video
curl -X POST http://localhost:3334/api/knowledge/ingest \
  -H "Content-Type: application/json" \
  -d '{"source": "https://www.youtube.com/watch?v=abc123", "type": "youtube"}'

# PDF file
curl -X POST http://localhost:3334/api/knowledge/ingest \
  -H "Content-Type: application/json" \
  -d '{"source": "/path/to/document.pdf", "type": "pdf"}'

# Web page
curl -X POST http://localhost:3334/api/knowledge/ingest \
  -H "Content-Type: application/json" \
  -d '{"source": "https://laravel.com/docs/11.x/authentication", "type": "web"}'

# Markdown file
curl -X POST http://localhost:3334/api/knowledge/ingest \
  -H "Content-Type: application/json" \
  -d '{"source": "/path/to/notes.md", "type": "markdown"}'
```

Response (all types):

```json
{
  "task_id": "task-0043",
  "source_type": "youtube",
  "status": "queued"
}
```

**Polling pattern for ingestion:**

```bash
# Submit ingestion
TASK_ID=$(curl -s -X POST http://localhost:3334/api/knowledge/ingest \
  -H "Content-Type: application/json" \
  -d '{"source": "https://youtube.com/watch?v=abc123", "type": "youtube"}' \
  | jq -r '.task_id')

# Poll until complete
while true; do
  STATUS=$(curl -s http://localhost:3334/api/tasks/$TASK_ID | jq -r '.status')
  echo "Status: $STATUS"
  if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
    break
  fi
  sleep 5
done

# Check result
curl http://localhost:3334/api/tasks/$TASK_ID
```

### Personas

**List all personas:**

```bash
curl http://localhost:3334/api/personas
```

```json
{
  "personas": [
    {
      "id": "persona-001",
      "name": "Alex Hormozi",
      "sources": ["youtube:12", "books:2"],
      "traits": ["direct", "value-focused", "no-fluff"],
      "created_at": "2026-04-01T09:00:00Z"
    }
  ],
  "total": 3
}
```

**Create a persona:**

```bash
curl -X POST http://localhost:3334/api/personas \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Alex Hormozi",
    "description": "Business strategist known for offer creation and scaling",
    "knowledge_sources": [
      "https://youtube.com/watch?v=video1",
      "https://youtube.com/watch?v=video2"
    ],
    "traits": ["direct", "value-focused", "uses-analogies", "no-fluff"]
  }'
```

```json
{
  "id": "persona-002",
  "name": "Alex Hormozi",
  "status": "building",
  "task_id": "task-0044"
}
```

The persona builds asynchronously by ingesting the knowledge sources, analyzing communication patterns, and creating a voice profile.

**Clone persona to ArkaOS agent:**

```bash
curl -X POST http://localhost:3334/api/personas/persona-002/clone \
  -H "Content-Type: application/json" \
  -d '{"department": "sales", "role": "Offer Strategist"}'
```

```json
{
  "agent_id": "sales-alex-hormozi",
  "agent_yaml": "departments/sales/agents/alex-hormozi.yaml",
  "status": "created"
}
```

**Delete a persona:**

```bash
curl -X DELETE http://localhost:3334/api/personas/persona-002
```

### System Health

```bash
curl http://localhost:3334/api/health
```

```json
{
  "checks": {
    "python": {"status": "ok", "version": "3.12.4"},
    "synapse": {"status": "ok", "avg_ms": 127},
    "knowledge_db": {"status": "ok", "size_mb": 4.2},
    "hooks": {"status": "ok", "count": 3},
    "agents": {"status": "ok", "loaded": 65},
    "skills": {"status": "ok", "validated": 244},
    "workflows": {"status": "ok", "registered": 24},
    "budget": {"status": "ok", "utilization_pct": 16.9},
    "tasks": {"status": "ok", "active": 2}
  },
  "overall": "healthy"
}
```

### Hook Metrics

```bash
curl http://localhost:3334/api/metrics
```

```json
{
  "hooks": {
    "user-prompt-submit-v2": {
      "calls_today": 142,
      "avg_ms": 127,
      "p95_ms": 198,
      "errors": 0
    },
    "post-tool-use-v2": {
      "calls_today": 1847,
      "avg_ms": 3,
      "p95_ms": 8,
      "errors": 0
    },
    "pre-compact-v2": {
      "calls_today": 4,
      "avg_ms": 45,
      "p95_ms": 62,
      "errors": 0
    }
  }
}
```

## Python CLI Tools

All 8 tools are standalone Python scripts using only the standard library. Every tool supports `--json` for machine-readable output and `--help` for usage info.

### Headline Scorer

Scores headlines for engagement potential using power words, emotional triggers, length, and specificity.

```bash
python scripts/tools/headline_scorer.py "10 Laravel Tips That Will Save You Hours"
```

```
Headline: "10 Laravel Tips That Will Save You Hours"
Score: 78/100

Breakdown:
  Power words: 2 (tips, save)      +15
  Number in headline: yes           +10
  Emotional trigger: medium         +12
  Length: 8 words (optimal 6-12)    +10
  Specificity: high (Laravel)       +8
  Curiosity gap: low                +3

Suggestions:
  - Add a curiosity gap: "...That Most Developers Miss"
  - Strengthen emotional trigger: "...That Will 10x Your Productivity"
```

### SEO Checker

Runs an on-page SEO audit on an HTML file.

```bash
python scripts/tools/seo_checker.py index.html
```

```
SEO Audit: index.html
Score: 64/100

Issues:
  [CRITICAL] Missing meta description
  [MAJOR] 3 images without alt text (lines 45, 78, 112)
  [MAJOR] Duplicate H1 tags (2 found, should be 1)
  [MINOR] Title tag too long (72 chars, target < 60)
  [MINOR] No structured data (schema.org)

Passed:
  [OK] H1 present
  [OK] Canonical URL set
  [OK] Mobile viewport meta tag
  [OK] No broken internal links
```

### RICE Prioritizer

Prioritizes features using the RICE framework (Reach, Impact, Confidence, Effort).

```bash
python scripts/tools/rice_prioritizer.py features.json
```

Input file format:

```json
[
  {"name": "Dark mode", "reach": 5000, "impact": 2, "confidence": 80, "effort": 3},
  {"name": "API v2", "reach": 2000, "impact": 3, "confidence": 90, "effort": 8},
  {"name": "SSO login", "reach": 800, "impact": 3, "confidence": 95, "effort": 5}
]
```

```
RICE Prioritization:

Rank | Feature    | RICE Score | Reach | Impact | Conf | Effort
1    | Dark mode  | 2667       | 5000  | 2x     | 80%  | 3 wks
2    | SSO login  | 456        | 800   | 3x     | 95%  | 5 wks
3    | API v2     | 675        | 2000  | 3x     | 90%  | 8 wks

Recommendation: Start with Dark mode (highest RICE, lowest effort)
```

### DCF Calculator

Discounted Cash Flow valuation using Damodaran methodology.

```bash
python scripts/tools/dcf_calculator.py --revenue 2000000 --growth 30 --margin 20
```

```
DCF Valuation

Inputs:
  Revenue: $2,000,000
  Growth rate: 30%
  Operating margin: 20%
  Discount rate: 12% (default)
  Terminal growth: 3% (default)

5-Year Projection:
  Year 1: $2,600,000 revenue, $520,000 FCF
  Year 2: $3,380,000 revenue, $676,000 FCF
  Year 3: $4,394,000 revenue, $878,800 FCF
  Year 4: $5,712,200 revenue, $1,142,440 FCF
  Year 5: $7,425,860 revenue, $1,485,172 FCF

Enterprise Value: $8,420,000
  PV of Cash Flows: $3,180,000
  PV of Terminal Value: $5,240,000

Sensitivity (EV at different growth/margin combos):
  20% growth / 15% margin: $4,100,000
  30% growth / 20% margin: $8,420,000
  40% growth / 25% margin: $14,800,000
```

### SaaS Metrics

Calculates SaaS health metrics from MRR data.

```bash
python scripts/tools/saas_metrics.py --new-mrr 50000 --churned-mrr 5000 --expansion-mrr 8000
```

```
SaaS Metrics Dashboard

MRR Breakdown:
  New MRR: $50,000
  Churned MRR: -$5,000
  Expansion MRR: $8,000
  Net New MRR: $53,000

Health Metrics:
  Quick Ratio: 11.6 (healthy > 4.0)
  Gross Churn: 10.0%
  Net Revenue Retention: 106.0% (healthy > 100%)
  Implied ARR: $636,000

Verdict: HEALTHY -- Strong net retention, low churn relative to new revenue
```

### Tech Debt Analyzer

Scans a codebase for tech debt indicators.

```bash
python scripts/tools/tech_debt_analyzer.py src/
```

```
Tech Debt Analysis: src/

Score: 34/100 (high debt)

Hotspot Files (top 5):
  1. src/controllers/PaymentController.php  -- 340 lines, 8 methods > 30 lines
  2. src/services/OrderService.php          -- 280 lines, nested 4+ levels
  3. src/models/User.php                    -- 45 fillable fields, god model
  4. src/routes/api.php                     -- 180 routes, no grouping
  5. src/middleware/Auth.php                 -- duplicated logic from 3 files

Summary:
  Files scanned: 147
  Functions > 30 lines: 23
  Nesting > 3 levels: 8
  Duplicated blocks: 12
  TODO/FIXME comments: 34
  Estimated fix time: 40 hours

Priority fixes:
  1. Extract PaymentController into service + form requests (8h)
  2. Split User model into domain models (6h)
  3. Group API routes by domain (4h)
```

### Brand Voice Analyzer

Analyzes text for voice consistency, tone, and common issues.

```bash
python scripts/tools/brand_voice_analyzer.py marketing-copy.txt
```

```
Brand Voice Analysis: marketing-copy.txt

Consistency Score: 72/100

Tone Profile:
  Professional: 68%
  Casual: 22%
  Urgent: 10%

Issues:
  [MAJOR] Passive voice: 14 instances (target < 5)
  [MAJOR] Tone shift at paragraph 3 (professional -> casual)
  [MINOR] Jargon without explanation: "synergy", "leverage"
  [MINOR] Sentence length variance high (8-42 words)

Recommendations:
  - Convert passive constructions to active voice
  - Maintain consistent tone throughout
  - Replace jargon with plain language
```

### OKR Cascade

Generates OKR cascade from a strategic theme.

```bash
python scripts/tools/okr_cascade.py growth
```

```
OKR Cascade: Growth Theme

COMPANY LEVEL
  Objective: Accelerate revenue growth to reach $5M ARR
    KR1: Increase MRR from $200K to $420K
    KR2: Achieve net revenue retention of 120%
    KR3: Reduce CAC payback period to under 6 months

PRODUCT TEAM
  Objective: Build features that drive expansion revenue
    KR1: Launch 3 features tied to premium tier
    KR2: Increase feature adoption to 60% within 30 days
    KR3: Reduce churn-causing friction points by 50%

MARKETING TEAM
  Objective: Scale acquisition channels efficiently
    KR1: Generate 2,000 qualified leads per month
    KR2: Achieve $150 blended CAC across channels
    KR3: Launch 2 new acquisition channels with positive ROI

SALES TEAM
  Objective: Convert pipeline into revenue
    KR1: Close $1.2M in new ACV this quarter
    KR2: Increase win rate from 22% to 30%
    KR3: Reduce sales cycle from 45 to 30 days
```

## Synapse Bridge

The Synapse bridge is the standalone script that hooks call to inject context. You can call it directly for debugging or integration.

**Basic usage:**

```bash
echo '{"user_input":"fix the auth bug"}' | python scripts/synapse-bridge.py
```

```json
{
  "context_string": "[CONSTITUTION: branch-isolation, solid-clean-code...] [DEPT: dev] [AGENT: backend-dev-andre] [PROJECT: laravel 11.x] [BRANCH: feat/auth-fix] [COMMANDS: /dev debug, /dev code-review] [QG: idle] [TIME: afternoon]",
  "total_ms": 74
}
```

**Layer breakdown mode:**

```bash
echo '{"user_input":"validate saas idea"}' | python scripts/synapse-bridge.py --layers-only
```

```json
{
  "layers": {
    "L0_constitution": {"ms": 2, "cached": true, "tokens": 45},
    "L1_department": {"ms": 8, "detected": "saas", "confidence": 0.94},
    "L2_agent": {"ms": 3, "agent": "saas-strategist-tiago"},
    "L3_project": {"ms": 5, "stack": "nuxt 4"},
    "L3.5_knowledge": {"ms": 89, "results": 2, "top_score": 0.84},
    "L4_branch": {"ms": 12, "branch": "main"},
    "L5_commands": {"ms": 6, "matches": ["saas/validate-idea", "saas/niche-evaluate"]},
    "L6_quality_gate": {"ms": 1, "status": "idle"},
    "L7_time": {"ms": 1, "period": "afternoon"}
  },
  "total_ms": 127
}
```

Use the layer breakdown to debug routing issues (is the right department detected?), performance problems (which layer is slow?), or knowledge retrieval quality (what scores are the results getting?).
