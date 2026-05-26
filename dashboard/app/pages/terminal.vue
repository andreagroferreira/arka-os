<script setup lang="ts">
// PR99b v3.68.0 — Real-shell terminal (single session).
// PR99c v3.69.0 — Multi-session tabs + browser-local command history.
//
// Each tab owns its own PTY session. PTYs are NOT persisted across
// reloads (they're per-process); only tab titles are. The 8-tab cap
// matches the backend default.

definePageMeta({ layout: 'default' })

const {
  tabs,
  activeId,
  activeTab,
  capReached,
  maxTabs,
  newTab,
  closeTab,
  switchTab,
  renameTab,
} = useTerminalTabs()

const HISTORY_KEY = 'arka-terminal-command-history'
const HISTORY_MAX = 500

interface HistoryEntry {
  ts: number
  cmd: string
}

function loadHistory(): HistoryEntry[] {
  if (typeof localStorage === 'undefined') return []
  try {
    const raw = localStorage.getItem(HISTORY_KEY)
    return raw ? (JSON.parse(raw) as HistoryEntry[]) : []
  } catch {
    return []
  }
}

const history = ref<HistoryEntry[]>(loadHistory())

function recordCommand(cmd: string) {
  const trimmed = cmd.trim()
  if (!trimmed || trimmed.length < 2) return
  history.value.unshift({ ts: Date.now(), cmd: trimmed })
  if (history.value.length > HISTORY_MAX) {
    history.value = history.value.slice(0, HISTORY_MAX)
  }
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(history.value))
  } catch {
    // quota — silently truncate further
    history.value = history.value.slice(0, 200)
  }
}

// PR99d v3.70.0 — theme picker + Ctrl+R history search.
const { themeName, setTheme, options: themeOptions } = useTerminalThemes()
const searchOpen = ref(false)
const searchQuery = ref('')

const searchResults = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return history.value.slice(0, 30)
  return history.value
    .filter((h) => h.cmd.toLowerCase().includes(q))
    .slice(0, 30)
})

function openSearch() {
  searchOpen.value = true
  searchQuery.value = ''
}

function pickFromSearch(cmd: string) {
  activeTab.value?.session.sendInput(cmd)
  searchOpen.value = false
}

const editingTabId = ref<string | null>(null)
const renameDraft = ref('')

function startRename(tabId: string, currentTitle: string) {
  editingTabId.value = tabId
  renameDraft.value = currentTitle
}

function commitRename() {
  if (editingTabId.value) {
    renameTab(editingTabId.value, renameDraft.value)
  }
  editingTabId.value = null
}

const toast = useToast()

function tryNewTab() {
  if (capReached.value) {
    toast.add({
      title: 'Maximum sessions reached',
      description: `You can have up to ${maxTabs} sessions open at once. Close one to open a new one.`,
      color: 'warning',
      icon: 'i-lucide-alert-triangle',
    })
    return
  }
  newTab()
}

// Keyboard shortcuts.
defineShortcuts({
  meta_t: { handler: tryNewTab, usingInput: false },
  meta_w: {
    handler: () => {
      if (activeId.value) closeTab(activeId.value)
    },
    usingInput: false,
  },
  ctrl_r: { handler: openSearch, usingInput: false },
  meta_1: { handler: () => switchByIndex(0), usingInput: false },
  meta_2: { handler: () => switchByIndex(1), usingInput: false },
  meta_3: { handler: () => switchByIndex(2), usingInput: false },
  meta_4: { handler: () => switchByIndex(3), usingInput: false },
  meta_5: { handler: () => switchByIndex(4), usingInput: false },
  meta_6: { handler: () => switchByIndex(5), usingInput: false },
  meta_7: { handler: () => switchByIndex(6), usingInput: false },
  meta_8: { handler: () => switchByIndex(7), usingInput: false },
})

function switchByIndex(idx: number) {
  const t = tabs.value[idx]
  if (t) switchTab(t.id)
}

// First-visit: open one tab automatically.
onMounted(() => {
  if (tabs.value.length === 0) newTab()
})

onBeforeUnmount(async () => {
  // Don't proactively close tabs — operator may navigate back. Backend
  // reaper will GC after the idle timeout (30 min).
})

const showHistory = ref(false)
</script>

