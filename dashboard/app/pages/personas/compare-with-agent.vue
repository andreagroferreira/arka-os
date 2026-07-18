<script setup lang="ts">
// PR88a v3.23.0 — Compare a persona against one of its linked agents.
//
// Driven by `?persona=p&agent=a`. Useful to see how an agent diverged
// from the persona it was cloned from (or whose DNA inspired it).

const route = useRoute()
const { fetchApi } = useApi()

const personaId = computed(() => String(route.query.persona ?? ''))
const agentId = computed(() => String(route.query.agent ?? ''))

interface PersonaDetail {
  id: string
  name?: string
  title?: string
  source?: string
  mbti?: string
  disc?: { primary?: string, secondary?: string }
  enneagram?: { type?: number, wing?: number }
  big_five?: {
    openness?: number
    conscientiousness?: number
    extraversion?: number
    agreeableness?: number
    neuroticism?: number
  }
  mental_models?: string[]
  expertise_domains?: string[]
  frameworks?: string[]
  communication?: { tone?: string, vocabulary_level?: string, avoid?: string[] }
  bio_md?: string // PR94c v3.49.0
  // Present when the backend returns an error payload instead of a persona.
  error?: string
}

interface AgentDetail {
  id: string
  name?: string
  role?: string
  department?: string
  mbti?: string
  disc?: { primary?: string, secondary?: string }
  enneagram?: { type?: number, wing?: number }
  big_five?: PersonaDetail['big_five']
  mental_models?: { primary?: string[], secondary?: string[] }
  expertise?: { domains?: string[], frameworks?: string[] }
  communication?: { tone?: string, vocabulary_level?: string, avoid?: string[] }
  bio_md?: string // PR94c v3.49.0
  // Present when the backend returns an error payload instead of an agent.
  error?: string
}

const { data: persona, status: pStatus } = fetchApi<PersonaDetail>(
  () => personaId.value ? `/api/personas/${personaId.value}` : ''
)
const { data: agent, status: aStatus } = fetchApi<AgentDetail>(
  () => agentId.value ? `/api/agents/${agentId.value}` : ''
)

const loading = computed(() => pStatus.value === 'pending' || aStatus.value === 'pending')
const errorMsg = computed(() => {
  if (!personaId.value || !agentId.value) {
    return 'Pass ?persona=p&agent=a'
  }
  if (persona.value?.error) return `Persona: ${persona.value.error}`
  if (agent.value?.error) return `Agent: ${agent.value.error}`
  return null
})

function diffClass(left: unknown, right: unknown): string {
  return left !== right
    ? 'bg-yellow-500/10 border-yellow-500/30'
    : ''
}
function listDiffClass(left: unknown[] | undefined, right: unknown[] | undefined): string {
  const a = JSON.stringify([...(left ?? [])].sort())
  const b = JSON.stringify([...(right ?? [])].sort())
  return a !== b ? 'bg-yellow-500/10 border-yellow-500/30' : ''
}

const bigFiveKeys = ['openness', 'conscientiousness', 'extraversion', 'agreeableness', 'neuroticism'] as const
</script>

