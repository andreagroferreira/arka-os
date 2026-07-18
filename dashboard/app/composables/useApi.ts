export const useApi = () => {
  const apiBase = useRuntimeConfig().public.apiBase || 'http://localhost:3334'

  // path may be a plain string or a getter — useFetch accepts a getter URL
  // and refetches when its reactive deps change (compare pages rely on it).
  const fetchApi = <T>(path: MaybeRefOrGetter<string>, opts?: Record<string, unknown>) =>
    useFetch<T>(() => `${apiBase}${toValue(path)}`, { ...opts })

  return { fetchApi, apiBase }
}
