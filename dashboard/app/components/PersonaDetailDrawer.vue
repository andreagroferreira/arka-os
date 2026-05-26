<script setup lang="ts">
// PR74 v2.92.0 — Persona detail + edit drawer.
//
// Click a persona card on the list → this drawer opens with every
// field visible. Toggle to Edit mode to mutate any field, then save
// via PUT /api/personas/{id} (writes to both JSON store + Obsidian).

import type { Persona } from '~/types'

interface DetailResponse extends Persona {
  _source_store?: 'obsidian' | 'json'
  _obsidian_path?: string
}

const props = defineProps<{
  modelValue: boolean
  personaId: string | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'saved', persona: Persona): void
  (e: 'deleted', personaId: string): void
}>()

const { apiBase } = useApi()
const toast = useToast()

const detail = ref<DetailResponse | null>(null)
const editing = ref(false)
const draft = ref<Persona | null>(null)
const saving = ref(false)
const deleting = ref(false)
const loading = ref(false)
const loadError = ref<string | null>(null)

watch(
  () => [props.modelValue, props.personaId] as const,
  async ([open, id]) => {
    if (!open || !id) {
      detail.value = null
      editing.value = false
      draft.value = null
      loadError.value = null
      return
    }
    await loadDetail(id)
  },
)

async function loadDetail(id: string) {
  loading.value = true
  loadError.value = null
  try {
    const data = await $fetch<DetailResponse | { error: string }>(
      `${apiBase}/api/personas/${id}`,
    )
    if ('error' in data && data.error) {
      loadError.value = data.error
      detail.value = null
    } else {
      detail.value = data as DetailResponse
    }
  } catch (err) {
    loadError.value = err instanceof Error ? err.message : 'unknown error'
  } finally {
    loading.value = false
  }
}

function startEdit() {
  if (!detail.value) return
  draft.value = JSON.parse(JSON.stringify(detail.value)) as Persona
  editing.value = true
}

function cancelEdit() {
  draft.value = null
  editing.value = false
}

