<script setup lang="ts">
// PR99b v3.68.0 — Real-shell terminal (single session).
// PR99c v3.69.0 — Multi-session tabs + browser-local command history.
// v3.70.2 — explicit composable imports (auto-import was missing the
// newly added useTerminalThemes on dev servers that didn't restart).

import { useTerminalTabs } from '~/composables/useTerminalTabs'
import { useTerminalThemes } from '~/composables/useTerminalThemes'

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

// v3.70.3 — sanitise legacy entries polluted by ANSI ESC sequences
// that leaked through the v3.69.0 line-buffer before the proper
// state-machine filter landed.
function isPlausibleCommand(cmd: string): boolean {
  if (!cmd || cmd.length < 2) return false
  // Reject anything that looks like a CSI/SS3 remnant
  if (/^\[?\?/.test(cmd)) return false
  if (/\[[\d;?]*[A-Za-z~]/.test(cmd)) return false
  // Reject anything starting with `[` followed by digits or letter — ESC remnant
  if (/^\[[\dA-Za-z]/.test(cmd)) return false
  // Must contain at least one alphanumeric — pure punctuation is suspect
  if (!/[A-Za-z0-9]/.test(cmd)) return false
  return true
}

function loadHistory(): HistoryEntry[] {
  if (typeof localStorage === 'undefined') return []
  try {
    const raw = localStorage.getItem(HISTORY_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw) as HistoryEntry[]
    return parsed.filter((e) => e && typeof e.cmd === 'string' && isPlausibleCommand(e.cmd))
  } catch {
    return []
  }
}

const history = ref<HistoryEntry[]>(loadHistory())

function clearHistory() {
  history.value = []
  try {
    localStorage.removeItem(HISTORY_KEY)
  } catch {
    // ignore
  }
}

function recordCommand(cmd: string) {
  const trimmed = cmd.trim()
  if (!isPlausibleCommand(trimmed)) return
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
// v3.70.3 — proper command palette UX (keyboard nav, selected row).
const { themeName, setTheme, options: themeOptions } = useTerminalThemes()
const searchOpen = ref(false)
const searchQuery = ref('')
const searchSelectedIdx = ref(0)

const searchResults = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return history.value.slice(0, 30)
  return history.value
    .filter((h) => h.cmd.toLowerCase().includes(q))
    .slice(0, 30)
})

watch(searchResults, () => {
  searchSelectedIdx.value = 0
})

function openSearch() {
  searchOpen.value = true
  searchQuery.value = ''
  searchSelectedIdx.value = 0
}

function pickFromSearch(cmd: string) {
  activeTab.value?.session.sendInput(cmd)
  searchOpen.value = false
}

// v3.70.4 — inline filter for the side panel.
const sidebarFilter = ref('')

const visibleHistory = computed(() => {
  const q = sidebarFilter.value.trim().toLowerCase()
  const filtered = history.value.filter((e) => isPlausibleCommand(e.cmd))
  if (!q) return filtered
  return filtered.filter((e) => e.cmd.toLowerCase().includes(q))
})

function sendToActive(cmd: string) {
  activeTab.value?.session.sendInput(cmd)
}

function searchKeydown(e: KeyboardEvent) {
  const total = searchResults.value.length
  if (total === 0) return
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    searchSelectedIdx.value = (searchSelectedIdx.value + 1) % total
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    searchSelectedIdx.value = (searchSelectedIdx.value - 1 + total) % total
  } else if (e.key === 'Enter') {
    e.preventDefault()
    const chosen = searchResults.value[searchSelectedIdx.value]
    if (chosen) pickFromSearch(chosen.cmd)
  }
}

function relativeTime(ts: number): string {
  const diff = (Date.now() - ts) / 1000
  if (diff < 60) return 'just now'
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
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
        class="w-80 shrink-0 rounded-lg border border-default bg-elevated/10 overflow-hidden flex flex-col"
      >
        <div class="px-3 py-2.5 border-b border-default flex items-center gap-2">
          <UIcon name="i-lucide-history" class="size-4 text-muted shrink-0" />
          <span class="text-sm font-semibold">History</span>
          <UBadge :label="String(visibleHistory.length)" size="xs" variant="subtle" />
          <div class="ml-auto flex items-center gap-1">
            <UButton
              size="xs"
              variant="ghost"
              icon="i-lucide-search"
              title="Open full search (⌃R)"
              @click="openSearch"
            />
            <UButton
              v-if="history.length > 0"
              size="xs"
              variant="ghost"
              color="error"
              icon="i-lucide-trash-2"
              title="Clear all"
              @click="clearHistory"
            />
            <UButton
              size="xs"
              variant="ghost"
              icon="i-lucide-x"
              title="Close panel"
              @click="showHistory = false"
            />
          </div>
        </div>

        <div class="px-3 py-2 border-b border-default">
          <UInput
            v-model="sidebarFilter"
            size="xs"
            placeholder="Filter…"
            icon="i-lucide-search"
            class="w-full"
          />
        </div>

        <div class="flex-1 overflow-y-auto">
          <div
            v-if="history.length === 0"
            class="p-6 text-center text-xs text-muted"
          >
            <UIcon name="i-lucide-terminal" class="size-6 mx-auto mb-2 opacity-50" />
            <p>No commands yet.</p>
          </div>
          <div
            v-else-if="visibleHistory.length === 0"
            class="p-6 text-center text-xs text-muted"
          >
            No matches for
            <span class="font-mono text-default">{{ sidebarFilter }}</span>.
          </div>
          <ul v-else class="divide-y divide-default">
            <li
              v-for="entry in visibleHistory"
              :key="entry.ts"
              class="group px-3 py-1.5 hover:bg-elevated/40 cursor-pointer flex items-center gap-2"
              :title="`${entry.cmd} — ${relativeTime(entry.ts)}`"
              @click="sendToActive(entry.cmd)"
            >
              <UIcon
                name="i-lucide-chevron-right"
                class="size-3 shrink-0 text-muted group-hover:text-primary"
              />
              <span class="flex-1 min-w-0 font-mono text-xs truncate">
                {{ entry.cmd }}
              </span>
              <span class="text-[10px] text-muted shrink-0 tabular-nums opacity-0 group-hover:opacity-100 transition-opacity">
                {{ relativeTime(entry.ts) }}
              </span>
              <UIcon
                name="i-lucide-corner-down-left"
                class="size-3 shrink-0 text-muted opacity-0 group-hover:opacity-100 transition-opacity"
              />
            </li>
          </ul>
        </div>

        <div class="px-3 py-2 border-t border-default text-[10px] text-muted">
          Click a command to send it to the active session.
        </div>
      </aside>
    </div>

    <footer class="text-xs text-muted">
      Sessions live on the backend until you close them or 30 min idle.
      History stays in this browser only. Ctrl+R to search history.
    </footer>

    <UModal
      v-model:open="searchOpen"
      :ui="{ content: 'max-w-2xl' }"
    >
      <template #content>
        <UCard :ui="{ body: 'p-0', header: 'px-4 py-3', footer: 'px-4 py-2.5' }">
          <template #header>
            <div class="flex items-center gap-3">
              <UIcon name="i-lucide-history" class="size-5 text-muted shrink-0" />
              <UInput
                v-model="searchQuery"
                placeholder="Filter command history…"
                size="lg"
                autofocus
                :ui="{ root: 'flex-1', base: 'border-0 shadow-none ring-0 focus:ring-0 px-0' }"
                @keydown="searchKeydown"
              />
              <span class="text-xs text-muted shrink-0 tabular-nums">
                {{ searchResults.length }} / {{ history.length }}
              </span>
              <kbd class="px-1.5 py-0.5 rounded bg-elevated/50 text-xs font-mono text-muted shrink-0">
                esc
              </kbd>
            </div>
          </template>

          <div class="max-h-[60vh] overflow-y-auto">
            <div
              v-if="history.length === 0"
              class="p-10 text-center text-sm text-muted"
            >
              <UIcon name="i-lucide-terminal" class="size-8 mx-auto mb-3 opacity-50" />
              <p>No commands yet.</p>
              <p class="text-xs mt-1">
                Run something in the terminal — it'll show up here.
              </p>
            </div>
            <div
              v-else-if="searchResults.length === 0"
              class="p-10 text-center text-sm text-muted"
            >
              No match for
              <span class="font-mono text-default">{{ searchQuery }}</span>.
            </div>
            <ul v-else class="divide-y divide-default">
              <li
                v-for="(entry, i) in searchResults"
                :key="entry.ts"
                class="px-4 py-2 cursor-pointer transition-colors flex items-center gap-3"
                :class="i === searchSelectedIdx
                  ? 'bg-primary/10 border-l-2 border-primary pl-[14px]'
                  : 'hover:bg-elevated/40 border-l-2 border-transparent'"
                @click="pickFromSearch(entry.cmd)"
                @mouseenter="searchSelectedIdx = i"
              >
                <UIcon
                  name="i-lucide-chevron-right"
                  class="size-3.5 shrink-0"
                  :class="i === searchSelectedIdx ? 'text-primary' : 'text-muted'"
                />
                <span class="flex-1 min-w-0 font-mono text-sm truncate">
                  {{ entry.cmd }}
                </span>
                <span class="text-xs text-muted shrink-0 tabular-nums">
                  {{ relativeTime(entry.ts) }}
                </span>
                <kbd
                  v-if="i === searchSelectedIdx"
                  class="px-1.5 py-0.5 rounded bg-primary/20 text-[10px] font-mono text-primary shrink-0"
                >
                  ↵ send
                </kbd>
              </li>
            </ul>
          </div>

          <template #footer>
            <div class="text-xs text-muted flex items-center gap-4">
              <span class="flex items-center gap-1">
                <kbd class="px-1.5 py-0.5 rounded bg-elevated/50 font-mono">↑</kbd>
                <kbd class="px-1.5 py-0.5 rounded bg-elevated/50 font-mono">↓</kbd>
                navigate
              </span>
              <span class="flex items-center gap-1">
                <kbd class="px-1.5 py-0.5 rounded bg-elevated/50 font-mono">↵</kbd>
                send to active session
              </span>
              <span class="flex items-center gap-1">
                <kbd class="px-1.5 py-0.5 rounded bg-elevated/50 font-mono">esc</kbd>
                close
              </span>
              <UButton
                v-if="history.length > 0"
                size="xs"
                variant="ghost"
                color="error"
                icon="i-lucide-trash-2"
                class="ml-auto"
                @click="clearHistory"
              >
                Clear all
              </UButton>
            </div>
          </template>
        </UCard>
      </template>
    </UModal>
      </div>
    </template>
  </UDashboardPanel>
</template>
