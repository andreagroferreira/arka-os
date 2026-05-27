// PR99c v3.69.0 — multi-session tab manager for the terminal.
// v3.71.0 — state is now a MODULE-LEVEL singleton (not page-scoped), so
// tabs + their live PTY sessions survive route navigation. The terminal
// UI lives in the app-wide dock (TerminalDock.vue), mounted once in the
// default layout outside <NuxtPage>, so navigating never unmounts it.
// On a full browser reload the singleton is gone, so reattachOnLoad()
// reconciles persisted session IDs against the live backend sessions and
// reconnects (the WS connect replays scrollback — see PR-T1 v3.71.0).
//
// Live session handles (which carry refs) are kept in a NON-reactive Map,
// separate from the reactive `tabs` metadata, so Vue never deep-unwraps
// their inner refs. SSR-safe: the dashboard runs with ssr:false.

import {
  useTerminalSession,
  type TerminalSessionHandle
} from '~/composables/useTerminalSession'

export interface TerminalTab {
  id: string
  title: string
  createdAt: number
  hasActivity: boolean
}

const STORAGE_KEY = 'arka-terminal-tabs'
const MAX_TABS = 8

interface PersistedTab {
  id: string
  title: string
  sessionId?: string
}

// ─── Module-level singleton state (survives navigation) ──────────────────
const tabs = ref<TerminalTab[]>([])
const activeId = ref<string | null>(null)
const sessions = new Map<string, TerminalSessionHandle>()
const stopWatchers = new Map<string, () => void>()
let _apiBase = ''
let _reattached = false

function loadPersisted(): PersistedTab[] {
  if (typeof localStorage === 'undefined') return []
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function persist() {
  if (typeof localStorage === 'undefined') return
  try {
    const payload: PersistedTab[] = tabs.value.map(t => ({
      id: t.id,
      title: t.title,
      sessionId: sessions.get(t.id)?.meta.value?.session_id
    }))
    localStorage.setItem(STORAGE_KEY, JSON.stringify(payload))
  } catch {
    // quota / private mode — swallow
  }
}

// Light the activity dot on an inactive tab when its session emits output.
function markActivity(id: string) {
  if (activeId.value === id) return
  const t = tabs.value.find(t => t.id === id)
  if (t) t.hasActivity = true
}

// Register a handle: persist again once its backend session_id lands (it
// arrives asynchronously after the WS connects), and flag background tabs
// that produce output. Both subscriptions are torn down in unregister().
function register(id: string, handle: TerminalSessionHandle) {
  sessions.set(id, handle)
  const stopWatch = watch(() => handle.meta.value?.session_id, () => persist())
  const stopOutput = handle.onOutput(() => markActivity(id))
  stopWatchers.set(id, () => {
    stopWatch()
    stopOutput()
  })
}

function unregister(id: string) {
  stopWatchers.get(id)?.()
  stopWatchers.delete(id)
  sessions.delete(id)
}

export function useTerminalTabs() {
  if (!_apiBase) _apiBase = useApi().apiBase
  const capReached = computed(() => tabs.value.length >= MAX_TABS)

  function makeId(): string {
    return Math.random().toString(36).slice(2, 10)
  }

  function sessionFor(id: string): TerminalSessionHandle | undefined {
    return sessions.get(id)
  }

  function newTab(): TerminalTab | null {
    if (tabs.value.length >= MAX_TABS) return null
    const id = makeId()
    register(id, useTerminalSession(_apiBase))
    const tab: TerminalTab = {
      id,
      title: `Session ${tabs.value.length + 1}`,
      createdAt: Date.now(),
      hasActivity: false
    }
    tabs.value.push(tab)
    activeId.value = id
    persist()
    return tab
  }

  async function closeTab(id: string) {
    const idx = tabs.value.findIndex(t => t.id === id)
    if (idx < 0) return
    await sessions.get(id)?.close()
    unregister(id)
    tabs.value.splice(idx, 1)
    if (activeId.value === id) {
      const next = tabs.value[Math.min(idx, tabs.value.length - 1)]
      activeId.value = next ? next.id : null
    }
    persist()
  }

  function switchTab(id: string) {
    const t = tabs.value.find(t => t.id === id)
    if (!t) return
    activeId.value = id
    t.hasActivity = false
  }

  function renameTab(id: string, title: string) {
    const t = tabs.value.find(t => t.id === id)
    if (!t) return
    t.title = title.trim() || t.title
    persist()
  }

  // After a full browser reload the singleton is empty. Reconcile the
  // persisted session IDs against the live backend sessions and reattach
  // the survivors; the WS connect replays their scrollback. Dead IDs are
  // dropped. Runs at most once per page load.
  async function reattachOnLoad() {
    if (_reattached) return
    _reattached = true
    const persisted = loadPersisted()
    if (persisted.length === 0) return
    const alive = new Set<string>()
    try {
      const r = await fetch(`${_apiBase}/api/terminal/sessions`)
      if (!r.ok) return
      const data = await r.json()
      for (const s of data.sessions || []) alive.add(s.session_id)
    } catch {
      return
    }
    const restore = persisted
      .filter(p => p.sessionId && alive.has(p.sessionId))
      .slice(0, MAX_TABS)
    for (const p of restore) {
      const handle = useTerminalSession(_apiBase)
      register(p.id, handle)
      tabs.value.push({
        id: p.id,
        title: p.title,
        createdAt: Date.now(),
        hasActivity: false
      })
      // Sets status to 'connecting' synchronously, so Terminal.vue's
      // auto-open() no-ops and we reuse the live PTY instead of spawning.
      void handle.attach(p.sessionId as string)
    }
    if (tabs.value.length > 0 && !activeId.value) {
      activeId.value = tabs.value[0]!.id
    }
    persist()
  }

  const activeSession = computed(() =>
    activeId.value ? sessions.get(activeId.value) ?? null : null
  )

  return {
    tabs,
    activeId,
    activeSession,
    capReached,
    maxTabs: MAX_TABS,
    sessionFor,
    newTab,
    closeTab,
    switchTab,
    renameTab,
    reattachOnLoad
  }
}
