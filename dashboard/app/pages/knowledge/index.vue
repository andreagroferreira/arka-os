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
// PR56 v2.73.0 — bulk URL ingest mode. Paste a list of URLs (one per
// line) and the backend queues one job per source.
const bulkUrls = ref('')

const activeInputMode = ref<'url' | 'file' | 'text' | 'research' | 'bulk' | 'record'>('url')

const inputModes = [
  { label: 'URL', value: 'url' as const, icon: 'i-lucide-link' },
  { label: 'Bulk', value: 'bulk' as const, icon: 'i-lucide-list' },
  { label: 'File', value: 'file' as const, icon: 'i-lucide-upload' },
  { label: 'Text', value: 'text' as const, icon: 'i-lucide-type' },
  { label: 'Research', value: 'research' as const, icon: 'i-lucide-search' },
  { label: 'Record', value: 'record' as const, icon: 'i-lucide-mic' },
]

const bulkUrlCount = computed(() =>
  bulkUrls.value
    .split('\n')
    .map((s) => s.trim())
    .filter((s) => s.length > 0).length
)

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
    if (url.startsWith('blob:')) return 'video'
    if (/^https?:\/\/(www\.)?(youtube\.com|youtu\.be)\//i.test(url)) return 'youtube'
    if (/\.pdf(\?.*)?$/i.test(url)) return 'pdf'
    if (/\.(mp3|wav|m4a|ogg|flac)(\?.*)?$/i.test(url)) return 'audio'
    if (/\.(mp4|mov|webm|mkv|avi)(\?.*)?$/i.test(url)) return 'video'
    if (/\.(md|mdx)(\?.*)?$/i.test(url)) return 'markdown'
    if (/^https?:\/\//i.test(url)) return 'web'
  }
  if (ingestFile.value) {
    const name = ingestFile.value.name.toLowerCase()
    if (name.endsWith('.pdf')) return 'pdf'
    if (/\.(mp3|wav|m4a|ogg|flac)$/.test(name)) return 'audio'
    if (/\.(mp4|mov|webm|mkv|avi)$/.test(name)) return 'video'
    if (/\.(md|mdx)$/.test(name)) return 'markdown'
  }
  return null
})

const typeColorMap: Record<string, 'error' | 'primary' | 'warning' | 'success' | 'neutral'> = {
  youtube: 'error',
  web: 'primary',
  pdf: 'warning',
  audio: 'success',
  markdown: 'neutral',
  video: 'error'
}

