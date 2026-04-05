# ArkaOS API Reference

## Dashboard API

FastAPI backend running on `localhost:3334`. Start with `npx arkaos dashboard`.

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/overview` | System stats (agents, skills, departments, budget, tasks) |
| GET | `/api/agents` | All agents (filter: `?dept=dev`) |
| GET | `/api/agents/{id}` | Agent detail with full behavioral DNA |
| GET | `/api/commands` | All commands (filter: `?dept=dev&q=search`) |
| GET | `/api/budget` | Budget summary + department breakdown |
| GET | `/api/budget/{tier}` | Single tier budget |
| GET | `/api/tasks` | All tasks (filter: `?status=completed`) |
| GET | `/api/tasks/{id}` | Single task detail |
| GET | `/api/tasks/active` | Active tasks only |
| GET | `/api/knowledge/stats` | Knowledge DB statistics |
| GET | `/api/knowledge/search?q=` | Semantic search in knowledge base |
| POST | `/api/knowledge/ingest` | Ingest content (YouTube, PDF, web, audio, markdown) |
| GET | `/api/personas` | All personas |
| GET | `/api/personas/{id}` | Persona detail |
| POST | `/api/personas` | Create persona |
| POST | `/api/personas/{id}/clone` | Clone persona to ArkaOS agent |
| DELETE | `/api/personas/{id}` | Delete persona |
| GET | `/api/health` | System health checks |
| GET | `/api/metrics` | Hook performance metrics |

### Example: Ingest Content

```bash
curl -X POST http://localhost:3334/api/knowledge/ingest \
  -H "Content-Type: application/json" \
  -d '{"source": "https://www.youtube.com/watch?v=abc123", "type": "youtube"}'
```

Response: `{"task_id": "task-0001", "source_type": "youtube", "status": "queued"}`

Poll progress: `GET /api/tasks/task-0001`

## Python CLI Tools

All tools are stdlib-only, support `--json` output and `--help`.

| Tool | Purpose | Usage |
|------|---------|-------|
| `headline_scorer.py` | Score headlines 0-100 | `python scripts/tools/headline_scorer.py "headline" --json` |
| `seo_checker.py` | On-page SEO audit | `python scripts/tools/seo_checker.py page.html --json` |
| `rice_prioritizer.py` | Feature prioritization | `python scripts/tools/rice_prioritizer.py features.json --json` |
| `dcf_calculator.py` | DCF valuation | `python scripts/tools/dcf_calculator.py --revenue 1M --growth 20 --json` |
| `saas_metrics.py` | SaaS health metrics | `python scripts/tools/saas_metrics.py --new-mrr 50000 --json` |
| `tech_debt_analyzer.py` | Codebase debt scan | `python scripts/tools/tech_debt_analyzer.py src/ --json` |
| `brand_voice_analyzer.py` | Voice consistency | `python scripts/tools/brand_voice_analyzer.py content.txt --json` |
| `okr_cascade.py` | OKR generation | `python scripts/tools/okr_cascade.py growth --json` |
| `skill_validator.py` | Validate skills | `python scripts/skill_validator.py departments/ --summary` |

## Synapse Bridge

Standalone context injection script called by hooks:

```bash
echo '{"user_input":"fix the auth bug"}' | python scripts/synapse-bridge.py
```

Returns: `{"context_string": "[Constitution] [dept:dev] [branch:main] [qg:active] [time:afternoon]", "total_ms": 74}`

With layer breakdown:
```bash
echo '{"user_input":"validate saas idea"}' | python scripts/synapse-bridge.py --layers-only
```
