# arka-knowledge — async-processing

Referenced from SKILL.md. Read only when needed.

## /kb capabilities

Check what tools and API keys are available for KB processing.

**Steps:**
1. Run `bash <scripts-dir>/kb-check-capabilities.sh`
2. Read `~/.arka-os/capabilities.json`
3. Display results to the user in a formatted table

Shows: binary availability (whisper, yt-dlp, ffmpeg, jq, python3), API keys (OpenAI, Gemini, OpenRouter), and the selected transcription method.

## /kb queue

Show all jobs and their current status.

**Steps:**
1. Run `bash <scripts-dir>/kb-status.sh`
2. Or read `~/.arka-os/kb-jobs.json` directly and format as a table
3. Show: job ID, status, title, transcription method
4. Status colors: queued (yellow), downloading/transcribing (blue), ready (green), completed (green), failed (red)

## /kb status [job-id]

Detailed status of a specific job.

**Steps:**
1. Run `bash <scripts-dir>/kb-status.sh <job-id>`
2. Or read the job from `~/.arka-os/kb-jobs.json` and display all fields
3. If `--json` flag: output raw JSON

## Worker / Queue Mechanics

- **Queue dispatcher:** `kb-queue.sh` writes a new job record to `~/.arka-os/kb-jobs.json` (status=`queued`), then detaches `kb-worker.sh` in background.
- **Worker:** `kb-worker.sh` handles a single job — runs yt-dlp, writes `audio.wav`, transcribes (Whisper local or API), updates status transitions (`downloading` → `transcribing` → `ready` or `failed`).
- **Concurrency:** all writes to `kb-jobs.json` must use `flock` on `~/.arka-os/kb-jobs.lock` to avoid corruption.
- **Logs:** per-job — `download.log`, `transcribe.log`, `worker.log` in the job output directory.
- **LLM boundary:** worker NEVER calls the LLM. The `ready` → `analyzing` → `completed` transitions happen only when `/kb process <job-id>` runs in Claude Code.

## Job Status Flow

```
queued → downloading → transcribing → ready → analyzing → completed
              ↓              ↓
           failed          failed
```

## Media Storage

```
~/.arka-os/
├── media/                          # Permanent, organized media storage
│   ├── 2026-03-15/                 # Date-based grouping
│   │   ├── a1b2c3d4/               # Job ID directory
│   │   │   ├── metadata.json       # yt-dlp output (title, duration)
│   │   │   ├── audio.wav           # Downloaded audio file
│   │   │   ├── audio.txt           # Transcription output
│   │   │   ├── download.log        # yt-dlp log
│   │   │   ├── transcribe.log      # Whisper log
│   │   │   └── worker.log          # Background process log
├── kb-jobs.json                    # Job state file
├── capabilities.json               # System capabilities
└── .env                            # API keys
```

## Job State File Shape (`~/.arka-os/kb-jobs.json`)

```json
{
  "jobs": [
    {
      "id": "a1b2c3d4",
      "url": "<youtube-url>",
      "persona": "<Name or null>",
      "status": "queued|downloading|transcribing|ready|analyzing|completed|failed",
      "method": "whisper-local|whisper-api|gemini|openrouter",
      "output_dir": "~/.arka-os/media/<date>/<id>/",
      "title": "<video title>",
      "duration": "<hh:mm:ss>",
      "created_at": "<ISO8601>",
      "updated_at": "<ISO8601>",
      "error": null
    }
  ]
}
```
