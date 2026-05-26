// PR99d v3.70.0 — theme presets for xterm.js.
//
// Stored as plain xterm.js ITheme objects. The active theme name lives
// in localStorage so it survives reloads. ArkaOS Dark is the default
// and is tuned to the dashboard's primary color.

export interface XtermTheme {
  background: string
  foreground: string
  cursor: string
  cursorAccent: string
  selectionBackground: string
  black: string
  red: string
  green: string
  yellow: string
  blue: string
  magenta: string
  cyan: string
  white: string
  brightBlack: string
  brightRed: string
  brightGreen: string
  brightYellow: string
  brightBlue: string
  brightMagenta: string
  brightCyan: string
  brightWhite: string
}

export const TERMINAL_THEMES: Record<string, XtermTheme> = {
  'arkaos-dark': {
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
  },
  dracula: {
    background: '#282a36',
    foreground: '#f8f8f2',
    cursor: '#f8f8f2',
    cursorAccent: '#282a36',
    selectionBackground: '#44475a',
    black: '#21222c',
    red: '#ff5555',
    green: '#50fa7b',
    yellow: '#f1fa8c',
    blue: '#bd93f9',
    magenta: '#ff79c6',
    cyan: '#8be9fd',
    white: '#f8f8f2',
    brightBlack: '#6272a4',
    brightRed: '#ff6e6e',
    brightGreen: '#69ff94',
    brightYellow: '#ffffa5',
    brightBlue: '#d6acff',
    brightMagenta: '#ff92df',
    brightCyan: '#a4ffff',
    brightWhite: '#ffffff',
  },
  'solarized-dark': {
    background: '#002b36',
    foreground: '#839496',
    cursor: '#93a1a1',
    cursorAccent: '#002b36',
    selectionBackground: '#073642',
    black: '#073642',
    red: '#dc322f',
    green: '#859900',
    yellow: '#b58900',
    blue: '#268bd2',
    magenta: '#d33682',
    cyan: '#2aa198',
    white: '#eee8d5',
    brightBlack: '#586e75',
    brightRed: '#cb4b16',
    brightGreen: '#586e75',
    brightYellow: '#657b83',
    brightBlue: '#839496',
    brightMagenta: '#6c71c4',
    brightCyan: '#93a1a1',
    brightWhite: '#fdf6e3',
  },
  'solarized-light': {
    background: '#fdf6e3',
    foreground: '#657b83',
    cursor: '#586e75',
    cursorAccent: '#fdf6e3',
    selectionBackground: '#eee8d5',
    black: '#073642',
    red: '#dc322f',
    green: '#859900',
    yellow: '#b58900',
    blue: '#268bd2',
    magenta: '#d33682',
    cyan: '#2aa198',
    white: '#eee8d5',
    brightBlack: '#002b36',
    brightRed: '#cb4b16',
    brightGreen: '#586e75',
    brightYellow: '#657b83',
    brightBlue: '#839496',
    brightMagenta: '#6c71c4',
    brightCyan: '#93a1a1',
    brightWhite: '#fdf6e3',
  },
  nord: {
    background: '#2e3440',
    foreground: '#d8dee9',
    cursor: '#d8dee9',
    cursorAccent: '#2e3440',
    selectionBackground: '#434c5e',
    black: '#3b4252',
    red: '#bf616a',
    green: '#a3be8c',
    yellow: '#ebcb8b',
    blue: '#81a1c1',
    magenta: '#b48ead',
    cyan: '#88c0d0',
    white: '#e5e9f0',
    brightBlack: '#4c566a',
    brightRed: '#bf616a',
    brightGreen: '#a3be8c',
    brightYellow: '#ebcb8b',
    brightBlue: '#81a1c1',
    brightMagenta: '#b48ead',
    brightCyan: '#8fbcbb',
    brightWhite: '#eceff4',
  },
}

export const THEME_LABELS: Record<string, string> = {
  'arkaos-dark': 'ArkaOS Dark',
  dracula: 'Dracula',
  'solarized-dark': 'Solarized Dark',
  'solarized-light': 'Solarized Light',
  nord: 'Nord',
}

const STORAGE_KEY = 'arka-terminal-theme'
const DEFAULT_THEME = 'arkaos-dark'

export function useTerminalThemes() {
  const themeName = useState<string>('terminal-theme', () => {
    if (typeof localStorage === 'undefined') return DEFAULT_THEME
    return localStorage.getItem(STORAGE_KEY) || DEFAULT_THEME
  })

  function setTheme(name: string) {
    if (!TERMINAL_THEMES[name]) return
    themeName.value = name
    try {
      localStorage.setItem(STORAGE_KEY, name)
    } catch {
      // ignore quota
    }
  }

  const activeTheme = computed<XtermTheme>(
    () => TERMINAL_THEMES[themeName.value] ?? TERMINAL_THEMES[DEFAULT_THEME]!,
  )

  const options = computed(() =>
    Object.entries(THEME_LABELS).map(([value, label]) => ({ value, label })),
  )

  return {
    themeName,
    activeTheme,
    setTheme,
    options,
  }
}
