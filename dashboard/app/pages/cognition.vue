<script setup lang="ts">
// v3.72.0 — Cognition page: monitor what Dreaming has been learning.
// Read-only view over the insights the Cognitive Layer already writes to
// <vault>/Projects/ArkaOS/Dreams. Backend: /api/cognition/{insights,status}.

import { marked } from 'marked'

definePageMeta({ layout: 'default' })

interface Insight {
  date: string
  title: string
  confidence: string
  sources: string[]
  tags: string[]
  body: string
}
interface Status {
  today: number
  week: number
  total: number
  by_confidence: { high: number, medium: number, low: number }
  vault_configured: boolean
  last_date: string | null
}

const { apiBase } = useApi()

const days = ref(7)
const confidenceFilter = ref<'all' | 'high' | 'medium' | 'low'>('all')
const tagFilter = ref('')
const insights = ref<Insight[]>([])
const status = ref<Status | null>(null)
const available = ref(true)
const loading = ref(true)
const expanded = ref<Set<string>>(new Set())

const windowOptions = [
  { label: 'Today', value: 1 },
  { label: 'Last 7 days', value: 7 },
  { label: 'Last 30 days', value: 30 }
]
const confidenceOptions = [
  { label: 'All confidence', value: 'all' },
  { label: 'High', value: 'high' },
  { label: 'Medium', value: 'medium' },
  { label: 'Low', value: 'low' }
]

async function refresh() {
  loading.value = true
  try {
    const [s, i] = await Promise.all([
      $fetch<Status>(`${apiBase}/api/cognition/status`),
      $fetch<{ insights: Insight[], available: boolean }>(
        `${apiBase}/api/cognition/insights?days=${days.value}`
      )
    ])
    status.value = s
    insights.value = i.insights
    available.value = i.available
  } catch {
    available.value = false
  } finally {
    loading.value = false
  }
}

onMounted(refresh)
// Reset the tag filter when the window changes — a tag may not exist in the
// new window, which would otherwise strand the user on an empty result.
watch(days, () => {
  tagFilter.value = ''
  refresh()
})

const allTags = computed(() => {
  const set = new Set<string>()
  for (const i of insights.value) for (const t of i.tags) set.add(t)
  return [...set].sort()
})

const filtered = computed(() => insights.value.filter((i) => {
  if (confidenceFilter.value !== 'all' && i.confidence !== confidenceFilter.value) return false
  if (tagFilter.value && !i.tags.includes(tagFilter.value)) return false
  return true
}))

function confidenceColor(c: string): 'success' | 'warning' | 'neutral' {
  if (c === 'high') return 'success'
  if (c === 'low') return 'neutral'
  return 'warning'
}

function toggle(key: string) {
  const next = new Set(expanded.value)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  expanded.value = next
}

function renderBody(body: string): string {
  if (!body) return ''
  try {
    return marked.parse(body, { async: false }) as string
  } catch {
    return body
  }
}

const isActive = computed(() => {
  if (!status.value?.last_date) return false
  const last = new Date(status.value.last_date + 'T00:00:00Z').getTime()
  return Date.now() - last < 3 * 86_400_000
})
</script>

