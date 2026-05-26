<script setup lang="ts">
// PR89a v3.27.0 — Departments index.
//
// Lists every department with agent count, tier distribution, and 30d
// cost. Click a row to drill into /departments/{dept}.

import type { TableColumn } from '@nuxt/ui'

interface DeptRow {
  department: string
  agent_count: number
  tier_counts: Record<'0' | '1' | '2' | '3', number>
  calls_30d: number
  cost_usd_30d: number | null
}

const { fetchApi } = useApi()
const { data, status, error, refresh } = await fetchApi<{
  departments: DeptRow[]
  total: number
}>('/api/departments')

const rows = computed<DeptRow[]>(() => data.value?.departments ?? [])
const search = ref('')
const filtered = computed(() => {
  const q = search.value.toLowerCase().trim()
  if (!q) return rows.value
  return rows.value.filter((r) => r.department.toLowerCase().includes(q))
})

const columns: TableColumn<DeptRow>[] = [
  { accessorKey: 'department', header: 'Department' },
  { accessorKey: 'agent_count', header: 'Agents' },
  { id: 'tiers', header: 'Tiers (0/1/2/3)' },
  { accessorKey: 'calls_30d', header: 'Calls (30d)' },
  { accessorKey: 'cost_usd_30d', header: 'Cost (30d)' },
  { id: 'actions', header: '' },
]

function formatCost(cost: number | null): string {
  if (cost === null || cost === undefined) return '—'
  if (cost < 0.01) return '<$0.01'
  if (cost < 1) return `$${cost.toFixed(3)}`
  return `$${cost.toFixed(2)}`
}
</script>

<template>
  <UDashboardPanel id="departments">
    <template #header>
      <UDashboardNavbar title="Departments">
        <template #leading>
          <UDashboardSidebarCollapse />
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
        :empty="!rows.length"
        empty-title="No departments yet"
        empty-icon="i-lucide-folder-tree"
        loading-label="Loading departments"
        :on-retry="() => refresh()"
      >
        <div class="flex items-center gap-3 mb-4">
          <UInput
            v-model="search"
            class="max-w-sm"
            icon="i-lucide-search"
            placeholder="Filter departments…"
          />
          <span class="ml-auto text-xs text-muted">
            {{ filtered.length }} dept{{ filtered.length === 1 ? '' : 's' }}
          </span>
        </div>

        <UTable
          :data="filtered"
          :columns="columns"
          :loading="status === 'pending'"
          :ui="{
            tbody: '[&>tr]:cursor-pointer [&>tr]:hover:bg-elevated/50 [&>tr]:transition-colors',
            th: 'py-2 first:rounded-l-lg last:rounded-r-lg border-y border-default first:border-l last:border-r',
            td: 'border-b border-default',
          }"
          @select="(_e: Event, row: { original: DeptRow }) => row?.original && navigateTo(`/departments/${row.original.department}`)"
        >
          <template #department-cell="{ row }">
            <span class="font-semibold capitalize">{{ row.original.department }}</span>
          </template>
          <template #agent_count-cell="{ row }">
            <span class="font-mono font-semibold">{{ row.original.agent_count }}</span>
          </template>
          <template #tiers-cell="{ row }">
            <div class="flex items-center gap-1 text-xs font-mono">
              <UBadge v-if="row.original.tier_counts['0'] > 0" :label="`0:${row.original.tier_counts['0']}`" color="error" variant="subtle" size="xs" />
              <UBadge v-if="row.original.tier_counts['1'] > 0" :label="`1:${row.original.tier_counts['1']}`" color="warning" variant="subtle" size="xs" />
              <UBadge v-if="row.original.tier_counts['2'] > 0" :label="`2:${row.original.tier_counts['2']}`" color="primary" variant="subtle" size="xs" />
              <UBadge v-if="row.original.tier_counts['3'] > 0" :label="`3:${row.original.tier_counts['3']}`" color="neutral" variant="subtle" size="xs" />
            </div>
          </template>
          <template #calls_30d-cell="{ row }">
            <span class="font-mono text-sm">{{ row.original.calls_30d }}</span>
          </template>
          <template #cost_usd_30d-cell="{ row }">
            <span class="font-mono text-sm font-semibold">{{ formatCost(row.original.cost_usd_30d) }}</span>
          </template>
          <template #actions-cell="{ row }">
            <UButton
              icon="i-lucide-arrow-right"
              variant="ghost"
              size="xs"
              aria-label="Open department"
              @click.stop="navigateTo(`/departments/${row.original.department}`)"
            />
          </template>
        </UTable>
      </DashboardState>
    </template>
  </UDashboardPanel>
</template>
