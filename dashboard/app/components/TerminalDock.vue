<script setup lang="ts">
// v3.71.0 — app-wide terminal dock. Mounted ONCE in the default layout
// (outside <NuxtPage>), so navigating between dashboard pages never
// unmounts it: the PTY WebSocket stays open and the xterm scrollback is
// preserved. Hidden with v-show (not v-if) so toggling the dock keeps
// the terminals mounted. On a full reload, reattachOnLoad() reconnects
// to the still-live backend sessions (which replay their scrollback).
//
// This component owns the command history, search palette, theme picker
// and keyboard shortcuts that used to live in pages/terminal.vue.

import { useTerminalTabs } from '~/composables/useTerminalTabs'
import { useTerminalThemes } from '~/composables/useTerminalThemes'
import { useTerminalDock } from '~/composables/useTerminalDock'

const {
  tabs,
  activeId,
  activeSession,
  capReached,
  maxTabs,
  sessionFor,
  newTab,
  closeTab,
  switchTab,
  renameTab,
  reattachOnLoad
} = useTerminalTabs()

const {
  isOpen,
  isMaximized,
  heightVh,
  open: openDock,
  close: closeDock,
  toggle: toggleDock,
  toggleMaximize,
  setHeight
} = useTerminalDock()

// ─── Command history (browser-local) ─────────────────────────────────────
const HISTORY_KEY = 'arka-terminal-command-history'
const HISTORY_MAX = 500

interface HistoryEntry {
  ts: number
  cmd: string
}

function isPlausibleCommand(cmd: string): boolean {
  if (!cmd || cmd.length < 2) return false
  if (/^\[?\?/.test(cmd)) return false
  if (/\[[\d;?]*[A-Za-z~]/.test(cmd)) return false
  if (/^\[[\dA-Za-z]/.test(cmd)) return false
  if (!/[A-Za-z0-9]/.test(cmd)) return false
  return true
}

function loadHistory(): HistoryEntry[] {
  if (typeof localStorage === 'undefined') return []
  try {
    const parsed = JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]') as HistoryEntry[]
    return parsed.filter(e => e && typeof e.cmd === 'string' && isPlausibleCommand(e.cmd))
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
    history.value = history.value.slice(0, 200)
  }
}

// ─── Theme + search palette ──────────────────────────────────────────────
const { themeName, setTheme, options: themeOptions } = useTerminalThemes()
const searchOpen = ref(false)
const searchQuery = ref('')
const searchSelectedIdx = ref(0)

const searchResults = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return history.value.slice(0, 30)
  return history.value.filter(h => h.cmd.toLowerCase().includes(q)).slice(0, 30)
})

watch(searchResults, () => {
  searchSelectedIdx.value = 0
})

const searchInputEl = ref<HTMLInputElement | null>(null)

function openSearch() {
  searchOpen.value = true
  searchQuery.value = ''
  searchSelectedIdx.value = 0
  nextTick(() => {
    requestAnimationFrame(() => searchInputEl.value?.focus())
  })
}

function pickFromSearch(cmd: string) {
  activeSession.value?.sendInput(cmd)
  searchOpen.value = false
}

const sidebarFilter = ref('')

const visibleHistory = computed(() => {
  const q = sidebarFilter.value.trim().toLowerCase()
  const filtered = history.value.filter(e => isPlausibleCommand(e.cmd))
  if (!q) return filtered
  return filtered.filter(e => e.cmd.toLowerCase().includes(q))
})

