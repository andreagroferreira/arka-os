<script setup lang="ts">
// PR96c v3.57.0 — Compare two personas side-by-side.
// v3.70.8 — picker UI when query params are missing (was blank before).
//
// Driven by `?a=p1&b=p2`. The page renders pickers when either id is
// missing so the operator can land on /personas/compare directly.

const route = useRoute()
const router = useRouter()
const { fetchApi } = useApi()

interface PersonaSummary {
  id: string
  name: string
  title?: string
}

const { data: listData, status: listStatus } = fetchApi<{ personas: PersonaSummary[] }>(
  '/api/personas'
)
const personaList = computed(() => listData.value?.personas ?? [])
const loadingList = computed(() => listStatus.value === 'pending')

const personaOptions = computed(() =>
  personaList.value.map(p => ({
    label: p.name + (p.title ? ` — ${p.title}` : ''),
    value: p.id
  }))
)

const leftId = computed(() => String(route.query.a ?? '').trim())
const rightId = computed(() => String(route.query.b ?? '').trim())

function setLeft(id: string) {
  router.replace({ query: { ...route.query, a: id || undefined } })
}
function setRight(id: string) {
  router.replace({ query: { ...route.query, b: id || undefined } })
}
function swapSides() {
  router.replace({
    query: { ...route.query, a: rightId.value || undefined, b: leftId.value || undefined }
  })
}

const ids = computed<string[]>(() =>
  [leftId.value, rightId.value].filter(Boolean).slice(0, 2)
)

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
  () => ids.value[0] ? `/api/personas/${ids.value[0]}` : ''
)
const { data: b, status: bStatus } = fetchApi<PersonaDetail>(
  () => ids.value[1] ? `/api/personas/${ids.value[1]}` : ''
)