<template>
  <UDashboardPanel id="terminal">
    <template #header>
      <UDashboardNavbar title="Terminal">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <div class="flex items-center gap-2">
            <UBadge color="warning" variant="soft" size="sm">
              <UIcon name="i-lucide-shield" class="size-3 mr-1" />
              localhost only
            </UBadge>
            <USelect
              :model-value="themeName"
              :items="themeOptions"
              size="xs"
              class="w-40"
              @update:model-value="setTheme($event as string)"
            />
            <UButton
              size="xs"
              variant="ghost"
              icon="i-lucide-search"
              title="Ctrl+R — search history"
              @click="openSearch"
            >
              ⌃R
            </UButton>
            <UButton
              size="xs"
              variant="ghost"
              :icon="showHistory ? 'i-lucide-x' : 'i-lucide-history'"
              @click="showHistory = !showHistory"
            >
              History ({{ history.length }})
            </UButton>
          </div>
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="flex flex-col gap-3 h-full p-4">
        <p class="text-sm text-muted -mt-1">
          Real PTY shell — run claude, codex, git, anything. ⌘T new · ⌘W close · ⌘1–8 switch · ⌃R search.
        </p>

        <div class="flex items-center gap-1 border-b border-default pb-2 overflow-x-auto">
      <div
        v-for="(tab, idx) in tabs"
        :key="tab.id"
        :class="[
          'group flex items-center gap-1 px-3 py-1.5 rounded-t-md cursor-pointer text-sm shrink-0 border-b-2 transition-colors',
          activeId === tab.id
            ? 'bg-elevated/60 border-primary text-default'
            : 'border-transparent text-muted hover:text-default hover:bg-elevated/30',
        ]"
        @click="switchTab(tab.id)"
        @dblclick="startRename(tab.id, tab.title)"
      >
        <span class="text-xs text-muted">{{ idx + 1 }}</span>
        <UInput
          v-if="editingTabId === tab.id"
          v-model="renameDraft"
          size="xs"
          autofocus
          @keydown.enter="commitRename"
          @keydown.esc="editingTabId = null"
          @blur="commitRename"
        />
        <span v-else>{{ tab.title }}</span>
        <UIcon
          v-if="tab.hasActivity && activeId !== tab.id"
          name="i-lucide-circle"
          class="size-2 text-amber-400 fill-current"
        />
        <button
          class="ml-1 size-4 grid place-items-center rounded text-muted hover:bg-default/50 hover:text-default opacity-0 group-hover:opacity-100"
          @click.stop="closeTab(tab.id)"
        >
          <UIcon name="i-lucide-x" class="size-3" />
        </button>
      </div>
      <UButton
        size="xs"
        variant="ghost"
        icon="i-lucide-plus"
        :disabled="capReached"
        :title="capReached ? `Max ${maxTabs} sessions` : 'New session'"
        @click="tryNewTab"
      >
        New
      </UButton>
    </div>

    <div class="flex-1 min-h-[480px] flex gap-3">
      <div class="flex-1 relative">
        <template v-for="tab in tabs" :key="tab.id">
          <Terminal
            v-show="activeId === tab.id"
            :session="tab.session"
            :on-input-line="recordCommand"
            class="absolute inset-0"
          />
        </template>
        <div
          v-if="tabs.length === 0"
          class="absolute inset-0 grid place-items-center text-muted text-sm"
        >
          No active sessions. Press ⌘T or click "+ New" to open one.
        </div>
      </div>
      <aside
        v-if="showHistory"
        class="w-72 shrink-0 rounded-lg border border-default bg-elevated/10 overflow-hidden flex flex-col"
      >
        <div class="px-3 py-2 border-b border-default text-xs uppercase tracking-wide text-muted">
          Command history
        </div>
        <div class="flex-1 overflow-auto text-xs font-mono">
          <button
            v-for="(entry, i) in history"
            :key="i"
            class="w-full text-left px-3 py-1.5 hover:bg-default/40 truncate"
            :title="entry.cmd"
            @click="activeTab?.session.sendInput(entry.cmd)"
          >
            {{ entry.cmd }}
          </button>
          <div v-if="history.length === 0" class="px-3 py-4 text-muted text-center">
            No commands yet
          </div>
        </div>
      </aside>
    </div>

    <footer class="text-xs text-muted">
      Sessions live on the backend until you close them or 30 min idle.
      History stays in this browser only. Ctrl+R to search history.
    </footer>

    <UModal v-model:open="searchOpen" :title="`Search history (${history.length})`">
      <template #body>
        <div class="space-y-2">
          <UInput
            v-model="searchQuery"
            placeholder="type to filter…"
            autofocus
            icon="i-lucide-search"
            @keydown.enter="searchResults[0] && pickFromSearch(searchResults[0].cmd)"
          />
          <div class="max-h-80 overflow-y-auto rounded-md border border-default divide-y divide-default">
            <button
              v-for="(entry, i) in searchResults"
              :key="i"
              class="w-full text-left px-3 py-2 text-sm font-mono hover:bg-elevated/40 truncate"
              @click="pickFromSearch(entry.cmd)"
            >
              {{ entry.cmd }}
            </button>
            <div v-if="searchResults.length === 0" class="px-3 py-4 text-muted text-center text-sm">
              No matches
            </div>
          </div>
          <p class="text-xs text-muted">
            Enter sends the top match to the active session.
          </p>
        </div>
      </template>
    </UModal>
      </div>
    </template>
  </UDashboardPanel>
</template>
