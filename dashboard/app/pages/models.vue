<script setup lang="ts">
// Model Fabric (PR-C) — who runs what, what this machine offers, where
// tokens flow. Backed by /api/models, /api/models/role, /api/models/usage.

interface ResolvedRole {
  role: string
  provider: string
  model: string
  effort: string
  source: string
  description?: string
}

interface RuntimeModel {
  value: string
  label: string
  tier: string
  note: string
}

interface OllamaModel {
  name: string
  size_gb: number
  family: string
  parameter_size: string
}

interface ModelsOverview {
  source: string
  config_path: string
  roles: ResolvedRole[]
  providers: Record<string, { type: string }>
  aliases: Record<string, Record<string, string>>
  fusion: { judge: Record<string, string>, panel: Array<Record<string, string>> }
  runtime: { id: string, models: RuntimeModel[] }
  ollama: { installed: boolean, running: boolean, host: string, models: OllamaModel[] }
  keys: { openrouter: boolean, anthropic: boolean }
}

interface BreakdownRow {
  total_cost_usd: number | null
  total_tokens_in: number
  total_tokens_out: number
  call_count: number
}

interface UsageSummary {
  period: string
  call_count: number
  total_cost_usd: number | null
  total_tokens_in: number
  total_tokens_out: number
  total_cached_tokens: number
  by_model: Record<string, BreakdownRow>
  by_provider: Record<string, BreakdownRow>
}

type Period = 'today' | 'week' | 'month' | 'all'

const { fetchApi, apiBase } = useApi()
const toast = useToast()

const {
  data: overview,
  status,
  error,
  refresh
} = fetchApi<ModelsOverview>('/api/models')

const period = ref<Period>('week')
const periodOptions: { label: string, value: Period }[] = [
  { label: 'Today', value: 'today' },
  { label: '7 days', value: 'week' },
  { label: '30 days', value: 'month' },
  { label: 'All time', value: 'all' }
]
const { data: usage, refresh: refreshUsage } = fetchApi<UsageSummary>(
  '/api/models/usage',
  { query: computed(() => ({ period: period.value })) }
)
watch(period, () => refreshUsage())

// ─── Provider lanes (signature element: live availability strip) ────────

const QUALITY_ROLES = new Set(['design', 'review', 'architecture', 'strategy', 'quality_gate'])

const laneStyles: Record<string, { badge: string, dot: string }> = {
  runtime: { badge: 'text-primary bg-primary/10', dot: 'bg-primary' },
  ollama: { badge: 'text-amber-600 dark:text-amber-400 bg-amber-500/10', dot: 'bg-amber-500' },
  openrouter: { badge: 'text-violet-600 dark:text-violet-400 bg-violet-500/10', dot: 'bg-violet-500' },
  anthropic: { badge: 'text-sky-600 dark:text-sky-400 bg-sky-500/10', dot: 'bg-sky-500' }
}

function laneStyle(provider: string) {
  return laneStyles[provider] ?? { badge: 'text-muted bg-muted/10', dot: 'bg-muted' }
}

interface Lane {
  id: string
  label: string
  live: boolean
  detail: string
}

const lanes = computed<Lane[]>(() => {
  const o = overview.value
  if (!o) return []
  const ollama = o.ollama ?? { installed: false, running: false, models: [] }
  const keys = o.keys ?? { openrouter: false, anthropic: false }
  const ollamaDetail = ollama.running
    ? `${(ollama.models ?? []).length} local models`
    : ollama.installed ? 'installed, not running' : 'not installed'
  return [
    { id: 'runtime', label: 'Runtime', live: true, detail: 'active CLI session' },
    { id: 'ollama', label: 'Ollama', live: ollama.running, detail: ollamaDetail },
    { id: 'openrouter', label: 'OpenRouter', live: keys.openrouter, detail: keys.openrouter ? 'key configured' : 'no key' },
    { id: 'anthropic', label: 'Anthropic', live: keys.anthropic, detail: keys.anthropic ? 'key configured' : 'no key' }
  ]
})

// ─── Inline role re-routing ──────────────────────────────────────────────

const editingRole = ref<string | null>(null)
const editTarget = ref('')
const saving = ref(false)

const targetOptions = computed(() => {
  const o = overview.value
  if (!o) return []
  const options: { label: string, value: string }[] = []
  // Concrete runtime models first (Fable 5, Opus, Sonnet, Haiku) so the
  // operator picks a real model, not just an abstract alias.
  for (const m of o.runtime?.models ?? []) {
    options.push({ label: `runtime / ${m.label} · ${m.note}`, value: `runtime/${m.value}` })
  }
  for (const alias of ['best', 'default', 'fast']) {
    options.push({ label: `runtime / ${alias} (alias)`, value: `runtime/${alias}` })
  }
  for (const m of o.ollama?.models ?? []) {
    options.push({ label: `ollama / ${m.name}`, value: `ollama/${m.name}` })
  }
  if (o.keys?.anthropic) {
    for (const alias of ['best', 'default', 'fast']) {
      options.push({ label: `anthropic / ${alias}`, value: `anthropic/${alias}` })
    }
  }
  if (o.keys?.openrouter) {
    options.push({ label: 'openrouter / (type model id)', value: 'openrouter/' })
  }
  return options
})

