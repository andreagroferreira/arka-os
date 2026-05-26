<script setup lang="ts">
// PR66 v2.83.0 — Command center.
//
// Replaces the 6-stat-card Overview that just counted things you
// already knew (agents=62, skills=256, ...) with telemetry-driven
// information the operator actually uses: greeting, today's cost,
// per-project state, recent incidents, quick actions.

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

const { fetchApi } = useApi()

const {
  data,
  status,
  error,
  refresh,
} = await fetchApi<CommandCenterPayload>('/api/overview/command-center')

const greetingLabel = computed(() => {
  const name = data.value?.greeting?.name?.trim()
  const language = data.value?.greeting?.language ?? 'en'
  if (!name) return language === 'pt' ? 'Olá' : 'Welcome'
  return language === 'pt' ? `Olá, ${name}` : `Hi, ${name}`
})

const todayCost = computed(() => data.value?.today_cost)

function formatCost(value: number | null | undefined): string {
  if (value === null || value === undefined) return 'n/a'
  if (value === 0) return '$0'
  if (value < 0.01) return `$${value.toFixed(4)}`
  return `$${value.toFixed(2)}`
}

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
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

function commitFreshness(days: number | null): { color: string; label: string } {
  if (days === null) return { color: 'text-muted', label: 'no git' }
  if (days === 0) return { color: 'text-green-500', label: 'today' }
  if (days === 1) return { color: 'text-green-500', label: '1 day ago' }
  if (days < 7) return { color: 'text-primary', label: `${days} days ago` }
  if (days < 30) return { color: 'text-yellow-500', label: `${days} days ago` }
  return { color: 'text-red-500', label: `${days} days ago` }
}

