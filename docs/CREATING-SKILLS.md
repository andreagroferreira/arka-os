# Creating Skills

Reference for contributors authoring new ArkaOS skills.

## What Is a Skill

A skill is a single, named capability that an agent executes when invoked. It lives in a `SKILL.md` file, optionally alongside reference documents. ArkaOS currently has 267 skills across 17 departments plus the `arka` orchestrator.

Skills are discovered by the Claude Code skills system at load time. The file path determines the command name and routing; there is no separate registration step.

## Directory Layout

```
departments/<dept>/skills/<skill-slug>/
├── SKILL.md          # Required — the skill definition
└── references/       # Optional — deep knowledge files
    └── <topic>.md
```

The orchestrator's own skills live under:

```
arka/skills/<skill-slug>/
└── SKILL.md
```

The root orchestrator skill (`arka/SKILL.md`) is the single entry point for all `/arka` commands.

### Naming rules

- Skill slug: lowercase, hyphen-separated (`code-review`, `seo-audit`, `validate-idea`)
- Department prefix: the `name` field in frontmatter must be `<dept>/<slug>` and must match the file path exactly
- Orchestrator skills: use `arka-<slug>` as the name (e.g. `arka-research`)

## SKILL.md Structure

Every `SKILL.md` has two parts: YAML frontmatter and a markdown body.

### Frontmatter

```yaml
---
name: dept/skill-slug
description: >
  One to three sentences. What the skill does, which frameworks it uses,
  and what output it produces.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent]
---
```

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Format: `dept/skill-slug`. Must match the directory path. |
| `description` | Yes | Used by routing and command search. Be specific — include the frameworks and output type. |
| `allowed-tools` | Yes | Comma-separated list of Claude Code tools the skill may use. Only list what the skill actually needs. |

Available tools for `allowed-tools`: `Read`, `Write`, `Edit`, `Bash`, `Grep`, `Glob`, `Agent`, `WebFetch`, `WebSearch`, plus MCP tools (e.g. `mcp__obsidian__search_notes`).

### Body structure

```markdown
# Skill Title — `/dept skill-slug`

> **Agent:** Agent Name (Role) | **Framework:** Framework Name(s)

## [Content sections]

## Proactive Triggers

Surface these issues WITHOUT being asked:

- [condition] — [what to flag]

## Output

[Fenced code block showing the exact output format]

## References

- [filename.md](references/filename.md) — description
```

The H1 title is the human-readable name. The `> **Agent:**` line attributes who runs this skill and which frameworks ground it. Both are required for passing validation.

## The KB-First Prefix

Skills that perform research or gather context must include the KB-first block before external tool calls. The block is a markdown blockquote wrapped in a `<!-- arka:kb-first-prefix begin -->` / `<!-- arka:kb-first-prefix end -->` comment pair — the prose sits between the two comments, not inside them, so the model actually reads it.

Do not hand-write it. It is a compact POINTER (PR-3 of the prompt-surface plan); the full doctrine lives once in `arka/SKILL.md` under "KB-First Research". `scripts/migrate_skills_kb_first.py` owns the canonical text — run it and the block is injected or refreshed in place. `scripts/marketplace_export.py` strips the block from exported skills, since the pointer names an ArkaOS-specific Obsidian MCP.

```markdown
<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` (and
> `mcp__graphify__query_graph` when configured) and cite `[[wikilinks]]`
> or graph nodes — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->
```

Editing the block by hand drifts it from every other migrated skill and the next run of the script overwrites your edit. To change the wording for everyone, edit `PREFIX_BLOCK` in the script and re-run it.

When to include it: any skill that calls `WebSearch`, `WebFetch`, `Context7`, `Firecrawl`, or performs discovery research. Skills that only read local files or run Bash commands do not need it.

The block goes immediately after the frontmatter, before the H1 title.

## Proactive Triggers

Proactive triggers are conditions the agent must surface automatically, without the user asking. They are the most valuable part of a skill — they catch issues the user did not know to check for.

Format:

```markdown
## Proactive Triggers

