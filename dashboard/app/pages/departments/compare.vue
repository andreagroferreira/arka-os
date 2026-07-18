<script setup lang="ts">
// PR90b v3.32.0 — Compare two departments side-by-side.
//
// Driven by `?a=dept1&b=dept2`. Reuses /api/departments/{id}. Shows
// agent count + tier distribution + workflows count + 30d cost.

const route = useRoute()
const { fetchApi } = useApi()

const deptA = computed(() => String(route.query.a ?? ''))
const deptB = computed(() => String(route.query.b ?? ''))

interface AgentLite {
  id: string
  name?: string
  role?: string
  tier?: number
  mbti?: string
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

const { data: a } = fetchApi<DeptDetail>(
  () => deptA.value ? `/api/departments/${deptA.value}` : ''
)
const { data: b } = fetchApi<DeptDetail>(
  () => deptB.value ? `/api/departments/${deptB.value}` : ''
)

const errorMsg = computed(() => {
  if (!deptA.value || !deptB.value) return 'Pass ?a=dept1&b=dept2'
  if (a.value?.error) return `Left: ${a.value.error}`
  if (b.value?.error) return `Right: ${b.value.error}`
  return null
})

function diffClass(left: unknown, right: unknown): string {
  return left !== right ? 'bg-yellow-500/10 border-yellow-500/30' : ''
}

function formatCost(cost: number | null | undefined): string {
  if (cost === null || cost === undefined) return '—'
  if (cost < 0.01) return '<$0.01'
  if (cost < 1) return `$${cost.toFixed(3)}`
  return `$${cost.toFixed(2)}`
}

const tierColor = (tier: number | undefined) => {
  const m: Record<number, 'error' | 'warning' | 'primary' | 'neutral'> = {
    0: 'error', 1: 'warning', 2: 'primary', 3: 'neutral'
  }
  return m[tier ?? 99] ?? 'neutral'
}
</script>

<template>
  <UDashboardPanel id="departments-compare">
    <template #header>
      <UDashboardNavbar title="Compare departments">
        <template #leading>
          <UButton
            icon="i-lucide-arrow-left"
            variant="ghost"
            size="sm"
            to="/departments"
            aria-label="Back"
          />
        </template>
        <template #trailing>
          <UBadge label="2-way" variant="subtle" size="sm" />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div v-if="errorMsg" class="p-6 text-center text-sm text-error">
        {{ errorMsg }}
      </div>
      <div v-else-if="!a || !b" class="p-6 text-center text-sm text-muted">
        <UIcon name="i-lucide-loader-2" class="size-4 animate-spin inline" /> Loading…
      </div>
      <div v-else class="space-y-4 max-w-6xl">
        <section class="grid grid-cols-2 gap-3">
          <NuxtLink :to="`/departments/${a.department}`" class="rounded-lg border border-default p-4 hover:border-primary/40">
            <p class="text-xs text-muted uppercase tracking-wide">Left</p>
            <h2 class="text-xl font-bold capitalize">{{ a.department }}</h2>
          </NuxtLink>
          <NuxtLink :to="`/departments/${b.department}`" class="rounded-lg border border-default p-4 hover:border-primary/40">
            <p class="text-xs text-muted uppercase tracking-wide">Right</p>
            <h2 class="text-xl font-bold capitalize">{{ b.department }}</h2>
          </NuxtLink>
        </section>

