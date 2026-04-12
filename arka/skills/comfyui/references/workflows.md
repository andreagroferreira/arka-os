# arka-comfyui — workflows

Referenced from SKILL.md. Read only when needed.

## Orchestration Workflow

For EVERY `/comfyui` request, follow this workflow:

### Phase 1 — Context Loading
1. Read ComfyUI skill reference: `/Users/andreagroferreira/AIProjects/lora_tester/.claude/skills/comfy_local/skill.md`
2. Check available workflows: `ls /Users/andreagroferreira/AIProjects/purz-comfyui-workflows/`
3. Check ComfyUI server: `curl -s http://localhost:8188/system_stats 2>/dev/null`
4. Load project context for affected repos
5. Identify which squad(s) the request needs

### Phase 2 — Analysis & Planning

**Before planning, verify context:**
- Restate the request to confirm understanding
- Ask at least 1 clarifying question about scope or intent
- Challenge at least 1 assumption (devil's advocate)
- Check memory/knowledge base for prior related work

**Squad routing logic:**
- Technical workflow requests -> ComfyUI Core Squad
- Creative production requests -> Cinematographic Squad (with Core support)
- Full production pipeline -> Both squads coordinated by Producer (Sterling)
- Research requests -> Node Researcher (Iris) or Model Specialist (Atlas)

1. Analyze the request and route to correct squad(s)
2. Determine which roles are needed
3. Create execution plan with:
   - **Squad(s) involved** (Core, Cinematographic, or both)
   - **Roles assigned** (which agents)
   - **Pipeline stages** (pre-prod, production, post-prod)
   - **Technical requirements** (models, nodes, VRAM, resolution)
   - **Deliverables** (files, formats, specs)

### Phase 3 — Plan Presentation & Approval

```
--- COMFYUI — Production Plan ---

REQUEST: [summary]

SQUAD ASSIGNMENT:
  Core: [roles involved]
  Cinematographic: [roles involved]

PIPELINE:
  1. [stage] — [role] — [deliverable]
  2. [stage] — [role] — [deliverable]
  ...

TECHNICAL REQUIREMENTS:
  - Models: [list]
  - Nodes: [custom nodes needed]
  - Resolution: [WxH]
  - Frames: [count]
  - VRAM estimate: [GB]

DELIVERABLES:
  - [format, resolution, codec, duration]

CONSIDERATIONS:
  - [risk/note]

---------------------------------
```

Ask for user approval: "Approve plan and proceed?"

### Phase 4 — Execution
1. Only proceed after approval
2. Use worktree isolation for code changes (NON-NEGOTIABLE)
3. Squad roles execute in their domain
4. Producer (Sterling) coordinates cross-squad handoffs

### Phase 5: Quality Gate (NON-NEGOTIABLE)

Before any output reaches the user:
- **Marta** (CQO) orchestrates the review
- **Eduardo** (Copy Director) reviews all text output
- **Francisca** (Tech/UX Director) reviews all code and technical output

**Verdict:** APPROVED or REJECTED. No exceptions.

### Phase 6 — Documentation & Report

```
--- COMFYUI — Production Report ---

COMPLETED:
  - [deliverables produced]

TECHNICAL:
  - Workflow: [name]
  - Models used: [list]
  - Resolution: [WxH] | Frames: [N] | FPS: [N]
  - Generation time: [estimate]

FILES:
  - [outputs and locations]

-----------------------------------
```

## Available Workflows Reference

### LTX-2 Text-to-Video (ltx2-t2v-lora)
| Property | Value |
|----------|-------|
| Resolution | 1280x720 |
| Frames | 48 (configurable, must be divisible by 8+1) |
| Model | ltx-2-19b-dev-fp8 |
| Text Encoder | Gemma 3 12B (FP4/FP8/Full) |
| LoRA Support | Yes (camera control, style) |
| Key Nodes | LTX2_NAG, LTXVConditioning, KSampler |
| Output | H.264 MP4, CRF 13, 24fps |

### LTX-2 Image-to-Video (ltx2-i2v-lora)
| Property | Value |
|----------|-------|
| Resolution | Input image resolution |
| Frames | 48 |
| Model | ltx-2-19b-dev-fp8 |
| Key Feature | First-frame conditioning |
| Key Nodes | LTXVImgToVideoInplaceKJ, LTX2_NAG |
| Output | H.264 MP4 |

### LTX-2 Audio-to-Video (ltx2-audio_to_video_extension_5x)
| Property | Value |
|----------|-------|
| Feature | Separate audio + video VAE encoding |
| Upscaling | 5x spatial upscaler |
| Chunked Inference | 4 chunks, 4096 tokens |
| Audio Processing | FL_Audio_Separation, audio crop, vocoder |
| Key Nodes | LTXVAudioVAEEncode/Decode, LTXVSeparateAVLatent |
| Output | H.264 MP4 with audio |

### SVD Simple (svd-simple)
| Property | Value |
|----------|-------|
| Resolution | 576x1024 |
| Frames | 14 + 2x interpolation = 27 |
| Model | svd.safetensors |
| Key Feature | Simple image-to-video |
| Interpolation | FILM VFI |
| Output | H.264 MP4 |

### SVD CLIP Extension 8x (svd-clip-extension-8x)
| Property | Value |
|----------|-------|
| Resolution | 576x1024 |
| Frames | 14 base + 8x interpolation |
| Model | svd.safetensors + CLIP Vision |
| Interpolation | GMFSS Fortuna (8x) |
| Output | H.264 MP4, high frame count |

### AnimateDiff Subject Replacement
| Property | Value |
|----------|-------|
| Model | deliberate_v3 (SD 1.5) |
| Segmentation | SAM + YOLOv8 person detection |
| Control | ControlNet inpaint + openpose |
| IP-Adapter | ip-adapter-plus_sd15 |
| Use Case | Replace subject in video while preserving motion |

### AnimateDiff Background Replacement
| Property | Value |
|----------|-------|
| Model | deliberate_v3 (SD 1.5) |
| Segmentation | SAM + YOLOv8 |
| Control | ControlNet inpaint |
| Use Case | Replace background while preserving subject |

## Model Registry

### Checkpoints
| Model | Type | Size | Use Case |
|-------|------|------|----------|
| ltx-2-19b-dev-fp8 | LTX-2 | ~10GB | Primary T2V/I2V |
| ltx-2-19b-distilled-fp8 | LTX-2 Distilled | ~10GB | Faster generation |
| deliberate_v3 | SD 1.5 | ~2GB | AnimateDiff base |
| svd | SVD | ~4GB | Image-to-video |

### Text Encoders
| Model | Precision | VRAM |
|-------|-----------|------|
| gemma_3_12B_it | Full | ~24GB |
| gemma_3_12B_it_fp8_scaled | FP8 | ~12GB |
| gemma_3_12B_it_fp4_mixed | FP4 | ~6GB |

### LoRAs
| LoRA | Purpose |
|------|---------|
| ltx-2-19b-distilled-lora-384 | Quality boost for distilled model |
| ltx-2-19b-lora-camera-control-dolly-left | Camera dolly movement |
| DoubleDolly_lora_weights | Double dolly camera effect |
| ltx2-cakeify-v2 | Style transfer (cakeify) |
| lcm-sd15-lora | LCM acceleration for SD 1.5 |
| temporaldiff-v1-animatediff | Temporal consistency |

### Interpolation Models
| Model | Multiplier | Quality |
|-------|-----------|---------|
| FILM VFI (film_net_fp32) | 2x | High |
| GMFSS Fortuna | 2x-8x | Very high |

## Cinematic Prompt Engineering Guide

The Screenwriter (Soren) and Director (Roman) use structured prompt engineering:

### Shot Type Vocabulary
```
ECU  — Extreme Close-Up (eyes, details)
CU   — Close-Up (face fills frame)
MCU  — Medium Close-Up (head + shoulders)
MS   — Medium Shot (waist up)
MWS  — Medium Wide Shot (knees up)
WS   — Wide Shot (full body + environment)
EWS  — Extreme Wide Shot (landscape dominates)
OTS  — Over-the-Shoulder
POV  — Point of View
```

### Camera Movement Vocabulary
```
dolly in/out    — Camera moves toward/away from subject
truck L/R       — Camera moves laterally
pan L/R         — Camera pivots horizontally (stationary)
tilt up/down    — Camera pivots vertically (stationary)
crane up/down   — Camera rises/lowers vertically
Steadicam       — Smooth handheld tracking
handheld        — Organic, documentary feel
zoom in/out     — Lens zoom (not camera movement)
rack focus      — Shift focus between planes
push in         — Slow dolly in for emphasis
```

### Lighting Vocabulary
```
three-point         — Key + fill + back (standard)
Rembrandt           — Triangle shadow on cheek
butterfly/Paramount — Shadow under nose
split               — Half face lit, half shadow
rim/edge            — Backlight outlining subject
practical           — Visible light sources in scene
motivated           — Light justified by scene elements
golden hour         — Warm, low-angle natural light
blue hour           — Cool, pre-dawn/post-sunset
chiaroscuro         — Extreme contrast (Caravaggio)
```

### Prompt Structure for Cinematic Output
```
[Shot type], [camera movement], [subject description],
[lighting], [color palette], [mood/atmosphere],
[lens/focal length], [aspect ratio reference],
[film stock/look reference], [time of day]
```

**Example:**
```
Medium wide shot, slow dolly in, a lone figure walking through
rain-soaked neon streets, Rembrandt lighting with cyan and magenta
neon reflections, melancholic noir atmosphere, 35mm anamorphic lens,
Kodak Vision3 500T film grain, late night
```

## ComfyUI API Reference

### Core Endpoints
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/prompt` | POST | Queue workflow: `{"prompt": {...}, "client_id": "..."}` |
| `/history/{prompt_id}` | GET | Poll job status and results |
| `/queue` | GET | Queue status (pending + running) |
| `/view?filename=X&type=output` | GET | Download generated media |
| `/object_info` | GET | All available nodes and their schemas |
| `/object_info/{NodeType}` | GET | Specific node schema + available models |
| `/system_stats` | GET | GPU memory, VRAM, compute stats |
| `/upload/image` | POST | Upload input image (multipart) |
| `/upload/mask` | POST | Upload mask image (multipart) |

### Workflow JSON Format (API)
```json
{
  "1": {
    "class_type": "NodeType",
    "inputs": {
      "param": "value",
      "connection": ["source_node_id", output_index]
    }
  }
}
```

### Batch Generation Pattern
```python
# 1. Submit all jobs upfront (queue them)
for job in jobs:
    response = post("/prompt", {"prompt": workflow})
    prompt_ids.append(response["prompt_id"])

# 2. Single polling loop
while pending:
    for pid in pending:
        history = get(f"/history/{pid}")
        if pid in history:
            download_outputs(history[pid])
            pending.remove(pid)
    time.sleep(3)
```

## /comfyui status

```bash
# Server status
curl -s http://localhost:8188/system_stats 2>/dev/null

# Project status
cd /Users/andreagroferreira/AIProjects/purz-comfyui-workflows && git log --oneline -5
cd /Users/andreagroferreira/AIProjects/lora_tester && git log --oneline -5
```

Present as:

```
--- COMFYUI ECOSYSTEM — Status ---

SERVER: [online/offline] (localhost:8188)
  GPU: [name] | VRAM: [total/used/free]

PURZ-COMFYUI-WORKFLOWS
  Branch: [branch]
  Last commit: [hash] — [message]
  Workflows: 7 (3 LTX-2, 2 SVD, 2 AnimateDiff)

LORA_TESTER
  Branch: [branch]
  Last commit: [hash] — [message]
  Components: CLI (252 lines) + Gallery (900 lines)

SQUADS READY:
  Core: Viktor, Kaito, Iris, Atlas, Nexus, Pixel (6)
  Cinematographic: Roman, Lena, Soren, Mika, Orion,
                   Celeste, Raven, Echo, Flux, Sterling (10)

----------------------------------
```

## /comfyui produce — Full Production Pipeline

The flagship command. Runs the complete Hollywood pipeline:

```
Phase 1: DEVELOPMENT (Screenwriter Soren + Director Roman)
  - Concept analysis and creative brief
  - Scene breakdown and beat sheet
  - Prompt script (structured cinematic prompts)
  - Shot list with camera/lighting specs

Phase 2: PRE-PRODUCTION (Art Director Mika + Cinematographer Lena)
  - Visual style development (lookdev)
  - Color palette and mood board
  - Storyboard (generated reference images)
  - Technical specs (resolution, fps, codec)

Phase 3: PRODUCTION (Pipeline Architect Viktor + Workflow Engineer Kaito)
  - Workflow selection or creation
  - Model and LoRA selection (Model Specialist Atlas)
  - Generation execution via ComfyUI API
  - Quality monitoring (QA Tester Pixel)

Phase 4: POST-PRODUCTION
  - VFX compositing (VFX Supervisor Orion)
  - Color grading (Colorist Celeste)
  - Sound design (Sound Designer Echo)
  - Motion graphics (Motion Graphics Flux)
  - Final edit and pacing (Editor Raven)

Phase 5: DELIVERY (Producer Sterling)
  - Export in requested format/codec
  - Quality Gate review
  - Documentation and handoff
```

## Custom Node Research Protocol

When Iris (Node Researcher) investigates custom nodes:

1. **ComfyUI Manager Registry** — Primary source for vetted nodes
2. **GitHub search** — `comfyui custom node [capability]`
3. **ComfyUI community** — Reddit r/comfyui, Discord, forums
4. **Evaluation criteria:**
   - Active maintenance (commits in last 3 months)
   - Star count and community adoption
   - Compatibility with current ComfyUI version
   - VRAM requirements
   - License compatibility
   - Node conflicts with existing installation

## Obsidian Output

All documentation: `/Users/andreagroferreira/Documents/Personal/Projects/WizardingCode Internal/ComfyUI/`

```
WizardingCode Internal/ComfyUI/
├── Home.md                    <- Ecosystem overview
├── Workflows/
│   ├── LTX-2 T2V.md
│   ├── LTX-2 I2V.md
│   ├── LTX-2 Audio.md
│   ├── SVD Simple.md
│   ├── SVD CLIP 8x.md
│   ├── AnimateDiff Subject.md
│   ├── AnimateDiff Background.md
│   └── Custom/               <- User-created workflows
├── Models/
│   ├── Checkpoints.md
│   ├── LoRAs.md
│   ├── VAEs.md
│   └── ControlNets.md
├── Production/
│   ├── Cinematic Prompt Guide.md
│   ├── Shot Types.md
│   ├── Camera Movement.md
│   ├── Lighting Design.md
│   └── Color Grading.md
├── Research/
│   ├── Custom Nodes.md
│   └── New Models.md
└── Projects/                  <- Production project logs
```
