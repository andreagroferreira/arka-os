"""Locating the POSIX shell the hook tests run their .sh twins under.

`subprocess.run(["bash", ...])` is not equivalent to `bash` typed at a
prompt. On Windows CreateProcess searches the *system directory* before
anything on PATH, and `C:\\Windows\\System32\\bash.exe` is the WSL launcher
shim. So a machine with WSL installed runs every `.sh` hook test under
WSL — which cannot open the `C:\\...` path it is handed and exits 127 —
even when Git for Windows' bash is first on PATH and `shutil.which("bash")`
correctly reports it.

Resolving through PATH ourselves and passing the absolute interpreter
path sidesteps the CreateProcess search order entirely. On POSIX this is
a no-op: `shutil.which("bash")` returns the same `/usr/bin/bash` (or
`/bin/bash`) the bare name would have found.
"""

from __future__ import annotations

import shutil

# Absolute path so CreateProcess never gets to run its own search.
# Falls back to the bare name where PATH lookup fails, keeping the old
# behavior rather than raising at import time.
BASH = shutil.which("bash") or "bash"
