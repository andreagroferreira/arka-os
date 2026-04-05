import { createSharedComposable } from '@vueuse/core'

const _useDashboard = () => {
  const router = useRouter()

  defineShortcuts({
    'g-h': () => router.push('/'),
    'g-a': () => router.push('/agents'),
    'g-c': () => router.push('/commands'),
    'g-b': () => router.push('/budget'),
    'g-t': () => router.push('/tasks'),
    'g-k': () => router.push('/knowledge'),
    'g-e': () => router.push('/health')
  })

  return {}
}

export const useDashboard = createSharedComposable(_useDashboard)
