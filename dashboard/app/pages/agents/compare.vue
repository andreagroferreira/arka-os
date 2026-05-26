<script setup lang="ts">
// PR87c v3.21.0 — Compare two agents side-by-side.
//
// Driven by `?ids=a,b` query string. Reads both agent payloads via
// /api/agents/{id} and renders identity / DNA / knowledge / comms in
// two columns. Cells where the values differ get a subtle warning
// tint so the operator can spot deltas quickly.

const route = useRoute()
const { fetchApi } = useApi()

const ids = computed<string[]>(() => {
  const raw = route.query.ids
  const str = Array.isArray(raw) ? raw.join(',') : (raw ?? '')
  return String(str).split(',').map((s) => s.trim()).filter(Boolean).slice(0, 2)
})

interface AgentDetail {
  id: string
  name?: string
  role?: string
  department?: string
  tier?: number
  model?: string
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
  expertise?: { domains?: string[], frameworks?: string[], depth?: string, years_equivalent?: number }
  mental_models?: { primary?: string[], secondary?: string[] }
  communication?: {
    tone?: string
    vocabulary_level?: string
    preferred_format?: string
    language?: string
  }
}

const { data: a, status: aStatus } = fetchApi<AgentDetail>(
  () => ids.value[0] ? `/api/agents/${ids.value[0]}` : '',
)
const { data: b, status: bStatus } = fetchApi<AgentDetail>(
  () => ids.value[1] ? `/api/agents/${ids.value[1]}` : '',
)