const loading = computed(() => aStatus.value === 'pending' || bStatus.value === 'pending')
const errorMsg = computed(() => {
  if (a.value?.error) return `Left: ${a.value.error}`
  if (b.value?.error) return `Right: ${b.value.error}`
  return null
})
const bothSelected = computed(() => leftId.value && rightId.value)

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
          <UButton
            icon="i-lucide-arrow-left"
            variant="ghost"
            size="sm"
            to="/personas"
            aria-label="Back"
          />
        </template>
        <template #trailing>
          <UBadge label="2-way" variant="subtle" size="sm" />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="p-4 space-y-4">
        <!-- Empty state: no personas at all -->
        <div
          v-if="!loadingList && personaList.length === 0"
          class="rounded-xl border border-default p-12 text-center"
        >
          <UIcon name="i-lucide-users" class="size-10 mx-auto mb-3 text-muted opacity-50" />
          <p class="text-default font-medium">
            No personas to compare yet.
          </p>
          <p class="text-sm text-muted mt-1">
            Create at least two personas before using the compare view.
          </p>
          <UButton to="/personas" class="mt-4" icon="i-lucide-arrow-left">
            Back to personas
          </UButton>
        </div>

        <!-- Empty state: only 1 persona -->
        <div
          v-else-if="!loadingList && personaList.length < 2"
          class="rounded-xl border border-default p-12 text-center"
        >
          <UIcon name="i-lucide-users" class="size-10 mx-auto mb-3 text-muted opacity-50" />
          <p class="text-default font-medium">
            You need at least 2 personas.
          </p>
          <p class="text-sm text-muted mt-1">
            Currently {{ personaList.length }} persona in the system.
          </p>
          <UButton to="/personas/new" class="mt-4" icon="i-lucide-plus">
            Create another persona
          </UButton>
        </div>

        <!-- Pickers (always visible when we have 2+ personas) -->
        <div v-else class="space-y-4">
          <div class="grid grid-cols-[1fr_auto_1fr] gap-2 items-end">
            <div>
              <label class="text-xs text-muted uppercase tracking-wide mb-1 block">Left</label>
              <USelectMenu
                :model-value="leftId"
                :items="personaOptions"
                placeholder="Pick a persona…"
                value-key="value"
                class="w-full"
                @update:model-value="(v: any) => setLeft(typeof v === 'string' ? v : (v?.value ?? ''))"
              />
            </div>
            <UButton
              icon="i-lucide-arrow-left-right"
              variant="ghost"
              size="sm"
              class="mb-0.5"
              :disabled="!bothSelected"
              title="Swap sides"
              @click="swapSides"
            />
            <div>
              <label class="text-xs text-muted uppercase tracking-wide mb-1 block">Right</label>
              <USelectMenu
                :model-value="rightId"
                :items="personaOptions"
                placeholder="Pick a persona…"
                value-key="value"
                class="w-full"
                @update:model-value="(v: any) => setRight(typeof v === 'string' ? v : (v?.value ?? ''))"
              />
            </div>
          </div>

          <!-- Hint when not both selected -->
          <div
            v-if="!bothSelected"
            class="rounded-xl border border-default border-dashed p-10 text-center text-sm text-muted"
          >
            <UIcon name="i-lucide-columns-2" class="size-7 mx-auto mb-2 opacity-50" />
            Pick two personas above to see the side-by-side diff.
          </div>

          <!-- Error from detail fetch -->
          <div v-else-if="errorMsg" class="p-4 text-sm text-error border border-error/30 rounded-lg">
            {{ errorMsg }}
          </div>

          <!-- Loading detail -->
          <div v-else-if="loading" class="p-6 text-center text-sm text-muted">
            <UIcon name="i-lucide-loader-2" class="size-4 animate-spin inline mr-2" />
            Loading personas…
          </div>

          <!-- Comparison content -->
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

            <h3 class="text-sm font-semibold uppercase tracking-wide text-muted pt-2">
              Behavioural DNA
            </h3>
            <div class="grid grid-cols-2 gap-3">
              <div :class="['rounded-lg border p-3', diffClass(a.mbti, b.mbti)]">
                <p class="text-xs text-muted">
                  MBTI
                </p>
                <p class="text-lg font-mono font-bold">
                  {{ a.mbti ?? '—' }}
                </p>
              </div>
              <div :class="['rounded-lg border p-3', diffClass(a.mbti, b.mbti)]">
                <p class="text-xs text-muted">
                  MBTI
                </p>
                <p class="text-lg font-mono font-bold">
                  {{ b.mbti ?? '—' }}
                </p>
              </div>
              <div :class="['rounded-lg border p-3', diffClass(`${a.disc?.primary}/${a.disc?.secondary}`, `${b.disc?.primary}/${b.disc?.secondary}`)]">
                <p class="text-xs text-muted">
                  DISC
                </p>
                <p class="text-lg font-mono font-bold">
                  {{ a.disc?.primary ?? '?' }}/{{ a.disc?.secondary ?? '?' }}
                </p>
              </div>
              <div :class="['rounded-lg border p-3', diffClass(`${a.disc?.primary}/${a.disc?.secondary}`, `${b.disc?.primary}/${b.disc?.secondary}`)]">
                <p class="text-xs text-muted">
                  DISC
                </p>
                <p class="text-lg font-mono font-bold">
                  {{ b.disc?.primary ?? '?' }}/{{ b.disc?.secondary ?? '?' }}
                </p>
              </div>
              <div :class="['rounded-lg border p-3', diffClass(`${a.enneagram?.type}w${a.enneagram?.wing}`, `${b.enneagram?.type}w${b.enneagram?.wing}`)]">
                <p class="text-xs text-muted">
                  Enneagram
                </p>
                <p class="text-lg font-mono font-bold">
                  {{ a.enneagram?.type ?? '?' }}w{{ a.enneagram?.wing ?? '?' }}
                </p>
              </div>
              <div :class="['rounded-lg border p-3', diffClass(`${a.enneagram?.type}w${a.enneagram?.wing}`, `${b.enneagram?.type}w${b.enneagram?.wing}`)]">
                <p class="text-xs text-muted">
                  Enneagram
                </p>
                <p class="text-lg font-mono font-bold">
                  {{ b.enneagram?.type ?? '?' }}w{{ b.enneagram?.wing ?? '?' }}
                </p>
              </div>
            </div>

            <h3 class="text-sm font-semibold uppercase tracking-wide text-muted pt-2">
              Big Five (OCEAN)
            </h3>
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

            <h3 class="text-sm font-semibold uppercase tracking-wide text-muted pt-2">
              Expertise domains
            </h3>
            <div class="grid grid-cols-2 gap-3">
              <div :class="['rounded-lg border p-3', listDiffClass(a.expertise_domains, b.expertise_domains)]">
                <ul class="list-disc list-inside text-sm space-y-1">
                  <li v-for="d in a.expertise_domains" :key="d">
                    {{ d }}
                  </li>
                  <li v-if="!a.expertise_domains?.length" class="list-none text-muted italic">
                    none
                  </li>
                </ul>
              </div>
              <div :class="['rounded-lg border p-3', listDiffClass(a.expertise_domains, b.expertise_domains)]">
                <ul class="list-disc list-inside text-sm space-y-1">
                  <li v-for="d in b.expertise_domains" :key="d">
                    {{ d }}
                  </li>
                  <li v-if="!b.expertise_domains?.length" class="list-none text-muted italic">
                    none
                  </li>
                </ul>
              </div>
            </div>

            <h3 class="text-sm font-semibold uppercase tracking-wide text-muted pt-2">
              Mental models
            </h3>
            <div class="grid grid-cols-2 gap-3">
              <div :class="['rounded-lg border p-3', listDiffClass(a.mental_models, b.mental_models)]">
                <ul class="list-disc list-inside text-sm space-y-1">
                  <li v-for="m in a.mental_models" :key="m">
                    {{ m }}
                  </li>
                  <li v-if="!a.mental_models?.length" class="list-none text-muted italic">
                    none
                  </li>
                </ul>
              </div>
              <div :class="['rounded-lg border p-3', listDiffClass(a.mental_models, b.mental_models)]">
                <ul class="list-disc list-inside text-sm space-y-1">
                  <li v-for="m in b.mental_models" :key="m">
                    {{ m }}
                  </li>
                  <li v-if="!b.mental_models?.length" class="list-none text-muted italic">
                    none
                  </li>
                </ul>
              </div>
            </div>

            <h3 class="text-sm font-semibold uppercase tracking-wide text-muted pt-2">
              Frameworks
            </h3>
            <div class="grid grid-cols-2 gap-3">
              <div :class="['rounded-lg border p-3', listDiffClass(a.frameworks, b.frameworks)]">
                <ul class="list-disc list-inside text-sm space-y-1">
                  <li v-for="f in a.frameworks" :key="f">
                    {{ f }}
                  </li>
                  <li v-if="!a.frameworks?.length" class="list-none text-muted italic">
                    none
                  </li>
                </ul>
              </div>
              <div :class="['rounded-lg border p-3', listDiffClass(a.frameworks, b.frameworks)]">
                <ul class="list-disc list-inside text-sm space-y-1">
                  <li v-for="f in b.frameworks" :key="f">
                    {{ f }}
                  </li>
                  <li v-if="!b.frameworks?.length" class="list-none text-muted italic">
                    none
                  </li>
                </ul>
              </div>
            </div>

            <h3 class="text-sm font-semibold uppercase tracking-wide text-muted pt-2">
              Bio (Markdown)
            </h3>
            <TextDiff
              :left="a.bio_md || ''"
              :right="b.bio_md || ''"
              :left-label="a.name || a.id"
              :right-label="b.name || b.id"
            />

            <h3 class="text-sm font-semibold uppercase tracking-wide text-muted pt-2">
              Communication tone
            </h3>
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
        </div>
      </div>
    </template>
  </UDashboardPanel>
</template>