function formatIncidentTs(iso: string): string {
  if (!iso) return ''
  try {
    return new Intl.DateTimeFormat('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(iso))
  } catch {
    return iso
  }
}

function copyCommand(cmd: string) {
  if (typeof navigator !== 'undefined' && navigator.clipboard) {
    navigator.clipboard.writeText(cmd).catch(() => { /* ignore */ })
  }
}
</script>

<template>
  <UDashboardPanel id="overview">
    <template #header>
      <UDashboardNavbar title="Command Center">
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
        loading-label="Loading command center"
        :on-retry="() => refresh()"
      >
        <div class="space-y-6">
          <!-- Hero: greeting + today's cost -->
          <UCard>
            <div class="flex flex-col gap-2 md:flex-row md:items-baseline md:justify-between">
              <div>
                <h1 class="text-2xl font-bold">{{ greetingLabel }}.</h1>
                <p class="text-sm text-muted mt-1">
                  <template v-if="data?.greeting?.role && data?.greeting?.company">
                    {{ data.greeting.role }} @ {{ data.greeting.company }}
                  </template>
                  <template v-else>
                    Set your profile in Settings to personalise this view.
                  </template>
                </p>
              </div>
              <div v-if="todayCost" class="flex items-baseline gap-6 text-right">
                <div>
                  <p class="text-xs font-semibold text-muted uppercase tracking-wider">
                    Today's cost
                  </p>
                  <p class="text-2xl font-bold">{{ formatCost(todayCost.total_usd) }}</p>
                </div>
                <div>
                  <p class="text-xs font-semibold text-muted uppercase tracking-wider">
                    Calls
                  </p>
                  <p class="text-2xl font-bold">{{ todayCost.call_count }}</p>
                </div>
                <div>
                  <p class="text-xs font-semibold text-muted uppercase tracking-wider">
                    Cache
                  </p>
                  <p class="text-2xl font-bold">
                    {{ (todayCost.cache_hit_rate * 100).toFixed(0) }}%
                  </p>
                </div>
              </div>
            </div>
          </UCard>

          <!-- PR91a v3.35.0 — Agent gap suggestions -->
          <AgentSuggestionsCard class="mb-6" />

          <!-- PR84d v3.10.0 — Top departments + Recent personas row -->
          <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
            <div>
              <h2 class="text-sm font-semibold uppercase tracking-wider text-muted mb-3">
                Top departments (30d)
              </h2>
              <DashboardState
                :status="status"
                :empty="!data?.top_departments_30d?.length"
                empty-title="No telemetry yet"
                empty-description="Department spend will appear once agents start running."
                empty-icon="i-lucide-bar-chart"
              >
                <div class="space-y-2">
                  <div
                    v-for="(d, idx) in data?.top_departments_30d"
                    :key="d.department"
                    class="rounded-lg border border-default p-3 flex items-center gap-3"
                  >
                    <span class="text-xs font-mono font-semibold text-muted w-6">#{{ idx + 1 }}</span>
                    <span class="flex-1 font-semibold capitalize">{{ d.department }}</span>
                    <span class="text-xs font-mono text-muted">{{ d.calls }} calls</span>
                    <span class="text-sm font-mono font-semibold">
                      {{ d.cost_usd === null ? '—' : `$${d.cost_usd.toFixed(2)}` }}
                    </span>
                  </div>
                </div>
              </DashboardState>
            </div>

            <div>
              <h2 class="text-sm font-semibold uppercase tracking-wider text-muted mb-3">
                Recent personas
              </h2>
              <DashboardState
                :status="status"
                :empty="!data?.recent_personas?.length"
                empty-title="No personas yet"
                empty-description="Create one from /personas → New Persona."
                empty-icon="i-lucide-user-plus"
              >
                <div class="space-y-2">
                  <NuxtLink
                    v-for="p in data?.recent_personas"
                    :key="p.id"
                    :to="`/personas/${p.id}`"
                    class="block rounded-lg border border-default p-3 hover:border-primary/40 transition-colors"
                  >
                    <div class="flex items-center justify-between gap-3">
                      <div class="min-w-0">
                        <p class="text-sm font-semibold truncate">{{ p.name }}</p>
                        <p class="text-xs text-muted truncate">{{ p.title || '—' }}</p>
                      </div>
                      <div class="flex items-center gap-2 shrink-0">
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

          <!-- Two columns: projects + incidents -->
          <div class="grid grid-cols-1 lg:grid-cols-[2fr_1fr] gap-6">
            <!-- Projects -->
            <div>
              <div class="flex items-baseline justify-between mb-3">
                <h2 class="text-sm font-semibold uppercase tracking-wider text-muted">
                  Projects
                </h2>
                <NuxtLink to="/settings" class="text-xs text-muted hover:text-primary">
                  Configure dirs →
                </NuxtLink>
              </div>
              <DashboardState
                :status="status"
                :empty="!data?.projects?.length"
                empty-title="No projects discovered yet"
                empty-description="Add your project directories in Settings → Projects."
                empty-icon="i-lucide-folder-open"
              >
                <div class="space-y-2">
                  <div
                    v-for="p in data?.projects"
                    :key="p.name"
                    class="rounded-lg border border-default p-3 hover:border-primary/40 transition-colors"
                  >
                    <div class="flex items-start justify-between gap-3">
                      <div class="min-w-0 flex-1">
                        <div class="flex items-center gap-2 mb-1">
                          <span class="text-sm font-semibold truncate">{{ p.name }}</span>
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
                        <p class="text-xs text-muted font-mono truncate">{{ p.path }}</p>
                        <div class="flex items-center gap-2 mt-2 flex-wrap">
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
                        class="text-xs font-mono shrink-0"
                        :class="commitFreshness(p.last_commit_days).color"
                      >
                        {{ commitFreshness(p.last_commit_days).label }}
                      </span>
                    </div>
                  </div>
                </div>
              </DashboardState>
            </div>

            <!-- Incidents + Quick actions -->
            <div class="space-y-6">
              <div>
                <h2 class="text-sm font-semibold uppercase tracking-wider text-muted mb-3">
                  Recent incidents
                </h2>
                <DashboardState
                  :status="status"
                  :empty="!data?.recent_incidents?.length"
                  empty-title="No incidents"
                  empty-description="Bypass uses and flow blocks show up here."
                  empty-icon="i-lucide-shield-check"
                >
                  <div class="space-y-2">
                    <div
                      v-for="(i, idx) in data?.recent_incidents"
                      :key="idx"
                      class="rounded-lg border border-default p-3"
                    >
                      <div class="flex items-center gap-2 mb-1">
                        <UBadge
                          :label="i.kind"
                          :color="i.kind === 'bypass' ? 'warning' : 'error'"
                          variant="subtle"
                          size="xs"
                        />
                        <span class="text-xs text-muted">{{ formatIncidentTs(i.ts) }}</span>
                      </div>
                      <p class="text-xs font-mono text-muted truncate" :title="i.reason">
                        {{ i.tool }} — {{ i.reason }}
                      </p>
                    </div>
                  </div>
                </DashboardState>
              </div>

              <div>
                <h2 class="text-sm font-semibold uppercase tracking-wider text-muted mb-3">
                  Quick actions
                </h2>
                <div class="space-y-1">
                  <button
                    v-for="a in data?.quick_actions"
                    :key="a.command"
                    type="button"
                    class="w-full text-left p-3 rounded-lg border border-default hover:border-primary/40 hover:bg-elevated/30 transition-colors"
                    @click="copyCommand(a.command)"
                  >
                    <div class="flex items-center gap-2">
                      <code class="text-sm font-mono font-semibold text-primary">{{ a.command }}</code>
                      <UIcon name="i-lucide-clipboard" class="size-3 text-muted ml-auto" />
                    </div>
                    <p class="text-xs text-muted mt-1">{{ a.description }}</p>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </DashboardState>
    </template>
  </UDashboardPanel>
</template>
