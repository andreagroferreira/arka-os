<script setup lang="ts">
// PR88b v3.24.0 — Workflows browser.
//
// Lists every YAML workflow under departments/*/workflows/*.yaml with
// metadata pulled from the file's frontmatter-ish top keys. Selecting
// a row opens a side panel with the raw YAML for inspection.

import type { TableColumn } from '@nuxt/ui'

interface WorkflowPhase {
  id: string
  name: string
  description: string
  gate_type: string
  agent_count: number
  agent_ids?: string[]
}

interface Workflow {
  id: string
  name: string
  description: string
  department: string
  tier: string
  command: string
  phases_count: number
  phases: WorkflowPhase[]
  file: string
  content: string
}

const { fetchApi, apiBase } = useApi()
const toast = useToast()
const { data, status, error, refresh } = await fetchApi<{ workflows: Workflow[] }>('/api/workflows')

// PR94d v3.50.0 — inline YAML editor state.
const editingYaml = ref(false)
const yamlDraft = ref('')
const savingYaml = ref(false)

function startEditYaml() {
  if (!selected.value) return
  yamlDraft.value = selected.value.content
  editingYaml.value = true
}

function cancelEditYaml() {
  yamlDraft.value = ''
  editingYaml.value = false
}

async function saveYaml() {
  if (!selected.value) return
  savingYaml.value = true
  try {
    const res = await $fetch<{ updated?: boolean, error?: string }>(
      `${apiBase}/api/workflows/${selected.value.id}/yaml`,
      { method: 'PUT', body: { content: yamlDraft.value } },
    )
    if (res.error) throw new Error(res.error)
    toast.add({
      title: 'YAML updated',
      description: selected.value.file,
      color: 'success',
      icon: 'i-lucide-check',
    })
    // Patch local content so the preview shows the new YAML immediately.
    selected.value = { ...selected.value, content: yamlDraft.value }
    editingYaml.value = false
    await refresh()
  } catch (err) {
    toast.add({
      title: 'Save failed',
      description: err instanceof Error ? err.message : 'unknown error',
      color: 'error',
    })
  } finally {
    savingYaml.value = false
  }
}

// PR89b v3.28.0 — recent runs for the selected workflow.
interface WorkflowRun {
  session_id: string
  started_at: string
  ended_at: string
  duration_s: number | null
  calls: number
  cost_usd: number | null
  tokens_in: number
  tokens_out: number
}
const runs = ref<WorkflowRun[]>([])
const runsLoading = ref(false)
const sidePanelTab = ref<'flow' | 'yaml' | 'runs'>('flow')

function gateColor(gateType: string): 'primary' | 'warning' | 'error' | 'neutral' {
  const m: Record<string, 'primary' | 'warning' | 'error' | 'neutral'> = {
    user_approval: 'warning',
    quality_gate: 'error',
    automatic: 'primary',
  }
  return m[gateType] ?? 'neutral'
}

// PR98c v3.65.0 — copy a workflow's command to the clipboard so the
// operator can paste it into their runtime (Claude Code / Codex / Gemini).
// We can't run workflows from the dashboard — they orchestrate through
// the runtime's skill system, not via subprocess.
async function copyCommand(cmd: string) {
  if (!cmd || typeof navigator === 'undefined' || !navigator.clipboard) return
  try {
    await navigator.clipboard.writeText(cmd)
    toast.add({
      title: 'Command copied',
      description: `${cmd} — paste into your runtime to run`,
      color: 'success',
      icon: 'i-lucide-clipboard-check',
    })
  } catch {
    toast.add({
      title: 'Clipboard failed',
      description: 'Browser blocked clipboard access',
      color: 'error',
    })
  }
}

async function loadRuns(id: string) {
  runsLoading.value = true
  try {
    const res = await $fetch<{ runs: WorkflowRun[] }>(
      `${apiBase}/api/workflows/${id}/runs?limit=10`,
    )
    runs.value = res.runs ?? []
  } catch {
    runs.value = []
  } finally {
    runsLoading.value = false
  }
}

