# PR 2 — Lazy-Load Skills Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement task-by-task.

**Goal:** Reduce per-session token consumption by 40-70k by splitting heavyweight orchestrator SKILL.md files into thin orchestrators + on-demand reference docs.

**Architecture:** Each skill's SKILL.md keeps only what Claude needs at invocation (purpose, command table, routing logic, squad summary). Deep content (full workflows, detailed roles, per-feature playbooks) moves to `references/*.md` inside the skill directory. The SKILL.md references these via relative path; Claude reads them with the Read tool only when the specific capability is needed.

**Tech Stack:** Markdown, YAML frontmatter, no code changes.

---

## Context & Baseline

- Skills location: `~/.claude/skills/arka-*/SKILL.md`
- Top 10 offenders (ranked by lines):
  1. arka-forge (649)
  2. arka-comfyui (586)
  3. arka-knowledge (474)
  4. arka-client_commerce (463)
  5. arka-operations (422)
  6. arka-onboard (389)
  7. arka-client_publisher (375)
  8. arka-ecommerce (363)
  9. arka-update (357)
  10. arka-platform-arka (330)
- Target: reduce each to ≤120 lines SKILL.md, move rest to `references/`
- Branch: `optimize/token-consumption-pr2` (from master)

## The Skill Split Pattern

**SKILL.md keeps (≤120 lines):**
- YAML frontmatter (`name`, `description`)
- 1-paragraph purpose
- Command table (full — this is routing, must stay)
- Squad role table (compact — just `Role | Agent Type | One-line responsibility`)
- "Orchestration Workflow" section as short bullets pointing to `references/workflows.md`
- "On-demand references" section listing what's available

**`references/` subdirectory holds:**
- `workflows.md` — full orchestration flows (standard, release, audit, evolve, etc.)
- `squad.md` — full agent descriptions with behavioral profiles
- `commands.md` — detailed per-command documentation if needed
- Any skill-specific deep dives

**Reference loading:** The SKILL.md instructs Claude: *"For workflow details see `references/workflows.md`"*. Claude uses Read only if the current task needs that content.

---

## Task 1: Establish pattern with arka-platform-arka (pilot)

**Why first:** It's the skill we just used, 330 lines, well-understood, and it's OUR orchestrator — low risk, immediate validation.

**Files:**
- Modify: `~/.claude/skills/arka-platform-arka/SKILL.md`
- Create: `~/.claude/skills/arka-platform-arka/references/workflows.md`
- Create: `~/.claude/skills/arka-platform-arka/references/squad.md`

- [ ] **Step 1.1: Read current SKILL.md fully**

Command: `cat ~/.claude/skills/arka-platform-arka/SKILL.md | wc -l`
Expected: 330 (baseline)

- [ ] **Step 1.2: Extract orchestration workflows to `references/workflows.md`**

Move these sections verbatim from SKILL.md to the new file:
- "Standard Flow (feature, fix, docs)"
- "Release Flow"
- "Audit Flow"
- "Evolve Flow"
- "Status Command"
- "Metrics Command"
- "Skill Create Command"
- "Agent Create Command"

Prepend file with:
```markdown
# arka-platform-arka — Full Orchestration Workflows

Referenced from SKILL.md. Read only when executing the relevant flow.
```

- [ ] **Step 1.3: Extract full squad details to `references/squad.md`**

Move the "Squad — The Platform Team" table expansions if they exist; keep the compact table in SKILL.md.

- [ ] **Step 1.4: Rewrite SKILL.md to thin orchestrator**

Keep:
- Frontmatter
- Project table
- Architecture diagram (~15 lines)
- Squad table (compact)
- Commands tables (all three: Standard, Release, Auto-Evolution, Skill & Agent Management)
- Short "Orchestration" section: 1 paragraph + `See references/workflows.md for detailed flows`
- Branch Strategy table
- /wiz Integration (3 bullets)
- Obsidian Output (3 lines)

Target: ≤120 lines.

- [ ] **Step 1.5: Validate line count**

Command: `wc -l ~/.claude/skills/arka-platform-arka/SKILL.md`
Expected: ≤120

- [ ] **Step 1.6: Smoke-test the skill**

Open a new Claude Code session, run `/platform-arka status`. Verify:
- Claude executes status flow correctly
- If it needs workflow details, it Reads `references/workflows.md`
- No broken references

- [ ] **Step 1.7: Commit**

```bash
git add ~/.claude/skills/arka-platform-arka/
git commit -m "perf(skills): split arka-platform-arka into thin orchestrator + references"
```

---

## Task 2: arka-forge (649 lines → target ≤120)

