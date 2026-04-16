---
name: arka-comfyui
description: >
  ComfyUI ecosystem orchestrator. Two specialized squads: ComfyUI Core (workflow engineering,
  custom nodes research, model discovery, pipeline optimization, API automation) and
  Hollywood Cinematographic Production (directing, cinematography, color grading, VFX,
  sound design, editing, motion graphics). Manages 2 projects: purz-comfyui-workflows
  (production-ready workflow collection) and lora_tester (LoRA batch testing toolkit).
  Full AI video production pipeline from concept to final cut.
  Use when user says "comfyui", "comfy", "workflow", "video production", "cinematography",
  "generate video", "text to video", "image to video", or wants to work with ComfyUI.
---

# ComfyUI Ecosystem Orchestrator — ARKA OS

Full-spectrum AI media production platform. From ComfyUI node engineering to Hollywood-grade cinematographic output.

## Ecosystem Overview

| Project | Type | Stack | Path |
|---------|------|-------|------|
| **purz-comfyui-workflows** | Workflow Collection | ComfyUI JSON (7 workflows, 110+ nodes) | `/Users/andreagroferreira/AIProjects/purz-comfyui-workflows` |
| **lora_tester** | CLI Tool + Gallery | Python 3.8+ (stdlib) + Vanilla HTML/JS | `/Users/andreagroferreira/AIProjects/lora_tester` |

## Squads

**ComfyUI Core:** Viktor, Kaito, Iris, Atlas, Nexus, Pixel — workflow JSON, custom nodes, models, VRAM, API.
**Cinematographic Production:** Roman, Lena, Soren, Mika, Orion, Celeste, Raven, Echo, Flux, Sterling — direction, DP, VFX, color, edit, sound, motion.

Full role definitions: `references/squads.md`.

## Commands

### General

| Command | Description |
|---------|-------------|
| `/comfyui <description>` | Describe what you need — orchestrator routes to correct squad |
| `/comfyui status` | Status of all ComfyUI projects + server availability |
| `/comfyui context` | Full ecosystem context (workflows, models, capabilities) |

### ComfyUI Core

| Command | Description |
|---------|-------------|
| `/comfyui workflow create\|edit\|list\|test` | Design, modify, list, or test workflows |
| `/comfyui node research <topic>` | Research custom nodes |
| `/comfyui model research\|list` | Research or query models (checkpoints, LoRAs, VAEs, ControlNets) |
| `/comfyui lora test` | Delegate to /lora-tester |
| `/comfyui optimize <workflow>` | VRAM/speed optimization |
| `/comfyui api <task>` | API automation |
| `/comfyui install <nodes>` | Guide custom node installation |

### Cinematographic Production

| Command | Description |
|---------|-------------|
| `/comfyui produce <concept>` | Full pipeline: concept → script → storyboard → generate → edit → deliver |
| `/comfyui direct\|shoot\|grade\|edit\|vfx\|sound\|motion` | Single-stage production commands |
| `/comfyui storyboard\|lookdev` | Pre-production: storyboard, visual style development |

### Pipelines

| Command | Description |
|---------|-------------|
| `/comfyui pipeline t2v\|i2v\|a2v` | Text/Image/Audio-to-Video (LTX-2 / SVD) |
| `/comfyui pipeline upscale\|interpolate\|mask` | Upscale, frame interpolation, subject/bg replacement |

## Orchestration Workflow

6-phase flow: context → analysis+squad routing → plan approval → execution (worktree) → Quality Gate → docs. Squad: technical → Core; creative → Cinematographic; full → both (Sterling coords); research → Iris/Atlas. Details: `references/workflows.md`

<!-- arka:feature:forge-integration:start -->
## Forge Integration

Complex requests (complexity score >= 5) are automatically routed to
The Forge for multi-agent planning before execution.

- Phase 0.5: Forge analysis (after spec creation, before squad planning)
- Complexity assessment: automatic via Synapse L8 (ForgeContextLayer)
- Manual invocation: `/forge` command
- Handoff: Forge outputs structured plan -> squad executes phases
<!-- arka:feature:forge-integration:end -->

<!-- arka:feature:quality-gate:start -->
## Quality Gate

Mandatory on every workflow. Nothing ships without approval.

- **Marta (CQO):** Orchestrates review, absolute veto power
- **Eduardo (Copy Director):** Reviews all text output
- **Francisca (Tech Director):** Reviews all code and technical output
- Verdict: APPROVED or REJECTED (binary, no partial)
<!-- arka:feature:quality-gate:end -->

<!-- arka:feature:spec-driven-gate:start -->
## Spec-Driven Development

Phase 0 of all workflows. No implementation begins without a validated spec.

- Invocation: automatic before any feature/fix work
- Gate: spec must be approved before planning phase starts
- Storage: `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`
- Review: user approval required on written spec
<!-- arka:feature:spec-driven-gate:end -->

<!-- arka:feature:workflow-tiers:start -->
## Workflow Tiers

Three workflow tiers based on task complexity:

| Tier | Phases | When |
|------|--------|------|
| Enterprise | 7-10 phases | Complex features, multi-file changes |
| Focused | 3-5 phases | Medium tasks, single-domain changes |
| Specialist | 1-2 phases | Simple tasks, quick fixes |

Tier selection is automatic based on complexity assessment.
Quality Gate phase is mandatory on ALL tiers.
<!-- arka:feature:workflow-tiers:end -->