<script setup lang="ts">
// PR76 v2.94.0 — Agent detail modernization.
// Fixes:
//  - UTabs now has default-value so DNA opens on entry
//  - Modern hero: department-tinted gradient + initials avatar + stats
//  - Activity stats row pulled from PR69 /api/agents/activity
//  - Edit toggle wired to AgentEditDrawer (PUT /api/agents/{id})

const route = useRoute()
const agentId = route.params.id as string

const { fetchApi, apiBase } = useApi()
const toast = useToast()
const { data: agent, status, error, refresh } = fetchApi<any>(`/api/agents/${agentId}`)

// Per-department activity (PR69 endpoint) for the stats row.
interface ActivityRow {
  call_count: number
  total_cost_usd: number | null
  total_tokens_in: number
  total_tokens_out: number
}
const { data: activityData } = fetchApi<{
  by_department: Record<string, ActivityRow>
  period: string
}>('/api/agents/activity?period=week')
const deptActivity = computed<ActivityRow | null>(() =>
  (activityData.value?.by_department?.[agent.value?.department ?? ''] ?? null),
)

// PR88d v3.26.0 — agent history (git log + trash entries)
interface HistoryEvent {
  kind: string
  ts: string | null
  summary: string
  ref?: string
  author?: string
}
const { data: historyData } = fetchApi<{ events: HistoryEvent[] }>(
  `/api/agents/${agentId}/history?limit=20`,
)

const historyEvents = computed<HistoryEvent[]>(() => historyData.value?.events ?? [])

function historyKindIcon(kind: string): string {
  return ({
    'git-commit': 'i-lucide-git-commit',
    'agent-delete': 'i-lucide-trash-2',
    'agent-move': 'i-lucide-folder-tree',
  } as Record<string, string>)[kind] ?? 'i-lucide-circle'
}
function historyKindColor(kind: string): string {
  return ({
    'git-commit': 'text-blue-500',
    'agent-delete': 'text-red-500',
    'agent-move': 'text-amber-500',
  } as Record<string, string>)[kind] ?? 'text-muted'
}

// PR83d v3.6.0 + PR86b v3.16.0 — activity strip (30d, agent or dept scope)
interface ActivityStrip {
  period: string
  scope: 'agent' | 'department'
  department: string
  calls: number
  cost_usd: number | null
  tokens_in: number
  tokens_out: number
  last_used: string | null
  dept_rank: number | null
  dept_count: number
}
const { data: activityStrip } = fetchApi<ActivityStrip>(
  `/api/agents/${agentId}/activity-strip?period=month`,
)

function formatRelative(iso: string | null): string {
  if (!iso) return 'never'
  const ts = Date.parse(iso)
  if (Number.isNaN(ts)) return 'never'
  const diff = Date.now() - ts
  const minutes = Math.floor(diff / 60_000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${days}d ago`
  const months = Math.floor(days / 30)
  return `${months}mo ago`
}

// PR86a v3.15.0 — favorites.
const favs = useFavorites()
await favs.load()

// PR86d v3.18.0 — render Markdown bio.
import { marked } from 'marked'
function markedHtml(src: string): string {
  if (!src?.trim()) return ''
  try {
    return marked.parse(src, { breaks: true, gfm: true }) as string
  } catch {
    return ''
  }
}

// PR95b v3.52.0 — edit YAML inline (modal).
const yamlEditorOpen = ref(false)
const yamlEditorDraft = ref('')
const yamlEditorSaving = ref(false)

async function openYamlEditor() {
  if (!agent.value) return
  // Fetch raw YAML once when opening (already on backend via PR89d).
  try {
    const blob = await $fetch<Blob>(
      `${apiBase}/api/agents/${agentId}/yaml`,
      { responseType: 'blob' },
    )
    yamlEditorDraft.value = await blob.text()
    yamlEditorOpen.value = true
  } catch (err) {
    toast.add({
      title: 'Failed to load YAML',
      description: err instanceof Error ? err.message : 'unknown error',
      color: 'error',
    })
  }
}

async function saveYamlEditor() {
  if (!agent.value) return
  yamlEditorSaving.value = true
  try {
    const res = await $fetch<{ updated?: boolean, error?: string }>(
      `${apiBase}/api/agents/${agentId}/yaml`,
      { method: 'PUT', body: { content: yamlEditorDraft.value } },
    )
    if (res.error) throw new Error(res.error)
    toast.add({
      title: 'YAML updated',
      description: agentId,
      color: 'success',
      icon: 'i-lucide-check',
    })
    yamlEditorOpen.value = false
    await refresh()
  } catch (err) {
    toast.add({
      title: 'Save failed',
      description: err instanceof Error ? err.message : 'unknown error',
      color: 'error',
    })
  } finally {
    yamlEditorSaving.value = false
  }
}

// PR89d v3.30.0 — download YAML.
const downloadingYaml = ref(false)
async function downloadYaml() {
  if (!agent.value) return
  downloadingYaml.value = true
  try {
    const blob = await $fetch<Blob>(
      `${apiBase}/api/agents/${agentId}/yaml`,
      { responseType: 'blob' },
    )
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${agentId}.yaml`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
    toast.add({
      title: 'YAML downloaded',
      description: `${agentId}.yaml`,
      color: 'success',
      icon: 'i-lucide-download',
    })
  } catch (err) {
    toast.add({
      title: 'Download failed',
      description: err instanceof Error ? err.message : 'unknown error',
      color: 'error',
    })
  } finally {
    downloadingYaml.value = false
  }
}

