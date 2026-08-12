#!/usr/bin/env python3
"""ArkaOS menu bar launcher (Foundation PR-5; Windows tray host #548).

A lightweight menu bar / system tray app that surfaces the ArkaOS
runtime state and one-click actions. macOS renders through rumps,
Windows through pystray — both hosts consume the same pure state
model and the same action helpers, which branch per platform:

  - Check for updates      -> scripts/auto-update.sh|.ps1 --force (PR-1 daemon)
  - Open Dashboard         -> start-dashboard.sh|.ps1 ensure + open UI port
  - Start Ollama           -> open -a Ollama / "ollama app.exe"
                              (fallback: ollama serve)
                              [local-ai profile only, when stopped]
  - Doctor                 -> Terminal/console running `npx arkaos doctor`
  - Auto-update on/off     -> npx arkaos autoupdate enable|disable
  - Quit

Posture (matches scripts/auto-update.sh): every failure path logs and
exits 0 — a broken login item must never crash. The UI imports are
guarded per platform: missing rumps/pystray, an unsupported platform,
or a headless session -> clean exit 0 with a hint.

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

IS_MACOS = sys.platform == "darwin"
IS_WINDOWS = sys.platform == "win32"

VALID_PROFILES = ("essential", "complete", "local-ai")
REFRESH_SECONDS = 60
TITLE = "▲"  # ▲ — brand wordmark glyph
TITLE_PENDING = "▲ •"  # ▲ • — sync pending badge
# Contract with installer/menubar.js (optoutPath) and the PR-1 daemon
# (installer/autoupdate.js optoutPath). menubar.test.js locks parity
# against the real JS modules — never rename one side alone.
MENUBAR_OPTOUT_BASENAME = "menubar.optout"
AUTOUPDATE_OPTOUT_BASENAME = "autoupdate.optout"

USAGE = """arka-menubar.py — ArkaOS menu bar launcher (macOS + Windows)
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
        manifest = json.loads(
            (home / "install-manifest.json").read_text(encoding="utf-8")
        )
        state["version"] = manifest.get("version") or None
    except Exception:
        pass
    try:
        sync = json.loads(
            (home / "sync-state.json").read_text(encoding="utf-8")
        )
        state["sync_pending"] = sync.get("version") == "pending-sync"
    except Exception:
        pass
    try:
        profile = json.loads(
            (home / "profile.json").read_text(encoding="utf-8")
        )
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


def _no_window() -> dict:
    """CREATE_NO_WINDOW so tray actions never flash a console (Windows).
    Empty elsewhere — the flag does not exist off Windows."""
    if IS_WINDOWS:
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    return {}


def _powershell(script: Path, *args: str) -> list:
    """argv for a scripts/*.ps1 sibling — same positional CLI as the .sh
    twins (`--force`, `ensure`), parsed from $args on the PowerShell side."""
    return [
        "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", str(script), *args,
    ]


def _open_url(url: str) -> None:
    if IS_WINDOWS:
        os.startfile(url)  # noqa: S606 — the URL is built from our own port file
    else:
        subprocess.run(["/usr/bin/open", url], timeout=15)


def stable_script(name: str) -> Path | None:
    """Resolve a scripts/ file: purge-proof ~/.arkaos/lib snapshot first,
    then the .repo-path reference (autoupdate.js::stableRoot parity)."""
    home = arka_home()
    lib = home / "lib" / "scripts" / name
    if lib.exists():
        return lib
    try:
        repo = Path((home / ".repo-path").read_text(encoding="utf-8").strip())
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
    name = "auto-update.ps1" if IS_WINDOWS else "auto-update.sh"
    script = stable_script(name)
    if script is None:
        log_line(f"check_updates: {name} not found")
        return
    if IS_WINDOWS:
        subprocess.Popen(_powershell(script, "--force"), **_no_window())
    else:
        subprocess.Popen(["/bin/bash", str(script), "--force"])


def _dashboard_env() -> dict:
    """Env for start-dashboard.*: the lib snapshot ships scripts/ but NOT
    dashboard/, so a script resolving ARKAOS_ROOT to its own parent finds
    no UI and degrades to API-only (verified live on Windows: no UI_PORT
    ever written, the button dead-ends). Point ARKAOS_ROOT at the
    .repo-path checkout — the same fallback stable_script() already
    trusts — where the built dashboard actually lives."""
    env = dict(os.environ)
    try:
        root = (arka_home() / ".repo-path").read_text(encoding="utf-8").strip()
        if root and Path(root).exists():
            env.setdefault("ARKAOS_ROOT", root)
    except Exception:
        pass
    return env


