<script setup lang="ts">
// PR78 v2.96.0 — Personas list rebuilt as a TABLE.
//
// Mirrors agents/index.vue structure. Click a row → navigates to
// /personas/{id} (dedicated detail page, not a drawer). Replaces the
// card grid + slide-over drawer that PR74/77 shipped.

import type { TableColumn } from '@nuxt/ui'
import type { Persona } from '~/types'

const { fetchApi } = useApi()

const { data, status, error, refresh } = await fetchApi<{
  personas: Persona[]
  total: number
  obsidian_available: boolean
}>('/api/personas')

const { data: usageData, refresh: refreshUsage } = fetchApi<{
  by_persona: Record<string, { agent_count: number, agent_ids: string[] }>
}>('/api/personas/usage')

const personas = computed<Persona[]>(() => data.value?.personas ?? [])

async function refreshAll() {
  await Promise.all([refresh(), refreshUsage()])
}

// ─── Filters ─────────────────────────────────────────────────────────────

const search = ref('')
const mbtiGroupFilter = ref<'all' | 'analysts' | 'diplomats' | 'sentinels' | 'explorers'>('all')
const sourceFilter = ref<'all' | 'obsidian' | 'json'>('all')
const page = ref(1)
const pageSize = 20

const MBTI_GROUPS: Record<string, string> = {
  INTJ: 'analysts', INTP: 'analysts', ENTJ: 'analysts', ENTP: 'analysts',
  INFJ: 'diplomats', INFP: 'diplomats', ENFJ: 'diplomats', ENFP: 'diplomats',
  ISTJ: 'sentinels', ISFJ: 'sentinels', ESTJ: 'sentinels', ESFJ: 'sentinels',
  ISTP: 'explorers', ISFP: 'explorers', ESTP: 'explorers', ESFP: 'explorers',
}

const mbtiGroupOptions = [
  { label: 'All Groups', value: 'all' },
  { label: 'Analysts (NT)', value: 'analysts' },
  { label: 'Diplomats (NF)', value: 'diplomats' },
  { label: 'Sentinels (S__J)', value: 'sentinels' },
  { label: 'Explorers (S__P)', value: 'explorers' },
]

const sourceOptions = [
  { label: 'All sources', value: 'all' },
  { label: 'From Obsidian', value: 'obsidian' },
  { label: 'JSON store', value: 'json' },
]

const filteredPersonas = computed<Persona[]>(() => {
  let result = personas.value
  const q = search.value.toLowerCase().trim()
  if (q) {
    result = result.filter((p) =>
      p.name.toLowerCase().includes(q)
      || (p.title?.toLowerCase().includes(q) ?? false)
      || (p.source?.toLowerCase().includes(q) ?? false)
      || (p.expertise_domains ?? []).some((d) => d.toLowerCase().includes(q)),
    )
  }
  if (mbtiGroupFilter.value !== 'all') {
    result = result.filter(
      (p) => MBTI_GROUPS[(p.mbti ?? '').toUpperCase()] === mbtiGroupFilter.value,
    )
  }
  if (sourceFilter.value !== 'all') {
    result = result.filter((p) => {
      const src = (p as Persona & { _source_store?: string })._source_store
      return src === sourceFilter.value
    })
  }
  return result
})

const totalFiltered = computed(() => filteredPersonas.value.length)

const paginatedPersonas = computed(() =>
  filteredPersonas.value.slice(
    (page.value - 1) * pageSize,
    page.value * pageSize,
  ),
)

const totalPages = computed(() =>
  Math.max(1, Math.ceil(totalFiltered.value / pageSize)),
)

watch([search, mbtiGroupFilter, sourceFilter], () => {
  page.value = 1
})

// ─── Render helpers ──────────────────────────────────────────────────────

function mbtiGroup(mbti: string | undefined): string {
  if (!mbti) return ''
  return MBTI_GROUPS[mbti.toUpperCase()] ?? ''
}

function mbtiColor(mbti: string | undefined): 'primary' | 'success' | 'warning' | 'error' | 'neutral' {
  const group = mbtiGroup(mbti)
  if (group === 'analysts') return 'primary'
  if (group === 'diplomats') return 'success'
  if (group === 'sentinels') return 'warning'
  if (group === 'explorers') return 'error'
  return 'neutral'
}

function agentCount(personaId: string): number {
  return usageData.value?.by_persona?.[personaId]?.agent_count ?? 0
}

const columns: TableColumn<Persona>[] = [
  { accessorKey: 'name',       header: 'Name' },
  { accessorKey: 'title',      header: 'Title' },
  { accessorKey: 'source',     header: 'Source' },
  { accessorKey: 'mbti',       header: 'MBTI' },
  { id: 'disc',                header: 'DISC' },
  { id: 'expertise',           header: 'Expertise' },
  { id: 'agents',              header: 'Agents' },
  { id: 'actions',             header: '' },
]

