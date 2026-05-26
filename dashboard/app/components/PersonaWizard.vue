<script setup lang="ts">
import type { Persona } from '~/types'

// PR62 v2.79.0 — 4-step AI-powered persona wizard.
// Replaces the original "fill a 30-field form" UX with:
//   1. Sources  → operator pastes URLs / picks files, optionally types a name
//   2. Ingest   → existing /api/knowledge/ingest-bulk fans the URLs out into
//                 background jobs and shows progress via WebSocket
//   3. Build    → /api/personas/build (PR57) reads the indexed chunks and
//                 returns a draft Persona; operator reviews + edits
//   4. Save     → POST /api/personas (manual create path), optional
//                 clone-to-agent at the end
//
// The wizard NEVER auto-saves — every transition is operator-confirmed.

const { apiBase } = useApi()
const toast = useToast()

const emit = defineEmits<{
  (e: 'completed', persona: Persona): void
  (e: 'cancelled'): void
}>()

type Step = 1 | 2 | 3 | 4
const step = ref<Step>(1)

// ─── Step 1 state ────────────────────────────────────────────────────────
const name = ref('')
const sourceLabel = ref('')
const sources = ref('')
const skipIngest = ref(false)
const sourceLineCount = computed(() =>
  sources.value
    .split('\n')
    .map((s) => s.trim())
    .filter((s) => s.length > 0)
    .length,
)

// PR83a v3.3.0 — Mode 3: build from a free-text description (no chunks).
type Mode = 'sources' | 'existing' | 'description'
const mode = ref<Mode>('sources')
const description = ref('')
const descriptionLength = computed(() => description.value.trim().length)

// ─── Step 2 state ────────────────────────────────────────────────────────
const ingestJobs = ref<Array<{
  source: string
  job_id?: string
  status: 'queued' | 'processing' | 'completed' | 'failed'
  progress: number
  error?: string
}>>([])
let ws: WebSocket | null = null
const allIngestComplete = computed(() =>
  ingestJobs.value.length > 0
  && ingestJobs.value.every((j) => j.status === 'completed' || j.status === 'failed'),
)
const ingestCompletedCount = computed(() =>
  ingestJobs.value.filter((j) => j.status === 'completed').length,
)

// ─── Step 3 state ────────────────────────────────────────────────────────
const draft = ref<Persona | null>(null)
const building = ref(false)
const buildError = ref<string | null>(null)
const chunksUsed = ref<number | null>(null)

// ─── Step 4 state ────────────────────────────────────────────────────────
const saving = ref(false)
const saveAndClone = ref(false)
const cloneDept = ref('strategy')
const cloneTier = ref<'1' | '2' | '3'>('2')

const departmentOptions = [
  'dev', 'marketing', 'brand', 'finance', 'strategy', 'ecom', 'kb', 'ops',
  'pm', 'saas', 'landing', 'content', 'community', 'sales', 'leadership', 'org',
].map((d) => ({ label: d, value: d }))

const tierOptions = [
  { label: 'Tier 1 — Squad Lead', value: '1' },
  { label: 'Tier 2 — Specialist', value: '2' },
  { label: 'Tier 3 — Support', value: '3' },
]

// ─── Step 1 → 2 transition ───────────────────────────────────────────────


