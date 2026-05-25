<script setup lang="ts">
// PR70 v2.87.0 — Health page polish.
// - 30s auto-refresh (paused while tab is hidden) + manual refresh
// - Last-checked timestamp in header
// - Severity-aware rendering (fail = red, warn = yellow)
// - Copy-fix button when a check has a fix command
// - Healthy banner ignores warnings (only blocking failures matter)

interface HealthCheck {
  name: string
  passed: boolean
  fix: string
  severity: 'fail' | 'warn'
}

interface HealthPayload {
  checks: HealthCheck[]
  passed: number
  total: number
  failed_blocking: number
  warning_count: number
  healthy: boolean
  ts: string
}

const { fetchApi } = useApi()
const toast = useToast()

const {
  data,
  status,
  error,
  refresh,
} = await fetchApi<HealthPayload>('/api/health')

// ─── Auto-refresh ───────────────────────────────────────────────────────

let pollTimer: ReturnType<typeof setInterval> | null = null

function startPolling() {
  stopPolling()
  pollTimer = setInterval(() => {
    refresh()
  }, 30_000)
}

function stopPolling() {
  if (pollTimer !== null) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function handleVisibility() {
  if (typeof document === 'undefined') return
  if (document.hidden) {
    stopPolling()
  } else {
    refresh()
    startPolling()
  }
}

onMounted(() => {
  if (typeof document !== 'undefined') {
    document.addEventListener('visibilitychange', handleVisibility)
  }
  startPolling()
})

onBeforeUnmount(() => {
  stopPolling()
  if (typeof document !== 'undefined') {
    document.removeEventListener('visibilitychange', handleVisibility)
  }
})

// ─── Copy fix ───────────────────────────────────────────────────────────

const copied = ref<string | null>(null)
let copyTimer: ReturnType<typeof setTimeout> | null = null

async function copyFix(check: HealthCheck) {
  if (!check.fix) return
  if (typeof navigator === 'undefined' || !navigator.clipboard) {
    toast.add({ title: 'Clipboard unavailable', color: 'warning' })
    return
  }
  try {
    await navigator.clipboard.writeText(check.fix)
    copied.value = check.name
    if (copyTimer) clearTimeout(copyTimer)
    copyTimer = setTimeout(() => { copied.value = null; copyTimer = null }, 1500)
    toast.add({
      title: 'Fix copied',
      description: check.fix,
      color: 'success',
    })
  } catch (err) {
    toast.add({
      title: 'Copy failed',
      description: err instanceof Error ? err.message : 'unknown error',
      color: 'error',
    })
  }
}

onBeforeUnmount(() => {
  if (copyTimer) clearTimeout(copyTimer)
})

// ─── Format helpers ─────────────────────────────────────────────────────

function formatTs(iso: string | undefined): string {
  if (!iso) return ''
  try {
    return new Intl.DateTimeFormat('en-US', {
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    }).format(new Date(iso))
  } catch {
    return iso
  }
}

type CheckStatus = 'pass' | 'warn' | 'fail'

function statusOf(c: HealthCheck): CheckStatus {
  if (c.passed) return 'pass'
  return c.severity === 'warn' ? 'warn' : 'fail'
}

const STATUS_META: Record<CheckStatus, { icon: string; color: string; label: string }> = {
  pass: { icon: 'i-lucide-check-circle', color: 'text-green-500',  label: 'Pass' },
  warn: { icon: 'i-lucide-alert-circle',  color: 'text-yellow-500', label: 'Warn' },
  fail: { icon: 'i-lucide-x-circle',      color: 'text-red-500',    label: 'Fail' },
}

function statusBadgeColor(s: CheckStatus): 'success' | 'warning' | 'error' {
  return s === 'pass' ? 'success' : s === 'warn' ? 'warning' : 'error'
}

// ─── Aggregate display ──────────────────────────────────────────────────

const checks = computed<HealthCheck[]>(() => data.value?.checks ?? [])
const passed = computed(() => data.value?.passed ?? 0)
const total = computed(() => data.value?.total ?? 0)
const failedBlocking = computed(() => data.value?.failed_blocking ?? 0)
const warningCount = computed(() => data.value?.warning_count ?? 0)
const allPassed = computed(() => failedBlocking.value === 0 && warningCount.value === 0 && total.value > 0)
const someWarnings = computed(() => failedBlocking.value === 0 && warningCount.value > 0)
</script>

<template>
  <UDashboardPanel id="health">
    <template #header>
      <UDashboardNavbar title="Health Checks">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #trailing>
          <span
            v-if="data?.ts"
            class="text-xs text-muted"
            :title="data.ts"
          >
            Last checked {{ formatTs(data.ts) }}
          </span>
          <UBadge
            v-if="data"
            :label="`${passed}/${total}`"
            :color="allPassed ? 'success' : someWarnings ? 'warning' : 'error'"
            variant="subtle"
            class="ml-3"
          />
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
        :empty="!checks.length"
        empty-title="No health checks available"
        empty-icon="i-lucide-heart-pulse"
        loading-label="Loading health checks"
        :on-retry="() => refresh()"
      >
        <!-- Overall banner -->
        <div
          class="mb-6 rounded-lg border p-6 text-center"
          :class="allPassed
            ? 'border-green-500/30 bg-green-500/5'
            : someWarnings
              ? 'border-yellow-500/30 bg-yellow-500/5'
              : 'border-red-500/30 bg-red-500/5'"
        >
          <UIcon
            :name="allPassed
              ? 'i-lucide-check-circle'
              : someWarnings
                ? 'i-lucide-alert-circle'
                : 'i-lucide-x-circle'"
            :class="allPassed
              ? 'text-green-500'
              : someWarnings ? 'text-yellow-500' : 'text-red-500'"
            class="size-12"
          />
          <p class="mt-2 text-lg font-semibold text-highlighted">
            <template v-if="allPassed">All Checks Passing</template>
            <template v-else-if="someWarnings">
              {{ warningCount }} Warning{{ warningCount === 1 ? '' : 's' }}
            </template>
            <template v-else>
              {{ failedBlocking }} Blocking Failure{{ failedBlocking === 1 ? '' : 's' }}
            </template>
          </p>
          <p class="text-sm text-muted">
            {{ passed }} of {{ total }} checks passed
            <template v-if="warningCount && failedBlocking">
              · {{ warningCount }} warn · {{ failedBlocking }} blocking
            </template>
          </p>
        </div>

        <!-- Check list -->
        <div class="space-y-3">
          <div
            v-for="check in checks"
            :key="check.name"
            class="flex items-start gap-3 rounded-lg border p-4"
            :class="{
              'border-default': check.passed,
              'border-yellow-500/30 bg-yellow-500/5': !check.passed && check.severity === 'warn',
              'border-red-500/30 bg-red-500/5': !check.passed && check.severity === 'fail',
            }"
          >
            <UIcon
              :name="STATUS_META[statusOf(check)].icon"
              :class="STATUS_META[statusOf(check)].color"
              class="mt-0.5 size-5 shrink-0"
            />
            <div class="flex-1 min-w-0">
              <h4 class="font-medium text-highlighted">{{ check.name }}</h4>
              <p v-if="!check.passed && check.fix" class="mt-1 text-sm text-muted">
                Fix: <code class="font-mono text-xs">{{ check.fix }}</code>
              </p>
            </div>
            <UButton
              v-if="!check.passed && check.fix"
              :icon="copied === check.name ? 'i-lucide-check' : 'i-lucide-copy'"
              :color="copied === check.name ? 'success' : 'neutral'"
              variant="ghost"
              size="xs"
              aria-label="Copy fix command"
              @click="copyFix(check)"
            />
            <UBadge
              :label="STATUS_META[statusOf(check)].label"
              :color="statusBadgeColor(statusOf(check))"
              variant="subtle"
              size="sm"
              class="shrink-0"
            />
          </div>
        </div>
      </DashboardState>
    </template>
  </UDashboardPanel>
</template>
