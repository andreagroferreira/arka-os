import { beforeEach, describe, expect, it } from 'vitest'
import {
  TERMINAL_THEMES,
  THEME_LABELS,
  useTerminalThemes
} from '../../app/composables/useTerminalThemes'

const REQUIRED_KEYS = [
  'background', 'foreground', 'cursor', 'cursorAccent', 'selectionBackground',
  'black', 'red', 'green', 'yellow', 'blue', 'magenta', 'cyan', 'white',
  'brightBlack', 'brightRed', 'brightGreen', 'brightYellow', 'brightBlue',
  'brightMagenta', 'brightCyan', 'brightWhite'
] as const

const HEX_RE = /^#[0-9a-f]{6}$/i

describe('TERMINAL_THEMES registry', () => {
  it('every theme has the full 22-key xterm shape with hex colors', () => {
    for (const [name, theme] of Object.entries(TERMINAL_THEMES)) {
      for (const key of REQUIRED_KEYS) {
        expect(theme, `${name}.${key}`).toHaveProperty(key)
        expect(
          theme[key as keyof typeof theme],
          `${name}.${key} must be a #rrggbb hex color`
        ).toMatch(HEX_RE)
      }
    }
  })

  it('every theme has a label and every label a theme', () => {
    expect(Object.keys(THEME_LABELS).sort()).toEqual(
      Object.keys(TERMINAL_THEMES).sort()
    )
  })

  it('ships arkaos-dark as the default', () => {
    expect(TERMINAL_THEMES['arkaos-dark']).toBeDefined()
  })
})

describe('useTerminalThemes', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it('setTheme switches the active theme and persists it', () => {
    const { setTheme, activeTheme, themeName } = useTerminalThemes()
    setTheme('dracula')

    expect(themeName.value).toBe('dracula')
    expect(activeTheme.value).toEqual(TERMINAL_THEMES.dracula)
    expect(window.localStorage.getItem('arka-terminal-theme')).toBe('dracula')
  })

  it('setTheme ignores unknown theme names', () => {
    const { setTheme, themeName } = useTerminalThemes()
    const before = themeName.value
    setTheme('does-not-exist')

    expect(themeName.value).toBe(before)
    expect(window.localStorage.getItem('arka-terminal-theme')).not.toBe('does-not-exist')
  })

  it('options exposes value/label pairs for the picker', () => {
    const { options } = useTerminalThemes()
    const values = options.value.map(o => o.value)
    expect(values).toContain('arkaos-dark')
    expect(values).toContain('dracula')
    expect(options.value[0]).toHaveProperty('label')
  })
})
