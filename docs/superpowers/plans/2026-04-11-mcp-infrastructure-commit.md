# MCP Infrastructure Commit — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Commit the existing MCP infrastructure (registry, profiles, scripts, arka-prompts server) to the ArkaOS repo so the installer can deploy it to all users.

**Architecture:** Copy 18 files from the local install (`~/.claude/skills/arka/`) to the repo at `mcps/`. Fix 3 hardcoded personal paths in `registry.json` with `{home}` placeholders. Extend `apply-mcps.sh` to resolve `{home}`. Update installer to deploy the `mcps/` directory.

**Tech Stack:** JSON, Bash, Node.js (installer), Python (arka-prompts server)

---

### Task 1: Copy MCP files to repo

**Files:**
- Create: `mcps/registry.json`
- Create: `mcps/profiles/*.json` (10 files)
- Create: `mcps/stacks/*.json` (2 files)
- Create: `mcps/scripts/apply-mcps.sh`
- Create: `mcps/arka-prompts/server.py`
- Create: `mcps/arka-prompts/commands.py`
- Create: `mcps/arka-prompts/pyproject.toml`
- Create: `mcps/arka-prompts/.gitignore`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p mcps/profiles mcps/stacks mcps/scripts mcps/arka-prompts
```

- [ ] **Step 2: Copy registry, profiles, stacks, and scripts**

```bash
cp ~/.claude/skills/arka/mcps/registry.json mcps/registry.json
cp ~/.claude/skills/arka/mcps/profiles/*.json mcps/profiles/
cp ~/.claude/skills/arka/mcps/stacks/*.json mcps/stacks/
cp ~/.claude/skills/arka/mcps/scripts/apply-mcps.sh mcps/scripts/apply-mcps.sh
chmod +x mcps/scripts/apply-mcps.sh
```

- [ ] **Step 3: Copy arka-prompts MCP server (excluding .venv and __pycache__)**

```bash
cp ~/.claude/skills/arka/mcp-server/server.py mcps/arka-prompts/server.py
cp ~/.claude/skills/arka/mcp-server/commands.py mcps/arka-prompts/commands.py
cp ~/.claude/skills/arka/mcp-server/pyproject.toml mcps/arka-prompts/pyproject.toml
```

- [ ] **Step 4: Create .gitignore for arka-prompts**

Write `mcps/arka-prompts/.gitignore`:
```
.venv/
__pycache__/
*.pyc
uv.lock
```

- [ ] **Step 5: Verify file count**

```bash
find mcps/ -type f | wc -l
```
Expected: 18 files (1 registry + 10 profiles + 2 stacks + 1 script + 3 server + 1 gitignore)

- [ ] **Step 6: Commit**

```bash
git add mcps/
git commit -m "feat(mcps): add MCP registry, profiles, scripts, and arka-prompts server"
```

---

### Task 2: Fix hardcoded paths in registry.json

**Files:**
- Modify: `mcps/registry.json:10,17,40`

- [ ] **Step 1: Replace hardcoded path on line 10 (arka-prompts args)**

Replace:
```json
"args": ["--directory", "/Users/andreagroferreira/.claude/skills/arka/mcp-server", "run", "server.py"],
```
With:
```json
"args": ["--directory", "{home}/.claude/skills/arka/mcp-server", "run", "server.py"],
```

- [ ] **Step 2: Replace hardcoded path on line 17 (obsidian vault)**

Replace:
```json
"args": ["@bitbonsai/mcpvault@latest", "/Users/andreagroferreira/Documents/Personal"],
```
With:
```json
"args": ["@bitbonsai/mcpvault@latest", "{home}/Documents/Personal"],
```

- [ ] **Step 3: Replace hardcoded path on line 40 (memory-bank root)**

Replace:
```json
"MEMORY_BANK_ROOT": "/Users/andreagroferreira/memory-bank"
```
With:
```json
"MEMORY_BANK_ROOT": "{home}/memory-bank"
```

- [ ] **Step 4: Verify no personal paths remain**

```bash
grep -n "andreagroferreira" mcps/registry.json
```
Expected: zero matches

- [ ] **Step 5: Verify JSON is valid**

```bash
python3 -c "import json; json.load(open('mcps/registry.json')); print('VALID')"
```
Expected: VALID

- [ ] **Step 6: Commit**

```bash
git add mcps/registry.json
git commit -m "fix(mcps): replace hardcoded paths with {home} placeholder in registry"
```

---

### Task 3: Extend apply-mcps.sh to resolve {home}

**Files:**
- Modify: `mcps/scripts/apply-mcps.sh:180`

- [ ] **Step 1: Find the existing {cwd} sed line**

```bash
grep -n "{cwd}" mcps/scripts/apply-mcps.sh
```
Expected: line 180 with `sed "s|{cwd}|$PROJECT_DIR|g"`

- [ ] **Step 2: Extend sed to also resolve {home}**

Replace:
```bash
MCP_ARGS=$(echo "$MCP_ARGS" | sed "s|{cwd}|$PROJECT_DIR|g")
```
With:
```bash
MCP_ARGS=$(echo "$MCP_ARGS" | sed "s|{cwd}|$PROJECT_DIR|g; s|{home}|$HOME|g")
```

- [ ] **Step 3: Check if there are other places that resolve args/env values**

```bash
grep -n "sed.*{" mcps/scripts/apply-mcps.sh
```
If other sed lines exist that handle env or args, add `{home}` resolution there too.

- [ ] **Step 4: Test the script resolves correctly**

```bash
mkdir -p /tmp/mcp-test
bash mcps/scripts/apply-mcps.sh laravel --project /tmp/mcp-test 2>&1
cat /tmp/mcp-test/.mcp.json | python3 -c "import json,sys; d=json.load(sys.stdin); print('VALID JSON'); [print(f'  {k}') for k in d.get('mcpServers',{})]"
grep -c "andreagroferreira" /tmp/mcp-test/.mcp.json
rm -rf /tmp/mcp-test
```
Expected: valid JSON with MCP servers listed, zero personal path matches

- [ ] **Step 5: Commit**

```bash
git add mcps/scripts/apply-mcps.sh
git commit -m "fix(mcps): resolve {home} placeholder in apply-mcps.sh"
```

---

### Task 4: Update installer to deploy mcps/ directory

**Files:**
- Modify: `installer/index.js` — `installSkill()` function
- Modify: `installer/update.js` — skill update function

- [ ] **Step 1: Add mcps directory copy to index.js installSkill()**

Find the section that copies the main arka skill (after `deployTop` or `copyResources` for the arka skill). Add after it:

```javascript
// Deploy MCP infrastructure (registry, profiles, scripts, arka-prompts server)
const mcpsSrc = join(arkaosRoot, "mcps");
const mcpsDest = join(installDir, "skills", "arka", "mcps");
if (existsSync(mcpsSrc)) {
  for (const sub of ["profiles", "stacks", "scripts"]) {
    const srcDir = join(mcpsSrc, sub);
    if (existsSync(srcDir)) {
      const destDir = join(mcpsDest, sub);
      ensureDir(destDir);
      for (const f of readdirSync(srcDir)) {
        copyFileSync(join(srcDir, f), join(destDir, f));
      }
    }
  }
  // Registry at root
  if (existsSync(join(mcpsSrc, "registry.json"))) {
    copyFileSync(join(mcpsSrc, "registry.json"), join(mcpsDest, "registry.json"));
  }
  // Make apply-mcps.sh executable
  try { chmodSync(join(mcpsDest, "scripts", "apply-mcps.sh"), 0o755); } catch {}

  // arka-prompts MCP server
  const serverSrc = join(mcpsSrc, "arka-prompts");
  const serverDest = join(installDir, "skills", "arka", "mcp-server");
  if (existsSync(serverSrc)) {
    ensureDir(serverDest);
    for (const f of ["server.py", "commands.py", "pyproject.toml"]) {
      if (existsSync(join(serverSrc, f))) {
        copyFileSync(join(serverSrc, f), join(serverDest, f));
      }
    }
  }
  ok("MCP infrastructure deployed (registry, profiles, scripts, arka-prompts)");
}
```

- [ ] **Step 2: Add same logic to update.js**

Add the same mcps copy block to the update function, using `console.log("         \u2713 MCP infrastructure updated");` instead of `ok()`.

- [ ] **Step 3: Verify install destination matches what skills expect**

Skills reference `$ARKA_OS/mcps/scripts/apply-mcps.sh` where `$ARKA_OS=~/.claude/skills/arka`. Verify the destination path:
```bash
echo "Expected: ~/.claude/skills/arka/mcps/scripts/apply-mcps.sh"
echo "Install destination: <installDir>/skills/arka/mcps/scripts/apply-mcps.sh"
```
These must match. If `installDir` is `~/.arkaos` then the deploy writes to `~/.arkaos/skills/arka/mcps/` — but skills expect `~/.claude/skills/arka/mcps/`. Check how other skills are deployed and match the pattern.

- [ ] **Step 4: Run full test suite**

```bash
python -m pytest tests/ --tb=short -q
```
Expected: 2002 passed

- [ ] **Step 5: Commit**

```bash
git add installer/index.js installer/update.js
git commit -m "feat(installer): deploy MCP infrastructure during install and update"
```

---

### Task 5: End-to-end validation and Quality Gate

- [ ] **Step 1: Verify no personal paths in any committed file**

```bash
grep -r "andreagroferreira" mcps/
```
Expected: zero matches

- [ ] **Step 2: Verify all files present**

```bash
ls mcps/registry.json mcps/profiles/*.json mcps/stacks/*.json mcps/scripts/apply-mcps.sh mcps/arka-prompts/server.py mcps/arka-prompts/commands.py mcps/arka-prompts/pyproject.toml
```
Expected: all 17 content files listed (18 minus .gitignore)

- [ ] **Step 3: Test apply-mcps.sh end-to-end**

```bash
mkdir -p /tmp/mcp-e2e
bash mcps/scripts/apply-mcps.sh laravel --project /tmp/mcp-e2e
python3 -c "
import json
with open('/tmp/mcp-e2e/.mcp.json') as f:
    d = json.load(f)
servers = list(d.get('mcpServers', {}).keys())
print(f'{len(servers)} MCP servers configured')
for s in servers:
    print(f'  - {s}')
assert len(servers) >= 5, f'Expected at least 5 servers, got {len(servers)}'
print('PASS')
"
rm -rf /tmp/mcp-e2e
```

- [ ] **Step 4: Run full test suite**

```bash
python -m pytest tests/ --tb=short -q
```
Expected: 2002+ passed

- [ ] **Step 5: Quality Gate — submit to Francisca (Tech) and Eduardo (Copy)**

- [ ] **Step 6: Commit spec doc**

```bash
git add docs/superpowers/specs/2026-04-11-mcp-infrastructure-commit-design.md
git add docs/superpowers/plans/2026-04-11-mcp-infrastructure-commit.md
git commit -m "docs: add MCP infrastructure commit spec and plan"
```
