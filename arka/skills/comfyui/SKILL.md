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

## Squads (summary)

| Squad | Purpose | Members |
|-------|---------|---------|
| **ComfyUI Core** | Technical engine: workflow JSON, custom nodes, models, VRAM, API automation | Viktor (Pipeline Architect), Kaito (Workflow Engineer), Iris (Node Researcher), Atlas (Model Specialist), Nexus (Automation Engineer), Pixel (QA Tester) |
| **Cinematographic Production** | Hollywood pipeline: direction, DP, art, VFX, color, edit, sound, motion, production | Roman (Director), Lena (DP), Soren (Screenwriter), Mika (Art Director), Orion (VFX), Celeste (Colorist), Raven (Editor), Echo (Sound Designer), Flux (Motion Graphics), Sterling (Producer) |

Full role definitions, agent types, and competencies: `references/squads.md`.

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

Every `/comfyui` request follows a 6-phase flow: (1) context loading, (2) analysis & planning with squad routing, (3) plan presentation & approval gate, (4) execution with worktree isolation, (5) mandatory Quality Gate (Marta/Eduardo/Francisca), (6) documentation & report.

Squad routing: technical → Core; creative production → Cinematographic; full production → both, coordinated by Producer Sterling; research → Iris or Atlas.

**See `references/workflows.md`** for full phase templates (plan, report), workflows catalogue (LTX-2 T2V/I2V/Audio, SVD, AnimateDiff), model registry, cinematic prompt engineering guide, ComfyUI API reference, status command, `/comfyui produce` pipeline, custom node research protocol, and Obsidian output structure.

## References

- `references/squads.md` — Full Core and Cinematographic squad role tables, agent types, core competencies
- `references/workflows.md` — Phase templates, workflow catalogue, model registry, API reference, prompt engineering guide, Obsidian output
