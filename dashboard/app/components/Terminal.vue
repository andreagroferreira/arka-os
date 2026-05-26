<script setup lang="ts">
// PR99b v3.68.0 — xterm.js terminal mount.
// PR99c v3.69.0 — accepts an external session via prop so the tab
// manager in /terminal can mount N instances, each bound to its own
// PTY session.

import { Terminal as XTerm } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import { WebLinksAddon } from '@xterm/addon-web-links'
import { SearchAddon } from '@xterm/addon-search'
import '@xterm/xterm/css/xterm.css'

interface Props {
  session?: ReturnType<typeof useTerminalSession>
  onInputLine?: (line: string) => void
}
const props = defineProps<Props>()

const container = ref<HTMLDivElement | null>(null)
const session = props.session ?? useTerminalSession()
const term = shallowRef<XTerm | null>(null)
const fit = shallowRef<FitAddon | null>(null)
const search = shallowRef<SearchAddon | null>(null)

const decoder = new TextDecoder('utf-8', { fatal: false })

const themeArkaOSDark = {
  background: '#0a0a0f',
  foreground: '#e6e6f0',
  cursor: '#7dd3fc',
  cursorAccent: '#0a0a0f',
  selectionBackground: '#1e3a5f',
  black: '#0a0a0f',
  red: '#f87171',
  green: '#86efac',
  yellow: '#fde68a',
  blue: '#7dd3fc',
  magenta: '#f0abfc',
  cyan: '#67e8f9',
  white: '#e6e6f0',
  brightBlack: '#3f3f46',
  brightRed: '#fca5a5',
  brightGreen: '#bbf7d0',
  brightYellow: '#fef3c7',
  brightBlue: '#bae6fd',
  brightMagenta: '#f5d0fe',
  brightCyan: '#a5f3fc',
  brightWhite: '#fafafa',
}

let unsubscribeOutput: (() => void) | null = null
let resizeObserver: ResizeObserver | null = null

onMounted(async () => {
  if (!container.value) return

  const t = new XTerm({
    cursorBlink: true,
    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
    fontSize: 13,
    lineHeight: 1.2,
    scrollback: 5000,
    theme: themeArkaOSDark,
    allowProposedApi: true,
  })
  const fitAddon = new FitAddon()
  const searchAddon = new SearchAddon()
  t.loadAddon(fitAddon)
  t.loadAddon(new WebLinksAddon())
  t.loadAddon(searchAddon)
  t.open(container.value)
  fitAddon.fit()

  term.value = t
  fit.value = fitAddon
  search.value = searchAddon

  await session.open()

  unsubscribeOutput = session.onOutput((chunk) => {
    const text = decoder.decode(chunk, { stream: true })
    t.write(text)
  })

  // PR99c v3.69.0 — line-buffer for command history without server-
  // side audit. Captures only printable chars up to Enter; ignores
  // arrow keys, ctrl combos, escape sequences.
  let lineBuf = ''
  t.onData((data) => {
    for (const ch of data) {
      if (ch === '\r' || ch === '\n') {
        const cmd = lineBuf.trim()
        if (cmd) props.onInputLine?.(cmd)
        lineBuf = ''
      } else if (ch === '\x7f' || ch === '\b') {
        lineBuf = lineBuf.slice(0, -1)
      } else if (ch >= ' ' && ch < '\x7f') {
        lineBuf += ch
      }
    }
    session.sendInput(data)
  })

  // Initial size sync once the WS is open.
  watch(session.status, (s) => {
    if (s === 'open') {
      const { cols, rows } = t
      session.sendResize(cols, rows)
    }
  }, { immediate: true })

  resizeObserver = new ResizeObserver(() => {
    try {
      fitAddon.fit()
      session.sendResize(t.cols, t.rows)
    } catch (_e) {
      // dom may have unmounted
    }
  })
  resizeObserver.observe(container.value)
})

onBeforeUnmount(async () => {
  unsubscribeOutput?.()
  resizeObserver?.disconnect()
  // PR99c: only close the session if we created it. When the parent
  // owns the session (props.session), parent is responsible for close.
  if (!props.session) {
    await session.close()
  }
  term.value?.dispose()
})

defineExpose({
  status: session.status,
  error: session.error,
  meta: session.meta,
})
</script>

<template>
  <div class="relative h-full w-full bg-[#0a0a0f] rounded-lg overflow-hidden border border-default">
    <div
      v-if="session.status.value === 'connecting'"
      class="absolute inset-0 z-10 grid place-items-center text-muted text-sm bg-[#0a0a0f]/80 backdrop-blur"
    >
      <div class="flex items-center gap-2">
        <UIcon name="i-lucide-loader" class="animate-spin size-4" />
        Spawning PTY…
      </div>
    </div>
    <div
      v-else-if="session.status.value === 'error' || session.status.value === 'closed'"
      class="absolute top-2 right-2 z-10 text-xs rounded-md bg-elevated/90 px-2 py-1 border border-default"
    >
      <span v-if="session.status.value === 'error'" class="text-red-400">
        {{ session.error.value || 'error' }}
      </span>
      <span v-else class="text-muted">closed</span>
    </div>
    <div ref="container" class="absolute inset-0 p-2" />
  </div>
</template>

<style scoped>
:deep(.xterm) {
  height: 100%;
  width: 100%;
  padding: 4px;
}
:deep(.xterm-viewport) {
  background-color: transparent !important;
}
</style>
