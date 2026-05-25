<script setup lang="ts">
// PR68 v2.85.0 — Commands page: ▶ Copy + ★ Favorites.
//
// The previous Commands page was a read-only catalogue (135 rows,
// search, filter, expand for keywords). Daniel Ek's audit question
// landed: "what is the job-to-be-done here vs the CLI?" The answer:
// fast lookup → copy to clipboard → paste back into Claude Code.
// PR68 makes that flow one-click + adds operator-curated favorites
// stored locally so the top-of-list is the operator's actual
// muscle-memory commands.

import type { TableColumn } from '@nuxt/ui'
import type { Command } from '~/types'

const { fetchApi } = useApi()
const toast = useToast()

const {
  data,
  status,
  error,
  refresh,
} = await fetchApi<{ commands: Command[], total: number }>('/api/commands')

// ─── Favorites (persisted in localStorage) ───────────────────────────────

const FAVORITES_KEY = 'arkaos_command_favorites'
const favorites = ref<Set<string>>(new Set())

function loadFavorites() {
  if (typeof window === 'undefined') return
  try {
    const raw = window.localStorage.getItem(FAVORITES_KEY)
    if (!raw) return
    const parsed = JSON.parse(raw)
    if (Array.isArray(parsed)) {
      favorites.value = new Set(parsed.filter((v): v is string => typeof v === 'string'))
    }
  } catch { /* corrupt JSON — ignore, start fresh */ }
}

function persistFavorites() {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(
      FAVORITES_KEY,
      JSON.stringify(Array.from(favorites.value)),
    )
  } catch { /* quota / disabled storage — silent */ }
}

function toggleFavorite(commandId: string) {
  if (favorites.value.has(commandId)) {
    favorites.value.delete(commandId)
  } else {
    favorites.value.add(commandId)
  }
  persistFavorites()
}

onMounted(() => {
  loadFavorites()
})

// ─── Filters + view ─────────────────────────────────────────────────────

const search = ref('')
const departmentFilter = ref('all')
const view = ref<'all' | 'favorites'>('all')
const page = ref(1)
const pageSize = 20
const expandedRow = ref<string | null>(null)

const commands = computed(() => data.value?.commands ?? [])

const departments = computed(() => {
  const depts = new Set(commands.value.map((c) => c.department))
  return [
    { label: 'All Departments', value: 'all' },
    ...Array.from(depts).sort().map((d) => ({ label: d, value: d })),
  ]
})

const baseList = computed<Command[]>(() => {
  if (view.value === 'favorites') {
    return commands.value.filter((c) => favorites.value.has(c.id))
  }
  return commands.value
})

const filteredCommands = computed<Command[]>(() => {
  let result = baseList.value
  const query = search.value.toLowerCase().trim()
  if (query) {
    result = result.filter((cmd) =>
      cmd.command.toLowerCase().includes(query)
      || cmd.description.toLowerCase().includes(query),
    )
  }
  if (departmentFilter.value !== 'all') {
    result = result.filter((cmd) => cmd.department === departmentFilter.value)
  }
  // Favorites pinned on top in the "all" view; the favorites-only
  // view doesn't need re-sorting.
  if (view.value === 'all') {
    result = [...result].sort((a, b) => {
      const aFav = favorites.value.has(a.id) ? 0 : 1
      const bFav = favorites.value.has(b.id) ? 0 : 1
      return aFav - bFav
    })
  }
  return result
})

const totalFiltered = computed(() => filteredCommands.value.length)

const paginatedCommands = computed(() =>
  filteredCommands.value.slice(
    (page.value - 1) * pageSize,
    page.value * pageSize,
  ),
)

const totalPages = computed(() =>
  Math.max(1, Math.ceil(totalFiltered.value / pageSize)),
)

watch([search, departmentFilter, view], () => {
  page.value = 1
})

// ─── Copy command to clipboard ──────────────────────────────────────────

const copied = ref<string | null>(null)
let copyTimer: ReturnType<typeof setTimeout> | null = null