const workflows = computed(() => data.value?.workflows ?? [])
const search = ref('')
const deptFilter = ref<'all' | string>('all')
const selected = ref<Workflow | null>(null)

const departments = computed(() => {
  const set = new Set<string>()
  for (const w of workflows.value) if (w.department) set.add(w.department)
  return [
    { label: 'All departments', value: 'all' },
    ...Array.from(set).sort().map((d) => ({ label: d, value: d })),
  ]
})

const filtered = computed(() => {
  let result = workflows.value
  if (deptFilter.value !== 'all') {
    result = result.filter((w) => w.department === deptFilter.value)
  }
  const q = search.value.toLowerCase().trim()
  if (q) {
    result = result.filter((w) =>
      w.name.toLowerCase().includes(q)
      || w.description.toLowerCase().includes(q)
      || w.command.toLowerCase().includes(q)
      || w.id.toLowerCase().includes(q),
    )
  }
  return result
})

const tierColor = (tier: string) => {
  const m: Record<string, 'primary' | 'success' | 'warning' | 'neutral'> = {
    enterprise: 'primary',
    focused: 'success',
    specialist: 'warning',
  }
  return m[tier] ?? 'neutral'
}

const columns: TableColumn<Workflow>[] = [
  { accessorKey: 'name', header: 'Name' },
  { accessorKey: 'department', header: 'Department' },
  { accessorKey: 'tier', header: 'Tier' },
  { accessorKey: 'command', header: 'Command' },
  { accessorKey: 'phases_count', header: 'Phases' },
]
</script>

