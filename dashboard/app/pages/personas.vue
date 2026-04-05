<script setup lang="ts">
import type { Persona } from '~/types'

const { fetchApi, apiBase } = useApi()
const toast = useToast()

// --- Fetch personas ---
const { data, status, error, refresh } = fetchApi<{ personas: Persona[], total: number }>('/api/personas')

const personas = computed(() => data.value?.personas ?? [])

// --- Form visibility ---
const showForm = ref(false)

// --- Form state ---
const defaultForm = () => ({
  name: '',
  title: '',
  source: '',
  tagline: '',
  mbti: '',
  disc_primary: '',
  disc_secondary: '',
  enneagram_type: '',
  enneagram_wing: '',
  big_five_o: 50,
  big_five_c: 50,
  big_five_e: 50,
  big_five_a: 50,
  big_five_n: 50,
  mental_models: '',
  expertise_domains: '',
  frameworks: '',
  communication_tone: ''
})

const form = ref(defaultForm())
const creating = ref(false)

const mbtiTypes = [
  'INTJ', 'INTP', 'ENTJ', 'ENTP',
  'INFJ', 'INFP', 'ENFJ', 'ENFP',
  'ISTJ', 'ISFJ', 'ESTJ', 'ESFJ',
  'ISTP', 'ISFP', 'ESTP', 'ESFP'
].map(t => ({ label: t, value: t }))

const discTypes = [
  { label: 'D — Dominance', value: 'D' },
  { label: 'I — Influence', value: 'I' },
  { label: 'S — Steadiness', value: 'S' },
  { label: 'C — Conscientiousness', value: 'C' }
]

const enneagramTypes = Array.from({ length: 9 }, (_, i) => ({
  label: `Type ${i + 1}`,
  value: String(i + 1)
}))

const departmentOptions = [
  'dev', 'marketing', 'brand', 'finance', 'strategy',
  'ecom', 'kb', 'ops', 'pm', 'saas',
  'landing', 'content', 'community', 'sales', 'leadership', 'org'
].map(d => ({ label: d, value: d }))

const tierOptions = [
  { label: 'Tier 1 — Squad Leads', value: '1' },
  { label: 'Tier 2 — Specialists', value: '2' },
  { label: 'Tier 3 — Support', value: '3' }
]

// --- Create persona ---
async function createPersona() {
  if (!form.value.name.trim()) return

  creating.value = true
  try {
    await $fetch(`${apiBase}/api/personas`, {
      method: 'POST',
      body: {
        name: form.value.name,
        title: form.value.title,
        source: form.value.source,
        tagline: form.value.tagline,
        mbti: form.value.mbti,
        disc: {
          primary: form.value.disc_primary,
          secondary: form.value.disc_secondary
        },
        enneagram: {
          type: form.value.enneagram_type ? Number(form.value.enneagram_type) : null,
          wing: form.value.enneagram_wing ? Number(form.value.enneagram_wing) : null
        },
        big_five: {
          openness: form.value.big_five_o,
          conscientiousness: form.value.big_five_c,
          extraversion: form.value.big_five_e,
          agreeableness: form.value.big_five_a,
          neuroticism: form.value.big_five_n
        },
        mental_models: form.value.mental_models ? form.value.mental_models.split(',').map(s => s.trim()).filter(Boolean) : [],
        expertise_domains: form.value.expertise_domains ? form.value.expertise_domains.split(',').map(s => s.trim()).filter(Boolean) : [],
        frameworks: form.value.frameworks ? form.value.frameworks.split(',').map(s => s.trim()).filter(Boolean) : [],
        communication: {
          tone: form.value.communication_tone
        }
      }
    })

    toast.add({ title: 'Persona created', description: `${form.value.name} has been added.`, color: 'success' })
    form.value = defaultForm()
    showForm.value = false
    await refresh()
  } catch {
    toast.add({ title: 'Error', description: 'Failed to create persona.', color: 'error' })
  } finally {
    creating.value = false
  }
}

// --- Delete persona ---
const deleting = ref<string | null>(null)

async function deletePersona(persona: Persona) {
  deleting.value = persona.id
  try {
    await $fetch(`${apiBase}/api/personas/${persona.id}`, { method: 'DELETE' })
    toast.add({ title: 'Persona deleted', description: `${persona.name} has been removed.`, color: 'success' })
    await refresh()
  } catch {
    toast.add({ title: 'Error', description: 'Failed to delete persona.', color: 'error' })
  } finally {
    deleting.value = null
  }
}

// --- Clone to agent ---
const cloneTarget = ref<Persona | null>(null)
const cloneModalOpen = ref(false)
const cloneDepartment = ref('')
const cloneTier = ref('')
const cloning = ref(false)

