<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { Command } from '~/types'

const { fetchApi } = useApi()

const { data, status, error, refresh } = await fetchApi<{ commands: Command[], total: number }>('/api/commands')

const commands = computed(() => data.value?.commands ?? [])

const search = ref('')
const departmentFilter = ref('all')
const page = ref(1)
const pageSize = 20
const expandedRow = ref<string | null>(null)

const departments = computed(() => {
  const depts = new Set(commands.value.map(c => c.department))
  return [
    { label: 'All Departments', value: 'all' },
    ...Array.from(depts).sort().map(d => ({ label: d, value: d }))
  ]
})

const filteredCommands = computed(() => {
  let result = commands.value
  const query = search.value.toLowerCase()

  if (query) {
    result = result.filter(cmd =>
      cmd.command.toLowerCase().includes(query)
      || cmd.description.toLowerCase().includes(query)
    )
  }

  if (departmentFilter.value !== 'all') {
    result = result.filter(cmd => cmd.department === departmentFilter.value)
  }

  return result
})

const totalFiltered = computed(() => filteredCommands.value.length)

const paginatedCommands = computed(() => {
  const start = (page.value - 1) * pageSize
  return filteredCommands.value.slice(start, start + pageSize)
})

const totalPages = computed(() => Math.max(1, Math.ceil(totalFiltered.value / pageSize)))

watch([search, departmentFilter], () => {
  page.value = 1
})

function toggleExpand(commandId: string) {
  expandedRow.value = expandedRow.value === commandId ? null : commandId
}

const columns: TableColumn<Command>[] = [
  {
    accessorKey: 'command',
    header: 'Command'
  },
  {
    accessorKey: 'department',
    header: 'Department'
  },
  {
    accessorKey: 'description',
    header: 'Description'
  }
]
</script>

<template>
  <UDashboardPanel id="commands">
    <template #header>
      <UDashboardNavbar title="Commands">
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
        <p class="text-sm text-muted">Failed to load commands.</p>
        <UButton label="Retry" variant="outline" color="primary" icon="i-lucide-refresh-cw" @click="refresh()" />
      </div>

      <!-- Empty -->
      <div v-else-if="!commands.length" class="flex flex-col items-center justify-center gap-4 py-12">
        <UIcon name="i-lucide-terminal" class="size-12 text-muted" />
        <p class="text-sm text-muted">No commands found.</p>
      </div>

      <!-- Content -->
      <template v-else>
        <div class="flex flex-wrap items-center gap-3 mb-4">
          <UInput
            v-model="search"
            class="max-w-sm"
            icon="i-lucide-search"
            placeholder="Search commands..."
            aria-label="Search commands by name or description"
          />

          <USelect
            v-model="departmentFilter"
            :items="departments"
            :ui="{ trailingIcon: 'group-data-[state=open]:rotate-180 transition-transform duration-200' }"
            placeholder="Department"
            class="min-w-48"
            aria-label="Filter by department"
          />

          <span class="ml-auto text-xs text-muted">
            {{ totalFiltered }} command{{ totalFiltered !== 1 ? 's' : '' }}
          </span>
        </div>

        <UTable
          :data="paginatedCommands"
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
          @select="(row: Command) => toggleExpand(row.id)"
        >
          <template #command-cell="{ row }">
            <code class="font-mono text-sm text-primary">{{ row.original.command }}</code>
          </template>
          <template #department-cell="{ row }">
            <UBadge :label="row.original.department" variant="subtle" size="sm" />
          </template>
          <template #expanded="{ row }">
            <div v-if="expandedRow === row.original.id && row.original.keywords?.length" class="px-4 py-3 bg-elevated/30">
              <p class="text-xs font-semibold text-muted uppercase tracking-wider mb-2">Keywords</p>
              <div class="flex flex-wrap gap-1.5">
                <UBadge
                  v-for="kw in row.original.keywords"
                  :key="kw"
                  :label="kw"
                  variant="outline"
                  size="xs"
                />
              </div>
            </div>
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
