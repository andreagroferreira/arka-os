---
name: video-produce
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
metadata:
  origin: community
  source: https://github.com/coreyhaines31/marketingskills
  license: MIT
---

# Video Produce

> **Agent:** Simão (Video Producer, orchestrating the production sub-squad)
> **Full pipeline:** the `content-video` enterprise workflow; invoked standalone, this skill runs the same phases with the same gates.

**Context:** read the product marketing context first —
`WizardingCode/Marketing/product-marketing.md` in Obsidian (KB-first),
else the project-local `.agents/product-marketing.md`.

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
2. **Research** contract: sourced
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

## Tool Landscape (reference)

The Phase 0 matrix picks a tier per capability; this section is the menu of
concrete tools behind those tiers — model choices for asset generation,
avatar options, editing/repurposing tools, and prompting guidance. Use it
when selecting a generation model, when a backend degrades to the manual
tier, or when the request names a specific tool.

### Extra brief inputs

Beyond the Brief phase (target, format, platform, length), capture:

- **Presenter** — AI avatar vs. voiceover vs. screen recording vs. filmed founder.
- **Existing assets** — screenshots, logos, product UI, footage, scripts.
- **One-off vs. template** — a single video, or a reusable template for recurring content.
- **Technical context** — tech stack, available API keys, per-minute tool budgets.

### Choosing your approach

| Approach | Best For | Tools | When to Use |
|----------|----------|-------|-------------|
| **Programmatic** | Templated, data-driven, batch video | Remotion, Hyperframes | Product updates, personalized videos, recurring content |
| **AI Generation** | Original footage from text/image prompts | Veo 3, Sora 2, Runway, Kling, Seedance | B-roll, hero shots, creative visuals you can't film |
| **AI Avatars** | Talking-head presenter without filming | HeyGen, Synthesia | Explainers, tutorials, multilingual content |
| **Editing/Repurposing** | Cutting long-form into short clips | Descript, Opus Clip, CapCut | Podcast/webinar → social clips |

### Programmatic video

Build videos with code. Best for repeatable, templated, or data-driven video
at scale. (The Full tier's Hyperframes route is the ArkaOS default here.)

**Hyperframes (HTML/CSS — recommended for agents):** open-source, Apache
2.0, from HeyGen. Plain HTML/CSS/JS, no framework DSL to learn. LLM-native:
AI models generate better HTML than React components. Each frame is an HTML
document; compose frames into a timeline, render to MP4. Best for product
announcements, changelogs, data-driven reports, personalized outreach.
Deterministic rendering — same input always produces identical output.

**Remotion (React):** mature open-source framework, more powerful than
Hyperframes but requires React knowledge. React components are frames, props
drive content, render locally or via Remotion Lambda (AWS) for scale. Best
for complex animations, interactive previews, large-scale batch rendering.

| Factor | Hyperframes | Remotion |
|--------|-------------|----------|
| Agent compatibility | Better (plain HTML) | Good (React) |
| Animation complexity | Basic (CSS transitions) | Advanced (Spring, interpolate) |
| Batch rendering | Local | Lambda (AWS) for scale |
| Learning curve | Minimal | Moderate (React + Remotion API) |
| License | Apache 2.0 | Company license for commercial use |

### AI video generation

Generate original footage from text or image prompts. Use for B-roll, hero
visuals, and scenes you can't practically film. (Maps to the asset-generation
capability: Higgsfield MCP on the Full tier, these models when selecting or
briefing per shot.)

| Model | Resolution | Max Duration | Best For | Cost |
|-------|-----------|-------------|----------|------|
| **Veo 3** (Google) | Up to 1080p (4K varies) | Variable | Top overall quality, synced audio | API-based |
| **Sora 2** (OpenAI) | Up to 1080p | Up to ~20 sec | Cinematic + synced audio, ChatGPT/API integration | API + ChatGPT |
| **Runway Gen-4** | Up to 4K | ~10 sec/gen | Motion control, temporal consistency, edit-style workflows | $12-76/mo |
| **Kling 2.5/3.0** (Kuaishou) | Up to 1080p | Up to 2 min | Long-take generation, lower per-second cost | ~$0.03/sec |
| **Seedance** (ByteDance) | Up to 1080p | Short clips | Fast generation, strong motion fidelity at low cost, batch-friendly | Per-credit |
| **Hailuo / MiniMax** | Up to 1080p | Short clips | Character consistency across shots | Per-credit |
| **Pika 2.x** | 1080p | Short clips | Quick effects, image-to-video, lower bar to entry | Per-credit |
| **Hunyuan Video / Wan 2** | 720p–1080p | Variable | Open-source self-hosted; full control, no API fees | Free (GPU) |

**Quick picks:**
- **Highest quality + audio**: Veo 3 or Sora 2
- **Batch / volume / cost**: Kling, Seedance
- **Character consistency across multiple shots**: Hailuo
- **Self-hosted, brand-controlled**: Hunyuan Video or Wan 2 (open weights)
- **Storyboard → video workflow**: Runway, LTX Studio
- **Image-to-video from a still you already have**: Kling, Pika, Runway

**Prompting for video models** — specify **subject + action + camera + style + mood**:

```
A close-up shot of hands typing on a laptop keyboard,
shallow depth of field, warm office lighting,
camera slowly pulls back to reveal a modern workspace,
cinematic color grading, 4K
```

