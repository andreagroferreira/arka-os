export const useApi = () => {
  const apiBase = useRuntimeConfig().public.apiBase || 'http://localhost:3334'

  // path may be a plain string or a getter — useFetch accepts a getter URL
  // and refetches when its reactive deps change (compare pages rely on it).
  //
  // An empty path means "nothing to fetch yet": the compare pages return ''
  // until their ids are known. useFetch has no notion of a skipped request, so
  // an empty path resolves to apiBase itself and 404s on every mount. Hold the
  // request while the path is empty, then fetch and keep tracking changes.
  // Callers that drive execution themselves (immediate: false) keep control.
  const fetchApi = <T>(path: MaybeRefOrGetter<string>, opts?: Record<string, unknown>) => {
    const relative = computed(() => toValue(path))
    const manual = opts?.immediate === false

    const result = useFetch<T>(() => `${apiBase}${relative.value}`, {
      ...opts,
      immediate: !manual && Boolean(relative.value),
      watch: false
    })

    if (!manual) {
      watch(relative, (next) => {
        if (next) result.execute()
      })
    }

    return result
  }

  return { fetchApi, apiBase }
}
