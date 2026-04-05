export function useApi() {
  const config = useRuntimeConfig()
  const apiBase = (config.public.apiBase as string) || 'http://localhost:3334'

  function fetchApi<T>(path: string, opts?: Record<string, unknown>) {
    return useFetch<T>(`${apiBase}${path}`, {
      ...opts,
    })
  }

  return { fetchApi, apiBase }
}
