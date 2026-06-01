<script setup lang="ts">
// PR2 — Per-source knowledge detail page.
//
// Polymorphic view for a single indexed source (id like `src-xxxx`).
// Loads GET /api/knowledge/sources/{id}. Renders media (YouTube embed,
// native video/audio, or download), the full transcript, the chunks this
// source contributed to the vector store, and a placeholder for PR3 agent
// attribution. Unknown ids return 404 -> "Source not found" empty state.

const route = useRoute()
const sourceId = route.params.id as string

const { fetchApi, apiBase } = useApi()
const toast = useToast()

interface SourceChunk {
  text: string
  heading: string
  metadata: Record<string, unknown>
}

interface SourceDetail {
  id: string
  source: string
  type: '' | 'youtube' | 'web' | 'pdf' | 'audio' | 'video' | 'markdown'
  title: string
  duration: number
  language: string
  thumbnail_path: string
  media_path: string
  transcript: string
  chunk_count: number
  status: string
  error: string
  created_at: string
  updated_at: string
  chunks: SourceChunk[]
}

const { data: source, status, error } = await fetchApi<SourceDetail>(
  `/api/knowledge/sources/${sourceId}`
)

// --- Type badge mapping (mirrors knowledge.vue) ---
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

const statusColorMap: Record<string, 'success' | 'error' | 'neutral'> = {
  ready: 'success',
  failed: 'error',
  pending: 'neutral'
}

// --- Derived labels ---
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

const headerTitle = computed(() => {
  const t = source.value?.title?.trim()
  if (t) return t
  return source.value ? sourceLabel(source.value.source) : 'Source'
})

const typeLabel = computed(() => {
  const t = source.value?.type
  if (!t) return 'Unknown'
  return t.charAt(0).toUpperCase() + t.slice(1)
})

// --- Media decision ---
// YouTube: prefer the original embed player (zero-storage, always available)
// when we can parse a video id from the source URL. Otherwise fall back to
// the native player when the backend has a stored media file.
const youtubeEmbedUrl = computed<string | null>(() => {
  if (source.value?.type !== 'youtube') return null
  const src = source.value.source
  if (!src.startsWith('http')) return null
  try {
    const u = new URL(src)
    let id = ''
    if (u.hostname.includes('youtu.be')) {
      id = u.pathname.replace(/^\//, '')
    } else if (u.searchParams.get('v')) {
      id = u.searchParams.get('v') ?? ''
    } else if (u.pathname.startsWith('/embed/')) {
      id = u.pathname.replace('/embed/', '')
    }
    if (!id) return null
    return `https://www.youtube.com/embed/${id}`
  } catch {
    return null
  }
})

const hasStoredMedia = computed(() => Boolean(source.value?.media_path))
const mediaSrc = computed(() => `${apiBase}/api/knowledge/sources/${sourceId}/media`)
const downloadUrl = computed(() => `${apiBase}/api/knowledge/sources/${sourceId}/download`)

const useNativeVideo = computed(() =>
  !youtubeEmbedUrl.value
  && hasStoredMedia.value
  && (source.value?.type === 'video' || source.value?.type === 'youtube')
)
const useNativeAudio = computed(() =>
  !youtubeEmbedUrl.value && hasStoredMedia.value && source.value?.type === 'audio'
)
const isExternalSource = computed(() => Boolean(source.value?.source?.startsWith('http')))

// --- Transcript helpers ---
const wordCount = computed(() => {
  const t = source.value?.transcript?.trim()
  if (!t) return 0
  return t.split(/\s+/).length
})

function formatDuration(seconds: number): string {
  if (!seconds || seconds <= 0) return ''
  const s = Math.floor(seconds % 60)
  const m = Math.floor((seconds / 60) % 60)
  const h = Math.floor(seconds / 3600)
  const pad = (n: number) => n.toString().padStart(2, '0')
  if (h > 0) return `${h}:${pad(m)}:${pad(s)}`
  return `${m}:${pad(s)}`
}

async function copyTranscript() {
  const text = source.value?.transcript ?? ''
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    toast.add({
      title: 'Transcript copied',
      description: `${wordCount.value} words`,
      color: 'success',
      icon: 'i-lucide-check'
    })
  } catch {
    toast.add({
      title: 'Copy failed',
      description: 'Clipboard is not available in this context.',
      color: 'error'
    })
  }
}

// --- Chunk expand/collapse ---
const expanded = ref<Set<number>>(new Set())
function toggleChunk(idx: number) {
  const next = new Set(expanded.value)
  if (next.has(idx)) {
    next.delete(idx)
  } else {
    next.add(idx)
  }
  expanded.value = next
}

// --- Agents: semantic matches + propose-only learning suggestion ---
interface AgentMatch {
  id: string
  name: string
  department: string
  role: string
  score: number
  matched_terms: string[]
}

