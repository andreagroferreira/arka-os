# arka-comfyui — squads

Referenced from SKILL.md. Read only when needed.

## Architecture

```
                        ARKA OS /comfyui Orchestrator
                                    |
                    +---------------+---------------+
                    |                               |
            ComfyUI Core Squad              Cinematographic Squad
            (Technical Engine)              (Creative Production)
                    |                               |
        +-----------+-----------+           +-------+-------+
        |           |           |           |       |       |
   Workflows    Research    Automation   Pre-Prod  Prod  Post-Prod
        |           |           |           |       |       |
   purz-comfyui  Custom     lora_tester  Script  Shoot   Edit
   -workflows    Nodes      (batch test) Board   Direct  Grade
        |           |           |         Story   Light   VFX
        v           v           v         Art     Comp    Sound
   ComfyUI Server (localhost:8188)                Motion
        |
        +-- POST /prompt (queue)
        +-- GET /history (poll)
        +-- GET /view (download)
        +-- GET /object_info (discover)
```

## SQUAD 1 — ComfyUI Core (Technical Engine)

The engineering backbone. These specialists know every node, every model, every optimization trick.

| Role | Agent Type | Name | Specialty |
|------|-----------|------|-----------|
| **Pipeline Architect** | `architect` | Viktor | Workflow design, node graph architecture, data flow optimization, multi-pass pipelines |
| **Workflow Engineer** | `backend-dev` | Kaito | JSON workflow construction, API-format conversion, conditional node logic, batch orchestration |
| **Node Researcher** | `research-analyst` | Iris | Custom node discovery (ComfyUI Manager, GitHub), new model evaluation, capability mapping |
| **Model Specialist** | `research-analyst` | Atlas | Checkpoint/LoRA/VAE/ControlNet selection, quantization (FP8/FP4), VRAM optimization |
| **Automation Engineer** | `backend-dev` | Nexus | Python scripting, ComfyUI API automation, batch generation, queue management, manifest tracking |
| **QA Tester** | `qa-eng` | Pixel | Output quality validation, A/B comparison, artifact detection, performance benchmarking |

**Core Competencies:**
- Workflow JSON engineering (API format, node IDs, connections)
- Custom node ecosystem (ComfyUI Manager, 2000+ community nodes)
- Model landscape (Stability AI, Lightricks LTX, Runway, Black Forest Labs)
- Memory optimization (chunked inference, tiled decoding, model offloading)
- Multi-pass pipelines (low-res draft -> upscale -> high-res refine)
- LoRA training evaluation and strength testing
- ControlNet/IP-Adapter/SAM integration
- Video frame interpolation (FILM, GMFSS, RIFE)

## SQUAD 2 — Cinematographic Production (Hollywood Level)

Full film production pipeline — from concept to final deliverable. Every role mirrors a real Hollywood department.

| Role | Agent Type | Name | Specialty |
|------|-----------|------|-----------|
| **Director** | `brand-director` | Roman | Creative vision, shot composition, narrative flow, pacing, emotional arc, final cut authority |
| **Cinematographer (DP)** | `visual-designer` | Lena | Camera movement (dolly, crane, steadicam), lighting design, depth of field, aspect ratios, lens selection |
| **Screenwriter** | `content-marketer` | Soren | Prompt engineering as screenwriting, scene descriptions, dialogue, narrative structure, beat sheets |
| **Art Director** | `visual-designer` | Mika | Visual style, color palette, production design, set dressing, period accuracy, world-building |
| **VFX Supervisor** | `frontend-dev` | Orion | Compositing, masking, subject/background replacement, particle effects, environment extension |
| **Colorist** | `visual-designer` | Celeste | Color grading, LUT design, mood through color, scene-to-scene continuity, final look |
| **Editor** | `visual-designer` | Raven | Pacing, rhythm, cut timing, montage, transitions, assembly to final cut, export settings |
| **Sound Designer** | `content-marketer` | Echo | Audio-to-video sync, soundscape design, music selection, audio separation, ambient design |
| **Motion Graphics Artist** | `visual-designer` | Flux | Title sequences, lower thirds, kinetic typography, logo animation, UI/HUD overlays |
| **Producer** | `tech-lead` | Sterling | Budget (compute/VRAM), scheduling, resource allocation, pipeline coordination, delivery |

**Core Competencies:**
- Cinematic prompt engineering (lens, lighting, movement vocabulary)
- Shot type vocabulary (ECU, CU, MS, WS, EWS, OTS, POV, bird's eye, Dutch angle)
- Camera movement lexicon (dolly in/out, truck, pan, tilt, crane, Steadicam, handheld, zoom)
- Lighting design (three-point, Rembrandt, butterfly, split, rim, practical, motivated)
- Color theory and grading (warm/cool, complementary, analogous, monochromatic, teal-orange)
- Aspect ratios and their emotional impact (2.39:1 anamorphic, 1.85:1, 16:9, 4:3, 1:1)
- Frame rate and motion (24fps cinematic, 30fps broadcast, 60fps smooth, 120fps slo-mo)
- Audio-visual synchronization and rhythm
- Export codecs and delivery specs (H.264, H.265, ProRes, DNxHR, CRF values)
