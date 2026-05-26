<script setup lang="ts">
// PR96c v3.57.0 — Compare two personas side-by-side.
//
// Driven by `?a=p1&b=p2`. Mirrors the agents/compare layout but
// adapts to the persona schema (flat mental_models, no department).

const route = useRoute()
const { fetchApi } = useApi()

const ids = computed<string[]>(() => {
  const raw = [route.query.a, route.query.b]
  return raw.map((v) => String(v ?? '').trim()).filter(Boolean).slice(0, 2)
})

interface PersonaDetail {
  id: string
  name?: string
  title?: string
  source?: string
  tagline?: string
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
  key_quotes?: string[]
  communication?: { tone?: string, vocabulary_level?: string, avoid?: string[] }
  bio_md?: string
  error?: string
}

const { data: a, status: aStatus } = fetchApi<PersonaDetail>(
  () => ids.value[0] ? `/api/personas/${ids.value[0]}` : '',
)
const { data: b, status: bStatus } = fetchApi<PersonaDetail>(
  () => ids.value[1] ? `/api/personas/${ids.value[1]}` : '',
)

const loading = computed(() => aStatus.value === 'pending' || bStatus.value === 'pending')
const errorMsg = computed(() => {
  if (ids.value.length < 2) return 'Pass two persona ids via ?a=p1&b=p2'
  if (a.value?.error) return `Left: ${a.value.error}`
  if (b.value?.error) return `Right: ${b.value.error}`
  return null
})

function diffClass(left: unknown, right: unknown): string {
  return left !== right ? 'bg-yellow-500/10 border-yellow-500/30' : ''
}
function listDiffClass(left: unknown[] | undefined, right: unknown[] | undefined): string {
  const x = JSON.stringify([...(left ?? [])].sort())
  const y = JSON.stringify([...(right ?? [])].sort())
  return x !== y ? 'bg-yellow-500/10 border-yellow-500/30' : ''
}

const bigFiveKeys = ['openness', 'conscientiousness', 'extraversion', 'agreeableness', 'neuroticism'] as const
</script>

<template>
  <UDashboardPanel id="personas-compare">
    <template #header>
      <UDashboardNavbar title="Compare personas">
        <template #leading>
          <UButton icon="i-lucide-arrow-left" variant="ghost" size="sm" to="/personas" aria-label="Back" />
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
          <NuxtLink :to="`/personas/${a.id}`" class="rounded-lg border border-default p-4 hover:border-primary/40">
            <p class="text-xs text-muted uppercase tracking-wide">Left</p>
            <h2 class="text-xl font-bold">{{ a.name }}</h2>
            <p class="text-sm text-muted">{{ a.title || '—' }}</p>
          </NuxtLink>
          <NuxtLink :to="`/personas/${b.id}`" class="rounded-lg border border-default p-4 hover:border-primary/40">
            <p class="text-xs text-muted uppercase tracking-wide">Right</p>
            <h2 class="text-xl font-bold">{{ b.name }}</h2>
            <p class="text-sm text-muted">{{ b.title || '—' }}</p>
          </NuxtLink>
        </section>

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
          <div :class="['rounded-lg border p-3', listDiffClass(a.expertise_domains, b.expertise_domains)]">
            <ul class="list-disc list-inside text-sm space-y-1">
              <li v-for="d in a.expertise_domains" :key="d">{{ d }}</li>
              <li v-if="!a.expertise_domains?.length" class="list-none text-muted italic">none</li>
            </ul>
          </div>
          <div :class="['rounded-lg border p-3', listDiffClass(a.expertise_domains, b.expertise_domains)]">
            <ul class="list-disc list-inside text-sm space-y-1">
              <li v-for="d in b.expertise_domains" :key="d">{{ d }}</li>
              <li v-if="!b.expertise_domains?.length" class="list-none text-muted italic">none</li>
            </ul>
          </div>
        </div>

        <h3 class="text-sm font-semibold uppercase tracking-wide text-muted pt-2">Mental models</h3>
        <div class="grid grid-cols-2 gap-3">
          <div :class="['rounded-lg border p-3', listDiffClass(a.mental_models, b.mental_models)]">
            <ul class="list-disc list-inside text-sm space-y-1">
              <li v-for="m in a.mental_models" :key="m">{{ m }}</li>
              <li v-if="!a.mental_models?.length" class="list-none text-muted italic">none</li>
            </ul>
          </div>
          <div :class="['rounded-lg border p-3', listDiffClass(a.mental_models, b.mental_models)]">
            <ul class="list-disc list-inside text-sm space-y-1">
              <li v-for="m in b.mental_models" :key="m">{{ m }}</li>
              <li v-if="!b.mental_models?.length" class="list-none text-muted italic">none</li>
            </ul>
          </div>
        </div>

        <h3 class="text-sm font-semibold uppercase tracking-wide text-muted pt-2">Frameworks</h3>
        <div class="grid grid-cols-2 gap-3">
          <div :class="['rounded-lg border p-3', listDiffClass(a.frameworks, b.frameworks)]">
            <ul class="list-disc list-inside text-sm space-y-1">
              <li v-for="f in a.frameworks" :key="f">{{ f }}</li>
              <li v-if="!a.frameworks?.length" class="list-none text-muted italic">none</li>
            </ul>
          </div>
          <div :class="['rounded-lg border p-3', listDiffClass(a.frameworks, b.frameworks)]">
            <ul class="list-disc list-inside text-sm space-y-1">
              <li v-for="f in b.frameworks" :key="f">{{ f }}</li>
              <li v-if="!b.frameworks?.length" class="list-none text-muted italic">none</li>
            </ul>
          </div>
        </div>

        <h3 class="text-sm font-semibold uppercase tracking-wide text-muted pt-2">Bio (Markdown)</h3>
        <TextDiff
          :left="a.bio_md || ''"
          :right="b.bio_md || ''"
          :left-label="a.name || a.id"
          :right-label="b.name || b.id"
        />

        <h3 class="text-sm font-semibold uppercase tracking-wide text-muted pt-2">Communication tone</h3>
        <TextDiff
          :left="a.communication?.tone || ''"
          :right="b.communication?.tone || ''"
          :left-label="a.name || a.id"
          :right-label="b.name || b.id"
        />

        <p class="text-xs text-muted pt-4 italic">
          Yellow tint = different. Red removed, green added.
        </p>
      </div>
    </template>
  </UDashboardPanel>
</template>