interface AgentMatchesResponse {
  matches: AgentMatch[]
  source_id?: string
  count?: number
  reason?: string
}

const agentMatches = ref<AgentMatch[]>([])
const agentMatchesLoading = ref(false)
const agentMatchesReason = ref<string | null>(null)
const proposalPending = ref(false)

async function fetchAgentMatches() {
  if (!source.value) return
  agentMatchesLoading.value = true
  agentMatchesReason.value = null
  try {
    const res = await $fetch<AgentMatchesResponse>(
      `${apiBase}/api/knowledge/sources/${sourceId}/agent-matches`,
      { params: { top_n: 5 } }
    )
    agentMatches.value = res.matches ?? []
    agentMatchesReason.value = res.reason ?? null
  } catch {
    agentMatchesReason.value = 'request failed'
    agentMatches.value = []
  } finally {
    agentMatchesLoading.value = false
  }
}

function scorePercent(score: number): number {
  return Math.round(Math.max(0, Math.min(1, score)) * 100)
}

async function generateProposal() {
  if (proposalPending.value) return
  proposalPending.value = true
  try {
    const res = await $fetch<{ proposal_path: string, agents: number }>(
      `${apiBase}/api/knowledge/sources/${sourceId}/agent-proposal`,
      {
        method: 'POST',
        body: { agent_ids: agentMatches.value.map(m => m.id) }
      }
    )
    toast.add({
      title: 'Proposal saved',
      description: res.proposal_path,
      color: 'success',
      icon: 'i-lucide-check'
    })
  } catch {
    toast.add({
      title: 'Could not generate proposal',
      description: 'The proposal request failed. Please try again.',
      color: 'error'
    })
  } finally {
    proposalPending.value = false
  }
}

// Non-blocking: fetch matches once the source resolves on the client.
onMounted(() => {
  if (source.value) fetchAgentMatches()
})
</script>

