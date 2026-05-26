<script setup lang="ts">
// PR78 v2.96.0 — Persona detail page.
//
// Mirror of agents/[id].vue: gradient hero + initials avatar + stats
// row + UTabs (DNA / Communication / Knowledge / Linked Agents).
// Edit drawer reused from PR74 (PersonaDetailDrawer's edit form)
// but slimmed: the page itself is the read view; the drawer only
// flips into edit mode.
//
// Replaces the previous drawer-everywhere UX with the page-per-record
// pattern that already shipped for /agents.

import type { Persona } from '~/types'

interface DetailResponse extends Persona {
  _source_store?: 'obsidian' | 'json'
  _obsidian_path?: string
}

const route = useRoute()
const personaId = route.params.id as string

const { fetchApi, apiBase } = useApi()
const toast = useToast()
const confirmDialog = useConfirmDialog()

const { data: detail, status, error, refresh } = fetchApi<DetailResponse>(`/api/personas/${personaId}`)

const { data: usageData } = fetchApi<{
  by_persona: Record<string, { agent_count: number, agent_ids: string[] }>
}>('/api/personas/usage')

const linkedAgentIds = computed<string[]>(() =>
  usageData.value?.by_persona?.[personaId]?.agent_ids ?? [],
)
const linkedAgentCount = computed(() => linkedAgentIds.value.length)

// ─── Hero helpers (matching personas/index.vue + agents/[id].vue) ───────