def action_open_dashboard() -> None:
    name = "start-dashboard.ps1" if IS_WINDOWS else "start-dashboard.sh"
    script = stable_script(name)
    if script is not None:
        try:
            if IS_WINDOWS:
                subprocess.run(_powershell(script, "ensure"),
                               timeout=120, env=_dashboard_env(), **_no_window())
            else:
                subprocess.run(["/bin/bash", str(script), "ensure"],
                               timeout=120, env=_dashboard_env())
        except Exception as err:
            log_line(f"open_dashboard: ensure failed ({err})")
    ui_port = ""
    try:
        ports = (arka_home() / "dashboard.ports").read_text(encoding="utf-8")
        for line in ports.splitlines():
            if line.startswith("UI_PORT="):
                ui_port = line.split("=", 1)[1].strip()
    except Exception:
        pass
    if ui_port.isdigit():
        _open_url(f"http://localhost:{ui_port}")
    else:
        log_line(
            f"open_dashboard: no UI_PORT after {name} ensure — "
            "check ~/.arkaos/logs for the dashboard startup error"
        )


def action_start_ollama() -> None:
    # Operator decision (PR-5 Phase 0): the app first, `serve` as fallback.
    if IS_WINDOWS:
        local = os.environ.get("LOCALAPPDATA", "")
        app = Path(local) / "Programs" / "Ollama" / "ollama app.exe"
        if local and app.exists():
            subprocess.Popen([str(app)], **_no_window())
            return
        if shutil.which("ollama"):
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                **_no_window(),
            )
        else:
            log_line("start_ollama: neither the Ollama app nor the ollama binary found")
        return
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
    if IS_WINDOWS:
        # `start` (with an explicit window title) opens a console the user
        # keeps; cmd resolves npx.cmd through PATHEXT, which CreateProcess
        # alone cannot.
        subprocess.Popen(
            ["cmd.exe", "/c", "start", "ArkaOS Doctor",
             "cmd.exe", "/k", "npx arkaos doctor"],
            **_no_window(),
        )
        return
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
    if shutil.which("npx") is not None:
        argv = ["npx", "arkaos", "autoupdate", verb]
        if IS_WINDOWS:
            # npx is npx.cmd — CreateProcess cannot exec batch files, so
            # route through cmd. Every argument is a fixed literal.
            argv = ["cmd.exe", "/c", *argv]
        subprocess.run(argv, capture_output=True, timeout=180, **_no_window())
    else:
        log_line(
            "autoupdate_toggle: npx not on the launcher PATH — "
            f"run manually: npx arkaos autoupdate {verb}"
        )
    # The CLI is the authority, but verify the observable contract: where
    # autoupdate.js has no platform support (win32 today) it errors WITHOUT
    # touching the opt-out marker, and the toggle would lie. The marker is
    # the whole read-side contract (read_state + auto-update.sh/.ps1 both
    # gate on it), so apply it directly when the CLI left it unchanged.
    marker = arka_home() / AUTOUPDATE_OPTOUT_BASENAME
    if marker.exists() == enable:  # still the opposite of what verb asked
        try:
            if enable:
                marker.unlink()
            else:
                marker.parent.mkdir(parents=True, exist_ok=True)
                marker.write_text("disabled from the menu bar\n", encoding="utf-8")
            log_line(
                f"autoupdate_toggle: CLI left the marker untouched — applied {verb} directly"
            )
        except Exception as err:
            log_line(f"autoupdate_toggle: {err}")


def action_disable_menubar() -> None:
    """Permanent opt-out from the menu itself (QG M7): writes the marker
    installer/menubar.js honors; the startup guard in run_app makes any
    remaining RunAtLoad an instant no-op until `npx arkaos menubar enable`."""
    marker = arka_home() / MENUBAR_OPTOUT_BASENAME
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("disabled from the menu bar\n", encoding="utf-8")
    log_line("disable: opt-out marker written — re-enable: npx arkaos menubar enable")


# ── UI hosts (guarded imports — never a crashing login item) ─────────────


