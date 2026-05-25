<script setup lang="ts">
// PR67 v2.84.0 — Tasks page rewritten against /api/jobs.
//
// The legacy /api/tasks endpoint returns the deprecated TaskManager
// data, which has no live updates and no cancel. The SQLite job queue
// (/api/jobs) is the real workhorse — knowledge ingest fans out into
// jobs, WebSocket broadcasts every progress event, DELETE /api/jobs/{id}
// cancels queued work. This page now consumes the real thing.
//
// What changed vs the previous tasks.vue:
//   - Polls /api/jobs (jobs are the new tasks)
//   - Subscribes to /ws/tasks for live progress + status flips
//   - Cancel button on queued/processing rows
//   - Empty state suggests a real command (Knowledge → ingest) instead
//     of the dead-link "npx arkaos index" hint
//   - DashboardState (PR64) wraps loading/error/empty consistently

import type { TableColumn } from '@nuxt/ui'
import type { Job, JobSummary } from '~/types'

const { fetchApi, apiBase } = useApi()
const toast = useToast()

const {
  data,
  status,
  error,
  refresh,
} = await fetchApi<{ jobs: Job[], summary: JobSummary }>('/api/jobs?limit=200')

const jobs = ref<Job[]>(data.value?.jobs ?? [])
const summary = ref<JobSummary>(data.value?.summary ?? {
  total: 0, queued: 0, processing: 0, completed: 0, failed: 0,
})

watch(data, (d) => {
  if (!d) return
  jobs.value = d.jobs ?? []
  summary.value = d.summary ?? {
    total: 0, queued: 0, processing: 0, completed: 0, failed: 0,
  }
})

// ─── Filter tabs ─────────────────────────────────────────────────────────

const activeTab = ref<'all' | 'active' | 'queued' | 'completed' | 'failed'>('all')

const tabItems = [
  { label: 'All', value: 'all' as const },
  { label: 'Active', value: 'active' as const },
  { label: 'Queued', value: 'queued' as const },
  { label: 'Completed', value: 'completed' as const },
  { label: 'Failed', value: 'failed' as const },
]

const ACTIVE_STATUSES: Job['status'][] = [
  'processing', 'downloading', 'transcribing', 'embedding',
]

const filteredJobs = computed<Job[]>(() => {
  if (activeTab.value === 'all') return jobs.value
  if (activeTab.value === 'active') {
    return jobs.value.filter((j) => ACTIVE_STATUSES.includes(j.status))
  }
  return jobs.value.filter((j) => j.status === activeTab.value)
})

const CANCELLABLE: Job['status'][] = ['queued', 'processing']
function isCancellable(job: Job): boolean {
  return CANCELLABLE.includes(job.status)
}

// ─── WebSocket — live updates ────────────────────────────────────────────

let ws: WebSocket | null = null
const wsConnected = ref(false)

function connectWebSocket() {
  if (ws && ws.readyState === WebSocket.OPEN) return
  const wsUrl = apiBase.replace('http://', 'ws://').replace('https://', 'wss://') + '/ws/tasks'
  ws = new WebSocket(wsUrl)
  ws.onopen = () => { wsConnected.value = true }
  ws.onclose = () => { wsConnected.value = false }
  ws.onerror = () => { wsConnected.value = false }
  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data) as {
        type: string
        job_id?: string
        progress?: number
        message?: string
        status?: Job['status']
        error?: string
        chunks_created?: number
      }
      if (!msg.job_id) return
      const idx = jobs.value.findIndex((j) => j.id === msg.job_id)
      if (idx === -1) {
        // We don't have the row yet (new job spawned mid-session).
        // Refetch the list so it shows up.
        refresh()
        return
      }
      const current = jobs.value[idx]
      if (!current) return
      const next: Job = { ...current }
      if (msg.type === 'job_progress') {
        if (typeof msg.progress === 'number') next.progress = msg.progress
        if (typeof msg.message === 'string') next.message = msg.message
        if (msg.status) next.status = msg.status
      } else if (msg.type === 'job_complete') {
        next.status = 'completed'
        next.progress = 100
        if (typeof msg.chunks_created === 'number') next.chunks_created = msg.chunks_created
      } else if (msg.type === 'job_failed') {
        next.status = 'failed'
        if (typeof msg.error === 'string') next.error = msg.error
      } else if (msg.type === 'job_cancelled') {
        next.status = 'cancelled'
      }
      jobs.value.splice(idx, 1, next)
    } catch {
      /* ignore malformed messages */
    }
  }
}

