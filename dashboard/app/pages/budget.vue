<script setup lang="ts">
// PR65 v2.82.0 — Budget rebuild backed by the PR47 LLM cost telemetry.
//
// The legacy /api/budget endpoint surfaces tokens-only ops counts. PR65
// adds /api/llm-costs (full PR47 CostSummary) and /api/llm-costs/trend
// (daily rollups), so this page can now show real cost USD by
// provider / model / category plus a 7-day spend chart.

interface BreakdownRow {
  total_cost_usd: number | null
  any_cost_known?: boolean
  total_tokens_in: number
  total_tokens_out: number
  total_cached_tokens: number
  call_count: number
  cache_hit_rate: number
}

interface CostSummary {
  period: string
  total_cost_usd: number | null
  total_tokens_in: number
  total_tokens_out: number
  total_cached_tokens: number
  cache_hit_rate: number
  call_count: number
  by_provider: Record<string, BreakdownRow>
  by_model: Record<string, BreakdownRow>
  by_category: Record<string, BreakdownRow>
  by_session: Array<{
    session_id: string
    call_count: number
    total_tokens_in: number
    total_tokens_out: number
    total_cost_usd: number | null
  }>
  advisories: string[]
  corrupt_line_count: number
}

interface TrendDay {
  date: string
  cost_usd: number | null
  tokens_in: number
  tokens_out: number
  call_count: number
}

interface TrendResponse {
  days: TrendDay[]
  period_days: number
}

type Period = 'today' | 'week' | 'month' | 'all'

const { fetchApi } = useApi()
const period = ref<Period>('today')

const periodOptions: { label: string; value: Period }[] = [
  { label: 'Today', value: 'today' },
  { label: '7 days', value: 'week' },
  { label: '30 days', value: 'month' },
  { label: 'All time', value: 'all' },
]

const {
  data: costs,
  status,
  error,
  refresh,
} = fetchApi<CostSummary>(
  '/api/llm-costs',
  { query: computed(() => ({ period: period.value })) },
)

const {
  data: trend,
  refresh: refreshTrend,
} = fetchApi<TrendResponse>('/api/llm-costs/trend?days=7')

watch(period, async () => {
  await refresh()
})

// ─── View tabs ───────────────────────────────────────────────────────────

type View = 'category' | 'provider' | 'model'

const view = ref<View>('category')

const viewTabs = [
  { label: 'By category', value: 'category' as const },
  { label: 'By provider', value: 'provider' as const },
  { label: 'By model', value: 'model' as const },
]

const breakdownRows = computed<Array<[string, BreakdownRow]>>(() => {
  const source = (() => {
    switch (view.value) {
      case 'category': return costs.value?.by_category ?? {}
      case 'provider': return costs.value?.by_provider ?? {}
      case 'model':    return costs.value?.by_model    ?? {}
    }
  })()
  return Object.entries(source).sort((a, b) => {
    const ca = a[1].total_cost_usd ?? 0
    const cb = b[1].total_cost_usd ?? 0
    return cb - ca
  })
})

const viewEmpty = computed(() =>
  breakdownRows.value.length === 0
  || (
    view.value === 'category'
    && breakdownRows.value.length === 1
    && breakdownRows.value[0]?.[0] === ''
  ),
)

const maxCostForBar = computed(() => {
  const max = breakdownRows.value.reduce(
    (acc, [, row]) => Math.max(acc, row.total_cost_usd ?? 0),
    0,
  )
  return max > 0 ? max : 1
})

function formatCost(value: number | null): string {
  if (value === null || value === undefined) return 'n/a'
  if (value === 0) return '$0'
  if (value < 0.01) return `$${value.toFixed(4)}`
  return `$${value.toFixed(2)}`
}

