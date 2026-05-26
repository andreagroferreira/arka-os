<script setup lang="ts">
// PR78 v2.96.0 — Personas list rebuilt as a TABLE.
//
// Mirrors agents/index.vue structure. Click a row → navigates to
// /personas/{id} (dedicated detail page, not a drawer). Replaces the
// card grid + slide-over drawer that PR74/77 shipped.

import type { TableColumn } from '@nuxt/ui'
import type { Persona } from '~/types'

const { fetchApi, apiBase } = useApi()

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
  if (favoritesOnly.value) {
    result = result.filter((p) => favs.isPersonaFavorite(p.id))
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
  { id: 'select',              header: '' },
  { id: 'favorite',            header: '' },
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

// PR86a v3.15.0 — favorites.
const favs = useFavorites()
await favs.load()
const favoritesOnly = ref(false)

// PR93c v3.45.0 — bulk export only selected rows.
const exportingSelected = ref(false)
async function exportSelectedZip() {
  if (selected.value.size === 0) return
  const ids = Array.from(selected.value).join(',')
  exportingSelected.value = true
  try {
    const blob = await $fetch<Blob>(
      `${apiBase}/api/personas/export-all.zip`,
      { query: { ids }, responseType: 'blob' },
    )
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `arkaos-personas-selected-${selected.value.size}.zip`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
    toast.add({
      title: `Exported ${selected.value.size} persona${selected.value.size === 1 ? '' : 's'}`,
      color: 'success',
      icon: 'i-lucide-archive',
    })
  } catch (err) {
    toast.add({
      title: 'Export failed',
      description: err instanceof Error ? err.message : 'unknown error',
      color: 'error',
    })
  } finally {
    exportingSelected.value = false
  }
}

// PR92a v3.39.0 — bulk export every persona as a zip.
const exportingZip = ref(false)
async function exportAllAsZip() {
  exportingZip.value = true
  try {
    const blob = await $fetch<Blob>(
      `${apiBase}/api/personas/export-all.zip`,
      { responseType: 'blob' },
    )
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'arkaos-personas.zip'
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
    toast.add({
      title: 'ZIP downloaded',
      description: 'arkaos-personas.zip',
      color: 'success',
      icon: 'i-lucide-archive',
    })
  } catch (err) {
    toast.add({
      title: 'Export failed',
      description: err instanceof Error ? err.message : 'unknown error',
      color: 'error',
    })
  } finally {
    exportingZip.value = false
  }
}

// PR87b v3.20.0 — import .md persona files.
// PR91b v3.36.0 — extended with URL import.
const importInput = ref<HTMLInputElement | null>(null)
const importing = ref(false)
const urlImportOpen = ref(false)
const urlImportText = ref('')

function triggerImport() {
  importInput.value?.click()
}

async function runUrlImport() {
  const urls = urlImportText.value
    .split('\n')
    .map((s) => s.trim())
    .filter(Boolean)
  if (urls.length === 0) return
  importing.value = true
  try {
    const res = await $fetch<{
      imported: number
      failed: number
      results: Array<{ filename: string, status: string, id?: string, error?: string }>
      error?: string
    }>(`${apiBase}/api/personas/import`, { method: 'POST', body: { urls } })
    if (res.error) throw new Error(res.error)
    toast.add({
      title: res.imported > 0
        ? `Imported ${res.imported} persona${res.imported === 1 ? '' : 's'}`
        : 'Nothing imported',
      description: res.failed > 0 ? `${res.failed} failed` : undefined,
      color: res.imported > 0 && res.failed === 0
        ? 'success'
        : res.imported > 0 ? 'warning' : 'error',
      icon: 'i-lucide-globe',
    })
    await refreshAll()
    urlImportText.value = ''
    urlImportOpen.value = false
  } catch (err) {
    toast.add({
      title: 'URL import failed',
      description: err instanceof Error ? err.message : 'unknown error',
      color: 'error',
    })
  } finally {
    importing.value = false
  }
}

async function onImportFiles(event: Event) {
  const target = event.target as HTMLInputElement
  const files = Array.from(target.files ?? [])
  target.value = ''
  if (files.length === 0) return
  importing.value = true
  try {
    const payload = await Promise.all(
      files.map(async (f) => ({
        name: f.name,
        content: await f.text(),
      })),
    )
    const res = await $fetch<{
      imported: number
      failed: number
      results: Array<{ filename: string, status: string, id?: string, error?: string }>
      error?: string
    }>(`${apiBase}/api/personas/import`, { method: 'POST', body: { files: payload } })
    if (res.error) throw new Error(res.error)
    toast.add({
      title: res.imported > 0
        ? `Imported ${res.imported} persona${res.imported === 1 ? '' : 's'}`
        : 'Nothing imported',
      description: res.failed > 0 ? `${res.failed} failed` : undefined,
      color: res.imported > 0 && res.failed === 0
        ? 'success'
        : res.imported > 0 ? 'warning' : 'error',
      icon: 'i-lucide-file-down',
    })
    await refreshAll()
  } catch (err) {
    toast.add({
      title: 'Import failed',
      description: err instanceof Error ? err.message : 'unknown error',
      color: 'error',
    })
  } finally {
    importing.value = false
  }
}

// PR83b v3.4.0 — bulk selection + delete.
const toast = useToast()
const confirmDialog = useConfirmDialog()
const selected = ref<Set<string>>(new Set())
const bulkDeleting = ref(false)

function toggleSelected(id: string) {
  if (selected.value.has(id)) selected.value.delete(id)
  else selected.value.add(id)
  selected.value = new Set(selected.value)
}

function toggleAllVisible() {
  const visibleIds = paginatedPersonas.value.map((p) => p.id)
  const allSelected = visibleIds.every((id) => selected.value.has(id))
  const next = new Set(selected.value)
  for (const id of visibleIds) {
    if (allSelected) next.delete(id)
    else next.add(id)
  }
  selected.value = next
}

const allVisibleSelected = computed(() => {
  const visibleIds = paginatedPersonas.value.map((p) => p.id)
  return visibleIds.length > 0 && visibleIds.every((id) => selected.value.has(id))
})

function clearSelection() {
  selected.value = new Set()
}

async function bulkDelete() {
  if (selected.value.size === 0) return
  const ids = Array.from(selected.value)
  const ok = await confirmDialog({
    title: `Delete ${ids.length} persona${ids.length === 1 ? '' : 's'}?`,
    description: 'Personas will be removed from the JSON store and the Obsidian vault. This cannot be undone.',
    confirmLabel: `Delete ${ids.length}`,
    cancelLabel: 'Cancel',
    variant: 'danger',
  })
  if (!ok) return
  bulkDeleting.value = true
  const results = await Promise.allSettled(
    ids.map((id) =>
      $fetch<{ deleted?: boolean, trash_id?: string, error?: string }>(
        `${apiBase}/api/personas/${id}`,
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
      title: `Deleted ${successes.length} persona${successes.length === 1 ? '' : 's'}`,
      description: failures > 0 ? `${failures} failed` : 'Undo from /trash within 50 ops.',
      color: failures > 0 ? 'warning' : 'success',
      actions: trashIds.length > 0
        ? [{ label: 'Undo', icon: 'i-lucide-rotate-ccw', onClick: () => undoTrashIds(trashIds) }]
        : undefined,
    })
  } else {
    toast.add({
      title: 'Nothing deleted',
      color: 'error',
    })
  }
  clearSelection()
  bulkDeleting.value = false
  await refreshAll()
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
            label="Archetypes"
            icon="i-lucide-sparkles"
            variant="ghost"
            size="sm"
            to="/personas/archetypes"
          />
          <UButton
            label="Export ZIP"
            icon="i-lucide-archive"
            variant="ghost"
            size="sm"
            :loading="exportingZip"
            @click="exportAllAsZip"
          />
          <UDropdownMenu
            :items="[
              { label: 'Pick .md files…', icon: 'i-lucide-file-up', onSelect: triggerImport },
              { label: 'From URLs…', icon: 'i-lucide-globe', onSelect: () => urlImportOpen = true },
            ]"
          >
            <UButton
              label="Import"
              icon="i-lucide-file-up"
              variant="soft"
              size="sm"
              :loading="importing"
              trailing-icon="i-lucide-chevron-down"
            />
          </UDropdownMenu>
          <input
            ref="importInput"
            type="file"
            accept=".md,text/markdown"
            multiple
            class="hidden"
            @change="onImportFiles"
          />
          <UModal v-model:open="urlImportOpen" title="Import from URLs">
            <template #content>
              <UCard>
                <template #header>
                  <h2 class="text-lg font-bold">Import personas from URLs</h2>
                  <p class="text-xs text-muted mt-0.5">
                    One raw .md URL per line. Files must have YAML
                    frontmatter with <code>type: persona</code>.
                  </p>
                </template>
                <UTextarea
                  v-model="urlImportText"
                  :rows="6"
                  placeholder="https://raw.githubusercontent.com/owner/repo/main/personas/alex.md"
                  class="w-full font-mono text-sm"
                />
                <template #footer>
                  <div class="flex items-center justify-end gap-2">
                    <UButton label="Cancel" variant="ghost" :disabled="importing" @click="urlImportOpen = false" />
                    <UButton
                      label="Import"
                      icon="i-lucide-globe"
                      color="primary"
                      :loading="importing"
                      :disabled="!urlImportText.trim()"
                      @click="runUrlImport"
                    />
                  </div>
                </template>
              </UCard>
            </template>
          </UModal>
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

          <UButton
            :label="favoritesOnly ? 'All' : 'Favorites'"
            icon="i-lucide-star"
            :color="favoritesOnly ? 'warning' : 'neutral'"
            :variant="favoritesOnly ? 'soft' : 'outline'"
            size="sm"
            @click="favoritesOnly = !favoritesOnly"
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
          @select="(row: { original: Persona }) => goToPersona(row.original.id)"
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
              icon="i-lucide-star"
              :color="favs.isPersonaFavorite(row.original.id) ? 'warning' : 'neutral'"
              :variant="favs.isPersonaFavorite(row.original.id) ? 'soft' : 'ghost'"
              size="xs"
              :aria-label="favs.isPersonaFavorite(row.original.id) ? 'Unfavorite' : 'Favorite'"
              @click.stop="favs.toggle('personas', row.original.id)"
            />
          </template>
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
              label="Export ZIP"
              icon="i-lucide-archive"
              size="sm"
              variant="soft"
              :loading="exportingSelected"
              @click="exportSelectedZip"
            />
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