const typeIconMap: Record<string, string> = {
  youtube: 'i-lucide-youtube',
  web: 'i-lucide-globe',
  pdf: 'i-lucide-file-text',
  audio: 'i-lucide-headphones',
  markdown: 'i-lucide-file-code',
  video: 'i-lucide-video'
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

function extFromMime(mime: string): string {
  const map: Record<string, string> = {
    'video/mp4': 'mp4',
    'video/quicktime': 'mov',
    'video/webm': 'webm',
    'video/x-matroska': 'mkv',
    'video/x-msvideo': 'avi'
  }
  return map[mime] ?? 'mp4'
}

// Upload a File via multipart. handleIngest's post-branch wiring
// (fetchJobs + connectWebSocket) tracks progress — no WS logic here.
async function uploadFile(file: File) {
  const formData = new FormData()
  formData.append('file', file)
  return await $fetch(`${apiBase}/api/knowledge/upload-file`, {
    method: 'POST',
    body: formData
  })
}

// --- Record mode (PR — capture the audio output the player produces) ---
// We never touch a protected/encrypted stream. We record the audio the
// machine legitimately plays (the analog hole), same category as Otter or
// Descript recording a meeting. The resulting .webm flows through the
// existing upload -> Whisper -> KB pipeline via uploadFile().
const recordTitle = ref('')
const recordSource = ref<'tab' | 'device'>('tab')
const recordDevices = ref<{ label: string, value: string }[]>([])
const selectedDeviceId = ref('')
const isRecording = ref(false)
const recordElapsed = ref(0)

let mediaRecorder: MediaRecorder | null = null
let recordStream: MediaStream | null = null
let recordChunks: Blob[] = []
let recordTimer: ReturnType<typeof setInterval> | null = null

const recordElapsedLabel = computed(() => {
  const total = recordElapsed.value
  const mm = String(Math.floor(total / 60)).padStart(2, '0')
  const ss = String(total % 60).padStart(2, '0')
  return `${mm}:${ss}`
})

const canStartRecording = computed(() => {
  if (isRecording.value) return false
  if (recordSource.value === 'device' && !selectedDeviceId.value) return false
  return true
})

const recordSourceItems = [
  { label: 'Browser tab audio (share the course tab)', value: 'tab' },
  { label: 'Audio input device', value: 'device' }
]

// Sanitize a title into a filename-safe stem. Keeps letters, digits, dash,
// underscore and space; collapses the rest to a single dash.
function safeFilename(title: string): string {
  const stem = (title || 'recording')
    .trim()
    .replace(/[^a-zA-Z0-9 _-]+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 80)
  return stem || 'recording'
}

function pickRecorderMime(): string | undefined {
  if (typeof MediaRecorder === 'undefined') return undefined
  const prefs = ['audio/webm;codecs=opus', 'audio/webm']
  for (const m of prefs) {
    if (MediaRecorder.isTypeSupported(m)) return m
  }
  return undefined
}

async function loadAudioDevices() {
  if (!import.meta.client || !navigator.mediaDevices?.enumerateDevices) return
  try {
    const devices = await navigator.mediaDevices.enumerateDevices()
    recordDevices.value = devices
      .filter(d => d.kind === 'audioinput')
      .map(d => ({ label: d.label || 'Microphone', value: d.deviceId }))
    if (!selectedDeviceId.value && recordDevices.value.length) {
      selectedDeviceId.value = recordDevices.value[0]!.value
    }
  } catch {
    // enumeration can fail before any permission grant; ignore quietly
  }
}

function stopRecordStream() {
  if (recordStream) {
    recordStream.getTracks().forEach(t => t.stop())
    recordStream = null
  }
}

function clearRecordTimer() {
  if (recordTimer) {
    clearInterval(recordTimer)
    recordTimer = null
  }
}

async function startRecording() {
  if (!import.meta.client) return
  ingestError.value = null
  recordChunks = []
  try {
    if (!navigator.mediaDevices) {
      ingestError.value = 'Recording is not supported in this browser.'
      return
    }
    let audioStream: MediaStream
    if (recordSource.value === 'tab') {
      // Chrome only offers tab audio when video is requested; we capture
      // video then immediately drop the video track and keep audio only.
      recordStream = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: true })
      const audioTracks = recordStream.getAudioTracks()
      if (!audioTracks.length) {
        stopRecordStream()
        ingestError.value = `No audio track was shared. Make sure 'Share tab audio' is checked, or use an audio input device.`
        return
      }
      // Drop the video track to keep only audio.
      recordStream.getVideoTracks().forEach(t => t.stop())
      audioStream = new MediaStream(audioTracks)
    } else {
      recordStream = await navigator.mediaDevices.getUserMedia({
        audio: { deviceId: selectedDeviceId.value ? { exact: selectedDeviceId.value } : undefined }
      })
      audioStream = recordStream
    }

    const mimeType = pickRecorderMime()
    mediaRecorder = mimeType
      ? new MediaRecorder(audioStream, { mimeType })
      : new MediaRecorder(audioStream)
    mediaRecorder.ondataavailable = (e: BlobEvent) => {
      if (e.data && e.data.size > 0) recordChunks.push(e.data)
    }
    mediaRecorder.onstop = () => {
      void finalizeRecording()
    }
    mediaRecorder.start()

    isRecording.value = true
    recordElapsed.value = 0
    clearRecordTimer()
    recordTimer = setInterval(() => {
      recordElapsed.value += 1
    }, 1000)
  } catch (err) {
    stopRecordStream()
    isRecording.value = false
    const name = (err as DOMException)?.name
    ingestError.value = name === 'NotAllowedError'
      ? 'Permission to capture audio was denied.'
      : 'Could not start recording. Your browser may not support audio capture.'
  }
}

