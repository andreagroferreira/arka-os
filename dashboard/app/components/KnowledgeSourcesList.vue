<script setup lang="ts">
// PR88c v3.25.0 — Listing + management of indexed knowledge sources.
//
// Sits below the ingest UI on /knowledge. Loads GET /api/knowledge/sources
// (returns `{sources: [{source, chunks}], total}`), supports search,
// per-row Delete (DELETE /api/knowledge/sources?source=...). Pagination
// inline.

interface SourceRow {
  source: string
  chunks: number
  id: string
  title?: string
  type?: string
  has_media?: boolean
  duration?: number
  status?: string
}

const { fetchApi, apiBase } = useApi()
const toast = useToast()
const confirmDialog = useConfirmDialog()

const { data, status, error, refresh } = await fetchApi<{
  sources: SourceRow[]
  total: number
}>('/api/knowledge/sources')

const sources = computed(() => data.value?.sources ?? [])
const search = ref('')
const page = ref(1)
const pageSize = 15

const filtered = computed(() => {
  const q = search.value.toLowerCase().trim()
  if (!q) return sources.value
  return sources.value.filter((s) => s.source.toLowerCase().includes(q))
})
const totalPages = computed(() => Math.max(1, Math.ceil(filtered.value.length / pageSize)))
const paged = computed(() =>
  filtered.value.slice((page.value - 1) * pageSize, page.value * pageSize),
)

watch(search, () => { page.value = 1 })

async function remove(row: SourceRow) {
  const ok = await confirmDialog({
    title: 'Delete source?',
    description: `Removes ${row.chunks} chunk${row.chunks === 1 ? '' : 's'} from the vector store. This cannot be undone.`,
    confirmLabel: 'Delete',
    cancelLabel: 'Cancel',
    variant: 'danger',
  })
  if (!ok) return
  try {
    const res = await $fetch<{ deleted?: number, error?: string }>(
      `${apiBase}/api/knowledge/sources`,
      { method: 'DELETE', query: { source: row.source } },
    )
    if (res.error) throw new Error(res.error)
    toast.add({
      title: `Removed ${res.deleted ?? 0} chunks`,
      description: row.source,
      color: 'success',
    })
    await refresh()
  } catch (err) {
    toast.add({
      title: 'Delete failed',
      description: err instanceof Error ? err.message : 'unknown error',
      color: 'error',
    })
  }
}

function sourceLabel(src: string): string {
  if (src.startsWith('http')) {
    try {
      const u = new URL(src)
      return u.hostname + u.pathname
    } catch {
      return src
    }
  }
  return src
}

const typeColorMap: Record<string, 'error' | 'primary' | 'warning' | 'success' | 'neutral'> = {
  youtube: 'error',
  web: 'primary',
  pdf: 'warning',
  audio: 'success',
  markdown: 'neutral',
  video: 'error'
}
</script>

<template>
  <UCard>
    <template #header>
      <div class="flex items-center justify-between gap-3">
        <div>
          <h3 class="text-lg font-bold">Indexed sources</h3>
          <p class="text-xs text-muted mt-0.5">
            Every distinct source contributing chunks to the vector store.
            <span v-if="data?.total">{{ data.total }} total.</span>
          </p>
        </div>
        <UButton
          icon="i-lucide-refresh-cw"
          variant="ghost"
          size="sm"
          aria-label="Refresh"
          :loading="status === 'pending'"
          @click="refresh"
        />
      </div>
    </template>

    <div v-if="error" class="py-6 text-center text-sm text-error">
      Failed to load sources.
    </div>
    <div v-else-if="!sources.length" class="py-6 text-center text-sm text-muted">
      <UIcon name="i-lucide-database" class="size-6 mx-auto mb-2" />
      No sources indexed yet. Use the ingest panel above to add content.
    </div>
    <div v-else class="space-y-3">
      <UInput
        v-model="search"
        icon="i-lucide-search"
        placeholder="Filter by source URL or path…"
        class="w-full"
      />

      <ul class="space-y-1.5">
        <li
          v-for="row in paged"
          :key="row.id"
          class="flex items-center gap-2 rounded-lg border border-default p-2.5 hover:border-primary/40 transition-colors"
        >
          <NuxtLink
            :to="`/knowledge/${row.id}`"
            class="flex items-center gap-3 flex-1 min-w-0"
          >
            <UIcon
              :name="row.source.startsWith('http') ? 'i-lucide-link' : 'i-lucide-file-text'"
              class="size-4 text-muted shrink-0"
            />
            <div class="flex-1 min-w-0">
              <p class="text-sm truncate text-highlighted" :title="row.source">
                {{ row.title || sourceLabel(row.source) }}
              </p>
            </div>
            <UBadge
              v-if="row.type"
              :label="row.type"
              :color="typeColorMap[row.type] ?? 'neutral'"
              variant="subtle"
              size="xs"
            />
          </NuxtLink>
          <UBadge :label="`${row.chunks} chunk${row.chunks === 1 ? '' : 's'}`" variant="subtle" size="xs" />
          <UButton
            icon="i-lucide-trash-2"
            color="error"
            variant="ghost"
            size="xs"
            aria-label="Delete source"
            @click.stop.prevent="remove(row)"
          />
        </li>
      </ul>

      <div v-if="totalPages > 1" class="flex items-center justify-center pt-2">
        <UPagination
          :page="page"
          :total="filtered.length"
          :items-per-page="pageSize"
          @update:page="(val) => page = val"
        />
      </div>
    </div>
  </UCard>
</template>