Surface these issues WITHOUT being asked:

- [condition] — [what to flag and what to suggest]
- [condition] — [what to flag and what to suggest]
- [condition] — [what to flag and what to suggest]
```

At least three triggers are required. Each trigger must be specific and actionable:

| Wrong (too vague) | Right (specific and actionable) |
|-------------------|---------------------------------|
| `Bad code → Flag it` | `Controller with business logic → Flag SRP violation, suggest service extraction` |
| `Security issue → Report it` | `JWT token stored in localStorage → Flag XSS risk, suggest httpOnly cookie` |
| `Missing test → Mention it` | `Test file with no assertions → Flag empty test, suggest adding at least one assertion per path` |

## Output Template

Every skill must define its output format in a fenced code block under an `## Output` section. Without a template, output format varies between runs.

```markdown
## Output

```markdown
## [Skill Name] Report

**[Metric]:** {value}
**[Status]:** APPROVED / REJECTED

### [Section 1]
- [ ] {item}

### [Section 2]
{free-form content}
```
```

## Validation

Run the validator on any new or modified skill:

```bash
python scripts/skill_validator.py departments/<dept>/skills/<skill-slug>
```

To validate all skills and see a summary:

```bash
python scripts/skill_validator.py departments/ --summary
```

### Scoring

| Score | Rating | Meaning |
|-------|--------|---------|
| 90-100 | EXCELLENT | Production-ready |
| 70-89 | GOOD | Usable, minor issues |
| 50-69 | WARN | Missing sections, needs work |
| 0-49 | FAIL | Missing required fields |

What the validator checks:

- `name`, `description`, `allowed-tools` present in frontmatter
- `name` matches the directory path
- Agent and framework attribution in the body
- `## Proactive Triggers` section with at least 3 triggers
- `## Output` section with a template
- Line count 60-120 (soft limit)
- H1 title and H2 section structure

## Skill Discovery

Claude Code discovers skills by scanning for `SKILL.md` files registered in the project's `.claude/` configuration. Skills are loaded at session start. Adding a new `SKILL.md` file in the correct location makes it available immediately in the next session without any additional configuration.

Skill names in frontmatter (`name: dept/skill-slug`) must be unique across the entire repository. The `name` field is what the routing system uses to match commands.

## Step-by-Step: Create Your First Skill

This example creates a security audit skill for the `dev` department.

### Step 1: Create the directory

```bash
mkdir -p departments/dev/skills/security-audit/references
```

### Step 2: Write SKILL.md

```markdown
---
name: dev/security-audit
description: >
  Security audit for web application codebases. Checks OWASP Top 10
  vulnerabilities, secret exposure, dependency CVEs, and authentication
  patterns. Produces a severity-ranked findings report.
allowed-tools: [Read, Bash, Grep, Glob]
---

# Security Audit — `/dev security-audit`

> **Agent:** Andre (Backend Core Lead) | **Framework:** OWASP Top 10, SANS CWE Top 25

## What It Checks

| Category | What to Look For |
|----------|-----------------|
| **Secrets** | API keys, passwords, tokens in source files or git history |
| **Injection** | SQL, command, LDAP injection points |
| **Auth** | Missing authentication, broken session management |
| **Dependencies** | Known CVEs in `composer.lock` or `package-lock.json` |
| **Input Validation** | Missing server-side validation on user-controlled input |
| **Sensitive Data** | PII logged, unencrypted at rest, exposed in error messages |

## Audit Process

1. Scan for secrets: `git log --all --oneline | grep -i "key\|secret\|password\|token"`
2. Check `.env.example` for patterns that suggest secrets in env files
3. Read route and controller files for unvalidated input paths
4. Check dependency files for known CVE references
5. Review error handling for stack traces or sensitive data in responses
6. Check authentication middleware application on protected routes

## Proactive Triggers

Surface these issues WITHOUT being asked:

- `.env` file tracked in git — flag immediately, secrets likely exposed in history
- `APP_KEY` or `SECRET_KEY` hardcoded in source — flag critical, rotation required
- Missing CSRF protection on state-changing routes — flag auth vulnerability
- `eval()` or `exec()` called with user input — flag code injection risk
- `console.log` or `dd()` left in production code — flag information disclosure

## Output

```markdown
## Security Audit: <project>