**Files:**
- Modify: `~/.claude/skills/arka-forge/SKILL.md`
- Create: `~/.claude/skills/arka-forge/references/workflows.md`
- Create: `~/.claude/skills/arka-forge/references/complexity-engine.md`
- Create: `~/.claude/skills/arka-forge/references/critic-synthesis.md`

- [ ] **Step 2.1: Read current SKILL.md and identify sections to extract**

Command: `cat ~/.claude/skills/arka-forge/SKILL.md`

Identify: complexity escalation logic, critic synthesis details, approach generation, any sections >30 lines.

- [ ] **Step 2.2: Extract complexity engine details to `references/complexity-engine.md`**

Move detailed complexity scoring rules, escalation thresholds, decision trees.

- [ ] **Step 2.3: Extract critic synthesis to `references/critic-synthesis.md`**

Move the critic review flow, synthesis algorithm, conflict resolution.

- [ ] **Step 2.4: Extract orchestration workflows to `references/workflows.md`**

Move full workflow execution flows.

- [ ] **Step 2.5: Rewrite SKILL.md to thin orchestrator**

Keep: frontmatter, purpose, command table, complexity tiers (compact table), references section.

- [ ] **Step 2.6: Validate and smoke-test**

Command: `wc -l ~/.claude/skills/arka-forge/SKILL.md` → ≤120
Smoke test: trigger a forge plan, verify complexity detection still works.

- [ ] **Step 2.7: Commit**

```bash
git commit -m "perf(skills): split arka-forge into thin orchestrator + references"
```

---

## Task 3: arka-comfyui (586 lines → ≤120)

**Files:**
- Modify: `~/.claude/skills/arka-comfyui/SKILL.md`
- Create: `~/.claude/skills/arka-comfyui/references/squads.md`
- Create: `~/.claude/skills/arka-comfyui/references/workflows.md`

- [ ] **Step 3.1:** Read SKILL.md, identify "ComfyUI Core" and "Custom Nodes" squad sections
- [ ] **Step 3.2:** Extract two-squad structure details to `references/squads.md`
- [ ] **Step 3.3:** Extract workflows to `references/workflows.md`
- [ ] **Step 3.4:** Rewrite SKILL.md keeping frontmatter, purpose, command table, compact squad summary
- [ ] **Step 3.5:** Validate line count ≤120, smoke-test
- [ ] **Step 3.6:** Commit: `perf(skills): split arka-comfyui into thin orchestrator + references`

---

## Task 4: arka-knowledge (474 lines → ≤120)

**Files:**
- Modify: `~/.claude/skills/arka-knowledge/SKILL.md`
- Create: `~/.claude/skills/arka-knowledge/references/ingestion-pipeline.md`
- Create: `~/.claude/skills/arka-knowledge/references/async-processing.md`

- [ ] **Step 4.1:** Extract async background processing details (YouTube, PDF, audio) to `references/ingestion-pipeline.md`
- [ ] **Step 4.2:** Extract queue/worker mechanics to `references/async-processing.md`
- [ ] **Step 4.3:** Rewrite SKILL.md: purpose, command table, compact squad, references
- [ ] **Step 4.4:** Validate ≤120 lines, smoke-test with `/knowledge` command
- [ ] **Step 4.5:** Commit

---

## Task 5: arka-client_commerce (463 lines → ≤120)

**Files:**
- Modify: `~/.claude/skills/arka-client_commerce/SKILL.md`
- Create: `~/.claude/skills/arka-client_commerce/references/workflows.md`
- Create: `~/.claude/skills/arka-client_commerce/references/integration.md`

- [ ] **Step 5.1:** Extract supplier-to-Shopify integration details to `references/integration.md`
- [ ] **Step 5.2:** Extract workflows to `references/workflows.md`
- [ ] **Step 5.3:** Rewrite SKILL.md thin
- [ ] **Step 5.4:** Validate ≤120, smoke-test
- [ ] **Step 5.5:** Commit

---

## Task 6: arka-operations (422 lines → ≤120)

**Files:**
- Modify: `~/.claude/skills/arka-operations/SKILL.md`
- Create: `~/.claude/skills/arka-operations/references/clickup-ops.md`
- Create: `~/.claude/skills/arka-operations/references/calendar-email.md`

- [ ] **Step 6.1:** Extract ClickUp task management to `references/clickup-ops.md`
- [ ] **Step 6.2:** Extract Gmail + Calendar flows to `references/calendar-email.md`
- [ ] **Step 6.3:** Rewrite SKILL.md thin
- [ ] **Step 6.4:** Validate ≤120, smoke-test
- [ ] **Step 6.5:** Commit

---

## Task 7: arka-onboard (389 lines → ≤120)

- [ ] **Step 7.1:** Extract stack-detection logic to `references/stack-detection.md`
- [ ] **Step 7.2:** Extract MCP configuration details to `references/mcp-config.md`
- [ ] **Step 7.3:** Rewrite SKILL.md thin
- [ ] **Step 7.4:** Validate ≤120, smoke-test
- [ ] **Step 7.5:** Commit