def run_app() -> int:
    # Permanent opt-out (QG M7): the plist/Startup entry may still fire
    # until an update removes it — the marker makes that launch a no-op.
    if (arka_home() / MENUBAR_OPTOUT_BASENAME).exists():
        print("arka-menubar: user opt-out — exiting (re-enable: npx arkaos menubar enable)")
        return 0
    if IS_MACOS:
        return run_app_macos()
    if IS_WINDOWS:
        return run_app_windows()
    print("arka-menubar: no menu bar host for this platform — nothing to do")
    return 0


def run_app_macos() -> int:
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
            # QG r2 follow-ups: the ollama probe result is CACHED and
            # refreshed by a worker (the 2s `ollama list` subprocess
            # never runs on the menu runloop); the auto-update toggle
            # is disabled while its worker is in flight.
            self._ollama_cache = "absent"
            self._probe_running = False
            self._toggle_inflight = False
            self.refresh(None)
            self.timer = rumps.Timer(self.refresh, REFRESH_SECONDS)
            self.timer.start()

        def _schedule_ollama_probe(self):
            """Worker-side probe -> cache; redraw only on change."""
            if self._probe_running:
                return
            self._probe_running = True
            before = self._ollama_cache

            def probe():
                try:
                    self._ollama_cache = ollama_status()
                finally:
                    self._probe_running = False

            worker = threading.Thread(target=probe, daemon=True)
            worker.start()

            def poll(timer):
                if not worker.is_alive():
                    timer.stop()
                    self._pollers.discard(timer)
                    if self._ollama_cache != before:
                        self.refresh(None)

            poller = self._rumps.Timer(poll, 1)
            self._pollers.add(poller)
            poller.start()

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
            if state["profile"] == "local-ai":
                ollama = self._ollama_cache
                self._schedule_ollama_probe()
            else:
                ollama = "absent"
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
                    "Auto-update: switching…" if self._toggle_inflight
                    else ("Auto-update: on" if state["autoupdate_on"] else "Auto-update: off"),
                    None if self._toggle_inflight else self.on_autoupdate_toggle,
                ),
                "disable": ("Disable menu bar (permanent)", self.on_disable),
                "quit": ("Quit until next login", self.on_quit),
            }
            for item_id in visible:
                label, callback = labels[item_id]
                entry = rumps.MenuItem(label, callback=callback)
                if item_id == "autoupdate_toggle" and not self._toggle_inflight:
                    entry.state = 1 if state["autoupdate_on"] else 0
                if item_id == "disable":
                    entries.append(rumps.separator)
                entries.append(entry)
            self.menu.update(entries)

        def on_check_updates(self, _):
            # Popen is non-blocking, but a fork/exec OSError must not
            # propagate into the rumps callback (QG r2 minor).
            try:
                action_check_updates()
            except Exception as err:
                log_line(f"check_updates: {err}")

        def on_open_dashboard(self, _):
            self._spawn(action_open_dashboard)

        def on_doctor(self, _):
            self._spawn(action_doctor)

        def on_start_ollama(self, _):
            self._spawn(action_start_ollama, refresh_after=True)

        def on_autoupdate_toggle(self, _):
            # Guard against double-fire while the (up to 180s) npx
            # worker runs — the item is disabled and relabelled until
            # the post-worker refresh (QG r2 minor).
            if self._toggle_inflight:
                return
            self._toggle_inflight = True
            enable = not read_state()["autoupdate_on"]

            def work():
                try:
                    action_autoupdate(enable=enable)
                finally:
                    self._toggle_inflight = False

            self._spawn(work, refresh_after=True)
            self.refresh(None)

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