function formatTokens(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`
  return value.toString()
}

function formatLabel(key: string): string {
  if (!key) return '(base / uncategorised)'
  return key
}

// ─── Trend chart ────────────────────────────────────────────────────────

const maxTrendCost = computed(() => {
  if (!trend.value?.days?.length) return 1
  const max = trend.value.days.reduce(
    (acc, d) => Math.max(acc, d.cost_usd ?? 0),
    0,
  )
  return max > 0 ? max : 1
})

function trendBarHeight(day: TrendDay): string {
  const cost = day.cost_usd ?? 0
  const percent = Math.min(100, (cost / maxTrendCost.value) * 100)
  return `${Math.max(percent, day.call_count > 0 ? 4 : 0)}%`
}

function trendDayLabel(iso: string): string {
  try {
    const d = new Date(iso + 'T00:00:00Z')
    return new Intl.DateTimeFormat('en-US', {
      weekday: 'short',
    }).format(d)
  } catch {
    return iso
  }
}

async function refreshAll() {
  await Promise.all([refresh(), refreshTrend()])
}
</script>

<template>
  <UDashboardPanel id="budget">
    <template #header>
      <UDashboardNavbar title="Usage &amp; Budget">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <USelect
            v-model="period"
            :items="periodOptions"
            size="sm"
            class="w-32"
          />
          <UButton
            label="Refresh"
            variant="ghost"
            icon="i-lucide-refresh-cw"
            size="sm"
            class="ml-2"
            @click="refreshAll"
          />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <DashboardState
        :status="status"
        :error="error"
        loading-label="Loading budget"
        :on-retry="() => refreshAll()"
      >
        <div class="space-y-6">
          <!-- Top-line summary -->
          <UCard>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <p class="text-xs font-semibold text-muted uppercase tracking-wider mb-1">
                  Total cost
                </p>
                <p class="text-2xl font-bold">
                  {{ formatCost(costs?.total_cost_usd ?? null) }}
                </p>
              </div>
              <div>
                <p class="text-xs font-semibold text-muted uppercase tracking-wider mb-1">
                  Calls
                </p>
                <p class="text-2xl font-bold">{{ costs?.call_count ?? 0 }}</p>
              </div>
              <div>
                <p class="text-xs font-semibold text-muted uppercase tracking-wider mb-1">
                  Tokens in / out
                </p>
                <p class="text-lg font-semibold">
                  {{ formatTokens(costs?.total_tokens_in ?? 0) }} /
                  {{ formatTokens(costs?.total_tokens_out ?? 0) }}
                </p>
              </div>
              <div>
                <p class="text-xs font-semibold text-muted uppercase tracking-wider mb-1">
                  Cache hit rate
                </p>
                <p class="text-2xl font-bold">
                  {{ ((costs?.cache_hit_rate ?? 0) * 100).toFixed(1) }}%
                </p>
              </div>
            </div>
          </UCard>

          <!-- 7-day trend (inline bar chart) -->
          <UCard v-if="trend?.days?.length">
            <div>
              <p class="text-xs font-semibold text-muted uppercase tracking-wider mb-4">
                Last 7 days
              </p>
              <div class="flex items-end gap-2 h-32">
                <div
                  v-for="day in trend.days"
                  :key="day.date"
                  class="flex-1 flex flex-col items-center gap-1"
                  :title="`${day.date} — ${formatCost(day.cost_usd)} (${day.call_count} calls)`"
                >
                  <div class="w-full h-full flex items-end">
                    <div
                      class="w-full rounded-t transition-none"
                      :class="day.call_count > 0 ? 'bg-primary' : 'bg-muted/20'"
                      :style="{ height: trendBarHeight(day) }"
                    />
                  </div>
                  <span class="text-xs text-muted">{{ trendDayLabel(day.date) }}</span>
                </div>
              </div>
            </div>
          </UCard>

          <!-- Advisories -->
          <UCard
            v-if="costs?.advisories?.length"
            class="border-yellow-500/30 bg-yellow-500/5"
          >
            <div class="flex items-start gap-3">
              <UIcon
                name="i-lucide-alert-triangle"
                class="size-5 text-yellow-500 mt-0.5 shrink-0"
              />
              <div>
                <p class="text-sm font-semibold text-yellow-500 mb-2">
                  Advisories
                </p>
                <ul class="space-y-1 text-sm">
                  <li v-for="a in costs.advisories" :key="a">
                    {{ a }}
                  </li>
                </ul>
              </div>
            </div>
          </UCard>

          <!-- Breakdown views -->
          <div>
            <UTabs
              v-model="view"
              :items="viewTabs"
              :ui="{ list: 'mb-4' }"
            />

            <div v-if="viewEmpty" class="flex flex-col items-center justify-center gap-3 py-12 rounded-lg border border-default">
              <UIcon name="i-lucide-bar-chart-3" class="size-10 text-muted" />
              <p class="text-sm text-muted">
                {{ view === 'category'
                  ? "No category-aware spend yet. Orchestration layers can set ARKA_CALL_CATEGORY before LLM calls to attribute spend (PR60)."
                  : "No spend data yet for this view." }}
              </p>
            </div>

            <div v-else class="space-y-2">
              <div
                v-for="[key, row] in breakdownRows"
                :key="key"
                class="flex items-center gap-3 rounded-lg border border-default p-3"
              >
                <span class="w-48 text-sm font-mono truncate" :title="formatLabel(key)">
                  {{ formatLabel(key) }}
                </span>
                <div class="flex-1 h-3 rounded-full bg-muted/10 overflow-hidden">
                  <div
                    class="h-3 rounded-full bg-primary"
                    :style="{
                      width: `${Math.max(2, ((row.total_cost_usd ?? 0) / maxCostForBar) * 100)}%`,
                    }"
                  />
                </div>
                <span class="w-20 text-right text-sm font-mono">
                  {{ formatCost(row.total_cost_usd) }}
                </span>
                <span class="w-16 text-right text-xs text-muted">
                  {{ row.call_count }} calls
                </span>
                <span class="w-20 text-right text-xs text-muted">
                  {{ formatTokens(row.total_tokens_in + row.total_tokens_out) }} tok
                </span>
              </div>
            </div>
          </div>

          <!-- Top sessions -->
          <UCard v-if="costs?.by_session?.length">
            <p class="text-xs font-semibold text-muted uppercase tracking-wider mb-3">
              Top sessions
            </p>
            <div class="space-y-2">
              <div
                v-for="s in costs.by_session"
                :key="s.session_id || 'unknown'"
                class="flex items-center gap-3 text-sm"
              >
                <span class="w-48 font-mono text-xs truncate">
                  {{ s.session_id || '(unknown)' }}
                </span>
                <span class="flex-1 text-muted">{{ s.call_count }} calls</span>
                <span class="w-20 text-right font-mono">{{ formatCost(s.total_cost_usd) }}</span>
                <span class="w-20 text-right text-xs text-muted">
                  {{ formatTokens(s.total_tokens_in + s.total_tokens_out) }} tok
                </span>
              </div>
            </div>
          </UCard>

          <!-- Note for corrupt rows -->
          <p
            v-if="costs?.corrupt_line_count"
            class="text-xs text-muted text-center"
          >
            Skipped {{ costs.corrupt_line_count }} corrupt JSONL line(s) in telemetry.
          </p>
        </div>
      </DashboardState>
    </template>
  </UDashboardPanel>
</template>