function disconnectWebSocket() {
  if (!ws) return
  try { ws.close() } catch { /* already closed */ }
  ws = null
  wsConnected.value = false
}

onMounted(() => {
  connectWebSocket()
})

onBeforeUnmount(() => {
  disconnectWebSocket()
})

// ─── Cancel ──────────────────────────────────────────────────────────────

const cancelling = ref<Set<string>>(new Set())

async function cancelJob(job: Job) {
  if (!isCancellable(job)) return
  cancelling.value.add(job.id)
  try {
    const res = await $fetch<{ cancelled?: boolean, error?: string }>(
      `${apiBase}/api/jobs/${job.id}`,
      { method: 'DELETE' },
    )
    if (res.cancelled) {
      // WS will broadcast 'job_cancelled' — handler will flip the row.
      // Refresh as a safety net in case the WS message races.
      await refresh()
      toast.add({
        title: 'Job cancelled',
        description: job.source || job.id,
        color: 'success',
      })
    } else {
      toast.add({
        title: 'Cancel rejected',
        description: res.error || 'Only queued jobs can be cancelled.',
        color: 'warning',
      })
    }
  } catch (err) {
    toast.add({
      title: 'Cancel failed',
      description: err instanceof Error ? err.message : 'unknown error',
      color: 'error',
    })
  } finally {
    cancelling.value.delete(job.id)
  }
}

// ─── Render helpers ──────────────────────────────────────────────────────

type StatusColor = 'success' | 'error' | 'primary' | 'warning' | 'neutral'

const STATUS_COLOR: Record<Job['status'], StatusColor> = {
  queued: 'neutral',
  processing: 'primary',
  downloading: 'primary',
  transcribing: 'primary',
  embedding: 'primary',
  completed: 'success',
  failed: 'error',
  cancelled: 'warning',
}

function statusColor(s: Job['status']): StatusColor {
  return STATUS_COLOR[s] ?? 'neutral'
}

function formatDate(dateStr: string) {
  if (!dateStr) return '-'
  try {
    return new Intl.DateTimeFormat('en-US', {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    }).format(new Date(dateStr))
  } catch {
    return dateStr
  }
}

function truncate(value: string, max = 60): string {
  if (!value) return ''
  return value.length > max ? value.slice(0, max - 1) + '…' : value
}

const columns: TableColumn<Job>[] = [
  { accessorKey: 'type',       header: 'Type' },
  { accessorKey: 'source',     header: 'Source' },
  { accessorKey: 'status',     header: 'Status' },
  { accessorKey: 'progress',   header: 'Progress' },
  { accessorKey: 'created_at', header: 'Created' },
  { accessorKey: 'actions',    header: '' },
]
</script>

