<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { Agent } from '~/types'

const { fetchApi } = useApi()

const { data, status, error, refresh } = await fetchApi<{ agents: Agent[], total: number }>('/api/agents')

const agents = computed(() => data.value?.agents ?? [])

const search = ref('')
const departmentFilter = ref('all')
const tierFilter = ref('all')
const page = ref(1)
const pageSize = 15

const departments = computed(() => {
  const depts = new Set(agents.value.map(a => a.department))
  return [
    { label: 'All Departments', value: 'all' },
    ...Array.from(depts).sort().map(d => ({ label: d, value: d }))
  ]
})

const tierOptions = [
  { label: 'All Tiers', value: 'all' },
  { label: 'Tier 0 — C-Suite', value: '0' },
  { label: 'Tier 1 — Squad Leads', value: '1' },
  { label: 'Tier 2 — Specialists', value: '2' },
  { label: 'Tier 3 — Support', value: '3' }
]

const filteredAgents = computed(() => {
  let result = agents.value
  const query = search.value.toLowerCase()

  if (query) {
    result = result.filter(agent =>
      agent.name.toLowerCase().includes(query)
      || agent.role.toLowerCase().includes(query)
      || agent.department.toLowerCase().includes(query)
    )
  }

  if (departmentFilter.value !== 'all') {
    result = result.filter(agent => agent.department === departmentFilter.value)
  }

  if (tierFilter.value !== 'all') {
    result = result.filter(agent => String(agent.tier) === tierFilter.value)
  }

  return result
})

const totalFiltered = computed(() => filteredAgents.value.length)

const paginatedAgents = computed(() => {
  const start = (page.value - 1) * pageSize
  return filteredAgents.value.slice(start, start + pageSize)
})

const totalPages = computed(() => Math.max(1, Math.ceil(totalFiltered.value / pageSize)))

watch([search, departmentFilter, tierFilter], () => {
  page.value = 1
})

const tierColor = (tier: number) => {
  const colors: Record<number, string> = {
    0: 'error',
    1: 'warning',
    2: 'primary',
    3: 'neutral'
  }
  return (colors[tier] ?? 'neutral') as 'error' | 'warning' | 'primary' | 'neutral'
}

const columns: TableColumn<Agent>[] = [
  {
    accessorKey: 'name',
    header: 'Name'
  },
  {
    accessorKey: 'role',
    header: 'Role'
  },
  {
    accessorKey: 'department',
    header: 'Department'
  },
  {
    accessorKey: 'tier',
    header: 'Tier'
  },
  {
    accessorFn: (row: Agent) => row.disc?.primary ?? '-',
    id: 'disc',
    header: 'DISC'
  },
  {
    accessorKey: 'mbti',
    header: 'MBTI'
  }
]

function onRowClick(row: Agent) {
  navigateTo(`/agents/${row.id}`)
}
</script>

<template>
  <UDashboardPanel id="agents">
    <template #header>
      <UDashboardNavbar title="Agents">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #trailing>
          <UBadge v-if="data?.total" :label="data.total" variant="subtle" />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <!-- Loading -->
      <div v-if="status === 'pending'" class="flex items-center justify-center py-12">
        <UIcon name="i-lucide-loader-2" class="size-8 animate-spin text-muted" />
      </div>

      <!-- Error -->
      <div v-else-if="error" class="flex flex-col items-center justify-center gap-4 py-12" role="alert">
        <UIcon name="i-lucide-alert-triangle" class="size-12 text-red-500" />
        <p class="text-sm text-muted">Failed to load agents.</p>
        <UButton label="Retry" variant="outline" color="primary" icon="i-lucide-refresh-cw" @click="refresh()" />
      </div>

      <!-- Empty -->
      <div v-else-if="!agents.length" class="flex flex-col items-center justify-center gap-4 py-12">
        <UIcon name="i-lucide-users" class="size-12 text-muted" />
        <p class="text-sm text-muted">No agents found.</p>
      </div>

      <!-- Content -->
      <template v-else>
        <div class="flex flex-wrap items-center gap-3 mb-4">
          <UInput
            v-model="search"
            class="max-w-sm"
            icon="i-lucide-search"
            placeholder="Search agents..."
            aria-label="Search agents by name, role, or department"
          />

          <USelect
            v-model="departmentFilter"
            :items="departments"
            :ui="{ trailingIcon: 'group-data-[state=open]:rotate-180 transition-transform duration-200' }"
            placeholder="Department"
            class="min-w-48"
            aria-label="Filter by department"
          />

          <USelect
            v-model="tierFilter"
            :items="tierOptions"
            :ui="{ trailingIcon: 'group-data-[state=open]:rotate-180 transition-transform duration-200' }"
            placeholder="Tier"
            class="min-w-44"
            aria-label="Filter by tier"
          />

          <span class="ml-auto text-xs text-muted">
            {{ totalFiltered }} agent{{ totalFiltered !== 1 ? 's' : '' }}
          </span>
        </div>

        <UTable
          :data="paginatedAgents"
          :columns="columns"
          :loading="status === 'pending'"
          class="shrink-0"
          :ui="{
            base: 'table-fixed border-separate border-spacing-0',
            thead: '[&>tr]:bg-elevated/50 [&>tr]:after:content-none',
            tbody: '[&>tr]:last:[&>td]:border-b-0 [&>tr]:cursor-pointer [&>tr]:hover:bg-elevated/50 [&>tr]:transition-colors',
            th: 'py-2 first:rounded-l-lg last:rounded-r-lg border-y border-default first:border-l last:border-r',
            td: 'border-b border-default'
          }"
          @select="onRowClick"
        >
          <template #department-cell="{ row }">
            <UBadge :label="row.original.department" variant="subtle" size="sm" />
          </template>
          <template #tier-cell="{ row }">
            <UBadge :label="`Tier ${row.original.tier}`" :color="tierColor(row.original.tier)" variant="subtle" size="sm" />
          </template>
          <template #mbti-cell="{ row }">
            <span class="font-mono text-sm">{{ row.original.mbti || '-' }}</span>
          </template>
        </UTable>

        <div v-if="totalPages > 1" class="flex items-center justify-center mt-6">
          <UPagination
            :page="page"
            :total="totalFiltered"
            :items-per-page="pageSize"
            @update:page="(val) => page = val"
          />
        </div>
      </template>
    </template>
  </UDashboardPanel>
</template>