// PR86c v3.17.0 — export to Obsidian.
const exporting = ref(false)
async function exportToVault() {
  if (!agent.value) return
  exporting.value = true
  try {
    const res = await $fetch<{ exported?: boolean, path?: string, error?: string }>(
      `${apiBase}/api/agents/${agentId}/export`,
      { method: 'POST' },
    )
    if (res.error) throw new Error(res.error)
    toast.add({
      title: 'Exported to Obsidian',
      description: res.path ? res.path.split('/').slice(-3).join('/') : undefined,
      color: 'success',
      icon: 'i-lucide-file-text',
    })
  } catch (err) {
    toast.add({
      title: 'Export failed',
      description: err instanceof Error ? err.message : 'unknown error',
      color: 'error',
    })
  } finally {
    exporting.value = false
  }
}

// PR76 — edit drawer state
const editOpen = ref(false)

function openEditor() {
  editOpen.value = true
}

async function onAgentSaved() {
  await refresh()
}

// --- Labels & mappings ---

const tierLabel: Record<number, string> = {
  0: 'C-Suite',
  1: 'Squad Lead',
  2: 'Specialist',
  3: 'Support',
}

const tierColor: Record<number, string> = {
  0: 'error',
  1: 'warning',
  2: 'primary',
  3: 'neutral',
}

const depthColor: Record<string, string> = {
  master: 'error',
  expert: 'warning',
  advanced: 'primary',
  intermediate: 'neutral',
}

const bigFiveLabels: Record<string, string> = {
  O: 'Openness',
  C: 'Conscientiousness',
  E: 'Extraversion',
  A: 'Agreeableness',
  N: 'Neuroticism',
}

const bigFiveKeys = ['O', 'C', 'E', 'A', 'N'] as const

const mbtiDescriptions: Record<string, string> = {
  INTJ: 'Ni-Te-Fi-Se — The Architect',
  INTP: 'Ti-Ne-Si-Fe — The Logician',
  ENTJ: 'Te-Ni-Se-Fi — The Commander',
  ENTP: 'Ne-Ti-Fe-Si — The Debater',
  INFJ: 'Ni-Fe-Ti-Se — The Advocate',
  INFP: 'Fi-Ne-Si-Te — The Mediator',
  ENFJ: 'Fe-Ni-Se-Ti — The Protagonist',
  ENFP: 'Ne-Fi-Te-Si — The Campaigner',
  ISTJ: 'Si-Te-Fi-Ne — The Inspector',
  ISFJ: 'Si-Fe-Ti-Ne — The Defender',
  ESTJ: 'Te-Si-Ne-Fi — The Executive',
  ESFJ: 'Fe-Si-Ne-Ti — The Consul',
  ISTP: 'Ti-Se-Ni-Fe — The Virtuoso',
  ISFP: 'Fi-Se-Ni-Te — The Adventurer',
  ESTP: 'Se-Ti-Fe-Ni — The Entrepreneur',
  ESFP: 'Se-Fi-Te-Ni — The Entertainer',
}

// --- DISC bar values ---

const discLetters = ['D', 'I', 'S', 'C'] as const

function discBarValue(letter: string): number {
  if (!agent.value?.disc) return 20
  if (agent.value.disc.primary === letter) return 90
  if (agent.value.disc.secondary === letter) return 70
  return 20
}

function discBarColor(letter: string): string {
  const colors: Record<string, string> = {
    D: 'bg-red-500',
    I: 'bg-yellow-500',
    S: 'bg-green-500',
    C: 'bg-blue-500',
  }
  return colors[letter] ?? 'bg-primary'
}

function bigFiveBarColor(value: number): string {
  if (value >= 75) return 'bg-primary'
  if (value >= 50) return 'bg-blue-400'
  if (value >= 30) return 'bg-yellow-500'
  return 'bg-neutral-500'
}