function startEdit(row: ResolvedRole) {
  editingRole.value = row.role
  editTarget.value = `${row.provider}/${row.model}`
}

async function saveEdit(role: string) {
  if (!editTarget.value.includes('/')) {
    toast.add({ title: 'Target must be provider/model', color: 'error' })
    return
  }
  saving.value = true
  try {
    await $fetch(`${apiBase}/api/models/role`, {
      method: 'POST',
      body: { role, target: editTarget.value }
    })
    toast.add({ title: `${role} re-routed`, description: editTarget.value, color: 'success', icon: 'i-lucide-route' })
    editingRole.value = null
    await refresh()
  } catch (err) {
    toast.add({
      title: 'Re-route failed',
      description: err instanceof Error ? err.message : 'unknown error',
      color: 'error'
    })
  } finally {
    saving.value = false
  }
}

async function useForMechanical(model: OllamaModel) {
  editTarget.value = `ollama/${model.name}`
  await saveEdit('mechanical')
}

// ─── Usage bars ──────────────────────────────────────────────────────────

const usageRows = computed<Array<[string, BreakdownRow]>>(() =>
  Object.entries(usage.value?.by_model ?? {}).sort(
    (a, b) => (b[1].total_tokens_in + b[1].total_tokens_out) - (a[1].total_tokens_in + a[1].total_tokens_out)
  ).slice(0, 10)
)

const maxUsageTokens = computed(() => {
  const max = usageRows.value.reduce(
    (acc, [, r]) => Math.max(acc, r.total_tokens_in + r.total_tokens_out), 0
  )
  return max > 0 ? max : 1
})