        <h3 class="text-sm font-semibold uppercase tracking-wide text-muted pt-2">
          Stats
        </h3>
        <div class="grid grid-cols-2 gap-3">
          <div :class="['rounded-lg border p-3', diffClass(a.agents.length, b.agents.length)]">
            <p class="text-xs text-muted">
              Agents
            </p>
            <p class="text-2xl font-bold">
              {{ a.agents.length }}
            </p>
          </div>
          <div :class="['rounded-lg border p-3', diffClass(a.agents.length, b.agents.length)]">
            <p class="text-xs text-muted">
              Agents
            </p>
            <p class="text-2xl font-bold">
              {{ b.agents.length }}
            </p>
          </div>
          <div :class="['rounded-lg border p-3', diffClass(a.workflows.length, b.workflows.length)]">
            <p class="text-xs text-muted">
              Workflows
            </p>
            <p class="text-2xl font-bold">
              {{ a.workflows.length }}
            </p>
          </div>
          <div :class="['rounded-lg border p-3', diffClass(a.workflows.length, b.workflows.length)]">
            <p class="text-xs text-muted">
              Workflows
            </p>
            <p class="text-2xl font-bold">
              {{ b.workflows.length }}
            </p>
          </div>
          <div :class="['rounded-lg border p-3', diffClass(a.calls_30d, b.calls_30d)]">
            <p class="text-xs text-muted">
              Calls (30d)
            </p>
            <p class="text-2xl font-bold">
              {{ a.calls_30d }}
            </p>
          </div>
          <div :class="['rounded-lg border p-3', diffClass(a.calls_30d, b.calls_30d)]">
            <p class="text-xs text-muted">
              Calls (30d)
            </p>
            <p class="text-2xl font-bold">
              {{ b.calls_30d }}
            </p>
          </div>
          <div :class="['rounded-lg border p-3', diffClass(a.cost_usd_30d, b.cost_usd_30d)]">
            <p class="text-xs text-muted">
              Cost (30d)
            </p>
            <p class="text-2xl font-bold">
              {{ formatCost(a.cost_usd_30d) }}
            </p>
          </div>
          <div :class="['rounded-lg border p-3', diffClass(a.cost_usd_30d, b.cost_usd_30d)]">
            <p class="text-xs text-muted">
              Cost (30d)
            </p>
            <p class="text-2xl font-bold">
              {{ formatCost(b.cost_usd_30d) }}
            </p>
          </div>
        </div>

        <h3 class="text-sm font-semibold uppercase tracking-wide text-muted pt-2">
          Agents
        </h3>
        <div class="grid grid-cols-2 gap-3">
          <div class="rounded-lg border border-default p-3 space-y-1">
            <NuxtLink
              v-for="ag in a.agents"
              :key="ag.id"
              :to="`/agents/${ag.id}`"
              class="flex items-center gap-2 text-sm hover:text-primary truncate"
            >
              <UBadge
                :label="`T${ag.tier}`"
                :color="tierColor(ag.tier)"
                variant="subtle"
                size="xs"
              />
              <span class="font-medium truncate">{{ ag.name }}</span>
              <span class="text-xs text-muted truncate">— {{ ag.role }}</span>
            </NuxtLink>
          </div>
          <div class="rounded-lg border border-default p-3 space-y-1">
            <NuxtLink
              v-for="ag in b.agents"
              :key="ag.id"
              :to="`/agents/${ag.id}`"
              class="flex items-center gap-2 text-sm hover:text-primary truncate"
            >
              <UBadge
                :label="`T${ag.tier}`"
                :color="tierColor(ag.tier)"
                variant="subtle"
                size="xs"
              />
              <span class="font-medium truncate">{{ ag.name }}</span>
              <span class="text-xs text-muted truncate">— {{ ag.role }}</span>
            </NuxtLink>
          </div>
        </div>

        <h3
          v-if="a.workflows.length > 0 || b.workflows.length > 0"
          class="text-sm font-semibold uppercase tracking-wide text-muted pt-2"
        >
          Workflows
        </h3>
        <div v-if="a.workflows.length > 0 || b.workflows.length > 0" class="grid grid-cols-2 gap-3">
          <div class="rounded-lg border border-default p-3 space-y-1">
            <p v-for="w in a.workflows" :key="w.id" class="text-sm truncate">
              <span class="font-mono text-xs text-muted">{{ w.command || w.id }}</span>
              · {{ w.name }}
            </p>
            <p v-if="!a.workflows.length" class="text-sm text-muted italic">
              No workflows
            </p>
          </div>
          <div class="rounded-lg border border-default p-3 space-y-1">
            <p v-for="w in b.workflows" :key="w.id" class="text-sm truncate">
              <span class="font-mono text-xs text-muted">{{ w.command || w.id }}</span>
              · {{ w.name }}
            </p>
            <p v-if="!b.workflows.length" class="text-sm text-muted italic">
              No workflows
            </p>
          </div>
        </div>

        <p class="text-xs text-muted pt-4 italic">
          Cells with a yellow tint differ between the two departments.
        </p>
      </div>
    </template>
  </UDashboardPanel>
</template>
