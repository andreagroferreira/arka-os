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

// PR92b v3.40.0 — initial values come from ?q=...&dept=...&tier=...
// so /agents links can deep-link to a filtered view.
const route = useRoute()
const router = useRouter()
const search = ref(String(route.query.q ?? ''))
const departmentFilter = ref(String(route.query.dept ?? 'all'))
const tierFilter = ref(String(route.query.tier ?? 'all'))
const page = ref(1)
const pageSize = 15

// PR86a + PR92b — favorites refs must exist BEFORE the filter watcher
// below references them (otherwise TDZ blows up the whole page).
const favs = useFavorites()
await favs.load()
const favoritesOnly = ref(route.query.fav === '1')

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

// PR87a v3.19.0 — DNA filters (DISC primary + MBTI group).
// PR92b v3.40.0 — seed from URL query.
const discFilter = ref<'all' | 'D' | 'I' | 'S' | 'C'>(
  (route.query.disc as any) ?? 'all',
)
const mbtiGroupFilter = ref<'all' | 'analysts' | 'diplomats' | 'sentinels' | 'explorers'>(
  (route.query.mbti as any) ?? 'all',
)

const discOptions = [
  { label: 'All DISC', value: 'all' },
  { label: 'D — Dominance', value: 'D' },
  { label: 'I — Influence', value: 'I' },
  { label: 'S — Steadiness', value: 'S' },
  { label: 'C — Conscientiousness', value: 'C' },
]

const mbtiGroupOptions = [
  { label: 'All MBTI groups', value: 'all' },
  { label: 'Analysts (NT)', value: 'analysts' },
  { label: 'Diplomats (NF)', value: 'diplomats' },
  { label: 'Sentinels (S__J)', value: 'sentinels' },
  { label: 'Explorers (S__P)', value: 'explorers' },
]

const MBTI_GROUPS: Record<string, string> = {
  INTJ: 'analysts', INTP: 'analysts', ENTJ: 'analysts', ENTP: 'analysts',
  INFJ: 'diplomats', INFP: 'diplomats', ENFJ: 'diplomats', ENFP: 'diplomats',
  ISTJ: 'sentinels', ISFJ: 'sentinels', ESTJ: 'sentinels', ESFJ: 'sentinels',
  ISTP: 'explorers', ISFP: 'explorers', ESTP: 'explorers', ESFP: 'explorers',
}

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

  if (discFilter.value !== 'all') {
    result = result.filter(agent => agent.disc?.primary === discFilter.value)
  }

  if (mbtiGroupFilter.value !== 'all') {
    result = result.filter(
      agent => MBTI_GROUPS[(agent.mbti ?? '').toUpperCase()] === mbtiGroupFilter.value,
    )
  }

  if (favoritesOnly.value) {
    result = result.filter(agent => favs.isAgentFavorite(agent.id))
  }

  return result
})

const totalFiltered = computed(() => filteredAgents.value.length)

const paginatedAgents = computed(() => {
  const start = (page.value - 1) * pageSize
  return filteredAgents.value.slice(start, start + pageSize)
})

const totalPages = computed(() => Math.max(1, Math.ceil(totalFiltered.value / pageSize)))

// PR92b v3.40.0 — push filter state to URL so deep-links survive reload
// and the browser back/forward buttons work as expected.
watch(
  [search, departmentFilter, tierFilter, discFilter, mbtiGroupFilter, favoritesOnly],
  () => {
    const query: Record<string, string> = {}
    if (search.value.trim()) query.q = search.value.trim()
    if (departmentFilter.value !== 'all') query.dept = departmentFilter.value
    if (tierFilter.value !== 'all') query.tier = tierFilter.value
    if (discFilter.value !== 'all') query.disc = discFilter.value
    if (mbtiGroupFilter.value !== 'all') query.mbti = mbtiGroupFilter.value
    if (favoritesOnly.value) query.fav = '1'
    router.replace({ query })
  },
  { flush: 'post' },
)

