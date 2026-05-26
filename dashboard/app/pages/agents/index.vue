<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { Agent } from '~/types'

const { fetchApi, apiBase } = useApi()
const toast = useToast()

const { data, status, error, refresh } = await fetchApi<{ agents: Agent[], total: number }>('/api/agents')

// PR69 v2.86.0 — per-department activity from PR47 telemetry.
// Used to badge agents whose department has run recently and to
// surface "no activity yet" hint when a department's never been
// invoked. Failure-tolerant — returns empty if telemetry unavailable.
interface ActivityRow {
  call_count: number
  total_cost_usd: number | null
  total_tokens_in: number
  total_tokens_out: number
}

const {
  data: activityData,
  refresh: refreshActivity,
} = fetchApi<{ by_department: Record<string, ActivityRow>, period: string }>(
  '/api/agents/activity?period=week',
)

const agents = computed(() => data.value?.agents ?? [])

function deptActivity(dept: string): ActivityRow | undefined {
  return activityData.value?.by_department?.[dept]
}

const copied = ref<string | null>(null)
let copyTimer: ReturnType<typeof setTimeout> | null = null

async function copyAgentMention(agent: Agent) {
  if (typeof navigator === 'undefined' || !navigator.clipboard) {
    toast.add({ title: 'Clipboard unavailable', color: 'warning' })
    return
  }
  // The most useful copy for an operator: a ready-to-paste mention
  // that names the agent + their role so the orchestrator can dispatch.
  const text = `Use ${agent.name} (${agent.role}, dept ${agent.department}, tier ${agent.tier}) for this task.`
  try {
    await navigator.clipboard.writeText(text)
    copied.value = agent.id
    if (copyTimer) clearTimeout(copyTimer)
    copyTimer = setTimeout(() => { copied.value = null; copyTimer = null }, 1500)
    toast.add({
      title: 'Copied',
      description: `${agent.name} mention ready to paste.`,
      color: 'success',
    })
  } catch (err) {
    toast.add({
      title: 'Copy failed',
      description: err instanceof Error ? err.message : 'unknown error',
      color: 'error',
    })
  }
}

onBeforeUnmount(() => {
  if (copyTimer) clearTimeout(copyTimer)
})

async function refreshAll() {
  await Promise.all([refresh(), refreshActivity()])
}

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
  { id: 'select',              header: '' },
  { accessorKey: 'name',       header: 'Name' },
  { accessorKey: 'role',       header: 'Role' },
  { accessorKey: 'department', header: 'Department' },
  { accessorKey: 'tier',       header: 'Tier' },
  {
    accessorFn: (row: Agent) => row.disc?.primary ?? '-',
    id: 'disc',
    header: 'DISC',
  },
  { accessorKey: 'mbti',       header: 'MBTI' },
  { id: 'activity',            header: 'Activity (7d)' },
  { id: 'actions',             header: '' },
]

function goToAgent(id: string) {
  navigateTo(`/agents/${id}`)
}

// PR83b v3.4.0 — bulk selection + delete.
// PR84b v3.8.0 — bulk move department.
const confirmDialog = useConfirmDialog()
const selected = ref<Set<string>>(new Set())
const bulkDeleting = ref(false)
const bulkMoving = ref(false)

const departmentMoveOptions = [
  'dev', 'marketing', 'brand', 'finance', 'strategy', 'ecom', 'kb', 'ops',
  'pm', 'saas', 'landing', 'content', 'community', 'sales', 'leadership', 'org',
].map((d) => ({
  label: `Move to ${d}`,
  icon: 'i-lucide-arrow-right',
  onSelect: () => bulkMove(d),
}))

async function bulkMove(targetDept: string) {
  if (selected.value.size === 0) return
  const ids = Array.from(selected.value)
  const ok = await confirmDialog({
    title: `Move ${ids.length} agent${ids.length === 1 ? '' : 's'} to ${targetDept}?`,
    description: 'The YAML files will be relocated and their `department:` field updated. Tier 0 agents and unknown departments are skipped.',
    confirmLabel: `Move to ${targetDept}`,
    cancelLabel: 'Cancel',
  })
  if (!ok) return
  bulkMoving.value = true
  const results = await Promise.allSettled(
    ids.map((id) =>
      $fetch<{ moved?: boolean, error?: string }>(`${apiBase}/api/agents/${id}/move`, {
        method: 'POST',
        body: { department: targetDept },
      }),
    ),
  )
  const successes = results.filter(
    (r) => r.status === 'fulfilled' && r.value.moved,
  ).length
  const failures = ids.length - successes
  toast.add({
    title: successes > 0
      ? `Moved ${successes} agent${successes === 1 ? '' : 's'}`
      : 'Nothing moved',
    description: failures > 0
      ? `${failures} skipped (Tier 0, collision, or missing)`
      : undefined,
    color: successes > 0 && failures === 0
      ? 'success'
      : failures > 0 && successes > 0 ? 'warning' : 'error',
  })
  clearSelection()
  bulkMoving.value = false
  await refreshAll()
}

function toggleSelected(id: string) {
  if (selected.value.has(id)) selected.value.delete(id)
  else selected.value.add(id)
  selected.value = new Set(selected.value)
}

function toggleAllVisible() {
  const visibleIds = paginatedAgents.value.map((a) => a.id)
  const allSelected = visibleIds.every((id) => selected.value.has(id))
  const next = new Set(selected.value)
  for (const id of visibleIds) {
    if (allSelected) next.delete(id)
    else next.add(id)
  }
  selected.value = next
}

