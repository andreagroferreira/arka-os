# Getting Started with ARKA OS

This guide walks you through installing ARKA OS and running your first commands. No coding experience required.

---

## What You Need

Before installing ARKA OS, make sure you have:

1. **Claude Code** — ARKA OS runs inside Claude Code, Anthropic's AI coding tool. [Install Claude Code here](https://claude.ai/code).
2. **Git** — Used to download ARKA OS. Most computers have it already. To check, open your terminal and type `git --version`. If you see a version number, you're good.
3. **A terminal** — On Mac, open the **Terminal** app (search for it in Spotlight). On Linux, open your terminal emulator.
4. **Obsidian** (recommended) — ARKA OS saves everything to an [Obsidian](https://obsidian.md) vault. It works without Obsidian, but you'll get the most value with it.

### Optional (for specific features)

These are only needed if you plan to use certain features:

| Tool | What It's For | Needed For |
|------|-------------|------------|
| [Node.js](https://nodejs.org) | JavaScript runtime | Vue, Nuxt, React, Next.js projects |
| [PHP](https://www.php.net) + [Composer](https://getcomposer.org) | PHP runtime | Laravel projects |
| [Python 3](https://www.python.org) | Python runtime | Scripts and AI automation |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | Video downloader | Learning from YouTube videos |
| [Whisper](https://github.com/openai/whisper) | Audio transcription | Learning from YouTube videos |
| [jq](https://jqlang.github.io/jq/) | JSON processor | Integration management |

Don't worry about installing these now — the installer will tell you what's missing when you need it.

---

## Installation

### One Command (Recommended)

Open your terminal and run:

```bash
curl -fsSL https://raw.githubusercontent.com/andreagroferreira/arka-os/master/install.sh | bash
```

This downloads ARKA OS and runs the installer automatically. It will:
- Download the ARKA OS files to `~/.arka-os/repo`
- Set up the `arka` command so you can use it from anywhere
- Install all the department skills and AI team members
- Create per-agent memory files for all 15 agents
- Auto-detect your Obsidian vault and create folders for organizing output
- Configure 3 Claude Code hooks (context injection, error tracking, session preservation)
- Generate an install manifest with SHA256 checksums
- Check which optional tools you have installed
- Ask if you want to set up integrations (you can do this later)

### Alternative: Clone Manually

If you prefer to clone the repository yourself:

```bash
git clone https://github.com/andreagroferreira/arka-os.git
cd arka-os
bash install.sh
```

### After Installation

Restart your terminal or run:

```bash
source ~/.zshrc
```

> **Using bash instead of zsh?** Run `source ~/.bashrc` instead.

### Verify It Works

```bash
arka --version
```

You should see something like: `1.0.0`

---

## First Run

Type `arka` in your terminal to start ARKA OS:

```bash
arka
```

This opens Claude Code with ARKA OS loaded. You'll have access to all departments, team members, and commands.

### Your First Command

Try the help command to see everything available:

```
/arka help
```

This shows you every command across all 7 departments.

### Check System Status

```
/arka status
```

This shows you:
- Your ARKA OS version
- Which departments are active
- How many AI team members are available
- Which integrations are configured
- How many external skills are installed

---

## Try These Next

Here are 5 beginner-friendly commands to get familiar with ARKA OS:

### 1. Run a Daily Standup

```
/arka standup
```

Get a summary of your projects, tasks, upcoming meetings, and anything that needs attention.

### 2. Create a Content Calendar

```
/mkt calendar "next week"
```

Luna (your content creator) will build a content calendar with post ideas for each day.

### 3. Brainstorm a Business Idea

```
/strat brainstorm "online course platform for cooking"
```

Tomas (your strategist) will analyze the idea from 5 different perspectives — visionary, pragmatist, devil's advocate, customer voice, and data analyst.

### 4. Generate Social Media Posts

```
/mkt social instagram "We just launched our new website"
```

Get ready-to-post Instagram content with captions, hashtags, and content suggestions.

### 5. Analyze Finances

```
/fin analysis "Should we hire a freelance designer?"
```

Helena (your CFO) will run the numbers and give you a recommendation based on financial impact.

---

## Setting Up Integrations

Integrations connect ARKA OS to external services like Slack, ClickUp, and Shopify. They're optional — ARKA OS works without them, but they unlock more features.

### Quick Setup

Run the integration setup wizard:

```bash
bash env-setup.sh
```

This will walk you through each integration one by one. For each service, it will:
1. Explain what the integration does
2. Tell you where to get the required key or token
3. Ask you to paste it in

You can skip any integration and come back later.

### Available Integrations

The setup wizard covers these services:

| Service | What You'll Need | What It Unlocks |
|---------|-----------------|----------------|
| ClickUp | API token | Task management with `/ops tasks` |
| Firecrawl | API key | Web research and scraping |
| PostgreSQL | Connection string | Direct database access |
| Discord | Bot token | Discord messaging with `/ops notify` |
| WhatsApp | API token + Phone ID | WhatsApp messaging |
| Teams | App ID + App secret | Microsoft Teams messaging |

> **Slack** uses automatic sign-in (OAuth), so no manual setup is needed.

### Where Are Keys Stored?

Your integration keys are saved in `~/.arka-os/.env` and loaded automatically when you start ARKA OS. They never leave your computer.

[Full integration guide &rarr;](INTEGRATIONS.md)

---

## Updating ARKA OS

ARKA OS checks for updates automatically once a day. When an update is available, you'll see a notification.

### To Update

```bash
arka update
```

This pulls the latest version and reinstalls everything. Your settings and integrations are preserved.

### Check Your Version

```bash
arka --version
```

---

## Uninstalling

If you want to remove ARKA OS:

```bash
cd arka-os
bash install.sh --uninstall
```

This removes:
- The `arka` command
- All installed skills and department files
- ARKA OS configuration
- Hooks from Claude Code settings

It does **not** remove:
- Your Obsidian vault content (that's yours to keep)
- Agent memory files in `~/.claude/agent-memory/` (cross-session learning)
- Gotchas tracking in `~/.arka-os/gotchas.json`
- Integration keys in `~/.arka-os/.env`
- The cloned repository (delete the `arka-os` folder manually)

---

## Common Issues & Fixes

### "command not found: arka"

Your terminal hasn't loaded the new command yet. Run:

```bash
source ~/.zshrc    # or: source ~/.bashrc
```

Or simply close and reopen your terminal.

### "Claude Code is not installed"

ARKA OS requires Claude Code. Install it from [claude.ai/code](https://claude.ai/code), then try again.

### "Permission denied" during install

Run the installer with explicit bash:

```bash
bash install.sh
```

Don't use `./install.sh` — it may not have execute permissions.

### Integrations not working

1. Make sure you ran `bash env-setup.sh` and entered valid keys
2. Restart your terminal so the keys are loaded
3. Check that the key is still valid in the service's dashboard

### YouTube learning not working

The `/kb learn` command for YouTube videos needs extra tools. Install them:

```bash
# Install yt-dlp (video downloader)
pip install yt-dlp

# Install whisper (audio transcription)
pip install openai-whisper

# Install ffmpeg (audio processing) — Mac
brew install ffmpeg
```

### "jq: command not found"

Some integration features need jq. Install it:

```bash
# Mac
brew install jq

# Ubuntu/Debian
sudo apt install jq
```

---

### System health check

Run a health check to make sure everything is properly configured:

```bash
arka doctor
```

This runs 15 checks — verifying CLI, hooks, agents, integrations, and more. Use `arka doctor --fix` to auto-repair common issues.

### Check recurring errors

ARKA OS automatically tracks errors you encounter across sessions:

```bash
arka gotchas
```

This shows the top 10 most frequent error patterns, organized by category (laravel, frontend, git, database, etc.).

### Run tests

Verify the installation is working correctly:

```bash
arka test
```

This runs the bats test suite covering CLI routing, hooks, doctor checks, and status line.

---

## What's Next?

| Want to... | Go to... |
|-----------|---------|
| See every available command | [Commands Reference](COMMANDS.md) |
| Learn about each department | [Departments Guide](DEPARTMENTS.md) |
| Connect external services | [Integrations Guide](INTEGRATIONS.md) |
| Install community skills | [External Skills Guide](EXTERNAL-SKILLS.md) |
| Build a feature (isolated branch) | Run `/dev feature "description"` |
| Create a new project | Run `/dev scaffold` and choose a type |
| Check system health | Run `arka doctor` |
| See recurring errors | Run `arka gotchas` |
