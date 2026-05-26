// PR99b v3.68.0 — single PTY session lifecycle.
//
// Encapsulates the REST + WebSocket handshake against /api/terminal/*.
// The composable owns no DOM and no xterm instance — it just produces
// the bytes-in/bytes-out duplex. The Terminal.vue component glues this
// to an xterm.js canvas.

export interface TerminalSessionMeta {
  session_id: string
  shell: string
  cwd: string
  token: string
  ws_path: string
  max_sessions: number
  active_count: number
}

export interface TerminalSessionHandle {
  meta: Ref<TerminalSessionMeta | null>
  status: Ref<'idle' | 'connecting' | 'open' | 'closed' | 'error'>
  error: Ref<string | null>
  open: () => Promise<void>
  sendInput: (data: string) => void
  sendResize: (cols: number, rows: number) => void
  close: () => Promise<void>
  onOutput: (cb: (chunk: Uint8Array) => void) => () => void
}

export function useTerminalSession(
  apiBaseOverride?: string,
): TerminalSessionHandle {
  // PR99c v3.69.0 — apiBaseOverride lets useTerminalTabs construct
  // sessions from user-event handlers without re-entering Nuxt's
  // composable context.
  const apiBase = apiBaseOverride ?? useApi().apiBase
  const meta = ref<TerminalSessionMeta | null>(null)
  const status = ref<'idle' | 'connecting' | 'open' | 'closed' | 'error'>('idle')
  const error = ref<string | null>(null)

  let ws: WebSocket | null = null
  const listeners: Array<(chunk: Uint8Array) => void> = []

  function wsUrl(path: string, token: string): string {
    const base = apiBase.replace(/^http/, 'ws')
    return `${base}${path}?token=${encodeURIComponent(token)}`
  }

  async function createSession(): Promise<TerminalSessionMeta> {
    const r = await fetch(`${apiBase}/api/terminal/sessions`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ cols: 120, rows: 32 }),
    })
    if (!r.ok) {
      const body = await r.text()
      throw new Error(`create session failed: ${r.status} ${body}`)
    }
    return await r.json()
  }

  async function open() {
    if (status.value === 'open' || status.value === 'connecting') return
    status.value = 'connecting'
    error.value = null
    try {
      const m = await createSession()
      meta.value = m
      ws = new WebSocket(wsUrl(m.ws_path, m.token))
      ws.binaryType = 'arraybuffer'
      ws.onopen = () => {
        status.value = 'open'
      }
      ws.onmessage = (ev) => {
        if (ev.data instanceof ArrayBuffer) {
          const chunk = new Uint8Array(ev.data)
          for (const cb of listeners) cb(chunk)
        } else if (typeof ev.data === 'string') {
          const enc = new TextEncoder().encode(ev.data)
          for (const cb of listeners) cb(enc)
        }
      }
      ws.onerror = () => {
        status.value = 'error'
        error.value = 'websocket error'
      }
      ws.onclose = (ev) => {
        status.value = 'closed'
        if (ev.code !== 1000 && ev.code !== 1005) {
          error.value = `closed (${ev.code}) ${ev.reason || ''}`.trim()
        }
      }
    } catch (e) {
      status.value = 'error'
      error.value = e instanceof Error ? e.message : String(e)
    }
  }

  function sendInput(data: string) {
    if (!ws || ws.readyState !== WebSocket.OPEN) return
    ws.send(JSON.stringify({ type: 'input', data }))
  }

  function sendResize(cols: number, rows: number) {
    if (!ws || ws.readyState !== WebSocket.OPEN) return
    ws.send(JSON.stringify({ type: 'resize', cols, rows }))
  }

  async function close() {
    try {
      ws?.close(1000, 'client close')
    } catch (_e) {
      // ignore
    }
    const id = meta.value?.session_id
    if (id) {
      try {
        await fetch(`${apiBase}/api/terminal/sessions/${id}`, { method: 'DELETE' })
      } catch (_e) {
        // ignore — best-effort cleanup; backend reaper will catch it
      }
    }
    status.value = 'closed'
  }

  function onOutput(cb: (chunk: Uint8Array) => void) {
    listeners.push(cb)
    return () => {
      const idx = listeners.indexOf(cb)
      if (idx >= 0) listeners.splice(idx, 1)
    }
  }

  return {
    meta,
    status,
    error,
    open,
    sendInput,
    sendResize,
    close,
    onOutput,
  }
}