<template>
  <UDashboardPanel id="persona-vs-agent">
    <template #header>
      <UDashboardNavbar title="Persona vs Agent">
        <template #leading>
          <UButton
            v-if="personaId"
            icon="i-lucide-arrow-left"
            variant="ghost"
            size="sm"
            :to="`/personas/${personaId}`"
            aria-label="Back to persona"
          />
        </template>
        <template #trailing>
          <UBadge label="diverge view" variant="subtle" size="sm" />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div v-if="errorMsg" class="p-6 text-center text-sm text-error">
        {{ errorMsg }}
      </div>
      <div v-else-if="loading" class="p-6 text-center text-sm text-muted">
        <UIcon name="i-lucide-loader-2" class="size-4 animate-spin inline" /> Loading…
      </div>
      <div v-else-if="persona && agent" class="space-y-4 max-w-6xl">
        <section class="grid grid-cols-2 gap-3">
          <NuxtLink :to="`/personas/${persona.id}`" class="rounded-lg border border-default p-4 hover:border-primary/40">
            <p class="text-xs text-muted uppercase tracking-wide">Persona</p>
            <h2 class="text-xl font-bold">{{ persona.name }}</h2>
            <p class="text-sm text-muted">{{ persona.title || '—' }}</p>
          </NuxtLink>
          <NuxtLink :to="`/agents/${agent.id}`" class="rounded-lg border border-default p-4 hover:border-primary/40">
            <p class="text-xs text-muted uppercase tracking-wide">Agent</p>
            <h2 class="text-xl font-bold">{{ agent.name }}</h2>
            <p class="text-sm text-muted">{{ agent.role }} · {{ agent.department }}</p>
          </NuxtLink>
        </section>

        <h3 class="text-sm font-semibold uppercase tracking-wide text-muted pt-2">
          Behavioural DNA
        </h3>
        <div class="grid grid-cols-2 gap-3">
          <div :class="['rounded-lg border p-3', diffClass(persona.mbti, agent.mbti)]">
            <p class="text-xs text-muted">
              MBTI
            </p>
            <p class="text-lg font-mono font-bold">
              {{ persona.mbti ?? '—' }}
            </p>
          </div>
          <div :class="['rounded-lg border p-3', diffClass(persona.mbti, agent.mbti)]">
            <p class="text-xs text-muted">
              MBTI
            </p>
            <p class="text-lg font-mono font-bold">
              {{ agent.mbti ?? '—' }}
            </p>
          </div>
          <div :class="['rounded-lg border p-3', diffClass(`${persona.disc?.primary}/${persona.disc?.secondary}`, `${agent.disc?.primary}/${agent.disc?.secondary}`)]">
            <p class="text-xs text-muted">
              DISC
            </p>
            <p class="text-lg font-mono font-bold">
              {{ persona.disc?.primary ?? '?' }}/{{ persona.disc?.secondary ?? '?' }}
            </p>
          </div>
          <div :class="['rounded-lg border p-3', diffClass(`${persona.disc?.primary}/${persona.disc?.secondary}`, `${agent.disc?.primary}/${agent.disc?.secondary}`)]">
            <p class="text-xs text-muted">
              DISC
            </p>
            <p class="text-lg font-mono font-bold">
              {{ agent.disc?.primary ?? '?' }}/{{ agent.disc?.secondary ?? '?' }}
            </p>
          </div>
          <div :class="['rounded-lg border p-3', diffClass(`${persona.enneagram?.type}w${persona.enneagram?.wing}`, `${agent.enneagram?.type}w${agent.enneagram?.wing}`)]">
            <p class="text-xs text-muted">
              Enneagram
            </p>
            <p class="text-lg font-mono font-bold">
              {{ persona.enneagram?.type ?? '?' }}w{{ persona.enneagram?.wing ?? '?' }}
            </p>
          </div>
          <div :class="['rounded-lg border p-3', diffClass(`${persona.enneagram?.type}w${persona.enneagram?.wing}`, `${agent.enneagram?.type}w${agent.enneagram?.wing}`)]">
            <p class="text-xs text-muted">
              Enneagram
            </p>
            <p class="text-lg font-mono font-bold">
              {{ agent.enneagram?.type ?? '?' }}w{{ agent.enneagram?.wing ?? '?' }}
            </p>
          </div>
        </div>

        <h3 class="text-sm font-semibold uppercase tracking-wide text-muted pt-2">
          Big Five (OCEAN)
        </h3>
        <div class="space-y-1">
          <div v-for="k in bigFiveKeys" :key="k" class="grid grid-cols-2 gap-3">
            <div :class="['rounded-lg border p-2 flex items-center gap-3', diffClass(persona.big_five?.[k], agent.big_five?.[k])]">
              <span class="text-xs text-muted w-36 shrink-0 capitalize">{{ k }}</span>
              <span class="font-mono text-sm">{{ persona.big_five?.[k] ?? '—' }}</span>
            </div>
            <div :class="['rounded-lg border p-2 flex items-center gap-3', diffClass(persona.big_five?.[k], agent.big_five?.[k])]">
              <span class="text-xs text-muted w-36 shrink-0 capitalize">{{ k }}</span>
              <span class="font-mono text-sm">{{ agent.big_five?.[k] ?? '—' }}</span>
            </div>
          </div>
        </div>

        <h3 class="text-sm font-semibold uppercase tracking-wide text-muted pt-2">
          Expertise domains
        </h3>
        <div class="grid grid-cols-2 gap-3">
          <div :class="['rounded-lg border p-3', listDiffClass(persona.expertise_domains, agent.expertise?.domains)]">
            <ul class="list-disc list-inside text-sm space-y-1">
              <li v-for="d in persona.expertise_domains" :key="d">
                {{ d }}
              </li>
              <li v-if="!persona.expertise_domains?.length" class="list-none text-muted italic">
                none
              </li>
            </ul>
          </div>
          <div :class="['rounded-lg border p-3', listDiffClass(persona.expertise_domains, agent.expertise?.domains)]">
            <ul class="list-disc list-inside text-sm space-y-1">
              <li v-for="d in agent.expertise?.domains" :key="d">
                {{ d }}
              </li>
              <li v-if="!agent.expertise?.domains?.length" class="list-none text-muted italic">
                none
              </li>
            </ul>
          </div>
        </div>

        <h3 class="text-sm font-semibold uppercase tracking-wide text-muted pt-2">
          Frameworks
        </h3>
        <div class="grid grid-cols-2 gap-3">
          <div :class="['rounded-lg border p-3', listDiffClass(persona.frameworks, agent.expertise?.frameworks)]">
            <ul class="list-disc list-inside text-sm space-y-1">
              <li v-for="f in persona.frameworks" :key="f">
                {{ f }}
              </li>
              <li v-if="!persona.frameworks?.length" class="list-none text-muted italic">
                none
              </li>
            </ul>
          </div>
          <div :class="['rounded-lg border p-3', listDiffClass(persona.frameworks, agent.expertise?.frameworks)]">
            <ul class="list-disc list-inside text-sm space-y-1">
              <li v-for="f in agent.expertise?.frameworks" :key="f">
                {{ f }}
              </li>
              <li v-if="!agent.expertise?.frameworks?.length" class="list-none text-muted italic">
                none
              </li>
            </ul>
          </div>
        </div>

        <h3 class="text-sm font-semibold uppercase tracking-wide text-muted pt-2">
          Mental models
        </h3>
        <div class="grid grid-cols-2 gap-3">
          <div :class="['rounded-lg border p-3', listDiffClass(persona.mental_models, agent.mental_models?.primary)]">
            <p class="text-xs text-muted mb-2">
              Persona — flat list
            </p>
            <ul class="list-disc list-inside text-sm space-y-1">
              <li v-for="m in persona.mental_models" :key="m">
                {{ m }}
              </li>
              <li v-if="!persona.mental_models?.length" class="list-none text-muted italic">
                none
              </li>
            </ul>
          </div>
          <div :class="['rounded-lg border p-3', listDiffClass(persona.mental_models, agent.mental_models?.primary)]">
            <p class="text-xs text-muted mb-2">
              Agent — primary
            </p>
            <ul class="list-disc list-inside text-sm space-y-1">
              <li v-for="m in agent.mental_models?.primary" :key="m">
                {{ m }}
              </li>
              <li v-if="!agent.mental_models?.primary?.length" class="list-none text-muted italic">
                none
              </li>
            </ul>
          </div>
        </div>

        <!-- PR94c v3.49.0 — free-text diff blocks -->
        <h3 class="text-sm font-semibold uppercase tracking-wide text-muted pt-2">
          Bio (Markdown)
        </h3>
        <TextDiff
          :left="persona.bio_md || ''"
          :right="agent.bio_md || ''"
          :left-label="persona.name || persona.id"
          :right-label="agent.name || agent.id"
        />

        <h3 class="text-sm font-semibold uppercase tracking-wide text-muted pt-2">
          Communication tone
        </h3>
        <TextDiff
          :left="persona.communication?.tone || ''"
          :right="agent.communication?.tone || ''"
          :left-label="persona.name || persona.id"
          :right-label="agent.name || agent.id"
        />

        <p class="text-xs text-muted pt-4 italic">
          Cells with a yellow tint differ between persona and agent. Red lines
          were removed; green lines were added.
        </p>
      </div>
    </template>
  </UDashboardPanel>
</template>
