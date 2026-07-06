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
