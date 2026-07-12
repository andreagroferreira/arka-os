---
name: video-setup
description: >
  One-time environment bootstrap for video production — preflights and
  (with per-step user confirmation) installs the Hyperframes skills,
  Agent-Reach CLI, and Higgsfield key wiring, ending with an honest
  capability matrix. TRIGGER: "/content video-setup", "setup video",
  "prepara o ambiente de vídeo", "instala o hyperframes", "configura a
  produção de vídeo", "video production setup". SKIP: actually producing
  a video -> content/video-produce (it preflights non-interactively and
  degrades); general MCP setup -> /arka keys or apply-mcps.
---

# Video Setup

> **Agent:** Simão (Video Producer) | **Purpose:** environment bootstrap, run once per machine

## Preflight (run first, print PASS/FAIL per row)

| Check | Command | Needed for |
|---|---|---|
| Node.js 22+ | `node --version` | Hyperframes rendering |
| FFmpeg | `ffmpeg -version` | encode/cut + transcription |
| Hyperframes skills | `ls ~/.claude/skills/ \| grep -i hyperframes` | video-as-code editing |
| Agent-Reach | `agent-reach doctor` | trend/research platform pulls |
| Higgsfield key | `HIGGSFIELD_API_KEY` in env or `~/.arkaos/keys.json` | generation engine (MCP) |

`npx arkaos doctor` runs the same five checks (warn-only) from the
installer side — this skill is the interactive fix path.

## Install steps — EACH gated on explicit user confirmation, never silent

1. **Hyperframes skills** (free, Apache-2.0, HeyGen):
   ```
   npx skills add heygen-com/hyperframes --full-depth --yes
   ```
   `--full-depth` is MANDATORY — without it the skills registry serves a
   stale snapshot that lags the upstream main branch. Installs ~20
   skills including the `/hyperframes` router, `/talking-head-recut`,
   `/faceless-explainer`, `/product-launch-video`, `/motion-graphics`,
   `/embedded-captions`, `/media-use`. Keep fresh later with
   `npx hyperframes skills update <workflow>`.
2. **Agent-Reach CLI** (MIT, beta — THIRD-PARTY GitHub code, NOT on
   PyPI): the package `agent-reach` does NOT exist in any registry —
   `pipx install agent-reach` / `uv tool install agent-reach` fail with
   "not found in registry" (verified 2026-07-11). The only source is
   the external third-party repo `github.com/Panniantong/Agent-Reach`
   (author: Panniantong, MIT license). Installing it runs code straight
   from that repo, so this step is DOUBLE-gated: show the user the
   source URL and license, and only after their explicit confirmation
   run, into an isolated tool env — NEVER a bare global pip
   (python-core rule: virtual environments only):
   ```
   uv tool install "git+https://github.com/Panniantong/Agent-Reach"
   ```
   (or `pipx install "git+https://github.com/Panniantong/Agent-Reach"`).
   Then run `agent-reach doctor` and show the user which of the
   15 platform backends are live; cookie/browser-session platforms
   (X, Reddit, IG, FB) need the user's own logged sessions and stay
   optional.
3. **Higgsfield key**: `npx arkaos keys set HIGGSFIELD_API_KEY <key>`
   (account at higgsfield.ai), then activate per project:
   `bash apply-mcps.sh --add higgsfield` or select the `content` MCP
   profile.

## Never install binaries

Node.js and FFmpeg are system packages — print the platform-specific
instruction and stop:

- macOS: `brew install ffmpeg` · `nvm install 22`
- Linux: `apt install ffmpeg` (or distro equivalent)
- Windows: `winget install Gyan.FFmpeg`

ArkaOS detects and instructs; it never mutates the user's system
package state.

## Capability matrix (always print at the end — honest, per backend)

| Capability | Full | Degraded | Manual |
|---|---|---|---|
| Asset generation | Higgsfield MCP | `arka-comfyui` (local) | asset brief with engine-ready prompts |
| Edit / render | Hyperframes (Node 22 + FFmpeg) | Higgsfield `explainer_video` / `shorts_studio` (server-side) | edit-ready package (script + assets + EDL + SRT) |
| Research | agent-reach | firecrawl + WebSearch | KB-only |

State plainly which tier each capability landed on and what it takes to
reach the tier above. A missing backend NEVER blocks the pipeline — it selects
the next tier and says so (multi-backend rule: no capability is ever
hardcoded to a single external backend).

## Output

Setup report: preflight table, what was installed (with user consent
noted per step), the capability matrix, and the exact next command to
try (`/content video <topic>`).
