<script setup lang="ts">
// PR89a v3.27.0 — Department detail page.
//
// Shows agents in the department + its workflows + 30d cost.

const route = useRoute()
const deptId = computed(() => String(route.params.dept ?? ''))
const { fetchApi } = useApi()

interface AgentLite {
  id: string
  name?: string
  role?: string
  tier?: number
  mbti?: string
  disc?: { primary?: string, secondary?: string }
}

interface WorkflowLite {
  id: string
  name: string
  tier: string
  command: string
  phases_count: number
}

interface DeptDetail {
  department: string
  agents: AgentLite[]
  workflows: WorkflowLite[]
  calls_30d: number
  cost_usd_30d: number | null
  error?: string
}

const { data, status, error, refresh } = await fetchApi<DeptDetail>(
  `/api/departments/${deptId.value}`,
)

const errorMsg = computed(() => data.value?.error || error.value?.message || null)
const detail = computed<DeptDetail | null>(() => {
  if (!data.value || data.value.error) return null
  return data.value
})

function formatCost(cost: number | null): string {
  if (cost === null || cost === undefined) return '—'
  if (cost < 0.01) return '<$0.01'
  if (cost < 1) return `$${cost.toFixed(3)}`
  return `$${cost.toFixed(2)}`
}

const tierColor = (tier: number | undefined) => {
  const colors: Record<number, 'error' | 'warning' | 'primary' | 'neutral'> = {
    0: 'error', 1: 'warning', 2: 'primary', 3: 'neutral',
  }
  return colors[tier ?? 99] ?? 'neutral'
}
</script>

<template>
  <UDashboardPanel :id="`dept-${deptId}`">
    <template #header>
      <UDashboardNavbar :title="`Department · ${deptId}`">
        <template #leading>
          <UButton icon="i-lucide-arrow-left" variant="ghost" size="sm" to="/departments" aria-label="Back" />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <DashboardState
        :status="status"
        :error="errorMsg ? new Error(errorMsg) : null"
        :empty="!detail"
        empty-title="Department not found"
        empty-icon="i-lucide-folder-x"
        loading-label="Loading department"
        :on-retry="() => refresh()"
      >
        <div v-if="detail" class="space-y-5 max-w-5xl">
          <!-- Stats row -->
          <section class="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div class="rounded-xl border border-default p-4 bg-elevated/20">
              <p class="text-sm font-semibold text-muted uppercase tracking-wide mb-1">Agents</p>
              <p class="text-2xl font-bold">{{ detail.agents.length }}</p>
            </div>
            <div class="rounded-xl border border-default p-4 bg-elevated/20">
              <p class="text-sm font-semibold text-muted uppercase tracking-wide mb-1">Workflows</p>
              <p class="text-2xl font-bold">{{ detail.workflows.length }}</p>
            </div>
            <div class="rounded-xl border border-default p-4 bg-elevated/20">
              <p class="text-sm font-semibold text-muted uppercase tracking-wide mb-1">Calls (30d)</p>
              <p class="text-2xl font-bold">{{ detail.calls_30d }}</p>
            </div>
            <div class="rounded-xl border border-default p-4 bg-elevated/20">
              <p class="text-sm font-semibold text-muted uppercase tracking-wide mb-1">Cost (30d)</p>
              <p class="text-2xl font-bold">{{ formatCost(detail.cost_usd_30d) }}</p>
            </div>
          </section>

          <!-- Agents -->
          <section>
            <h2 class="text-sm font-semibold uppercase tracking-wide text-muted mb-3">Agents</h2>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-2">
              <NuxtLink
                v-for="a in detail.agents"
                :key="a.id"
                :to="`/agents/${a.id}`"
                class="block rounded-lg border border-default p-3 hover:border-primary/40 transition-colors"
              >
                <div class="flex items-center justify-between gap-3">
                  <div class="min-w-0">
                    <p class="font-semibold truncate">{{ a.name }}</p>
                    <p class="text-xs text-muted truncate">{{ a.role || '—' }}</p>
                  </div>
                  <div class="flex items-center gap-2 shrink-0">
                    <UBadge
                      :label="`T${a.tier}`"
                      :color="tierColor(a.tier)"
                      variant="subtle"
                      size="xs"
                    />
                    <UBadge v-if="a.mbti" :label="a.mbti" variant="soft" size="xs" />
                  </div>
                </div>
              </NuxtLink>
            </div>
          </section>

          <!-- Workflows -->
          <section v-if="detail.workflows.length > 0">
            <h2 class="text-sm font-semibold uppercase tracking-wide text-muted mb-3">Workflows</h2>
            <div class="space-y-2">
              <NuxtLink
                v-for="w in detail.workflows"
                :key="w.id"
                to="/workflows"
                class="block rounded-lg border border-default p-3 hover:border-primary/40 transition-colors"
              >
                <div class="flex items-center justify-between gap-3">
                  <div class="min-w-0">
                    <p class="font-semibold truncate">{{ w.name }}</p>
                    <p class="text-xs text-muted font-mono truncate">{{ w.command || w.id }}</p>
                  </div>
                  <div class="flex items-center gap-2 shrink-0 text-xs">
                    <UBadge v-if="w.tier" :label="w.tier" variant="subtle" size="xs" />
                    <span class="text-muted">{{ w.phases_count }} phase{{ w.phases_count === 1 ? '' : 's' }}</span>
                  </div>
                </div>
              </NuxtLink>
            </div>
          </section>
        </div>
      </DashboardState>
    </template>
  </UDashboardPanel>
</template>
