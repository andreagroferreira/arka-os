<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { Task, TaskSummary } from '~/types'

const { fetchApi } = useApi()

const { data, status, error, refresh } = await fetchApi<{ tasks: Task[], summary: TaskSummary }>('/api/tasks')

const tasks = computed(() => data.value?.tasks ?? [])
const summary = computed(() => data.value?.summary ?? { total: 0, active: 0, queued: 0, completed: 0 })

const activeTab = ref('all')

const tabItems = [
  { label: 'All', value: 'all' },
  { label: 'Active', value: 'active' },
  { label: 'Queued', value: 'queued' },
  { label: 'Completed', value: 'completed' },
  { label: 'Failed', value: 'failed' }
]

const filteredTasks = computed(() => {
  if (activeTab.value === 'all') return tasks.value
  return tasks.value.filter(t => {
    if (activeTab.value === 'active') return t.status === 'processing' || t.status === 'active'
    return t.status === activeTab.value
  })
})

type StatusColorType = 'success' | 'error' | 'primary' | 'warning' | 'neutral'

function statusColor(taskStatus: string): StatusColorType {
  const colors: Record<string, StatusColorType> = {
    completed: 'success',
    processing: 'primary',
    active: 'primary',
    queued: 'neutral',
    failed: 'error',
    cancelled: 'warning'
  }
  return colors[taskStatus] ?? 'neutral'
}

function formatDate(dateStr: string) {
  if (!dateStr) return '-'
  try {
    return new Intl.DateTimeFormat('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    }).format(new Date(dateStr))
  } catch {
    return dateStr
  }
}

const columns: TableColumn<Task>[] = [
  {
    accessorKey: 'agent',
    header: 'Type'
  },
  {
    accessorKey: 'title',
    header: 'Title'
  },
  {
    accessorKey: 'department',
    header: 'Department'
  },
  {
    accessorKey: 'status',
    header: 'Status'
  },
  {
    accessorKey: 'progress',
    header: 'Progress'
  },
  {
    accessorKey: 'created_at',
    header: 'Created'
  }
]
</script>

<template>
  <UDashboardPanel id="tasks">
    <template #header>
      <UDashboardNavbar title="Tasks">
        <template #leading>
          <UDashboardSidebarCollapse />
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
        <p class="text-sm text-muted">Failed to load tasks.</p>
        <UButton label="Retry" variant="outline" color="primary" icon="i-lucide-refresh-cw" @click="refresh()" />
      </div>

      <!-- Content -->
      <template v-else>
        <!-- Summary Cards -->
        <div class="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <div class="rounded-lg border border-default p-4 text-center">
            <p class="text-2xl font-semibold text-highlighted">{{ summary.total }}</p>
            <p class="text-xs text-muted">Total</p>
          </div>
          <div class="rounded-lg border border-default p-4 text-center">
            <p class="text-2xl font-semibold text-primary">{{ summary.active }}</p>
            <p class="text-xs text-muted">Active</p>
          </div>
          <div class="rounded-lg border border-default p-4 text-center">
            <p class="text-2xl font-semibold text-yellow-500">{{ summary.queued }}</p>
            <p class="text-xs text-muted">Queued</p>
          </div>
          <div class="rounded-lg border border-default p-4 text-center">
            <p class="text-2xl font-semibold text-green-500">{{ summary.completed }}</p>
            <p class="text-xs text-muted">Completed</p>
          </div>
        </div>

        <!-- Status Filter Tabs -->
        <div class="mt-6">
          <UTabs
            :items="tabItems"
            :model-value="activeTab"
            @update:model-value="activeTab = $event as string"
          />
        </div>

        <!-- Empty State -->
        <div v-if="!tasks.length" class="mt-6 flex flex-col items-center justify-center gap-4 py-16">
          <UIcon name="i-lucide-list-checks" class="size-16 text-muted" />
          <h3 class="text-lg font-semibold text-highlighted">No tasks yet</h3>
          <p class="text-sm text-muted text-center max-w-md">
            Tasks are created when you run ArkaOS workflows. Start by indexing your project or running a command.
          </p>
          <div class="mt-2 rounded-lg border border-default bg-elevated/50 px-4 py-3">
            <p class="text-xs text-muted mb-1">Try running:</p>
            <code class="font-mono text-sm text-primary">npx arkaos index</code>
          </div>
        </div>

        <!-- Filtered Empty -->
        <div v-else-if="!filteredTasks.length" class="mt-6 flex flex-col items-center justify-center gap-4 py-12">
          <UIcon name="i-lucide-filter-x" class="size-12 text-muted" />
          <p class="text-sm text-muted">No {{ activeTab }} tasks found.</p>
        </div>

        <!-- Task Table -->
        <div v-else class="mt-4">
          <UTable
            :data="filteredTasks"
            :columns="columns"
            :loading="status === 'pending'"
            class="shrink-0"
            :ui="{
              base: 'table-fixed border-separate border-spacing-0',
              thead: '[&>tr]:bg-elevated/50 [&>tr]:after:content-none',
              tbody: '[&>tr]:last:[&>td]:border-b-0',
              th: 'py-2 first:rounded-l-lg last:rounded-r-lg border-y border-default first:border-l last:border-r',
              td: 'border-b border-default'
            }"
          >
            <template #agent-cell="{ row }">
              <UBadge :label="row.original.agent" variant="subtle" color="primary" size="sm" />
            </template>
            <template #department-cell="{ row }">
              <span class="text-sm text-muted">{{ row.original.department }}</span>
            </template>
            <template #status-cell="{ row }">
              <UBadge
                :label="row.original.status"
                :color="statusColor(row.original.status)"
                variant="subtle"
                size="sm"
                class="capitalize"
              />
            </template>
            <template #progress-cell="{ row }">
              <div class="flex items-center gap-2 min-w-24">
                <UProgress :value="row.original.progress" :max="100" size="xs" class="flex-1" />
                <span class="text-xs text-muted font-mono w-8 text-right">{{ row.original.progress }}%</span>
              </div>
            </template>
            <template #created_at-cell="{ row }">
              <span class="text-xs text-muted">{{ formatDate(row.original.created_at) }}</span>
            </template>
          </UTable>
        </div>
      </template>
    </template>
  </UDashboardPanel>
</template>
