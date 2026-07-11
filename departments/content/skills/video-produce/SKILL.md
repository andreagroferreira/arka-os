---
name: content/video-produce
description: >
  End-to-end video production — brief to rendered MP4: research → Hollywood
  script → storyboard → Higgsfield asset generation → Hyperframes
  edit/render → virality QA, with per-capability backend degradation
  (never blocks on a missing tool). TRIGGER: "/content video <topic>",
  "produz um vídeo sobre", "faz-me um vídeo", "produce a video", "edit
  this video", "edita este vídeo", "monta o vídeo do episódio". SKIP:
  script only -> content/script-structure; short-form batch of RENDERED
  videos -> /content shorts (content-shorts-produce workflow); short-form
  scripting only -> /content short (content/short-form); one-off
  environment setup ->
  content/video-setup; YouTube channel strategy -> content/youtube-strategy.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` and cite
> `[[wikilinks]]` — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Video Produce — `/content video <topic>`

> **Agent:** Simão (Video Producer, orchestrating the production sub-squad)
> **Full pipeline:** the `content-video` enterprise workflow; invoked standalone, this skill runs the same phases with the same gates.

## Phase 0 — Preflight (non-interactive)

Run the video-setup checks silently and pick the strongest available
tier PER CAPABILITY. Print the matrix, state the tiers chosen, proceed
— a missing backend selects the next tier, it never blocks
(multi-backend rule):

| Capability | Full | Degraded | Manual |
|---|---|---|---|
| Asset generation | Higgsfield MCP (`generate_image/video/audio`, `create_voice`, `motion_control`, `upscale`) | `arka-comfyui` local | asset brief: engine-ready prompts per shot |
| Edit / render | Hyperframes skills (Node 22 + FFmpeg; load `/hyperframes` router) | Higgsfield `explainer_video` / `shorts_studio` server-side | edit-ready package: script + assets + shot list/EDL + SRT captions |
| Research | agent-reach | firecrawl + WebSearch | KB-only |

## Pipeline (gates match the content-video workflow)

1. **Brief** — target (brand channel / personal / client — anonymized /
   new niche), format, platform, length. → user approval.
2. **Research** — `/content research <topic>` contract: sourced
   production brief (Madalena → Dinis). → user approval on the brief.
3. **Script (Joana, Hollywood grade)** — beat sheet first (Save the
   Cat / Story Circle adapted to length), then full script in
   scene/shot/VO/on-screen-text columns; Hook Architecture on the first
   30 seconds; 3 hook variants (Filipe). Never-default voice — no AI
   clichés, no listicle cadence. → user approval.
4. **Storyboard (Simão)** — shot list + per-shot generation prompts +
   audio/VO plan + thumbnail package (Isabel, via the brand design
   doctrine: benchmark named, `[arka:design]` marker emitted).
   → **user approval (creative lock before money is spent)**.
5. **Asset generation** — execute per the matrix. Voice via
   `create_voice`/`generate_audio`; b-roll via `generate_video`
   (cost-tier models for routine shots, hero models only for hero
   shots); stills via `generate_image`; post via `remove_background`/
   `upscale`/`reframe`. → **user approval on generated assets —
   Higgsfield credits are metered; NEVER regenerate in a loop without
   explicit approval.**
6. **Edit / render** — PREFLIGHT (one line, mandatory before the Full
   tier): if `ls ~/.claude/skills | grep -qi hyperframes` fails, STOP
   with the exact message "Hyperframes não instalado — corre
   /content video-setup" — NEVER load `/hyperframes` blind or improvise
   what Hyperframes might be. (Tier degradation is a Phase 0 decision;
   reaching this step on the Full tier with the skills missing means
   setup drift: the honest move is the stop + fix command, or an
   explicitly re-stated downgrade to the Degraded/Manual tier.)
   Full tier: load the `/hyperframes` router skill, pick the
   workflow (`/talking-head-recut`, `/faceless-explainer`,
   `/product-launch-video`…), compose in HTML+GSAP (load `gsap-core` +
   `gsap-timeline` for motion graphics; `gsap-plugins` for kinetic
   type/SplitText), add word-level captions (`/embedded-captions`),
   render MP4. Degraded tier: hand assets+script to Higgsfield
   `explainer_video`/`shorts_studio`. Manual tier: assemble the
   edit-ready package and say exactly what a human editor gets.
7. **Virality QA** — STEPPS audit pre-publish (Filipe) +
   `virality_predictor`/`video_analysis` when Higgsfield is live
   (hook strength, retention risk) + technical QC (sync, caption
   accuracy, aspect ratios).
8. **Quality Gate** — Marta + Eduardo (script/captions/description
   copy) + Francisca (render quality, spec compliance). Binary.
9. **Delivery** — master MP4 + 9:16 reframe + thumbnail + title/
   description/tags + SRT + repurposing spec (Nuno, 1→30+). Output to
   Obsidian `WizardingCode/Content/Video/<date>-<slug>/`.

## Quality doctrine

- The chosen backend tier is STATED in the delivery — never imply a
  render happened when the manual package shipped.
- Every visual asset follows the anti-default doctrine (squad reference
  §8): the video must not look like every other AI video, same bar as
  UI work.
- Time and token cost are never arguments against a reshoot the QG
  demands (excellence-mandate); the CostGovernor budget and the phase-5
  approval gate are the only ceilings.

## Examples

```
/content video "why AI agents fail in production"
/content video "lançamento da feature X" --format explainer --platform youtube
```
