import { createSharedComposable } from '@vueuse/core'

// PR85c v3.13.0 — extended shortcut map + context-aware `n` + help modal.
const _useDashboard = () => {
  const router = useRouter()
  const route = useRoute()
  const shortcutsHelpOpen = useState('shortcutsHelpOpen', () => false)
  // PR85d v3.14.0 — global search palette state.
  const searchOpen = useState('searchOpen', () => false)

  function contextualNew() {
    const path = route.path
    if (path.startsWith('/agents')) return router.push('/agents/new')
    if (path.startsWith('/personas')) return router.push('/personas/new')
    // Default: go to agents/new (most common new-thing action)
    return router.push('/agents/new')
  }

  defineShortcuts({
    'g-h': () => router.push('/'),
    'g-a': () => router.push('/agents'),
    'g-p': () => router.push('/personas'),
    'g-c': () => router.push('/commands'),
    'g-b': () => router.push('/budget'),
    'g-t': () => router.push('/tasks'),
    'g-k': () => router.push('/knowledge'),
    'g-e': () => router.push('/health'),
    'g-s': () => router.push('/settings'),
    'g-r': () => router.push('/trash'),
    'n': () => contextualNew(),
    '?': () => { shortcutsHelpOpen.value = !shortcutsHelpOpen.value },
    '/': () => { searchOpen.value = true },
    'meta_k': () => { searchOpen.value = true }
  })

  return { shortcutsHelpOpen, searchOpen }
}

export const useDashboard = createSharedComposable(_useDashboard)