**Files scanned:** {count}
**Critical findings:** {count}
**Risk level:** CRITICAL / HIGH / MEDIUM / LOW / PASS

### Critical
- [ ] {file}:{line} — {description} — {remediation}

### High
- [ ] {file}:{line} — {description} — {remediation}

### Medium
- [ ] {file}:{line} — {description} — {remediation}

### Summary
{2-3 sentence overall assessment and priority recommendation}
```

## References

- [owasp-top-10.md](references/owasp-top-10.md) — OWASP Top 10 quick reference with code examples
```

### Step 3: Add reference docs (optional)

Reference files go in `references/`. Keep each file under 200 lines, focused on one topic. The agent reads them on demand during execution.

```bash
# Create references/owasp-top-10.md with OWASP Top 10 content
```

### Step 4: Validate

```bash
python scripts/skill_validator.py departments/dev/skills/security-audit
```

Expected output:

```
Validating: departments/dev/skills/security-audit/SKILL.md

[PASS] Frontmatter present
[PASS] name field: dev/security-audit
[PASS] description field present
[PASS] allowed-tools field present
[PASS] Name matches directory path
[PASS] Has agent attribution
[PASS] Has framework attribution
[PASS] Has Proactive Triggers section
[PASS] Has Output section
[PASS] Line count: 72 (target: 60-120)
[PASS] Has at least 3 proactive triggers

Score: 100/100 — EXCELLENT
```

### Step 5: Test the skill

Invoke the skill in a Claude Code session:

```
/dev security-audit
```

Or with a target:

```
/dev security-audit @src/
```

Verify that the output matches the template defined in the `## Output` section.

## Common Mistakes

**Name does not match directory path.**

```yaml
# Wrong — skill is at departments/dev/skills/api-design/ but name says:
name: dev/api

# Correct:
name: dev/api-design
```

**Missing agent and framework attribution.**

```markdown
# Wrong — no agent line:
# API Design — `/dev api-design`

# Correct:
# API Design — `/dev api-design`
> **Agent:** Gabriel (Architect) | **Framework:** OpenAPI 3.1, REST Conventions
```

**Proactive triggers too generic.**

```markdown
# Wrong:
- Bad input — flag it

# Correct:
- Endpoint accepts user input without validation — Flag missing server-side validation, suggest FormRequest
```

**No output template.**

Every skill must define what its output looks like. Include a fenced code block with placeholders under `## Output`.

**Skill too long.**

Skills should be 60-120 lines. If yours exceeds 200 lines, move reference material to `references/` files and link to them from the `## References` section.

**Using `allowed-tools` that the skill does not need.**

Only list tools the skill actually calls. Unnecessary tools in `allowed-tools` expand the permission surface and reduce clarity.

## Skills vs Workflows

Skills and workflows serve different purposes:

| | Skill | Workflow |
|---|---|---|
| Definition | Single `SKILL.md` file | Multi-phase YAML file |
| Scope | Single capability | End-to-end process (3-10 phases) |
| Execution | Direct agent response | Orchestrated with gates and parallel steps |
| Location | `departments/<dept>/skills/<slug>/` | `departments/<dept>/workflows/<slug>.yaml` |
| When to use | One focused task | Complex tasks requiring coordination, QA gates, approval steps |

For tasks requiring Quality Gate review, human approval, or parallel agent execution, use a workflow instead of a skill.

---

Related: [SKILL-STANDARD.md](SKILL-STANDARD.md) — original skill standard with validation scoring detail. [ARCHITECTURE.md](ARCHITECTURE.md) — Synapse context injection and skill discovery internals. [DEPARTMENTS.md](DEPARTMENTS.md) — per-department skill inventory.
