import { existsSync, cpSync, chmodSync, readdirSync, mkdirSync } from "node:fs";
import { join } from "node:path";

// Deploys config/hooks/_lib/ (shared hook libraries — the Python
// interpreter resolver lives here) into an install's hooks directory.
// Single implementation shared by the fresh-install path
// (index.js::installHooks) and the update path (update.js): the v4.3.2
// regression existed precisely because the two deploy loops drifted.
// Returns true when the lib dir was copied, false when the source has
// no _lib/ to deploy.
export function copyHookLib(srcHooksDir, destHooksDir) {
  const srcLibDir = join(srcHooksDir, "_lib");
  if (!existsSync(srcLibDir)) return false;
  const destLibDir = join(destHooksDir, "_lib");
  mkdirSync(destLibDir, { recursive: true });
  cpSync(srcLibDir, destLibDir, { recursive: true });
  // chmod is a no-op on Windows (NTFS ACLs aren't POSIX); the try/catch
  // keeps the copy result authoritative even if it throws.
  try {
    for (const f of readdirSync(destLibDir)) {
      if (f.endsWith(".sh")) chmodSync(join(destLibDir, f), 0o755);
    }
  } catch {}
  return true;
}

// F2-6 fast-path assets: the Node shims + the generated gate manifest
// (engine.cjs travels inside _lib/ via copyHookLib). The list lives HERE,
// in the single shared deploy function, so index.js and update.js cannot
// drift the way the v4.3.2 hook-lib regression did. The .sh/.ps1 hooks
// keep deploying regardless — they are the delegation target and the
// ARKA_HOOK_FASTPATH=0 kill-switch path. POSIX-only feature: the assets
// still copy on Windows (harmless), but the adapter never registers them.
export const HOOK_ASSETS = [
  "pre-tool-use.cjs",
  "post-tool-use.cjs",
  "gate-manifest.json",
];

export function copyHookAssets(srcHooksDir, destHooksDir) {
  let copied = 0;
  for (const name of HOOK_ASSETS) {
    const srcPath = join(srcHooksDir, name);
    if (!existsSync(srcPath)) continue;
    mkdirSync(destHooksDir, { recursive: true });
    cpSync(srcPath, join(destHooksDir, name));
    if (name.endsWith(".cjs")) {
      try { chmodSync(join(destHooksDir, name), 0o755); } catch {}
    }
    copied += 1;
  }
  return copied;
}
