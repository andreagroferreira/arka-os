<script setup lang="ts">
// PR98b v3.64.0 — quick list of starred agents/personas in the sidebar.
//
// Shows up to 4 agents + 4 personas. Each row links to its detail.
// Hides itself when the operator has zero favourites.

const favs = useFavorites()
const { fetchApi } = useApi()

await favs.load()
const { data: agentsData } = fetchApi<{ agents: Array<{ id: string, name: string }> }>(
  '/api/agents',
)
const { data: personasData } = fetchApi<{ personas: Array<{ id: string, name: string }> }>(
  '/api/personas',
)

interface FavRow { id: string, name: string }

const starredAgents = computed<FavRow[]>(() => {
  const all = agentsData.value?.agents ?? []
  return favs.state.value.agents
    .map((id) => all.find((a) => a.id === id))
    .filter((a): a is FavRow => Boolean(a))
    .slice(0, 4)
})

const starredPersonas = computed<FavRow[]>(() => {
  const all = personasData.value?.personas ?? []
  return favs.state.value.personas
    .map((id) => all.find((p) => p.id === id))
    .filter((p): p is FavRow => Boolean(p))
    .slice(0, 4)
})

const hasAny = computed(
  () => starredAgents.value.length > 0 || starredPersonas.value.length > 0,
)
</script>

<template>
  <div
    v-if="hasAny"
    class="rounded-lg border border-default bg-elevated/20 p-2 mx-2 mb-2 text-xs"
    aria-label="Starred agents and personas"
  >
    <div class="flex items-center gap-1.5 mb-1.5">
      <UIcon name="i-lucide-star" class="size-3 text-amber-500" />
      <span class="font-semibold uppercase tracking-wide text-muted text-[10px]">
        Favorites
      </span>
    </div>

    <div v-if="starredAgents.length > 0" class="space-y-0.5 mb-1.5">
      <NuxtLink
        v-for="a in starredAgents"
        :key="`a-${a.id}`"
        :to="`/agents/${a.id}`"
        class="flex items-center gap-1.5 rounded px-1.5 py-1 hover:bg-elevated/40 transition-colors"
      >
        <UIcon name="i-lucide-user" class="size-3 text-primary shrink-0" />
        <span class="truncate">{{ a.name }}</span>
      </NuxtLink>
    </div>

    <div v-if="starredPersonas.length > 0" class="space-y-0.5">
      <NuxtLink
        v-for="p in starredPersonas"
        :key="`p-${p.id}`"
        :to="`/personas/${p.id}`"
        class="flex items-center gap-1.5 rounded px-1.5 py-1 hover:bg-elevated/40 transition-colors"
      >
        <UIcon name="i-lucide-user-plus" class="size-3 text-emerald-500 shrink-0" />
        <span class="truncate">{{ p.name }}</span>
      </NuxtLink>
    </div>
  </div>
</template>
