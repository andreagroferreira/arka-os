<script setup lang="ts">
// Plan Canvas — review and decide on Forge plans (design direction
// validated by brand 2026-07-20: master-detail, Decision Rail as the
// page's single EKG-family signature, green budget = awaiting-review
// accent + approved badge + Approve button, keyboard-first).

interface PlanSummary {
  id: string
  name: string
  status: string
  tier: string
  confidence: number
  created_at: string
}

interface PlanPhase {
  name: string
  department: string
  agents: string[]
  deliverables: string[]
  acceptance_criteria: string[]
  depends_on: string[]
}

interface PlanDetail {
  id: string
  name: string
  created_at: string
  forged_by: string
  goal: string
  status: string
  approved_at: string | null
  approved_by: string | null
  rejected_at: string | null
  rejected_by: string | null
  executed_at: string | null
  review_note: string | null
  plan_phases: PlanPhase[]
  complexity: { score: number, tier: string }
  critic: {
    confidence: number
    // IdentifiedRisk serializes risk/mitigation/severity, not description.
    risks: { risk?: string, mitigation?: string, severity?: string }[]
    rejected_elements: { element?: string, reason?: string }[]
  }
  governance: {
    constitution_check: string
    violations: string[]
    quality_gate_required: boolean
  }
  execution_path: { type: string, target: string, departments: string[] }
  degraded: boolean
}

const { fetchApi, apiBase } = useApi()
const toast = useToast()
const confirm = useConfirmDialog()

const { data, status, error, refresh } = await fetchApi<{
  plans: PlanSummary[]
  active_id: string | null
}>('/api/plans')

const plans = computed(() => data.value?.plans ?? [])
const activeId = computed(() => data.value?.active_id ?? null)
const awaiting = computed(() =>
  plans.value.filter(p => ['draft', 'reviewing'].includes(p.status)).length
)
const executing = computed(() =>
  plans.value.filter(p => p.status === 'executing').length
)

const selectedId = ref<string | null>(null)
const detailPath = computed(() =>
  selectedId.value ? `/api/plans/${selectedId.value}` : ''
)
const {
  data: detailData,
  status: detailStatus,
  refresh: refreshDetail
} = await fetchApi<{ plan?: PlanDetail, legacy?: boolean, error?: string }>(
  () => detailPath.value,
  { immediate: false, watch: false }
)
// Explicit over reactive-URL magic: with immediate:false the watcher
// chain proved unreliable in the production build — refetch on select.
watch(selectedId, (id) => {
  if (id) refreshDetail()
})
const plan = computed(() => detailData.value?.plan ?? null)
const legacy = computed(() => detailData.value?.legacy === true)

// ── status vocabulary (green stays scarce: approved only) ──────────────
type BadgeColor = 'error' | 'primary' | 'info' | 'warning' | 'neutral'
type BadgeVariant = 'outline' | 'subtle'
const STATUS_BADGE: Record<string, { color: BadgeColor, variant: BadgeVariant }> = {
  draft: { color: 'neutral', variant: 'outline' },
  reviewing: { color: 'warning', variant: 'subtle' },
  approved: { color: 'primary', variant: 'subtle' },
  executing: { color: 'info', variant: 'subtle' },
  completed: { color: 'neutral', variant: 'subtle' },
  rejected: { color: 'error', variant: 'subtle' },
  cancelled: { color: 'neutral', variant: 'outline' },
  archived: { color: 'neutral', variant: 'outline' }
}
const badgeFor = (s: string) => STATUS_BADGE[s] ?? STATUS_BADGE.draft!

const decidable = computed(() =>
  plan.value && !legacy.value
    ? ['draft', 'reviewing'].includes(plan.value.status)
    : false
)

// ── selection + keyboard (j/k/enter/esc/a/r; inputs are guarded by
//    Nuxt UI's default usingInput=false) ─────────────────────────────────
const cursor = ref(0)
watch(plans, (list) => {
  if (cursor.value >= list.length) cursor.value = Math.max(0, list.length - 1)
})
const select = (id: string) => {
  selectedId.value = id
  cursor.value = plans.value.findIndex(p => p.id === id)
}
defineShortcuts({
  j: () => {
    if (plans.value.length) {
      cursor.value = Math.min(cursor.value + 1, plans.value.length - 1)
    }
  },
  k: () => {
    if (plans.value.length) cursor.value = Math.max(cursor.value - 1, 0)
  },
  enter: () => {
    const target = plans.value[cursor.value]
    if (target) select(target.id)
  },
  escape: () => { selectedId.value = null },
  a: () => { if (decidable.value) decide('approve') },
  r: () => { if (decidable.value) decide('reject') }
})

