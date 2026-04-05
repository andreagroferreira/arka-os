---
name: dev/runbook
description: >
  Generate operational runbooks for deployment, incident response, rollback, and scaling procedures.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent]
---

# Runbook Generator — `/dev runbook`

> **Agent:** Andre (Backend Dev) | **Framework:** SRE (Google), Three Ways (Gene Kim)

## What It Does

Generates structured operational runbooks from service analysis. Covers deployment, health checks, rollback, incident response, and scaling procedures.

## Runbook Sections

| Section | Purpose | Required |
|---------|---------|----------|
| Service Overview | Name, owner, dependencies, endpoints | Yes |
| Health Checks | URLs, expected responses, check intervals | Yes |
| Deployment | Step-by-step deploy with verification | Yes |
| Rollback | How to revert, data migration rollback | Yes |
| Incident Response | Triage, escalation contacts, communication | Yes |
| Scaling | Horizontal/vertical triggers and procedures | If applicable |
| Maintenance | Scheduled tasks, backups, log rotation | If applicable |

## Generation Workflow

1. **Analyze** the service: stack, dependencies, infrastructure
2. **Detect** existing configs: Dockerfile, docker-compose, CI/CD, k8s manifests
3. **Generate** runbook with copy-pasteable commands
4. **Validate** every command runs in staging
5. **Store** runbook alongside service code in version control

## Runbook Quality Checklist

- [ ] Every command is copy-pasteable (no placeholders without explanation)
- [ ] Every critical step has a verification check after it
- [ ] Rollback triggers are explicit (what metric/error = rollback)
- [ ] Escalation contacts are named with phone/Slack
- [ ] Runbook tested outside of incident conditions
- [ ] Last review date documented

## Common Pitfalls

| Pitfall | Impact | Prevention |
|---------|--------|------------|
| Missing rollback commands | Incident drags on | Mandate rollback section in review |
| Steps without verification | Silent failures | Add expected output after each step |
| Stale contacts | Escalation fails | Review contacts quarterly |
| Never tested | Fails during incident | Dry-run in staging monthly |

## Proactive Triggers

Surface these issues WITHOUT being asked:

- Production service without runbook → flag operational risk
- Runbook >6 months without update → flag stale procedures
- No rollback section in deployment runbook → flag recovery gap

## Output

```markdown
## Runbook: <service-name>

### Service Overview
- **Owner:** <team/person>
- **Stack:** <e.g., Laravel 11, PostgreSQL 16, Redis 7>
- **Dependencies:** <upstream/downstream services>
- **Endpoints:** <health, API base URL>

### Health Checks
| Check | URL/Command | Expected | Interval |
|-------|------------|----------|----------|
| HTTP health | GET /health | 200 OK | 30s |
| DB connection | `php artisan db:monitor` | Connected | 60s |
| Queue depth | `redis-cli llen queues:default` | < 1000 | 60s |

### Deployment
1. `git pull origin main`
2. `composer install --no-dev --optimize-autoloader`
3. `php artisan migrate --force`
   Verify: `php artisan migrate:status` shows all ran
4. `php artisan config:cache && php artisan route:cache`
5. `sudo systemctl reload php-fpm`
   Verify: GET /health returns 200

### Rollback
**Trigger:** Error rate > 5% or p99 latency > 2s post-deploy
1. `git checkout <previous-tag>`
2. `composer install --no-dev`
3. `php artisan migrate:rollback --step=1`
4. `sudo systemctl reload php-fpm`
   Verify: GET /health returns 200, error rate normalizes

### Incident Response
1. **Triage:** Check /health, logs (`tail -f storage/logs/laravel.log`)
2. **Escalate:** <contact name> — Slack #incidents / phone
3. **Communicate:** Post in #status-page within 10 minutes
4. **Resolve:** Apply fix or rollback
5. **Postmortem:** Within 48 hours, update this runbook
```