<template>
  <UDashboardPanel id="knowledge-source">
    <template #header>
      <UDashboardNavbar :title="headerTitle">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #trailing>
          <UButton
            label="Back"
            variant="ghost"
            icon="i-lucide-arrow-left"
            to="/knowledge"
            aria-label="Back to knowledge base"
          />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <!-- Loading -->
      <div v-if="status === 'pending'" class="flex items-center justify-center py-24">
        <UIcon name="i-lucide-loader-2" class="size-8 animate-spin text-muted" />
      </div>

      <!-- Not found (404 from API, or no source data resolved) -->
      <div
        v-else-if="(error && (error.statusCode === 404 || error.data?.error === 'not found')) || !source"
        class="flex flex-col items-center justify-center gap-4 py-24"
      >
        <UIcon name="i-lucide-file-x" class="size-12 text-muted" />
        <p class="text-sm text-muted">
          Source not found.
        </p>
        <UButton
          label="Back to Knowledge"
          variant="outline"
          icon="i-lucide-arrow-left"
          to="/knowledge"
        />
      </div>

      <!-- Error (non-404 failure) -->
      <div
        v-else-if="error"
        class="flex flex-col items-center justify-center gap-4 py-24"
        role="alert"
      >
        <UIcon name="i-lucide-alert-triangle" class="size-12 text-red-500" />
        <p class="text-sm text-muted">
          Failed to load this source.
        </p>
        <UButton
          label="Back to Knowledge"
          variant="outline"
          icon="i-lucide-arrow-left"
          to="/knowledge"
        />
      </div>

      <!-- Content -->
      <div v-else class="space-y-6 pb-12">
        <!-- ===== HEADER ===== -->
        <section class="rounded-2xl border border-default bg-elevated/10 p-6">
          <div class="flex items-start gap-4">
            <div class="shrink-0 size-12 rounded-xl bg-default/80 border border-default flex items-center justify-center">
              <UIcon
                :name="typeIconMap[source.type] ?? 'i-lucide-file'"
                class="size-6 text-muted"
              />
            </div>
            <div class="flex-1 min-w-0 space-y-2">
              <h1 class="text-2xl font-bold tracking-tight text-highlighted break-words">
                {{ headerTitle }}
              </h1>
              <div class="flex flex-wrap items-center gap-2">
                <UBadge
                  :label="typeLabel"
                  :icon="typeIconMap[source.type]"
                  :color="typeColorMap[source.type] ?? 'neutral'"
                  variant="subtle"
                  size="sm"
                />
                <UBadge
                  :label="source.status || 'unknown'"
                  :color="statusColorMap[source.status] ?? 'neutral'"
                  variant="subtle"
                  size="sm"
                  class="capitalize"
                />
                <UBadge
                  v-if="source.language"
                  :label="source.language"
                  variant="outline"
                  size="sm"
                />
                <UBadge
                  v-if="source.duration > 0"
                  :label="formatDuration(source.duration)"
                  icon="i-lucide-clock"
                  variant="outline"
                  size="sm"
                />
                <UBadge
                  :label="`${source.chunk_count} chunk${source.chunk_count === 1 ? '' : 's'}`"
                  variant="subtle"
                  size="sm"
                />
              </div>
              <p class="text-xs text-muted font-mono break-all">
                {{ source.source }}
              </p>
              <p class="text-xs text-muted/60 font-mono select-all">
                {{ source.id }}
              </p>
            </div>
          </div>
          <div
            v-if="source.status === 'failed' && source.error"
            class="mt-4 rounded-lg border border-red-500/20 bg-red-500/5 p-3"
            role="alert"
          >
            <div class="flex items-start gap-2">
              <UIcon name="i-lucide-alert-circle" class="size-4 text-red-500 mt-0.5 shrink-0" />
              <p class="text-sm text-red-400">
                {{ source.error }}
              </p>
            </div>
          </div>
        </section>

        <!-- ===== MEDIA ===== -->
        <section class="rounded-xl border border-default bg-elevated/10 p-5">
          <div class="flex items-center justify-between gap-3 mb-4">
            <h2 class="text-sm font-semibold uppercase tracking-wide text-muted">
              Media
            </h2>
            <UButton
              v-if="hasStoredMedia"
              label="Download"
              icon="i-lucide-download"
              variant="outline"
              size="sm"
              :to="downloadUrl"
              target="_blank"
              external
              aria-label="Download original media file"
            />
          </div>

          <!-- YouTube embed (zero-storage, preferred) -->
          <div
            v-if="youtubeEmbedUrl"
            class="relative w-full overflow-hidden rounded-lg bg-black"
            style="aspect-ratio: 16 / 9"
          >
            <iframe
              :src="youtubeEmbedUrl"
              :title="headerTitle"
              class="absolute inset-0 size-full"
              frameborder="0"
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
              allowfullscreen
            />
          </div>

          <!-- Native video player -->
          <video
            v-else-if="useNativeVideo"
            :src="mediaSrc"
            controls
            class="w-full rounded-lg bg-black"
            preload="metadata"
          >
            Your browser does not support the video element.
          </video>

          <!-- Native audio player -->
          <audio
            v-else-if="useNativeAudio"
            :src="mediaSrc"
            controls
            class="w-full"
            preload="metadata"
          >
            Your browser does not support the audio element.
          </audio>

          <!-- No media -->
          <div v-else class="flex flex-col items-start gap-2 py-2">
            <p class="text-sm text-muted">
              No media for this source.
            </p>
            <UButton
              v-if="isExternalSource"
              :label="sourceLabel(source.source)"
              icon="i-lucide-external-link"
              variant="link"
              size="sm"
              :to="source.source"
              target="_blank"
              external
              :padded="false"
            />
          </div>
        </section>

        <!-- ===== TRANSCRIPT ===== -->
        <section class="rounded-xl border border-default bg-elevated/10 p-5">
          <div class="flex items-center justify-between gap-3 mb-4 flex-wrap">
            <h2 class="text-sm font-semibold uppercase tracking-wide text-muted">
              Transcript
            </h2>
            <div class="flex items-center gap-3">
              <span v-if="wordCount > 0" class="text-xs font-mono text-muted">
                {{ wordCount }} words
                <template v-if="source.duration > 0">· {{ formatDuration(source.duration) }}</template>
              </span>
              <UButton
                v-if="source.transcript"
                label="Copy"
                icon="i-lucide-copy"
                variant="ghost"
                size="xs"
                aria-label="Copy transcript to clipboard"
                @click="copyTranscript"
              />
            </div>
          </div>
          <p v-if="!source.transcript" class="text-sm text-muted py-2">
            No transcript available.
          </p>
          <div
            v-else
            class="max-h-96 overflow-y-auto rounded-lg border border-default bg-default/40 p-4"
          >
            <p class="text-sm leading-relaxed whitespace-pre-wrap font-mono text-highlighted/90">
              {{ source.transcript }}
            </p>
          </div>
        </section>

        <!-- ===== KNOWLEDGE (CHUNKS) ===== -->
        <section class="rounded-xl border border-default bg-elevated/10 p-5">
          <div class="flex items-center justify-between gap-3 mb-4">
            <h2 class="text-sm font-semibold uppercase tracking-wide text-muted">
              Knowledge attributed
            </h2>
            <UBadge
              :label="`${source.chunk_count} chunk${source.chunk_count === 1 ? '' : 's'}`"
              variant="subtle"
              size="sm"
            />
          </div>
          <p v-if="!source.chunks?.length" class="text-sm text-muted py-2">
            No chunks indexed from this source.
          </p>
          <ul v-else class="space-y-2">
            <li
              v-for="(chunk, idx) in source.chunks"
              :key="idx"
              class="rounded-lg border border-default bg-default/30 p-3"
            >
              <button
                type="button"
                class="flex items-start gap-2 w-full text-left"
                :aria-expanded="expanded.has(idx)"
                :aria-label="expanded.has(idx) ? 'Collapse chunk' : 'Expand chunk'"
                @click="toggleChunk(idx)"
              >
                <UIcon
                  :name="expanded.has(idx) ? 'i-lucide-chevron-down' : 'i-lucide-chevron-right'"
                  class="size-4 text-muted mt-0.5 shrink-0"
                />
                <div class="flex-1 min-w-0">
                  <p
                    v-if="chunk.heading"
                    class="text-sm font-semibold text-highlighted mb-1"
                  >
                    {{ chunk.heading }}
                  </p>
                  <p
                    class="text-sm text-muted whitespace-pre-wrap"
                    :class="expanded.has(idx) ? '' : 'line-clamp-2'"
                  >
                    {{ chunk.text }}
                  </p>
                </div>
              </button>
            </li>
          </ul>
        </section>

        <!-- ===== AGENTS ===== -->
        <section class="rounded-xl border border-default bg-elevated/10 p-5">
          <div class="flex items-start justify-between gap-3 mb-4 flex-wrap">
            <div class="flex-1 min-w-0 space-y-1">
              <div class="flex items-center gap-2">
                <UIcon name="i-lucide-users" class="size-4 text-muted" />
                <h2 class="text-sm font-semibold uppercase tracking-wide text-muted">
                  Agents
                </h2>
              </div>
              <p class="text-sm text-muted">
                Agents whose expertise matches this source — suggested to learn from it.
              </p>
            </div>
            <div class="flex flex-col items-end gap-1">
              <UButton
                label="Generate proposal"
                icon="i-lucide-file-output"
                variant="outline"
                size="sm"
                :loading="proposalPending"
                :disabled="agentMatchesLoading || !agentMatches.length"
                aria-label="Generate a review-only learning proposal for the matched agents"
                @click="generateProposal"
              />
              <p class="text-xs text-muted/70 max-w-xs text-right">
                Generates a review-only proposal — it never edits agent files automatically.
              </p>
            </div>
          </div>

          <!-- Loading -->
          <div
            v-if="agentMatchesLoading"
            class="flex items-center gap-2 py-4 text-sm text-muted"
          >
            <UIcon name="i-lucide-loader-2" class="size-4 animate-spin" />
            Finding relevant agents…
          </div>

          <!-- Embedder offline -->
          <p
            v-else-if="agentMatchesReason === 'embedder unavailable'"
            class="text-sm text-muted py-2"
          >
            Semantic matching is offline (vector embeddings unavailable). Install fastembed to enable agent suggestions.
          </p>

          <!-- No matches / no source text -->
          <p
            v-else-if="!agentMatches.length"
            class="text-sm text-muted py-2"
          >
            No agent suggestions for this source yet.
          </p>

          <!-- Matches -->
          <ul v-else class="space-y-2">
            <li
              v-for="agent in agentMatches"
              :key="agent.id"
              class="rounded-lg border border-default bg-default/30 p-4"
            >
              <div class="flex items-start justify-between gap-3 flex-wrap">
                <div class="min-w-0 space-y-1">
                  <div class="flex items-center gap-2 flex-wrap">
                    <NuxtLink
                      :to="`/agents/${agent.id}`"
                      class="text-sm font-semibold text-highlighted hover:text-primary transition-colors"
                    >
                      {{ agent.name }}
                    </NuxtLink>
                    <UBadge
                      v-if="agent.department"
                      :label="agent.department"
                      variant="subtle"
                      color="neutral"
                      size="xs"
                    />
                  </div>
                  <p v-if="agent.role" class="text-xs text-muted">
                    {{ agent.role }}
                  </p>
                </div>
                <div class="flex flex-col items-end gap-1 shrink-0 min-w-32">
                  <span class="text-xs font-mono text-muted">
                    {{ scorePercent(agent.score) }}% match
                  </span>
                  <UProgress
                    :value="scorePercent(agent.score)"
                    :max="100"
                    size="xs"
                    class="w-32"
                    :aria-label="`${agent.name} relevance ${scorePercent(agent.score)} percent`"
                  />
                </div>
              </div>
              <div
                v-if="agent.matched_terms?.length"
                class="mt-3 flex flex-wrap gap-1.5"
              >
                <UBadge
                  v-for="term in agent.matched_terms"
                  :key="term"
                  :label="term"
                  variant="soft"
                  color="primary"
                  size="xs"
                />
              </div>
            </li>
          </ul>
        </section>
      </div>
    </template>
  </UDashboardPanel>
</template>