Common mistakes: too vague ("a person working"), ignoring camera movement
(specify dolly, pan, static), forgetting style ("cinematic," "documentary,"
"commercial"), requesting readable text in video (AI models struggle with it).
Full guide: [references/ai-video-prompting.md](references/ai-video-prompting.md).

**AI generation vs. stock:**

| Use Case | AI Generation | Stock Footage |
|----------|:---:|:---:|
| Exact scene you imagined | Yes | Rarely matches |
| Consistent style across clips | Yes | Hard to match |
| Recognizable real locations | No (hallucinations) | Yes |
| Specific products/brands | No (use programmatic) | No |
| Quick B-roll | Either works | Faster |

### AI avatars

Create talking-head videos without filming. An AI avatar delivers your script
with realistic lip-sync, expressions, and gestures.

**HeyGen (recommended — has MCP server):** best lip-sync and micro-expressions,
230+ avatars, 140+ languages. Official MCP server lets agents generate avatar
videos directly. Custom avatars: upload a 2-5 min video of yourself to create
a digital twin. Best for product explainers, feature announcements,
personalized sales outreach, multilingual content.

**Synthesia:** full-body avatars with expressive body language, built-in
script generation from URLs/docs. Best for corporate training, compliance
videos, enterprise presentations where professional tone matters more than
photorealism.

| Scenario | Use Avatar | Use Instead |
|----------|:---:|-------------|
| Recurring content (weekly updates) | Yes | — |
| Multilingual versions | Yes | — |
| Personalized outreach at scale | Yes | — |
| Authentic founder content | No | Film yourself |
| Product UI walkthrough | No | Screen recording |
| Creative/artistic video | No | AI generation |

### Editing and repurposing

Turn existing content into multiple video formats.

| Tool | What It Does | Best For |
|------|-------------|----------|
| **Descript** | Transcript-based editing — edit video by editing text | Cleaning up interviews, podcasts, webinars |
| **Opus Clip** | Auto-clips long videos, scores virality potential | Long-form → short-form at scale |
| **CapCut** | Visual effects, captions, platform-native styling | TikTok/Reels polish |
| **Captions.ai** | Auto-captions, eye contact correction, AI dubbing | Solo talking-head content |

**Repurposing workflow:**

```
Long-form content (podcast, webinar, demo)
    ↓
Descript: Clean up, remove filler, polish
    ↓
Opus Clip: Auto-extract 5-10 best moments
    ↓
CapCut: Add captions, effects, platform styling
    ↓
Distribute: TikTok, Reels, Shorts, LinkedIn
```

**Reverse-engineer a viral edit:** to replicate the *style* of an edit you
admire — cut rhythm, caption treatment, punch-ins, on-screen text, sound
design — decompose it into a reusable edit spec (a beat sheet) and apply it
to your own footage. Pull the reference (visual/multimodal mode extracts
frames at the cut points), extract the edit anatomy beat by beat, and output
a per-beat table plus the 3-5 signature moves that make the edit
recognizable. This copies the editing grammar, never the reference's
footage/script/music. Full method:
[references/edit-anatomy.md](references/edit-anatomy.md).

### Agent-native pipeline

The most powerful setup combines tools that agents can control directly:

```
Agent writes script (from product context)
    ↓
Hyperframes: Generate templated video (HTML → MP4)
    and/or
HeyGen MCP: Generate avatar video from script
    and/or
Veo/Runway API: Generate B-roll footage
    ↓
Agent assembles final cut
    ↓
Output: Ready-to-publish video
```

Hyperframes uses HTML (any coding agent can generate it), HeyGen exposes an
MCP server (agents call it directly), and video-model APIs are standard HTTP
requests — so no manual editing step is required.

### Common mistakes

1. **Starting with tools, not strategy** — decide what video you need before picking tools.
2. **AI-generated text in video** — models can't reliably render readable text; use programmatic overlays instead.
3. **Uncanny valley avatars** — if avatar quality matters, invest in the higher HeyGen tiers.
4. **No captions** — 85% of social video is watched without sound.
5. **Wrong aspect ratio** — 9:16 for social, 16:9 for YouTube/website, 1:1 for feeds.
6. **Over-producing** — authentic often outperforms polished, especially on TikTok.

### Tool integrations

| Tool | Type | MCP | Guide |
|------|------|:---:|-------|
| **HeyGen** | AI avatars | Yes | [heygen.md](../../../marketing/tools/integrations/heygen.md) |
| **Hyperframes** | Programmatic video | - | [hyperframes.md](../../../marketing/tools/integrations/hyperframes.md) |
| **Remotion** | Programmatic video | - | [remotion.dev](https://www.remotion.dev/docs) |
| **Runway** | AI generation | - | [runwayml.com/docs](https://docs.dev.runwayml.com) |

## Related ArkaOS skills

- **`content/script-structure`** — script only (no production)
- **`content/short-form`** — short-form scripting and batches
- **`content/youtube-strategy`** — YouTube channel strategy
- **`content/video-setup`** — one-off environment setup
- **`mkt/social-strategy`** — video content strategy and what to post
- **`mkt/paid-campaign`** — paid video ad creative and iteration
- **`landing/copy-framework`** — video scripts and messaging
- **`landing/persuasion-apply`** — hooks and persuasion in video
