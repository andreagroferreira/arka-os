<script setup lang="ts">
import type { KnowledgeStats, KnowledgeSearchResult, IngestRequest, IngestResponse, IngestTask } from '~/types'

const { fetchApi, apiBase } = useApi()

const { data: stats, status, error, refresh } = await fetchApi<KnowledgeStats>('/api/knowledge/stats')

const isIndexed = computed(() => (stats.value?.total_chunks ?? 0) > 0)

// --- Ingest Form State ---
const ingestUrl = ref('')
const ingestFile = ref<File | null>(null)
const ingestFileInputRef = ref<HTMLInputElement | null>(null)
const isIngesting = ref(false)
const ingestError = ref<string | null>(null)
const isDragging = ref(false)
const pasteText = ref('')
const pasteTitle = ref('')

const activeInputMode = ref<'url' | 'file' | 'text' | 'research'>('url')

const inputModes = [
  { label: 'URL', value: 'url' as const, icon: 'i-lucide-link' },
  { label: 'File', value: 'file' as const, icon: 'i-lucide-upload' },
  { label: 'Text', value: 'text' as const, icon: 'i-lucide-type' },
  { label: 'Research', value: 'research' as const, icon: 'i-lucide-search' },
]

function handleDrop(e: DragEvent) {
  isDragging.value = false
  const file = e.dataTransfer?.files?.[0]
  if (file) {
    ingestFile.value = file
    ingestUrl.value = ''
  }
}

type SourceType = IngestRequest['type'] | null

const detectedType = computed<SourceType>(() => {
  const url = ingestUrl.value.trim()
  if (url) {
    if (/^https?:\/\/(www\.)?(youtube\.com|youtu\.be)\//i.test(url)) return 'youtube'
    if (/\.pdf(\?.*)?$/i.test(url)) return 'pdf'
    if (/\.(mp3|wav|m4a|ogg|flac)(\?.*)?$/i.test(url)) return 'audio'
    if (/\.(md|mdx)(\?.*)?$/i.test(url)) return 'markdown'
    if (/^https?:\/\//i.test(url)) return 'web'
  }
  if (ingestFile.value) {
    const name = ingestFile.value.name.toLowerCase()
    if (name.endsWith('.pdf')) return 'pdf'
    if (/\.(mp3|wav|m4a|ogg|flac)$/.test(name)) return 'audio'
    if (/\.(md|mdx)$/.test(name)) return 'markdown'
  }
  return null
})

const typeColorMap: Record<string, 'error' | 'primary' | 'warning' | 'success' | 'neutral'> = {
  youtube: 'error',
  web: 'primary',
  pdf: 'warning',
  audio: 'success',
  markdown: 'neutral'
}

const typeIconMap: Record<string, string> = {
  youtube: 'i-lucide-youtube',
  web: 'i-lucide-globe',
  pdf: 'i-lucide-file-text',
  audio: 'i-lucide-headphones',
  markdown: 'i-lucide-file-code'
}

function handleFileSelect(event: Event) {
  const target = event.target as HTMLInputElement
  ingestFile.value = target.files?.[0] ?? null
  if (ingestFile.value) {
    ingestUrl.value = ''
  }
}

function clearFile() {
  ingestFile.value = null
  if (ingestFileInputRef.value) {
    ingestFileInputRef.value.value = ''
  }
}

const canIngest = computed(() => {
  return detectedType.value !== null && !isIngesting.value
})

// --- Active Ingestion Tracking via WebSocket ---
const activeTask = ref<IngestTask | null>(null)
let ws: WebSocket | null = null

// Persist active task ID across page navigation
const ACTIVE_TASK_KEY = 'arkaos_active_ingest_task'

async function restoreActiveTask() {
  const savedId = localStorage.getItem(ACTIVE_TASK_KEY)
  if (!savedId) return
  try {
    const task = await $fetch<any>(`${apiBase}/api/tasks/${savedId}`)
    if (task && task.status && !['completed', 'failed', 'cancelled'].includes(task.status)) {
      activeTask.value = task
      isIngesting.value = true
      connectWebSocket()
    } else {
      localStorage.removeItem(ACTIVE_TASK_KEY)
    }
  } catch {
    localStorage.removeItem(ACTIVE_TASK_KEY)
  }
}

onMounted(() => {
  restoreActiveTask()
})

function connectWebSocket() {
  if (ws && ws.readyState === WebSocket.OPEN) return

  const wsUrl = apiBase.replace('http://', 'ws://').replace('https://', 'wss://') + '/ws/tasks'
  ws = new WebSocket(wsUrl)

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      const jobId = data.job_id || data.task_id

      // Update active task if it matches
      if (activeTask.value && jobId === activeTask.value.id) {
        if (data.type === 'job_progress' || data.type === 'task_progress') {
          activeTask.value.progress_percent = data.progress
          activeTask.value.progress_message = data.message
          activeTask.value.status = data.status
        } else if (data.type === 'job_complete' || data.type === 'task_complete') {
          activeTask.value.status = 'completed'
          activeTask.value.progress_percent = 100
          activeTask.value.output_data = { chunks_created: data.chunks_created }
          isIngesting.value = false
          localStorage.removeItem(ACTIVE_TASK_KEY)
          refresh()
          fetchJobs()
        } else if (data.type === 'job_failed' || data.type === 'task_failed') {
          activeTask.value.status = 'failed'
          activeTask.value.error = data.error
          isIngesting.value = false
          localStorage.removeItem(ACTIVE_TASK_KEY)
        }
      }

      // Always refresh jobs table on any job event
      if (data.type?.startsWith('job_')) {
        fetchJobs()
      }
    } catch {}
  }

  ws.onclose = () => {
    // Reconnect after 2s if still ingesting
    if (isIngesting.value) {
      setTimeout(connectWebSocket, 2000)
    }
  }
}

