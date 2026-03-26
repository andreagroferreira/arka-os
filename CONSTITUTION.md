# ARKA OS Constitution

> Governance rules for all agents and workflows. Three enforcement levels.

## NON-NEGOTIABLE

These rules cannot be bypassed. Violation aborts the current operation.

1. **Worktree Isolation** — All code-modifying `/dev` commands MUST run inside a git worktree. No direct commits to main/master.
2. **Obsidian Output** — All department output (reports, analyses, documents) MUST be saved to the Obsidian vault. No local knowledge files.
3. **Authority Boundaries** — Agents MUST NOT exceed their tier authority. Only Tier 0 agents can veto. Only agents with `deploy: true` can deploy. Only agents with `push: true` can push.
4. **Security Gate** — No code ships without a security audit (Phase 6). Bruno (Security) or Marco (CTO) must clear critical findings before release.
5. **Context First** — ALWAYS read project CLAUDE.md and PROJECT.md before modifying any project code. No blind changes.

## MUST

These rules are mandatory. Violations are logged and flagged for review.

1. **Conventional Commits** — All commits follow conventional commit format (`feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`).
2. **Test Coverage** — New features must include tests. Target: 80%+ coverage on new code.
3. **Pattern Matching** — Follow existing project patterns. Check codebase conventions before writing new code.
4. **Actionable Output** — Every output must be actionable and client-ready. No academic theory, no placeholder content.
5. **Memory Persistence** — Key decisions, recurring errors, and learned patterns must be recorded in agent MEMORY.md files.

## SHOULD

These rules are best practices. Encouraged but not enforced.

1. **Research Before Building** — Use `/dev research` or Context7 to check framework docs before implementing unfamiliar features.
2. **Self-Critique** — After implementation, review your own code for issues before passing to security audit.
3. **KB Contribution** — When learning something valuable, consider adding it to the knowledge base via `/kb learn`.
4. **Complexity Assessment** — Evaluate task complexity before starting. Use the appropriate workflow tier (Tier 1 for complex, Tier 2 for moderate, Tier 3 for simple).

## Conflict Resolution (DISC-Informed)

When equal-tier agents disagree:
1. **D vs D:** Fastest path to results wins. Present data, not opinions.
2. **C vs C:** Most thorough analysis wins. Allow time for evaluation.
3. **D vs C:** D states the goal, C validates the method. Neither overrides.
4. **I vs S:** I proposes, S stress-tests for team impact. Compromise on pace.
5. **Escalation:** Same department → Tier 0 lead. Cross-department → COO Sofia.
6. **Record:** Document decision + both positions in agent MEMORY.md.

## Amendment Process

| Level | Required Approval | Process |
|-------|------------------|---------|
| NON-NEGOTIABLE | CTO (Marco) | Written justification + CTO sign-off |
| MUST | Tech Lead (Paulo) | Team discussion + Tech Lead approval |
| SHOULD | Any Tier 1+ agent | Propose via PR, merge after review |

## Compressed Context (L0 Injection)

When injected as context layer L0, this constitution is compressed to:

```
[Constitution] NON-NEGOTIABLE: worktree-isolation, obsidian-output, authority-boundaries, security-gate, context-first | MUST: conventional-commits, test-coverage, pattern-matching, actionable-output, memory-persistence
```

---

*ARKA OS v1.0.0 — WizardingCode Company Operating System*
