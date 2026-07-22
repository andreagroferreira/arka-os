---
name: dev/watch
description: >
  Watch a video (URL or local file) so the agent can answer questions about
  what is on screen and what is said. Downloads with yt-dlp, extracts
  auto-scaled frames with ffmpeg (scene-aware or fast keyframes, near-duplicate
  dedup), pulls a timestamped transcript (native captions first, Whisper API
  fallback), and prints frame paths for the agent to Read. TRIGGER: a video
  URL (YouTube, Loom, TikTok, X, Vimeo…) or local video file plus a question;
  "vê este vídeo", "analisa este vídeo", "watch this video", "o que acontece
  em/aos X min", reference-video analysis before design work, video deliverable
  review in the Quality Gate, screen-recording bug reports, "/dev watch".
  SKIP: video PRODUCTION or generation -> content/video-produce or Higgsfield;
  turning a video into a scroll site -> dev/animated-website (it calls this
  skill for its analysis phase); audio-only transcription of a podcast with no
  visual questions -> run --detail transcript and summarize.
allowed-tools: [Read, Bash, AskUserQuestion]
metadata:
  origin: community
  source: https://github.com/bradautomates/claude-video
  license: MIT
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` (and
> `mcp__graphify__query_graph` when configured) and cite `[[wikilinks]]`
> or graph nodes — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# /watch — video input for ArkaOS agents

You don't have a video input; this skill gives you one. A bundled Python
pipeline gets captions first, downloads only what it needs, extracts frames
as JPEGs, produces a timestamped transcript, and prints frame paths. You then
`Read` each frame to see the video and answer grounded in evidence — the way
the "frames COMPLETOS" doctrine requires for reference-video analysis.

Absorbed from `bradautomates/claude-video` v0.2.0 (MIT) and maintained
natively by ArkaOS. ArkaOS-specific behavior: config lives in
`~/.arkaos/watch.env`, API keys resolve from `/arka keys`
(`~/.arkaos/keys.json`) before any .env file, and every run appends a usage
record to `~/.arkaos/telemetry/watch-usage.jsonl` (frames + estimated image
tokens) so CostGovernor sees video analysis cost.

## Resolve `SKILL_DIR` (before any command)

Set `SKILL_DIR` to the absolute path of the directory containing THIS
SKILL.md (your harness showed it when you Read this file). The scripts are at
`SKILL_DIR/scripts/`. Guard once:

```bash
[ -f "$SKILL_DIR/scripts/watch.py" ] || { echo "watch.py not under $SKILL_DIR" >&2; exit 1; }
```

Run scripts with the canonical ArkaOS interpreter when present, else python3:

```bash
PY="$HOME/.arkaos/bin/arka-py"; command -v "$PY" >/dev/null || PY=python3
```

## Step 0 — preflight (silent on success)

```bash
"$PY" "${SKILL_DIR}/scripts/setup.py" --check
```

Exit 0 → proceed without comment (keyless-after-setup counts as ready — do
NOT announce that setup is complete). Non-zero:

| Exit | Meaning | Action |
|------|---------|--------|
| 2 | ffmpeg / ffprobe / yt-dlp missing or broken (a binary that dies at load counts as missing) | run `"$PY" "${SKILL_DIR}/scripts/setup.py"` — auto-installs via brew on macOS, prints commands elsewhere |
| 3 | genuine first run, no Whisper key | encourage a key (see Keys); user may decline → proceed with `--no-whisper` |
| 4 | both | installer, then key |

`--json` gives the structured status (`status`, `can_proceed`, `first_run`,
`missing_binaries`, `whisper_backend`, `watch_detail`, `config_file`).
First-run flow: install binaries first, let the installer scaffold
`~/.arkaos/watch.env`, then ask the detail preference below.

**Keys (Whisper fallback):** preferred home is `/arka keys` —
`OPENAI_API_KEY` (whisper-1) or `GROQ_API_KEY` (whisper-large-v3, cheaper —
preferred when both exist). Resolution order: environment →
`~/.arkaos/keys.json` → `~/.arkaos/watch.env` → `./.env`. A missing key is
encouraged, never a blocker: captions cover most public videos free.

**First-run detail preference:** ask once via `AskUserQuestion` (order
lightest→heaviest, keep "(recommended)" on balanced): `transcript` (no
frames) · `efficient` (keyframes, cap 50) · `balanced` (recommended —
scene-aware, cap 100) · `token-burner` (uncapped). Write the bare
`WATCH_DETAIL=<value>` line (no inline comment) into `~/.arkaos/watch.env`,
then `SETUP_COMPLETE=true`.

## Invoke

```bash
"$PY" "${SKILL_DIR}/scripts/watch.py" "<url-or-path>"
```

Flags: `--detail transcript|efficient|balanced|token-burner` ·
`--start T` / `--end T` (SS, MM:SS, HH:MM:SS — focused mode, denser fps) ·
`--timestamps T1,T2,…` (pin frames at transcript-flagged moments) ·
`--max-frames N` · `--resolution W` (default 512; 1024 only to read on-screen
text — ~4× image tokens) · `--fps F` (≤2) · `--out-dir DIR` ·
`--whisper groq|openai` · `--no-whisper` · `--no-dedup`.

Then: **Read every frame path the report lists, in one parallel batch.**
Frames carry `t=MM:SS` absolute timestamps aligned with the transcript.
Answer citing timestamps; with no question, summarize structure, key moments,
and spoken content. At `transcript` detail, still synthesize a summary — never
paste the raw transcript.

Cleanup: the report prints the work dir — `rm -rf` it unless follow-ups are
likely. Follow-ups reuse what is already in context; do NOT re-run.

## Frame budget discipline

Cost is dominated by frames (~197 image tokens each at 512px). Full-video
budgets by duration: ≤30s ~30 · ≤1min ~40 · ≤3min ~60 · ≤10min ~80 · >10min
sparse (warning printed). When the user names a moment or the video exceeds
~10 minutes, prefer focused mode (`--start`/`--end` — up to 2 fps) over a
sparse full scan. Dedup collapses held slides and static recordings before
the cap so the budget buys distinct content.

**Transcript-cue frames:** scene selection misses deictic moments ("look
here", "as you can see") because pointing is low visual change. Read the
transcript, judge which cues matter (ignore rhetorical "look…"), re-run with
`--timestamps 4:32,7:10` pointed at the downloaded file in the work dir.

## Failure modes

- Download fails (login/region-locked) → tell the user plainly; don't retry.
- No captions AND no key → frames-only, say so, offer `/arka keys`.
- Whisper chunk failures → transcript is partial; noted on stderr; retry with
  the other backend if needed.
- Long-video warning → acknowledge it and offer a focused re-run.
- Client-confidential recordings → run `--no-whisper` (audio must not leave
  the machine; only extracted audio ever goes to a Whisper API, and only
  when captions are missing).

## Security

Local-only except: extracted mono audio → `api.groq.com` /
`api.openai.com`, only on Whisper fallback. yt-dlp requests public data; no
accounts, no cookies. Keys are never logged or echoed. Working files stay in
the work dir; config/keys in `~/.arkaos/` (0600).

Scripts: `watch.py` (entry) · `download.py` (yt-dlp) · `frames.py` (ffmpeg +
dedup) · `transcribe.py` (captions) · `whisper.py` (Groq/OpenAI clients) ·
`setup.py` (preflight/installer) · `config.py` (paths, keys, telemetry).
