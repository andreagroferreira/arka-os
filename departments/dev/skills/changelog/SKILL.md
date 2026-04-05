---
name: dev/changelog
description: >
  Generate changelogs from git history using conventional commits. Lint commit messages, detect version bumps, and render Keep a Changelog format.
allowed-tools: [Read, Bash, Grep, Glob, Agent]
---

# Changelog Generator — `/dev changelog`

> **Agent:** Andre (Senior Backend Dev) | **Framework:** Keep a Changelog, Conventional Commits, SemVer

## Conventional Commit Format

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

| Type | Changelog Section | SemVer Bump |
|------|------------------|-------------|
| `feat` | Added | MINOR |
| `fix` | Fixed | PATCH |
| `perf` | Changed | PATCH |
| `security` | Security | PATCH |
| `refactor` | Changed | -- |
| `docs` | -- (internal) | -- |
| `test` | -- (internal) | -- |
| `chore` | -- (internal) | -- |
| `feat!` / `BREAKING CHANGE:` | Breaking Changes | MAJOR |
| `deprecated` | Deprecated | -- |
| `remove` | Removed | MAJOR |

## Generation Workflow

1. **Determine range** -- Last tag to HEAD (or tag-to-tag)
   ```bash
   git log v1.3.0..HEAD --pretty=format:"%s" --no-merges
   ```

2. **Parse commits** -- Extract type, scope, description, breaking changes

3. **Detect version bump** -- Highest priority: MAJOR > MINOR > PATCH

4. **Group by section** -- Map commit types to Keep a Changelog sections

5. **Render changelog** -- Prepend new entry to CHANGELOG.md

## Quality Rules

| Rule | Rationale |
|------|-----------|
| Every bullet must be user-meaningful | No "fix typo in test" in release notes |
| Breaking changes include migration steps | Users need actionable guidance |
| Security fixes in dedicated section | Visibility for security-conscious users |
| Empty sections are omitted | Clean, scannable output |
| Duplicate bullets are removed | One entry per change |
| Scope shown for multi-package repos | `auth: add OAuth2 support` |

## Commit Linting Checklist

- [ ] Commit starts with valid type (`feat`, `fix`, `perf`, etc.)
- [ ] Description is lowercase, imperative mood, < 72 chars
- [ ] Scope matches known modules (if enforced)
- [ ] Breaking changes use `!` suffix or `BREAKING CHANGE:` footer
- [ ] No merge commits in changelog range

## Monorepo Strategy

- Filter commits by scope for package-specific changelogs
- Keep infrastructure changes in root CHANGELOG.md
- Store package changelogs at package root
- Use scoped commits: `feat(api): add pagination endpoint`

## Proactive Triggers

Surface these issues WITHOUT being asked:

- >20 commits without changelog update → flag documentation drift
- Non-conventional commit messages → flag automation breakage
- No changelog entry for breaking changes → flag user communication gap

## Output

```markdown
# Changelog

## [X.Y.Z] - YYYY-MM-DD

### Breaking Changes
- **scope:** Description of breaking change
  Migration: [steps to migrate]

### Added
- **scope:** New feature description (#PR)

### Fixed
- **scope:** Bug fix description (#PR)

### Changed
- **scope:** Change description (#PR)

### Security
- **scope:** Security fix description (#PR)

### Deprecated
- **scope:** Deprecation notice and timeline
```
