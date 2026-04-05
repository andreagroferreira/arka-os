export const useApi = () => {
  const apiBase = useRuntimeConfig().public.apiBase || 'http://localhost:3334'

  const fetchApi = <T>(path: string) =>
    useFetch<T>(`${apiBase}${path}`)

  return { fetchApi, apiBase }
}
