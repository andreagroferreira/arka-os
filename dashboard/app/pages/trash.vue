<script setup lang="ts">
// PR85b v3.12.0 — Trash listing + Restore / Discard.

interface TrashEntry {
  id: string
  kind: 'agent-delete' | 'persona-delete' | 'agent-move'
  item_id: string
  timestamp: number
  original_path: string
  new_path: string | null
  has_payload: boolean
}

const { fetchApi, apiBase } = useApi()
const toast = useToast()
const confirmDialog = useConfirmDialog()

const { data, status, error, refresh } = await fetchApi<{ entries: TrashEntry[] }>(
  '/api/trash?limit=50'
)

async function restore(entry: TrashEntry) {
  try {
    const res = await $fetch<{ restored?: boolean, error?: string }>(
      `${apiBase}/api/trash/${entry.id}/restore`,
      { method: 'POST' }
    )
    if (res.error) throw new Error(res.error)
    toast.add({
      title: 'Restored',
      description: kindLabel(entry.kind) + ' restored.',
      color: 'success',
      icon: 'i-lucide-rotate-ccw'
    })
    await refresh()
  } catch (err) {
    toast.add({
      title: 'Restore failed',
      description: err instanceof Error ? err.message : 'unknown error',
      color: 'error'
    })
  }
}

async function discard(entry: TrashEntry) {
  const ok = await confirmDialog({
    title: 'Discard trash entry?',
    description: `${kindLabel(entry.kind)} for ${entry.item_id} will be permanently dropped.`,
    confirmLabel: 'Discard',
    cancelLabel: 'Cancel',
    variant: 'danger'
  })
  if (!ok) return
  try {
    await $fetch(`${apiBase}/api/trash/${entry.id}`, { method: 'DELETE' })
    toast.add({ title: 'Discarded', color: 'success' })
    await refresh()
  } catch (err) {
    toast.add({
      title: 'Discard failed',
      description: err instanceof Error ? err.message : 'unknown error',
      color: 'error'
    })
  }
}

function kindLabel(kind: string): string {
  return {
    'agent-delete': 'Agent delete',
    'persona-delete': 'Persona delete',
    'agent-move': 'Agent move'
  }[kind] ?? kind
}

function kindColor(kind: string): 'error' | 'warning' | 'primary' | 'neutral' {
  return ({
    'agent-delete': 'error',
    'persona-delete': 'error',
    'agent-move': 'warning'
  } as const)[kind] ?? 'neutral'
}

function formatRelative(ts: number): string {
  const diff = Date.now() - ts * 1000
  const minutes = Math.floor(diff / 60_000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}
</script>

<template>
  <UDashboardPanel id="trash">
    <template #header>
      <UDashboardNavbar title="Trash">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #trailing>
          <UBadge
            v-if="data?.entries?.length"
            :label="`${data.entries.length} item${data.entries.length === 1 ? '' : 's'}`"
            variant="subtle"
          />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <DashboardState
        :status="status"
        :error="error"
        :empty="!data?.entries?.length"
        empty-title="Trash is empty"
        empty-description="Deleted agents, personas, and department moves show up here for 50 entries."
        empty-icon="i-lucide-trash"
        loading-label="Loading trash"
        :on-retry="() => refresh()"
      >
        <div class="space-y-2 max-w-4xl">
          <div
            v-for="entry in data?.entries ?? []"
            :key="entry.id"
            class="rounded-lg border border-default p-3 flex items-center gap-3 hover:border-primary/40 transition-colors"
          >
            <UBadge
              :label="kindLabel(entry.kind)"
              :color="kindColor(entry.kind)"
              variant="subtle"
              size="sm"
            />
            <div class="flex-1 min-w-0">
              <p class="text-sm font-mono font-semibold truncate">
                {{ entry.item_id }}
              </p>
              <p class="text-xs text-muted truncate" :title="entry.original_path">
                {{ entry.original_path }}<span v-if="entry.new_path"> → {{ entry.new_path }}</span>
              </p>
            </div>
            <span class="text-xs text-muted shrink-0">{{ formatRelative(entry.timestamp) }}</span>
            <UButton
              label="Restore"
              icon="i-lucide-rotate-ccw"
              size="xs"
              variant="soft"
              color="primary"
              @click="restore(entry)"
            />
            <UButton
              icon="i-lucide-x"
              size="xs"
              variant="ghost"
              color="neutral"
              aria-label="Discard"
              @click="discard(entry)"
            />
          </div>
        </div>
      </DashboardState>
    </template>
  </UDashboardPanel>
</template>