function formatTokens(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`
  return value.toString()
}

function formatCost(value: number | null): string {
  if (value === null || value === undefined) return 'n/a'
  if (value === 0) return '$0'
  if (value < 0.01) return `$${value.toFixed(4)}`
  return `$${value.toFixed(2)}`
}
</script>

<template>
  <UDashboardPanel id="models">
    <template #header>
      <UDashboardNavbar title="Models">
        <template #right>
          <UButton
            label="Refresh"
            variant="ghost"
            icon="i-lucide-refresh-cw"
            size="sm"
            @click="() => { refresh(); refreshUsage() }"
          />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <DashboardState
        :status="status"
        :error="error"
        loading-label="Loading model fabric"
        :on-retry="() => refresh()"
      >
        <div class="space-y-6">
          <!-- Provider lanes: live availability strip -->
          <UCard>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div
                v-for="lane in lanes"
                :key="lane.id"
                class="flex items-start gap-3"
              >
                <span class="relative flex h-2.5 w-2.5 mt-1.5">
                  <span
                    v-if="lane.live"
                    class="animate-ping absolute inline-flex h-full w-full rounded-full opacity-60 motion-reduce:hidden"
                    :class="laneStyle(lane.id).dot"
                  />
                  <span
                    class="relative inline-flex rounded-full h-2.5 w-2.5"
                    :class="lane.live ? laneStyle(lane.id).dot : 'bg-muted/40'"
                  />
                </span>
                <div>
                  <p class="text-sm font-semibold">
                    {{ lane.label }}
                  </p>
                  <p class="text-xs text-muted">
                    {{ lane.detail }}
                  </p>
                </div>
              </div>
            </div>
          </UCard>

          <!-- Role routing -->
          <UCard>
            <template #header>
              <div class="flex items-center justify-between">
                <p class="text-xs font-semibold text-muted uppercase tracking-wider">
                  Role routing
                </p>
                <p class="text-xs text-muted font-mono hidden md:block">
                  {{ overview?.config_path }}
                </p>
              </div>
            </template>
            <div class="divide-y divide-default">
              <div
                v-for="row in overview?.roles ?? []"
                :key="row.role"
                class="flex items-center gap-3 py-2.5"
              >
                <UIcon
                  :name="QUALITY_ROLES.has(row.role) ? 'i-lucide-gem' : 'i-lucide-cog'"
                  class="size-4 shrink-0 mt-0.5 self-start"
                  :class="QUALITY_ROLES.has(row.role) ? 'text-primary' : 'text-muted'"
                />
                <div class="w-56 shrink-0">
                  <p class="text-sm font-medium">
                    {{ row.role }}
                  </p>
                  <p v-if="row.description" class="text-xs text-muted leading-snug">
                    {{ row.description }}
                  </p>
                </div>
                <template v-if="editingRole === row.role">
                  <UInputMenu
                    v-model="editTarget"
                    :items="targetOptions"
                    value-key="value"
                    create-item
                    size="sm"
                    class="flex-1 max-w-xs"
                    placeholder="provider/model"
                    @create="(item: string) => { editTarget = item }"
                  />
                  <UButton
                    size="xs"
                    label="Save"
                    :loading="saving"
                    @click="saveEdit(row.role)"
                  />
                  <UButton
                    size="xs"
                    variant="ghost"
                    label="Cancel"
                    @click="editingRole = null"
                  />
                </template>
                <template v-else>
                  <span
                    class="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium"
                    :class="laneStyle(row.provider).badge"
                  >
                    {{ row.provider }}
                  </span>
                  <span class="text-sm font-mono truncate">
                    {{ row.model || '(unset)' }}
                  </span>
                  <UBadge variant="subtle" size="sm" color="neutral">
                    {{ row.effort }}
                  </UBadge>
                  <UButton
                    icon="i-lucide-pencil"
                    variant="ghost"
                    size="xs"
                    class="ml-auto"
                    :aria-label="`Edit ${row.role} routing`"
                    @click="startEdit(row)"
                  />
                </template>
              </div>
            </div>
          </UCard>

          <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <!-- Local Ollama models -->
            <UCard>
              <template #header>
                <p class="text-xs font-semibold text-muted uppercase tracking-wider">
                  Local models (Ollama)
                </p>
              </template>
              <div v-if="overview?.ollama?.running && (overview.ollama?.models ?? []).length" class="divide-y divide-default">
                <div
                  v-for="m in (overview.ollama?.models ?? [])"
                  :key="m.name"
                  class="flex items-center gap-3 py-2"
                >
                  <UIcon name="i-lucide-hard-drive" class="size-4 text-amber-500 shrink-0" />
                  <div class="min-w-0 flex-1">
                    <p class="text-sm font-mono truncate">
                      {{ m.name }}
                    </p>
                    <p class="text-xs text-muted">
                      {{ m.family || 'unknown family' }}
                      <template v-if="m.parameter_size">
                        · {{ m.parameter_size }}
                      </template>
                      <template v-if="m.size_gb">
                        · {{ m.size_gb }} GB
                      </template>
                      <template v-if="!m.size_gb">
                        · cloud-proxied
                      </template>
                    </p>
                  </div>
                  <UButton
                    size="xs"
                    variant="soft"
                    label="Use for mechanical"
                    :loading="saving"
                    @click="useForMechanical(m)"
                  />
                </div>
              </div>
              <div v-else-if="overview?.ollama?.installed" class="py-6 text-center">
                <p class="text-sm text-muted">
                  Ollama is installed but not running.
                </p>
                <p class="text-xs text-muted mt-1 font-mono">
                  ollama serve
                </p>
              </div>
              <div v-else class="py-6 text-center">
                <p class="text-sm text-muted">
                  No local models yet.
                </p>
                <p class="text-xs text-muted mt-1">
                  Install Ollama to run free local models for mechanical work and fusion panels.
                </p>
              </div>
            </UCard>

            <!-- Usage by model -->
            <UCard>
              <template #header>
                <div class="flex items-center justify-between">
                  <p class="text-xs font-semibold text-muted uppercase tracking-wider">
                    Usage by model
                  </p>
                  <USelect
                    v-model="period"
                    :items="periodOptions"
                    size="xs"
                    class="min-w-24"
                    aria-label="Usage period"
                  />
                </div>
              </template>
              <div v-if="usageRows.length" class="space-y-3">
                <div class="flex items-baseline justify-between">
                  <p class="text-sm">
                    <span class="font-semibold">{{ usage?.call_count ?? 0 }}</span>
                    <span class="text-muted"> calls · </span>
                    <span class="font-semibold">{{ formatTokens((usage?.total_tokens_in ?? 0) + (usage?.total_tokens_out ?? 0)) }}</span>
                    <span class="text-muted"> tokens</span>
                  </p>
                  <p class="text-sm font-semibold">
                    {{ formatCost(usage?.total_cost_usd ?? null) }}
                  </p>
                </div>
                <div v-for="[name, row] in usageRows" :key="name" class="space-y-1">
                  <div class="flex items-center justify-between text-xs">
                    <span class="font-mono truncate">{{ name || '(unattributed)' }}</span>
                    <span class="text-muted shrink-0 ml-2">
                      {{ formatTokens(row.total_tokens_in + row.total_tokens_out) }} · {{ row.call_count }} calls
                    </span>
                  </div>
                  <div class="h-1.5 rounded-full bg-muted/20 overflow-hidden">
                    <div
                      class="h-full rounded-full bg-primary"
                      :style="{ width: `${Math.max(2, ((row.total_tokens_in + row.total_tokens_out) / maxUsageTokens) * 100)}%` }"
                    />
                  </div>
                </div>
              </div>
              <div v-else class="py-6 text-center">
                <p class="text-sm text-muted">
                  No usage recorded for this period.
                </p>
                <p class="text-xs text-muted mt-1">
                  Calls made through the Model Fabric land here automatically.
                </p>
              </div>
            </UCard>
          </div>
        </div>
      </DashboardState>
    </template>
  </UDashboardPanel>
</template>