// ── tabs + raw escape-hatch ────────────────────────────────────────────
const tab = ref<'phases' | 'forge'>('phases')
const showRaw = ref(false)
watch(selectedId, () => {
  tab.value = 'phases'
  showRaw.value = false
})

// ── decision ───────────────────────────────────────────────────────────
const note = ref('')
const deciding = ref(false)
watch(selectedId, () => {
  note.value = ''
})

async function decide(action: 'approve' | 'reject') {
  if (!plan.value || deciding.value) return
  if (action === 'reject') {
    const ok = await confirm({
      title: `Reject "${plan.value.name}"`,
      description: 'The plan moves to rejected — a terminal state. '
        + 'Your note stays on the record as the rationale.',
      confirmLabel: 'Reject plan',
      variant: 'danger'
    })
    if (!ok) return
  }
  deciding.value = true
  try {
    const result = await $fetch<{ status?: string, error?: string }>(
      `${apiBase}/api/plans/${plan.value.id}/decision`,
      { method: 'POST', body: { action, note: note.value } }
    )
    if (result.error) {
      toast.add({ title: 'Decision refused', description: result.error, color: 'error' })
    } else {
      toast.add({
        title: action === 'approve' ? 'Plan approved' : 'Plan rejected',
        color: action === 'approve' ? 'primary' : 'neutral'
      })
      note.value = ''
      await Promise.all([refresh(), refreshDetail()])
    }
  } catch {
    toast.add({ title: 'Decision failed', description: 'API unreachable.', color: 'error' })
  } finally {
    deciding.value = false
  }
}

// ── Decision Rail (the signature): static line, real trail only ────────
const RAIL = ['draft', 'reviewing', 'approved', 'executing', 'completed']
const NEGATIVE = ['rejected', 'cancelled']
const railStations = computed(() => {
  if (!plan.value) return []
  const p = plan.value
  const negative = NEGATIVE.includes(p.status)
  const reachedIndex = negative
    ? RAIL.indexOf('reviewing')
    : RAIL.indexOf(p.status === 'archived' ? 'completed' : p.status)
  return RAIL.map((stage, i) => ({
    stage,
    reached: i <= reachedIndex,
    current: !negative && stage === (p.status === 'archived' ? 'completed' : p.status),
    detail: stage === 'draft' && p.created_at
      ? `forged ${formatWhen(p.created_at)}${p.forged_by ? ` · ${p.forged_by}` : ''}`
      : stage === 'approved' && p.approved_at
        ? `${formatWhen(p.approved_at)}${p.approved_by ? ` · ${p.approved_by}` : ''}`
        : stage === 'executing' && p.executed_at
          ? formatWhen(p.executed_at)
          : '',
    note: stage === 'approved' && p.status !== 'rejected' ? p.review_note : null
  }))
})
const negativeTerminal = computed(() => {
  if (!plan.value || !NEGATIVE.includes(plan.value.status)) return null
  const p = plan.value
  const trail = p.rejected_at
    ? `${formatWhen(p.rejected_at)}${p.rejected_by ? ` · ${p.rejected_by}` : ''}`
    : ''
  return {
    stage: p.status,
    detail: trail,
    note: p.review_note
  }
})

function formatWhen(iso: string): string {
  const d = new Date(iso)
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' })
      + ' ' + d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
}

// ── polling (ArkaLiveFeed cadence; paused when the tab is hidden) ──────
const visibility = useDocumentVisibility()
let poll: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  poll = setInterval(() => {
    if (visibility.value === 'visible') refresh()
  }, 15_000)
})
onBeforeUnmount(() => {
  if (poll) clearInterval(poll)
})
</script>