<template>
  <UDashboardPanel id="workflows">
    <template #header>
      <UDashboardNavbar title="Workflows">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #trailing>
          <UBadge v-if="workflows.length" :label="String(workflows.length)" variant="subtle" />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <DashboardState
        :status="status"
        :error="error"
        :empty="!workflows.length"
        empty-title="No workflows found"
        empty-description="YAML workflows live under departments/*/workflows/."
        empty-icon="i-lucide-workflow"
        loading-label="Scanning workflows"
        :on-retry="() => refresh()"
      >
        <div class="flex flex-wrap items-center gap-3 mb-4">
          <UInput
            v-model="search"
            class="max-w-sm"
            icon="i-lucide-search"
            placeholder="Search name, command, description…"
          />
          <USelect
            v-model="deptFilter"
            :items="departments"
            placeholder="Department"
            class="min-w-44"
          />
          <span class="ml-auto text-xs text-muted">
            {{ filtered.length }} workflow{{ filtered.length === 1 ? '' : 's' }}
          </span>
        </div>

        <div class="grid grid-cols-1 xl:grid-cols-[1.4fr_1fr] gap-4">
          <UTable
            :data="filtered"
            :columns="columns"
            :loading="status === 'pending'"
            :ui="{
              tbody: '[&>tr]:cursor-pointer [&>tr]:hover:bg-elevated/50 [&>tr]:transition-colors',
              th: 'py-2 first:rounded-l-lg last:rounded-r-lg border-y border-default first:border-l last:border-r',
              td: 'border-b border-default',
            }"
            @select="(row: { original: Workflow }) => { selected = row.original; sidePanelTab = 'flow'; runs = []; editingYaml = false; loadRuns(row.original.id) }"
          >
            <template #name-cell="{ row }">
              <div class="min-w-0">
                <p class="font-medium truncate">{{ row.original.name }}</p>
                <p class="text-xs text-muted font-mono truncate">{{ row.original.id }}</p>
              </div>
            </template>
            <template #department-cell="{ row }">
              <UBadge :label="row.original.department" variant="subtle" size="sm" />
            </template>
            <template #tier-cell="{ row }">
              <UBadge
                v-if="row.original.tier"
                :label="row.original.tier"
                :color="tierColor(row.original.tier)"
                variant="subtle"
                size="sm"
              />
              <span v-else class="text-xs text-muted">—</span>
            </template>
            <template #command-cell="{ row }">
              <code v-if="row.original.command" class="text-xs font-mono">{{ row.original.command }}</code>
              <span v-else class="text-xs text-muted">—</span>
            </template>
            <template #phases_count-cell="{ row }">
              <span class="font-mono text-sm">{{ row.original.phases_count }}</span>
            </template>
          </UTable>

          <div
            v-if="selected"
            class="rounded-lg border border-default overflow-hidden flex flex-col"
          >
            <div class="px-4 py-3 border-b border-default bg-elevated/30">
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                  <p class="text-xs text-muted uppercase tracking-wide">Workflow</p>
                  <p class="font-semibold truncate">{{ selected.name }}</p>
                  <p class="text-xs text-muted font-mono truncate">{{ selected.file }}</p>
                </div>
                <div class="flex items-center gap-1">
                  <UButton
                    v-if="selected.command"
                    label="Copy command"
                    icon="i-lucide-clipboard-copy"
                    variant="soft"
                    color="primary"
                    size="xs"
                    @click="copyCommand(selected.command)"
                  />
                  <UButton
                    icon="i-lucide-x"
                    variant="ghost"
                    size="xs"
                    aria-label="Close preview"
                    @click="selected = null"
                  />
                </div>
              </div>
              <p v-if="selected.description" class="text-xs text-muted mt-2">
                {{ selected.description }}
              </p>
              <div class="flex items-center gap-1 mt-3 text-xs">
                <button
                  type="button"
                  class="px-2 py-1 rounded-md transition-colors"
                  :class="sidePanelTab === 'flow' ? 'bg-elevated/60 text-default font-semibold' : 'text-muted hover:text-default'"
                  @click="sidePanelTab = 'flow'"
                >
                  Flow
                </button>
                <button
                  type="button"
                  class="px-2 py-1 rounded-md transition-colors"
                  :class="sidePanelTab === 'yaml' ? 'bg-elevated/60 text-default font-semibold' : 'text-muted hover:text-default'"
                  @click="sidePanelTab = 'yaml'"
                >
                  YAML
                </button>
                <button
                  type="button"
                  class="px-2 py-1 rounded-md transition-colors"
                  :class="sidePanelTab === 'runs' ? 'bg-elevated/60 text-default font-semibold' : 'text-muted hover:text-default'"
                  @click="sidePanelTab = 'runs'"
                >
                  Runs
                </button>
              </div>
            </div>
            <div v-if="sidePanelTab === 'flow'" class="p-4">
              <ol v-if="selected.phases.length > 0" class="relative border-l border-default ml-2 space-y-3">
                <li
                  v-for="(ph, idx) in selected.phases"
                  :key="ph.id || idx"
                  class="ml-4"
                >
                  <span class="absolute -left-1.5 size-3 rounded-full bg-primary border border-primary/60" />
                  <div class="rounded-lg border border-default p-3 bg-elevated/20">
                    <div class="flex items-center gap-2 flex-wrap">
                      <span class="font-mono text-xs text-muted">{{ idx + 1 }}.</span>
                      <span class="font-semibold">{{ ph.name || ph.id }}</span>
                      <UBadge
                        v-if="ph.gate_type"
                        :label="ph.gate_type"
                        :color="gateColor(ph.gate_type)"
                        variant="subtle"
                        size="xs"
                      />
                    </div>
                    <p v-if="ph.description" class="text-xs text-muted mt-1">
                      {{ ph.description }}
                    </p>
                    <!-- PR93a v3.43.0 — clickable agent badges -->
                    <div v-if="ph.agent_ids && ph.agent_ids.length > 0" class="flex flex-wrap gap-1 mt-2">
                      <NuxtLink
                        v-for="aid in ph.agent_ids"
                        :key="aid"
                        :to="`/agents/${aid}`"
                        class="inline-flex items-center gap-1 rounded-md border border-default px-1.5 py-0.5 text-[10px] font-mono hover:border-primary/40 hover:text-primary transition-colors"
                      >
                        <UIcon name="i-lucide-user" class="size-2.5" />
                        {{ aid }}
                      </NuxtLink>
                    </div>
                  </div>
                </li>
              </ol>
              <div v-else class="py-6 text-center text-sm text-muted">
                No phases defined.
              </div>
            </div>
            <div v-else-if="sidePanelTab === 'yaml'" class="flex flex-col">
              <div class="px-4 py-2 border-b border-default flex items-center justify-between text-xs">
                <span class="text-muted font-mono">{{ selected.file }}</span>
                <div class="flex items-center gap-2">
                  <template v-if="!editingYaml">
                    <UButton
                      label="Edit"
                      icon="i-lucide-pencil"
                      size="xs"
                      variant="soft"
                      @click="startEditYaml"
                    />
                  </template>
                  <template v-else>
                    <UButton
                      label="Cancel"
                      variant="ghost"
                      size="xs"
                      :disabled="savingYaml"
                      @click="cancelEditYaml"
                    />
                    <UButton
                      label="Save"
                      icon="i-lucide-check"
                      color="primary"
                      size="xs"
                      :loading="savingYaml"
                      @click="saveYaml"
                    />
                  </template>
                </div>
              </div>
              <div v-if="!editingYaml" class="overflow-x-auto">
                <pre class="p-4 text-xs font-mono whitespace-pre">{{ selected.content }}</pre>
              </div>
              <UTextarea
                v-else
                v-model="yamlDraft"
                :rows="20"
                class="m-2 font-mono text-xs"
              />
            </div>
            <div v-else class="p-4">
              <div v-if="runsLoading" class="py-6 text-center text-sm text-muted">
                <UIcon name="i-lucide-loader-2" class="size-4 animate-spin inline" /> Loading…
              </div>
              <div v-else-if="!runs.length" class="py-6 text-center text-sm text-muted">
                <UIcon name="i-lucide-history" class="size-6 mx-auto mb-2" />
                No recorded runs yet. Set
                <code class="font-mono text-xs">ARKA_CALL_CATEGORY=workflow:{{ selected.id }}</code>
                in the orchestrator to populate this.
              </div>
              <ul v-else class="space-y-2">
                <li
                  v-for="r in runs"
                  :key="r.session_id"
                  class="rounded-lg border border-default p-3"
                >
                  <div class="flex items-center justify-between gap-3 text-xs">
                    <span class="font-mono text-muted truncate">{{ r.session_id }}</span>
                    <span class="text-muted shrink-0">{{ r.started_at }}</span>
                  </div>
                  <div class="flex items-center gap-3 text-xs mt-2">
                    <span>
                      <span class="text-muted">Calls</span>
                      <span class="font-mono font-semibold ml-1">{{ r.calls }}</span>
                    </span>
                    <span>
                      <span class="text-muted">Cost</span>
                      <span class="font-mono font-semibold ml-1">
                        {{ r.cost_usd === null ? '—' : `$${r.cost_usd.toFixed(3)}` }}
                      </span>
                    </span>
                    <span v-if="r.duration_s !== null">
                      <span class="text-muted">Duration</span>
                      <span class="font-mono font-semibold ml-1">{{ r.duration_s }}s</span>
                    </span>
                  </div>
                </li>
              </ul>
            </div>
          </div>
          <div
            v-else
            class="rounded-lg border border-dashed border-default p-8 text-center text-sm text-muted self-start"
          >
            Click a row to preview its YAML.
          </div>
        </div>
      </DashboardState>
    </template>
  </UDashboardPanel>
</template>
