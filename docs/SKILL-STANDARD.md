# ArkaOS Skill Standard

How to create, validate, and contribute skills to ArkaOS. This guide walks through the complete SKILL.md format, builds a real skill from scratch, and shows common mistakes.

## What Is a Skill

A skill is a single capability that an agent can execute. Each skill is a directory containing a `SKILL.md` file and optional reference documents. Skills are framework-backed, meaning they use validated enterprise methodologies (not just generic advice).

ArkaOS has 244 skills across 17 departments. You can create new ones for any department.

## Directory Structure

```
departments/{dept}/skills/{skill-slug}/
├── SKILL.md                    # Required -- the skill definition
└── references/                 # Optional -- deep knowledge files
    ├── framework-guide.md
    └── checklist.md
```

The skill slug must be lowercase with hyphens: `code-review`, `seo-audit`, `validate-idea`.

## Complete SKILL.md Template

Every SKILL.md has two parts: YAML frontmatter and markdown body.

### Frontmatter (Required)

```yaml
---
name: dept/skill-slug
description: >
  One to three sentences describing what this skill does,
  what frameworks it uses, and what output it produces.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent]
---
```

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Format: `dept/skill-slug`. Must match the directory path. |
| `description` | Yes | What the skill does. Used in command search and routing. |
| `allowed-tools` | Yes | Which Claude Code tools this skill can use. |

### Body Structure

```markdown
# Skill Title -- `/dept skill-slug`

> **Agent:** Agent Name (Role) | **Framework:** Framework Name(s)

## [Main Sections]

Tables, checklists, step-by-step instructions. This is the actionable
content the agent follows when executing the skill.

## Proactive Triggers

Surface these issues WITHOUT being asked:

- [condition] --> [what to flag]
- [condition] --> [what to flag]
- [condition] --> [what to flag]

## Output

```markdown
[Output template showing the exact format of what the skill produces]
```

## References

- [file.md](references/file.md) -- description
```

## Real Example: Building a "Code Review" Skill

Here is the complete process of creating a code review skill for the dev department.

### Step 1: Create the Directory

```bash
mkdir -p departments/dev/skills/code-review
mkdir -p departments/dev/skills/code-review/references
```

### Step 2: Write SKILL.md

```markdown
---
name: dev/code-review
description: >
  Reviews code changes for quality, security, performance, and pattern
  adherence. Uses SOLID principles, OWASP top 10, and project-specific
  conventions. Produces a structured review with severity ratings.
allowed-tools: [Read, Bash, Grep, Glob]
---

# Code Review -- `/dev code-review`

> **Agent:** Andre (Senior Backend Dev) | **Framework:** SOLID, OWASP Top 10, Clean Code

## Review Checklist

| Category | What to Check | Severity if Failed |
|----------|--------------|-------------------|
| **Correctness** | Does the code do what the PR description says? | Critical |
| **Security** | SQL injection, XSS, CSRF, auth bypass, secrets in code | Critical |
| **SOLID** | SRP violations, tight coupling, interface segregation | Major |
| **Clean Code** | Function length > 30 lines, nesting > 3 levels, dead code | Major |
| **Tests** | Coverage for happy path + edge cases + error cases | Major |
| **Performance** | N+1 queries, missing indexes, unbounded queries | Major |
| **Naming** | Self-documenting names, no abbreviations, consistent casing | Minor |
| **Patterns** | Matches existing project patterns (check 2-3 similar files) | Minor |

## Process

1. Read the diff (staged + unstaged changes)
2. Identify the files and their purpose
3. Check each file against the review checklist
4. Read 2-3 similar existing files to verify pattern adherence
5. Run existing tests to confirm they pass
6. Produce the review report

## Proactive Triggers

Surface these issues WITHOUT being asked:

- Credentials or API keys in code --> Flag immediately, suggest .env
- Missing database index on foreign key --> Flag with migration suggestion
- Controller with business logic --> Flag SRP violation, suggest service extraction
- Test file with no assertions --> Flag empty test
- Function over 50 lines --> Flag with refactor suggestion

## Output

```markdown
## Code Review Report

**Files reviewed:** {count}
**Verdict:** APPROVED / CHANGES REQUESTED

### Critical Issues
- [ ] {file}:{line} -- {description}

### Major Issues
- [ ] {file}:{line} -- {description}

### Minor Issues
- [ ] {file}:{line} -- {description}

### Positive Notes
- {what was done well}