function heroInitials(name: string | undefined): string {
  if (!name) return '·'
  const parts = name.trim().split(/\s+/)
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

function mbtiGradientClass(mbti: string | undefined): string {
  if (!mbti) return 'bg-gradient-to-br from-muted/20 to-muted/5'
  const code = mbti.toUpperCase()
  if (['INTJ', 'INTP', 'ENTJ', 'ENTP'].includes(code))
    return 'bg-gradient-to-br from-blue-500/30 to-indigo-600/10'
  if (['INFJ', 'INFP', 'ENFJ', 'ENFP'].includes(code))
    return 'bg-gradient-to-br from-emerald-500/30 to-teal-600/10'
  if (['ISTJ', 'ISFJ', 'ESTJ', 'ESFJ'].includes(code))
    return 'bg-gradient-to-br from-amber-500/30 to-orange-600/10'
  if (['ISTP', 'ISFP', 'ESTP', 'ESFP'].includes(code))
    return 'bg-gradient-to-br from-rose-500/30 to-pink-600/10'
  return 'bg-gradient-to-br from-primary/20 to-primary/5'
}

const mbtiDescriptions: Record<string, string> = {
  INTJ: 'Ni-Te-Fi-Se — The Architect',
  INTP: 'Ti-Ne-Si-Fe — The Logician',
  ENTJ: 'Te-Ni-Se-Fi — The Commander',
  ENTP: 'Ne-Ti-Fe-Si — The Debater',
  INFJ: 'Ni-Fe-Ti-Se — The Advocate',
  INFP: 'Fi-Ne-Si-Te — The Mediator',
  ENFJ: 'Fe-Ni-Se-Ti — The Protagonist',
  ENFP: 'Ne-Fi-Te-Si — The Campaigner',
  ISTJ: 'Si-Te-Fi-Ne — The Inspector',
  ISFJ: 'Si-Fe-Ti-Ne — The Defender',
  ESTJ: 'Te-Si-Ne-Fi — The Executive',
  ESFJ: 'Fe-Si-Ne-Ti — The Consul',
  ISTP: 'Ti-Se-Ni-Fe — The Virtuoso',
  ISFP: 'Fi-Se-Ni-Te — The Adventurer',
  ESTP: 'Se-Ti-Fe-Ni — The Entrepreneur',
  ESFP: 'Se-Fi-Te-Ni — The Entertainer',
}

const discLetters = ['D', 'I', 'S', 'C'] as const
const bigFiveKeys = ['openness', 'conscientiousness', 'extraversion', 'agreeableness', 'neuroticism'] as const
const bigFiveLabels: Record<string, string> = {
  openness: 'Openness',
  conscientiousness: 'Conscientiousness',
  extraversion: 'Extraversion',
  agreeableness: 'Agreeableness',
  neuroticism: 'Neuroticism',
}

function discBarValue(letter: string): number {
  if (!detail.value?.disc) return 20
  if (detail.value.disc.primary === letter) return 90
  if (detail.value.disc.secondary === letter) return 70
  return 20
}

function discBarColor(letter: string): string {
  const colors: Record<string, string> = {
    D: 'bg-red-500', I: 'bg-yellow-500', S: 'bg-green-500', C: 'bg-blue-500',
  }
  return colors[letter] ?? 'bg-primary'
}

function bigFiveBarColor(value: number): string {
  if (value >= 75) return 'bg-primary'
  if (value >= 50) return 'bg-blue-400'
  if (value >= 30) return 'bg-yellow-500'
  return 'bg-neutral-500'
}

// ─── Tabs ───────────────────────────────────────────────────────────────

const tabs = [
  { label: 'DNA',           value: 'dna',           icon: 'i-lucide-dna' },
  { label: 'Communication', value: 'communication', icon: 'i-lucide-message-square' },
  { label: 'Knowledge',     value: 'knowledge',     icon: 'i-lucide-brain' },
  { label: 'Linked Agents', value: 'agents',        icon: 'i-lucide-users' },
]

// ─── Edit drawer state ─────────────────────────────────────────────────

const editOpen = ref(false)
const draft = ref<Persona | null>(null)
const saving = ref(false)
const dirty = ref(false)

function startEdit() {
  if (!detail.value) return
  draft.value = JSON.parse(JSON.stringify(detail.value)) as Persona
  dirty.value = false
  editOpen.value = true
}

function markDirty() { dirty.value = true }

async function tryCloseEdit() {
  if (dirty.value && !saving.value) {
    const ok = await confirmDialog({
      title: 'Discard unsaved edits?',
      description: 'Any changes you made will be lost.',
      confirmLabel: 'Discard',
      cancelLabel: 'Keep editing',
      variant: 'danger',
    })
    if (!ok) return
  }
  editOpen.value = false
  draft.value = null
}

async function saveEdit() {
  if (!draft.value) return
  saving.value = true
  try {
    const res = await $fetch<{
      id: string
      updated: boolean
      json_written: boolean
      obsidian_path: string | null
      error?: string
    }>(`${apiBase}/api/personas/${personaId}`, {
      method: 'PUT',
      body: draft.value,
    })
    if (res.error) throw new Error(res.error)
    toast.add({
      title: 'Persona saved',
      description: res.obsidian_path
        ? `Wrote ${res.obsidian_path.split('/').slice(-2).join('/')}`
        : 'Saved to JSON store',
      color: 'success',
    })
    await refresh()
    editOpen.value = false
    draft.value = null
    dirty.value = false
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

async function deletePersona() {
  if (!detail.value) return
  const ok = await confirmDialog({
    title: `Delete persona "${detail.value.name}"?`,
    description:
      'Removes it from the JSON store. The Obsidian file (if any) is '
      + 'left in place — delete manually from Obsidian if you want it gone.',
    confirmLabel: 'Delete persona',
    variant: 'danger',
  })
  if (!ok) return
  try {
    await $fetch(`${apiBase}/api/personas/${personaId}`, { method: 'DELETE' })
    toast.add({
      title: 'Persona deleted',
      description: detail.value.name,
      color: 'success',
    })
    await navigateTo('/personas')
  } catch (err) {
    toast.add({
      title: 'Delete failed',
      description: err instanceof Error ? err.message : 'unknown error',
      color: 'error',
    })
  }
}

function listToCsv(list: string[] | undefined): string {
  return (list ?? []).join(', ')
}

function csvToList(value: string): string[] {
  return value.split(',').map((s) => s.trim()).filter(Boolean)
}

// PR81 v2.99.0 — AI list-field suggester for personas.
// PR82c v3.2.0 — extended with 'communication_avoid' and 'key_quotes'.
type SuggestField = 'mental_models' | 'frameworks' | 'expertise_domains' | 'communication_avoid' | 'key_quotes'
const suggestingField = ref<SuggestField | null>(null)

// PR86a v3.15.0 — favorites.
const favs = useFavorites()
await favs.load()

// PR86d v3.18.0 — render Markdown bio.
import { marked } from 'marked'
function markedHtml(src: string): string {
  if (!src?.trim()) return ''
  try {
    return marked.parse(src, { breaks: true, gfm: true }) as string
  } catch {
    return ''
  }
}

// PR85a v3.11.0 — Clone to Agent dialog.
const cloneOpen = ref(false)
function onCloned(agentId: string) {
  navigateTo(`/agents/${agentId}`)
}

// PR84c v3.9.0 — Auto-fill empty lists in one go.
const autofilling = ref(false)

async function autofillEmpties() {
  if (!draft.value || !detail.value) return
  type ListKey = 'mental_models' | 'expertise_domains' | 'frameworks' | 'key_quotes' | 'communication_avoid'
  const targets: ListKey[] = []
  if ((draft.value.mental_models ?? []).length === 0) targets.push('mental_models')
  if ((draft.value.expertise_domains ?? []).length === 0) targets.push('expertise_domains')
  if ((draft.value.frameworks ?? []).length === 0) targets.push('frameworks')
  if ((draft.value.key_quotes ?? []).length === 0) targets.push('key_quotes')
  if ((draft.value.communication.avoid ?? []).length === 0) targets.push('communication_avoid')
  if (targets.length === 0) {
    toast.add({ title: 'No empty lists', description: 'Every list already has at least one item.', color: 'info' })
    return
  }
  autofilling.value = true
  const results = await Promise.allSettled(
    targets.map((field) =>
      $fetch<{ suggestions: string[], provider_name: string, error?: string }>(
        `${apiBase}/api/personas/suggest`,
        {
          method: 'POST',
          body: {
            field,
            count: 5,
            context: {
              name: detail.value!.name,
              title: detail.value!.title,
              current: [],
            },
          },
        },
      ),
    ),
  )
  let filledCount = 0
  let providerName = ''
  results.forEach((r, idx) => {
    if (r.status !== 'fulfilled' || r.value.error) return
    const items = r.value.suggestions ?? []
    if (items.length === 0) return
    const field = targets[idx]
    if (!draft.value) return
    if (field === 'communication_avoid') {
      draft.value.communication.avoid = items
    } else {
      ;(draft.value as any)[field] = items
    }
    filledCount += 1
    providerName = r.value.provider_name || providerName
  })
  autofilling.value = false
  if (filledCount > 0) {
    markDirty()
    toast.add({
      title: `Filled ${filledCount} list${filledCount === 1 ? '' : 's'}`,
      description: `via ${providerName}`,
      color: 'success',
      icon: 'i-lucide-sparkles',
    })
  } else {
    toast.add({ title: 'Nothing filled', description: 'LLM returned no items.', color: 'error' })
  }
}

// PR83c v3.5.0 — single-string suggester (tone for personas).
const suggestingString = ref<'tone' | null>(null)

async function suggestString(field: 'tone') {
  if (!draft.value || !detail.value) return
  const current = draft.value.communication.tone
  suggestingString.value = field
  try {
    const res = await $fetch<{ value: string, provider_name: string, error?: string }>(
      `${apiBase}/api/personas/suggest-string`,
      {
        method: 'POST',
        body: {
          field,
          context: {
            name: detail.value.name,
            title: detail.value.title,
            current,
          },
        },
      },
    )
    if (res.error) throw new Error(res.error)
    draft.value.communication.tone = res.value
    markDirty()
    toast.add({
      title: 'Generated',
      description: `via ${res.provider_name}`,
      color: 'success',
      icon: 'i-lucide-sparkles',
    })
  } catch (err) {
    toast.add({
      title: 'Generate failed',
      description: err instanceof Error ? err.message : 'unknown error',
      color: 'error',
    })
  } finally {
    suggestingString.value = null
  }
}

async function suggest(field: SuggestField) {
  if (!draft.value || !detail.value) return
  const current
    = field === 'communication_avoid'
      ? (draft.value.communication.avoid ?? [])
      : ((draft.value as any)[field] as string[] ?? [])
  suggestingField.value = field
  try {
    const res = await $fetch<{
      suggestions: string[]
      provider_name: string
      error?: string
    }>(`${apiBase}/api/personas/suggest`, {
      method: 'POST',
      body: {
        field,
        count: 5,
        context: {
          name: detail.value.name,
          title: detail.value.title,
          current,
        },
      },
    })
    if (res.error) throw new Error(res.error)
    const additions = (res.suggestions ?? []).filter(
      (s) => !current.some((c) => c.toLowerCase() === s.toLowerCase()),
    )
    if (additions.length === 0) {
      toast.add({
        title: 'No new suggestions',
        description: 'The model returned only items you already have.',
        color: 'info',
      })
      return
    }
    const merged = [...current, ...additions]
    if (field === 'communication_avoid') {
      draft.value.communication.avoid = merged
    } else {
      ;(draft.value as any)[field] = merged
    }
    markDirty()
    toast.add({
      title: `Added ${additions.length} suggestion${additions.length === 1 ? '' : 's'}`,
      description: `via ${res.provider_name}`,
      color: 'success',
      icon: 'i-lucide-sparkles',
    })
  } catch (err) {
    toast.add({
      title: 'Suggestion failed',
      description: err instanceof Error ? err.message : 'unknown error',
      color: 'error',
    })
  } finally {
    suggestingField.value = null
  }
}

const mbtiOptions = [
  'INTJ', 'INTP', 'ENTJ', 'ENTP',
  'INFJ', 'INFP', 'ENFJ', 'ENFP',
  'ISTJ', 'ISFJ', 'ESTJ', 'ESFJ',
  'ISTP', 'ISFP', 'ESTP', 'ESFP',
].map((t) => ({ label: t, value: t }))

const discOptions = [
  { label: 'D — Dominance', value: 'D' },
  { label: 'I — Influence', value: 'I' },
  { label: 'S — Steadiness', value: 'S' },
  { label: 'C — Conscientiousness', value: 'C' },
]

const vocabOptions = [
  { label: 'Lay (no jargon)', value: 'lay' },
  { label: 'Specialist (industry terms)', value: 'specialist' },
  { label: 'Expert (research-level)', value: 'expert' },
]
</script>

<template>
  <UDashboardPanel id="persona-detail">
    <template #header>
      <UDashboardNavbar :title="detail?.name ?? 'Persona'">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #trailing>
          <UButton
            label="Back"
            variant="ghost"
            icon="i-lucide-arrow-left"
            to="/personas"
            aria-label="Back to personas list"
          />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <DashboardState
        :status="status"
        :error="error"
        :empty="!detail"
        empty-title="Persona not found"
        empty-icon="i-lucide-user-x"
        loading-label="Loading persona"
        :on-retry="() => refresh()"
      >
        <div v-if="detail" class="space-y-6 pb-12">
          <!-- HERO -->
          <section
            class="relative overflow-hidden rounded-2xl border border-default p-6 md:p-8"
            :class="mbtiGradientClass(detail.mbti)"
          >
            <div class="flex items-start gap-5">
              <div class="shrink-0 size-20 rounded-2xl bg-default/80 border border-default flex items-center justify-center shadow-lg backdrop-blur-sm">
                <span class="text-2xl font-bold tracking-tight text-highlighted">
                  {{ heroInitials(detail.name) }}
                </span>
              </div>
              <div class="flex-1 min-w-0 space-y-2">
                <div class="flex items-start justify-between gap-3 flex-wrap">
                  <div class="min-w-0">
                    <h1 class="text-3xl md:text-4xl font-bold tracking-tight text-highlighted">
                      {{ detail.name }}
                    </h1>
                    <p v-if="detail.title" class="text-base md:text-lg text-muted mt-0.5">
                      {{ detail.title }}
                    </p>
                  </div>
                  <div class="flex items-center gap-2">
                    <UButton
                      icon="i-lucide-star"
                      :color="favs.isPersonaFavorite(detail.id) ? 'warning' : 'neutral'"
                      :variant="favs.isPersonaFavorite(detail.id) ? 'soft' : 'ghost'"
                      size="sm"
                      :aria-label="favs.isPersonaFavorite(detail.id) ? 'Unfavorite' : 'Favorite'"
                      @click="favs.toggle('personas', detail.id)"
                    />
                    <UButton
                      label="Clone to Agent"
                      icon="i-lucide-copy-plus"
                      variant="soft"
                      size="sm"
                      @click="cloneOpen = true"
                    />
                    <UButton label="Edit" icon="i-lucide-pencil" size="sm" @click="startEdit" />
                    <UButton
                      icon="i-lucide-trash-2"
                      color="error"
                      variant="ghost"
                      size="sm"
                      aria-label="Delete persona"
                      @click="deletePersona"
                    />
                  </div>
                </div>
                <p v-if="detail.tagline" class="text-sm italic text-muted">
                  "{{ detail.tagline }}"
                </p>
                <div class="flex flex-wrap items-center gap-2 pt-1">
                  <UBadge
                    v-if="detail._source_store === 'obsidian'"
                    label="From Obsidian"
                    icon="i-lucide-file-text"
                    color="primary"
                    variant="subtle"
                    size="sm"
                  />
                  <UBadge
                    v-else-if="detail._source_store === 'json'"
                    label="JSON store"
                    variant="outline"
                    size="sm"
                  />
                  <UBadge v-if="detail.mbti" :label="detail.mbti" variant="soft" size="sm" />
                  <UBadge
                    v-if="detail.disc?.primary"
                    :label="`DISC: ${detail.disc.primary}${detail.disc.secondary ? '/' + detail.disc.secondary : ''}`"
                    variant="subtle"
                    size="sm"
                  />
                </div>
                <p
                  v-if="detail._obsidian_path"
                  class="text-[10px] text-muted/70 font-mono truncate mt-2"
                  :title="detail._obsidian_path"
                >
                  {{ detail._obsidian_path.split('/').slice(-2).join('/') }}
                </p>
              </div>
            </div>
          </section>

          <!-- STATS -->
          <section class="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div class="rounded-xl border border-default p-4 bg-elevated/20">
              <p class="text-sm font-semibold text-muted uppercase tracking-wide mb-1">Linked agents</p>
              <p class="text-2xl font-bold">{{ linkedAgentCount }}</p>
            </div>
            <div class="rounded-xl border border-default p-4 bg-elevated/20">
              <p class="text-sm font-semibold text-muted uppercase tracking-wide mb-1">Mental models</p>
              <p class="text-2xl font-bold">{{ detail.mental_models?.length ?? 0 }}</p>
            </div>
            <div class="rounded-xl border border-default p-4 bg-elevated/20">
              <p class="text-sm font-semibold text-muted uppercase tracking-wide mb-1">Expertise domains</p>
              <p class="text-2xl font-bold">{{ detail.expertise_domains?.length ?? 0 }}</p>
            </div>
            <div class="rounded-xl border border-default p-4 bg-elevated/20">
              <p class="text-sm font-semibold text-muted uppercase tracking-wide mb-1">Frameworks</p>
              <p class="text-2xl font-bold">{{ detail.frameworks?.length ?? 0 }}</p>
            </div>
          </section>

          <!-- BIO (PR86d) -->
          <section
            v-if="(detail as any).bio_md"
            class="rounded-xl border border-default bg-elevated/10 p-5"
          >
            <h3 class="text-sm font-semibold uppercase tracking-wide text-muted mb-3">
              Bio
            </h3>
            <div
              class="prose prose-sm dark:prose-invert max-w-none"
              v-html="markedHtml((detail as any).bio_md)"
            />
          </section>

          <!-- TABS -->
          <UTabs :items="tabs" default-value="dna" class="w-full">
            <template #content="{ item }">
              <!-- DNA -->
              <div v-if="item.value === 'dna'" class="space-y-6 mt-6">
                <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <UCard>
                    <div class="space-y-2">
                      <p class="text-sm font-semibold text-muted uppercase tracking-wide">MBTI</p>
                      <p class="text-4xl font-bold font-mono tracking-widest">
                        {{ detail.mbti || '----' }}
                      </p>
                      <p v-if="detail.mbti && mbtiDescriptions[detail.mbti]" class="text-sm text-muted">
                        {{ mbtiDescriptions[detail.mbti] }}
                      </p>
                    </div>
                  </UCard>

                  <UCard>
                    <div class="space-y-2">
                      <p class="text-sm font-semibold text-muted uppercase tracking-wide">Enneagram</p>
                      <p class="text-3xl font-bold">
                        Type {{ detail.enneagram?.type ?? '-' }}
                        <span v-if="detail.enneagram?.wing" class="text-xl font-normal text-muted">
                          w{{ detail.enneagram.wing }}
                        </span>
                      </p>
                    </div>
                  </UCard>

                  <UCard>
                    <div class="space-y-3">
                      <p class="text-sm font-semibold text-muted uppercase tracking-wide">DISC</p>
                      <p class="text-3xl font-bold font-mono">
                        {{ detail.disc?.primary ?? '' }}{{ detail.disc?.secondary ?? '' }}
                      </p>
                      <div class="space-y-2 pt-1">
                        <div v-for="letter in discLetters" :key="letter" class="flex items-center gap-2">
                          <span class="w-4 text-xs font-mono font-bold text-muted">{{ letter }}</span>
                          <div class="flex-1 h-2 rounded-full bg-muted/20">
                            <div
                              class="h-2 rounded-full"
                              :class="discBarColor(letter)"
                              :style="{ width: `${discBarValue(letter)}%` }"
                            />
                          </div>
                          <span class="w-6 text-right text-xs font-mono text-muted">
                            {{ discBarValue(letter) }}
                          </span>
                        </div>
                      </div>
                    </div>
                  </UCard>
                </div>

                <UCard>
                  <p class="text-sm font-semibold text-muted uppercase tracking-wide mb-4">
                    Big Five (OCEAN)
                  </p>
                  <div v-if="detail.big_five" class="space-y-3">
                    <div v-for="key in bigFiveKeys" :key="key" class="flex items-center gap-3">
                      <span class="w-36 text-sm text-muted">{{ bigFiveLabels[key] }}</span>
                      <div class="flex-1 h-2 rounded-full bg-muted/20">
                        <div
                          class="h-2 rounded-full"
                          :class="bigFiveBarColor((detail.big_five as any)[key] ?? 0)"
                          :style="{ width: `${(detail.big_five as any)[key] ?? 0}%` }"
                        />
                      </div>
                      <span class="w-8 text-right text-sm font-mono">
                        {{ (detail.big_five as any)[key] ?? 0 }}
                      </span>
                    </div>
                  </div>
                </UCard>
              </div>

              <!-- COMMUNICATION -->
              <div v-else-if="item.value === 'communication'" class="space-y-4 mt-6">
                <UCard v-if="detail.communication">
                  <dl class="grid grid-cols-3 gap-2 text-sm">
                    <dt class="text-muted">Tone</dt>
                    <dd class="col-span-2">{{ detail.communication.tone || '—' }}</dd>
                    <dt class="text-muted">Vocabulary</dt>
                    <dd class="col-span-2">{{ detail.communication.vocabulary_level || '—' }}</dd>
                  </dl>
                </UCard>
                <div v-else class="py-8 text-center text-sm text-muted">
                  No communication data available.
                </div>
              </div>

              <!-- KNOWLEDGE -->
              <div v-else-if="item.value === 'knowledge'" class="space-y-4 mt-6">
                <UCard v-if="detail.mental_models?.length">
                  <p class="text-sm font-semibold text-muted uppercase tracking-wide mb-3">
                    Mental models ({{ detail.mental_models.length }})
                  </p>
                  <div class="flex flex-wrap gap-1.5">
                    <UBadge v-for="m in detail.mental_models" :key="m" :label="m" variant="outline" size="sm" />
                  </div>
                </UCard>

                <UCard v-if="detail.expertise_domains?.length">
                  <p class="text-sm font-semibold text-muted uppercase tracking-wide mb-3">
                    Expertise ({{ detail.expertise_domains.length }})
                  </p>
                  <div class="flex flex-wrap gap-1.5">
                    <UBadge v-for="e in detail.expertise_domains" :key="e" :label="e" variant="soft" size="sm" />
                  </div>
                </UCard>

                <UCard v-if="detail.frameworks?.length">
                  <p class="text-sm font-semibold text-muted uppercase tracking-wide mb-3">
                    Frameworks ({{ detail.frameworks.length }})
                  </p>
                  <ul class="space-y-2">
                    <li v-for="f in detail.frameworks" :key="f" class="flex items-center gap-2 text-sm">
                      <UIcon name="i-lucide-check" class="size-3.5 text-primary shrink-0" />
                      {{ f }}
                    </li>
                  </ul>
                </UCard>

                <UCard v-if="detail.key_quotes?.length">
                  <p class="text-sm font-semibold text-muted uppercase tracking-wide mb-3">
                    Key quotes ({{ detail.key_quotes.length }})
                  </p>
                  <ul class="space-y-2">
                    <li
                      v-for="q in detail.key_quotes"
                      :key="q"
                      class="text-sm italic text-muted border-l-2 border-primary/30 pl-3"
                    >
                      "{{ q }}"
                    </li>
                  </ul>
                </UCard>

                <div
                  v-if="!detail.mental_models?.length && !detail.expertise_domains?.length && !detail.frameworks?.length && !detail.key_quotes?.length"
                  class="py-8 text-center text-sm text-muted"
                >
                  No knowledge data available.
                </div>
              </div>

              <!-- LINKED AGENTS -->
              <div v-else-if="item.value === 'agents'" class="space-y-4 mt-6">
                <UCard v-if="linkedAgentCount > 0">
                  <p class="text-sm font-semibold text-muted uppercase tracking-wide mb-3">
                    Linked to {{ linkedAgentCount }} agent{{ linkedAgentCount === 1 ? '' : 's' }}
                  </p>
                  <div class="space-y-2">
                    <NuxtLink
                      v-for="aid in linkedAgentIds"
                      :key="aid"
                      :to="`/agents/${aid}`"
                      class="flex items-center justify-between p-3 rounded-lg border border-default hover:border-primary/40 transition-colors"
                    >
                      <span class="font-mono text-sm">{{ aid }}</span>
                      <UIcon name="i-lucide-arrow-right" class="size-4 text-muted" />
                    </NuxtLink>
                  </div>
                </UCard>
                <div v-else class="py-8 text-center text-sm text-muted">
                  Not linked to any agent yet. Open an agent's edit drawer
                  to attach this persona.
                </div>
              </div>
            </template>
          </UTabs>

          <!-- EDIT DRAWER -->
          <USlideover
            :open="editOpen"
            :ui="{ content: 'max-w-2xl w-full' }"
            @update:open="(v) => v ? null : tryCloseEdit()"
          >
            <template #content>
              <UCard
                v-if="draft"
                :ui="{
                  root: 'h-full flex flex-col rounded-none',
                  body: 'flex-1 overflow-y-auto',
                }"
              >
                <template #header>
                  <div class="flex items-center justify-between gap-3">
                    <h2 class="text-xl font-bold">Edit {{ draft.name || 'persona' }}</h2>
                    <div class="flex items-center gap-2">
                      <UButton
                        label="Auto-fill empties"
                        icon="i-lucide-sparkles"
                        color="primary"
                        variant="soft"
                        size="sm"
                        :loading="autofilling"
                        @click="autofillEmpties"
                      />
                      <UButton
                        icon="i-lucide-x"
                        variant="ghost"
                        size="sm"
                        aria-label="Close"
                        @click="tryCloseEdit"
                      />
                    </div>
                  </div>
                </template>

                <div class="space-y-5">
                  <section class="space-y-3">
                    <h3 class="text-xs font-semibold uppercase tracking-wider text-muted">Identity</h3>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                      <UFormField label="Name" required>
                        <UInput v-model="draft.name" class="w-full" @update:model-value="markDirty" />
                      </UFormField>
                      <UFormField label="Title">
                        <UInput v-model="draft.title" class="w-full" @update:model-value="markDirty" />
                      </UFormField>
                      <UFormField label="Source">
                        <UInput v-model="draft.source" class="w-full" @update:model-value="markDirty" />
                      </UFormField>
                      <UFormField label="Tagline">
                        <UInput v-model="draft.tagline" class="w-full" @update:model-value="markDirty" />
                      </UFormField>
                    </div>
                  </section>

                  <section class="space-y-3">
                    <h3 class="text-xs font-semibold uppercase tracking-wider text-muted">Behavioural DNA</h3>
                    <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
                      <UFormField label="MBTI">
                        <USelect v-model="draft.mbti" :items="mbtiOptions" class="w-full" @update:model-value="markDirty" />
                      </UFormField>
                      <UFormField label="DISC primary">
                        <USelect v-model="draft.disc.primary" :items="discOptions" class="w-full" @update:model-value="markDirty" />
                      </UFormField>
                      <UFormField label="Enneagram">
                        <UInput v-model.number="draft.enneagram.type" type="number" :min="1" :max="9" class="w-full" @update:model-value="markDirty" />
                      </UFormField>
                      <UFormField label="Wing">
                        <UInput v-model.number="draft.enneagram.wing" type="number" :min="1" :max="9" class="w-full" @update:model-value="markDirty" />
                      </UFormField>
                    </div>
                    <div class="space-y-2">
                      <div
                        v-for="key in bigFiveKeys"
                        :key="key"
                        class="flex items-center gap-3"
                      >
                        <label class="text-xs text-muted w-36 shrink-0 capitalize">{{ key }}</label>
                        <UInput
                          v-model.number="(draft.big_five as any)[key]"
                          type="number"
                          :min="0"
                          :max="100"
                          class="w-20"
                          @update:model-value="markDirty"
                        />
                        <input
                          v-model.number="(draft.big_five as any)[key]"
                          type="range"
                          :min="0"
                          :max="100"
                          class="flex-1"
                          @input="markDirty"
                        />
                      </div>
                    </div>
                  </section>

                  <section class="space-y-3">
                    <h3 class="text-xs font-semibold uppercase tracking-wider text-muted">Knowledge</h3>
                    <UFormField label="Mental models" help="comma-separated">
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
                        :model-value="listToCsv(draft.mental_models)"
                        @update:model-value="(v: string) => { if (draft) { draft.mental_models = csvToList(v); markDirty() } }"
                        class="w-full"
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
                        @update:model-value="(v: string) => { if (draft) { draft.expertise_domains = csvToList(v); markDirty() } }"
                        class="w-full"
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
                        @update:model-value="(v: string) => { if (draft) { draft.frameworks = csvToList(v); markDirty() } }"
                        class="w-full"
                      />
                    </UFormField>
                  </section>

                  <section class="space-y-3">
                    <h3 class="text-xs font-semibold uppercase tracking-wider text-muted">Communication</h3>
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
                        <USelect v-model="draft.communication.vocabulary_level" :items="vocabOptions" class="w-full" @update:model-value="markDirty" />
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
                        @update:model-value="(v: string) => { if (draft) { draft.communication.avoid = csvToList(v); markDirty() } }"
                        class="w-full"
                      />
                    </UFormField>
                  </section>

                  <section class="space-y-3">
                    <h3 class="text-xs font-semibold uppercase tracking-wider text-muted">
                      Bio (Markdown)
                    </h3>
                    <MarkdownEditor
                      :model-value="(draft as any).bio_md ?? ''"
                      :rows="10"
                      placeholder="A free-text Markdown bio for this persona — voice samples, context, references."
                      @update:model-value="(v: string) => { if (draft) { (draft as any).bio_md = v; markDirty() } }"
                    />
                  </section>

                  <section class="space-y-3">
                    <div class="flex items-center justify-between">
                      <h3 class="text-xs font-semibold uppercase tracking-wider text-muted">Key quotes</h3>
                      <UButton
                        label="Suggest with AI"
                        icon="i-lucide-sparkles"
                        size="xs"
                        color="primary"
                        variant="soft"
                        :loading="suggestingField === 'key_quotes'"
                        :disabled="suggestingField !== null"
                        @click="suggest('key_quotes')"
                      />
                    </div>
                    <UTextarea
                      :model-value="(draft.key_quotes ?? []).join('\n')"
                      :rows="4"
                      placeholder="One quote per line. Verbatim or paraphrased."
                      @update:model-value="(v: string) => { if (draft) { draft.key_quotes = v.split('\n').map((q) => q.trim()).filter(Boolean); markDirty() } }"
                      class="w-full"
                    />
                    <p class="text-xs text-muted">
                      {{ (draft.key_quotes ?? []).length }} quote{{ (draft.key_quotes ?? []).length === 1 ? '' : 's' }}.
                      One per line.
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
                      <UButton label="Cancel" variant="ghost" :disabled="saving" @click="tryCloseEdit" />
                      <UButton
                        label="Save"
                        icon="i-lucide-check"
                        :loading="saving"
                        :disabled="!dirty"
                        @click="saveEdit"
                      />
                    </div>
                  </div>
                </template>
              </UCard>
            </template>
          </USlideover>

          <PersonaCloneDialog
            v-if="detail"
            v-model="cloneOpen"
            :persona-id="detail.id"
            :persona-name="detail.name"
            @cloned="onCloned"
          />
        </div>
      </DashboardState>
    </template>
  </UDashboardPanel>
</template>
