<script setup lang="ts">
// Mission Control (Pulse v2). Editorial sci-fi recomposition of the
// command center: numbered sections, count-up telemetry, agent
// constellation, live signal feed. Primary gate stays on
// /api/overview/command-center; section fetches are non-blocking.

interface ProjectRow {
  name: string
  path: string
  stack: string[]
  status: string
  ecosystem: string
  last_commit_days: number | null
}

interface IncidentRow {
  ts: string
  tool: string
  reason: string
  cwd: string
  bypass_used: boolean
  kind: 'bypass' | 'blocked'
}

interface QuickAction {
  command: string
  description: string
}

interface TopDeptRow {
  department: string
  calls: number
  cost_usd: number | null
  tokens_in: number
  tokens_out: number
}

interface RecentPersonaRow {
  id: string
  name: string
  title: string
  mbti: string
  source_store: string
  created_at: string | null
}

interface CommandCenterPayload {
  greeting: {
    name: string
    role: string
    company: string
    language: string
  }
  today_cost: {
    total_usd: number | null
    call_count: number
    tokens_in: number
    tokens_out: number
    cache_hit_rate: number
  }
  projects: ProjectRow[]
  recent_incidents: IncidentRow[]
  top_departments_30d: TopDeptRow[]
  recent_personas: RecentPersonaRow[]
  quick_actions: QuickAction[]
}

interface AgentRow {
  id: string
  name: string
  department: string
  tier: number
}

interface DeptRow {
  department: string
  agent_count: number
  calls_30d: number
  cost_usd_30d: number | null
}

interface TrendDay {
  date: string
  cost_usd: number
}

const { fetchApi } = useApi()

const {
  data,
  status,
  error,
  refresh
} = await fetchApi<CommandCenterPayload>('/api/overview/command-center')

// Section fetches — lazy so a slow endpoint never blocks the hero.
const { data: agentsData } = fetchApi<{ agents: AgentRow[] }>('/api/agents', { lazy: true })
const { data: deptsData } = fetchApi<{ departments: DeptRow[] }>('/api/departments', { lazy: true })
const { data: trendData } = fetchApi<{ days: TrendDay[] }>('/api/llm-costs/trend?days=30', { lazy: true })

const greetingLabel = computed(() => {
  const name = data.value?.greeting?.name?.trim()
  const language = data.value?.greeting?.language ?? 'en'
  if (!name) return language === 'pt' ? 'Olá' : 'Welcome'
  return language === 'pt' ? `Olá, ${name}` : `Hi, ${name}`
})

const todayCost = computed(() => data.value?.today_cost)

const trendSeries = computed(() =>
  (trendData.value?.days ?? []).map(d => ({ date: d.date, value: d.cost_usd ?? 0 }))
)

