# 17 · Skill Packs

The curated core and the plugin marketplace. ArkaOS ships 275 skills, and you should not pay context rent for all of them in every session. Since v4.14 the distribution model has two halves: a curated core that installs by default, and 16 department packs you add when you need them.

## Why a curated core

Every skill you install adds its name and description to what your AI runtime can load per session. Install 275 and you pay for 275, whether the session is about code review or cart recovery. Collections that dump everything into the context window perform worse for it.

The curated core keeps the always-on surface small and enforces that in CI: the build fails if the default install grows past 80 skills or 40,000 description characters. The audit runs from the repository, so the promise is checkable:

```bash
python scripts/tools/skill_budget.py
```

What the core contains:

| Layer | Content |
|---|---|
| Main orchestrator | `/arka`, routing, standups, system commands |
| 17 department hubs | One entry point per department (`/dev`, `/mkt`, `/fin`, ...) |
| 14 meta skills | The cross-cutting machinery: evidence flow, Forge planning, fusion, recipes, research |
| 37 curated sub-skills | The two or three most used skills of each department, chosen by usage |

## Installing a department pack

The rest of the catalog lives on the ArkaOS plugin marketplace, one pack per department. Inside Claude Code:

```
/plugin marketplace add andreagroferreira/arka-os
/plugin install arkaos-marketing@arkaos
```

Available packs: `arkaos-dev`, `arkaos-brand`, `arkaos-marketing`, `arkaos-finance`, `arkaos-strategy`, `arkaos-ecom`, `arkaos-kb`, `arkaos-ops`, `arkaos-pm`, `arkaos-saas`, `arkaos-landing`, `arkaos-content`, `arkaos-community`, `arkaos-sales`, `arkaos-leadership`, `arkaos-org`.

Each pack namespaces its skills (`arkaos-marketing:cold-email`), which also resolves the handful of slug names that exist in more than one department. Nothing collides with skills you already have.

To update installed packs after a new ArkaOS release:

```
/plugin marketplace update arkaos
```

## Keeping the full catalog instead

Machines that installed before v4.14 keep the complete skill set and see a deprecation notice on update. Nothing shrinks silently. To choose a mode explicitly:

```bash
npx arkaos update --skills curated   # lean default
npx arkaos update --skills full      # complete catalog, kept across updates
```

The choice persists in `~/.arkaos/skills-mode.json`. Fresh installs default to curated.

## How the packs stay honest

The plugin trees are generated from the same in-repo sources as the core, by `scripts/marketplace_gen.py`. A byte-level drift gate compares the committed tree against a fresh generation on every CI run, so editing a generated file breaks the build. When a skill is promoted into a department, regeneration places it in that department's pack automatically.

If you ask for a skill that lives in a pack you have not installed, ArkaOS tells you which pack to install rather than improvising an answer without it.

## Checking your machine

```bash
npx arkaos doctor
```

The `skills-surface` check compares what is deployed against your chosen mode. It only warns, and it never deletes: skills it does not recognize (your own, or ecosystem packs) are untouchable by design.
