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
import { useTerminalThemes, type XtermTheme } from '~/composables/useTerminalThemes'
import { useTerminalSession } from '~/composables/useTerminalSession'

interface Props {
  session?: ReturnType<typeof useTerminalSession>
  onInputLine?: (line: string) => void
  theme?: XtermTheme
}
const props = defineProps<Props>()

const container = ref<HTMLDivElement | null>(null)
const session = props.session ?? useTerminalSession()
const term = shallowRef<XTerm | null>(null)
const fit = shallowRef<FitAddon | null>(null)
const search = shallowRef<SearchAddon | null>(null)

const decoder = new TextDecoder('utf-8', { fatal: false })

// PR99d v3.70.0 — theme comes from prop or from the composable
// default (operator's choice stored in localStorage).
const { activeTheme } = useTerminalThemes()
const effectiveTheme = computed(() => props.theme ?? activeTheme.value)

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
    theme: effectiveTheme.value,
    allowProposedApi: true,
  })

  // React to theme switches without remounting.
  watch(effectiveTheme, (next) => {
    if (term.value) term.value.options.theme = next
  }, { deep: true })
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
  // side audit. Captures only printable chars up to Enter.
  // v3.70.3 — proper ANSI ESC-sequence skipper so arrow keys / cursor
  // queries / function keys never leak into the history. The state
  // machine handles `\x1b[...<final>` (CSI) and `\x1bO<char>` (SS3).
  let lineBuf = ''
  let escState: 'none' | 'esc' | 'csi' | 'ss3' = 'none'
  t.onData((data) => {
    for (const ch of data) {
      if (escState === 'esc') {
        if (ch === '[') escState = 'csi'
        else if (ch === 'O') escState = 'ss3'
        else escState = 'none' // unknown ESC sequence, drop just this byte
        continue
      }
      if (escState === 'csi') {
        // Final byte of a CSI is in 0x40-0x7E (@A..Z[\]^_`a..z{|}~)
        if (ch >= '@' && ch <= '~') escState = 'none'
        continue
      }
      if (escState === 'ss3') {
        // SS3 is ESC O <one-char>
        escState = 'none'
        continue
      }
      if (ch === '\x1b') {
        escState = 'esc'
        continue
      }
      if (ch === '\r' || ch === '\n') {
        const cmd = lineBuf.trim()
        if (cmd) props.onInputLine?.(cmd)
        lineBuf = ''
        continue
      }
      if (ch === '\x7f' || ch === '\b') {
        lineBuf = lineBuf.slice(0, -1)
        continue
      }
      if (ch === '\x03' || ch === '\x15') {
        // Ctrl-C or Ctrl-U — operator abandoned the line
        lineBuf = ''
        continue
      }
      if (ch >= ' ' && ch <= '~') {
        lineBuf += ch
      }
      // any other control byte is silently dropped
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
