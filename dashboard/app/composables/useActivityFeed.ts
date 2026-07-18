// PR93d v3.46.0 — client-side activity feed.
//
// Persistence: localStorage `arkaos_activity_feed` (last 50 events).
// Events are pushed by `push()` from anywhere in the app. The
// NotificationsBell component reads + clears.

import { createSharedComposable } from '@vueuse/core'

export interface ActivityEvent {
  id: string
  ts: string // ISO
  kind: 'success' | 'warning' | 'error' | 'info'
  title: string
  description?: string
  to?: string
  read?: boolean
}

const STORAGE_KEY = 'arkaos_activity_feed'
const MAX_EVENTS = 50

const _useActivityFeed = () => {
  const events = useState<ActivityEvent[]>('activityFeed', () => [])
  const loaded = useState<boolean>('activityFeedLoaded', () => false)
  // PR94a v3.47.0 — unread count is now derived from `read: false`.
  const unreadCount = computed(
    () => events.value.filter(e => !e.read).length
  )

  function _persist() {
    if (typeof window === 'undefined') return
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(events.value))
    } catch {
      // Storage full or disabled — silently drop persistence.
    }
  }

  function load() {
    if (loaded.value || typeof window === 'undefined') return
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY)
      if (raw) {
        const parsed = JSON.parse(raw)
        if (Array.isArray(parsed)) {
          events.value = parsed.slice(0, MAX_EVENTS)
        }
      }
    } catch {
      events.value = []
    }
    loaded.value = true
  }

  function push(entry: Omit<ActivityEvent, 'id' | 'ts' | 'read'>) {
    load()
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
    const ts = new Date().toISOString()
    // PR94a — every new event starts unread.
    events.value = [{ id, ts, read: false, ...entry }, ...events.value].slice(0, MAX_EVENTS)
    _persist()
  }

  function markRead(id: string) {
    let changed = false
    events.value = events.value.map((e) => {
      if (e.id === id && !e.read) {
        changed = true
        return { ...e, read: true }
      }
      return e
    })
    if (changed) _persist()
  }

  function markAllRead() {
    let changed = false
    events.value = events.value.map((e) => {
      if (!e.read) {
        changed = true
        return { ...e, read: true }
      }
      return e
    })
    if (changed) _persist()
  }

  function clear() {
    events.value = []
    _persist()
  }

  function remove(id: string) {
    events.value = events.value.filter(e => e.id !== id)
    _persist()
  }

  return { events, unreadCount, load, push, clear, remove, markRead, markAllRead }
}

export const useActivityFeed = createSharedComposable(_useActivityFeed)