async function saveEdit() {
  if (!draft.value || !props.personaId) return
  saving.value = true
  try {
    const res = await $fetch<{
      id: string
      updated: boolean
      json_written: boolean
      obsidian_path: string | null
      error?: string
    }>(`${apiBase}/api/personas/${props.personaId}`, {
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
    emit('saved', draft.value)
    detail.value = { ...detail.value, ...draft.value } as DetailResponse
    editing.value = false
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
  if (!props.personaId) return
  if (typeof window === 'undefined') return
  const ok = window.confirm(
    `Delete persona "${detail.value?.name}"?\n\n`
    + 'This removes it from the JSON store. The Obsidian file (if any) '
    + 'is left in place — delete manually from Obsidian if you want it gone.',
  )
  if (!ok) return
  deleting.value = true
  try {
    await $fetch(`${apiBase}/api/personas/${props.personaId}`, {
      method: 'DELETE',
    })
    toast.add({
      title: 'Persona deleted',
      description: detail.value?.name ?? '',
      color: 'success',
    })
    emit('deleted', props.personaId)
    emit('update:modelValue', false)
  } catch (err) {
    toast.add({
      title: 'Delete failed',
      description: err instanceof Error ? err.message : 'unknown error',
      color: 'error',
    })
  } finally {
    deleting.value = false
  }
}

function closeDrawer() {
  if (editing.value && !saving.value) {
    if (typeof window !== 'undefined'
        && !window.confirm('Discard unsaved edits?')) {
      return
    }
  }
  cancelEdit()
  emit('update:modelValue', false)
}

function listToCsv(list: string[] | undefined): string {
  return (list ?? []).join(', ')
}

function csvToList(value: string): string[] {
  return value.split(',').map((s) => s.trim()).filter(Boolean)
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
  <USlideover
    :open="modelValue"
    :ui="{ content: 'max-w-2xl w-full' }"
    @update:open="(v) => v ? null : closeDrawer()"
  >
    <template #content>
      <UCard
        :ui="{
          root: 'h-full flex flex-col rounded-none',
          body: 'flex-1 overflow-y-auto',
        }"
      >
        <template #header>
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <h2 class="text-xl font-bold truncate">
                {{ detail?.name ?? 'Persona' }}
              </h2>
              <div class="flex items-center gap-2 mt-1 flex-wrap">
                <UBadge
                  v-if="detail?._source_store === 'obsidian'"
                  label="From Obsidian"
                  icon="i-lucide-file-text"
                  color="primary"
                  variant="subtle"
                  size="xs"
                />
                <UBadge
                  v-else-if="detail?._source_store === 'json'"
                  label="JSON store"
                  variant="outline"
                  size="xs"
                />
                <span
                  v-if="detail?._obsidian_path"
                  class="text-xs text-muted font-mono truncate"
                  :title="detail._obsidian_path"
                >
                  {{ detail._obsidian_path.split('/').slice(-2).join('/') }}
                </span>
              </div>
            </div>
            <div class="flex items-center gap-1 shrink-0">
              <UButton
                v-if="!editing"
                icon="i-lucide-pencil"
                variant="ghost"
                size="sm"
                aria-label="Edit persona"
                @click="startEdit"
              />
              <UButton
                v-if="!editing"
                icon="i-lucide-trash-2"
                color="error"
                variant="ghost"
                size="sm"
                :loading="deleting"
                aria-label="Delete persona"
                @click="deletePersona"
              />
              <UButton
                icon="i-lucide-x"
                variant="ghost"
                size="sm"
                aria-label="Close"
                @click="closeDrawer"
              />
            </div>
          </div>
        </template>

        <div v-if="loading" class="flex items-center justify-center py-12">
          <UIcon name="i-lucide-loader-2" class="size-8 animate-spin text-muted" />
        </div>

        <div v-else-if="loadError" class="flex flex-col items-center justify-center gap-3 py-12">
          <UIcon name="i-lucide-alert-triangle" class="size-10 text-red-500" />
          <p class="text-sm text-muted">{{ loadError }}</p>
        </div>

        <div v-else-if="detail && !editing" class="space-y-6">
          <p v-if="detail.tagline" class="text-base italic text-muted">
            "{{ detail.tagline }}"
          </p>

          <section v-if="detail.title || detail.source">
            <h3 class="text-xs font-semibold uppercase tracking-wider text-muted mb-2">Identity</h3>
            <dl class="grid grid-cols-3 gap-2 text-sm">
              <dt class="text-muted">Title</dt>
              <dd class="col-span-2">{{ detail.title || '—' }}</dd>
              <dt class="text-muted">Source</dt>
              <dd class="col-span-2 font-mono text-xs">{{ detail.source || '—' }}</dd>
            </dl>
          </section>

          <section>
            <h3 class="text-xs font-semibold uppercase tracking-wider text-muted mb-2">Behavioural DNA</h3>
            <dl class="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
              <dt class="text-muted">MBTI</dt>
              <dd>{{ detail.mbti || '—' }}</dd>
              <dt class="text-muted">DISC</dt>
              <dd>
                {{ detail.disc?.primary || '—' }}{{ detail.disc?.secondary ? `/${detail.disc.secondary}` : '' }}
              </dd>
              <dt class="text-muted">Enneagram</dt>
              <dd>
                {{ detail.enneagram?.type ?? '—' }}w{{ detail.enneagram?.wing ?? '?' }}
              </dd>
            </dl>
            <div class="mt-3 space-y-1.5">
              <div
                v-for="trait in ([
                  ['Openness', detail.big_five?.openness ?? 0],
                  ['Conscientiousness', detail.big_five?.conscientiousness ?? 0],
                  ['Extraversion', detail.big_five?.extraversion ?? 0],
                  ['Agreeableness', detail.big_five?.agreeableness ?? 0],
                  ['Neuroticism', detail.big_five?.neuroticism ?? 0],
                ] as Array<[string, number]>)"
                :key="trait[0]"
                class="flex items-center gap-3"
              >
                <span class="text-xs text-muted w-36 shrink-0">{{ trait[0] }}</span>
                <div class="flex-1 h-2 rounded-full bg-muted/15 overflow-hidden">
                  <div class="h-2 rounded-full bg-primary" :style="{ width: `${trait[1]}%` }" />
                </div>
                <span class="text-xs font-mono w-10 text-right">{{ trait[1] }}</span>
              </div>
            </div>
          </section>

          <section v-if="detail.mental_models?.length">
            <h3 class="text-xs font-semibold uppercase tracking-wider text-muted mb-2">
              Mental models ({{ detail.mental_models.length }})
            </h3>
            <div class="flex flex-wrap gap-1.5">
              <UBadge
                v-for="m in detail.mental_models"
                :key="m"
                :label="m"
                variant="outline"
                size="xs"
              />
            </div>
          </section>

          <section v-if="detail.expertise_domains?.length">
            <h3 class="text-xs font-semibold uppercase tracking-wider text-muted mb-2">
              Expertise ({{ detail.expertise_domains.length }})
            </h3>
            <div class="flex flex-wrap gap-1.5">
              <UBadge
                v-for="e in detail.expertise_domains"
                :key="e"
                :label="e"
                variant="soft"
                size="xs"
              />
            </div>
          </section>

          <section v-if="detail.frameworks?.length">
            <h3 class="text-xs font-semibold uppercase tracking-wider text-muted mb-2">
              Frameworks ({{ detail.frameworks.length }})
            </h3>
            <div class="flex flex-wrap gap-1.5">
              <UBadge
                v-for="f in detail.frameworks"
                :key="f"
                :label="f"
                variant="outline"
                size="xs"
              />
            </div>
          </section>

          <section v-if="detail.key_quotes?.length">
            <h3 class="text-xs font-semibold uppercase tracking-wider text-muted mb-2">
              Key quotes ({{ detail.key_quotes.length }})
            </h3>
            <ul class="space-y-2">
              <li
                v-for="q in detail.key_quotes"
                :key="q"
                class="text-sm italic text-muted border-l-2 border-primary/30 pl-3"
              >
                "{{ q }}"
              </li>
            </ul>
          </section>

          <section v-if="detail.communication">
            <h3 class="text-xs font-semibold uppercase tracking-wider text-muted mb-2">Communication</h3>
            <dl class="grid grid-cols-3 gap-2 text-sm">
              <dt class="text-muted">Tone</dt>
              <dd class="col-span-2">{{ detail.communication.tone || '—' }}</dd>
              <dt class="text-muted">Vocabulary</dt>
              <dd class="col-span-2">{{ detail.communication.vocabulary_level || '—' }}</dd>
            </dl>
          </section>
        </div>

        <div v-else-if="draft" class="space-y-5">
          <section class="space-y-3">
            <h3 class="text-xs font-semibold uppercase tracking-wider text-muted">Identity</h3>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
              <UFormField label="Name" required>
                <UInput v-model="draft.name" class="w-full" />
              </UFormField>
              <UFormField label="Title">
                <UInput v-model="draft.title" class="w-full" />
              </UFormField>
              <UFormField label="Source">
                <UInput v-model="draft.source" class="w-full" />
              </UFormField>
              <UFormField label="Tagline">
                <UInput v-model="draft.tagline" class="w-full" />
              </UFormField>
            </div>
          </section>

          <section class="space-y-3">
            <h3 class="text-xs font-semibold uppercase tracking-wider text-muted">Behavioural DNA</h3>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
              <UFormField label="MBTI">
                <USelect v-model="draft.mbti" :items="mbtiOptions" class="w-full" />
              </UFormField>
              <UFormField label="DISC primary">
                <USelect v-model="draft.disc.primary" :items="discOptions" class="w-full" />
              </UFormField>
              <UFormField label="Enneagram">
                <UInput v-model.number="draft.enneagram.type" type="number" :min="1" :max="9" class="w-full" />
              </UFormField>
              <UFormField label="Wing">
                <UInput v-model.number="draft.enneagram.wing" type="number" :min="1" :max="9" class="w-full" />
              </UFormField>
            </div>
            <div class="space-y-2">
              <div
                v-for="key in (['openness', 'conscientiousness', 'extraversion', 'agreeableness', 'neuroticism'] as const)"
                :key="key"
                class="flex items-center gap-3"
              >
                <label class="text-xs text-muted w-36 shrink-0 capitalize">{{ key }}</label>
                <UInput
                  v-model.number="draft.big_five[key]"
                  type="number"
                  :min="0"
                  :max="100"
                  class="w-20"
                />
                <input
                  v-model.number="draft.big_five[key]"
                  type="range"
                  :min="0"
                  :max="100"
                  class="flex-1"
                />
              </div>
            </div>
          </section>

          <section class="space-y-3">
            <h3 class="text-xs font-semibold uppercase tracking-wider text-muted">Knowledge</h3>
            <UFormField label="Mental models" help="comma-separated">
              <UInput
                :model-value="listToCsv(draft.mental_models)"
                @update:model-value="(v: string) => draft && (draft.mental_models = csvToList(v))"
                class="w-full"
              />
            </UFormField>
            <UFormField label="Expertise domains" help="comma-separated">
              <UInput
                :model-value="listToCsv(draft.expertise_domains)"
                @update:model-value="(v: string) => draft && (draft.expertise_domains = csvToList(v))"
                class="w-full"
              />
            </UFormField>
            <UFormField label="Frameworks" help="comma-separated">
              <UInput
                :model-value="listToCsv(draft.frameworks)"
                @update:model-value="(v: string) => draft && (draft.frameworks = csvToList(v))"
                class="w-full"
              />
            </UFormField>
          </section>

          <section class="space-y-3">
            <h3 class="text-xs font-semibold uppercase tracking-wider text-muted">Communication</h3>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
              <UFormField label="Tone">
                <UInput v-model="draft.communication.tone" class="w-full" />
              </UFormField>
              <UFormField label="Vocabulary level">
                <USelect v-model="draft.communication.vocabulary_level" :items="vocabOptions" class="w-full" />
              </UFormField>
            </div>
          </section>
        </div>

        <template #footer>
          <div v-if="editing" class="flex justify-end gap-2">
            <UButton label="Cancel" variant="ghost" :disabled="saving" @click="cancelEdit" />
            <UButton
              label="Save"
              icon="i-lucide-check"
              :loading="saving"
              @click="saveEdit"
            />
          </div>
          <p v-else class="text-xs text-muted text-right">
            Click ✏️ to edit. Saves to JSON store + Obsidian vault when configured.
          </p>
        </template>
      </UCard>
    </template>
  </USlideover>
</template>
