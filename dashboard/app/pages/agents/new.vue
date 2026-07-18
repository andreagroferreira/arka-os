<script setup lang="ts">
// PR82a v3.0.0 — /agents/new manual create page.
//
// Single-page form (sections, no multi-step) that mirrors the safe-to-edit
// fields from AgentEditDrawer but in "create" mode:
//   - Identity (name, role, department, tier)
//   - Behavioural DNA (DISC + Enneagram + MBTI + Big Five, with sensible
//     defaults — operator can edit)
//   - Knowledge (mental models, expertise domains, frameworks)
//   - Communication (tone, vocab, format, language, avoid)
//
// AI-assist (PR81) is wired on the three list fields so a draft agent
// can be filled with one click. On Save → POST /api/agents → navigate
// to /agents/{slug}.

import type { Persona } from '~/types'

const { fetchApi, apiBase } = useApi()
const toast = useToast()

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
  department: string
  tier: number
  disc_primary: string
  disc_secondary: string
  enneagram_type: number
  enneagram_wing: number
  mbti: string
  big_five: {
    openness: number
    conscientiousness: number
    extraversion: number
    agreeableness: number
    neuroticism: number
  }
  mental_models_primary: string[]
  expertise_domains: string[]
  expertise_depth: string
  expertise_years: number
  frameworks: string[]
  comm_tone: string
  comm_vocab: string
  comm_format: string
  comm_language: string
  comm_avoid: string[]
  linked_personas: string[]
}

const draft = ref<AgentDraft>({
  name: '',
  role: '',
  department: 'dev',
  tier: 2,
  disc_primary: 'I',
  disc_secondary: 'S',
  enneagram_type: 5,
  enneagram_wing: 4,
  mbti: 'INTJ',
  big_five: {
    openness: 70,
    conscientiousness: 70,
    extraversion: 50,
    agreeableness: 60,
    neuroticism: 30
  },
  mental_models_primary: [],
  expertise_domains: [],
  expertise_depth: 'advanced',
  expertise_years: 5,
  frameworks: [],
  comm_tone: '',
  comm_vocab: 'specialist',
  comm_format: '',
  comm_language: 'en',
  comm_avoid: [],
  linked_personas: []
})

const saving = ref(false)

// PR83c v3.5.0 — single-string suggester.
type StringField = 'tone' | 'preferred_format'
const suggestingString = ref<StringField | null>(null)

