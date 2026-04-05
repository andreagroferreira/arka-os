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

// --- Active Ingestion Tracking ---
const activeTask = ref<IngestTask | null>(null)
let pollInterval: ReturnType<typeof setInterval> | null = null

function startPolling(taskId: string) {
  stopPolling()
  pollInterval = setInterval(async () => {
    try {
      const response = await $fetch<IngestTask>(`${apiBase}/api/tasks/${taskId}`)
      activeTask.value = response
      if (response.status === 'completed' || response.status === 'failed') {
        stopPolling()
        isIngesting.value = false
        if (response.status === 'completed') {
          refresh()
          fetchHistory()
        }
      }
    } catch {
      // Polling failure is non-critical, will retry on next interval
    }
  }, 2000)
}

function stopPolling() {
  if (pollInterval) {
    clearInterval(pollInterval)
    pollInterval = null
  }
}

onUnmounted(() => {
  stopPolling()
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

    activeTask.value = {
      id: response.task_id,
      title: source,
      status: 'queued',
      progress_percent: 0,
      progress_message: 'Queued for processing...',
      source_type: response.source_type
    }

    startPolling(response.task_id)
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
  clearFile()
}

// --- Ingestion History ---
const historyTasks = ref<IngestTask[]>([])
const historyLoading = ref(false)

async function fetchHistory() {
  historyLoading.value = true
  try {
    const response = await $fetch<{ tasks: IngestTask[] }>(`${apiBase}/api/tasks`, {
      params: { status: 'completed' }
    })
    historyTasks.value = (response.tasks ?? []).filter(
      t => t.source_type && ['youtube', 'web', 'pdf', 'audio', 'markdown'].includes(t.source_type)
    )
  } catch {
    // History fetch failure is non-critical
  } finally {
    historyLoading.value = false
  }
}

fetchHistory()

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
            <!-- Main URL Input — full width, prominent -->
            <div class="relative">
              <UInput
                id="ingest-url"
                v-model="ingestUrl"
                placeholder="Paste a YouTube URL, web page, or article link..."
                icon="i-lucide-sparkles"
                size="xl"
                class="w-full"
                :disabled="!!ingestFile"
                :ui="{ base: 'text-base' }"
                @keydown.enter.prevent="canIngest && handleIngest()"
              />
            </div>

            <!-- Source types + file upload + action — single row -->
            <div class="flex flex-wrap items-center gap-3">
              <!-- Supported types -->
              <div class="flex items-center gap-1.5">
                <UBadge label="YouTube" color="error" variant="outline" size="xs" icon="i-lucide-play" />
                <UBadge label="Web" color="primary" variant="outline" size="xs" icon="i-lucide-globe" />
                <UBadge label="PDF" color="warning" variant="outline" size="xs" icon="i-lucide-file-text" />
                <UBadge label="Audio" color="success" variant="outline" size="xs" icon="i-lucide-headphones" />
                <UBadge label="Markdown" color="neutral" variant="outline" size="xs" icon="i-lucide-file-code" />
              </div>

              <!-- Divider -->
              <div class="h-4 w-px bg-muted/30" />

              <!-- File upload — styled button -->
              <label class="cursor-pointer">
                <input
                  ref="ingestFileInputRef"
                  type="file"
                  accept=".pdf,.mp3,.wav,.m4a,.ogg,.flac,.md,.mdx"
                  class="hidden"
                  @change="handleFileSelect"
                />
                <span class="inline-flex items-center gap-1.5 rounded-md border border-default px-3 py-1.5 text-xs font-medium text-muted hover:text-highlighted hover:border-primary/50 transition-colors">
                  <UIcon name="i-lucide-upload" class="size-3.5" />
                  {{ ingestFile ? ingestFile.name : 'Upload file' }}
                </span>
              </label>
              <UButton
                v-if="ingestFile"
                icon="i-lucide-x"
                variant="ghost"
                color="neutral"
                size="xs"
                @click="clearFile"
              />

              <!-- Spacer -->
              <div class="flex-1" />

              <!-- Detected type -->
              <div v-if="detectedType" class="flex items-center gap-1.5">
                <UIcon :name="typeIconMap[detectedType] ?? 'i-lucide-file'" class="size-4 text-primary" />
                <UBadge
                  :label="detectedType.charAt(0).toUpperCase() + detectedType.slice(1)"
                  :color="typeColorMap[detectedType] ?? 'neutral'"
                  variant="subtle"
                  size="sm"
                />
              </div>

              <!-- Ingest button -->
              <UButton
                label="Ingest"
                icon="i-lucide-zap"
                size="md"
                :disabled="!canIngest"
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

        <!-- Ingestion History -->
        <div v-if="historyTasks.length" class="mt-4 rounded-lg border border-default p-6">
          <h3 class="mb-4 text-lg font-semibold text-highlighted">Recent Ingestions</h3>
          <div class="space-y-3">
            <div
              v-for="task in historyTasks"
              :key="task.id"
              class="flex items-center justify-between gap-4 rounded-lg border border-default p-3"
            >
              <div class="flex items-center gap-3 min-w-0">
                <UIcon
                  :name="typeIconMap[task.source_type ?? ''] ?? 'i-lucide-file'"
                  class="size-4 shrink-0 text-muted"
                />
                <span class="text-sm text-highlighted truncate">{{ task.title }}</span>
              </div>
              <div class="flex items-center gap-3 shrink-0">
                <UBadge
                  v-if="task.source_type"
                  :label="task.source_type.charAt(0).toUpperCase() + task.source_type.slice(1)"
                  :color="typeColorMap[task.source_type] ?? 'neutral'"
                  variant="subtle"
                  size="sm"
                />
                <span v-if="task.output_data?.chunks_created" class="text-xs text-muted">
                  {{ task.output_data.chunks_created }} chunks
                </span>
                <span class="text-xs text-muted">{{ formatDate(task.created_at) }}</span>
              </div>
            </div>
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
