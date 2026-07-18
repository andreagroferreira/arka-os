<script setup lang="ts">
// PR76 v2.94.0 — Agent edit drawer.
//
// Opens from the agent detail hero. Lets non-technical operators
// edit the safe-to-mutate fields without touching YAML directly:
//
//   - Identity (name, role, tier)
//   - Mental models (primary + secondary lists)
//   - Frameworks list
//   - Expertise domains + depth + years
//   - Communication (tone, vocab level, preferred format, avoid)
//   - Linked personas (multi-select from /api/personas)
//
// Save → PUT /api/agents/{id} (atomic YAML write on the backend).
// NEVER edits: id, department, behavioural DNA (DISC/Enneagram/MBTI/
// Big-Five). Those are intentionally locked because changing them
// silently invalidates the agent's identity model.

import type { Persona } from '~/types'

// Shape of the agent payload this drawer edits. Mirrors the safe-to-mutate
// fields returned by GET /api/agents/{id} — everything optional except id,
// because the backend only includes populated keys.
interface AgentEditable {
  id: string
  name?: string
  role?: string
  department?: string
  tier?: number
  mental_models?: { primary?: string[], secondary?: string[] }
  frameworks?: string[]
  expertise_domains?: string[]
  expertise_depth?: string
  expertise_years?: number
  communication?: {
    tone?: string
    vocabulary_level?: string
    preferred_format?: string
    language?: string
    avoid?: string[]
  }
  linked_personas?: string[]
  bio_md?: string
}

// Shape of the AI-generated draft returned by POST /api/agents/draft.
// Values are unknown at the boundary — applyRewrite validates each one
// (Array.isArray / typeof) before assigning into the typed draft.
interface RewriteDraft {
  expertise?: {
    domains?: unknown
    frameworks?: unknown
    depth?: unknown
    years_equivalent?: unknown
  }
  mental_models?: {
    primary?: unknown
    secondary?: unknown
  }
  communication?: {
    tone?: unknown
    vocabulary_level?: unknown
    preferred_format?: unknown
    language?: unknown
    avoid?: unknown
  }
}

const props = defineProps<{
  modelValue: boolean
  agent: AgentEditable | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'saved'): void
}>()

const { apiBase, fetchApi } = useApi()
const toast = useToast()
const confirmDialog = useConfirmDialog()

// Persona list — for the linked_personas multi-select.
const { data: personasData } = fetchApi<{ personas: Persona[] }>('/api/personas')
const personaOptions = computed(() =>
  (personasData.value?.personas ?? []).map(p => ({
    label: p.name + (p.title ? ` — ${p.title}` : ''),
    value: p.id
  }))
)

interface AgentDraft {
  name: string
  role: string
  tier: number
  mental_models: { primary: string[], secondary: string[] }
  frameworks: string[]
  expertise_domains: string[]
  expertise_depth: string
  expertise_years: number
  communication: {
    tone: string
    vocabulary_level: string
    preferred_format: string
    language: string
    avoid: string[]
  }
  linked_personas: string[]
  bio_md: string
}

const draft = ref<AgentDraft | null>(null)
const saving = ref(false)
const dirty = ref(false)

watch(
  () => [props.modelValue, props.agent] as const,
  ([open, agent]) => {
    if (open && agent) {
      draft.value = {
        name: agent.name ?? '',
        role: agent.role ?? '',
        tier: agent.tier ?? 2,
        mental_models: {
          primary: agent.mental_models?.primary ?? [],
          secondary: agent.mental_models?.secondary ?? []
        },
        frameworks: agent.frameworks ?? [],
        expertise_domains: agent.expertise_domains ?? [],
        expertise_depth: agent.expertise_depth ?? '',
        expertise_years: agent.expertise_years ?? 0,
        communication: {
          tone: agent.communication?.tone ?? '',
          vocabulary_level: agent.communication?.vocabulary_level ?? '',
          preferred_format: agent.communication?.preferred_format ?? '',
          language: agent.communication?.language ?? '',
          avoid: agent.communication?.avoid ?? []
        },
        linked_personas: agent.linked_personas ?? [],
        bio_md: agent.bio_md ?? ''
      }
      dirty.value = false
    } else if (!open) {
      draft.value = null
      dirty.value = false
    }
  },
  { immediate: true }
)