function openCloneModal(persona: Persona) {
  cloneTarget.value = persona
  cloneDepartment.value = ''
  cloneTier.value = ''
  cloneModalOpen.value = true
}

function closeCloneModal() {
  cloneModalOpen.value = false
  cloneTarget.value = null
}

async function cloneToAgent() {
  if (!cloneTarget.value || !cloneDepartment.value || !cloneTier.value) return

  cloning.value = true
  try {
    await $fetch(`${apiBase}/api/personas/${cloneTarget.value.id}/clone`, {
      method: 'POST',
      body: {
        department: cloneDepartment.value,
        tier: Number(cloneTier.value)
      }
    })
    toast.add({
      title: 'Agent created',
      description: `${cloneTarget.value.name} cloned to ${cloneDepartment.value} department.`,
      color: 'success'
    })
    closeCloneModal()
    await refresh()
  } catch {
    toast.add({ title: 'Error', description: 'Failed to clone persona to agent.', color: 'error' })
  } finally {
    cloning.value = false
  }
}

// --- DNA badge colors ---
function mbtiColor(mbti: string): string {
  if (!mbti) return 'neutral'
  const analysts = ['INTJ', 'INTP', 'ENTJ', 'ENTP']
  const diplomats = ['INFJ', 'INFP', 'ENFJ', 'ENFP']
  const sentinels = ['ISTJ', 'ISFJ', 'ESTJ', 'ESFJ']
  if (analysts.includes(mbti)) return 'primary'
  if (diplomats.includes(mbti)) return 'success'
  if (sentinels.includes(mbti)) return 'warning'
  return 'error'
}

function discColor(disc: string): string {
  const colors: Record<string, string> = { D: 'error', I: 'warning', S: 'success', C: 'primary' }
  return colors[disc] ?? 'neutral'
}
</script>

