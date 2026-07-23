#!/usr/bin/env python3
"""ArkaOS menu bar launcher (Foundation PR-5).

A lightweight macOS menu bar app (rumps) that surfaces the ArkaOS
runtime state and one-click actions:

  - Check for updates      -> scripts/auto-update.sh --force (PR-1 daemon)
  - Open Dashboard         -> start-dashboard.sh ensure + open UI port
  - Start Ollama           -> open -a Ollama (fallback: ollama serve)
                              [local-ai profile only, when stopped]
  - Doctor                 -> Terminal running `npx arkaos doctor`
  - Auto-update on/off     -> npx arkaos autoupdate enable|disable
  - Quit

Posture (matches scripts/auto-update.sh): every failure path logs and
exits 0 — a broken login item must never crash. rumps import is guarded:
non-macOS, missing rumps, or headless -> clean exit 0 with a hint.

State model and menu-visibility logic are PURE functions so tests
exercise them via the introspection flags without rumps or a display:

  arka-menubar.py --print-state   JSON of read_state()
  arka-menubar.py --print-menu    JSON of visible menu item ids

Test hooks (env): ARKA_MENUBAR_HOME overrides the ~/.arkaos parent dir;
ARKA_MENUBAR_OLLAMA (absent|stopped|running) overrides the live probe.
The probe itself only runs on the local-ai profile (the only profile
that ever surfaces Start Ollama); other profiles never spawn ollama.
"""

# PEP 604 annotations (`Path | None`) are evaluated at def time without
# this import and raise TypeError on Python < 3.10 — and the plist's
# last-resort interpreter is the macOS system /usr/bin/python3 (3.9).
# The future import turns them into strings, importable everywhere.
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

VALID_PROFILES = ("essential", "complete", "local-ai")
REFRESH_SECONDS = 60
TITLE = "▲"  # ▲ — brand wordmark glyph
TITLE_PENDING = "▲ •"  # ▲ • — sync pending badge
# Contract with installer/menubar.js (optoutPath) and the PR-1 daemon
# (installer/autoupdate.js optoutPath). menubar.test.js locks parity
# against the real JS modules — never rename one side alone.
MENUBAR_OPTOUT_BASENAME = "menubar.optout"
AUTOUPDATE_OPTOUT_BASENAME = "autoupdate.optout"

USAGE = """arka-menubar.py — ArkaOS menu bar launcher (macOS)
  (no args)        run the menu bar app (exits 0 when unsupported)
  --print-state    JSON snapshot of the runtime state
  --print-menu     JSON list of visible menu item ids
  --help           this text
"""


def arka_home() -> Path:
    override = os.environ.get("ARKA_MENUBAR_HOME", "")
    base = Path(override) if override else Path.home()
    return base / ".arkaos"


# ── Pure state model ─────────────────────────────────────────────────────


def read_state(home: Path | None = None) -> dict:
    """Read-only snapshot of the runtime state. Never throws."""
    home = home or arka_home()
    state = {
        "version": None,
        "sync_pending": False,
        "profile": "essential",
        "autoupdate_on": True,
    }
    try:
        manifest = json.loads((home / "install-manifest.json").read_text())
        state["version"] = manifest.get("version") or None
    except Exception:
        pass
    try:
        sync = json.loads((home / "sync-state.json").read_text())
        state["sync_pending"] = sync.get("version") == "pending-sync"
    except Exception:
        pass
    try:
        profile = json.loads((home / "profile.json").read_text())
        value = str(profile.get("installProfile", "essential")).strip().lower()
        state["profile"] = value if value in VALID_PROFILES else "essential"
    except Exception:
        pass
    state["autoupdate_on"] = not (home / AUTOUPDATE_OPTOUT_BASENAME).exists()
    return state


def ollama_status() -> str:
    """absent | stopped | running — read-only probes, short timeouts."""
    override = os.environ.get("ARKA_MENUBAR_OLLAMA", "")
    if override in ("absent", "stopped", "running"):
        return override
    if shutil.which("ollama") is None:
        return "absent"
    try:
        subprocess.run(
            ["ollama", "list"], capture_output=True, timeout=2, check=True
        )
        return "running"
    except Exception:
        return "stopped"


def ollama_status_for(state: dict) -> str:
    """Gate the live probe: only the local-ai profile ever surfaces the
    Start Ollama item, so every other profile skips the subprocess."""
    if state.get("profile") != "local-ai":
        return "absent"
    return ollama_status()