function markDirty() {
  dirty.value = true
}

function listToCsv(list: string[]): string {
  return (list ?? []).join(', ')
}

function csvToList(value: string): string[] {
  return value.split(',').map(s => s.trim()).filter(Boolean)
}

// PR81 v2.99.0 — AI list-field suggester.
// PR82c v3.2.0 — extended with 'communication_avoid'.
type SuggestField = 'mental_models_primary' | 'frameworks' | 'expertise_domains' | 'communication_avoid'
const suggestingField = ref<SuggestField | null>(null)

// PR84a v3.7.0 — AI Rewrite from description.
const rewriteOpen = ref(false)
const rewriteDescription = ref('')
const rewriting = ref(false)

async function rewriteFromDescription() {
  if (!draft.value || !props.agent) return
  const desc = rewriteDescription.value.trim()
  if (desc.length < 20) {
    toast.add({
      title: 'Add more detail',
      description: 'Describe the agent in at least a sentence or two.',
      color: 'warning'
    })
    return
  }
  rewriting.value = true
  try {
    const res = await $fetch<{
      draft: RewriteDraft
      provider_name: string
      error?: string
    }>(`${apiBase}/api/agents/draft`, {
      method: 'POST',
      body: {
        description: desc,
        name: draft.value.name,
        role: draft.value.role,
        department: props.agent.department,
        tier: draft.value.tier
      }
    })
    if (res.error) throw new Error(res.error)
    applyRewrite(res.draft)
    markDirty()
    toast.add({
      title: 'Rewritten',
      description: `via ${res.provider_name} — review and Save when ready.`,
      color: 'success',
      icon: 'i-lucide-sparkles'
    })
    rewriteOpen.value = false
    rewriteDescription.value = ''
  } catch (err) {
    toast.add({
      title: 'Rewrite failed',
      description: err instanceof Error ? err.message : 'unknown error',
      color: 'error'
    })
  } finally {
    rewriting.value = false
  }
}

function applyRewrite(d: RewriteDraft) {
  if (!draft.value) return
  // NOTE: identity (id, department) stays. Behavioural DNA is intentionally
  // not editable here, so we do not touch it. We rewrite the SAFE fields
  // operators edit through this drawer.
  const exp = d?.expertise ?? {}
  if (Array.isArray(exp.domains)) draft.value.expertise_domains = exp.domains.map(String)
  if (Array.isArray(exp.frameworks)) draft.value.frameworks = exp.frameworks.map(String)
  if (exp.depth) draft.value.expertise_depth = String(exp.depth)
  if (typeof exp.years_equivalent === 'number') draft.value.expertise_years = exp.years_equivalent
  const mm = d?.mental_models ?? {}
  if (Array.isArray(mm.primary)) draft.value.mental_models.primary = mm.primary.map(String)
  if (Array.isArray(mm.secondary)) draft.value.mental_models.secondary = mm.secondary.map(String)
  const comm = d?.communication ?? {}
  if (comm.tone) draft.value.communication.tone = String(comm.tone)
  if (comm.vocabulary_level) draft.value.communication.vocabulary_level = String(comm.vocabulary_level)
  if (comm.preferred_format) draft.value.communication.preferred_format = String(comm.preferred_format)
  if (comm.language) draft.value.communication.language = String(comm.language)
  if (Array.isArray(comm.avoid)) draft.value.communication.avoid = comm.avoid.map(String)
}

// PR83c v3.5.0 — single-string suggester.
type StringField = 'tone' | 'preferred_format'
const suggestingString = ref<StringField | null>(null)

