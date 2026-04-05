# ArkaOS Skill Standard

How to create and validate skills for ArkaOS.

## SKILL.md Format

Every skill is a directory with a `SKILL.md` file:

```
departments/{dept}/skills/{skill-slug}/
├── SKILL.md                    # Required
└── references/                 # Optional deep knowledge
    └── topic.md
```

### Frontmatter (required)

```yaml
---
name: dept/skill-slug
description: >
  Brief description of what this skill does.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent]
---
```

### Structure

```markdown
# Skill Title — `/dept skill-slug`

> **Agent:** Name (Role) | **Framework:** Framework names

## [Main content — tables, checklists, actionable steps]

## Proactive Triggers

Surface these issues WITHOUT being asked:

- condition → what to flag
- condition → what to flag
- condition → what to flag

## Output

```markdown
[Output template]
```

## References

- [file.md](references/file.md) — description
```

## Guidelines

- **60-120 lines** ideal length
- **Tables and checklists** over prose
- **One agent** per skill
- **Framework attribution** — name the framework used
- **Proactive triggers** — 3+ conditions the skill flags automatically
- **Output template** — show expected output format

## Create a Skill

```bash
mkdir -p departments/dev/skills/my-skill
# Write SKILL.md following the format above
```

## Validate

```bash
python scripts/skill_validator.py departments/dev/skills/my-skill
```

Validates: frontmatter fields, name format, line count, headings, agent attribution, output section.

Scores: EXCELLENT (90+), GOOD (70-89), WARN (50-69), FAIL (<50).

## Validate All Skills

```bash
python scripts/skill_validator.py departments/ --summary
```
