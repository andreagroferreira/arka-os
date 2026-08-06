// PR430 regression suite — the empty-path guard in `useApi` must never cost
// the reactivity of the useFetch cache key.
//
// Nuxt derives the asyncData key from the request URL, but only tracks it
// reactively when `watch` is left alone: fetch.js:106 passes `key.value`
// (a frozen string) instead of `key` (the computed) as soon as `watch: false`
// is set. Two fetches that both start on an empty path then share one
// asyncData entry forever — the compare pages render the same record twice —
// and the pages that pass a reactive `query` stop refetching.
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { defineComponent, h, nextTick, ref, computed, type Ref } from 'vue'

const API_BASE = 'http://localhost:3334'

interface Tagged { tag: string }

let calls: Array<{ url: string, options: Record<string, unknown> }>
let transport: ReturnType<typeof vi.fn>

beforeEach(() => {
  calls = []
  transport = vi.fn((url: string, options: Record<string, unknown> = {}) => {
    calls.push({ url, options })
    return Promise.resolve({ tag: url.split('/').pop() })
  })
  vi.stubGlobal('$fetch', transport)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

const urls = () => calls.map(c => c.url)

/** Two independent fetches whose paths start empty — the compare-page shape. */
function twoColumnProbe() {
  const idA = ref('')
  const idB = ref('')
  const probe: Record<string, unknown> = {}

  const Probe = defineComponent({
    setup() {
      const { fetchApi } = useApi()
      probe.a = fetchApi<Tagged>(() => idA.value ? `/api/agents/${idA.value}` : '')
      probe.b = fetchApi<Tagged>(() => idB.value ? `/api/agents/${idB.value}` : '')
      return () => h('div')
    }
  })

  return { Probe, idA, idB, probe }
}

/** A single fetch driven by an externally supplied path ref + options. */
function singleProbe(path: Ref<string>, opts?: Record<string, unknown>) {
  const probe: Record<string, unknown> = {}
  const Probe = defineComponent({
    setup() {
      const { fetchApi } = useApi()
      probe.one = fetchApi<Tagged>(() => path.value, opts)
      return () => h('div')
    }
  })
  return { Probe, probe }
}

async function settle(ticks = 4) {
  for (let i = 0; i < ticks; i++) {
    await nextTick()
    await Promise.resolve()
  }
}

describe('useApi — empty-path guard', () => {
  it('fires no request while the path is empty', async () => {
    const path = ref('')
    const { Probe } = singleProbe(path)

    await mountSuspended(Probe)
    await settle()

    expect(transport).not.toHaveBeenCalled()
    // Specifically: never the bare API root, which is what an empty path
    // collapses to once concatenated with apiBase.
    expect(urls()).not.toContain(API_BASE)
    expect(urls()).not.toContain(`${API_BASE}/`)
  })

  it('stops requesting again when a resolved path is cleared back to empty', async () => {
    const path = ref('/api/agents/solo')
    const { Probe } = singleProbe(path)

    await mountSuspended(Probe)
    await settle()
    expect(urls()).toEqual([`${API_BASE}/api/agents/solo`])

    path.value = ''
    await settle()

    expect(urls()).toEqual([`${API_BASE}/api/agents/solo`])
  })
})

describe('useApi — the transport wrapper stays transparent', () => {
  it('delegates to a caller-supplied $fetch instead of replacing it', async () => {
    // The wrapper owns the empty-path decision only; a caller that brings its
    // own transport (an interceptor, a test double) must still be the one
    // that performs the request.
    const callerFetch = vi.fn(() => Promise.resolve({ tag: 'from-caller' }))
    const path = ref('/api/agents/delegated')
    const { Probe, probe } = singleProbe(path, { $fetch: callerFetch })

    await mountSuspended(Probe)
    await settle()

    const one = probe.one as { data: Ref<Tagged | undefined> }
    expect(callerFetch).toHaveBeenCalledTimes(1)
    expect(callerFetch.mock.calls[0]![0]).toBe(`${API_BASE}/api/agents/delegated`)
    expect(one.data.value).toEqual({ tag: 'from-caller' })
    // The default transport must not have been used behind its back.
    expect(transport).not.toHaveBeenCalled()
  })

  it('still guards the empty path for a caller-supplied $fetch', async () => {
    const callerFetch = vi.fn(() => Promise.resolve({ tag: 'never' }))
    const path = ref('')
    const { Probe } = singleProbe(path, { $fetch: callerFetch })

    await mountSuspended(Probe)
    await settle()

    expect(callerFetch).not.toHaveBeenCalled()
  })

  it('propagates transport rejections instead of swallowing them', async () => {
    // A guard that returned a resolved value on failure would turn every 500
    // into a silent empty page — the pages branch on `error`.
    const boom = new Error('upstream exploded')
    transport.mockImplementationOnce(() => Promise.reject(boom))
    const path = ref('/api/agents/failing')
    const { Probe, probe } = singleProbe(path)

    await mountSuspended(Probe)
    await settle()

    const one = probe.one as {
      error: Ref<{ message?: string } | null>
      status: Ref<string>
      data: Ref<Tagged | undefined>
    }
    expect(one.status.value).toBe('error')
    expect(one.error.value?.message).toContain('upstream exploded')
    expect(one.data.value).toBeUndefined()
  })
})

describe('useApi — cache key stays reactive', () => {
  // The Quality Gate probe for PR430, kept verbatim in intent: two entries
  // that start merged on the empty key must separate once the URLs diverge.
  it('separates the two entries once the URLs diverge', async () => {
    const { Probe, idA, idB, probe } = twoColumnProbe()
    await mountSuspended(Probe)

    idA.value = 'alpha'
    idB.value = 'beta'
    await settle()

    const a = probe.a as { data: Ref<Tagged | undefined> }
    const b = probe.b as { data: Ref<Tagged | undefined> }

    // Distinct writes must stay distinct — a shared asyncData entry would
    // make the second write overwrite the first.
    a.data.value = { tag: 'AAA' }
    b.data.value = { tag: 'BBB' }
    await nextTick()

    expect(a.data.value).toEqual({ tag: 'AAA' })
    expect(b.data.value).toEqual({ tag: 'BBB' })
  })

  it('gives each compare column its own fetched payload', async () => {
    const { Probe, idA, idB, probe } = twoColumnProbe()
    await mountSuspended(Probe)

    idA.value = 'lhs'
    idB.value = 'rhs'
    await settle()

    const a = probe.a as { data: Ref<Tagged | undefined> }
    const b = probe.b as { data: Ref<Tagged | undefined> }

    expect(urls()).toEqual(
      expect.arrayContaining([`${API_BASE}/api/agents/lhs`, `${API_BASE}/api/agents/rhs`])
    )
    expect(a.data.value).toEqual({ tag: 'lhs' })
    expect(b.data.value).toEqual({ tag: 'rhs' })
  })

  it('refetches with fresh data when the path changes A -> B', async () => {
    const path = ref('')
    const { Probe, probe } = singleProbe(path)
    await mountSuspended(Probe)
    await settle()

    path.value = '/api/agents/first'
    await settle()
    const one = probe.one as { data: Ref<Tagged | undefined> }
    expect(one.data.value).toEqual({ tag: 'first' })

    path.value = '/api/agents/second'
    await settle()

    expect(one.data.value).toEqual({ tag: 'second' })
    expect(urls()).toEqual([
      `${API_BASE}/api/agents/first`,
      `${API_BASE}/api/agents/second`
    ])
  })

  it('refetches when a reactive query changes on a static path', async () => {
    // budget.vue / models.vue / audit.vue pass `query: computed(...)`; the
    // query is part of the key, so freezing the key would strand them on the
    // first period selected.
    const period = ref('7d')
    const probe: Record<string, unknown> = {}
    const Probe = defineComponent({
      setup() {
        const { fetchApi } = useApi()
        probe.costs = fetchApi<Tagged>('/api/llm-costs/summary', {
          query: computed(() => ({ period: period.value }))
        })
        return () => h('div')
      }
    })

    await mountSuspended(Probe)
    await settle()
    expect(calls).toHaveLength(1)
    expect((calls[0]!.options as { query: { period: string } }).query.period).toBe('7d')

    period.value = '30d'
    await settle()

    expect(calls).toHaveLength(2)
    expect((calls[1]!.options as { query: { period: string } }).query.period).toBe('30d')
  })
})

describe('useApi — caller-driven fetches keep manual control', () => {
  // plan-canvas.vue:83 passes `{ immediate: false, watch: false }` and drives
  // execution from its own watcher. Those callers must keep short-circuiting.
  //
  // `watch: false` freezes the asyncData key, so two such probes that both
  // start on an empty path would share one entry across tests — the explicit
  // key is what keeps each case independent (the app has a single caller).
  const manual = (key: string) => ({ immediate: false, watch: false, key })

  it('does not fetch on mount nor on path change', async () => {
    const path = ref('')
    const { Probe } = singleProbe(path, manual('manual-mount'))

    await mountSuspended(Probe)
    await settle()
    expect(transport).not.toHaveBeenCalled()

    path.value = '/api/plans/plan-1'
    await settle()

    expect(transport).not.toHaveBeenCalled()
  })

  it('fetches the current path only when the caller refreshes', async () => {
    const path = ref('')
    const { Probe, probe } = singleProbe(path, manual('manual-refresh'))

    await mountSuspended(Probe)
    await settle()

    path.value = '/api/plans/plan-2'
    await settle()

    const one = probe.one as { refresh: () => Promise<void>, data: Ref<Tagged | undefined> }
    await one.refresh()
    await settle()

    expect(urls()).toEqual([`${API_BASE}/api/plans/plan-2`])
    expect(one.data.value).toEqual({ tag: 'plan-2' })
  })

  it('still short-circuits a manual refresh on an empty path', async () => {
    const path = ref('')
    const { Probe, probe } = singleProbe(path, manual('manual-empty-refresh'))

    await mountSuspended(Probe)
    await settle()

    // plan-canvas guards its own watcher with `if (id)`, but the composable
    // must not depend on every caller remembering to.
    const one = probe.one as { refresh: () => Promise<void> }
    await one.refresh()
    await settle()

    expect(transport).not.toHaveBeenCalled()
  })
})