async function suggestString(field: StringField) {
  if (!draft.value.name.trim() || !draft.value.role.trim()) {
    toast.add({
      title: 'Add a name and role first',
      color: 'warning'
    })
    return
  }
  const current = field === 'tone' ? draft.value.comm_tone : draft.value.comm_format
  suggestingString.value = field
  try {
    const res = await $fetch<{ value: string, provider_name: string, error?: string }>(
      `${apiBase}/api/agents/suggest-string`,
      {
        method: 'POST',
        body: {
          field,
          context: {
            name: draft.value.name,
            role: draft.value.role,
            department: draft.value.department,
            current
          }
        }
      }
    )
    if (res.error) throw new Error(res.error)
    if (field === 'tone') draft.value.comm_tone = res.value
    else draft.value.comm_format = res.value
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

// PR82b v3.1.0 — AI draft from description.
const description = ref('')
const drafting = ref(false)

// Shape of the AI-generated draft returned by POST /api/agents/draft.
// Values are unknown at the boundary — applyDraft validates each one
// (Array.isArray / typeof) before assigning into the typed draft.
interface GeneratedDraft {
  behavioral_dna?: {
    disc?: { primary?: unknown, secondary?: unknown }
    enneagram?: { type?: unknown, wing?: unknown }
    mbti?: unknown
    big_five?: {
      openness?: unknown
      conscientiousness?: unknown
      extraversion?: unknown
      agreeableness?: unknown
      neuroticism?: unknown
    }
  }
  expertise?: {
    domains?: unknown
    frameworks?: unknown
    depth?: unknown
    years_equivalent?: unknown
  }
  mental_models?: { primary?: unknown }
  communication?: {
    tone?: unknown
    vocabulary_level?: unknown
    preferred_format?: unknown
    language?: unknown
    avoid?: unknown
  }
}

async function draftFromDescription() {
  const desc = description.value.trim()
  if (desc.length < 20) {
    toast.add({
      title: 'Add more detail',
      description: 'Describe the agent in at least a sentence or two.',
      color: 'warning'
    })
    return
  }
  drafting.value = true
  try {
    const res = await $fetch<{
      draft: GeneratedDraft
      provider_name: string
      error?: string
    }>(`${apiBase}/api/agents/draft`, {
      method: 'POST',
      body: {
        description: desc,
        name: draft.value.name,
        role: draft.value.role,
        department: draft.value.department,
        tier: draft.value.tier
      }
    })
    if (res.error) throw new Error(res.error)
    applyDraft(res.draft)
    toast.add({
      title: 'Draft generated',
      description: `via ${res.provider_name} — review and edit before creating.`,
      color: 'success',
      icon: 'i-lucide-sparkles'
    })
  } catch (err) {
    toast.add({
      title: 'Draft failed',
      description: err instanceof Error ? err.message : 'unknown error',
      color: 'error'
    })
  } finally {
    drafting.value = false
  }
}

function applyDraft(d: GeneratedDraft) {
  const dna = d?.behavioral_dna ?? {}
  const disc = dna.disc ?? {}
  const enn = dna.enneagram ?? {}
  const bf = dna.big_five ?? {}
  if (disc.primary) draft.value.disc_primary = String(disc.primary).toUpperCase()
  if (disc.secondary) draft.value.disc_secondary = String(disc.secondary).toUpperCase()
  if (enn.type) draft.value.enneagram_type = Number(enn.type)
  if (enn.wing) draft.value.enneagram_wing = Number(enn.wing)
  if (dna.mbti) draft.value.mbti = String(dna.mbti).toUpperCase()
  for (const key of ['openness', 'conscientiousness', 'extraversion', 'agreeableness', 'neuroticism'] as const) {
    if (typeof bf[key] === 'number') draft.value.big_five[key] = bf[key]
  }
  const exp = d?.expertise ?? {}
  if (Array.isArray(exp.domains)) draft.value.expertise_domains = exp.domains.map(String)
  if (Array.isArray(exp.frameworks)) draft.value.frameworks = exp.frameworks.map(String)
  if (exp.depth) draft.value.expertise_depth = String(exp.depth)
  if (typeof exp.years_equivalent === 'number') draft.value.expertise_years = exp.years_equivalent
  const mm = d?.mental_models ?? {}
  if (Array.isArray(mm.primary)) draft.value.mental_models_primary = mm.primary.map(String)
  const comm = d?.communication ?? {}
  if (comm.tone) draft.value.comm_tone = String(comm.tone)
  if (comm.vocabulary_level) draft.value.comm_vocab = String(comm.vocabulary_level)
  if (comm.preferred_format) draft.value.comm_format = String(comm.preferred_format)
  if (comm.language) draft.value.comm_language = String(comm.language)
  if (Array.isArray(comm.avoid)) draft.value.comm_avoid = comm.avoid.map(String)
}

const departmentOptions = [
  'dev', 'marketing', 'brand', 'finance', 'strategy', 'ecom', 'kb', 'ops',
  'pm', 'saas', 'landing', 'content', 'community', 'sales', 'leadership', 'org'
].map(d => ({ label: d, value: d }))

const tierOptions = [
  { label: 'Tier 1 — Squad Lead', value: 1 },
  { label: 'Tier 2 — Specialist', value: 2 },
  { label: 'Tier 3 — Support', value: 3 }
]
const discOptions = ['D', 'I', 'S', 'C'].map(v => ({ label: v, value: v }))
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
const mbtiOptions = [
  'INTJ', 'INTP', 'ENTJ', 'ENTP',
  'INFJ', 'INFP', 'ENFJ', 'ENFP',
  'ISTJ', 'ISFJ', 'ESTJ', 'ESFJ',
  'ISTP', 'ISFP', 'ESTP', 'ESFP'
].map(t => ({ label: t, value: t }))

function listToCsv(list: string[]): string {
  return list.join(', ')
}
function csvToList(value: string): string[] {
  return value.split(',').map(s => s.trim()).filter(Boolean)
}

// PR81 suggest wiring — three list fields.
// PR82c v3.2.0 — extended with 'communication_avoid'.
type SuggestField = 'mental_models' | 'frameworks' | 'expertise_domains' | 'communication_avoid'
const suggestingField = ref<SuggestField | null>(null)

async function suggest(field: SuggestField) {
  const current
    = field === 'mental_models'
      ? draft.value.mental_models_primary
      : field === 'frameworks'
        ? draft.value.frameworks
        : field === 'expertise_domains'
          ? draft.value.expertise_domains
          : draft.value.comm_avoid
  if (!draft.value.name.trim() || !draft.value.role.trim()) {
    toast.add({
      title: 'Add a name and role first',
      description: 'AI needs the basics to make useful suggestions.',
      color: 'warning'
    })
    return
  }
  suggestingField.value = field
  try {
    const res = await $fetch<{
      suggestions: string[]
      provider_name: string
      error?: string
    }>(`${apiBase}/api/agents/suggest`, {
      method: 'POST',
      body: {
        field,
        count: 5,
        context: {
          name: draft.value.name,
          role: draft.value.role,
          department: draft.value.department,
          current
        }
      }
    })
    if (res.error) throw new Error(res.error)
    const additions = (res.suggestions ?? []).filter(
      s => !current.some(c => c.toLowerCase() === s.toLowerCase())
    )
    if (additions.length === 0) {
      toast.add({ title: 'No new suggestions', color: 'info' })
      return
    }
    const merged = [...current, ...additions]
    if (field === 'mental_models') draft.value.mental_models_primary = merged
    else if (field === 'frameworks') draft.value.frameworks = merged
    else if (field === 'expertise_domains') draft.value.expertise_domains = merged
    else draft.value.comm_avoid = merged
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

const canSave = computed(() => {
  return (
    draft.value.name.trim().length > 0
    && draft.value.role.trim().length > 0
    && draft.value.department.trim().length > 0
    && draft.value.disc_primary !== draft.value.disc_secondary
  )
})

async function save() {
  if (!canSave.value) return
  saving.value = true
  try {
    const body = {
      name: draft.value.name.trim(),
      role: draft.value.role.trim(),
      department: draft.value.department,
      tier: draft.value.tier,
      behavioral_dna: {
        disc: {
          primary: draft.value.disc_primary,
          secondary: draft.value.disc_secondary
        },
        enneagram: {
          type: draft.value.enneagram_type,
          wing: draft.value.enneagram_wing
        },
        mbti: draft.value.mbti,
        big_five: draft.value.big_five
      },
      mental_models: { primary: draft.value.mental_models_primary, secondary: [] },
      expertise: {
        domains: draft.value.expertise_domains,
        frameworks: draft.value.frameworks,
        depth: draft.value.expertise_depth,
        years_equivalent: draft.value.expertise_years
      },
      communication: {
        tone: draft.value.comm_tone,
        vocabulary_level: draft.value.comm_vocab,
        preferred_format: draft.value.comm_format,
        language: draft.value.comm_language,
        avoid: draft.value.comm_avoid
      },
      linked_personas: draft.value.linked_personas
    }
    const res = await $fetch<{
      id: string
      created: boolean
      yaml_path?: string
      error?: string
    }>(`${apiBase}/api/agents`, { method: 'POST', body })
    if (res.error) throw new Error(res.error)
    toast.add({
      title: 'Agent created',
      description: res.yaml_path?.split('/').slice(-3).join('/') ?? res.id,
      color: 'success'
    })
    navigateTo(`/agents/${res.id}`)
  } catch (err) {
    toast.add({
      title: 'Create failed',
      description: err instanceof Error ? err.message : 'unknown error',
      color: 'error'
    })
  } finally {
    saving.value = false
  }
}

const bigFiveLabels: Record<string, string> = {
  openness: 'Openness',
  conscientiousness: 'Conscientiousness',
  extraversion: 'Extraversion',
  agreeableness: 'Agreeableness',
  neuroticism: 'Neuroticism'
}
const bigFiveKeys = ['openness', 'conscientiousness', 'extraversion', 'agreeableness', 'neuroticism'] as const
</script>

<template>
  <UDashboardPanel id="agents-new">
    <template #header>
      <UDashboardNavbar title="New Agent">
        <template #leading>
          <UButton
            icon="i-lucide-arrow-left"
            variant="ghost"
            size="sm"
            aria-label="Back to agents"
            to="/agents"
          />
        </template>
        <template #trailing>
          <UBadge
            label="AI-assisted"
            icon="i-lucide-sparkles"
            color="primary"
            variant="soft"
            size="sm"
          />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="max-w-4xl mx-auto py-2 space-y-6">
        <section class="rounded-xl border border-primary/30 bg-primary/5 p-4 space-y-3">
          <div class="flex items-center justify-between gap-3">
            <div>
              <h3 class="text-sm font-semibold uppercase tracking-wide text-primary flex items-center gap-2">
                <UIcon name="i-lucide-sparkles" class="size-4" />
                Draft with AI
              </h3>
              <p class="text-xs text-muted mt-0.5">
                Describe the agent in plain text — the LLM fills the whole form below.
                You can still edit everything before saving.
              </p>
            </div>
            <UButton
              label="Generate draft"
              icon="i-lucide-wand"
              color="primary"
              :loading="drafting"
              :disabled="description.trim().length < 20"
              @click="draftFromDescription"
            />
          </div>
          <UTextarea
            v-model="description"
            placeholder="A senior strategist who decides fast, demands evidence, and is allergic to fluff. Spent 10 years at McKinsey covering CPG..."
            :rows="3"
            class="w-full"
          />
          <p class="text-xs text-muted">
            Tip: fill in <span class="font-mono">Name</span> /
            <span class="font-mono">Role</span> /
            <span class="font-mono">Department</span> below first for more precise output.
          </p>
        </section>

        <section class="space-y-3">
          <h3 class="text-sm font-semibold uppercase tracking-wide text-muted">
            Identity
          </h3>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
            <UFormField label="Name" required>
              <UInput v-model="draft.name" class="w-full" placeholder="Lucas" />
            </UFormField>
            <UFormField label="Role" required>
              <UInput v-model="draft.role" class="w-full" placeholder="Market & Competitive Intelligence Analyst" />
            </UFormField>
            <UFormField label="Department" required>
              <USelect v-model="draft.department" :items="departmentOptions" class="w-full" />
            </UFormField>
            <UFormField label="Tier">
              <USelect v-model="draft.tier" :items="tierOptions" class="w-full" />
            </UFormField>
          </div>
        </section>

        <section class="space-y-3">
          <h3 class="text-sm font-semibold uppercase tracking-wide text-muted">
            Behavioural DNA
          </h3>
          <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
            <UFormField label="DISC primary">
              <USelect v-model="draft.disc_primary" :items="discOptions" class="w-full" />
            </UFormField>
            <UFormField label="DISC secondary">
              <USelect v-model="draft.disc_secondary" :items="discOptions" class="w-full" />
            </UFormField>
            <UFormField label="Enneagram type">
              <UInput
                v-model.number="draft.enneagram_type"
                type="number"
                :min="1"
                :max="9"
                class="w-full"
              />
            </UFormField>
            <UFormField label="Enneagram wing">
              <UInput
                v-model.number="draft.enneagram_wing"
                type="number"
                :min="1"
                :max="9"
                class="w-full"
              />
            </UFormField>
            <UFormField label="MBTI">
              <USelect v-model="draft.mbti" :items="mbtiOptions" class="w-full" />
            </UFormField>
          </div>
          <p v-if="draft.disc_primary === draft.disc_secondary" class="text-xs text-error">
            DISC primary and secondary must differ.
          </p>
          <div class="space-y-2">
            <p class="text-sm font-semibold text-muted">
              Big Five (OCEAN)
            </p>
            <div v-for="key in bigFiveKeys" :key="key" class="flex items-center gap-3">
              <span class="w-40 text-sm text-muted">{{ bigFiveLabels[key] }}</span>
              <UInput
                v-model.number="draft.big_five[key]"
                type="number"
                :min="0"
                :max="100"
                class="w-20"
              />
              <div class="flex-1 h-2 rounded-full bg-muted/20">
                <div class="h-2 rounded-full bg-primary" :style="{ width: `${draft.big_five[key]}%` }" />
              </div>
            </div>
          </div>
        </section>

        <section class="space-y-3">
          <h3 class="text-sm font-semibold uppercase tracking-wide text-muted">
            Knowledge
          </h3>
          <UFormField label="Mental models (primary)" help="comma-separated">
            <template #hint>
              <UButton
                label="Suggest with AI"
                icon="i-lucide-sparkles"
                size="xs"
                color="primary"
                variant="soft"
                :loading="suggestingField === 'mental_models'"
                :disabled="suggestingField !== null"
                @click="suggest('mental_models')"
              />
            </template>
            <UInput
              :model-value="listToCsv(draft.mental_models_primary)"
              class="w-full"
              @update:model-value="(v: string) => { draft.mental_models_primary = csvToList(v) }"
            />
          </UFormField>
          <UFormField label="Expertise domains" help="comma-separated">
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
              @update:model-value="(v: string) => { draft.expertise_domains = csvToList(v) }"
            />
          </UFormField>
          <div class="grid grid-cols-2 gap-3">
            <UFormField label="Depth">
              <USelect v-model="draft.expertise_depth" :items="depthOptions" class="w-full" />
            </UFormField>
            <UFormField label="Years (equivalent)">
              <UInput
                v-model.number="draft.expertise_years"
                type="number"
                :min="0"
                :max="60"
                class="w-full"
              />
            </UFormField>
          </div>
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
              @update:model-value="(v: string) => { draft.frameworks = csvToList(v) }"
            />
          </UFormField>
        </section>

        <section class="space-y-3">
          <h3 class="text-sm font-semibold uppercase tracking-wide text-muted">
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
              <UInput v-model="draft.comm_tone" class="w-full" placeholder="Analytical, calm" />
            </UFormField>
            <UFormField label="Vocabulary level">
              <USelect v-model="draft.comm_vocab" :items="vocabOptions" class="w-full" />
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
              <UInput v-model="draft.comm_format" class="w-full" placeholder="Briefs, tables, charts" />
            </UFormField>
            <UFormField label="Language">
              <UInput v-model="draft.comm_language" class="w-full" placeholder="en" />
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
              :model-value="listToCsv(draft.comm_avoid)"
              class="w-full"
              @update:model-value="(v: string) => { draft.comm_avoid = csvToList(v) }"
            />
          </UFormField>
        </section>

        <section class="space-y-3">
          <h3 class="text-sm font-semibold uppercase tracking-wide text-muted">
            Linked personas
          </h3>
          <USelectMenu
            v-model="draft.linked_personas"
            :items="personaOptions"
            value-key="value"
            multiple
            placeholder="Select personas to link"
            class="w-full"
          />
        </section>

        <div class="flex items-center justify-end gap-2 pt-4 border-t border-default">
          <UButton
            label="Cancel"
            variant="ghost"
            :disabled="saving"
            to="/agents"
          />
          <UButton
            label="Create agent"
            icon="i-lucide-check"
            :loading="saving"
            :disabled="!canSave"
            @click="save"
          />
        </div>
      </div>
    </template>
  </UDashboardPanel>
</template>