async function startIngest() {
  if (mode.value === 'description') {
    // PR83a — no ingest, no chunks. Build directly from description.
    if (descriptionLength.value < 20 || !name.value.trim()) return
    step.value = 3
    await runDescriptionBuild()
    return
  }
  if (mode.value === 'existing' || skipIngest.value) {
    // Jump straight to step 3 — operator says content is already indexed.
    step.value = 3
    await runBuild()
    return
  }
  const cleaned = sources.value
    .split('\n')
    .map((s) => s.trim())
    .filter((s) => s.length > 0)
  if (cleaned.length === 0 || !name.value.trim()) return
  step.value = 2
  ingestJobs.value = cleaned.map((source) => ({
    source,
    status: 'queued',
    progress: 0,
  }))
  try {
    const res = await $fetch<{ jobs: Array<{ source: string, job_id?: string, error?: string }>, count: number }>(
      `${apiBase}/api/knowledge/ingest-bulk`,
      { method: 'POST', body: { sources: cleaned } },
    )
    res.jobs.forEach((j) => {
      const row = ingestJobs.value.find((r) => r.source === j.source)
      if (!row) return
      if (j.error) {
        row.status = 'failed'
        row.error = j.error
      } else if (j.job_id) {
        row.job_id = j.job_id
        row.status = 'processing'
      }
    })
    connectWebSocket()
  } catch (err) {
    toast.add({
      title: 'Ingest failed',
      description: err instanceof Error ? err.message : 'unknown error',
      color: 'error',
    })
    step.value = 1
  }
}


function connectWebSocket() {
  if (ws && ws.readyState === WebSocket.OPEN) return
  const wsUrl = apiBase.replace('http://', 'ws://').replace('https://', 'wss://') + '/ws/tasks'
  ws = new WebSocket(wsUrl)
  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      const row = ingestJobs.value.find((j) => j.job_id === data.job_id)
      if (!row) return
      if (data.type === 'job_progress') {
        row.progress = data.progress
        row.status = 'processing'
      } else if (data.type === 'job_complete') {
        row.status = 'completed'
        row.progress = 100
      } else if (data.type === 'job_failed') {
        row.status = 'failed'
        row.error = data.error
      }
    } catch { /* ignore malformed messages */ }
  }
}


function disconnectWebSocket() {
  if (ws) {
    try { ws.close() } catch { /* already closed */ }
    ws = null
  }
}


onBeforeUnmount(() => {
  disconnectWebSocket()
})


// ─── Step 3: build the persona draft ────────────────────────────────────


async function runDescriptionBuild() {
  building.value = true
  buildError.value = null
  draft.value = null
  try {
    const res = await $fetch<{ persona: Persona, provider_name: string, error?: string }>(
      `${apiBase}/api/personas/draft`,
      {
        method: 'POST',
        body: {
          name: name.value.trim(),
          description: description.value.trim(),
          source_label: sourceLabel.value.trim() || name.value.trim(),
        },
      },
    )
    if ('error' in res && typeof (res as any).error === 'string') {
      throw new Error((res as any).error)
    }
    draft.value = res.persona
    chunksUsed.value = 0
    step.value = 4
  } catch (err) {
    buildError.value = err instanceof Error ? err.message : 'unknown error'
  } finally {
    building.value = false
  }
}


async function runBuild() {
  building.value = true
  buildError.value = null
  draft.value = null
  try {
    const res = await $fetch<{ persona: Persona, chunks_used: number, provider_name: string }>(
      `${apiBase}/api/personas/build`,
      {
        method: 'POST',
        body: {
          name: name.value.trim(),
          source_label: sourceLabel.value.trim() || name.value.trim(),
        },
      },
    )
    if ('error' in res && typeof (res as any).error === 'string') {
      throw new Error((res as any).error)
    }
    draft.value = res.persona
    chunksUsed.value = res.chunks_used
    step.value = 4
  } catch (err) {
    buildError.value = err instanceof Error ? err.message : 'unknown error'
  } finally {
    building.value = false
  }
}


// ─── Step 4: save + optional clone ──────────────────────────────────────


async function savePersona() {
  if (!draft.value) return
  saving.value = true
  try {
    const created = await $fetch<Persona>(`${apiBase}/api/personas`, {
      method: 'POST',
      body: draft.value,
    })
    if (saveAndClone.value && cloneDept.value && cloneTier.value) {
      await $fetch(`${apiBase}/api/personas/${created.id}/clone`, {
        method: 'POST',
        body: { department: cloneDept.value, tier: Number(cloneTier.value) },
      })
    }
    toast.add({
      title: saveAndClone.value ? 'Persona saved + agent cloned' : 'Persona saved',
      description: `${created.name} is now in your board.`,
      color: 'success',
    })
    emit('completed', created)
  } catch (err) {
    toast.add({
      title: 'Save failed',
      description: err instanceof Error ? err.message : 'unknown error',
      color: 'error',
    })
  } finally {
    saving.value = false
  }
}


