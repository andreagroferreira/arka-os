## Node.js Stack Conventions

- ESM modules (import/export); no CommonJS `require()`.
- Support Node and Bun runtimes when writing CLI tooling.
- Graceful fallbacks when optional dependencies are missing.
- All paths via `os.homedir()` or `path.join`; never hardcoded.
- No interactive prompts in headless/CI runs.