async function copyCommand(cmd: Command) {
  if (typeof navigator === 'undefined' || !navigator.clipboard) {
    toast.add({
      title: 'Clipboard unavailable',
      description: 'Your browser blocked navigator.clipboard.',
      color: 'warning',
    })
    return
  }
  try {
    await navigator.clipboard.writeText(cmd.command)
    copied.value = cmd.id
    if (copyTimer) clearTimeout(copyTimer)
    copyTimer = setTimeout(() => {
      copied.value = null
      copyTimer = null
    }, 1500)
    toast.add({
      title: 'Copied',
      description: cmd.command,
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

// ─── Expansion + table ──────────────────────────────────────────────────

function toggleExpand(commandId: string) {
  expandedRow.value = expandedRow.value === commandId ? null : commandId
}

const columns: TableColumn<Command>[] = [
  { accessorKey: 'star',        header: '' },
  { accessorKey: 'command',     header: 'Command' },
  { accessorKey: 'department',  header: 'Department' },
  { accessorKey: 'description', header: 'Description' },
  { accessorKey: 'actions',     header: '' },
]

const viewTabs = [
  { label: 'All', value: 'all' as const },
  { label: 'Favorites', value: 'favorites' as const },
]

const favoritesCount = computed(() => favorites.value.size)
</script>

<template>
  <UDashboardPanel id="commands">
    <template #header>
      <UDashboardNavbar title="Commands">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #trailing>
          <UBadge
            v-if="data?.total"
            :label="`${data.total} total`"
            variant="subtle"
            size="xs"
          />
          <UBadge
            v-if="favoritesCount"
            :label="`★ ${favoritesCount}`"
            variant="subtle"
            color="warning"
            size="xs"
            class="ml-2"
          />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <DashboardState
        :status="status"
        :error="error"
        :empty="!commands.length"
        empty-title="No commands found"
        empty-icon="i-lucide-terminal"
        loading-label="Loading commands"
        :on-retry="() => refresh()"
      >
        <!-- View tabs + filters -->
        <div class="flex flex-wrap items-center gap-3 mb-4">
          <UTabs
            :items="viewTabs"
            :model-value="view"
            class="shrink-0"
            @update:model-value="view = $event as 'all' | 'favorites'"
          />

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

        <!-- Favorites empty state -->
        <div
          v-if="view === 'favorites' && favoritesCount === 0"
          class="flex flex-col items-center justify-center gap-3 py-16 rounded-lg border border-default"
        >
          <UIcon name="i-lucide-star" class="size-12 text-muted" />
          <p class="text-sm text-muted">No favorites yet.</p>
          <p class="text-xs text-muted text-center max-w-sm">
            Click the ★ next to any command to pin it here for one-click access.
          </p>
        </div>

        <!-- Table -->
        <template v-else>
          <UTable
            :data="paginatedCommands"
            :columns="columns"
            :loading="status === 'pending'"
            class="shrink-0"
            :ui="{
              base: 'table-fixed border-separate border-spacing-0',
              thead: '[&>tr]:bg-elevated/50 [&>tr]:after:content-none',
              tbody: '[&>tr]:last:[&>td]:border-b-0 [&>tr]:hover:bg-elevated/50 [&>tr]:transition-colors',
              th: 'py-2 first:rounded-l-lg last:rounded-r-lg border-y border-default first:border-l last:border-r',
              td: 'border-b border-default',
            }"
          >
            <template #star-cell="{ row }">
              <UButton
                :icon="favorites.has(row.original.id) ? 'i-lucide-star' : 'i-lucide-star'"
                :color="favorites.has(row.original.id) ? 'warning' : 'neutral'"
                variant="ghost"
                size="xs"
                :aria-label="favorites.has(row.original.id) ? 'Unfavorite' : 'Favorite'"
                :class="favorites.has(row.original.id) ? '' : 'opacity-30 hover:opacity-100'"
                @click.stop="toggleFavorite(row.original.id)"
              />
            </template>
            <template #command-cell="{ row }">
              <button
                type="button"
                class="text-left w-full"
                @click="toggleExpand(row.original.id)"
              >
                <code class="font-mono text-sm text-primary">{{ row.original.command }}</code>
              </button>
            </template>
            <template #department-cell="{ row }">
              <UBadge :label="row.original.department" variant="subtle" size="sm" />
            </template>
            <template #description-cell="{ row }">
              <span class="text-sm text-muted">{{ row.original.description }}</span>
            </template>
            <template #actions-cell="{ row }">
              <UButton
                :icon="copied === row.original.id ? 'i-lucide-check' : 'i-lucide-copy'"
                :color="copied === row.original.id ? 'success' : 'neutral'"
                variant="ghost"
                size="xs"
                aria-label="Copy command to clipboard"
                @click.stop="copyCommand(row.original)"
              />
            </template>
            <template #expanded="{ row }">
              <div
                v-if="expandedRow === row.original.id && row.original.keywords?.length"
                class="px-4 py-3 bg-elevated/30"
              >
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
      </DashboardState>
    </template>
  </UDashboardPanel>
</template>
