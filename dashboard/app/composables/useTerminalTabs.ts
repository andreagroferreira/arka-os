// PR99c v3.69.0 — multi-session tab manager for /terminal.
//
// Owns an array of `useTerminalSession()` handles plus the active tab
// id. Persists tab titles (not PTYs — those are re-created fresh on
// reload) to localStorage. Enforces an 8-tab cap (matching the backend
// default).

export interface TerminalTab {
  id: string
  title: string
  session: ReturnType<typeof useTerminalSession>
  createdAt: number
  hasActivity: boolean
}

const STORAGE_KEY = 'arka-terminal-tab-titles'
const MAX_TABS = 8

interface PersistedTitle {
  id: string
  title: string
}

function loadPersistedTitles(): Record<string, string> {
  if (typeof localStorage === 'undefined') return {}
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return {}
    const parsed = JSON.parse(raw) as PersistedTitle[]
    return Object.fromEntries(parsed.map(p => [p.id, p.title]))
  } catch {
    return {}
  }
}

function persistTitles(tabs: TerminalTab[]) {
  if (typeof localStorage === 'undefined') return
  try {
    const payload: PersistedTitle[] = tabs.map(t => ({ id: t.id, title: t.title }))
    localStorage.setItem(STORAGE_KEY, JSON.stringify(payload))
  } catch {
    // quota / private mode — swallow
  }
}

export function useTerminalTabs() {
  const { apiBase } = useApi()
  const tabs = ref<TerminalTab[]>([])
  const activeId = ref<string | null>(null)
  const capReached = computed(() => tabs.value.length >= MAX_TABS)

  function makeId(): string {
    return Math.random().toString(36).slice(2, 10)
  }

  function newTab(): TerminalTab | null {
    if (tabs.value.length >= MAX_TABS) return null
    const id = makeId()
    const persistedTitles = loadPersistedTitles()
    const titleFromStorage = persistedTitles[id]
    const tab: TerminalTab = {
      id,
      title: titleFromStorage || `Session ${tabs.value.length + 1}`,
      session: useTerminalSession(apiBase),
      createdAt: Date.now(),
      hasActivity: false,
    }
    tabs.value.push(tab)
    activeId.value = id
    persistTitles(tabs.value)
    return tab
  }

  async function closeTab(id: string) {
    const idx = tabs.value.findIndex(t => t.id === id)
    if (idx < 0) return
    const tab = tabs.value[idx]
    if (!tab) return
    await tab.session.close()
    tabs.value.splice(idx, 1)
    if (activeId.value === id) {
      const next = tabs.value[Math.min(idx, tabs.value.length - 1)]
      activeId.value = next ? next.id : null
    }
    persistTitles(tabs.value)
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
    persistTitles(tabs.value)
  }

  function markActivity(id: string) {
    if (activeId.value === id) return
    const t = tabs.value.find(t => t.id === id)
    if (t) t.hasActivity = true
  }

  async function closeAll() {
    await Promise.all(tabs.value.map(t => t.session.close()))
    tabs.value = []
    activeId.value = null
    persistTitles([])
  }

  const activeTab = computed(() => tabs.value.find(t => t.id === activeId.value) ?? null)

  return {
    tabs,
    activeId,
    activeTab,
    capReached,
    maxTabs: MAX_TABS,
    newTab,
    closeTab,
    switchTab,
    renameTab,
    markActivity,
    closeAll,
  }
}
