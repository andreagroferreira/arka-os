// PR86a v3.15.0 — shared favourites state + toggle helper.
//
// Single source of truth for the dashboard so the star button in
// agents/personas detail pages stays in sync with the filter chip
// on the index tables.

import { createSharedComposable } from '@vueuse/core'

interface FavoritesPayload {
  agents: string[]
  personas: string[]
}

const _useFavorites = () => {
  const { apiBase } = useApi()
  const toast = useToast()
  const state = useState<FavoritesPayload>('favorites', () => ({
    agents: [],
    personas: [],
  }))
  const loaded = useState<boolean>('favoritesLoaded', () => false)

  async function load(force = false) {
    if (loaded.value && !force) return
    try {
      const res = await $fetch<FavoritesPayload>(`${apiBase}/api/favorites`)
      state.value = {
        agents: res.agents ?? [],
        personas: res.personas ?? [],
      }
      loaded.value = true
    } catch {
      // Best-effort — leave defaults
      loaded.value = true
    }
  }

  function isAgentFavorite(id: string): boolean {
    return state.value.agents.includes(id)
  }

  function isPersonaFavorite(id: string): boolean {
    return state.value.personas.includes(id)
  }

  async function toggle(kind: 'agents' | 'personas', id: string) {
    try {
      const res = await $fetch<{ favorited?: boolean, error?: string }>(
        `${apiBase}/api/favorites/${kind}/${id}`,
        { method: 'POST' },
      )
      if (res.error) throw new Error(res.error)
      const bucket = state.value[kind]
      if (res.favorited && !bucket.includes(id)) {
        state.value = { ...state.value, [kind]: [...bucket, id] }
      } else if (!res.favorited) {
        state.value = { ...state.value, [kind]: bucket.filter((x) => x !== id) }
      }
      return res.favorited
    } catch (err) {
      toast.add({
        title: 'Favorite toggle failed',
        description: err instanceof Error ? err.message : 'unknown error',
        color: 'error',
      })
      return null
    }
  }

  return { state, load, isAgentFavorite, isPersonaFavorite, toggle, loaded }
}

export const useFavorites = createSharedComposable(_useFavorites)
