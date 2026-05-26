<script setup lang="ts">
// PR91a v3.35.0 — "What's missing?" home page card.
//
// Lists empty departments (high severity) and depts missing a Tier 2
// specialist (medium). Each suggestion is a link to /agents/new.

interface Suggestion {
  department: string
  reason: string
  recommended_tier: 1 | 2
  severity: 'high' | 'medium'
}

const { fetchApi } = useApi()
const { data, status } = fetchApi<{ suggestions: Suggestion[], total_gaps: number }>(
  '/api/agents/suggestions?limit=6',
)

const suggestions = computed<Suggestion[]>(() => data.value?.suggestions ?? [])

function severityColor(s: string): 'error' | 'warning' | 'neutral' {
  return s === 'high' ? 'error' : s === 'medium' ? 'warning' : 'neutral'
}
</script>

<template>
  <UCard v-if="status !== 'pending' && suggestions.length > 0">
    <template #header>
      <div class="flex items-center justify-between">
        <div>
          <h3 class="text-lg font-semibold">What's missing?</h3>
          <p class="text-xs text-muted mt-0.5">
            {{ data?.total_gaps }} gap{{ data?.total_gaps === 1 ? '' : 's' }} across departments. Showing top {{ suggestions.length }}.
          </p>
        </div>
        <UIcon name="i-lucide-sparkles" class="size-5 text-primary" />
      </div>
    </template>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-2">
      <NuxtLink
        v-for="s in suggestions"
        :key="`${s.department}:${s.recommended_tier}`"
        to="/agents/new"
        class="flex items-center gap-3 rounded-lg border border-default p-3 hover:border-primary/40 transition-colors"
      >
        <UBadge
          :label="s.severity"
          :color="severityColor(s.severity)"
          variant="subtle"
          size="xs"
        />
        <div class="flex-1 min-w-0">
          <p class="text-sm font-semibold capitalize truncate">{{ s.department }}</p>
          <p class="text-xs text-muted truncate">{{ s.reason }}</p>
        </div>
        <span class="text-xs font-mono text-muted shrink-0">T{{ s.recommended_tier }}</span>
        <UIcon name="i-lucide-arrow-right" class="size-4 text-muted shrink-0" />
      </NuxtLink>
    </div>
  </UCard>
</template>