watch([search, departmentFilter, tierFilter, discFilter, mbtiGroupFilter], () => {
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
  { id: 'favorite',            header: '' },
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

// PR95d v3.54.0 — keyboard nav for the table.
const cursorIndex = ref(-1)

function cursorDown() {
  const total = paginatedAgents.value.length
  if (total === 0) return
  cursorIndex.value = Math.min(total - 1, Math.max(0, cursorIndex.value + 1))
  scrollCursorIntoView()
}
function cursorUp() {
  const total = paginatedAgents.value.length
  if (total === 0) return
  cursorIndex.value = Math.max(0, cursorIndex.value === -1 ? 0 : cursorIndex.value - 1)
  scrollCursorIntoView()
}
function cursorOpen() {
  if (cursorIndex.value < 0) return
  const row = paginatedAgents.value[cursorIndex.value]
  if (row?.id) goToAgent(row.id)
}
function scrollCursorIntoView() {
  if (typeof document === 'undefined') return
  // Defer to next tick so the class change has rendered.
  setTimeout(() => {
    const el = document.querySelector('[data-cursor="true"]')
    el?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, 0)
}

defineShortcuts({
  j: () => cursorDown(),
  k: () => cursorUp(),
  arrowdown: () => cursorDown(),
  arrowup: () => cursorUp(),
  enter: () => cursorOpen(),
})

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

function openCompare() {
  if (selected.value.size !== 2) return
  const ids = Array.from(selected.value).slice(0, 2).join(',')
  navigateTo(`/agents/compare?ids=${ids}`)
}

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
      $fetch<{ moved?: boolean, trash_id?: string, error?: string }>(
        `${apiBase}/api/agents/${id}/move`,
        { method: 'POST', body: { department: targetDept } },
      ),
    ),
  )
  const successes = results.filter(
    (r) => r.status === 'fulfilled' && r.value.moved,
  )
  const trashIds = successes
    .map((r) => (r.status === 'fulfilled' ? r.value.trash_id : null))
    .filter((v): v is string => Boolean(v))
  const failures = ids.length - successes.length
  toast.add({
    title: successes.length > 0
      ? `Moved ${successes.length} agent${successes.length === 1 ? '' : 's'}`
      : 'Nothing moved',
    description: failures > 0
      ? `${failures} skipped (Tier 0, collision, or missing)`
      : undefined,
    color: successes.length > 0 && failures === 0
      ? 'success'
      : failures > 0 && successes.length > 0 ? 'warning' : 'error',
    actions: trashIds.length > 0
      ? [{ label: 'Undo', icon: 'i-lucide-rotate-ccw', onClick: () => undoTrashIds(trashIds) }]
      : undefined,
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
      $fetch<{ deleted?: boolean, trash_id?: string, error?: string }>(
        `${apiBase}/api/agents/${id}`,
        { method: 'DELETE' },
      ),
    ),
  )
  const successes = results.filter(
    (r) => r.status === 'fulfilled' && r.value.deleted,
  )
  const trashIds = successes
    .map((r) => (r.status === 'fulfilled' ? r.value.trash_id : null))
    .filter((v): v is string => Boolean(v))
  const failures = ids.length - successes.length
  if (successes.length > 0) {
    toast.add({
      title: `Deleted ${successes.length} agent${successes.length === 1 ? '' : 's'}`,
      description: failures > 0 ? `${failures} skipped (Tier 0 or missing)` : 'Undo from /trash within 50 ops.',
      color: failures > 0 ? 'warning' : 'success',
      actions: trashIds.length > 0
        ? [{ label: 'Undo', icon: 'i-lucide-rotate-ccw', onClick: () => undoTrashIds(trashIds) }]
        : undefined,
    })
    // PR93d v3.46.0 — also surface in the notifications bell.
    useActivityFeed().push({
      kind: failures > 0 ? 'warning' : 'success',
      title: `Deleted ${successes.length} agent${successes.length === 1 ? '' : 's'}`,
      description: failures > 0 ? `${failures} skipped` : 'Undo via /trash',
      to: '/trash',
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

// PR97c v3.61.0 — bulk star / unstar selected agents.
async function bulkStar(favorited: boolean) {
  if (selected.value.size === 0) return
  const ids = Array.from(selected.value)
  const applied = await favs.setMany('agents', ids, favorited)
  if (applied === null) return
  toast.add({
    title: favorited
      ? `Starred ${applied} agent${applied === 1 ? '' : 's'}`
      : `Unstarred ${applied} agent${applied === 1 ? '' : 's'}`,
    description: applied < ids.length ? `${ids.length - applied} already in state` : undefined,
    color: 'success',
    icon: favorited ? 'i-lucide-star' : 'i-lucide-star-off',
  })
}

async function undoTrashIds(ids: string[]) {
  const results = await Promise.allSettled(
    ids.map((tid) =>
      $fetch<{ restored?: boolean, error?: string }>(
        `${apiBase}/api/trash/${tid}/restore`,
        { method: 'POST' },
      ),
    ),
  )
  const restored = results.filter(
    (r) => r.status === 'fulfilled' && r.value.restored,
  ).length
  toast.add({
    title: restored > 0 ? `Restored ${restored}` : 'Undo failed',
    description: restored < ids.length ? `${ids.length - restored} could not be restored.` : undefined,
    color: restored === ids.length ? 'success' : restored > 0 ? 'warning' : 'error',
  })
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

          <USelect
            v-model="discFilter"
            :items="discOptions"
            placeholder="DISC"
            class="min-w-36"
            aria-label="Filter by DISC primary"
          />

          <USelect
            v-model="mbtiGroupFilter"
            :items="mbtiGroupOptions"
            placeholder="MBTI group"
            class="min-w-44"
            aria-label="Filter by MBTI group"
          />

          <UButton
            :label="favoritesOnly ? 'All' : 'Favorites'"
            :icon="favoritesOnly ? 'i-lucide-star' : 'i-lucide-star'"
            :color="favoritesOnly ? 'warning' : 'neutral'"
            :variant="favoritesOnly ? 'soft' : 'outline'"
            size="sm"
            @click="favoritesOnly = !favoritesOnly"
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
          <template #favorite-cell="{ row }">
            <UButton
              :icon="favs.isAgentFavorite(row.original.id) ? 'i-lucide-star' : 'i-lucide-star'"
              :color="favs.isAgentFavorite(row.original.id) ? 'warning' : 'neutral'"
              :variant="favs.isAgentFavorite(row.original.id) ? 'soft' : 'ghost'"
              size="xs"
              :aria-label="favs.isAgentFavorite(row.original.id) ? 'Unfavorite' : 'Favorite'"
              @click.stop="favs.toggle('agents', row.original.id)"
            />
          </template>
          <template #name-cell="{ row }">
            <div :data-cursor="row.index === cursorIndex ? 'true' : undefined" class="flex items-center gap-1.5">
              <UIcon
                v-if="row.index === cursorIndex"
                name="i-lucide-chevron-right"
                class="size-3.5 text-primary shrink-0"
              />
              <button class="text-left font-medium text-primary hover:underline" @click="goToAgent(row.original.id)">
                {{ row.original.name }}
              </button>
            </div>
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
            <UButton
              icon="i-lucide-star"
              size="sm"
              variant="soft"
              color="warning"
              aria-label="Star selected"
              @click="bulkStar(true)"
            />
            <UButton
              icon="i-lucide-star-off"
              size="sm"
              variant="ghost"
              color="neutral"
              aria-label="Unstar selected"
              @click="bulkStar(false)"
            />
            <UButton
              label="Compare"
              icon="i-lucide-columns-2"
              size="sm"
              variant="soft"
              :disabled="selected.size !== 2"
              @click="openCompare"
            />
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