### Summary
{2-3 sentence overall assessment}
```

## References

- [solid-checklist.md](references/solid-checklist.md) -- SOLID principle checklist with code examples
- [owasp-top-10.md](references/owasp-top-10.md) -- OWASP Top 10 quick reference
```

### Step 3: Add Reference Docs (Optional)

Reference files in the `references/` directory provide deep knowledge that the agent can read when executing the skill. Keep each reference focused on one topic, under 200 lines.

### Step 4: Validate

```bash
python scripts/skill_validator.py departments/dev/skills/code-review
```

Expected output:

```
Validating: departments/dev/skills/code-review/SKILL.md

[PASS] Frontmatter present
[PASS] name field: dev/code-review
[PASS] description field present (142 chars)
[PASS] allowed-tools field present
[PASS] Name matches directory path
[PASS] Has agent attribution
[PASS] Has framework attribution
[PASS] Has Proactive Triggers section
[PASS] Has Output section
[PASS] Line count: 78 (target: 60-120)
[PASS] Has at least 3 proactive triggers

Score: 95/100 -- EXCELLENT
```

## Validation Scoring

| Score | Rating | Meaning |
|-------|--------|---------|
| 90-100 | EXCELLENT | Production-ready, follows all conventions |
| 70-89 | GOOD | Usable, minor improvements suggested |
| 50-69 | WARN | Missing sections or conventions, needs work |
| 0-49 | FAIL | Missing required fields, cannot be loaded |

What the validator checks:
- Frontmatter fields (`name`, `description`, `allowed-tools`) exist and are valid
- `name` matches the directory path (`dept/skill-slug`)
- Agent and framework attribution in the body
- Proactive Triggers section with at least 3 triggers
- Output section with a template
- Line count between 60 and 120 (soft limit)
- Heading structure (H1 title, H2 sections)

### Validate All Skills

```bash
python scripts/skill_validator.py departments/ --summary
```

Output:

```
Validated 244 skills across 17 departments

EXCELLENT: 198 (81%)
GOOD: 38 (16%)
WARN: 8 (3%)
FAIL: 0 (0%)

Average score: 91.4
```

## Proactive Triggers Explained

Proactive triggers are conditions the agent should flag automatically, without you asking. They make skills more valuable by catching issues you did not know to look for.

Five real examples from existing skills:

| Skill | Trigger Condition | What Gets Flagged |
|-------|------------------|-------------------|
| `dev/security-audit` | `.env` file committed to git | "Secrets exposed in repository. Add to .gitignore immediately." |
| `mkt/seo-audit` | Page has no `<h1>` tag | "Missing H1 tag. Search engines use H1 as primary relevance signal." |
| `fin/unit-economics` | LTV/CAC ratio below 3:1 | "Unit economics unsustainable. CAC must decrease or LTV must increase." |
| `ops/gdpr-compliance` | No cookie consent banner detected | "GDPR violation risk. Cookie consent required for EU visitors." |
| `saas/validate-idea` | TAM under $100M | "Niche market. Consider adjacent markets or premium pricing." |

## Common Mistakes

**Mistake: Name does not match directory path.**

```yaml
# Wrong -- skill is at departments/dev/skills/api-design/ but name says:
name: dev/api
# Right:
name: dev/api-design
```

**Mistake: Missing agent attribution.**

```markdown
# Wrong -- no agent specified:
# API Design -- `/dev api-design`

# Right:
# API Design -- `/dev api-design`
> **Agent:** Gabriel (Architect) | **Framework:** OpenAPI 3.1, REST conventions
```

**Mistake: Generic proactive triggers.**

```markdown
# Wrong -- too vague:
- Bad code --> Flag it
- Security issue --> Report it

# Right -- specific and actionable:
- Endpoint accepts user input without validation --> Flag missing FormRequest
- JWT token stored in localStorage --> Flag XSS risk, suggest httpOnly cookie
```

**Mistake: No output template.**

Every skill must define what its output looks like. Without a template, the agent's output format varies between runs. Always include a structured output section with placeholders.

**Mistake: Skill too long (200+ lines).**

Skills should be 60-120 lines. If yours is longer, split reference material into `references/` files and link to them. The SKILL.md should contain actionable instructions, not encyclopedic knowledge.

## Contributing Skills

1. Pick a department and identify a gap (something the department should handle but does not have a skill for)
2. Create the directory under `departments/{dept}/skills/{slug}/`
3. Write SKILL.md following this standard
4. Add reference docs if the skill needs deep knowledge
5. Run the validator and fix any issues
6. Test by using the skill: `/dept skill-slug "test input"`