<template>
  <UDashboardPanel id="cognition">
    <template #header>
      <UDashboardNavbar title="Dreaming">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <UBadge
            :color="isActive ? 'success' : 'neutral'"
            variant="soft"
            size="sm"
          >
            <UIcon
              :name="isActive ? 'i-lucide-activity' : 'i-lucide-moon'"
              class="size-3 mr-1"
            />
            {{ isActive ? 'Active' : 'Idle' }}
            <span v-if="status?.last_date" class="ml-1 opacity-70">· {{ status.last_date }}</span>
          </UBadge>
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="flex flex-col gap-4 p-4">
        <p class="text-sm text-muted -mt-1">
          What the Cognitive Layer has been learning — insights surfaced by
          Dreaming from your vault and sessions.
        </p>

        <!-- Stats -->
        <div v-if="status?.vault_configured" class="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div class="rounded-lg border border-default bg-elevated/10 p-3">
            <div class="text-2xl font-semibold tabular-nums">
              {{ status.today }}
            </div>
            <div class="text-xs text-muted">
              today
            </div>
          </div>
          <div class="rounded-lg border border-default bg-elevated/10 p-3">
            <div class="text-2xl font-semibold tabular-nums">
              {{ status.week }}
            </div>
            <div class="text-xs text-muted">
              last 7 days
            </div>
          </div>
          <div class="rounded-lg border border-default bg-elevated/10 p-3">
            <div class="text-2xl font-semibold tabular-nums">
              {{ status.total }}
            </div>
            <div class="text-xs text-muted">
              total insights
            </div>
          </div>
          <div class="rounded-lg border border-default bg-elevated/10 p-3 flex flex-col justify-center gap-1">
            <div class="flex items-center gap-2 text-xs">
              <UBadge color="success" variant="soft" size="xs">
                high {{ status.by_confidence.high }}
              </UBadge>
              <UBadge color="warning" variant="soft" size="xs">
                med {{ status.by_confidence.medium }}
              </UBadge>
              <UBadge color="neutral" variant="soft" size="xs">
                low {{ status.by_confidence.low }}
              </UBadge>
            </div>
          </div>
        </div>

        <!-- Filters -->
        <div class="flex flex-wrap items-center gap-2">
          <USelect
            v-model="days"
            :items="windowOptions"
            size="sm"
            class="w-40"
          />
          <USelect
            v-model="confidenceFilter"
            :items="confidenceOptions"
            size="sm"
            class="w-44"
          />
          <USelect
            v-if="allTags.length"
            v-model="tagFilter"
            :items="[{ label: 'All tags', value: '' }, ...allTags.map(t => ({ label: '#' + t, value: t }))]"
            size="sm"
            class="w-40"
          />
          <UButton
            size="sm"
            variant="ghost"
            icon="i-lucide-refresh-cw"
            :loading="loading"
            @click="refresh"
          >
            Refresh
          </UButton>
        </div>

        <!-- Feed -->
        <div v-if="loading" class="text-sm text-muted py-8 text-center">
          <UIcon name="i-lucide-loader" class="animate-spin size-5 mx-auto mb-2" />
          Loading insights…
        </div>
        <div
          v-else-if="!available || !status?.vault_configured"
          class="rounded-lg border border-dashed border-default p-10 text-center text-muted"
        >
          <UIcon name="i-lucide-moon-star" class="size-8 mx-auto mb-3 opacity-40" />
          <p class="text-sm">
            No vault connected, or Dreaming hasn't run yet.
          </p>
          <p class="text-xs mt-1 opacity-70">
            Configure a vault and let the Cognitive Layer dream — insights show up here.
          </p>
        </div>
        <div
          v-else-if="filtered.length === 0"
          class="rounded-lg border border-dashed border-default p-10 text-center text-muted"
        >
          <UIcon name="i-lucide-search-x" class="size-7 mx-auto mb-3 opacity-40" />
          <p class="text-sm">
            No insights match these filters.
          </p>
        </div>
        <ul v-else class="flex flex-col gap-3">
          <li
            v-for="(ins, idx) in filtered"
            :key="`${ins.date}-${idx}`"
            class="rounded-lg border border-default bg-elevated/10 overflow-hidden"
          >
            <button
              class="w-full flex items-start gap-3 p-3 text-left hover:bg-elevated/20 transition-colors"
              @click="toggle(`${ins.date}-${idx}`)"
            >
              <UBadge
                :color="confidenceColor(ins.confidence)"
                variant="soft"
                size="xs"
                class="mt-0.5 shrink-0 uppercase"
              >
                {{ ins.confidence }}
              </UBadge>
              <div class="flex-1 min-w-0">
                <div class="font-medium truncate">
                  {{ ins.title }}
                </div>
                <div class="flex items-center gap-2 mt-1 flex-wrap">
                  <span class="text-xs text-muted tabular-nums">{{ ins.date }}</span>
                  <UBadge
                    v-for="t in ins.tags"
                    :key="t"
                    variant="subtle"
                    size="xs"
                  >
                    #{{ t }}
                  </UBadge>
                </div>
              </div>
              <UIcon
                :name="expanded.has(`${ins.date}-${idx}`) ? 'i-lucide-chevron-up' : 'i-lucide-chevron-down'"
                class="size-4 shrink-0 text-muted mt-0.5"
              />
            </button>
            <div v-if="expanded.has(`${ins.date}-${idx}`)" class="px-3 pb-3 border-t border-default/60 pt-3">
              <!-- Trusted content: the operator's own Dreaming output from
                   their local vault, served over the localhost-only API —
                   same trust boundary as the persona bio renderer. -->
              <!-- eslint-disable-next-line vue/no-v-html -->
              <div class="prose prose-sm dark:prose-invert max-w-none text-sm" v-html="renderBody(ins.body)" />
              <div v-if="ins.sources.length" class="flex items-center gap-1.5 flex-wrap mt-3 pt-2 border-t border-default/40">
                <span class="text-[11px] text-muted">sources:</span>
                <UBadge
                  v-for="s in ins.sources"
                  :key="s"
                  variant="subtle"
                  size="xs"
                  color="info"
                >
                  {{ s }}
                </UBadge>
              </div>
            </div>
          </li>
        </ul>
      </div>
    </template>
  </UDashboardPanel>
</template>
