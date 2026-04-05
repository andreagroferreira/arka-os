# ArkaOS Commands

## CLI Commands

| Command | Description |
|---------|-------------|
| `npx arkaos install` | Install ArkaOS (auto-detects runtime) |
| `npx arkaos install --runtime <name>` | Install for specific runtime |
| `npx arkaos init` | Initialize project config (`.arkaos.json`) |
| `npx arkaos update` | Update to latest version |
| `npx arkaos migrate` | Migrate from v1 to v2 |
| `npx arkaos doctor` | Run health checks |
| `npx arkaos dashboard` | Start monitoring dashboard |
| `npx arkaos index` | Index knowledge base (Obsidian vault) |
| `npx arkaos search "query"` | Semantic search in knowledge base |
| `npx arkaos uninstall` | Remove ArkaOS |

## Department Commands

| Prefix | Department | Example Commands |
|--------|-----------|-----------------|
| `/dev` | Development | `/dev feature "user auth"`, `/dev security-audit`, `/dev api-design` |
| `/mkt` | Marketing | `/mkt seo-audit`, `/mkt growth-plan`, `/mkt email-sequence` |
| `/brand` | Brand & Design | `/brand identity`, `/brand colors`, `/brand voice` |
| `/fin` | Finance | `/fin budget`, `/fin valuation`, `/fin unit-economics` |
| `/strat` | Strategy | `/strat blue-ocean`, `/strat five-forces`, `/strat bmc` |
| `/ecom` | E-Commerce | `/ecom store-audit`, `/ecom pricing-strategy` |
| `/kb` | Knowledge | `/kb learn <url>`, `/kb research` |
| `/ops` | Operations | `/ops sop-create`, `/ops gdpr-compliance`, `/ops iso27001` |
| `/pm` | Project Mgmt | `/pm sprint-plan`, `/pm roadmap-build`, `/pm story-write` |
| `/saas` | SaaS | `/saas validate`, `/saas metrics-dashboard`, `/saas plg-setup` |
| `/landing` | Landing Pages | `/landing copy-framework`, `/landing funnel-design` |
| `/content` | Content | `/content hook-write`, `/content viral-design` |
| `/community` | Communities | `/community platform-setup`, `/community growth-plan` |
| `/sales` | Sales | `/sales pipeline-manage`, `/sales spin-sell` |
| `/lead` | Leadership | `/lead okr-set`, `/lead team-health` |
| `/org` | Organization | `/org design`, `/org compensation` |

## Python CLI Tools

```bash
python scripts/tools/headline_scorer.py "Your headline" --json
python scripts/tools/seo_checker.py page.html --json
python scripts/tools/rice_prioritizer.py features.json --json
python scripts/tools/dcf_calculator.py --revenue 1000000 --growth 20 --json
python scripts/tools/saas_metrics.py --new-mrr 50000 --json
python scripts/tools/tech_debt_analyzer.py src/ --json
python scripts/tools/brand_voice_analyzer.py content.txt --json
python scripts/tools/okr_cascade.py growth --json
```
