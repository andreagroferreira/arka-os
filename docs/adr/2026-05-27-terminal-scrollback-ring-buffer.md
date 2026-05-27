# ADR: In-memory scrollback ring-buffer for terminal session replay

- **Date:** 2026-05-27
- **Status:** Accepted
- **Deciders:** Marco (CTO), Bruno (Security), operator (Andre)
- **Feature:** Persistent terminal sessions (PR-T1 backend + PR-T2 frontend, shipped together as v3.71.0)

## Context

The dashboard terminal (xterm.js + PTY over WebSocket, the PR99 series)
loses the operator's session whenever they navigate to another dashboard
page or reload the browser. The page component unmounts, the page-scoped
`useTerminalTabs` state is destroyed, and the frontend forgets the session
IDs — so even though the backend PTY survives the 30-minute idle window,
the client can never reattach. A long-running process (e.g. `claude`)
keeps running on an orphaned PTY while the operator sees a blank terminal.

The chosen fix ("Completo / robusto") reattaches a reconnecting client to
the live backend PTY. But a freshly reconnected WebSocket only receives
*new* output — the kernel PTY buffer does not replay the transcript the
operator had on screen. To restore the session "as it was left", the
server must retain recent output and replay it on (re)connect.

## Decision

Each `TerminalSession` keeps a **bounded, in-memory scrollback ring-buffer**
of raw PTY output bytes, recorded at the single output choke-point
(`TerminalSession.read`). On WebSocket (re)connect the server sends the
buffer to the client **before** attaching the live reader, so the
historical prefix always precedes new output with no interleave and no
duplication (the buffered bytes were already consumed from the kernel
buffer on first read).

This "no duplication" guarantee holds for the **serialized single
connection per session** that the frontend enforces (the
`attach()`/`open()` no-op guard prevents a tab from double-connecting).
`asyncio` allows only one `add_reader` per fd, so two *concurrent*
WebSockets on the same session id are not supported — the second would
replace the first's reader and the shared replay snapshot could
duplicate. Single-writer-per-session enforcement is tracked as a
follow-up; it is out of scope under the localhost single-operator model.

- **Default size:** 512 KB per session (~4 MB across the 8-session cap).
- **Configurable:** `ARKAOS_TERMINAL_SCROLLBACK_BYTES`.
- **Eviction:** oldest bytes dropped when over cap (`del buf[:-cap]`).

## Privacy / security trade-off (the crux)

The audit log (`core/terminal/audit.py`) is deliberately **metadata-only**
— it never captures input/output payloads, to avoid persisting secrets
(PATs, passwords, tokens) that operators paste into terminals. The
scrollback buffer **does** hold raw output, which softens that posture.

We accept this under the following invariants, which preserve the core
guarantee *"nothing sensitive is written to disk"*:

1. **RAM-only.** The buffer lives in process memory. It is **never**
   written to disk and **never** sent to the audit log.
2. **Transient.** Lost on API process restart (the bearer token rotates
   on restart too, so stale client session IDs cleanly fail to reattach).
3. **Cleared on close.** `_close_fd` empties the buffer when the session
   ends (manual close, exit, idle-timeout, shutdown).
4. **Auth-gated replay.** The buffer is only ever transmitted over a
   WebSocket that passed the localhost origin check **and** the
   per-process bearer token, for that exact session id.
5. **Bounded.** Capped size limits the blast radius of #1.

Functionally, the replayed bytes are the same bytes that were already on
the operator's screen; we are restoring their own view on their own
machine. This holds only under the **localhost single-operator**
deployment model, which remains an explicit invariant of the feature
(documented in `core/terminal/__init__.py`).

## Consequences

- ✅ Sessions survive dashboard navigation and browser reload with recent
  scrollback intact.
- ✅ No new on-disk surface; audit privacy invariant preserved.
- ⚠️ Output older than the cap is not recoverable (acceptable; communicated
  in the UI as "recent history").
- ⚠️ Trimming at a raw byte boundary can clip a multi-byte UTF-8 / ANSI
  sequence at the very head of the replay; xterm.js tolerates a stray
  leading partial byte, so this is cosmetic at worst.
- ⛔ Not safe for multi-user / remote-host deployment without per-operator
  token isolation and session ownership — out of scope, see localhost
  invariant.

## Alternatives considered

- **No replay, reattach only:** simplest, but the operator reconnects to a
  blank screen above the cursor — fails the "as I left it" requirement.
- **Server-side persistent transcript (disk):** would survive API restart
  but directly violates the metadata-only audit privacy stance. Rejected.
- **Client-side buffering in IndexedDB:** the client is exactly what dies
  on reload, so it cannot be the source of truth for replay. Rejected.