---

## Task 8: arka-client_publisher (375 lines → ≤120)

- [ ] **Step 8.1:** Extract event-specific workflows to `references/workflows.md`
- [ ] **Step 8.2:** Extract squad routing to `references/squad.md`
- [ ] **Step 8.3:** Rewrite SKILL.md thin
- [ ] **Step 8.4:** Validate ≤120, smoke-test
- [ ] **Step 8.5:** Commit

---

## Task 9: arka-ecommerce (363 lines → ≤120)

- [ ] **Step 9.1:** Extract 5-parallel-agents audit flow to `references/audit-flow.md`
- [ ] **Step 9.2:** Extract RFM/pricing/marketplace details to `references/playbooks.md`
- [ ] **Step 9.3:** Rewrite SKILL.md thin
- [ ] **Step 9.4:** Validate ≤120, smoke-test
- [ ] **Step 9.5:** Commit

---

## Task 10: arka-update (357 lines → ≤120)

- [ ] **Step 10.1:** Extract sync engine instructions to `references/sync-engine.md`
- [ ] **Step 10.2:** Extract hybrid orchestration flow to `references/workflows.md`
- [ ] **Step 10.3:** Rewrite SKILL.md thin (this is a critical skill — be careful, smoke-test thoroughly)
- [ ] **Step 10.4:** Validate ≤120, smoke-test with real `/arka update` on a test project
- [ ] **Step 10.5:** Commit

---

## Task 11: Verify 256-skill manifest unchanged

**Why:** The skill list in the session-start system-reminder is the Claude Code runtime auto-indexing SKILL.md frontmatter. We must not change any `name` or `description` field — only move body content.

- [ ] **Step 11.1:** Diff all frontmatter blocks

Command:
```bash
for skill in ~/.claude/skills/arka-{forge,comfyui,knowledge,client_commerce,operations,onboard,client_publisher,ecommerce,update,platform-arka}/SKILL.md; do
  echo "=== $skill ==="
  head -5 "$skill"
done
```

Expected: every frontmatter still has intact `name:` and `description:` fields.

- [ ] **Step 11.2:** Restart Claude Code, check system-reminder skill list still has all 10 skills with same descriptions

Expected: No skill disappears, no description changes.

---

## Task 12: Measure token savings

- [ ] **Step 12.1:** Total lines before/after

```bash
# Before (from baseline):
# Total target skills: 4,349 lines

# After:
wc -l ~/.claude/skills/arka-{forge,comfyui,knowledge,client_commerce,operations,onboard,client_publisher,ecommerce,update,platform-arka}/SKILL.md | tail -1
```

Expected: ≤1,200 lines total (down from 4,349) = ~3,100 lines saved = ~12,000 tokens per skill invocation NOT loaded into prompt when Claude doesn't need the detail.

Cumulative savings across a session that invokes 3-4 of these skills: ~40k tokens.

- [ ] **Step 12.2:** Write savings report to plan document

Append to this file a "Results" section with actual numbers.

---

## Task 13: Quality Gate

- [ ] **Step 13.1:** Dispatch Marta (CQO) review via `superpowers:requesting-code-review`

Focus areas:
- No skill broke (all smoke tests pass)
- Descriptions still accurate (they're the manifest Claude sees at session start)
- References are discoverable (SKILL.md must tell Claude where to look)
- No content lost — moved, not deleted

- [ ] **Step 13.2:** Address any REJECTED feedback, re-submit

- [ ] **Step 13.3:** On APPROVED, merge branch to master

```bash
git checkout master
git merge optimize/token-consumption-pr2 --no-ff
```

- [ ] **Step 13.4:** Do NOT release yet — bundle with PR 3 and PR 4 for a single v2.16.0 release

---

## Rollback Plan

If a skill breaks in production:
```bash
git checkout master -- ~/.claude/skills/<skill-name>/SKILL.md
rm -rf ~/.claude/skills/<skill-name>/references/
```

Each skill is an independent commit, so rollback is granular.

---

## Out of Scope (deferred)

- Remaining 246 skills not in top 10 — can be done later if needed; 80% of bloat is in these 10
- Ecosystem orchestrators we didn't touch (arka-wizardingcode, arka-client_retail, arka-client_video, arka-client_fashion, arka-client_media, arka-edp, arka-lora-tester, arka-client_advisory) — add to follow-up if wins warrant

## Risks

1. **Breaking a skill silently** — mitigated by smoke test per task
2. **Reference files not being read when needed** — SKILL.md must explicitly tell Claude: *"For X, Read references/Y.md first"*
3. **Frontmatter corruption** — verified in Task 11