<template>
  <UDashboardPanel id="plan-canvas">
    <template #header>
      <UDashboardNavbar title="Plan Canvas">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <UButton
            icon="i-lucide-refresh-cw"
            color="neutral"
            variant="ghost"
            aria-label="Refresh plans"
            @click="() => refresh()"
          />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <DashboardState
        :status="status"
        :error="error"
        :empty="!plans.length"
        empty-title="No forge plans yet"
        empty-description="Plans land here when The Forge persists them — run /arka forge on a task."
        empty-icon="i-lucide-drafting-compass"
        :on-retry="() => refresh()"
      >
        <div class="mx-auto w-full max-w-6xl space-y-10 py-2">
          <ArkaPageHero
            numeral="I"
            label="plan canvas"
            title="The plan is the contract."
            subtitle="Read deeply, decide once, leave a trail — approval is an operator act, not a formality."
          >
            <template #stats>
              <div class="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
                <ArkaStatCard
                  label="awaiting review"
                  :value="awaiting"
                  accent
                  hint="draft + reviewing — the number that changes your next action"
                />
                <ArkaStatCard
                  label="executing"
                  :value="executing"
                  hint="approved and in motion"
                />
              </div>
            </template>
          </ArkaPageHero>

          <ArkaSection numeral="II" label="queue · review">
            <div class="grid grid-cols-1 gap-6 lg:grid-cols-5">
              <!-- master: the queue -->
              <div class="lg:col-span-2 space-y-1" role="listbox" aria-label="Forge plans">
                <button
                  v-for="(p, i) in plans"
                  :key="p.id"
                  type="button"
                  role="option"
                  :aria-selected="selectedId === p.id"
                  class="w-full rounded-md border px-3 py-2.5 text-left transition-colors duration-150 focus-visible:outline-2 focus-visible:outline-primary"
                  :class="[
                    selectedId === p.id
                      ? 'border-[var(--ui-border-accented)] bg-[var(--ui-bg-elevated)]'
                      : 'border-transparent hover:bg-[var(--ui-bg-elevated)]',
                    cursor === i ? 'ring-1 ring-[var(--ui-border-accented)]' : ''
                  ]"
                  @click="select(p.id)"
                >
                  <div class="flex items-center justify-between gap-2">
                    <span class="truncate text-sm font-medium">
                      {{ p.name || p.id }}
                    </span>
                    <UBadge
                      :color="badgeFor(p.status).color"
                      :variant="badgeFor(p.status).variant"
                      size="sm"
                      class="shrink-0 capitalize"
                    >
                      <UIcon
                        v-if="p.status === 'completed'"
                        name="i-lucide-check"
                        class="size-3"
                      />
                      {{ p.status }}
                    </UBadge>
                  </div>
                  <div class="mt-1 flex items-center gap-3 text-xs text-muted">
                    <span class="arka-data">{{ p.tier }}</span>
                    <span class="arka-data">conf {{ (p.confidence ?? 0).toFixed(2) }}</span>
                    <span v-if="p.id === activeId" class="arka-eyebrow">active</span>
                  </div>
                </button>
                <p class="px-3 pt-2 text-[11px] text-muted">
                  <kbd>j</kbd>/<kbd>k</kbd> navigate · <kbd>↵</kbd> open ·
                  <kbd>esc</kbd> close · <kbd>a</kbd> approve · <kbd>r</kbd> reject
                </p>
              </div>

              <!-- detail: review pane + Decision Rail -->
              <div class="lg:col-span-3">
                <ArkaGlowCard v-if="plan" :live="decidable">
                  <div class="grid grid-cols-1 gap-6 xl:grid-cols-[1fr_215px]">
                    <div class="min-w-0 space-y-4">
                      <header class="space-y-1">
                        <div class="flex items-start justify-between gap-3">
                          <h2 class="arka-serif-title text-2xl leading-tight">
                            {{ plan.name || plan.id }}
                          </h2>
                          <UButton
                            :label="showRaw ? 'hide raw' : 'raw'"
                            color="neutral"
                            variant="ghost"
                            size="xs"
                            icon="i-lucide-braces"
                            :aria-expanded="showRaw"
                            @click="showRaw = !showRaw"
                          />
                        </div>
                        <p class="arka-data text-xs text-muted">
                          {{ plan.id }}
                        </p>
                        <p v-if="plan.goal" class="text-sm text-muted">
                          {{ plan.goal }}
                        </p>
                        <UBadge
                          v-if="plan.degraded"
                          color="warning"
                          variant="subtle"
                          size="sm"
                        >
                          degraded forge — constitution phases only
                        </UBadge>
                        <UBadge
                          v-if="legacy"
                          color="neutral"
                          variant="outline"
                          size="sm"
                        >
                          legacy format — read-only
                        </UBadge>
                      </header>

                      <pre
                        v-if="showRaw"
                        class="arka-data max-h-72 overflow-auto rounded-md border border-[var(--ui-border)] bg-[var(--ui-bg)] p-3 text-[11px] leading-relaxed"
                      >{{ JSON.stringify(plan, null, 2) }}</pre>

                      <nav class="flex gap-1 border-b border-[var(--ui-border)]" aria-label="Plan views">
                        <button
                          v-for="t in (['phases', 'forge'] as const)"
                          :key="t"
                          type="button"
                          class="arka-eyebrow px-3 py-2 transition-colors duration-150"
                          :class="tab === t
                            ? 'border-b-2 border-primary text-[var(--ui-text)]'
                            : 'text-muted hover:text-[var(--ui-text)]'"
                          :aria-current="tab === t ? 'true' : undefined"
                          @click="tab = t"
                        >
                          {{ t }}
                        </button>
                      </nav>

                      <!-- phases: stacked cards to READ (the rail is the
                           page's only vertical stepper) -->
                      <div v-if="tab === 'phases'" class="space-y-3">
                        <div
                          v-for="(phase, i) in plan.plan_phases"
                          :key="phase.name"
                          class="rounded-md border border-[var(--ui-border)] p-3"
                        >
                          <div class="flex items-center justify-between gap-2">
                            <p class="text-sm font-medium">
                              <span class="arka-numeral mr-1.5">{{ i + 1 }}</span>
                              {{ phase.name }}
                            </p>
                            <span class="arka-eyebrow shrink-0">{{ phase.department }}</span>
                          </div>
                          <ul
                            v-if="phase.deliverables.length"
                            class="mt-2 space-y-1 text-xs text-muted"
                          >
                            <li v-for="d in phase.deliverables" :key="d" class="flex gap-2">
                              <span aria-hidden="true">—</span><span>{{ d }}</span>
                            </li>
                          </ul>
                          <p
                            v-if="phase.acceptance_criteria.length"
                            class="mt-2 text-[11px] text-muted"
                          >
                            <span class="arka-eyebrow">accepts</span>
                            {{ phase.acceptance_criteria.join(' · ') }}
                          </p>
                        </div>
                        <p v-if="!plan.plan_phases.length" class="text-sm text-muted">
                          This plan carries no phases — inspect the raw payload.
                        </p>
                      </div>

                      <!-- forge: complexity, critic, governance -->
                      <div v-else class="space-y-4 text-sm">
                        <div class="grid grid-cols-2 gap-3">
                          <div class="rounded-md border border-[var(--ui-border)] p-3">
                            <p class="arka-eyebrow">
                              complexity
                            </p>
                            <p class="mt-1">
                              <span class="arka-data text-lg">{{ plan.complexity.score }}</span>
                              <span class="ml-2 text-xs text-muted">{{ plan.complexity.tier }}</span>
                            </p>
                          </div>
                          <div class="rounded-md border border-[var(--ui-border)] p-3">
                            <p class="arka-eyebrow">
                              critic confidence
                            </p>
                            <p class="arka-data mt-1 text-lg">
                              {{ (plan.critic.confidence ?? 0).toFixed(2) }}
                            </p>
                          </div>
                        </div>
                        <div v-if="plan.critic.risks.length">
                          <p class="arka-eyebrow mb-1.5">
                            risks identified
                          </p>
                          <ul class="space-y-1 text-xs text-muted">
                            <li v-for="(risk, i) in plan.critic.risks" :key="i" class="flex flex-col gap-0.5">
                              <span>
                                <span class="mr-1.5 uppercase">{{ risk.severity || 'risk' }}</span>
                                {{ risk.risk || '—' }}
                              </span>
                              <span v-if="risk.mitigation" class="pl-1 italic">
                                → {{ risk.mitigation }}
                              </span>
                            </li>
                          </ul>
                        </div>
                        <div>
                          <p class="arka-eyebrow mb-1.5">
                            governance
                          </p>
                          <p class="text-xs text-muted">
                            constitution: {{ plan.governance.constitution_check }}
                            · quality gate:
                            {{ plan.governance.quality_gate_required ? 'required' : 'not required' }}
                            · path: {{ plan.execution_path.type }}
                            <template v-if="plan.execution_path.target">
                              → {{ plan.execution_path.target }}
                            </template>
                          </p>
                          <p
                            v-if="plan.governance.violations.length"
                            class="mt-1 text-xs text-error"
                          >
                            violations: {{ plan.governance.violations.join('; ') }}
                          </p>
                        </div>
                      </div>
                    </div>

                    <!-- The Decision Rail: static line, stations, real trail.
                         Only the current station pulses. -->
                    <aside aria-label="Plan lifecycle and decision">
                      <ol class="relative ml-2 border-l border-[var(--ui-border)] pl-5">
                        <li
                          v-for="station in railStations"
                          :key="station.stage"
                          class="relative pb-5 last:pb-0"
                        >
                          <span
                            class="absolute -left-[27px] top-0.5 flex size-3 items-center justify-center"
                            aria-hidden="true"
                          >
                            <span v-if="station.current" class="arka-live-dot" />
                            <span
                              v-else
                              class="size-1.5 rounded-full"
                              :class="station.reached
                                ? 'bg-[var(--ui-text-muted)]'
                                : 'bg-[var(--ui-border)]'"
                            />
                          </span>
                          <p
                            class="arka-eyebrow"
                            :class="station.current
                              ? 'text-[var(--ui-text)]'
                              : station.reached ? '' : 'opacity-40'"
                          >
                            {{ station.stage }}
                          </p>
                          <p v-if="station.detail" class="arka-data mt-0.5 text-[10px] text-muted">
                            {{ station.detail }}
                          </p>
                          <p
                            v-if="station.note"
                            class="mt-1 border-l-2 border-[var(--ui-border)] pl-2 text-[11px] italic text-muted"
                          >
                            {{ station.note }}
                          </p>
                        </li>
                      </ol>

                      <!-- negative terminal leaves the line (deviation IS
                           the meaning) -->
                      <div
                        v-if="negativeTerminal"
                        class="ml-6 mt-3 rounded-md border border-dashed border-[var(--ui-border)] p-2.5"
                      >
                        <p class="arka-eyebrow capitalize text-muted">
                          {{ negativeTerminal.stage }}
                        </p>
                        <p
                          v-if="negativeTerminal.detail"
                          class="arka-data mt-0.5 text-[10px] text-muted"
                        >
                          {{ negativeTerminal.detail }}
                        </p>
                        <p
                          v-if="negativeTerminal.note"
                          class="mt-1 text-[11px] italic text-muted"
                        >
                          {{ negativeTerminal.note }}
                        </p>
                      </div>

                      <!-- decision zone: anchored at the rail, one primary CTA -->
                      <div v-if="decidable" class="mt-5 space-y-2.5">
                        <UTextarea
                          v-model="note"
                          placeholder="Decision note (lands on the record)"
                          :rows="3"
                          class="w-full"
                          aria-label="Decision note"
                        />
                        <div class="flex flex-col gap-2">
                          <UButton
                            label="Approve plan"
                            color="primary"
                            icon="i-lucide-check"
                            block
                            :loading="deciding"
                            @click="decide('approve')"
                          />
                          <UButton
                            label="Reject"
                            color="neutral"
                            variant="outline"
                            icon="i-lucide-x"
                            block
                            :disabled="deciding"
                            @click="decide('reject')"
                          />
                        </div>
                      </div>
                    </aside>
                  </div>
                </ArkaGlowCard>

                <div
                  v-else
                  class="flex h-full min-h-48 items-center justify-center rounded-md border border-dashed border-[var(--ui-border)]"
                >
                  <p v-if="detailStatus === 'pending'" class="text-sm text-muted" role="status">
                    <UIcon name="i-lucide-loader-2" class="mr-1 inline size-4 animate-spin" />
                    loading plan…
                  </p>
                  <p v-else class="max-w-56 text-center text-sm text-muted">
                    Select a plan to review — the queue stays in sight while you read.
                  </p>
                </div>
              </div>
            </div>
          </ArkaSection>
        </div>
      </DashboardState>
    </template>
  </UDashboardPanel>
</template>