function disconnectWebSocket() {
  if (ws) {
    ws.close()
    ws = null
  }
}

onUnmounted(() => {
  disconnectWebSocket()
})

async function handleIngest() {
  if (!detectedType.value) return

  isIngesting.value = true
  ingestError.value = null
  activeTask.value = null

  const source = ingestUrl.value.trim() || ingestFile.value?.name || ''

  try {
    const response = await $fetch<IngestResponse>(`${apiBase}/api/knowledge/ingest`, {
      method: 'POST',
      body: {
        source,
        type: detectedType.value
      } satisfies IngestRequest
    })

    const jobId = response.job_id || response.task_id
    activeTask.value = {
      id: jobId,
      title: source,
      status: 'queued',
      progress_percent: 0,
      progress_message: 'Queued for processing...',
      source_type: response.source_type
    }

    localStorage.setItem(ACTIVE_TASK_KEY, jobId)
    fetchJobs()
    connectWebSocket()
  } catch (err) {
    isIngesting.value = false
    ingestError.value = err instanceof Error ? err.message : 'Failed to start ingestion'
  }
}

function retryIngest() {
  activeTask.value = null
  ingestError.value = null
}

function dismissActiveTask() {
  activeTask.value = null
  ingestUrl.value = ''
  localStorage.removeItem(ACTIVE_TASK_KEY)
  clearFile()
}

// --- Jobs Table (SQLite) ---
const jobs = ref<any[]>([])
const jobsSummary = ref<any>({})

async function fetchJobs() {
  try {
    const response = await $fetch<{ jobs: any[], summary: any }>(`${apiBase}/api/jobs`)
    jobs.value = response.jobs ?? []
    jobsSummary.value = response.summary ?? {}
  } catch {}
}

fetchJobs()