function goToPersona(id: string) {
  navigateTo(`/personas/${id}`)
}
</script>

<template>
  <UDashboardPanel id="personas">
    <template #header>
      <UDashboardNavbar title="Personas">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #trailing>
          <UBadge v-if="data?.total" :label="data.total" variant="subtle" />
          <UBadge
            v-if="data?.obsidian_available"
            label="Obsidian"
            icon="i-lucide-file-text"
            variant="soft"
            color="primary"
            size="xs"
            class="ml-2"
          />
        </template>
        <template #right>
          <UButton
            label="New Persona"
            icon="i-lucide-plus"
            size="sm"
            to="/personas/new"
          />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <DashboardState
        :status="status"
        :error="error"
        :empty="!personas.length"
        empty-title="No personas yet"
        empty-description="Create your first persona — use the AI builder or fill the form manually."
        empty-icon="i-lucide-user-plus"
        loading-label="Loading personas"
        :on-retry="() => refreshAll()"
      >
        <div class="flex flex-wrap items-center gap-3 mb-4">
          <UInput
            v-model="search"
            class="max-w-sm"
            icon="i-lucide-search"
            placeholder="Search by name, title, source, or expertise…"
            aria-label="Search personas"
          />

          <USelect
            v-model="mbtiGroupFilter"
            :items="mbtiGroupOptions"
            placeholder="MBTI group"
            class="min-w-44"
            aria-label="Filter by MBTI group"
          />

          <USelect
            v-model="sourceFilter"
            :items="sourceOptions"
            placeholder="Source"
            class="min-w-40"
            aria-label="Filter by source store"
          />

          <span class="ml-auto text-xs text-muted">
            {{ totalFiltered }} persona{{ totalFiltered !== 1 ? 's' : '' }}
          </span>
        </div>

        <UTable
          :data="paginatedPersonas"
          :columns="columns"
          :loading="status === 'pending'"
          class="shrink-0"
          :ui="{
            base: 'table-fixed border-separate border-spacing-0',
            thead: '[&>tr]:bg-elevated/50 [&>tr]:after:content-none',
            tbody: '[&>tr]:last:[&>td]:border-b-0 [&>tr]:cursor-pointer [&>tr]:hover:bg-elevated/50 [&>tr]:transition-colors',
            th: 'py-2 first:rounded-l-lg last:rounded-r-lg border-y border-default first:border-l last:border-r',
            td: 'border-b border-default',
          }"
          @select="(row: Persona) => goToPersona(row.id)"
        >
          <template #name-cell="{ row }">
            <span class="font-medium">{{ row.original.name }}</span>
          </template>
          <template #title-cell="{ row }">
            <span class="text-sm text-muted truncate">{{ row.original.title || '—' }}</span>
          </template>
          <template #source-cell="{ row }">
            <span class="text-xs text-muted font-mono truncate" :title="row.original.source">
              {{ row.original.source || '—' }}
            </span>
          </template>
          <template #mbti-cell="{ row }">
            <UBadge
              v-if="row.original.mbti"
              :label="row.original.mbti"
              :color="mbtiColor(row.original.mbti)"
              variant="subtle"
              size="xs"
            />
            <span v-else class="text-xs text-muted">—</span>
          </template>
          <template #disc-cell="{ row }">
            <span class="font-mono text-xs">
              {{ row.original.disc?.primary || '—' }}{{ row.original.disc?.secondary ? `/${row.original.disc.secondary}` : '' }}
            </span>
          </template>
          <template #expertise-cell="{ row }">
            <div class="flex flex-wrap gap-1">
              <UBadge
                v-for="e in (row.original.expertise_domains ?? []).slice(0, 2)"
                :key="e"
                :label="e"
                variant="soft"
                size="xs"
              />
              <UBadge
                v-if="(row.original.expertise_domains ?? []).length > 2"
                :label="`+${(row.original.expertise_domains ?? []).length - 2}`"
                variant="outline"
                size="xs"
              />
            </div>
          </template>
          <template #agents-cell="{ row }">
            <UBadge
              v-if="agentCount(row.original.id) > 0"
              :label="`${agentCount(row.original.id)}`"
              color="primary"
              variant="subtle"
              size="xs"
            />
            <span v-else class="text-xs text-muted">0</span>
          </template>
          <template #actions-cell="{ row }">
            <UButton
              size="xs"
              variant="ghost"
              icon="i-lucide-arrow-right"
              aria-label="Open persona detail"
              @click.stop="goToPersona(row.original.id)"
            />
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
      </DashboardState>
    </template>
  </UDashboardPanel>
</template>