function stopRecording() {
  if (!isRecording.value) return
  clearRecordTimer()
  isRecording.value = false
  // onstop -> finalizeRecording builds the file and releases tracks.
  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    mediaRecorder.stop()
  } else {
    void finalizeRecording()
  }
}

// Build a File from the captured chunks and push it through the SAME path
// the file-upload mode uses (uploadFile + activeTask/WS/jobs wiring).
async function finalizeRecording() {
  const mime = mediaRecorder?.mimeType || 'audio/webm'
  const blob = new Blob(recordChunks, { type: mime })
  recordChunks = []
  stopRecordStream()
  mediaRecorder = null
  clearRecordTimer()

  if (!blob.size) {
    ingestError.value = 'No audio was captured.'
    return
  }

  const name = `${safeFilename(recordTitle.value)}-${Date.now()}.webm`
  const file = new File([blob], name, { type: blob.type })

  ingestError.value = null
  try {
    const res = await uploadFile(file) as { job_id?: string } | undefined
    const jobId = res?.job_id
    if (jobId) {
      activeTask.value = {
        id: jobId,
        title: recordTitle.value || name,
        source_type: 'audio',
        status: 'queued',
        progress_percent: 0,
        progress_message: 'Queued for transcription...'
      } as IngestTask
      isIngesting.value = true
      localStorage.setItem(ACTIVE_TASK_KEY, jobId)
    }
    recordTitle.value = ''
    fetchJobs()
    connectWebSocket()
  } catch (err) {
    ingestError.value = err instanceof Error ? err.message : 'Failed to queue the recording'
  }
}

// Re-enumerate devices when the user picks the device source.
watch(recordSource, (mode) => {
  if (mode === 'device') loadAudioDevices()
})

const canIngest = computed(() => {
  if (activeInputMode.value === 'record') return false
  if (activeInputMode.value === 'bulk') return bulkUrlCount.value > 0
  return detectedType.value !== null
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
          fetchKnowledgeSources()
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
  clearRecordTimer()
  stopRecordStream()
})