def menu_items(state: dict, ollama: str) -> list:
    """Pure: visible menu item ids for a given state."""
    items = ["check_updates", "open_dashboard", "doctor"]
    if state.get("profile") == "local-ai" and ollama == "stopped":
        items.append("start_ollama")
    items.append("autoupdate_toggle")
    items.append("disable")
    items.append("quit")
    return items


def title_for(state: dict) -> str:
    return TITLE_PENDING if state.get("sync_pending") else TITLE


def version_label(state: dict) -> str:
    """User-visible copy — never renders 'vunknown'."""
    version = state.get("version")
    return f"ArkaOS v{version}" if version else "ArkaOS (version unknown)"


# ── Action helpers (subprocess, never blocking the UI thread) ────────────


def stable_script(name: str) -> Path | None:
    """Resolve a scripts/ file: purge-proof ~/.arkaos/lib snapshot first,
    then the .repo-path reference (autoupdate.js::stableRoot parity)."""
    home = arka_home()
    lib = home / "lib" / "scripts" / name
    if lib.exists():
        return lib
    try:
        repo = Path((home / ".repo-path").read_text().strip())
        candidate = repo / "scripts" / name
        if candidate.exists():
            return candidate
    except Exception:
        pass
    return None


def log_line(message: str) -> None:
    try:
        log_dir = arka_home() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        with open(log_dir / "menubar.log", "a", encoding="utf-8") as handle:
            handle.write(message.rstrip() + "\n")
    except Exception:
        pass


def action_check_updates() -> None:
    script = stable_script("auto-update.sh")
    if script is None:
        log_line("check_updates: auto-update.sh not found")
        return
    subprocess.Popen(["/bin/bash", str(script), "--force"])


def action_open_dashboard() -> None:
    script = stable_script("start-dashboard.sh")
    if script is not None:
        try:
            subprocess.run(["/bin/bash", str(script), "ensure"], timeout=120)
        except Exception as err:
            log_line(f"open_dashboard: ensure failed ({err})")
    ui_port = ""
    try:
        for line in (arka_home() / "dashboard.ports").read_text().splitlines():
            if line.startswith("UI_PORT="):
                ui_port = line.split("=", 1)[1].strip()
    except Exception:
        pass
    if ui_port.isdigit():
        subprocess.run(["/usr/bin/open", f"http://localhost:{ui_port}"], timeout=15)
    else:
        log_line(
            "open_dashboard: no UI_PORT after start-dashboard.sh ensure — "
            "check ~/.arkaos/logs for the dashboard startup error"
        )


def action_start_ollama() -> None:
    # Operator decision (PR-5 Phase 0): the app first, `serve` as fallback.
    result = subprocess.run(["/usr/bin/open", "-a", "Ollama"],
                            capture_output=True, timeout=15)
    if result.returncode != 0:
        if shutil.which("ollama"):
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            log_line("start_ollama: neither Ollama.app nor ollama binary found")


def action_doctor() -> None:
    subprocess.run([
        "/usr/bin/osascript", "-e",
        'tell application "Terminal" to activate',
        "-e",
        'tell application "Terminal" to do script "npx arkaos doctor"',
    ], capture_output=True, timeout=15)


def action_autoupdate(enable: bool) -> None:
    """Runs on a worker thread (npx resolves the registry — slow/offline
    must degrade to a logged line, never a silent no-op)."""
    verb = "enable" if enable else "disable"
    if shutil.which("npx") is None:
        log_line(
            "autoupdate_toggle: npx not on the LaunchAgent PATH — "
            f"run manually: npx arkaos autoupdate {verb}"
        )
        return
    subprocess.run(["npx", "arkaos", "autoupdate", verb],
                   capture_output=True, timeout=180)


def action_disable_menubar() -> None:
    """Permanent opt-out from the menu itself (QG M7): writes the marker
    installer/menubar.js honors; the startup guard in run_app makes any
    remaining RunAtLoad an instant no-op until `npx arkaos menubar enable`."""
    marker = arka_home() / MENUBAR_OPTOUT_BASENAME
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("disabled from the menu bar\n", encoding="utf-8")
    log_line("disable: opt-out marker written — re-enable: npx arkaos menubar enable")


# ── rumps app (guarded import — never a crashing login item) ─────────────