// --- Tabs ---

const tabs = [
  { label: 'DNA', value: 'dna', icon: 'i-lucide-dna' },
  { label: 'Communication', value: 'communication', icon: 'i-lucide-message-square' },
  { label: 'Mental Models', value: 'models', icon: 'i-lucide-brain' },
  { label: 'Authority', value: 'authority', icon: 'i-lucide-shield' },
  { label: 'Expertise', value: 'expertise', icon: 'i-lucide-award' },
]

// PR76 — hero helpers

const initials = computed<string>(() => {
  const name = agent.value?.name ?? ''
  if (!name) return '·'
  const parts = name.trim().split(/\s+/)
  if (parts.length === 1) return (parts[0] ?? '').slice(0, 2).toUpperCase()
  return ((parts[0]?.[0] ?? '') + (parts[parts.length - 1]?.[0] ?? '')).toUpperCase()
})

// Per-department gradient hex pair (from + to). Picked once per dept
// so the same dept always renders the same hero tint.
const DEPT_GRADIENTS: Record<string, [string, string]> = {
  brand:       ['from-fuchsia-500/30', 'to-purple-600/10'],
  marketing:   ['from-pink-500/30',    'to-rose-600/10'],
  dev:         ['from-blue-500/30',    'to-cyan-600/10'],
  ecom:        ['from-amber-500/30',   'to-orange-600/10'],
  finance:     ['from-emerald-500/30', 'to-green-600/10'],
  strategy:    ['from-indigo-500/30',  'to-violet-600/10'],
  kb:          ['from-teal-500/30',    'to-cyan-600/10'],
  ops:         ['from-slate-500/30',   'to-gray-600/10'],
  pm:          ['from-sky-500/30',     'to-blue-600/10'],
  saas:        ['from-violet-500/30',  'to-indigo-600/10'],
  landing:     ['from-orange-500/30',  'to-red-600/10'],
  content:     ['from-rose-500/30',    'to-pink-600/10'],
  community:   ['from-yellow-500/30',  'to-amber-600/10'],
  sales:       ['from-red-500/30',     'to-orange-600/10'],
  leadership:  ['from-purple-500/30',  'to-pink-600/10'],
  org:         ['from-gray-500/30',    'to-slate-600/10'],
}

const heroGradientClasses = computed(() => {
  const dept = agent.value?.department ?? ''
  const [from, to] = DEPT_GRADIENTS[dept] ?? ['from-primary/20', 'to-primary/5']
  return `bg-gradient-to-br ${from} ${to}`
})

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
</script>

