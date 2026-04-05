<script setup lang="ts">
import type { Persona } from '~/types'

const { fetchApi, apiBase } = useApi()
const toast = useToast()

// --- Fetch personas (no await — non-blocking) ---
const { data, status, error, refresh } = fetchApi<{ personas: Persona[]; total: number }>('/api/personas')

const personas = computed(() => data.value?.personas ?? [])

// --- Form visibility ---
const showForm = ref(false)

// --- Form state ---
function defaultForm() {
  return {
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
    communication_tone: '',
  }
}

const form = ref(defaultForm())
const creating = ref(false)

// --- Options ---
const mbtiTypes = [
  'INTJ', 'INTP', 'ENTJ', 'ENTP',
  'INFJ', 'INFP', 'ENFJ', 'ENFP',
  'ISTJ', 'ISFJ', 'ESTJ', 'ESFJ',
  'ISTP', 'ISFP', 'ESTP', 'ESFP',
].map(t => ({ label: t, value: t }))

const discTypes = [
  { label: 'D — Dominance', value: 'D' },
  { label: 'I — Influence', value: 'I' },
  { label: 'S — Steadiness', value: 'S' },
  { label: 'C — Conscientiousness', value: 'C' },
]

const enneagramTypes = Array.from({ length: 9 }, (_, i) => ({
  label: `Type ${i + 1}`,
  value: String(i + 1),
}))

const departmentOptions = [
  'dev', 'marketing', 'brand', 'finance', 'strategy',
  'ecom', 'kb', 'ops', 'pm', 'saas',
  'landing', 'content', 'community', 'sales', 'leadership', 'org',
].map(d => ({ label: d, value: d }))

const tierOptions = [
  { label: 'Tier 1 — Squad Leads', value: '1' },
  { label: 'Tier 2 — Specialists', value: '2' },
  { label: 'Tier 3 — Support', value: '3' },
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
          secondary: form.value.disc_secondary,
        },
        enneagram: {
          type: form.value.enneagram_type ? Number(form.value.enneagram_type) : null,
          wing: form.value.enneagram_wing ? Number(form.value.enneagram_wing) : null,
        },
        big_five: {
          openness: form.value.big_five_o,
          conscientiousness: form.value.big_five_c,
          extraversion: form.value.big_five_e,
          agreeableness: form.value.big_five_a,
          neuroticism: form.value.big_five_n,
        },
        mental_models: form.value.mental_models
          ? form.value.mental_models.split(',').map(s => s.trim()).filter(Boolean)
          : [],
        expertise_domains: form.value.expertise_domains
          ? form.value.expertise_domains.split(',').map(s => s.trim()).filter(Boolean)
          : [],
        frameworks: form.value.frameworks
          ? form.value.frameworks.split(',').map(s => s.trim()).filter(Boolean)
          : [],
        communication: {
          tone: form.value.communication_tone,
        },
      },
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

// --- Clone to agent (inline expansion, no modal) ---
const cloneExpandedId = ref<string | null>(null)
const cloneDepartment = ref('')
const cloneTier = ref('')
const cloning = ref(false)

function toggleClone(persona: Persona) {
  if (cloneExpandedId.value === persona.id) {
    cloneExpandedId.value = null
  } else {
    cloneExpandedId.value = persona.id
    cloneDepartment.value = ''
    cloneTier.value = ''
  }
}