const loading = computed(() => aStatus.value === 'pending' || bStatus.value === 'pending')
const errorMsg = computed(() => {
  if (ids.value.length < 2) return 'Pass two agent ids via ?ids=a,b'
  if (a.value && (a.value as any).error) return `Left agent: ${(a.value as any).error}`
  if (b.value && (b.value as any).error) return `Right agent: ${(b.value as any).error}`
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
  <UDashboardPanel id="agents-compare">
    <template #header>
      <UDashboardNavbar title="Compare agents">
        <template #leading>
          <UButton icon="i-lucide-arrow-left" variant="ghost" size="sm" to="/agents" aria-label="Back" />
        </template>
        <template #trailing>
          <UBadge label="2-way" variant="subtle" size="sm" />
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
      <div v-else-if="a && b" class="space-y-4 max-w-6xl">
        <section class="grid grid-cols-2 gap-3">
          <div class="rounded-lg border border-default p-4">
            <p class="text-xs text-muted">Left</p>
            <h2 class="text-xl font-bold">{{ a.name }}</h2>
            <p class="text-sm text-muted">{{ a.role }} · {{ a.department }}</p>
          </div>
          <div class="rounded-lg border border-default p-4">
            <p class="text-xs text-muted">Right</p>
            <h2 class="text-xl font-bold">{{ b.name }}</h2>
            <p class="text-sm text-muted">{{ b.role }} · {{ b.department }}</p>
          </div>
        </section>

        <h3 class="text-sm font-semibold uppercase tracking-wide text-muted pt-2">Identity</h3>
        <div class="grid grid-cols-2 gap-3">
          <div :class="['rounded-lg border p-3', diffClass(a.tier, b.tier)]">
            <p class="text-xs text-muted">Tier</p>
            <p class="text-sm font-mono">{{ a.tier ?? '—' }}</p>
          </div>
          <div :class="['rounded-lg border p-3', diffClass(a.tier, b.tier)]">
            <p class="text-xs text-muted">Tier</p>
            <p class="text-sm font-mono">{{ b.tier ?? '—' }}</p>
          </div>
          <div :class="['rounded-lg border p-3', diffClass(a.model, b.model)]">
            <p class="text-xs text-muted">Model</p>
            <p class="text-sm font-mono">{{ a.model ?? '—' }}</p>
          </div>
          <div :class="['rounded-lg border p-3', diffClass(a.model, b.model)]">
            <p class="text-xs text-muted">Model</p>
            <p class="text-sm font-mono">{{ b.model ?? '—' }}</p>
          </div>
        </div>

        <h3 class="text-sm font-semibold uppercase tracking-wide text-muted pt-2">Behavioural DNA</h3>
        <div class="grid grid-cols-2 gap-3">
          <div :class="['rounded-lg border p-3', diffClass(a.mbti, b.mbti)]">
            <p class="text-xs text-muted">MBTI</p>
            <p class="text-lg font-mono font-bold">{{ a.mbti ?? '—' }}</p>
          </div>
          <div :class="['rounded-lg border p-3', diffClass(a.mbti, b.mbti)]">
            <p class="text-xs text-muted">MBTI</p>
            <p class="text-lg font-mono font-bold">{{ b.mbti ?? '—' }}</p>
          </div>
          <div :class="['rounded-lg border p-3', diffClass(`${a.disc?.primary}/${a.disc?.secondary}`, `${b.disc?.primary}/${b.disc?.secondary}`)]">
            <p class="text-xs text-muted">DISC</p>
            <p class="text-lg font-mono font-bold">{{ a.disc?.primary ?? '?' }}/{{ a.disc?.secondary ?? '?' }}</p>
          </div>
          <div :class="['rounded-lg border p-3', diffClass(`${a.disc?.primary}/${a.disc?.secondary}`, `${b.disc?.primary}/${b.disc?.secondary}`)]">
            <p class="text-xs text-muted">DISC</p>
            <p class="text-lg font-mono font-bold">{{ b.disc?.primary ?? '?' }}/{{ b.disc?.secondary ?? '?' }}</p>
          </div>
          <div :class="['rounded-lg border p-3', diffClass(`${a.enneagram?.type}w${a.enneagram?.wing}`, `${b.enneagram?.type}w${b.enneagram?.wing}`)]">
            <p class="text-xs text-muted">Enneagram</p>
            <p class="text-lg font-mono font-bold">{{ a.enneagram?.type ?? '?' }}w{{ a.enneagram?.wing ?? '?' }}</p>
          </div>
          <div :class="['rounded-lg border p-3', diffClass(`${a.enneagram?.type}w${a.enneagram?.wing}`, `${b.enneagram?.type}w${b.enneagram?.wing}`)]">
            <p class="text-xs text-muted">Enneagram</p>
            <p class="text-lg font-mono font-bold">{{ b.enneagram?.type ?? '?' }}w{{ b.enneagram?.wing ?? '?' }}</p>
          </div>
        </div>

        <h3 class="text-sm font-semibold uppercase tracking-wide text-muted pt-2">Big Five (OCEAN)</h3>
        <div class="space-y-1">
          <div v-for="k in bigFiveKeys" :key="k" class="grid grid-cols-2 gap-3">
            <div :class="['rounded-lg border p-2 flex items-center gap-3', diffClass(a.big_five?.[k], b.big_five?.[k])]">
              <span class="text-xs text-muted w-36 shrink-0 capitalize">{{ k }}</span>
              <span class="font-mono text-sm">{{ a.big_five?.[k] ?? '—' }}</span>
            </div>
            <div :class="['rounded-lg border p-2 flex items-center gap-3', diffClass(a.big_five?.[k], b.big_five?.[k])]">
              <span class="text-xs text-muted w-36 shrink-0 capitalize">{{ k }}</span>
              <span class="font-mono text-sm">{{ b.big_five?.[k] ?? '—' }}</span>
            </div>
          </div>
        </div>

        <h3 class="text-sm font-semibold uppercase tracking-wide text-muted pt-2">Expertise domains</h3>
        <div class="grid grid-cols-2 gap-3">
          <div :class="['rounded-lg border p-3', listDiffClass(a.expertise?.domains, b.expertise?.domains)]">
            <ul class="list-disc list-inside text-sm space-y-1">
              <li v-for="d in a.expertise?.domains" :key="d">{{ d }}</li>
              <li v-if="!a.expertise?.domains?.length" class="list-none text-muted italic">none</li>
            </ul>
          </div>
          <div :class="['rounded-lg border p-3', listDiffClass(a.expertise?.domains, b.expertise?.domains)]">
            <ul class="list-disc list-inside text-sm space-y-1">
              <li v-for="d in b.expertise?.domains" :key="d">{{ d }}</li>
              <li v-if="!b.expertise?.domains?.length" class="list-none text-muted italic">none</li>
            </ul>
          </div>
        </div>

        <h3 class="text-sm font-semibold uppercase tracking-wide text-muted pt-2">Frameworks</h3>
        <div class="grid grid-cols-2 gap-3">
          <div :class="['rounded-lg border p-3', listDiffClass(a.expertise?.frameworks, b.expertise?.frameworks)]">
            <ul class="list-disc list-inside text-sm space-y-1">
              <li v-for="f in a.expertise?.frameworks" :key="f">{{ f }}</li>
              <li v-if="!a.expertise?.frameworks?.length" class="list-none text-muted italic">none</li>
            </ul>
          </div>
          <div :class="['rounded-lg border p-3', listDiffClass(a.expertise?.frameworks, b.expertise?.frameworks)]">
            <ul class="list-disc list-inside text-sm space-y-1">
              <li v-for="f in b.expertise?.frameworks" :key="f">{{ f }}</li>
              <li v-if="!b.expertise?.frameworks?.length" class="list-none text-muted italic">none</li>
            </ul>
          </div>
        </div>

        <h3 class="text-sm font-semibold uppercase tracking-wide text-muted pt-2">Mental models (primary)</h3>
        <div class="grid grid-cols-2 gap-3">
          <div :class="['rounded-lg border p-3', listDiffClass(a.mental_models?.primary, b.mental_models?.primary)]">
            <ul class="list-disc list-inside text-sm space-y-1">
              <li v-for="m in a.mental_models?.primary" :key="m">{{ m }}</li>
              <li v-if="!a.mental_models?.primary?.length" class="list-none text-muted italic">none</li>
            </ul>
          </div>
          <div :class="['rounded-lg border p-3', listDiffClass(a.mental_models?.primary, b.mental_models?.primary)]">
            <ul class="list-disc list-inside text-sm space-y-1">
              <li v-for="m in b.mental_models?.primary" :key="m">{{ m }}</li>
              <li v-if="!b.mental_models?.primary?.length" class="list-none text-muted italic">none</li>
            </ul>
          </div>
        </div>

        <p class="text-xs text-muted pt-4 italic">
          Cells with a yellow tint differ between the two agents.
        </p>
      </div>
    </template>
  </UDashboardPanel>
</template>