<template>
  <UDashboardPanel id="agent-detail">
    <template #header>
      <UDashboardNavbar :title="agent?.name ?? 'Agent'">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #trailing>
          <UButton
            label="Back"
            variant="ghost"
            icon="i-lucide-arrow-left"
            to="/agents"
            aria-label="Back to agents list"
          />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <!-- Loading -->
      <div v-if="status === 'pending'" class="flex items-center justify-center py-24">
        <UIcon name="i-lucide-loader-2" class="size-8 animate-spin text-muted" />
      </div>

      <!-- Error -->
      <div v-else-if="error" class="flex flex-col items-center justify-center gap-4 py-24" role="alert">
        <UIcon name="i-lucide-alert-triangle" class="size-12 text-red-500" />
        <p class="text-sm text-muted">Failed to load agent data.</p>
        <UButton label="Back to Agents" variant="outline" icon="i-lucide-arrow-left" to="/agents" />
      </div>

      <!-- Not found -->
      <div v-else-if="!agent" class="flex flex-col items-center justify-center gap-4 py-24">
        <UIcon name="i-lucide-user-x" class="size-12 text-muted" />
        <p class="text-sm text-muted">Agent not found.</p>
        <UButton label="Back to Agents" variant="outline" icon="i-lucide-arrow-left" to="/agents" />
      </div>

      <!-- Content -->
      <div v-else class="space-y-6 pb-12">
        <!-- ===== HERO ===== -->
        <section
          class="relative overflow-hidden rounded-2xl border border-default p-6 md:p-8"
          :class="heroGradientClasses"
        >
          <div class="flex items-start gap-5">
            <div class="shrink-0 size-20 rounded-2xl bg-default/80 border border-default flex items-center justify-center shadow-lg backdrop-blur-sm">
              <span class="text-2xl font-bold tracking-tight text-highlighted">{{ initials }}</span>
            </div>
            <div class="flex-1 min-w-0 space-y-2">
              <div class="flex items-start justify-between gap-3 flex-wrap">
                <div class="min-w-0">
                  <h1 class="text-3xl md:text-4xl font-bold tracking-tight text-highlighted">
                    {{ agent.name }}
                  </h1>
                  <p class="text-base md:text-lg text-muted mt-0.5">{{ agent.role }}</p>
                </div>
                <div class="flex items-center gap-2">
                  <UButton
                    icon="i-lucide-star"
                    :color="favs.isAgentFavorite(agent.id) ? 'warning' : 'neutral'"
                    :variant="favs.isAgentFavorite(agent.id) ? 'soft' : 'ghost'"
                    size="sm"
                    :aria-label="favs.isAgentFavorite(agent.id) ? 'Unfavorite' : 'Favorite'"
                    @click="favs.toggle('agents', agent.id)"
                  />
                  <UButton
                    label="Export"
                    icon="i-lucide-file-text"
                    variant="soft"
                    size="sm"
                    :loading="exporting"
                    @click="exportToVault"
                  />
                  <UButton
                    label="YAML"
                    icon="i-lucide-download"
                    variant="ghost"
                    size="sm"
                    :loading="downloadingYaml"
                    @click="downloadYaml"
                  />
                  <UButton
                    label="Edit YAML"
                    icon="i-lucide-file-code"
                    variant="ghost"
                    size="sm"
                    @click="openYamlEditor"
                  />
                  <UButton
                    label="Edit"
                    icon="i-lucide-pencil"
                    size="sm"
                    @click="openEditor"
                  />
                </div>
              </div>
              <div class="flex flex-wrap items-center gap-2 pt-1">
                <UBadge :label="agent.department" variant="subtle" />
                <UBadge
                  :label="`Tier ${agent.tier} — ${tierLabel[agent.tier] ?? ''}`"
                  variant="subtle"
                  :color="(tierColor[agent.tier] ?? 'neutral') as any"
                />
                <UBadge
                  v-if="agent.expertise_depth"
                  :label="agent.expertise_depth"
                  variant="subtle"
                  :color="(depthColor[agent.expertise_depth] ?? 'neutral') as any"
                />
                <UBadge
                  v-if="agent.expertise_years"
                  :label="`${agent.expertise_years}y experience`"
                  variant="outline"
                />
                <UBadge v-if="agent.mbti" :label="agent.mbti" variant="soft" size="sm" />
              </div>
              <p class="text-xs text-muted/60 font-mono select-all pt-2">{{ agent.id }}</p>
            </div>
          </div>
        </section>

        <!-- ===== STATS ROW ===== -->
        <section class="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div class="rounded-xl border border-default p-4 bg-elevated/20">
            <p class="text-sm font-semibold text-muted uppercase tracking-wide mb-1">7d calls (dept)</p>
            <p class="text-2xl font-bold">{{ deptActivity?.call_count ?? 0 }}</p>
          </div>
          <div class="rounded-xl border border-default p-4 bg-elevated/20">
            <p class="text-sm font-semibold text-muted uppercase tracking-wide mb-1">7d cost</p>
            <p class="text-2xl font-bold">{{ formatCost(deptActivity?.total_cost_usd) }}</p>
          </div>
          <div class="rounded-xl border border-default p-4 bg-elevated/20">
            <p class="text-sm font-semibold text-muted uppercase tracking-wide mb-1">Tokens (in/out)</p>
            <p class="text-lg font-semibold">
              {{ formatTokens(deptActivity?.total_tokens_in ?? 0) }} /
              {{ formatTokens(deptActivity?.total_tokens_out ?? 0) }}
            </p>
          </div>
          <div class="rounded-xl border border-default p-4 bg-elevated/20">
            <p class="text-sm font-semibold text-muted uppercase tracking-wide mb-1">Linked personas</p>
            <p class="text-2xl font-bold">{{ agent.linked_personas?.length ?? 0 }}</p>
          </div>
        </section>

        <!-- ===== ACTIVITY STRIP (PR83d) ===== -->
        <section
          v-if="activityStrip"
          class="rounded-xl border border-default bg-elevated/10 p-4"
        >
          <div class="flex flex-wrap items-center gap-x-6 gap-y-3 text-sm">
            <div class="flex items-center gap-2">
              <UIcon name="i-lucide-activity" class="size-4 text-primary" />
              <span class="font-semibold uppercase tracking-wide text-muted text-xs">
                30d activity ({{ activityStrip.scope === 'agent' ? 'agent' : 'dept' }})
              </span>
            </div>
            <div class="flex items-center gap-2">
              <span class="text-muted">Calls</span>
              <span class="font-mono font-semibold">{{ activityStrip.calls }}</span>
            </div>
            <div class="flex items-center gap-2">
              <span class="text-muted">Cost</span>
              <span class="font-mono font-semibold">{{ formatCost(activityStrip.cost_usd) }}</span>
            </div>
            <div class="flex items-center gap-2">
              <span class="text-muted">Tokens</span>
              <span class="font-mono">
                {{ formatTokens(activityStrip.tokens_in) }} /
                {{ formatTokens(activityStrip.tokens_out) }}
              </span>
            </div>
            <div class="flex items-center gap-2">
              <span class="text-muted">Last used</span>
              <span class="font-mono">{{ formatRelative(activityStrip.last_used) }}</span>
            </div>
            <div v-if="activityStrip.dept_rank" class="flex items-center gap-2">
              <span class="text-muted">Dept rank</span>
              <UBadge
                :label="`#${activityStrip.dept_rank} of ${activityStrip.dept_count}`"
                :color="activityStrip.dept_rank <= 3 ? 'primary' : 'neutral'"
                variant="subtle"
                size="sm"
              />
            </div>
          </div>
        </section>

        <!-- ===== BIO (PR86d) ===== -->
        <section
          v-if="(agent as any).bio_md"
          class="rounded-xl border border-default bg-elevated/10 p-5"
        >
          <h3 class="text-sm font-semibold uppercase tracking-wide text-muted mb-3">
            Bio
          </h3>
          <div
            class="prose prose-sm dark:prose-invert max-w-none"
            v-html="markedHtml((agent as any).bio_md)"
          />
        </section>

        <!-- ===== HISTORY TIMELINE (PR88d) ===== -->
        <section
          v-if="historyEvents.length > 0"
          class="rounded-xl border border-default bg-elevated/10 p-5"
        >
          <h3 class="text-sm font-semibold uppercase tracking-wide text-muted mb-4">
            History
          </h3>
          <ol class="relative border-l border-default ml-2 space-y-3">
            <li
              v-for="(ev, idx) in historyEvents"
              :key="idx"
              class="ml-4"
            >
              <span
                class="absolute -left-1.5 size-3 rounded-full bg-elevated border border-default flex items-center justify-center"
              >
                <UIcon :name="historyKindIcon(ev.kind)" :class="['size-2', historyKindColor(ev.kind)]" />
              </span>
              <div class="rounded-lg border border-default p-3 bg-elevated/20">
                <div class="flex items-center gap-2 flex-wrap text-xs">
                  <span class="font-mono text-muted">{{ ev.ts ? formatRelative(ev.ts) : '—' }}</span>
                  <UBadge
                    :label="ev.kind"
                    :color="ev.kind === 'git-commit' ? 'primary' : ev.kind === 'agent-move' ? 'warning' : 'error'"
                    variant="subtle"
                    size="xs"
                  />
                  <code v-if="ev.ref" class="font-mono text-muted">{{ ev.ref }}</code>
                  <span v-if="ev.author" class="text-muted">· {{ ev.author }}</span>
                </div>
                <p class="text-sm mt-1">{{ ev.summary }}</p>
              </div>
            </li>
          </ol>
        </section>

        <!-- PR95b v3.52.0 — YAML editor modal -->
        <UModal v-model:open="yamlEditorOpen" :ui="{ content: 'max-w-3xl' }">
          <template #content>
            <UCard>
              <template #header>
                <div class="flex items-center justify-between gap-3">
                  <div>
                    <h2 class="text-lg font-bold">Edit agent YAML</h2>
                    <p class="text-xs text-muted mt-0.5 font-mono">{{ agent?.id }}</p>
                  </div>
                  <UButton
                    icon="i-lucide-x"
                    variant="ghost"
                    size="sm"
                    :disabled="yamlEditorSaving"
                    @click="yamlEditorOpen = false"
                  />
                </div>
              </template>
              <UTextarea
                v-model="yamlEditorDraft"
                :rows="20"
                class="w-full font-mono text-xs"
              />
              <template #footer>
                <div class="flex items-center justify-between gap-2 text-xs">
                  <p class="text-muted">
                    Edits go through the same validator as PUT /api/agents/{id}/yaml —
                    parse + dict root + matching id. Tier 0 agents are locked.
                  </p>
                  <div class="flex gap-2 shrink-0">
                    <UButton
                      label="Cancel"
                      variant="ghost"
                      :disabled="yamlEditorSaving"
                      @click="yamlEditorOpen = false"
                    />
                    <UButton
                      label="Save"
                      icon="i-lucide-check"
                      color="primary"
                      :loading="yamlEditorSaving"
                      @click="saveYamlEditor"
                    />
                  </div>
                </div>
              </template>
            </UCard>
          </template>
        </UModal>

        <AgentEditDrawer
          v-model="editOpen"
          :agent="agent"
          @saved="onAgentSaved"
        />

        <!-- ===== TABS ===== -->
        <UTabs :items="tabs" default-value="dna" class="w-full">
          <template #content="{ item }">
            <!-- ===== TAB: DNA ===== -->
            <div v-if="item.value === 'dna'" class="space-y-6 mt-6">
              <!-- DNA Summary — 3 cards -->
              <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                <!-- Card 1: MBTI -->
                <UCard>
                  <div class="space-y-2">
                    <p class="text-sm font-semibold text-muted uppercase tracking-wide">MBTI</p>
                    <p class="text-4xl font-bold font-mono tracking-widest">
                      {{ agent.mbti || '----' }}
                    </p>
                    <p v-if="agent.mbti && mbtiDescriptions[agent.mbti]" class="text-sm text-muted">
                      {{ mbtiDescriptions[agent.mbti] }}
                    </p>
                  </div>
                </UCard>

                <!-- Card 2: Enneagram -->
                <UCard>
                  <div class="space-y-3">
                    <p class="text-sm font-semibold text-muted uppercase tracking-wide">Enneagram</p>
                    <div>
                      <p class="text-3xl font-bold">
                        Type {{ agent.enneagram?.type ?? '-' }}
                        <span v-if="agent.enneagram?.wing" class="text-xl font-normal text-muted">
                          w{{ agent.enneagram.wing }}
                        </span>
                      </p>
                      <p v-if="agent.enneagram?.label" class="text-sm text-muted mt-1">
                        {{ agent.enneagram.label }}
                      </p>
                    </div>

                    <div class="grid grid-cols-2 gap-2 pt-1">
                      <div class="rounded-lg bg-red-500/10 border border-red-500/20 p-2.5">
                        <p class="text-[10px] font-bold text-red-400 uppercase tracking-wider mb-1">Fear</p>
                        <p class="text-xs text-muted leading-snug">
                          {{ agent.enneagram?.core_fear ?? 'Unknown' }}
                        </p>
                      </div>
                      <div class="rounded-lg bg-emerald-500/10 border border-emerald-500/20 p-2.5">
                        <p class="text-[10px] font-bold text-emerald-400 uppercase tracking-wider mb-1">Drive</p>
                        <p class="text-xs text-muted leading-snug">
                          {{ agent.enneagram?.core_motivation ?? 'Unknown' }}
                        </p>
                      </div>
                    </div>
                  </div>
                </UCard>

                <!-- Card 3: DISC -->
                <UCard>
                  <div class="space-y-3">
                    <p class="text-sm font-semibold text-muted uppercase tracking-wide">DISC</p>
                    <div>
                      <p class="text-3xl font-bold font-mono">
                        {{ agent.disc?.primary ?? '' }}{{ agent.disc?.secondary ?? '' }}
                      </p>
                      <p v-if="agent.disc?.label" class="text-sm text-muted mt-1">
                        {{ agent.disc.label }}
                      </p>
                    </div>

                    <div class="space-y-2 pt-1">
                      <div v-for="letter in discLetters" :key="letter" class="flex items-center gap-2">
                        <span class="w-4 text-xs font-mono font-bold text-muted">{{ letter }}</span>
                        <div class="flex-1 h-2 rounded-full bg-muted/20">
                          <div
                            class="h-2 rounded-full transition-none"
                            :class="discBarColor(letter)"
                            :style="{ width: `${discBarValue(letter)}%` }"
                          />
                        </div>
                        <span class="w-6 text-right text-xs font-mono text-muted">
                          {{ discBarValue(letter) }}
                        </span>
                      </div>
                    </div>
                  </div>
                </UCard>
              </div>

              <!-- Big Five -->
              <UCard>
                <div class="space-y-1">
                  <p class="text-sm font-semibold text-muted uppercase tracking-wide mb-4">
                    Big Five (OCEAN)
                  </p>
                  <div v-if="agent.big_five" class="space-y-3">
                    <div
                      v-for="key in bigFiveKeys"
                      :key="key"
                      class="flex items-center gap-3"
                    >
                      <span class="w-36 text-sm text-muted">{{ bigFiveLabels[key] }}</span>
                      <div class="flex-1 h-2 rounded-full bg-muted/20">
                        <div
                          class="h-2 rounded-full transition-none"
                          :class="bigFiveBarColor(agent.big_five[key] ?? 0)"
                          :style="{ width: `${agent.big_five[key] ?? 0}%` }"
                        />
                      </div>
                      <span class="w-8 text-right text-sm font-mono">
                        {{ agent.big_five[key] ?? 0 }}
                      </span>
                    </div>
                  </div>
                  <p v-else class="text-sm text-muted">No Big Five data available.</p>
                </div>
              </UCard>
            </div>

            <!-- ===== TAB: COMMUNICATION ===== -->
            <div v-else-if="item.value === 'communication'" class="space-y-4 mt-6">
              <div v-if="agent.communication" class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <UCard>
                  <div class="space-y-4">
                    <div>
                      <p class="text-sm font-semibold text-muted uppercase tracking-wide mb-1">Tone</p>
                      <p class="text-sm">{{ agent.communication.tone ?? '-' }}</p>
                    </div>
                    <div>
                      <p class="text-sm font-semibold text-muted uppercase tracking-wide mb-1">Vocabulary Level</p>
                      <UBadge :label="agent.communication.vocabulary_level ?? '-'" variant="subtle" />
                    </div>
                    <div>
                      <p class="text-sm font-semibold text-muted uppercase tracking-wide mb-1">Language</p>
                      <p class="text-sm font-mono">{{ agent.communication.language ?? '-' }}</p>
                    </div>
                  </div>
                </UCard>

                <UCard>
                  <div class="space-y-4">
                    <div>
                      <p class="text-sm font-semibold text-muted uppercase tracking-wide mb-1">Preferred Format</p>
                      <p class="text-sm">{{ agent.communication.preferred_format ?? '-' }}</p>
                    </div>
                    <div v-if="agent.communication.avoid?.length">
                      <p class="text-sm font-semibold text-muted uppercase tracking-wide mb-2">Avoids</p>
                      <ul class="space-y-1.5">
                        <li
                          v-for="item in agent.communication.avoid"
                          :key="item"
                          class="flex items-start gap-2 text-sm text-muted"
                        >
                          <UIcon name="i-lucide-x" class="size-4 text-red-400 mt-0.5 shrink-0" />
                          {{ item }}
                        </li>
                      </ul>
                    </div>
                  </div>
                </UCard>
              </div>

              <!-- DISC Communication Details -->
              <UCard v-if="agent.disc?.communication_style || agent.disc?.under_pressure || agent.disc?.motivator">
                <div class="space-y-4">
                  <p class="text-sm font-semibold text-muted uppercase tracking-wide">DISC Communication Profile</p>
                  <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div v-if="agent.disc.communication_style">
                      <p class="text-xs text-muted mb-1">Communication Style</p>
                      <p class="text-sm">{{ agent.disc.communication_style }}</p>
                    </div>
                    <div v-if="agent.disc.under_pressure">
                      <p class="text-xs text-muted mb-1">Under Pressure</p>
                      <p class="text-sm">{{ agent.disc.under_pressure }}</p>
                    </div>
                    <div v-if="agent.disc.motivator">
                      <p class="text-xs text-muted mb-1">Motivator</p>
                      <p class="text-sm">{{ agent.disc.motivator }}</p>
                    </div>
                  </div>
                </div>
              </UCard>

              <div v-if="!agent.communication && !agent.disc?.communication_style" class="py-8 text-center">
                <p class="text-sm text-muted">No communication data available.</p>
              </div>
            </div>

            <!-- ===== TAB: MENTAL MODELS ===== -->
            <div v-else-if="item.value === 'models'" class="space-y-4 mt-6">
              <div v-if="agent.mental_models" class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <UCard>
                  <div class="space-y-3">
                    <p class="text-sm font-semibold text-muted uppercase tracking-wide">Primary Models</p>
                    <ul v-if="agent.mental_models.primary?.length" class="space-y-2">
                      <li
                        v-for="model in agent.mental_models.primary"
                        :key="model"
                        class="flex items-center gap-2"
                      >
                        <div class="size-1.5 rounded-full bg-primary shrink-0" />
                        <span class="text-sm font-medium">{{ model }}</span>
                      </li>
                    </ul>
                    <p v-else class="text-sm text-muted">None listed.</p>
                  </div>
                </UCard>

                <UCard>
                  <div class="space-y-3">
                    <p class="text-sm font-semibold text-muted uppercase tracking-wide">Secondary Models</p>
                    <ul v-if="agent.mental_models.secondary?.length" class="space-y-2">
                      <li
                        v-for="model in agent.mental_models.secondary"
                        :key="model"
                        class="flex items-center gap-2"
                      >
                        <div class="size-1.5 rounded-full bg-muted/40 shrink-0" />
                        <span class="text-sm text-muted">{{ model }}</span>
                      </li>
                    </ul>
                    <p v-else class="text-sm text-muted">None listed.</p>
                  </div>
                </UCard>
              </div>

              <div v-else class="py-8 text-center">
                <p class="text-sm text-muted">No mental model data available.</p>
              </div>
            </div>

            <!-- ===== TAB: AUTHORITY ===== -->
            <div v-else-if="item.value === 'authority'" class="space-y-4 mt-6">
              <div v-if="agent.authority">
                <UCard>
                  <div class="space-y-5">
                    <div>
                      <p class="text-sm font-semibold text-muted uppercase tracking-wide mb-3">Permissions</p>
                      <div class="flex flex-wrap gap-2">
                        <UBadge v-if="agent.authority.veto" label="Veto" color="error" variant="subtle" />
                        <UBadge v-if="agent.authority.approve_architecture" label="Approve Architecture" color="success" variant="subtle" />
                        <UBadge v-if="agent.authority.approve_budget" label="Approve Budget" color="success" variant="subtle" />
                        <UBadge v-if="agent.authority.approve_quality" label="Approve Quality" color="success" variant="subtle" />
                        <UBadge v-if="agent.authority.block_release" label="Block Release" color="error" variant="subtle" />
                        <UBadge v-if="agent.authority.orchestrate" label="Orchestrate" color="primary" variant="subtle" />
                      </div>
                    </div>

                    <div v-if="agent.authority.delegates_to?.length">
                      <p class="text-sm font-semibold text-muted uppercase tracking-wide mb-2">Delegates To</p>
                      <div class="flex flex-wrap gap-2">
                        <UBadge
                          v-for="d in agent.authority.delegates_to"
                          :key="d"
                          :label="d"
                          variant="outline"
                          size="sm"
                        />
                      </div>
                    </div>

                    <div v-if="agent.authority.escalates_to">
                      <p class="text-sm font-semibold text-muted uppercase tracking-wide mb-1">Escalates To</p>
                      <p class="text-sm font-mono">{{ agent.authority.escalates_to }}</p>
                    </div>

                    <div v-if="!agent.authority.escalates_to && !agent.authority.delegates_to?.length && !agent.authority.veto">
                      <p class="text-sm text-muted">Standard execution authority.</p>
                    </div>
                  </div>
                </UCard>
              </div>

              <div v-else class="py-8 text-center">
                <p class="text-sm text-muted">No authority data available.</p>
              </div>
            </div>

            <!-- ===== TAB: EXPERTISE ===== -->
            <div v-else-if="item.value === 'expertise'" class="space-y-4 mt-6">
              <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <UCard>
                  <div class="space-y-3">
                    <p class="text-sm font-semibold text-muted uppercase tracking-wide">Domains</p>
                    <div v-if="agent.expertise_domains?.length" class="flex flex-wrap gap-2">
                      <UBadge
                        v-for="d in agent.expertise_domains"
                        :key="d"
                        :label="d"
                        color="primary"
                        variant="subtle"
                        size="sm"
                      />
                    </div>
                    <p v-else class="text-sm text-muted">No domains listed.</p>
                  </div>
                </UCard>

                <UCard>
                  <div class="space-y-3">
                    <p class="text-sm font-semibold text-muted uppercase tracking-wide">Frameworks</p>
                    <ul v-if="agent.frameworks?.length" class="space-y-2">
                      <li
                        v-for="f in agent.frameworks"
                        :key="f"
                        class="flex items-center gap-2 text-sm"
                      >
                        <UIcon name="i-lucide-check" class="size-3.5 text-primary shrink-0" />
                        {{ f }}
                      </li>
                    </ul>
                    <p v-else class="text-sm text-muted">No frameworks listed.</p>
                  </div>
                </UCard>
              </div>

              <UCard v-if="agent.expertise_depth || agent.expertise_years">
                <div class="flex flex-wrap gap-6">
                  <div v-if="agent.expertise_depth">
                    <p class="text-sm font-semibold text-muted uppercase tracking-wide mb-1">Depth</p>
                    <UBadge
                      :label="agent.expertise_depth"
                      :color="(depthColor[agent.expertise_depth] ?? 'neutral') as any"
                      variant="subtle"
                      size="lg"
                    />
                  </div>
                  <div v-if="agent.expertise_years">
                    <p class="text-sm font-semibold text-muted uppercase tracking-wide mb-1">Experience</p>
                    <p class="text-2xl font-bold">
                      {{ agent.expertise_years }}
                      <span class="text-sm font-normal text-muted">years</span>
                    </p>
                  </div>
                </div>
              </UCard>
            </div>
          </template>
        </UTabs>
      </div>
    </template>
  </UDashboardPanel>
</template>
