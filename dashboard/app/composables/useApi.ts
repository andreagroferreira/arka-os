export const useApi = () => {
  const apiBase = useRuntimeConfig().public.apiBase || 'http://localhost:3334'

  const fetchApi = <T>(path: string, opts?: Record<string, any>) =>
    useFetch<T>(`${apiBase}${path}`, { ...opts })

  return { fetchApi, apiBase }
}