const allVisibleSelected = computed(() => {
  const visibleIds = paginatedAgents.value.map((a) => a.id)
  return visibleIds.length > 0 && visibleIds.every((id) => selected.value.has(id))
})

function clearSelection() {
  selected.value = new Set()
}

async function bulkDelete() {
  if (selected.value.size === 0) return
  const ids = Array.from(selected.value)
  const ok = await confirmDialog({
    title: `Delete ${ids.length} agent${ids.length === 1 ? '' : 's'}?`,
    description: 'YAML files will be removed from disk. This cannot be undone. Tier 0 agents are protected and will be skipped.',
    confirmLabel: `Delete ${ids.length}`,
    cancelLabel: 'Cancel',
    variant: 'danger',
  })
  if (!ok) return
  bulkDeleting.value = true
  const results = await Promise.allSettled(
    ids.map((id) =>
      $fetch<{ deleted?: boolean, error?: string }>(`${apiBase}/api/agents/${id}`, {
        method: 'DELETE',
      }),
    ),
  )
  const successes = results.filter(
    (r) => r.status === 'fulfilled' && r.value.deleted,
  ).length
  const failures = ids.length - successes
  if (successes > 0) {
    toast.add({
      title: `Deleted ${successes} agent${successes === 1 ? '' : 's'}`,
      description: failures > 0 ? `${failures} skipped (Tier 0 or missing)` : undefined,
      color: failures > 0 ? 'warning' : 'success',
    })
  } else {
    toast.add({
      title: 'Nothing deleted',
      description: 'All targets were protected or missing.',
      color: 'error',
    })
  }
  clearSelection()
  bulkDeleting.value = false
  await refreshAll()
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
        <template #right>
          <UButton
            label="New Agent"
            icon="i-lucide-plus"
            size="sm"
            to="/agents/new"
          />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <DashboardState
        :status="status"
        :error="error"
        :empty="!agents.length"
        empty-title="No agents found"
        empty-icon="i-lucide-users"
        loading-label="Loading agents"
        :on-retry="() => refreshAll()"
      >
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
        >
          <template #select-header>
            <UCheckbox
              :model-value="allVisibleSelected"
              aria-label="Select all visible"
              @update:model-value="toggleAllVisible"
            />
          </template>
          <template #select-cell="{ row }">
            <UCheckbox
              :model-value="selected.has(row.original.id)"
              :aria-label="`Select ${row.original.name}`"
              @update:model-value="() => toggleSelected(row.original.id)"
              @click.stop
            />
          </template>
          <template #name-cell="{ row }">
            <button class="text-left font-medium text-primary hover:underline" @click="goToAgent(row.original.id)">
              {{ row.original.name }}
            </button>
          </template>
          <template #department-cell="{ row }">
            <UBadge :label="row.original.department" variant="subtle" size="sm" />
          </template>
          <template #tier-cell="{ row }">
            <UBadge :label="`Tier ${row.original.tier}`" :color="tierColor(row.original.tier)" variant="subtle" size="sm" />
          </template>
          <template #mbti-cell="{ row }">
            <span class="font-mono text-sm">{{ row.original.mbti || '-' }}</span>
          </template>
          <template #activity-cell="{ row }">
            <template v-if="deptActivity(row.original.department)">
              <div class="flex items-center gap-2">
                <span class="inline-block size-2 rounded-full bg-green-500" />
                <span class="text-xs font-mono">
                  {{ deptActivity(row.original.department)?.call_count ?? 0 }} calls
                </span>
              </div>
            </template>
            <span v-else class="text-xs text-muted">—</span>
          </template>
          <template #actions-cell="{ row }">
            <UButton
              :icon="copied === row.original.id ? 'i-lucide-check' : 'i-lucide-copy'"
              :color="copied === row.original.id ? 'success' : 'neutral'"
              variant="ghost"
              size="xs"
              aria-label="Copy agent mention"
              @click.stop="copyAgentMention(row.original)"
            />
            <UButton
              size="xs"
              variant="ghost"
              icon="i-lucide-arrow-right"
              aria-label="Open agent detail"
              @click="goToAgent(row.original.id)"
            />
          </template>
        </UTable>

        <Transition
          enter-active-class="transition ease-out duration-150"
          enter-from-class="translate-y-4 opacity-0"
          enter-to-class="translate-y-0 opacity-100"
          leave-active-class="transition ease-in duration-100"
          leave-from-class="translate-y-0 opacity-100"
          leave-to-class="translate-y-4 opacity-0"
        >
          <div
            v-if="selected.size > 0"
            class="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 flex items-center gap-3 rounded-xl border border-default bg-elevated shadow-lg px-4 py-2"
          >
            <span class="text-sm font-semibold">
              {{ selected.size }} selected
            </span>
            <UButton
              label="Clear"
              variant="ghost"
              size="xs"
              @click="clearSelection"
            />
            <div class="h-5 w-px bg-default" />
            <UDropdownMenu :items="departmentMoveOptions">
              <UButton
                label="Move to..."
                icon="i-lucide-folder-tree"
                size="sm"
                variant="soft"
                :loading="bulkMoving"
                trailing-icon="i-lucide-chevron-down"
              />
            </UDropdownMenu>
            <UButton
              label="Delete"
              icon="i-lucide-trash-2"
              color="error"
              size="sm"
              :loading="bulkDeleting"
              @click="bulkDelete"
            />
          </div>
        </Transition>

        <div v-if="totalPages > 1" class="flex items-center justify-center mt-6">
          <UPagination
            :page="page"
            :total="totalFiltered"
            :items-per-page="pageSize"
            @update:page="(val) => page = val"
          />
        </div>
      </DashboardState>
    </template>
  </UDashboardPanel>
</template>