async function handleIngest() {
  if (
    !detectedType.value
    && activeInputMode.value !== 'text'
    && activeInputMode.value !== 'bulk'
  ) return

  ingestError.value = null

  try {
    // File upload — use multipart form
    if (activeInputMode.value === 'file' && ingestFile.value) {
      await uploadFile(ingestFile.value)
    }
    // blob: URL — fetch the bytes client-side, then upload as a File
    else if (ingestUrl.value.trim().startsWith('blob:')) {
      const blobUrl = ingestUrl.value.trim()
      try {
        const resp = await fetch(blobUrl)
        const blob = await resp.blob()
        const file = new File([blob], `video-${Date.now()}.${extFromMime(blob.type)}`, { type: blob.type })
        await uploadFile(file)
      } catch {
        ingestError.value = 'Could not read the blob: URL (it may have been revoked, cross-origin, or DRM-protected). Download the file and use the File tab instead.'
        return
      }
    }
    // Text paste — save to temp file via API
    else if (activeInputMode.value === 'text' && pasteText.value.length > 10) {
      await $fetch(`${apiBase}/api/knowledge/ingest`, {
        method: 'POST',
        body: { source: pasteText.value.slice(0, 100), type: 'markdown', text: pasteText.value, title: pasteTitle.value },
      })
    }
    // Bulk URL paste — one job per non-blank line, server caps at 50
    else if (activeInputMode.value === 'bulk' && bulkUrlCount.value > 0) {
      const sources = bulkUrls.value
        .split('\n')
        .map((s) => s.trim())
        .filter((s) => s.length > 0)
      await $fetch(`${apiBase}/api/knowledge/ingest-bulk`, {
        method: 'POST',
        body: { sources },
      })
    }
    // URL or Research — standard ingest
    else {
      const source = ingestUrl.value.trim()
      const type = detectedType.value
      if (!source || !type) return
      await $fetch(`${apiBase}/api/knowledge/ingest`, {
        method: 'POST',
        body: { source, type },
      })
    }

    // Clear form immediately
    ingestUrl.value = ''
    clearFile()
    pasteText.value = ''
    pasteTitle.value = ''
    bulkUrls.value = ''

    // Refresh jobs table + connect WebSocket
    fetchJobs()
    connectWebSocket()
  } catch (err) {
    ingestError.value = err instanceof Error ? err.message : 'Failed to queue job'
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

// --- Job row -> source detail id (make completed job rows clickable) ---
// The jobs table only carries the `source` string, not the stable
// `src-<sha1>` detail id. GET /api/knowledge/sources already returns
// `{id, source, ...}` for every indexed source, keyed on the SAME source
// string. We fetch it once and build a source->id lookup so a completed job
// row can link to /knowledge/{id} — the per-source detail page (player +
// transcript + download).
const knowledgeSources = ref<{ source: string, id: string }[]>([])

async function fetchKnowledgeSources() {
  try {
    const response = await $fetch<{ sources: { source: string, id: string }[] }>(
      `${apiBase}/api/knowledge/sources`
    )
    knowledgeSources.value = response.sources ?? []
  } catch {}
}

fetchKnowledgeSources()

const sourceIdBySource = computed(
  () => new Map(knowledgeSources.value.map(s => [s.source, s.id]))
)

// A job row opens its detail page only when it has completed AND a matching
// indexed source exists. Failed/processing/queued jobs have no detail page.
function jobDetailId(job: { source?: string, status?: string }): string | null {
  if (job.status !== 'completed' || !job.source) return null
  return sourceIdBySource.value.get(job.source) ?? null
}

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

// RAG honesty (PR-3 v4.1): keyword-degraded results carry score=null —
// there is no similarity to show, so label them instead of faking "0%".
function formatScore(score: number | null): string {
  if (score === null || score === undefined) return 'keyword match'
  return `${(score * 100).toFixed(0)}%`
}

// PR73 v2.91.0 — `vec_available` is the canonical PR47-era flag from
// the new VectorStore; `vss_available` is the legacy field name from
// earlier sqlite-vss builds. Treat either as "active".
const vectorSearchActive = computed(() =>
  Boolean(stats.value?.vec_available || stats.value?.vss_available),
)

// PR71 v2.88.0 — delete all chunks from a given source.

const deletingSource = ref<string | null>(null)

const confirmDialog = useConfirmDialog()

async function askDeleteSource(source: string) {
  if (!source) return
  const ok = await confirmDialog({
    title: 'Delete every indexed chunk from this source?',
    description:
      `${source}\n\nRemoves the source from search results but does NOT `
      + 'delete the original file. You can re-ingest later if needed.',
    confirmLabel: 'Delete chunks',
    variant: 'danger',
  })
  if (!ok) return
  await deleteSource(source)
}

async function deleteSource(source: string) {
  deletingSource.value = source
  try {
    const res = await $fetch<{ deleted?: number, source?: string, error?: string }>(
      `${apiBase}/api/knowledge/sources`,
      { method: 'DELETE', query: { source } },
    )
    if (res.error) {
      toast.add({
        title: 'Delete failed',
        description: res.error,
        color: 'error',
      })
      return
    }
    const deleted = res.deleted ?? 0
    // Drop the matching rows from the in-memory list without a full re-fetch.
    searchResults.value = searchResults.value.filter((r) => r.source !== source)
    searchTotal.value = searchResults.value.length
    // Refresh stats so the chunk count in the header updates.
    if (typeof refresh === 'function') {
      await refresh()
    }
    toast.add({
      title: deleted > 0
        ? `Deleted ${deleted} chunk${deleted === 1 ? '' : 's'}`
        : 'Nothing to delete',
      description: source,
      color: 'success',
    })
  } catch (err) {
    toast.add({
      title: 'Delete failed',
      description: err instanceof Error ? err.message : 'unknown error',
      color: 'error',
    })
  } finally {
    deletingSource.value = null
  }
}

// PR71 — highlight the search query in the preview text.
// Tolerates malformed regex (escapes special characters) and HTML-
// escapes the input so v-html'd output is safe from XSS via DB rows.
function highlightMatches(text: string, query: string): string {
  const safe = escapeHtml(text || '')
  const q = (query || '').trim()
  if (!q) return safe
  const pattern = new RegExp(`(${escapeRegex(q)})`, 'gi')
  return safe.replace(
    pattern,
    '<mark class="bg-primary/20 text-primary rounded px-0.5">$1</mark>',
  )
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function escapeRegex(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
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
            v-if="stats?.vec_available !== undefined || stats?.vss_available !== undefined"
            :label="vectorSearchActive ? 'Vector Active' : 'Vector Off'"
            :color="vectorSearchActive ? 'success' : 'warning'"
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
        <!-- Single block wrapper: prevents the first card collapsing to
             height:0 as a bare flex child of UDashboardPanel #body. Mirrors
             the budget.vue / tasks.vue pattern (one block child per body).
             No space-y here: children already carry their own mt-* margins. -->
        <div>
          <!-- Add Content Section -->
          <UCard>
            <fieldset class="space-y-5">
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
                  <UBadge label="Video" color="error" variant="outline" size="xs" />
                </div>
                <p class="text-xs text-muted">
                  Direct video links (MP4, MOV, WebM) and <code>blob:</code> URLs are supported.
                </p>
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
                  accept=".pdf,.mp3,.wav,.m4a,.ogg,.flac,.md,.mdx,.txt,.mp4,.mov,.webm,.mkv,.avi"
                  class="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                  @change="handleFileSelect"
                />
                <div v-if="!ingestFile">
                  <UIcon name="i-lucide-cloud-upload" class="size-10 text-muted mx-auto mb-3" />
                  <p class="text-sm font-medium text-highlighted">Drop files here or click to browse</p>
                  <p class="text-xs text-muted mt-1">PDF, MP3, WAV, MP4, MOV, WebM, Markdown, TXT</p>
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

              <!-- Mode: Bulk URLs (PR56 v2.73.0) -->
              <div v-if="activeInputMode === 'bulk'" class="space-y-3">
                <UTextarea
                  v-model="bulkUrls"
                  placeholder="Paste one URL per line. Up to 50 sources per batch.&#10;&#10;https://www.youtube.com/watch?v=...&#10;https://example.com/article&#10;https://example.com/paper.pdf"
                  :rows="8"
                  size="lg"
                  class="w-full font-mono text-sm"
                />
                <div class="flex items-center justify-between text-xs text-muted">
                  <span>{{ bulkUrlCount }} source{{ bulkUrlCount === 1 ? '' : 's' }} detected</span>
                  <span v-if="bulkUrlCount > 50" class="text-red-400">
                    Over the 50-source cap — extras will be rejected.
                  </span>
                </div>
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

              <!-- Mode: Record (capture played audio -> Whisper -> KB) -->
              <div v-if="activeInputMode === 'record'" class="space-y-3">
                <UInput
                  v-model="recordTitle"
                  placeholder="Title for this recording (e.g. Course — Module 3)"
                  icon="i-lucide-mic"
                  size="lg"
                  class="w-full"
                  :disabled="isRecording"
                />
                <USelect
                  v-model="recordSource"
                  :items="recordSourceItems"
                  :disabled="isRecording"
                  class="w-full"
                />
                <USelect
                  v-if="recordSource === 'device'"
                  v-model="selectedDeviceId"
                  :items="recordDevices"
                  :disabled="isRecording"
                  placeholder="Pick an audio input device"
                  class="w-full"
                />
                <div class="flex items-center gap-3">
                  <UButton
                    v-if="!isRecording"
                    label="Start recording"
                    icon="i-lucide-circle"
                    color="primary"
                    size="md"
                    :disabled="!canStartRecording"
                    @click="startRecording"
                  />
                  <UButton
                    v-else
                    label="Stop & transcribe"
                    icon="i-lucide-square"
                    color="error"
                    size="md"
                    @click="stopRecording"
                  />
                  <div v-if="isRecording" class="flex items-center gap-2">
                    <span class="relative flex size-2.5">
                      <span class="absolute inline-flex h-full w-full animate-ping rounded-full bg-red-500 opacity-75" />
                      <span class="relative inline-flex size-2.5 rounded-full bg-red-500" />
                    </span>
                    <span class="text-sm font-mono text-highlighted" aria-live="polite">{{ recordElapsedLabel }}</span>
                  </div>
                </div>
                <p class="text-xs text-muted">
                  Records the audio your computer plays while you watch content you have access to.
                  For DRM-protected video, tab audio may be silent — install a virtual audio device
                  (BlackHole on macOS, VB-Cable on Windows) and pick it under 'Audio input device'.
                  We never access the protected video stream — only the audio output.
                </p>
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
                  v-if="activeInputMode !== 'record'"
                  :label="
                    activeInputMode === 'research' ? 'Research & Index'
                    : activeInputMode === 'bulk' ? `Ingest ${bulkUrlCount} source${bulkUrlCount === 1 ? '' : 's'}`
                    : 'Ingest'
                  "
                  icon="i-lucide-zap"
                  size="md"
                  :disabled="!canIngest && !(activeInputMode === 'text' && pasteText.length > 50)"
                  :loading="false"
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
                    class="border-b border-default last:border-b-0 transition-colors"
                    :class="jobDetailId(job)
                      ? 'cursor-pointer hover:bg-primary/5'
                      : 'hover:bg-elevated/20'"
                    @click="jobDetailId(job) && navigateTo(`/knowledge/${jobDetailId(job)}`)"
                  >
                    <td class="py-2.5 px-4">
                      <div class="flex items-center gap-2 min-w-0">
                        <UIcon :name="typeIconMap[job.type] ?? 'i-lucide-file'" class="size-4 shrink-0 text-muted" />
                        <NuxtLink
                          v-if="jobDetailId(job)"
                          :to="`/knowledge/${jobDetailId(job)}`"
                          class="truncate text-highlighted hover:text-primary hover:underline"
                          :aria-label="`Open ${job.title} — transcript, video and knowledge`"
                          @click.stop
                        >
                          {{ job.title }}
                        </NuxtLink>
                        <span v-else class="truncate text-highlighted">{{ job.title }}</span>
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
                      <div class="flex items-center justify-end gap-1.5">
                        <span>{{ formatDate(job.completed_at || job.created_at) }}</span>
                        <UIcon
                          v-if="jobDetailId(job)"
                          name="i-lucide-chevron-right"
                          class="size-3.5 text-muted shrink-0"
                          aria-hidden="true"
                        />
                      </div>
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
                :label="vectorSearchActive ? 'Active' : 'Unavailable'"
                :color="vectorSearchActive ? 'success' : 'warning'"
                variant="subtle"
                size="sm"
              />
              <p class="text-xs text-muted mt-1">Vector Search</p>
              <p
                v-if="!vectorSearchActive && stats?.vec_unavailable_reason"
                class="text-xs text-yellow-400 mt-2 text-left"
                :title="stats.vec_unavailable_reason"
              >
                {{ stats.vec_unavailable_reason }}
              </p>
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
                      <div class="flex items-center gap-2 shrink-0">
                        <span class="text-xs text-muted whitespace-nowrap">
                          Score: {{ formatScore(result.score) }}
                        </span>
                        <UButton
                          v-if="result.source"
                          :icon="deletingSource === result.source
                            ? 'i-lucide-loader-2'
                            : 'i-lucide-trash-2'"
                          :loading="deletingSource === result.source"
                          variant="ghost"
                          color="error"
                          size="xs"
                          aria-label="Delete all chunks from this source"
                          @click.stop="askDeleteSource(result.source)"
                        />
                      </div>
                    </div>
                    <p v-if="result.source" class="text-xs text-muted mb-1 truncate">
                      <UIcon name="i-lucide-file-text" class="size-3 inline-block mr-1" />
                      {{ result.source }}
                    </p>
                    <!-- PR71 v2.88.0 — highlight query matches in the preview -->
                    <p class="text-sm text-muted line-clamp-3" v-html="highlightMatches(result.text || result.content, searchQuery)" />
                  </div>
                </div>

                <div v-else class="mt-4 text-center text-sm text-muted py-6">
                  <UIcon name="i-lucide-search-x" class="size-8 text-muted mx-auto mb-2" />
                  <p>No results found for "{{ searchQuery }}".</p>
                </div>
              </template>
            </div>

            <!-- PR88c v3.25.0 — Indexed sources management -->
            <div class="mt-6">
              <KnowledgeSourcesList />
            </div>
          </template>
        </div>
      </template>
    </template>
  </UDashboardPanel>
</template>