<template>
  <UDashboardPanel id="personas">
    <template #header>
      <UDashboardNavbar title="Personas">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #trailing>
          <UBadge v-if="data?.total" :label="data.total" variant="subtle" />
          <UButton
            :label="showForm ? 'Cancel' : 'New Persona'"
            :icon="showForm ? 'i-lucide-x' : 'i-lucide-plus'"
            :variant="showForm ? 'ghost' : 'solid'"
            size="sm"
            @click="showForm = !showForm"
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
        <p class="text-sm text-muted">Failed to load personas.</p>
        <UButton label="Retry" variant="outline" color="primary" icon="i-lucide-refresh-cw" @click="refresh()" />
      </div>

      <!-- Content -->
      <template v-else>
        <!-- Create Persona Form -->
        <UCard v-if="showForm" class="mb-6">
          <template #header>
            <div class="flex items-center gap-2">
              <UIcon name="i-lucide-user-plus" class="size-5 text-primary" />
              <h3 class="text-sm font-semibold">Create Persona</h3>
            </div>
          </template>

          <form @submit.prevent="createPersona" class="space-y-6">
            <!-- Identity -->
            <fieldset>
              <legend class="text-xs font-semibold text-muted uppercase tracking-wider mb-3">Identity</legend>
              <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <UFormField label="Name" required>
                  <UInput
                    v-model="form.name"
                    placeholder="e.g. Alex Hormozi"
                    aria-label="Persona name"
                    required
                  />
                </UFormField>
                <UFormField label="Title">
                  <UInput
                    v-model="form.title"
                    placeholder="e.g. Business Strategy"
                    aria-label="Persona title"
                  />
                </UFormField>
                <UFormField label="Source">
                  <UInput
                    v-model="form.source"
                    placeholder="e.g. Alex Hormozi"
                    aria-label="Persona source"
                  />
                </UFormField>
                <UFormField label="Tagline">
                  <UInput
                    v-model="form.tagline"
                    placeholder="e.g. The Natural Commander"
                    aria-label="Persona tagline"
                  />
                </UFormField>
              </div>
            </fieldset>

            <!-- Behavioral DNA -->
            <fieldset>
              <legend class="text-xs font-semibold text-muted uppercase tracking-wider mb-3">Behavioral DNA</legend>
              <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <UFormField label="MBTI">
                  <USelect
                    v-model="form.mbti"
                    :items="mbtiTypes"
                    placeholder="Select MBTI"
                    aria-label="MBTI type"
                  />
                </UFormField>
                <UFormField label="DISC Primary">
                  <USelect
                    v-model="form.disc_primary"
                    :items="discTypes"
                    placeholder="Primary"
                    aria-label="DISC primary type"
                  />
                </UFormField>
                <UFormField label="DISC Secondary">
                  <USelect
                    v-model="form.disc_secondary"
                    :items="discTypes"
                    placeholder="Secondary"
                    aria-label="DISC secondary type"
                  />
                </UFormField>
                <UFormField label="Enneagram Type">
                  <USelect
                    v-model="form.enneagram_type"
                    :items="enneagramTypes"
                    placeholder="Type"
                    aria-label="Enneagram type"
                  />
                </UFormField>
              </div>
              <div class="mt-4">
                <UFormField label="Enneagram Wing">
                  <UInput
                    v-model="form.enneagram_wing"
                    type="number"
                    min="1"
                    max="9"
                    placeholder="e.g. 4"
                    class="max-w-32"
                    aria-label="Enneagram wing"
                  />
                </UFormField>
              </div>
            </fieldset>

            <!-- Big Five -->
            <fieldset>
              <legend class="text-xs font-semibold text-muted uppercase tracking-wider mb-3">Big Five (OCEAN)</legend>
              <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
                <UFormField label="Openness">
                  <div class="flex items-center gap-2">
                    <input
                      v-model.number="form.big_five_o"
                      type="range"
                      min="0"
                      max="100"
                      class="w-full accent-primary"
                      aria-label="Openness score"
                    />
                    <span class="text-xs font-mono text-muted w-8 text-right">{{ form.big_five_o }}</span>
                  </div>
                </UFormField>
                <UFormField label="Conscientiousness">
                  <div class="flex items-center gap-2">
                    <input
                      v-model.number="form.big_five_c"
                      type="range"
                      min="0"
                      max="100"
                      class="w-full accent-primary"
                      aria-label="Conscientiousness score"
                    />
                    <span class="text-xs font-mono text-muted w-8 text-right">{{ form.big_five_c }}</span>
                  </div>
                </UFormField>
                <UFormField label="Extraversion">
                  <div class="flex items-center gap-2">
                    <input
                      v-model.number="form.big_five_e"
                      type="range"
                      min="0"
                      max="100"
                      class="w-full accent-primary"
                      aria-label="Extraversion score"
                    />
                    <span class="text-xs font-mono text-muted w-8 text-right">{{ form.big_five_e }}</span>
                  </div>
                </UFormField>
                <UFormField label="Agreeableness">
                  <div class="flex items-center gap-2">
                    <input
                      v-model.number="form.big_five_a"
                      type="range"
                      min="0"
                      max="100"
                      class="w-full accent-primary"
                      aria-label="Agreeableness score"
                    />
                    <span class="text-xs font-mono text-muted w-8 text-right">{{ form.big_five_a }}</span>
                  </div>
                </UFormField>
                <UFormField label="Neuroticism">
                  <div class="flex items-center gap-2">
                    <input
                      v-model.number="form.big_five_n"
                      type="range"
                      min="0"
                      max="100"
                      class="w-full accent-primary"
                      aria-label="Neuroticism score"
                    />
                    <span class="text-xs font-mono text-muted w-8 text-right">{{ form.big_five_n }}</span>
                  </div>
                </UFormField>
              </div>
            </fieldset>

            <!-- Knowledge & Communication -->
            <fieldset>
              <legend class="text-xs font-semibold text-muted uppercase tracking-wider mb-3">Knowledge & Communication</legend>
              <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <UFormField label="Mental Models" hint="Comma-separated">
                  <UInput
                    v-model="form.mental_models"
                    placeholder="e.g. Grand Slam Offer, Value Equation"
                    aria-label="Mental models, comma-separated"
                  />
                </UFormField>
                <UFormField label="Expertise Domains" hint="Comma-separated">
                  <UInput
                    v-model="form.expertise_domains"
                    placeholder="e.g. business strategy, offer creation"
                    aria-label="Expertise domains, comma-separated"
                  />
                </UFormField>
                <UFormField label="Frameworks" hint="Comma-separated">
                  <UInput
                    v-model="form.frameworks"
                    placeholder="e.g. $100M Offers, Value Equation"
                    aria-label="Frameworks, comma-separated"
                  />
                </UFormField>
                <UFormField label="Communication Tone">
                  <UInput
                    v-model="form.communication_tone"
                    placeholder="e.g. direct, high-energy"
                    aria-label="Communication tone"
                  />
                </UFormField>
              </div>
            </fieldset>

            <!-- Submit -->
            <div class="flex justify-end">
              <UButton
                type="submit"
                label="Create Persona"
                icon="i-lucide-plus"
                :loading="creating"
                :disabled="!form.name.trim()"
              />
            </div>
          </form>
        </UCard>

        <!-- Empty state -->
        <div v-if="!personas.length && !showForm" class="flex flex-col items-center justify-center gap-4 py-12">
          <UIcon name="i-lucide-user-plus" class="size-12 text-muted" />
          <p class="text-sm text-muted">No personas yet. Create your first one.</p>
          <UButton label="New Persona" icon="i-lucide-plus" @click="showForm = true" />
        </div>

        <!-- Personas Grid -->
        <div v-if="personas.length" class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          <UCard
            v-for="persona in personas"
            :key="persona.id"
            class="group"
          >
            <div class="space-y-3">
              <!-- Header -->
              <div class="flex items-start justify-between gap-2">
                <div class="min-w-0">
                  <h3 class="text-sm font-semibold truncate">{{ persona.name }}</h3>
                  <p v-if="persona.title" class="text-xs text-muted truncate">{{ persona.title }}</p>
                </div>
                <UButton
                  icon="i-lucide-trash-2"
                  size="xs"
                  variant="ghost"
                  color="error"
                  :loading="deleting === persona.id"
                  aria-label="Delete persona"
                  class="opacity-0 group-hover:opacity-100 transition-opacity shrink-0"
                  @click="deletePersona(persona)"
                />
              </div>

              <!-- Tagline & Source -->
              <p v-if="persona.tagline" class="text-xs text-muted italic">{{ persona.tagline }}</p>
              <p v-if="persona.source" class="text-xs text-muted">
                Source: <span class="font-medium">{{ persona.source }}</span>
              </p>

              <!-- DNA Badges -->
              <div class="flex flex-wrap gap-1.5">
                <UBadge
                  v-if="persona.mbti"
                  :label="persona.mbti"
                  :color="mbtiColor(persona.mbti) as any"
                  variant="subtle"
                  size="xs"
                />
                <UBadge
                  v-if="persona.disc?.primary"
                  :label="`DISC: ${persona.disc.primary}${persona.disc.secondary ? '/' + persona.disc.secondary : ''}`"
                  :color="discColor(persona.disc.primary) as any"
                  variant="subtle"
                  size="xs"
                />
                <UBadge
                  v-if="persona.enneagram?.type"
                  :label="`E${persona.enneagram.type}${persona.enneagram.wing ? 'w' + persona.enneagram.wing : ''}`"
                  variant="outline"
                  size="xs"
                />
              </div>

              <!-- Expertise -->
              <div v-if="persona.expertise_domains?.length" class="flex flex-wrap gap-1">
                <UBadge
                  v-for="domain in persona.expertise_domains.slice(0, 3)"
                  :key="domain"
                  :label="domain"
                  variant="outline"
                  size="xs"
                  color="neutral"
                />
                <UBadge
                  v-if="persona.expertise_domains.length > 3"
                  :label="`+${persona.expertise_domains.length - 3}`"
                  variant="outline"
                  size="xs"
                  color="neutral"
                />
              </div>

              <!-- Clone button -->
              <div class="pt-2 border-t border-default">
                <UButton
                  label="Clone to Agent"
                  icon="i-lucide-copy"
                  size="xs"
                  variant="outline"
                  block
                  @click="openCloneModal(persona)"
                />
              </div>
            </div>
          </UCard>
        </div>
      </template>

      <!-- Clone Modal -->
      <UModal v-model:open="cloneModalOpen">
        <template #content>
          <UCard>
            <template #header>
              <div class="flex items-center justify-between">
                <h3 class="text-sm font-semibold">Clone "{{ cloneTarget?.name }}" to Agent</h3>
                <UButton icon="i-lucide-x" size="xs" variant="ghost" @click="closeCloneModal" aria-label="Close" />
              </div>
            </template>

            <form @submit.prevent="cloneToAgent" class="space-y-4">
              <UFormField label="Department" required>
                <USelect
                  v-model="cloneDepartment"
                  :items="departmentOptions"
                  placeholder="Select department"
                  aria-label="Target department"
                />
              </UFormField>

              <UFormField label="Tier" required>
                <USelect
                  v-model="cloneTier"
                  :items="tierOptions"
                  placeholder="Select tier"
                  aria-label="Agent tier"
                />
              </UFormField>

              <div class="flex justify-end gap-2">
                <UButton label="Cancel" variant="ghost" @click="closeCloneModal" />
                <UButton
                  type="submit"
                  label="Clone"
                  icon="i-lucide-copy"
                  :loading="cloning"
                  :disabled="!cloneDepartment || !cloneTier"
                />
              </div>
            </form>
          </UCard>
        </template>
      </UModal>
    </template>
  </UDashboardPanel>
</template>
