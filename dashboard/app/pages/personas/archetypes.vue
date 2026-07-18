<script setup lang="ts">
// PR94b v3.48.0 — Browseable catalog of persona archetypes.
//
// Reads /api/personas/archetypes (PR93b) and renders each as a card.
// "Create from this" deep-links to /personas/new?archetype=<id> where
// the wizard auto-selects description mode and pre-fills.

interface Archetype {
  id: string
  name: string
  title: string
  tagline: string
  mbti: string
  disc: { primary: string, secondary: string }
  enneagram: { type: number, wing: number }
  description: string
}

const { fetchApi } = useApi()
const { data, status, error, refresh } = await fetchApi<{
  archetypes: Archetype[]
  total: number
}>('/api/personas/archetypes')

const archetypes = computed<Archetype[]>(() => data.value?.archetypes ?? [])

function discColor(letter: string): 'error' | 'warning' | 'success' | 'primary' | 'neutral' {
  const m: Record<string, 'error' | 'warning' | 'success' | 'primary' | 'neutral'> = {
    D: 'error', I: 'warning', S: 'success', C: 'primary'
  }
  return m[letter] ?? 'neutral'
}
</script>

<template>
  <UDashboardPanel id="archetypes">
    <template #header>
      <UDashboardNavbar title="Persona archetypes">
        <template #leading>
          <UButton
            icon="i-lucide-arrow-left"
            variant="ghost"
            size="sm"
            to="/personas"
            aria-label="Back"
          />
        </template>
        <template #trailing>
          <UBadge v-if="data?.total" :label="String(data.total)" variant="subtle" />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <DashboardState
        :status="status"
        :error="error"
        :empty="!archetypes.length"
        empty-title="No archetypes available"
        empty-icon="i-lucide-sparkles"
        loading-label="Loading archetypes"
        :on-retry="() => refresh()"
      >
        <p class="text-sm text-muted mb-6 max-w-2xl">
          Curated starter profiles. Each one ships a description, behavioural DNA
          defaults, and a recommended communication style. Use them as a base
          when you don't have indexed content yet — the wizard pre-fills the
          description and you tweak from there.
        </p>

        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <div
            v-for="arch in archetypes"
            :key="arch.id"
            class="rounded-xl border border-default p-5 flex flex-col gap-3 hover:border-primary/40 transition-colors"
          >
            <div>
              <h3 class="text-lg font-bold">
                {{ arch.name }}
              </h3>
              <p class="text-xs text-muted">
                {{ arch.title }}
              </p>
            </div>
            <p class="text-sm italic text-muted">
              "{{ arch.tagline }}"
            </p>
            <div class="flex flex-wrap gap-1.5">
              <UBadge :label="arch.mbti" variant="subtle" size="xs" />
              <UBadge
                :label="`DISC: ${arch.disc.primary}/${arch.disc.secondary}`"
                :color="discColor(arch.disc.primary)"
                variant="subtle"
                size="xs"
              />
              <UBadge
                :label="`E${arch.enneagram.type}w${arch.enneagram.wing}`"
                variant="outline"
                size="xs"
              />
            </div>
            <p class="text-sm text-muted line-clamp-3">
              {{ arch.description }}
            </p>
            <div class="pt-2 mt-auto">
              <UButton
                label="Create from this"
                icon="i-lucide-sparkles"
                color="primary"
                size="sm"
                block
                :to="`/personas/new?archetype=${arch.id}`"
              />
            </div>
          </div>
        </div>
      </DashboardState>
    </template>
  </UDashboardPanel>
</template>
