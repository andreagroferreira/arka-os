import { beforeEach, describe, expect, it } from 'vitest'
import { useActivityFeed } from '../../app/composables/useActivityFeed'

describe('useActivityFeed', () => {
  beforeEach(() => {
    window.localStorage.clear()
    const feed = useActivityFeed()
    feed.clear()
  })

  it('pushes events as unread and derives unreadCount', () => {
    const feed = useActivityFeed()
    feed.push({ kind: 'info', title: 'one' })
    feed.push({ kind: 'success', title: 'two' })

    expect(feed.events.value).toHaveLength(2)
    expect(feed.events.value[0]!.title).toBe('two') // newest first
    expect(feed.events.value[0]!.read).toBe(false)
    expect(feed.unreadCount.value).toBe(2)
  })

  it('caps the feed at 50 events', () => {
    const feed = useActivityFeed()
    for (let i = 0; i < 60; i++) {
      feed.push({ kind: 'info', title: `event-${i}` })
    }
    expect(feed.events.value).toHaveLength(50)
    expect(feed.events.value[0]!.title).toBe('event-59')
    expect(feed.events.value[49]!.title).toBe('event-10')
  })

  it('markRead only updates the targeted event and persists', () => {
    const feed = useActivityFeed()
    feed.push({ kind: 'info', title: 'keep' })
    feed.push({ kind: 'error', title: 'mark me' })
    const target = feed.events.value[0]!
    const other = feed.events.value[1]!

    feed.markRead(target.id)

    expect(feed.events.value[0]!.read).toBe(true)
    expect(feed.events.value[1]!.read).toBe(false)
    expect(feed.unreadCount.value).toBe(1)
    expect(other.id).not.toBe(target.id)

    const stored = JSON.parse(window.localStorage.getItem('arkaos_activity_feed')!)
    expect(stored.find((e: { id: string }) => e.id === target.id).read).toBe(true)
  })

  it('markAllRead and clear reset the unread count', () => {
    const feed = useActivityFeed()
    feed.push({ kind: 'warning', title: 'a' })
    feed.push({ kind: 'info', title: 'b' })

    feed.markAllRead()
    expect(feed.unreadCount.value).toBe(0)

    feed.push({ kind: 'info', title: 'c' })
    expect(feed.unreadCount.value).toBe(1)

    feed.clear()
    expect(feed.events.value).toHaveLength(0)
    expect(window.localStorage.getItem('arkaos_activity_feed')).toBe('[]')
  })

  it('remove drops only the given id', () => {
    const feed = useActivityFeed()
    feed.push({ kind: 'info', title: 'x' })
    feed.push({ kind: 'info', title: 'y' })
    const doomed = feed.events.value[0]!.id

    feed.remove(doomed)

    expect(feed.events.value).toHaveLength(1)
    expect(feed.events.value[0]!.title).toBe('x')
  })
})
