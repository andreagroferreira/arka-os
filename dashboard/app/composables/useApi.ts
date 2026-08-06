export const useApi = () => {
  const apiBase = useRuntimeConfig().public.apiBase || 'http://localhost:3334'

  // path may be a plain string or a getter — useFetch accepts a getter URL
  // and refetches when its reactive deps change (compare pages rely on it).
  //
  // An empty path means "nothing to fetch yet". Every empty-until-selected
  // caller has that shape: the four compare pages return '' until their ids
  // land (agents/compare.vue:49-54, departments/compare.vue:36-41,
  // personas/compare.vue:75-80, personas/compare-with-agent.vue:54-59) and so
  // does plan-canvas.vue:73-76 until a plan row is picked. useFetch has no
  // skip flag, so an empty path collapses the URL to apiBase itself and 404s
  // on mount. The guard therefore sits in the transport, never in
  // `watch`/`immediate`: `watch: false` freezes the cache key at setup
  // (fetch.js:106 passes `key.value`, not `key`), which merges two parallel
  // fetches that start empty into one asyncData entry — both compare columns
  // would then render the same record — and also kills the refetch of the
  // pages that pass a reactive `query`.
  //
  // The app is client-only (`ssr: false`), so overriding `$fetch` costs
  // nothing: useFetch's `useRequestFetch()` branch is server-side only, and
  // apiBase is absolute, which disqualifies that branch anyway.
  type Transport = typeof globalThis.$fetch

  const fetchApi = <T>(path: MaybeRefOrGetter<string>, opts?: Record<string, unknown>) => {
    const relative = computed(() => toValue(path))
    const caller = opts?.$fetch as Transport | undefined

    const skipWhenPathEmpty = ((...args: Parameters<Transport>) =>
      relative.value
        ? (caller ?? globalThis.$fetch)(...args)
        : Promise.resolve(undefined)) as Transport

    return useFetch<T>(() => `${apiBase}${relative.value}`, {
      ...opts,
      $fetch: skipWhenPathEmpty
    })
  }

  return { fetchApi, apiBase }
}