async function cloneToAgent(persona: Persona) {
  if (!cloneDepartment.value || !cloneTier.value) return

  cloning.value = true
  try {
    await $fetch(`${apiBase}/api/personas/${persona.id}/clone`, {
      method: 'POST',
      body: {
        department: cloneDepartment.value,
        tier: Number(cloneTier.value),
      },
    })
    toast.add({
      title: 'Agent created',
      description: `${persona.name} cloned to ${cloneDepartment.value} department.`,
      color: 'success',
    })
    cloneExpandedId.value = null
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
      <div class="overflow-y-auto h-[calc(100vh-4rem)]">
      <!-- Loading -->
      <div v-if="status === 'pending'" class="flex items-center justify-center py-12" aria-label="Loading personas">
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
        <UCard v-if="showForm" class="mb-8">
          <form @submit.prevent="createPersona" class="space-y-8 p-2">
            <!-- Identity -->
            <fieldset>
              <legend class="text-xs font-bold uppercase tracking-widest text-muted mb-4">Identity</legend>
              <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <UFormField label="Name" required>
                  <UInput
                    v-model="form.name"
                    placeholder="e.g. Alex Hormozi"
                    aria-label="Persona name"
                    class="w-full"
                    required
                  />
                </UFormField>
                <UFormField label="Title">
                  <UInput
                    v-model="form.title"
                    placeholder="e.g. Business Strategy"
                    aria-label="Persona title"
                    class="w-full"
                  />
                </UFormField>
                <UFormField label="Source">
                  <UInput
                    v-model="form.source"
                    placeholder="e.g. Alex Hormozi"
                    aria-label="Persona source"
                    class="w-full"
                  />
                </UFormField>
                <UFormField label="Tagline">
                  <UInput
                    v-model="form.tagline"
                    placeholder="e.g. The Natural Commander"
                    aria-label="Persona tagline"
                    class="w-full"
                  />
                </UFormField>
              </div>
            </fieldset>

            <!-- Behavioral DNA -->
            <fieldset>
              <legend class="text-xs font-bold uppercase tracking-widest text-muted mb-4">Behavioral DNA</legend>
              <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <UFormField label="MBTI">
                  <USelect
                    v-model="form.mbti"
                    :items="mbtiTypes"
                    placeholder="Select MBTI"
                    aria-label="MBTI type"
                    class="w-full"
                  />
                </UFormField>
                <UFormField label="DISC Primary">
                  <USelect
                    v-model="form.disc_primary"
                    :items="discTypes"
                    placeholder="Primary"
                    aria-label="DISC primary type"
                    class="w-full"
                  />
                </UFormField>
                <UFormField label="DISC Secondary">
                  <USelect
                    v-model="form.disc_secondary"
                    :items="discTypes"
                    placeholder="Secondary"
                    aria-label="DISC secondary type"
                    class="w-full"
                  />
                </UFormField>
                <UFormField label="Enneagram Type">
                  <USelect
                    v-model="form.enneagram_type"
                    :items="enneagramTypes"
                    placeholder="Type"
                    aria-label="Enneagram type"
                    class="w-full"
                  />
                </UFormField>
              </div>
              <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
                <UFormField label="Enneagram Wing (1-9)">
                  <UInput
                    v-model="form.enneagram_wing"
                    type="number"
                    :min="1"
                    :max="9"
                    placeholder="e.g. 4"
                    aria-label="Enneagram wing"
                    class="w-full"
                  />
                </UFormField>
              </div>
            </fieldset>

            <!-- Big Five -->
            <fieldset>
              <legend class="text-xs font-bold uppercase tracking-widest text-muted mb-4">Big Five / OCEAN (0-100)</legend>
              <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
                <UFormField label="Openness">
                  <UInput
                    v-model.number="form.big_five_o"
                    type="number"
                    :min="0"
                    :max="100"
                    aria-label="Openness score"
                    class="w-full"
                  />
                </UFormField>
                <UFormField label="Conscientiousness">
                  <UInput
                    v-model.number="form.big_five_c"
                    type="number"
                    :min="0"
                    :max="100"
                    aria-label="Conscientiousness score"
                    class="w-full"
                  />
                </UFormField>
                <UFormField label="Extraversion">
                  <UInput
                    v-model.number="form.big_five_e"
                    type="number"
                    :min="0"
                    :max="100"
                    aria-label="Extraversion score"
                    class="w-full"
                  />
                </UFormField>
                <UFormField label="Agreeableness">
                  <UInput
                    v-model.number="form.big_five_a"
                    type="number"
                    :min="0"
                    :max="100"
                    aria-label="Agreeableness score"
                    class="w-full"
                  />
                </UFormField>
                <UFormField label="Neuroticism">
                  <UInput
                    v-model.number="form.big_five_n"
                    type="number"
                    :min="0"
                    :max="100"
                    aria-label="Neuroticism score"
                    class="w-full"
                  />
                </UFormField>
              </div>
            </fieldset>

            <!-- Knowledge & Communication -->
            <fieldset>
              <legend class="text-xs font-bold uppercase tracking-widest text-muted mb-4">Knowledge & Communication</legend>
              <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <UFormField label="Mental Models" hint="Comma-separated">
                  <UInput
                    v-model="form.mental_models"
                    placeholder="e.g. Grand Slam Offer, Value Equation"
                    aria-label="Mental models, comma-separated"
                    class="w-full"
                  />
                </UFormField>
                <UFormField label="Expertise Domains" hint="Comma-separated">
                  <UInput
                    v-model="form.expertise_domains"
                    placeholder="e.g. business strategy, offer creation"
                    aria-label="Expertise domains, comma-separated"
                    class="w-full"
                  />
                </UFormField>
                <UFormField label="Frameworks" hint="Comma-separated">
                  <UInput
                    v-model="form.frameworks"
                    placeholder="e.g. $100M Offers, Value Equation"
                    aria-label="Frameworks, comma-separated"
                    class="w-full"
                  />
                </UFormField>
                <UFormField label="Communication Tone">
                  <UInput
                    v-model="form.communication_tone"
                    placeholder="e.g. direct, high-energy"
                    aria-label="Communication tone"
                    class="w-full"
                  />
                </UFormField>
              </div>
            </fieldset>

            <!-- Submit -->
            <UButton
              type="submit"
              label="Create Persona"
              icon="i-lucide-sparkles"
              size="lg"
              block
              :loading="creating"
              :disabled="!form.name.trim()"
            />
          </form>
        </UCard>

        <!-- Empty state -->
        <div v-if="!personas.length && !showForm" class="flex flex-col items-center justify-center gap-6 py-20">
          <div class="rounded-full bg-muted/10 p-6">
            <UIcon name="i-lucide-users" class="size-12 text-muted" />
          </div>
          <div class="text-center space-y-2">
            <h3 class="text-base font-semibold">No personas yet</h3>
            <p class="text-sm text-muted max-w-sm">
              Personas define the behavioral DNA for your AI agents. Create one to get started.
            </p>
          </div>
          <UButton
            label="Create your first persona"
            icon="i-lucide-plus"
            size="lg"
            @click="showForm = true"
          />
        </div>

        <!-- Personas Grid -->
        <div v-if="personas.length" class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          <UCard
            v-for="persona in personas"
            :key="persona.id"
            class="group flex flex-col"
          >
            <div class="flex flex-col gap-3 flex-1">
              <!-- Header -->
              <div>
                <h3 class="text-base font-bold truncate">{{ persona.name }}</h3>
                <p v-if="persona.title" class="text-sm text-muted truncate mt-0.5">{{ persona.title }}</p>
                <p v-if="persona.source" class="text-xs text-muted/60 mt-1">
                  Source: {{ persona.source }}
                </p>
              </div>

              <!-- Tagline -->
              <p v-if="persona.tagline" class="text-sm text-muted italic leading-relaxed">
                "{{ persona.tagline }}"
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

              <!-- Expertise domains -->
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

              <!-- Actions -->
              <div class="pt-3 mt-auto border-t border-default space-y-3">
                <div class="flex gap-2">
                  <UButton
                    label="Clone to Agent"
                    icon="i-lucide-copy"
                    size="sm"
                    variant="solid"
                    class="flex-1"
                    @click="toggleClone(persona)"
                  />
                  <UButton
                    icon="i-lucide-trash-2"
                    size="sm"
                    variant="ghost"
                    color="error"
                    :loading="deleting === persona.id"
                    aria-label="Delete persona"
                    @click="deletePersona(persona)"
                  />
                </div>

                <!-- Inline clone expansion -->
                <div v-if="cloneExpandedId === persona.id" class="space-y-3 pt-2">
                  <UFormField label="Department" required>
                    <USelect
                      v-model="cloneDepartment"
                      :items="departmentOptions"
                      placeholder="Select department"
                      aria-label="Target department"
                      class="w-full"
                    />
                  </UFormField>
                  <UFormField label="Tier" required>
                    <USelect
                      v-model="cloneTier"
                      :items="tierOptions"
                      placeholder="Select tier"
                      aria-label="Agent tier"
                      class="w-full"
                    />
                  </UFormField>
                  <UButton
                    label="Confirm Clone"
                    icon="i-lucide-check"
                    size="sm"
                    block
                    :loading="cloning"
                    :disabled="!cloneDepartment || !cloneTier"
                    @click="cloneToAgent(persona)"
                  />
                </div>
              </div>
            </div>
          </UCard>
        </div>
      </template>
      </div>
    </template>
  </UDashboardPanel>
</template>