def run_app() -> int:
    if sys.platform != "darwin":
        print("arka-menubar: macOS only — nothing to do")
        return 0
    # Permanent opt-out (QG M7): the plist may still RunAtLoad until an
    # update removes it — the marker makes that launch an instant no-op.
    if (arka_home() / MENUBAR_OPTOUT_BASENAME).exists():
        print("arka-menubar: user opt-out — exiting (re-enable: npx arkaos menubar enable)")
        return 0
    try:
        import rumps
    except Exception as err:  # missing dep, headless session, SIP oddity
        print(
            "arka-menubar: rumps unavailable "
            f"({err}) — install: ~/.arkaos/venv/bin/pip install rumps"
        )
        return 0

    class ArkaMenuBar(rumps.App):
        def __init__(self):
            super().__init__(TITLE, quit_button=None)
            self._rumps = rumps
            self._pollers = set()
            self.refresh(None)
            self.timer = rumps.Timer(self.refresh, REFRESH_SECONDS)
            self.timer.start()

        def _spawn(self, work, refresh_after=False):
            """Run side-effect work off the AppKit main thread (a blocking
            subprocess in a rumps callback freezes the whole menu bar).
            The worker only runs subprocesses and reads files — ALL rumps
            interaction stays on the main thread: an optional 1s poll timer
            (main thread) refreshes the menu once the worker finishes.
            Worker bodies are exception-guarded to log_line — a missing
            binary must never die silently (QG M5)."""
            def guarded():
                try:
                    work()
                except Exception as err:
                    log_line(f"action: {err}")

            worker = threading.Thread(target=guarded, daemon=True)
            worker.start()
            if not refresh_after:
                return

            def poll(timer):
                if not worker.is_alive():
                    timer.stop()
                    self._pollers.discard(timer)
                    self.refresh(None)

            poller = self._rumps.Timer(poll, 1)
            self._pollers.add(poller)
            poller.start()

        def refresh(self, _sender):
            state = read_state()
            ollama = ollama_status_for(state)
            self.title = title_for(state)
            self.menu.clear()
            info = rumps.MenuItem(version_label(state))
            info.set_callback(None)  # informational, not clickable
            entries = [info]
            if state["sync_pending"]:
                pending = rumps.MenuItem("Sync pending — open a Claude session")
                pending.set_callback(None)
                entries.append(pending)
            entries.append(rumps.separator)
            visible = menu_items(state, ollama)
            labels = {
                "check_updates": ("Check for updates", self.on_check_updates),
                "open_dashboard": ("Open Dashboard", self.on_open_dashboard),
                "doctor": ("Run Doctor", self.on_doctor),
                "start_ollama": ("Start Ollama", self.on_start_ollama),
                "autoupdate_toggle": (
                    "Auto-update: on" if state["autoupdate_on"] else "Auto-update: off",
                    self.on_autoupdate_toggle,
                ),
                "disable": ("Disable menu bar (permanent)", self.on_disable),
                "quit": ("Quit until next login", self.on_quit),
            }
            for item_id in visible:
                label, callback = labels[item_id]
                entry = rumps.MenuItem(label, callback=callback)
                if item_id == "autoupdate_toggle":
                    entry.state = 1 if state["autoupdate_on"] else 0
                if item_id == "disable":
                    entries.append(rumps.separator)
                entries.append(entry)
            self.menu.update(entries)

        def on_check_updates(self, _):
            action_check_updates()

        def on_open_dashboard(self, _):
            self._spawn(action_open_dashboard)

        def on_doctor(self, _):
            self._spawn(action_doctor)

        def on_start_ollama(self, _):
            self._spawn(action_start_ollama, refresh_after=True)

        def on_autoupdate_toggle(self, _):
            enable = not read_state()["autoupdate_on"]
            self._spawn(lambda: action_autoupdate(enable=enable), refresh_after=True)

        def on_disable(self, _):
            try:
                action_disable_menubar()
            except Exception as err:
                log_line(f"disable: {err}")
            self._rumps.quit_application()

        def on_quit(self, _):
            self._rumps.quit_application()

    try:
        ArkaMenuBar().run()
    except Exception as err:
        log_line(f"fatal: {err}")
        print(f"arka-menubar: exiting cleanly after error ({err})")
    return 0


def main(argv: list) -> int:
    if "--help" in argv or "-h" in argv:
        print(USAGE)
        return 0
    if "--print-state" in argv:
        print(json.dumps(read_state()))
        return 0
    if "--print-menu" in argv:
        state = read_state()
        print(json.dumps(menu_items(state, ollama_status_for(state))))
        return 0
    if argv and argv[0].startswith("-"):
        print(f"arka-menubar: unknown option {argv[0]}\n\n{USAGE}")
        return 2
    return run_app()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