function sendToActive(cmd: string) {
  activeSession.value?.sendInput(cmd)
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

// ─── Tab rename ──────────────────────────────────────────────────────────
const editingTabId = ref<string | null>(null)
const renameDraft = ref('')

function startRename(tabId: string, currentTitle: string) {
  editingTabId.value = tabId
  renameDraft.value = currentTitle
}

function commitRename() {
  if (editingTabId.value) renameTab(editingTabId.value, renameDraft.value)
  editingTabId.value = null
}

// ─── New tab + cap toast ─────────────────────────────────────────────────
const toast = useToast()

function tryNewTab() {
  if (capReached.value) {
    toast.add({
      title: 'Maximum sessions reached',
      description: `You can have up to ${maxTabs} sessions open at once. Close one to open a new one.`,
      color: 'warning',
      icon: 'i-lucide-alert-triangle'
    })
    return
  }
  newTab()
}

const showHistory = ref(false)

// ─── Terminal refits (v-show + dock-open need explicit refit) ────────────
const termRefs = ref<Record<string, { refit?: () => void } | null>>({})

function setTermRef(id: string, el: unknown) {
  if (el) termRefs.value[id] = el as { refit?: () => void }
  else termRefs.value[id] = null
}

function refitActive() {
  const id = activeId.value
  if (!id) return
  nextTick(() => {
    requestAnimationFrame(() => termRefs.value[id]?.refit?.())
  })
}

watch([isOpen, isMaximized, heightVh], () => {
  if (isOpen.value) refitActive()
})

// ─── Keep the dock to the RIGHT of the sidebar so the menu stays visible
// and clickable even when the dock is maximized. The sidebar is resizable
// /collapsible, so track its right edge live. Falls back to 0 (full width)
// if the element can't be found.
const dockLeft = ref(0)
let sidebarRO: ResizeObserver | null = null

function trackSidebar() {
  // Nuxt UI renders <UDashboardSidebar id="default"> as the DOM element
  // #dashboard-sidebar-default. It's `hidden` below lg, where its rect
  // collapses to 0 and the dock correctly spans full width.
  const el = document.querySelector('#dashboard-sidebar-default') as HTMLElement | null
  if (!el) return
  const update = () => {
    dockLeft.value = Math.max(0, el.getBoundingClientRect().right)
  }
  update()
  sidebarRO = new ResizeObserver(update)
  sidebarRO.observe(el)
  window.addEventListener('resize', update)
}

// Opening the dock with no sessions spawns the first one. Covers both
// the toggle case (false -> true change) and the already-open-on-mount
// case (persisted state), handled in onMounted below.
function ensureSession() {
  if (isOpen.value && tabs.value.length === 0) newTab()
}

watch(isOpen, ensureSession)

// ─── Resize drag (top edge) ──────────────────────────────────────────────
function startResize(e: PointerEvent) {
  if (isMaximized.value) return
  e.preventDefault()
  const startY = e.clientY
  const startH = heightVh.value
  function onMove(ev: PointerEvent) {
    const dy = startY - ev.clientY
    setHeight(startH + (dy / window.innerHeight) * 100)
  }
  function onUp() {
    window.removeEventListener('pointermove', onMove)
    window.removeEventListener('pointerup', onUp)
  }
  window.addEventListener('pointermove', onMove)
  window.addEventListener('pointerup', onUp)
}

// ─── Keyboard shortcuts ──────────────────────────────────────────────────
function switchByIndex(idx: number) {
  const t = tabs.value[idx]
  if (t) switchTab(t.id)
}

defineShortcuts({
  // Cmd/Ctrl+J toggles the dock from anywhere in the dashboard.
  meta_j: { handler: toggleDock, usingInput: false },
  ctrl_j: { handler: toggleDock, usingInput: false },
  // Session shortcuts only act while the dock is open.
  meta_t: { handler: () => { if (isOpen.value) tryNewTab() }, usingInput: false },
  meta_w: {
    handler: () => {
      if (isOpen.value && activeId.value) closeTab(activeId.value)
    },
    usingInput: false
  },
  ctrl_r: { handler: () => { if (isOpen.value) openSearch() }, usingInput: false },
  meta_1: { handler: () => { if (isOpen.value) switchByIndex(0) }, usingInput: false },
  meta_2: { handler: () => { if (isOpen.value) switchByIndex(1) }, usingInput: false },
  meta_3: { handler: () => { if (isOpen.value) switchByIndex(2) }, usingInput: false },
  meta_4: { handler: () => { if (isOpen.value) switchByIndex(3) }, usingInput: false },
  meta_5: { handler: () => { if (isOpen.value) switchByIndex(4) }, usingInput: false },
  meta_6: { handler: () => { if (isOpen.value) switchByIndex(5) }, usingInput: false },
  meta_7: { handler: () => { if (isOpen.value) switchByIndex(6) }, usingInput: false },
  meta_8: { handler: () => { if (isOpen.value) switchByIndex(7) }, usingInput: false }
})

// Reattach surviving sessions after a reload, then restore the dock if
// it was open (and reveal it whenever sessions came back).
onMounted(async () => {
  trackSidebar()
  await reattachOnLoad()
  if (tabs.value.length > 0) openDock()
  ensureSession()
})

onBeforeUnmount(() => {
  sidebarRO?.disconnect()
})
</script>

<template>
  <div>
    <!-- Floating launcher when the dock is closed. v-if (not v-show)
         because v-show is a directive that doesn't attach to a component
         with a non-element root (UButton). -->
    <UButton
      v-if="!isOpen"
      icon="i-lucide-terminal"
      color="neutral"
      variant="solid"
      class="fixed bottom-4 right-4 z-40 shadow-lg"
      aria-label="Open terminal (Cmd+J)"
      title="Open terminal — ⌘J"
      @click="openDock()"
    >
      Terminal
      <UBadge
        v-if="tabs.length"
        :label="String(tabs.length)"
        size="xs"
        variant="subtle"
      />
    </UButton>

    <!-- The dock. v-show (not v-if) so the xterm instances stay mounted. -->
    <section
      v-show="isOpen"
      class="fixed right-0 bottom-0 z-40 flex flex-col bg-default border-t border-l border-default shadow-2xl"
      :style="{ height: isMaximized ? '94vh' : `${heightVh}vh`, left: `${dockLeft}px` }"
      role="region"
      aria-label="Terminal dock"
    >
      <!-- Resize handle -->
      <div
        class="h-1.5 w-full cursor-row-resize bg-transparent hover:bg-primary/40 shrink-0"
        :class="{ 'pointer-events-none': isMaximized }"
        role="separator"
        aria-orientation="horizontal"
        aria-label="Resize terminal"
        @pointerdown="startResize"
      />

      <!-- Header: tabs + controls -->
      <header class="flex items-center gap-2 px-3 py-1.5 border-b border-default shrink-0">
        <div class="flex items-center gap-1 overflow-x-auto flex-1 min-w-0">
          <div
            v-for="(tab, idx) in tabs"
            :key="tab.id"
            :class="[
              'group flex items-center gap-1 px-3 py-1 rounded-md cursor-pointer text-sm shrink-0 border transition-colors',
              activeId === tab.id
                ? 'bg-elevated/60 border-primary text-default'
                : 'border-transparent text-muted hover:text-default hover:bg-elevated/30'
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
              :aria-label="`Close ${tab.title}`"
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
            aria-label="New terminal session"
            @click="tryNewTab"
          >
            New
          </UButton>
        </div>

        <div class="flex items-center gap-1.5 shrink-0">
          <UBadge
            color="warning"
            variant="soft"
            size="sm"
            class="hidden sm:flex"
          >
            <UIcon name="i-lucide-shield" class="size-3 mr-1" />
            localhost only
          </UBadge>
          <USelect
            :model-value="themeName"
            :items="themeOptions"
            size="xs"
            class="w-36 hidden md:block"
            aria-label="Terminal theme"
            @update:model-value="setTheme($event as string)"
          />
          <UButton
            size="xs"
            variant="ghost"
            icon="i-lucide-search"
            title="Search history — ⌃R"
            aria-label="Search command history"
            @click="openSearch"
          />
          <UButton
            size="xs"
            variant="ghost"
            :icon="showHistory ? 'i-lucide-panel-right-close' : 'i-lucide-history'"
            :title="`History (${history.length})`"
            aria-label="Toggle history panel"
            @click="showHistory = !showHistory"
          />
          <UButton
            size="xs"
            variant="ghost"
            :icon="isMaximized ? 'i-lucide-minimize-2' : 'i-lucide-maximize-2'"
            :title="isMaximized ? 'Restore' : 'Maximize'"
            aria-label="Toggle maximize"
            @click="toggleMaximize"
          />
          <UButton
            size="xs"
            variant="ghost"
            icon="i-lucide-chevron-down"
            title="Close dock — ⌘J"
            aria-label="Close terminal dock"
            @click="closeDock"
          />
        </div>
      </header>

      <!-- Body: terminals + history sidebar -->
      <div class="flex-1 min-h-0 flex gap-2 p-2">
        <div class="flex-1 relative min-w-0">
          <template v-for="tab in tabs" :key="tab.id">
            <Terminal
              v-show="activeId === tab.id"
              :ref="el => setTermRef(tab.id, el)"
              :session="sessionFor(tab.id)"
              :on-input-line="recordCommand"
              :active="activeId === tab.id && isOpen"
              class="absolute inset-0"
            />
          </template>
          <div
            v-if="tabs.length === 0"
            class="absolute inset-0 grid place-items-center text-muted text-sm"
          >
            No active sessions. Press ⌘T or click "+ New".
          </div>
        </div>

        <aside
          v-if="showHistory"
          class="w-72 shrink-0 rounded-lg border border-default bg-elevated/10 overflow-hidden flex flex-col"
        >
          <div class="px-3 py-2 border-b border-default flex items-center gap-2">
            <UIcon name="i-lucide-history" class="size-4 text-muted shrink-0" />
            <span class="text-sm font-semibold">History</span>
            <UBadge :label="String(visibleHistory.length)" size="xs" variant="subtle" />
            <div class="ml-auto flex items-center gap-1">
              <UButton
                v-if="history.length > 0"
                size="xs"
                variant="ghost"
                color="error"
                icon="i-lucide-trash-2"
                title="Clear all"
                aria-label="Clear history"
                @click="clearHistory"
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
              aria-label="Filter history"
            />
          </div>
          <div class="flex-1 overflow-y-auto">
            <div v-if="history.length === 0" class="p-6 text-center text-xs text-muted">
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
            <ul v-else class="py-1">
              <li
                v-for="(entry, i) in visibleHistory"
                :key="`${entry.ts}-${i}`"
                class="group mx-1 px-2.5 py-1 rounded-md cursor-pointer flex items-center gap-2 hover:bg-elevated/40 transition-colors"
                :title="`${entry.cmd} — ${relativeTime(entry.ts)}`"
                @click="sendToActive(entry.cmd)"
              >
                <span class="flex-1 min-w-0 font-mono text-xs truncate">{{ entry.cmd }}</span>
                <span class="text-[10px] text-muted/70 shrink-0 tabular-nums opacity-0 group-hover:opacity-100 transition-opacity">
                  {{ relativeTime(entry.ts) }}
                </span>
                <UIcon
                  name="i-lucide-corner-down-left"
                  class="size-3 shrink-0 text-muted opacity-0 group-hover:opacity-100 transition-opacity"
                />
              </li>
            </ul>
          </div>
        </aside>
      </div>

      <!-- Search palette -->
      <UModal v-model:open="searchOpen" :ui="{ content: 'max-w-2xl ring-0 shadow-2xl' }">
        <template #content>
          <div class="rounded-xl bg-default overflow-hidden">
            <div class="flex items-center gap-3 px-4 py-3 border-b border-default/60">
              <UIcon name="i-lucide-history" class="size-4 text-muted shrink-0" />
              <input
                ref="searchInputEl"
                v-model="searchQuery"
                type="text"
                autofocus
                placeholder="Filter command history…"
                aria-label="Search command history"
                class="palette-input flex-1 bg-transparent text-default placeholder:text-muted/70 focus:outline-none border-0 ring-0 text-sm"
                @keydown="searchKeydown"
              >
              <span class="text-[11px] text-muted/70 shrink-0 tabular-nums">
                {{ searchResults.length }} of {{ history.length }}
              </span>
            </div>
            <div class="max-h-[60vh] overflow-y-auto">
              <div v-if="history.length === 0" class="px-6 py-12 text-center text-sm text-muted">
                <UIcon name="i-lucide-terminal" class="size-7 mx-auto mb-3 opacity-30" />
                <p>No commands yet.</p>
                <p class="text-xs mt-1 opacity-70">
                  Run something in the terminal — it'll show up here.
                </p>
              </div>
              <div
                v-else-if="searchResults.length === 0"
                class="px-6 py-12 text-center text-sm text-muted"
              >
                No match for <span class="font-mono text-default">{{ searchQuery }}</span>.
              </div>
              <ul v-else class="py-1">
                <li
                  v-for="(entry, i) in searchResults"
                  :key="`${entry.ts}-${i}`"
                  class="mx-1 px-3 py-1.5 rounded-md cursor-pointer flex items-center gap-3 transition-colors"
                  :class="i === searchSelectedIdx ? 'bg-elevated/70' : 'hover:bg-elevated/30'"
                  @click="pickFromSearch(entry.cmd)"
                  @mouseenter="searchSelectedIdx = i"
                >
                  <span class="flex-1 min-w-0 font-mono text-sm truncate">{{ entry.cmd }}</span>
                  <span class="text-[11px] text-muted/70 shrink-0 tabular-nums">{{ relativeTime(entry.ts) }}</span>
                  <UIcon
                    name="i-lucide-corner-down-left"
                    class="size-3.5 shrink-0 transition-opacity"
                    :class="i === searchSelectedIdx ? 'text-default opacity-100' : 'text-muted opacity-0'"
                  />
                </li>
              </ul>
            </div>
            <div class="px-4 py-2.5 border-t border-default/60 flex items-center gap-4 text-[11px] text-muted/80">
              <span class="flex items-center gap-1.5"><kbd class="palette-kbd">↑</kbd><kbd class="palette-kbd">↓</kbd> navigate</span>
              <span class="flex items-center gap-1.5"><kbd class="palette-kbd">↵</kbd> send</span>
              <span class="flex items-center gap-1.5"><kbd class="palette-kbd">esc</kbd> close</span>
              <button
                v-if="history.length > 0"
                class="ml-auto text-muted/80 hover:text-red-400 transition-colors flex items-center gap-1"
                @click="clearHistory"
              >
                <UIcon name="i-lucide-trash-2" class="size-3" /> Clear
              </button>
            </div>
          </div>
        </template>
      </UModal>
    </section>
  </div>
</template>

<style scoped>
.palette-input {
  box-shadow: none !important;
  outline: none !important;
}
.palette-input:focus,
.palette-input:focus-visible {
  outline: none !important;
  box-shadow: none !important;
  border-color: transparent !important;
}
.palette-kbd {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 1.1rem;
  padding: 0 0.3rem;
  height: 1.1rem;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 10px;
  line-height: 1;
  border-radius: 4px;
  background-color: rgb(var(--ui-bg-elevated) / 0.5);
  color: rgb(var(--ui-text-muted));
  border: 1px solid rgb(var(--ui-border) / 0.4);
}
</style>
