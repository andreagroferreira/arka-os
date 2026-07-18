<script setup lang="ts">
// PR87d v3.22.0 — compact stats card mounted at the bottom of the
// sidebar. Polls /api/sidebar-stats every 60s.

interface SidebarStats {
  agents: number
  personas: number
  departments: number
  today_cost_usd: number | null
  today_calls: number
}

const { fetchApi } = useApi()
const { data, refresh } = fetchApi<SidebarStats>('/api/sidebar-stats')

let timer: ReturnType<typeof setInterval> | null = null
onMounted(() => {
  timer = setInterval(() => {
    refresh()
  }, 60_000)
})
onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
})

function formatCost(cost: number | null): string {
  if (cost === null || cost === undefined) return '—'
  if (cost < 0.01) return '<$0.01'
  if (cost < 1) return `$${cost.toFixed(3)}`
  return `$${cost.toFixed(2)}`
}
</script>

<template>
  <div
    v-if="data"
    class="rounded-lg border border-default bg-elevated/20 p-3 mx-2 mb-2 text-xs space-y-1.5"
    aria-label="Workspace quick stats"
  >
    <div class="flex items-center justify-between">
      <span class="text-muted">Agents</span>
      <span class="font-mono font-semibold">{{ data.agents }}</span>
    </div>
    <div class="flex items-center justify-between">
      <span class="text-muted">Personas</span>
      <span class="font-mono font-semibold">{{ data.personas }}</span>
    </div>
    <div class="flex items-center justify-between">
      <span class="text-muted">Departments</span>
      <span class="font-mono font-semibold">{{ data.departments }}</span>
    </div>
    <div class="border-t border-default/60 mt-2 pt-1.5 flex items-center justify-between">
      <span class="text-muted">Today</span>
      <span class="font-mono font-semibold text-primary">
        {{ formatCost(data.today_cost_usd) }}
      </span>
    </div>
    <div class="flex items-center justify-between text-[10px] text-muted/70">
      <span>{{ data.today_calls }} call{{ data.today_calls === 1 ? '' : 's' }}</span>
      <span>auto · 60s</span>
    </div>
  </div>
</template>
