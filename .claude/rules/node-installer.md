---
paths:
  - "installer/**/*.js"
  - "installer/**/*.mjs"
  - "package.json"
---

# Node.js Installer Rules

- ESM modules (import/export), no CommonJS require()
- Support both Node.js and Bun runtimes
- Graceful fallbacks when optional dependencies unavailable
- No interactive prompts during headless/CI runs
- All paths must use os.homedir() or path.join, never hardcoded