function formatDate(dateStr: string | undefined) {
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

// --- Search ---
const searchQuery = ref('')
const searchResults = ref<KnowledgeSearchResult[]>([])
const searchTotal = ref(0)
const searching = ref(false)
const hasSearched = ref(false)

async function handleSearch() {
  if (!searchQuery.value.trim()) {
    searchResults.value = []
    searchTotal.value = 0
    hasSearched.value = false
    return
  }

  searching.value = true
  hasSearched.value = true
  try {
    const { data } = await useFetch<{ results: KnowledgeSearchResult[], query: string, total: number }>(
      `${apiBase}/api/knowledge/search`,
      { params: { q: searchQuery.value } }
    )
    searchResults.value = data.value?.results ?? []
    searchTotal.value = data.value?.total ?? 0
  } finally {
    searching.value = false
  }
}

function formatScore(score: number): string {
  return `${(score * 100).toFixed(0)}%`
}
</script>

<template>
  <UDashboardPanel id="knowledge">
    <template #header>
      <UDashboardNavbar title="Knowledge Base">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #trailing>
          <UBadge
            v-if="stats?.vss_available !== undefined"
            :label="stats.vss_available ? 'VSS Active' : 'VSS Unavailable'"
            :color="stats.vss_available ? 'success' : 'neutral'"
            variant="subtle"
          />
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
        <p class="text-sm text-muted">Failed to load knowledge stats.</p>
        <UButton label="Retry" variant="outline" color="primary" icon="i-lucide-refresh-cw" @click="refresh()" />
      </div>

      <!-- Content -->
      <template v-else>
        <!-- Add Content Section -->
        <UCard>
          <fieldset :disabled="isIngesting" class="space-y-5">
            <!-- Input Mode Tabs -->
            <div class="flex items-center gap-1 rounded-lg bg-muted/10 p-1 w-fit">
              <button
                v-for="mode in inputModes"
                :key="mode.value"
                class="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors"
                :class="activeInputMode === mode.value ? 'bg-elevated text-highlighted shadow-sm' : 'text-muted hover:text-highlighted'"
                @click="activeInputMode = mode.value"
              >
                <UIcon :name="mode.icon" class="size-3.5" />
                {{ mode.label }}
              </button>
            </div>

            <!-- Mode: URL -->
            <div v-if="activeInputMode === 'url'" class="space-y-3">
              <UInput
                v-model="ingestUrl"
                placeholder="Paste a YouTube URL, web page, article, or research link..."
                icon="i-lucide-link"
                size="xl"
                class="w-full"
                :ui="{ base: 'text-base' }"
                @keydown.enter.prevent="canIngest && handleIngest()"
              />
              <div class="flex items-center gap-1.5">
                <UBadge label="YouTube" color="error" variant="outline" size="xs" />
                <UBadge label="Web" color="primary" variant="outline" size="xs" />
                <UBadge label="Articles" color="primary" variant="outline" size="xs" />
                <UBadge label="Docs" color="neutral" variant="outline" size="xs" />
              </div>
            </div>

            <!-- Mode: File Upload with Drag & Drop -->
            <div
              v-if="activeInputMode === 'file'"
              class="relative rounded-xl border-2 border-dashed transition-colors p-8 text-center"
              :class="isDragging ? 'border-primary bg-primary/5' : 'border-default hover:border-primary/40'"
              @dragover.prevent="isDragging = true"
              @dragleave.prevent="isDragging = false"
              @drop.prevent="handleDrop"
            >
              <input
                ref="ingestFileInputRef"
                type="file"
                accept=".pdf,.mp3,.wav,.m4a,.ogg,.flac,.md,.mdx,.txt"
                class="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                @change="handleFileSelect"
              />
              <div v-if="!ingestFile">
                <UIcon name="i-lucide-cloud-upload" class="size-10 text-muted mx-auto mb-3" />
                <p class="text-sm font-medium text-highlighted">Drop files here or click to browse</p>
                <p class="text-xs text-muted mt-1">PDF, MP3, WAV, Markdown, TXT</p>
              </div>
              <div v-else class="flex items-center justify-center gap-3">
                <UIcon :name="typeIconMap[detectedType ?? ''] ?? 'i-lucide-file'" class="size-6 text-primary" />
                <div class="text-left">
                  <p class="text-sm font-medium text-highlighted">{{ ingestFile.name }}</p>
                  <p class="text-xs text-muted">{{ (ingestFile.size / 1024).toFixed(1) }} KB</p>
                </div>
                <UButton icon="i-lucide-x" variant="ghost" size="xs" @click.stop="clearFile" />
              </div>
            </div>

            <!-- Mode: Text / Paste -->
            <div v-if="activeInputMode === 'text'" class="space-y-3">
              <textarea
                v-model="pasteText"
                rows="6"
                placeholder="Paste or write text content here... Notes, excerpts, research findings, transcripts..."
                class="w-full rounded-lg border border-default bg-transparent px-4 py-3 text-sm text-highlighted placeholder:text-muted/50 focus:border-primary focus:outline-none resize-y"
              />
              <UInput
                v-model="pasteTitle"
                placeholder="Title (optional) — e.g., 'Meeting Notes Q3', 'Research: Growth Hacking'"
                icon="i-lucide-type"
                size="sm"
                class="w-full"
              />
            </div>

            <!-- Mode: Research -->
            <div v-if="activeInputMode === 'research'" class="space-y-3">
              <UInput
                v-model="ingestUrl"
                placeholder="Enter a topic or URL to research... e.g., 'Alex Hormozi business model'"
                icon="i-lucide-search"
                size="xl"
                class="w-full"
                :ui="{ base: 'text-base' }"
                @keydown.enter.prevent="canIngest && handleIngest()"
              />
              <p class="text-xs text-muted">ArkaOS will fetch the page, extract the content, and index it into your knowledge base.</p>
            </div>

            <!-- Action Row -->
            <div class="flex items-center justify-between gap-4">
              <div class="flex items-center gap-2">
                <template v-if="detectedType">
                  <UIcon :name="typeIconMap[detectedType] ?? 'i-lucide-file'" class="size-4 text-primary" />
                  <UBadge
                    :label="detectedType.charAt(0).toUpperCase() + detectedType.slice(1)"
                    :color="typeColorMap[detectedType] ?? 'neutral'"
                    variant="subtle"
                    size="sm"
                  />
                </template>
                <span v-else-if="activeInputMode === 'text' && pasteText" class="text-xs text-muted">
                  {{ pasteText.split(/\s+/).length }} words
                </span>
              </div>

              <UButton
                :label="activeInputMode === 'research' ? 'Research & Index' : 'Ingest'"
                icon="i-lucide-zap"
                size="md"
                :disabled="!canIngest && !(activeInputMode === 'text' && pasteText.length > 50)"
                :loading="isIngesting"
                @click="handleIngest"
              />
            </div>

            <!-- Error -->
            <div v-if="ingestError" class="rounded-md border border-red-500/20 bg-red-500/5 p-3" role="alert">
              <div class="flex items-center gap-2">
                <UIcon name="i-lucide-alert-circle" class="size-4 text-red-500" />
                <p class="text-sm text-red-400">{{ ingestError }}</p>
              </div>
            </div>
          </fieldset>
        </UCard>

        <!-- Active Ingestion Progress -->
        <div v-if="activeTask" class="mt-4 rounded-lg border border-default p-6">
          <div class="flex items-center justify-between gap-4 mb-4">
            <div class="flex items-center gap-2 min-w-0">
              <UIcon
                v-if="activeTask.status === 'queued' || activeTask.status === 'processing'"
                name="i-lucide-loader-2"
                class="size-5 shrink-0 animate-spin text-primary"
              />
              <UIcon
                v-else-if="activeTask.status === 'completed'"
                name="i-lucide-check-circle"
                class="size-5 shrink-0 text-green-500"
              />
              <UIcon
                v-else-if="activeTask.status === 'failed'"
                name="i-lucide-x-circle"
                class="size-5 shrink-0 text-red-500"
              />
              <span class="text-sm font-medium text-highlighted truncate">{{ activeTask.title }}</span>
            </div>
            <div class="flex items-center gap-2 shrink-0">
              <UBadge
                v-if="activeTask.source_type"
                :label="activeTask.source_type.charAt(0).toUpperCase() + activeTask.source_type.slice(1)"
                :color="typeColorMap[activeTask.source_type] ?? 'neutral'"
                variant="subtle"
                size="sm"
              />
              <UBadge
                :label="activeTask.status"
                :color="activeTask.status === 'completed' ? 'success' : activeTask.status === 'failed' ? 'error' : 'primary'"
                variant="subtle"
                size="sm"
                class="capitalize"
              />
            </div>
          </div>

          <!-- Progress Bar -->
          <div v-if="activeTask.status !== 'failed'" class="space-y-2">
            <UProgress :value="activeTask.progress_percent" :max="100" size="sm" />
            <div class="flex items-center justify-between">
              <p class="text-xs text-muted">{{ activeTask.progress_message }}</p>
              <span class="text-xs font-mono text-muted">{{ activeTask.progress_percent }}%</span>
            </div>
          </div>

          <!-- Completed -->
          <div v-if="activeTask.status === 'completed'" class="mt-3 rounded-md border border-green-200 bg-green-50 p-3 dark:border-green-800 dark:bg-green-950">
            <div class="flex items-center gap-2">
              <UIcon name="i-lucide-check" class="size-4 text-green-600" />
              <p class="text-sm text-green-700 dark:text-green-300">
                Ingestion complete.
                <span v-if="activeTask.output_data?.chunks_created">
                  {{ activeTask.output_data.chunks_created }} chunks created.
                </span>
              </p>
            </div>
            <div class="mt-2">
              <UButton label="Dismiss" variant="ghost" size="xs" @click="dismissActiveTask" />
            </div>
          </div>

          <!-- Failed -->
          <div v-if="activeTask.status === 'failed'" class="mt-3 rounded-md border border-red-200 bg-red-50 p-3 dark:border-red-800 dark:bg-red-950" role="alert">
            <div class="flex items-center gap-2">
              <UIcon name="i-lucide-alert-circle" class="size-4 text-red-500" />
              <p class="text-sm text-red-700 dark:text-red-300">
                {{ activeTask.error || 'Ingestion failed.' }}
              </p>
            </div>
            <div class="mt-2 flex gap-2">
              <UButton label="Retry" variant="outline" size="xs" icon="i-lucide-refresh-cw" @click="retryIngest" />
              <UButton label="Dismiss" variant="ghost" size="xs" @click="dismissActiveTask" />
            </div>
          </div>
        </div>

        <!-- Jobs Queue Table -->
        <div v-if="jobs.length" class="mt-4">
          <div class="flex items-center justify-between mb-3">
            <h3 class="text-sm font-semibold text-muted uppercase tracking-wider">Job Queue</h3>
            <div class="flex items-center gap-3 text-xs text-muted">
              <span v-if="jobsSummary.active">{{ jobsSummary.active }} active</span>
              <span>{{ jobsSummary.completed ?? 0 }} completed</span>
              <span v-if="jobsSummary.total_chunks">{{ jobsSummary.total_chunks }} total chunks</span>
            </div>
          </div>

          <div class="rounded-lg border border-default overflow-hidden">
            <table class="w-full text-sm">
              <thead>
                <tr class="border-b border-default bg-elevated/30">
                  <th class="text-left py-2.5 px-4 text-xs font-semibold text-muted">Source</th>
                  <th class="text-left py-2.5 px-3 text-xs font-semibold text-muted w-20">Type</th>
                  <th class="text-left py-2.5 px-3 text-xs font-semibold text-muted w-40">Status</th>
                  <th class="text-right py-2.5 px-3 text-xs font-semibold text-muted w-20">Chunks</th>
                  <th class="text-right py-2.5 px-4 text-xs font-semibold text-muted w-32">Time</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="job in jobs"
                  :key="job.id"
                  class="border-b border-default last:border-b-0 hover:bg-elevated/20 transition-colors"
                >
                  <td class="py-2.5 px-4">
                    <div class="flex items-center gap-2 min-w-0">
                      <UIcon :name="typeIconMap[job.type] ?? 'i-lucide-file'" class="size-4 shrink-0 text-muted" />
                      <span class="truncate text-highlighted">{{ job.title }}</span>
                    </div>
                  </td>
                  <td class="py-2.5 px-3">
                    <UBadge
                      v-if="job.type"
                      :label="job.type"
                      :color="typeColorMap[job.type] ?? 'neutral'"
                      variant="subtle"
                      size="xs"
                    />
                  </td>
                  <td class="py-2.5 px-3">
                    <div class="flex items-center gap-2">
                      <UIcon
                        v-if="['queued','processing','downloading','transcribing','embedding'].includes(job.status)"
                        name="i-lucide-loader-2"
                        class="size-3.5 animate-spin text-primary shrink-0"
                      />
                      <UIcon v-else-if="job.status === 'completed'" name="i-lucide-check-circle" class="size-3.5 text-green-500 shrink-0" />
                      <UIcon v-else-if="job.status === 'failed'" name="i-lucide-x-circle" class="size-3.5 text-red-500 shrink-0" />
                      <div class="flex-1 min-w-0">
                        <div v-if="['processing','downloading','transcribing','embedding'].includes(job.status)" class="space-y-1">
                          <div class="h-1.5 rounded-full bg-muted/20 overflow-hidden">
                            <div class="h-1.5 rounded-full bg-primary transition-all" :style="{ width: `${job.progress}%` }" />
                          </div>
                          <p class="text-[10px] text-muted truncate">{{ job.message }}</p>
                        </div>
                        <span v-else class="text-xs" :class="job.status === 'completed' ? 'text-green-400' : job.status === 'failed' ? 'text-red-400' : 'text-muted'">
                          {{ job.status }}
                        </span>
                      </div>
                    </div>
                  </td>
                  <td class="py-2.5 px-3 text-right">
                    <span v-if="job.chunks_created" class="text-xs font-mono">{{ job.chunks_created }}</span>
                    <span v-else class="text-xs text-muted">—</span>
                  </td>
                  <td class="py-2.5 px-4 text-right text-xs text-muted">
                    {{ formatDate(job.completed_at || job.created_at) }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Stats Section -->
        <div class="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-3">
          <div class="rounded-lg border border-default p-4 text-center">
            <p class="text-2xl font-semibold text-highlighted">{{ stats?.total_chunks ?? 0 }}</p>
            <p class="text-xs text-muted">Total Chunks</p>
          </div>
          <div class="rounded-lg border border-default p-4 text-center">
            <p class="text-2xl font-semibold text-highlighted">{{ stats?.total_files ?? 0 }}</p>
            <p class="text-xs text-muted">Total Files</p>
          </div>
          <div class="rounded-lg border border-default p-4 text-center">
            <UBadge
              :label="stats?.vss_available ? 'Available' : 'Unavailable'"
              :color="stats?.vss_available ? 'success' : 'neutral'"
              variant="subtle"
              size="sm"
            />
            <p class="text-xs text-muted mt-1">Vector Search</p>
          </div>
        </div>

        <!-- Not Indexed State -->
        <div v-if="!isIndexed" class="mt-8">
          <div class="rounded-lg border-2 border-dashed border-default p-8 text-center">
            <UIcon name="i-lucide-database" class="size-16 text-muted mx-auto" />
            <h3 class="mt-4 text-lg font-semibold text-highlighted">Knowledge base not indexed yet</h3>
            <p class="mt-2 text-sm text-muted max-w-lg mx-auto">
              Index your Obsidian vault to enable semantic search across your entire knowledge base.
            </p>
            <div class="mt-6 inline-block rounded-lg border border-default bg-elevated/50 px-6 py-4 text-left">
              <p class="text-xs text-muted mb-2">Run this command to index:</p>
              <code class="font-mono text-sm text-primary">npx arkaos index</code>
            </div>
            <p class="mt-4 text-xs text-muted max-w-md mx-auto">
              This indexes your markdown files into a local vector database for automatic context retrieval.
              The process runs locally and your data never leaves your machine.
            </p>
          </div>
        </div>

        <!-- Indexed State -->
        <template v-else>
          <!-- Knowledge Areas -->
          <div v-if="stats?.areas?.length" class="mt-6">
            <h3 class="mb-4 text-lg font-semibold text-highlighted">Knowledge Areas</h3>
            <div class="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              <div
                v-for="area in stats.areas"
                :key="area.name"
                class="rounded-lg border border-default p-4"
              >
                <h4 class="font-medium text-highlighted">{{ area.name }}</h4>
                <div class="mt-2 flex gap-4 text-xs text-muted">
                  <span>{{ area.chunks }} chunks</span>
                  <span>{{ area.files }} files</span>
                </div>
              </div>
            </div>
          </div>

          <!-- Search -->
          <div class="mt-6 rounded-lg border border-default p-6">
            <h3 class="mb-4 text-lg font-semibold text-highlighted">Search Knowledge</h3>
            <form class="flex gap-2" @submit.prevent="handleSearch">
              <UInput
                v-model="searchQuery"
                class="flex-1"
                icon="i-lucide-search"
                placeholder="Search the knowledge base..."
                aria-label="Search knowledge base"
              />
              <UButton
                type="submit"
                label="Search"
                :loading="searching"
                icon="i-lucide-search"
              />
            </form>

            <!-- Search Results -->
            <div v-if="searching" class="mt-4 flex items-center justify-center py-8">
              <UIcon name="i-lucide-loader-2" class="size-6 animate-spin text-muted" />
            </div>

            <template v-else-if="hasSearched">
              <div v-if="searchResults.length" class="mt-4 space-y-3">
                <p class="text-xs text-muted">{{ searchTotal }} result{{ searchTotal !== 1 ? 's' : '' }} found</p>
                <div
                  v-for="(result, idx) in searchResults"
                  :key="result.id ?? idx"
                  class="rounded-lg border border-default p-4"
                >
                  <div class="mb-2 flex items-center justify-between gap-2">
                    <div class="flex items-center gap-2 min-w-0">
                      <UBadge v-if="result.area" :label="result.area" variant="subtle" size="sm" />
                      <span v-if="result.heading" class="text-sm font-medium text-highlighted truncate">
                        {{ result.heading }}
                      </span>
                    </div>
                    <span class="text-xs text-muted whitespace-nowrap">
                      Score: {{ formatScore(result.score) }}
                    </span>
                  </div>
                  <p v-if="result.source" class="text-xs text-muted mb-1 truncate">
                    <UIcon name="i-lucide-file-text" class="size-3 inline-block mr-1" />
                    {{ result.source }}
                  </p>
                  <p class="text-sm text-muted line-clamp-3">
                    {{ result.text || result.content }}
                  </p>
                </div>
              </div>

              <div v-else class="mt-4 text-center text-sm text-muted py-6">
                <UIcon name="i-lucide-search-x" class="size-8 text-muted mx-auto mb-2" />
                <p>No results found for "{{ searchQuery }}".</p>
              </div>
            </template>
          </div>
        </template>
      </template>
    </template>
  </UDashboardPanel>
</template>
