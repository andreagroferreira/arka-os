#!/usr/bin/env python3
"""ArkaOS Scheduler Daemon — entry point for launchd/systemd/schtasks.

Runs in a loop, checking every 60 seconds whether any scheduled cognitive
task (Dreaming, Research) should execute at the current time.
"""

import sys
import time
from pathlib import Path

# Ensure ArkaOS core is importable
ARKAOS_ROOT = Path(__file__).resolve().parent.parent
if str(ARKAOS_ROOT) not in sys.path:
    sys.path.insert(0, str(ARKAOS_ROOT))

from core.cognition.scheduler.daemon import ArkaScheduler  # noqa: E402

HOME = Path.home()
CONFIG_PATH = str(HOME / ".arkaos" / "schedules.yaml")
LOG_DIR = str(HOME / ".arkaos" / "logs")
LOCK_PATH = str(HOME / ".arkaos" / "scheduler.lock")


def main() -> None:
    scheduler = ArkaScheduler(
        config_path=CONFIG_PATH,
        log_dir=LOG_DIR,
        lock_path=LOCK_PATH,
    )

    if not scheduler.acquire_lock():
        print("Another scheduler instance is already running. Exiting.")
        sys.exit(1)

    print(f"ArkaOS Scheduler started — {len(scheduler.schedules)} tasks loaded")
    try:
        while True:
            scheduler.run_once()
            time.sleep(60)
    except KeyboardInterrupt:
        print("Scheduler stopped.")
    finally:
        scheduler.release_lock()


if __name__ == "__main__":
    main()