def run_app_windows() -> int:
    """pystray tray host (#548) — same state model and action helpers as
    the rumps host. The menu is regenerated from a callable every time it
    opens (pystray contract), so there is no rumps-style menu.update():
    workers refresh the cached snapshot and the icon/tooltip only."""
    try:
        import pystray
        from PIL import Image, ImageDraw
    except Exception as err:  # missing deps, headless session
        print(
            "arka-menubar: pystray/Pillow unavailable "
            f"({err}) — install: %USERPROFILE%\\.arkaos\\venv\\Scripts\\pip install pystray Pillow"
        )
        return 0

    def draw_icon(pending: bool) -> "Image.Image":
        """The ▲ wordmark as a drawn glyph — Windows tray icons are
        bitmaps, not text. White reads on the dark taskbar; the amber dot
        mirrors the TITLE_PENDING badge."""
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.polygon([(32, 6), (60, 54), (4, 54)], fill=(255, 255, 255, 255))
        if pending:
            draw.ellipse((42, 38, 62, 58), fill=(255, 149, 0, 255))
        return img

    # Shared mutable snapshot: menu generation must be instant (it runs
    # when the menu opens), so the 2s ollama probe only ever runs on the
    # refresher/worker threads — the rumps host's cache posture (QG r2).
    ui = {
        "state": read_state(),
        "ollama": "absent",
        "toggle_inflight": False,
    }
    stop_event = threading.Event()
    icon = pystray.Icon("ArkaOS")

    def refresh(probe_ollama: bool = True) -> None:
        state = read_state()
        ui["state"] = state
        if probe_ollama:
            ui["ollama"] = ollama_status_for(state)
        icon.icon = draw_icon(state.get("sync_pending", False))
        icon.title = "ArkaOS — sync pending" if state.get("sync_pending") else "ArkaOS"
        icon.update_menu()

    def spawn(work, refresh_after: bool = False) -> None:
        """Worker thread with the same guard posture as rumps _spawn: a
        missing binary must log, never die silently (QG M5)."""
        def guarded():
            try:
                work()
            except Exception as err:
                log_line(f"action: {err}")
            finally:
                if refresh_after:
                    refresh()

        threading.Thread(target=guarded, daemon=True).start()

    def on_check_updates(_icon, _item):
        spawn(action_check_updates)

    def on_open_dashboard(_icon, _item):
        spawn(action_open_dashboard)

    def on_doctor(_icon, _item):
        spawn(action_doctor)

    def on_start_ollama(_icon, _item):
        spawn(action_start_ollama, refresh_after=True)

    def on_autoupdate_toggle(_icon, _item):
        if ui["toggle_inflight"]:
            return
        ui["toggle_inflight"] = True
        enable = not read_state()["autoupdate_on"]

        def work():
            try:
                action_autoupdate(enable=enable)
            finally:
                ui["toggle_inflight"] = False

        spawn(work, refresh_after=True)
        icon.update_menu()

    def on_disable(_icon, _item):
        try:
            action_disable_menubar()
        except Exception as err:
            log_line(f"disable: {err}")
        icon.stop()

    def on_quit(_icon, _item):
        icon.stop()

    def build_menu():
        state = ui["state"]
        info = pystray.MenuItem(version_label(state), None, enabled=False)
        yield info
        if state.get("sync_pending"):
            yield pystray.MenuItem(
                "Sync pending — open a Claude session", None, enabled=False
            )
        yield pystray.Menu.SEPARATOR
        inflight = ui["toggle_inflight"]
        labels = {
            "check_updates": pystray.MenuItem("Check for updates", on_check_updates),
            # default=True: left-clicking the tray icon opens the dashboard.
            "open_dashboard": pystray.MenuItem(
                "Open Dashboard", on_open_dashboard, default=True
            ),
            "doctor": pystray.MenuItem("Run Doctor", on_doctor),
            "start_ollama": pystray.MenuItem("Start Ollama", on_start_ollama),
            "autoupdate_toggle": pystray.MenuItem(
                "Auto-update: switching…" if inflight
                else ("Auto-update: on" if state.get("autoupdate_on") else "Auto-update: off"),
                None if inflight else on_autoupdate_toggle,
                checked=None if inflight
                else (lambda _item: ui["state"].get("autoupdate_on", True)),
                enabled=not inflight,
            ),
            "disable": pystray.MenuItem("Disable menu bar (permanent)", on_disable),
            "quit": pystray.MenuItem("Quit until next login", on_quit),
        }
        for item_id in menu_items(state, ui["ollama"]):
            if item_id == "disable":
                yield pystray.Menu.SEPARATOR
            yield labels[item_id]

    icon.menu = pystray.Menu(build_menu)
    icon.icon = draw_icon(ui["state"].get("sync_pending", False))
    icon.title = "ArkaOS"

    def refresher():
        # First pass runs the (profile-gated) ollama probe off the UI
        # thread before the user ever opens the menu.
        refresh()
        while not stop_event.wait(REFRESH_SECONDS):
            refresh()

    def setup(live_icon):
        live_icon.visible = True
        threading.Thread(target=refresher, daemon=True).start()

    try:
        icon.run(setup=setup)
    except Exception as err:
        log_line(f"fatal: {err}")
        print(f"arka-menubar: exiting cleanly after error ({err})")
    finally:
        stop_event.set()
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