// ─── Auto-advance when ingest completes ─────────────────────────────────


watch(allIngestComplete, async (done) => {
  if (done && step.value === 2 && ingestCompletedCount.value > 0) {
    step.value = 3
    await runBuild()
  }
})


function cancel() {
  disconnectWebSocket()
  emit('cancelled')
}


function backToStep1() {
  disconnectWebSocket()
  step.value = 1
  ingestJobs.value = []
}
</script>

<template>
  <UCard>
    <template #header>
      <div class="flex items-center justify-between">
        <div>
          <h3 class="text-lg font-semibold">AI Persona Builder</h3>
          <p class="text-sm text-muted mt-1">
            Step {{ step }} of 4 — {{ {
              1: 'Sources',
              2: 'Indexing',
              3: 'Generating DNA',
              4: 'Review & save',
            }[step] }}
          </p>
        </div>
        <UButton
          label="Cancel"
          variant="ghost"
          color="neutral"
          size="sm"
          @click="cancel"
        />
      </div>
    </template>

    <!-- Progress indicator -->
    <div class="flex items-center gap-2 mb-6">
      <div
        v-for="s in [1, 2, 3, 4] as Step[]"
        :key="s"
        class="flex-1 h-1 rounded-full"
        :class="s <= step ? 'bg-primary' : 'bg-muted/30'"
      />
    </div>

    <!-- Step 1: Sources -->
    <div v-if="step === 1" class="space-y-4">
      <UFormField label="Person name" required>
        <UInput
          v-model="name"
          placeholder="e.g. Alex Hormozi"
          size="lg"
          class="w-full"
        />
      </UFormField>

      <UFormField label="Source label (optional)" help="How this person should appear in the persona's source field. Defaults to the name above.">
        <UInput
          v-model="sourceLabel"
          placeholder="e.g. Alex Hormozi — $100M Offers / $100M Leads"
          class="w-full"
        />
      </UFormField>

      <UFormField label="How should we generate this persona?">
        <div class="grid grid-cols-1 md:grid-cols-3 gap-2">
          <button
            v-for="m in ([
              { key: 'sources',     title: 'Ingest sources',  desc: 'YouTube, articles, PDFs — best fidelity' },
              { key: 'existing',    title: 'Existing chunks', desc: 'Use what is already indexed' },
              { key: 'description', title: 'From description', desc: 'No sources — pure description' },
            ] as const)"
            :key="m.key"
            type="button"
            class="text-left rounded-lg border p-3 transition-colors"
            :class="mode === m.key ? 'border-primary bg-primary/5' : 'border-default hover:border-primary/40'"
            @click="mode = m.key"
          >
            <p class="text-sm font-semibold">{{ m.title }}</p>
            <p class="text-xs text-muted mt-1">{{ m.desc }}</p>
          </button>
        </div>
      </UFormField>

      <UFormField
        v-if="mode === 'sources'"
        label="Sources (one URL per line)"
        help="YouTube videos, articles, PDFs, blog posts about this person. The builder will search the indexed chunks and synthesise their behavioural DNA. Up to 50 sources per batch."
      >
        <UTextarea
          v-model="sources"
          :rows="6"
          placeholder="https://www.youtube.com/watch?v=...&#10;https://example.com/article&#10;https://example.com/paper.pdf"
          class="w-full font-mono text-sm"
        />
      </UFormField>

      <UFormField
        v-else-if="mode === 'description'"
        label="Description"
        help="Plain-text description of the person — their style, beliefs, what they do, how they talk. The LLM uses this verbatim. Minimum 20 characters."
      >
        <UTextarea
          v-model="description"
          :rows="6"
          placeholder="A direct-response copywriter who treats offers as the only true growth lever. Punchy, allergic to fluff. Loves Hormozi-style hooks."
          class="w-full"
        />
      </UFormField>

      <div
        v-if="mode === 'sources'"
        class="flex items-center justify-between text-xs text-muted"
      >
        <span>{{ sourceLineCount }} source{{ sourceLineCount === 1 ? '' : 's' }} detected</span>
      </div>

      <div v-else-if="mode === 'existing'" class="text-xs text-muted">
        We will search the vector DB for chunks tagged with this name and synthesise from what we find. Make sure you've ingested content for this person first.
      </div>

      <div v-else-if="mode === 'description'" class="text-xs text-muted">
        {{ descriptionLength }} character{{ descriptionLength === 1 ? '' : 's' }} ·
        {{ descriptionLength >= 20 ? 'ready' : `${20 - descriptionLength} more needed` }}
      </div>

      <div class="flex justify-end gap-2 pt-4">
        <UButton
          :label="(
            mode === 'sources' ? `Index ${sourceLineCount} source${sourceLineCount === 1 ? '' : 's'} & build`
            : mode === 'existing' ? 'Generate from existing knowledge'
            : 'Generate from description'
          )"
          icon="i-lucide-arrow-right"
          :disabled="(
            !name.trim()
            || (mode === 'sources' && (sourceLineCount === 0 || sourceLineCount > 50))
            || (mode === 'description' && descriptionLength < 20)
          )"
          size="md"
          @click="startIngest"
        />
      </div>
      <p v-if="mode === 'sources' && sourceLineCount > 50" class="text-xs text-red-400">
        Over the 50-source cap. Trim the list before continuing.
      </p>
    </div>

    <!-- Step 2: Ingest progress -->
    <div v-else-if="step === 2" class="space-y-4">
      <p class="text-sm text-muted">
        Indexing {{ ingestJobs.length }} source{{ ingestJobs.length === 1 ? '' : 's' }} into the knowledge base.
        This auto-advances when complete.
      </p>
      <div class="space-y-2">
        <div
          v-for="(job, idx) in ingestJobs"
          :key="idx"
          class="rounded-lg border border-default p-3"
        >
          <div class="flex items-center gap-3">
            <UIcon
              :name="{
                queued: 'i-lucide-clock',
                processing: 'i-lucide-loader-2 animate-spin',
                completed: 'i-lucide-check-circle',
                failed: 'i-lucide-x-circle',
              }[job.status]"
              :class="{
                queued: 'text-muted',
                processing: 'text-primary',
                completed: 'text-green-500',
                failed: 'text-red-500',
              }[job.status]"
              class="size-4 shrink-0"
            />
            <div class="flex-1 min-w-0">
              <p class="text-sm font-mono truncate">{{ job.source }}</p>
              <UProgress
                v-if="job.status === 'processing' || job.status === 'queued'"
                :value="job.progress"
                :max="100"
                size="xs"
                class="mt-1"
              />
              <p v-if="job.error" class="text-xs text-red-400 mt-1">{{ job.error }}</p>
            </div>
            <span class="text-xs text-muted">{{ job.progress }}%</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Step 3: Building -->
    <div v-else-if="step === 3" class="space-y-4">
      <div v-if="building" class="flex flex-col items-center gap-4 py-12">
        <UIcon name="i-lucide-loader-2" class="size-12 animate-spin text-primary" />
        <p class="text-sm text-muted">
          Reading indexed chunks about <strong>{{ name }}</strong>…
        </p>
        <p class="text-xs text-muted">
          The builder searches the vector store, joins the top chunks, and asks the configured LLM to extract a behavioural-DNA persona.
        </p>
      </div>
      <div v-else-if="buildError" class="rounded-lg border border-red-500/20 bg-red-500/5 p-4">
        <div class="flex items-start gap-3">
          <UIcon name="i-lucide-alert-circle" class="size-5 text-red-500 mt-0.5 shrink-0" />
          <div class="flex-1">
            <p class="text-sm font-medium text-red-400">Build failed</p>
            <p class="text-xs text-muted mt-1">{{ buildError }}</p>
          </div>
        </div>
        <div class="flex gap-2 mt-3">
          <UButton label="Retry" variant="outline" size="sm" @click="runBuild" />
          <UButton label="Back to sources" variant="ghost" size="sm" @click="backToStep1" />
        </div>
      </div>
    </div>

    <!-- Step 4: Review & save -->
    <div v-else-if="step === 4 && draft" class="space-y-4">
      <div class="rounded-lg border border-green-500/20 bg-green-500/5 p-3">
        <p class="text-sm text-green-400">
          <UIcon name="i-lucide-sparkles" class="size-4 inline" />
          Built from <strong>{{ chunksUsed }}</strong> knowledge chunk{{ chunksUsed === 1 ? '' : 's' }}. Edit any field below before saving.
        </p>
      </div>

      <fieldset class="space-y-3">
        <legend class="text-xs font-bold uppercase tracking-widest text-muted mb-2">Identity</legend>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
          <UFormField label="Name">
            <UInput v-model="draft.name" class="w-full" />
          </UFormField>
          <UFormField label="Title">
            <UInput v-model="draft.title" class="w-full" />
          </UFormField>
        </div>
        <UFormField label="Tagline">
          <UInput v-model="draft.tagline" class="w-full" />
        </UFormField>
      </fieldset>

      <fieldset class="space-y-3">
        <legend class="text-xs font-bold uppercase tracking-widest text-muted mb-2">Behavioural DNA</legend>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
          <UFormField label="MBTI">
            <UInput v-model="draft.mbti" class="w-full" />
          </UFormField>
          <UFormField label="DISC primary">
            <UInput v-model="draft.disc.primary" class="w-full" />
          </UFormField>
          <UFormField label="Enneagram type">
            <UInput v-model.number="draft.enneagram.type" type="number" :min="1" :max="9" class="w-full" />
          </UFormField>
          <UFormField label="Enneagram wing">
            <UInput v-model.number="draft.enneagram.wing" type="number" :min="1" :max="9" class="w-full" />
          </UFormField>
        </div>
      </fieldset>

      <fieldset class="space-y-3">
        <legend class="text-xs font-bold uppercase tracking-widest text-muted mb-2">Knowledge</legend>
        <UFormField label="Mental models" help="comma-separated">
          <UInput
            :model-value="draft.mental_models.join(', ')"
            @update:model-value="(v: string) => draft && (draft.mental_models = v.split(',').map(s => s.trim()).filter(Boolean))"
            class="w-full"
          />
        </UFormField>
        <UFormField label="Expertise domains" help="comma-separated">
          <UInput
            :model-value="draft.expertise_domains.join(', ')"
            @update:model-value="(v: string) => draft && (draft.expertise_domains = v.split(',').map(s => s.trim()).filter(Boolean))"
            class="w-full"
          />
        </UFormField>
      </fieldset>

      <fieldset class="space-y-3">
        <legend class="text-xs font-bold uppercase tracking-widest text-muted mb-2">Save options</legend>
        <UCheckbox
          v-model="saveAndClone"
          label="Also clone to an agent immediately"
        />
        <div v-if="saveAndClone" class="grid grid-cols-2 gap-3 pl-6">
          <UFormField label="Department">
            <USelect v-model="cloneDept" :items="departmentOptions" class="w-full" />
          </UFormField>
          <UFormField label="Tier">
            <USelect v-model="cloneTier" :items="tierOptions" class="w-full" />
          </UFormField>
        </div>
      </fieldset>

      <div class="flex justify-end gap-2 pt-4">
        <UButton label="Back" variant="ghost" @click="backToStep1" />
        <UButton
          :label="saveAndClone ? 'Save & clone' : 'Save persona'"
          icon="i-lucide-check"
          :loading="saving"
          @click="savePersona"
        />
      </div>
    </div>
  </UCard>
</template>