const constellationAgents = computed(() => agentsData.value?.agents ?? [])
const constellationDepts = computed(() =>
  (deptsData.value?.departments ?? []).map(d => ({ department: d.department, calls_30d: d.calls_30d }))
)

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`
  return n.toString()
}

function statusColor(status: string): 'success' | 'warning' | 'neutral' | 'error' {
  switch (status) {
    case 'active': return 'success'
    case 'paused': return 'warning'
    case 'archived': return 'neutral'
    case 'error': return 'error'
    default: return 'neutral'
  }
}

function commitFreshness(days: number | null): { color: string, label: string } {
  if (days === null) return { color: 'text-muted', label: 'no git' }
  if (days === 0) return { color: 'text-primary', label: 'today' }
  if (days === 1) return { color: 'text-primary', label: '1 day ago' }
  if (days < 7) return { color: 'text-primary', label: `${days} days ago` }
  if (days < 30) return { color: 'text-warning', label: `${days} days ago` }
  return { color: 'text-error', label: `${days} days ago` }
}

function formatIncidentTs(iso: string): string {
  if (!iso) return ''
  try {
    return new Intl.DateTimeFormat('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    }).format(new Date(iso))
  } catch {
    return iso
  }
}

const toast = useToast()
function copyCommand(cmd: string) {
  if (typeof navigator !== 'undefined' && navigator.clipboard) {
    navigator.clipboard.writeText(cmd)
      .then(() => toast.add({ title: 'Copied to clipboard', description: cmd, icon: 'i-lucide-clipboard-check' }))
      .catch(() => toast.add({ title: 'Copy failed', description: cmd, color: 'error', icon: 'i-lucide-clipboard-x' }))
  } else {
    toast.add({ title: 'Clipboard unavailable', description: cmd, color: 'warning' })
  }
}
</script>

<template>
  <UDashboardPanel id="overview">
    <template #header>
      <UDashboardNavbar title="Mission Control">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <UButton
            label="Refresh"
            variant="ghost"
            icon="i-lucide-refresh-cw"
            size="sm"
            @click="refresh()"
          />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <DashboardState
        :status="status"
        :error="error"
        loading-label="Loading mission control"
        :on-retry="() => refresh()"
      >
        <div class="mx-auto w-full max-w-6xl space-y-12 py-2">
          <!-- I. STATUS -->
          <div class="space-y-6">
            <ArkaPageHero
              numeral="I"
              label="mission control"
              :title="greetingLabel"
              :subtitle="data?.greeting?.role && data?.greeting?.company
                ? `${data.greeting.role} @ ${data.greeting.company} — status of every agent, every memory, every signal.`
                : 'Status of every agent, every memory, every signal.'"
            >
              <template #stats>
                <div class="grid grid-cols-2 gap-3 pt-4 lg:grid-cols-4">
                  <ArkaStatCard
                    label="today's cost"
                    :value="todayCost?.total_usd ?? null"
                    format="currency"
                    :decimals="2"
                    accent
                  />
                  <ArkaStatCard
                    label="calls"
                    :value="todayCost?.call_count ?? null"
                  />
                  <ArkaStatCard
                    label="tokens in / out"
                    :value="(todayCost?.tokens_in ?? 0) + (todayCost?.tokens_out ?? 0)"
                    format="tokens"
                    :hint="todayCost ? `${formatTokens(todayCost.tokens_in ?? 0)} in · ${formatTokens(todayCost.tokens_out ?? 0)} out` : ''"
                  />
                  <ArkaStatCard
                    label="cache hit rate"
                    :value="todayCost?.cache_hit_rate ?? null"
                    format="percent"
                  />
                </div>
              </template>
            </ArkaPageHero>

            <div class="arka-pulse-line" aria-hidden="true" />

            <ArkaGlowCard v-if="trendSeries.length" :padded="false" class="px-2 pt-4 pb-1">
              <div class="flex items-center justify-between px-3 pb-2">
                <span class="arka-eyebrow">cumulative spend · 30d</span>
                <span class="arka-data text-xs text-muted">
                  ${{ trendSeries.reduce((s, d) => s + d.value, 0).toFixed(2) }} total
                </span>
              </div>
              <ClientOnly>
                <ArkaTrendChart :series="trendSeries" :height="150" />
              </ClientOnly>
            </ArkaGlowCard>
          </div>

          <!-- II. AGENT CONSTELLATION -->
          <ArkaSection numeral="II" label="agent constellation">
            <template #actions>
              <NuxtLink to="/agents" class="arka-data text-xs text-muted transition-colors hover:text-primary">
                open control room →
              </NuxtLink>
            </template>
            <ArkaGlowCard :padded="false">
              <ClientOnly>
                <ArkaConstellation
                  v-if="constellationAgents.length"
                  :agents="constellationAgents"
                  :departments="constellationDepts"
                  :height="380"
                />
                <div v-else class="flex h-64 items-center justify-center">
                  <p class="arka-data text-xs text-muted">
                    mapping the constellation…
                  </p>
                </div>
              </ClientOnly>
            </ArkaGlowCard>
            <div v-if="data?.top_departments_30d?.length" class="flex flex-wrap gap-2">
              <NuxtLink
                v-for="(d, idx) in data.top_departments_30d"
                :key="d.department"
                :to="`/departments/${d.department}`"
                class="flex items-center gap-2 rounded-full border border-default bg-elevated px-3 py-1.5 transition-colors hover:border-primary/40"
              >
                <span class="arka-data text-[10px] text-muted">#{{ idx + 1 }}</span>
                <span class="text-xs font-medium capitalize">{{ d.department }}</span>
                <span class="arka-data text-[10px] text-muted">{{ d.calls }} calls</span>
                <span class="arka-data text-[10px]" :class="d.cost_usd === null ? 'text-muted' : 'text-primary'">
                  {{ d.cost_usd === null ? '—' : `$${d.cost_usd.toFixed(2)}` }}
                </span>
              </NuxtLink>
            </div>
          </ArkaSection>

          <!-- III. LIVE FEED -->
          <ArkaSection numeral="III" label="live feed">
            <template #actions>
              <span class="flex items-center gap-2">
                <span class="arka-live-dot" />
                <span class="arka-data text-[10px] text-muted uppercase">live</span>
              </span>
            </template>
            <ArkaLiveFeed />
          </ArkaSection>

          <!-- IV. PROJECTS & ACTIONS -->
          <ArkaSection numeral="IV" label="projects & actions">
            <AgentSuggestionsCard />
            <div class="grid grid-cols-1 gap-6 lg:grid-cols-[2fr_1fr]">
              <div class="space-y-2">
                <DashboardState
                  :status="status"
                  :empty="!data?.projects?.length"
                  empty-title="No projects discovered yet"
                  empty-description="Add your project directories in Settings → Projects."
                  empty-icon="i-lucide-folder-open"
                >
                  <ArkaGlowCard
                    v-for="p in data?.projects"
                    :key="p.name"
                    interactive
                    class="mb-2"
                  >
                    <div class="flex items-start justify-between gap-3">
                      <div class="min-w-0 flex-1">
                        <div class="mb-1 flex items-center gap-2">
                          <span class="truncate text-sm font-semibold">{{ p.name }}</span>
                          <UBadge
                            v-if="p.status"
                            :label="p.status"
                            :color="statusColor(p.status)"
                            variant="subtle"
                            size="xs"
                          />
                          <UBadge
                            v-if="p.ecosystem"
                            :label="p.ecosystem"
                            color="primary"
                            variant="outline"
                            size="xs"
                          />
                        </div>
                        <p class="arka-data truncate text-xs text-muted">
                          {{ p.path }}
                        </p>
                        <div class="mt-2 flex flex-wrap items-center gap-2">
                          <UBadge
                            v-for="s in p.stack"
                            :key="s"
                            :label="s"
                            variant="soft"
                            size="xs"
                          />
                        </div>
                      </div>
                      <span
                        class="arka-data shrink-0 text-xs"
                        :class="commitFreshness(p.last_commit_days).color"
                      >
                        {{ commitFreshness(p.last_commit_days).label }}
                      </span>
                    </div>
                  </ArkaGlowCard>
                </DashboardState>
              </div>

              <div class="space-y-6">
                <div>
                  <p class="arka-eyebrow mb-3">
                    quick launch
                  </p>
                  <div class="space-y-1.5">
                    <button
                      v-for="a in data?.quick_actions"
                      :key="a.command"
                      type="button"
                      class="arka-glow-card w-full p-3 text-left"
                      data-interactive="true"
                      @click="copyCommand(a.command)"
                    >
                      <div class="flex items-center gap-2">
                        <code class="arka-data text-sm font-semibold text-primary">{{ a.command }}</code>
                        <UIcon name="i-lucide-clipboard" class="ml-auto size-3 text-muted" />
                      </div>
                      <p class="mt-1 text-xs text-muted">
                        {{ a.description }}
                      </p>
                    </button>
                  </div>
                </div>

                <div>
                  <p class="arka-eyebrow mb-3">
                    recent incidents
                  </p>
                  <DashboardState
                    :status="status"
                    :empty="!data?.recent_incidents?.length"
                    empty-title="No incidents"
                    empty-description="Bypass uses and flow blocks show up here."
                    empty-icon="i-lucide-shield-check"
                  >
                    <div class="space-y-1.5">
                      <div
                        v-for="(i, idx) in data?.recent_incidents"
                        :key="idx"
                        class="rounded-lg border border-default p-3"
                      >
                        <div class="mb-1 flex items-center gap-2">
                          <UBadge
                            :label="i.kind"
                            :color="i.kind === 'bypass' ? 'warning' : 'error'"
                            variant="subtle"
                            size="xs"
                          />
                          <span class="arka-data text-xs text-muted">{{ formatIncidentTs(i.ts) }}</span>
                        </div>
                        <p class="arka-data truncate text-xs text-muted" :title="i.reason">
                          {{ i.tool }} — {{ i.reason }}
                        </p>
                      </div>
                    </div>
                  </DashboardState>
                </div>

                <div>
                  <p class="arka-eyebrow mb-3">
                    recent personas
                  </p>
                  <DashboardState
                    :status="status"
                    :empty="!data?.recent_personas?.length"
                    empty-title="No personas yet"
                    empty-description="Create one from /personas → New Persona."
                    empty-icon="i-lucide-user-plus"
                  >
                    <div class="space-y-1.5">
                      <NuxtLink
                        v-for="p in data?.recent_personas"
                        :key="p.id"
                        :to="`/personas/${p.id}`"
                        class="block rounded-lg border border-default p-3 transition-colors hover:border-primary/40"
                      >
                        <div class="flex items-center justify-between gap-3">
                          <div class="min-w-0">
                            <p class="truncate text-sm font-semibold">
                              {{ p.name }}
                            </p>
                            <p class="truncate text-xs text-muted">
                              {{ p.title || '—' }}
                            </p>
                          </div>
                          <div class="flex shrink-0 items-center gap-2">
                            <UBadge
                              v-if="p.mbti"
                              :label="p.mbti"
                              variant="subtle"
                              size="xs"
                            />
                            <UBadge
                              v-if="p.source_store === 'obsidian'"
                              icon="i-lucide-file-text"
                              label="Obsidian"
                              color="primary"
                              variant="soft"
                              size="xs"
                            />
                          </div>
                        </div>
                      </NuxtLink>
                    </div>
                  </DashboardState>
                </div>
              </div>
            </div>
          </ArkaSection>
        </div>
      </DashboardState>
    </template>
  </UDashboardPanel>
</template>