async function suggestString(field: StringField) {
  if (!draft.value || !props.agent) return
  const current
    = field === 'tone' ? draft.value.communication.tone : draft.value.communication.preferred_format
  suggestingString.value = field
  try {
    const res = await $fetch<{ value: string, provider_name: string, error?: string }>(
      `${apiBase}/api/agents/suggest-string`,
      {
        method: 'POST',
        body: {
          field,
          context: {
            name: props.agent.name,
            role: props.agent.role,
            department: props.agent.department,
            current
          }
        }
      }
    )
    if (res.error) throw new Error(res.error)
    if (field === 'tone') draft.value.communication.tone = res.value
    else draft.value.communication.preferred_format = res.value
    markDirty()
    toast.add({
      title: 'Generated',
      description: `via ${res.provider_name}`,
      color: 'success',
      icon: 'i-lucide-sparkles'
    })
  } catch (err) {
    toast.add({
      title: 'Generate failed',
      description: err instanceof Error ? err.message : 'unknown error',
      color: 'error'
    })
  } finally {
    suggestingString.value = null
  }
}

async function suggest(field: SuggestField) {
  if (!draft.value || !props.agent) return
  const backendField = field === 'mental_models_primary' ? 'mental_models' : field
  const current
    = field === 'mental_models_primary'
      ? draft.value.mental_models.primary
      : field === 'frameworks'
        ? draft.value.frameworks
        : field === 'expertise_domains'
          ? draft.value.expertise_domains
          : draft.value.communication.avoid
  suggestingField.value = field
  try {
    const res = await $fetch<{
      suggestions: string[]
      provider_name: string
      error?: string
    }>(`${apiBase}/api/agents/suggest`, {
      method: 'POST',
      body: {
        field: backendField,
        count: 5,
        context: {
          name: props.agent.name,
          role: props.agent.role,
          department: props.agent.department,
          current
        }
      }
    })
    if (res.error) throw new Error(res.error)
    const additions = (res.suggestions ?? []).filter(
      s => !current.some(c => c.toLowerCase() === s.toLowerCase())
    )
    if (additions.length === 0) {
      toast.add({
        title: 'No new suggestions',
        description: 'The model returned only items you already have.',
        color: 'info'
      })
      return
    }
    const merged = [...current, ...additions]
    if (field === 'mental_models_primary') {
      draft.value.mental_models.primary = merged
    } else if (field === 'frameworks') {
      draft.value.frameworks = merged
    } else if (field === 'expertise_domains') {
      draft.value.expertise_domains = merged
    } else {
      draft.value.communication.avoid = merged
    }
    markDirty()
    toast.add({
      title: `Added ${additions.length} suggestion${additions.length === 1 ? '' : 's'}`,
      description: `via ${res.provider_name}`,
      color: 'success',
      icon: 'i-lucide-sparkles'
    })
  } catch (err) {
    toast.add({
      title: 'Suggestion failed',
      description: err instanceof Error ? err.message : 'unknown error',
      color: 'error'
    })
  } finally {
    suggestingField.value = null
  }
}

async function save() {
  if (!draft.value || !props.agent?.id) return
  saving.value = true
  try {
    const payload = {
      name: draft.value.name,
      role: draft.value.role,
      tier: draft.value.tier,
      mental_models: draft.value.mental_models,
      frameworks: draft.value.frameworks,
      expertise_domains: draft.value.expertise_domains,
      expertise: {
        depth: draft.value.expertise_depth,
        years_equivalent: draft.value.expertise_years
      },
      communication: draft.value.communication,
      linked_personas: draft.value.linked_personas,
      bio_md: draft.value.bio_md
    }
    const res = await $fetch<{
      id: string
      updated: boolean
      yaml_path?: string
      error?: string
    }>(`${apiBase}/api/agents/${props.agent.id}`, {
      method: 'PUT',
      body: payload
    })
    if (res.error) throw new Error(res.error)
    toast.add({
      title: 'Agent saved',
      description: res.yaml_path
        ? `Wrote ${res.yaml_path.split('/').slice(-3).join('/')}`
        : 'YAML updated',
      color: 'success'
    })
    dirty.value = false
    emit('saved')
    emit('update:modelValue', false)
  } catch (err) {
    toast.add({
      title: 'Save failed',
      description: err instanceof Error ? err.message : 'unknown error',
      color: 'error'
    })
  } finally {
    saving.value = false
  }
}

