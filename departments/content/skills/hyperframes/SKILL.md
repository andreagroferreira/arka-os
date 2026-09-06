---
name: content/hyperframes
description: >
  Direct Hyperframes work — video-as-code in HTML/CSS/JS + GSAP rendered to a
  deterministic MP4 — on a new or existing project: compose, animate, keyframe,
  caption, mix audio, port from Remotion, import from Figma, render, preview,
  publish, batch-render. Loads the /hyperframes router FIRST and wraps it in the
  ArkaOS doctrine (Simão owns it, [arka:design] marker on compositions,
  dev/watch review of the render, Quality Gate). TRIGGER: "/content
  hyperframes", "renderiza o vídeo", "render this composition", "ajusta os
  keyframes", "adiciona legendas embutidas", "motion graphic", "title card",
  "lower third", "converte este projeto Remotion", "importa do Figma para
  vídeo", "slideshow", "faceless explainer", "explainer sem rosto", any cwd
  holding hyperframes.json or BRIEF.md + STORYBOARD.md (Synapse L5 project
  signal — inside a running /content video pipeline the pipeline keeps
  ownership and calls this skill at its edit/render phase). SKIP: brief-to-MP4
  production with research, script and asset generation -> content/video-produce
  (its edit/render phase loads this skill); one-off environment install
  -> content/video-setup; watching or analysing a video -> dev/watch;
  scroll-driven website from a video -> dev/animated-website.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, Skill, WebFetch]
metadata:
  origin: arkaos
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` (and
> `mcp__graphify__query_graph` when configured) and cite `[[wikilinks]]`
> or graph nodes — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Hyperframes — `/content hyperframes <task>`

> **Agent:** Simão (Video Producer) | **Engine:** Hyperframes by HeyGen (Apache-2.0) — core skills under `~/.claude/skills/`, creation workflows installed on demand by the router
> **Rule:** the `/hyperframes` router owns the workflow; this skill owns the ArkaOS ceremony around it. Never reconstruct Hyperframes from memory.

## Phase 0 — Preflight (one command, always)

```
npx hyperframes skills check
```

| Result | Action |
|---|---|
| `N current`, nothing outdated | proceed |
| `↑ outdated` listed | `npx hyperframes skills update` refreshes the core set and every skill already installed, and leaves a workflow that was never installed alone; the router installs that one itself when it selects it, with `npx hyperframes skills update <workflow>` |
| `~/.claude/skills/hyperframes/SKILL.md` missing | STOP with exactly "Hyperframes não instalado — corre /content video-setup". Never improvise the format. |
| `node --version` below 22, or no `ffmpeg` | STOP and print the platform install line — `content/video-setup` owns installs, this skill never mutates system packages |

## Phase 1 — Load the router, then follow it

Invoke `Skill(hyperframes)` FIRST. It resumes project state (`BRIEF.md`, `hyperframes.json`, `STORYBOARD.md`), runs the intent interview for fresh creation, picks the owning workflow from its route table and installs it. Two ArkaOS constraints on top:

- A specific operation on an existing project (inspect, diagnose, validate, preview, render, publish, batch-render): the router loads `/hyperframes-cli` — do that operation and nothing else.
- Fresh creation: the interview ends by writing `BRIEF.md`. Read the marketing context first (KB-first: `WizardingCode/Marketing/product-marketing.md` in Obsidian, else the project-local `.agents/product-marketing.md`) so the brief carries the real positioning, never an invented one.

## Phase 2 — Compose under the design doctrine

A Hyperframes composition is `.html`, so the frontend excellence gate applies exactly as it does to UI (constitution `excellence-mandate`, `core/workflow/frontend_gate.py`). Before the first Write/Edit of a composition emit the structured marker on a line of its own:

```
[arka:design] benchmark=<named reference: Linear launch films, Vercel Ship keynote, Stripe Sessions…> skills=hyperframes,hyperframes-core,hyperframes-animation,<hyperframes-creative|hyperframes-keyframes|hyperframes-audio as loaded> tokens=<brand tokens path|none>
```

- ArkaOS-branded output follows The Assembly v1.1 (`docs/design/brand-assembly/`, skill `arkaos-design`): zinc + rose, Signal used sparingly, Space Grotesk / IBM Plex — `tokens=` points there.
- Client work: `tokens=` points at the project's design-system document (`project-design-system-prerequisite`): no document, no composition — extract it first with `/brand design-system`.
- Anti-default: no template title cards, no stock easing on every element, no "AI video" look. GSAP timelines with labels and position parameters (Simão's framework): load `dev/gsap` for GSAP itself (`references/timeline.md` for timelines, labels and position parameters; `references/core.md` for tweens and easing; `references/plugins.md` for kinetic type and SplitText; `references/performance.md` before the render) — upstream `hyperframes-animation` covers the Hyperframes-specific timing, it does not replace it. Word-level captions through `/embedded-captions` whenever there is speech.
- Assets: `/media-use` resolves BGM, SFX, images and logos from licensed sources before anything is downloaded. Generated assets come from Higgsfield (`content/image-create`, `generate_video`); credits are metered — never regenerate in a loop without explicit approval.

## Phase 3 — Render and review with evidence

1. Render through the router / `/hyperframes-cli` (`npx hyperframes render …`). Keep the command and exit code on record (G3 of the evidence flow).
2. Review the render with `dev/watch` on the output MP4: complete frames + timestamped transcript. Judge the hook (first 3 s), pacing, caption accuracy, audio sync, aspect ratio, brand fidelity. Screenshots are not evidence; frames are.
3. Loop on defects. A reshoot the review demands is never blocked by time or token cost; the CostGovernor budget is the only ceiling.

## Phase 4 — Quality Gate and delivery

Marta orchestrates Eduardo (on-screen copy, captions, description) and Francisca (render spec, determinism, composition code quality). Binary verdict. Deliver the master MP4, the per-platform reframes the brief asked for, the SRT when captions exist, and the `[arka:design]` line plus review notes in the delivery summary. Output goes to Obsidian `WizardingCode/Content/Video/<date>-<slug>/` (or the client project's vault path).

## Never

- Never load `/hyperframes` when the preflight fails, and never guess what Hyperframes is.
- Never bypass the router's route table with a hand-picked workflow "because it looks right" — the router reads `references/routes/<workflow>.md` and decides.
- Never ship a render nobody watched.
- Never install Hyperframes skills from a marketplace other than `heygen-com/hyperframes`; third-party "video" skills that wrap paid engines or hook every `*video*` skill are rejected by decision (spec `hyperframes-routing`).

## Examples

```
/content hyperframes "renderiza o projeto em ./launch-film e revê o resultado"
/content hyperframes "adiciona legendas embutidas word-level ao talking head em ./ep03"
/content hyperframes "converte a composição Remotion em ./remotion-intro para Hyperframes"
/content hyperframes "motion graphic de 8 s com o número 30K a subir, brand ArkaOS"
```
