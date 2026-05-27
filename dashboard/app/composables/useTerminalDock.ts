// v3.71.0 — app-wide terminal dock UI state. Module-level singleton so
// open/maximized/height survive route navigation, and persisted to
// localStorage so the dock restores "as you left it" across a reload.
// The dock itself (TerminalDock.vue) is mounted once in the default
// layout.

const STATE_KEY = 'arka-terminal-dock'

interface DockState {
  open: boolean
  maximized: boolean
  height: number
}

function loadState(): DockState {
  const fallback: DockState = { open: false, maximized: false, height: 45 }
  if (typeof localStorage === 'undefined') return fallback
  try {
    const s = JSON.parse(localStorage.getItem(STATE_KEY) || '{}')
    return {
      open: Boolean(s.open),
      maximized: Boolean(s.maximized),
      height: s.height >= 20 && s.height <= 95 ? s.height : 45
    }
  } catch {
    return fallback
  }
}

const _initial = loadState()
const isOpen = ref(_initial.open)
const isMaximized = ref(_initial.maximized)
const heightVh = ref(_initial.height)

function save() {
  if (typeof localStorage === 'undefined') return
  try {
    localStorage.setItem(
      STATE_KEY,
      JSON.stringify({
        open: isOpen.value,
        maximized: isMaximized.value,
        height: heightVh.value
      })
    )
  } catch {
    // quota / private mode
  }
}

export function useTerminalDock() {
  function open(opts?: { maximized?: boolean }) {
    isOpen.value = true
    if (opts?.maximized) isMaximized.value = true
    save()
  }

  function close() {
    isOpen.value = false
    save()
  }

  function toggle() {
    if (isOpen.value) close()
    else open()
  }

  function toggleMaximize() {
    isMaximized.value = !isMaximized.value
    save()
  }

  function setHeight(vh: number) {
    heightVh.value = Math.min(95, Math.max(20, Math.round(vh)))
    save()
  }

  return {
    isOpen,
    isMaximized,
    heightVh,
    open,
    close,
    toggle,
    toggleMaximize,
    setHeight
  }
}