<template>
  <UDashboardPanel id="tasks">
    <template #header>
      <UDashboardNavbar title="Tasks">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #trailing>
          <UBadge
            :label="wsConnected ? 'Live' : 'Offline'"
            :color="wsConnected ? 'success' : 'neutral'"
            variant="subtle"
            size="xs"
            :icon="wsConnected ? 'i-lucide-radio-tower' : 'i-lucide-radio'"
          />
        </template>
        <template #right>
          <UButton
            label="Refresh"
            variant="ghost"
            icon="i-lucide-refresh-cw"
            size="sm"
            @click="refresh()"
          />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <DashboardState
        :status="status"
        :error="error"
        loading-label="Loading jobs"
        :on-retry="() => refresh()"
      >
        <!-- Summary cards -->
        <div class="grid grid-cols-2 gap-4 sm:grid-cols-5">
          <div class="rounded-lg border border-default p-4 text-center">
            <p class="text-2xl font-semibold text-highlighted">{{ summary.total }}</p>
            <p class="text-xs text-muted">Total</p>
          </div>
          <div class="rounded-lg border border-default p-4 text-center">
            <p class="text-2xl font-semibold text-primary">{{ summary.processing ?? 0 }}</p>
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
          <div class="rounded-lg border border-default p-4 text-center">
            <p class="text-2xl font-semibold text-red-500">{{ summary.failed }}</p>
            <p class="text-xs text-muted">Failed</p>
          </div>
        </div>

        <!-- Filter tabs -->
        <div class="mt-6">
          <UTabs
            :items="tabItems"
            :model-value="activeTab"
            @update:model-value="activeTab = $event as 'all' | 'active' | 'queued' | 'completed' | 'failed'"
          />
        </div>

        <!-- Global empty (no jobs at all) -->
        <DashboardState
          :status="status"
          :empty="!jobs.length"
          empty-title="No jobs yet"
          empty-icon="i-lucide-list-checks"
        >
          <template #empty>
            <UIcon name="i-lucide-list-checks" class="size-16 text-muted" />
            <h3 class="text-lg font-semibold text-highlighted">No jobs yet</h3>
            <p class="text-sm text-muted text-center max-w-md">
              Jobs are created when you ingest content. Head to the Knowledge tab and paste a URL or upload a file — each one runs as a job here in real time.
            </p>
            <UButton
              to="/knowledge"
              label="Open Knowledge"
              icon="i-lucide-brain"
              size="md"
              class="mt-2"
            />
          </template>

          <!-- Filtered empty (jobs exist but not in this tab) -->
          <div
            v-if="!filteredJobs.length"
            class="mt-6 flex flex-col items-center justify-center gap-4 py-12"
          >
            <UIcon name="i-lucide-filter-x" class="size-12 text-muted" />
            <p class="text-sm text-muted">No {{ activeTab }} jobs found.</p>
          </div>

          <!-- Job table -->
          <div v-else class="mt-4">
            <UTable
              :data="filteredJobs"
              :columns="columns"
              :loading="status === 'pending'"
              class="shrink-0"
              :ui="{
                base: 'table-fixed border-separate border-spacing-0',
                thead: '[&>tr]:bg-elevated/50 [&>tr]:after:content-none',
                tbody: '[&>tr]:last:[&>td]:border-b-0',
                th: 'py-2 first:rounded-l-lg last:rounded-r-lg border-y border-default first:border-l last:border-r',
                td: 'border-b border-default',
              }"
            >
              <template #type-cell="{ row }">
                <UBadge :label="row.original.type || 'unknown'" variant="subtle" color="primary" size="sm" />
              </template>
              <template #source-cell="{ row }">
                <span class="text-sm font-mono" :title="row.original.source">
                  {{ truncate(row.original.source, 50) }}
                </span>
                <p v-if="row.original.message" class="text-xs text-muted mt-0.5">
                  {{ truncate(row.original.message, 60) }}
                </p>
                <p v-if="row.original.error" class="text-xs text-red-400 mt-0.5">
                  {{ truncate(row.original.error, 80) }}
                </p>
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
                  <span class="text-xs text-muted font-mono w-8 text-right">
                    {{ row.original.progress }}%
                  </span>
                </div>
              </template>
              <template #created_at-cell="{ row }">
                <span class="text-xs text-muted">{{ formatDate(row.original.created_at) }}</span>
              </template>
              <template #actions-cell="{ row }">
                <UButton
                  v-if="isCancellable(row.original)"
                  icon="i-lucide-x"
                  variant="ghost"
                  color="error"
                  size="xs"
                  :loading="cancelling.has(row.original.id)"
                  aria-label="Cancel job"
                  @click="cancelJob(row.original)"
                />
              </template>
            </UTable>
          </div>
        </DashboardState>
      </DashboardState>
    </template>
  </UDashboardPanel>
</template>
