// PR92d v3.42.0 — runtime theme color picker.
//
// Stores the operator's preferred primary color in localStorage and
// applies it to the live Nuxt UI app config so every component picks
// up the new hue on next render.

import { createSharedComposable } from '@vueuse/core'

const STORAGE_KEY = 'arkaos_theme_color'

export const THEME_COLOR_OPTIONS = [
  { label: 'Emerald (default)', value: 'emerald' },
  { label: 'Blue', value: 'blue' },
  { label: 'Indigo', value: 'indigo' },
  { label: 'Violet', value: 'violet' },
  { label: 'Rose', value: 'rose' },
  { label: 'Amber', value: 'amber' },
  { label: 'Teal', value: 'teal' },
  { label: 'Cyan', value: 'cyan' },
] as const

export type ThemeColor = (typeof THEME_COLOR_OPTIONS)[number]['value']

const _useThemeColor = () => {
  const appConfig = useAppConfig()
  const current = ref<ThemeColor>('emerald')

  function apply(color: ThemeColor) {
    current.value = color
    if (appConfig.ui?.colors) {
      ;(appConfig.ui.colors as any).primary = color
    }
  }

  function setAndPersist(color: ThemeColor) {
    apply(color)
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(STORAGE_KEY, color)
    }
  }

  function loadFromStorage() {
    if (typeof window === 'undefined') return
    const saved = window.localStorage.getItem(STORAGE_KEY) as ThemeColor | null
    if (saved && THEME_COLOR_OPTIONS.some((o) => o.value === saved)) {
      apply(saved)
    }
  }

  return { current, apply, setAndPersist, loadFromStorage }
}

export const useThemeColor = createSharedComposable(_useThemeColor)