async function tryClose() {
  if (dirty.value && !saving.value) {
    const ok = await confirmDialog({
      title: 'Discard unsaved edits?',
      description: 'Any changes you made to this agent will be lost.',
      confirmLabel: 'Discard',
      cancelLabel: 'Keep editing',
      variant: 'danger'
    })
    if (!ok) return
  }
  emit('update:modelValue', false)
}

const tierOptions = [
  { label: 'Tier 0 — C-Suite', value: 0 },
  { label: 'Tier 1 — Squad Lead', value: 1 },
  { label: 'Tier 2 — Specialist', value: 2 },
  { label: 'Tier 3 — Support', value: 3 }
]
const depthOptions = [
  { label: 'Intermediate', value: 'intermediate' },
  { label: 'Advanced', value: 'advanced' },
  { label: 'Expert', value: 'expert' },
  { label: 'Master', value: 'master' }
]
const vocabOptions = [
  { label: 'Lay (no jargon)', value: 'lay' },
  { label: 'Specialist (industry terms)', value: 'specialist' },
  { label: 'Expert (research-level)', value: 'expert' }
]
</script>

<template>
  <USlideover
    :open="modelValue"
    :ui="{ content: 'max-w-2xl w-full' }"
    @update:open="(v) => v ? null : tryClose()"
  >
    <template #content>
      <UCard
        :ui="{
          root: 'h-full flex flex-col rounded-none',
          body: 'flex-1 overflow-y-auto'
        }"
      >
        <template #header>
          <div class="flex items-center justify-between gap-3">
            <div>
              <h2 class="text-xl font-bold">
                Edit agent
              </h2>
              <p class="text-sm text-muted mt-0.5">
                {{ props.agent?.name }}
                <span class="text-xs text-muted/60 ml-1">— {{ props.agent?.id }}</span>
              </p>
            </div>
            <UButton
              icon="i-lucide-x"
              variant="ghost"
              size="sm"
              aria-label="Close"
              @click="tryClose"
            />
          </div>
        </template>

        <div v-if="draft" class="space-y-6">
          <!-- PR84a — AI Rewrite -->
          <div class="rounded-xl border border-primary/30 bg-primary/5">
            <button
              type="button"
              class="w-full flex items-center justify-between gap-3 p-3 text-left"
              @click="rewriteOpen = !rewriteOpen"
            >
              <div class="flex items-center gap-2">
                <UIcon name="i-lucide-sparkles" class="size-4 text-primary" />
                <span class="text-sm font-semibold text-primary">Rewrite from description</span>
              </div>
              <UIcon
                :name="rewriteOpen ? 'i-lucide-chevron-up' : 'i-lucide-chevron-down'"
                class="size-4 text-muted"
              />
            </button>
            <div v-if="rewriteOpen" class="p-3 pt-0 space-y-3">
              <p class="text-xs text-muted">
                Paste a new description to regenerate expertise, mental models,
                frameworks, and communication. Identity (name, role, department)
                and behavioural DNA are preserved.
              </p>
              <UTextarea
                v-model="rewriteDescription"
                :rows="3"
                placeholder="A senior strategist who decides fast and demands evidence. 10 years at McKinsey covering CPG..."
                class="w-full"
              />
              <div class="flex items-center justify-between">
                <span class="text-xs text-muted">
                  {{ rewriteDescription.trim().length }} char{{ rewriteDescription.trim().length === 1 ? '' : 's' }}
                  · {{ rewriteDescription.trim().length >= 20 ? 'ready' : `${20 - rewriteDescription.trim().length} more needed` }}
                </span>
                <UButton
                  label="Rewrite"
                  icon="i-lucide-wand"
                  color="primary"
                  size="sm"
                  :loading="rewriting"
                  :disabled="rewriteDescription.trim().length < 20"
                  @click="rewriteFromDescription"
                />
              </div>
            </div>
          </div>

          <p class="rounded-lg border border-yellow-500/30 bg-yellow-500/5 p-3 text-xs text-muted">
            <UIcon name="i-lucide-info" class="size-3.5 inline" />
            Behavioural DNA (DISC, Enneagram, MBTI, Big Five) is locked here
            on purpose — changing it silently invalidates the agent's
            identity model. Edit it directly in the YAML file when truly
            needed.
          </p>

          <section class="space-y-3">
            <h3 class="text-xs font-semibold uppercase tracking-wider text-muted">
              Identity
            </h3>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
              <UFormField label="Name">
                <UInput v-model="draft.name" class="w-full" @update:model-value="markDirty" />
              </UFormField>
              <UFormField label="Role">
                <UInput v-model="draft.role" class="w-full" @update:model-value="markDirty" />
              </UFormField>
              <UFormField label="Tier">
                <USelect
                  v-model="draft.tier"
                  :items="tierOptions"
                  class="w-full"
                  @update:model-value="markDirty"
                />
              </UFormField>
            </div>
          </section>

          <section class="space-y-3">
            <div class="flex items-center justify-between">
              <h3 class="text-xs font-semibold uppercase tracking-wider text-muted">
                Mental models
              </h3>
              <UButton
                label="Suggest with AI"
                icon="i-lucide-sparkles"
                size="xs"
                color="primary"
                variant="soft"
                :loading="suggestingField === 'mental_models_primary'"
                :disabled="suggestingField !== null"
                @click="suggest('mental_models_primary')"
              />
            </div>
            <UFormField label="Primary" help="comma-separated">
              <UInput
                :model-value="listToCsv(draft.mental_models.primary)"
                class="w-full"
                @update:model-value="(v: string) => { if (draft) { draft.mental_models.primary = csvToList(v); markDirty() } }"
              />
            </UFormField>
            <UFormField label="Secondary" help="comma-separated">
              <UInput
                :model-value="listToCsv(draft.mental_models.secondary)"
                class="w-full"
                @update:model-value="(v: string) => { if (draft) { draft.mental_models.secondary = csvToList(v); markDirty() } }"
              />
            </UFormField>
          </section>

          <section class="space-y-3">
            <h3 class="text-xs font-semibold uppercase tracking-wider text-muted">
              Expertise
            </h3>
            <UFormField label="Domains" help="comma-separated">
              <template #hint>
                <UButton
                  label="Suggest with AI"
                  icon="i-lucide-sparkles"
                  size="xs"
                  color="primary"
                  variant="soft"
                  :loading="suggestingField === 'expertise_domains'"
                  :disabled="suggestingField !== null"
                  @click="suggest('expertise_domains')"
                />
              </template>
              <UInput
                :model-value="listToCsv(draft.expertise_domains)"
                class="w-full"
                @update:model-value="(v: string) => { if (draft) { draft.expertise_domains = csvToList(v); markDirty() } }"
              />
            </UFormField>
            <UFormField label="Frameworks" help="comma-separated">
              <template #hint>
                <UButton
                  label="Suggest with AI"
                  icon="i-lucide-sparkles"
                  size="xs"
                  color="primary"
                  variant="soft"
                  :loading="suggestingField === 'frameworks'"
                  :disabled="suggestingField !== null"
                  @click="suggest('frameworks')"
                />
              </template>
              <UInput
                :model-value="listToCsv(draft.frameworks)"
                class="w-full"
                @update:model-value="(v: string) => { if (draft) { draft.frameworks = csvToList(v); markDirty() } }"
              />
            </UFormField>
            <div class="grid grid-cols-2 gap-3">
              <UFormField label="Depth">
                <USelect
                  v-model="draft.expertise_depth"
                  :items="depthOptions"
                  class="w-full"
                  @update:model-value="markDirty"
                />
              </UFormField>
              <UFormField label="Years (equivalent)">
                <UInput
                  v-model.number="draft.expertise_years"
                  type="number"
                  :min="0"
                  :max="60"
                  class="w-full"
                  @update:model-value="markDirty"
                />
              </UFormField>
            </div>
          </section>

          <section class="space-y-3">
            <h3 class="text-xs font-semibold uppercase tracking-wider text-muted">
              Communication
            </h3>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
              <UFormField label="Tone">
                <template #hint>
                  <UButton
                    label="Generate"
                    icon="i-lucide-sparkles"
                    size="xs"
                    color="primary"
                    variant="soft"
                    :loading="suggestingString === 'tone'"
                    :disabled="suggestingString !== null"
                    @click="suggestString('tone')"
                  />
                </template>
                <UInput v-model="draft.communication.tone" class="w-full" @update:model-value="markDirty" />
              </UFormField>
              <UFormField label="Vocabulary level">
                <USelect
                  v-model="draft.communication.vocabulary_level"
                  :items="vocabOptions"
                  class="w-full"
                  @update:model-value="markDirty"
                />
              </UFormField>
              <UFormField label="Preferred format">
                <template #hint>
                  <UButton
                    label="Generate"
                    icon="i-lucide-sparkles"
                    size="xs"
                    color="primary"
                    variant="soft"
                    :loading="suggestingString === 'preferred_format'"
                    :disabled="suggestingString !== null"
                    @click="suggestString('preferred_format')"
                  />
                </template>
                <UInput v-model="draft.communication.preferred_format" class="w-full" @update:model-value="markDirty" />
              </UFormField>
              <UFormField label="Language">
                <UInput
                  v-model="draft.communication.language"
                  placeholder="en, pt"
                  class="w-full"
                  @update:model-value="markDirty"
                />
              </UFormField>
            </div>
            <UFormField label="Avoid (phrases)" help="comma-separated">
              <template #hint>
                <UButton
                  label="Suggest with AI"
                  icon="i-lucide-sparkles"
                  size="xs"
                  color="primary"
                  variant="soft"
                  :loading="suggestingField === 'communication_avoid'"
                  :disabled="suggestingField !== null"
                  @click="suggest('communication_avoid')"
                />
              </template>
              <UInput
                :model-value="listToCsv(draft.communication.avoid)"
                class="w-full"
                @update:model-value="(v: string) => { if (draft) { draft.communication.avoid = csvToList(v); markDirty() } }"
              />
            </UFormField>
          </section>

          <section class="space-y-3">
            <h3 class="text-xs font-semibold uppercase tracking-wider text-muted">
              Bio (Markdown)
            </h3>
            <MarkdownEditor
              :model-value="draft.bio_md"
              :rows="10"
              placeholder="A free-text Markdown bio for this agent — context, voice samples, internal notes."
              @update:model-value="(v: string) => { if (draft) { draft.bio_md = v; markDirty() } }"
            />
          </section>

          <section class="space-y-3">
            <h3 class="text-xs font-semibold uppercase tracking-wider text-muted">
              Linked personas
              <span class="ml-2 text-[10px] font-normal text-muted normal-case tracking-normal">
                — agent draws from these persona profiles
              </span>
            </h3>
            <USelectMenu
              v-model="draft.linked_personas"
              :items="personaOptions"
              value-key="value"
              multiple
              placeholder="Select personas to link"
              class="w-full"
              @update:model-value="markDirty"
            />
            <p class="text-xs text-muted">
              {{ draft.linked_personas.length }} linked.
              Personas come from the Persona library (auto-synced with your
              Obsidian vault).
            </p>
          </section>
        </div>

        <template #footer>
          <div class="flex items-center justify-between gap-2">
            <span v-if="dirty" class="text-xs text-yellow-400">
              <UIcon name="i-lucide-circle-dot" class="size-3 inline" />
              Unsaved changes
            </span>
            <span v-else class="text-xs text-muted">No changes</span>
            <div class="flex gap-2">
              <UButton
                label="Cancel"
                variant="ghost"
                :disabled="saving"
                @click="tryClose"
              />
              <UButton
                label="Save"
                icon="i-lucide-check"
                :loading="saving"
                :disabled="!dirty"
                @click="save"
              />
            </div>
          </div>
        </template>
      </UCard>
    </template>
  </USlideover>
</template>
