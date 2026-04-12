# arka-platform-arka — Full Orchestration Workflows

Referenced from SKILL.md. Read only when executing the relevant flow.

## Standard Flow (feature, fix, docs)

```
1. Context Loading
   - Read CLAUDE.md, VERSION, package.json, pyproject.toml
   - Load recent git history (git log --oneline -20)
   - Check current test status (pytest --tb=no -q)

2. Analysis & Planning
   - Product Owner assesses scope and priority
   - Skill Architect identifies affected areas (core/installer/dashboard/skills)
   - Assign appropriate engineer(s) based on affected layers

3. Plan Presentation & Approval
   - Present plan: affected files, squad roles, scope estimate
   - User approves before any code execution

4. Execution
   - Features/evolve: branch (feature/* or evolve/*) + worktree isolation
   - Hotfixes/patches: direct on master
   - Squad agents execute in their domain
   - QA Engineer runs tests after changes

5. Quality Gate
   - Marta (CQO) orchestrates review
   - Eduardo (Copy) reviews all text output
   - Francisca (Tech) reviews all code
   - APPROVED or REJECTED — no exceptions

6. Documentation
   - Update Obsidian at WizardingCode Internal/ArkaOS/
```

## Release Flow

```
1. Pre-flight
   - Run full test suite: cd /Users/andreagroferreira/AIProjects/arka-os && python -m pytest tests/ --tb=short -q
   - Check git status (must be clean working tree)
   - Review changes since last release: git log $(git describe --tags --abbrev=0)..HEAD --oneline

2. Preparation
   - Determine version bump type (patch/minor/major) from changes
   - Update VERSION, package.json version, pyproject.toml version
   - Generate changelog from conventional commits
   - Commit: git commit -m "chore: bump to vX.Y.Z"

3. Confirmation Gate (PAUSE)
   - Present to user: new version number, changelog summary, files changed count
   - WAIT for explicit user confirmation before proceeding
   - If user declines: revert bump commit, stop

4. Publish (only after user confirms)
   - git push origin master
   - gh release create vX.Y.Z --title "vX.Y.Z" --notes "<changelog>"
   - npm publish:
     ```bash
     # Method 1: Direct (if ~/.npmrc has valid publish token)
     npm publish --access public

     # Method 2: Temp config (if Method 1 fails with 403)
     TMPRC=$(mktemp)
     echo "//registry.npmjs.org/:_authToken=<TOKEN>" > "$TMPRC"
     npm publish --access public --userconfig "$TMPRC"
     rm -f "$TMPRC"
     ```
   - Verify: npm view arkaos version (must show new version)
   - npm account: wizardingcode | Package: arkaos | Access: public

5. Post-release
   - Save release notes to Obsidian: WizardingCode Internal/ArkaOS/Releases/vX.Y.Z.md
   - Update metrics snapshot
```

## Audit Flow

```
1. Platform Analyst scans the codebase:

   a. Department completeness:
      - List all departments/ subdirectories
      - Check each has: agents/*.yaml, skills/*/SKILL.md, workflows/*.yaml
      - Flag departments missing any component

   b. Agent validation:
      - Parse all departments/*/agents/*.yaml
      - Verify 4-framework behavioral DNA (DISC, Enneagram, Big Five, MBTI)
      - Flag agents with incomplete profiles

   c. Skill coverage:
      - List all ~/.claude/skills/arka-*/SKILL.md
      - Cross-reference with department command tables
      - Flag commands without corresponding skills

   d. Test coverage:
      - Run: python -m pytest tests/ --tb=no -q
      - Count test files vs source files
      - Flag untested modules

   e. Code quality:
      - Check for unused imports, dead code patterns
      - Verify CLAUDE.md accuracy against actual file structure
      - Check VERSION consistency across package.json, pyproject.toml, VERSION

2. Present findings ranked by impact (high/medium/low)
3. Save audit report to Obsidian: WizardingCode Internal/ArkaOS/Audits/YYYY-MM-DD.md
```

## Evolve Flow

```
1. Run audit (automatic first step — reuse audit flow above)

2. Proposal
   - Filter audit findings to actionable improvements
   - Rank by impact and effort (quick wins first)
   - Present top 5 proposals with:
     - What: description of the improvement
     - Why: impact on ArkaOS quality/completeness
     - How: which squad member(s) implement it
     - Effort: small/medium/large
   - User selects which proposals to implement

3. Implementation
   - Create branch: evolve/YYYY-MM-DD-<description>
   - Use worktree isolation
   - Each improvement as a separate commit with conventional commit message
   - QA Engineer runs tests after each change

4. Quality Gate
   - Marta (CQO) orchestrates final review
   - Eduardo (Copy) reviews any text changes
   - Francisca (Tech) reviews any code changes
   - APPROVED → merge to master
   - REJECTED → fix and re-submit
```

## Status Command

```
1. Read current version from VERSION file
2. Run: python -m pytest tests/ --tb=no -q (capture pass/fail/total)
3. Run: git log --oneline -10 (recent activity)
4. Run: git describe --tags --abbrev=0 (latest release tag)
5. Count: departments, agents, skills, tests
6. Present formatted status:

   === ArkaOS Platform Status ===
   Version: X.Y.Z
   Latest Release: vX.Y.Z (YYYY-MM-DD)
   Tests: X passed / Y total
   Departments: 17 | Agents: 65 | Skills: 244+
   Recent commits: [last 5]
   Reports to: /wiz (WizardingCode Internal)
   ==============================
```

## Metrics Command

```
1. Count files:
   - departments/*/agents/*.yaml → agent count
   - ~/.claude/skills/arka-*/SKILL.md → skill count
   - departments/ subdirectories → department count
   - tests/python/ test files → test count

2. Check completeness:
   - Departments with all 3 components (agents, skills, workflows)
   - Agents with full 4-framework DNA

3. Version history:
   - git tag --sort=-version:refname | head -10

4. Present formatted metrics dashboard
```

## Skill Create Command

```
1. Ask for skill name and target department
2. Create directory: ~/.claude/skills/arka-<name>/
3. Scaffold SKILL.md with:
   - YAML frontmatter (name, description)
   - Command table template
   - Squad roles section
   - Orchestration workflow template
4. Inform user to register in settings.json if needed
```

## Agent Create Command

```
1. Ask for agent name, department, and role
2. Scaffold YAML file at departments/<dept>/agents/<name>.yaml with:
   - Basic identity (name, role, department)
   - 4-framework DNA template (DISC, Enneagram, Big Five, MBTI) with placeholders
3. Run agent validate to check consistency
```
