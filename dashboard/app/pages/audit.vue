<script setup lang="ts">
// PR90d v3.34.0 — Audit log page.
//
// Lists hook bypass / block events from the enforcement telemetry log.
// Operators filter by kind (bypass / blocked) and tool name.

interface AuditEvent {
  ts: string
  tool: string
  reason: string
  cwd: string
  bypass_used: boolean
  kind: 'bypass' | 'blocked'
}

const { fetchApi } = useApi()

const kind = ref<'all' | 'bypass' | 'blocked'>('all')
const toolFilter = ref('')
const limit = ref(100)

const { data, status, error, refresh } = await fetchApi<{
  events: AuditEvent[]
  total: number
}>(
  '/api/audit',
  {
    query: computed(() => ({
      limit: limit.value,
      kind: kind.value === 'all' ? undefined : kind.value,
      tool: toolFilter.value.trim() || undefined
    }))
  }
)

const events = computed<AuditEvent[]>(() => data.value?.events ?? [])

const kindOptions = [
  { label: 'All kinds', value: 'all' },
  { label: 'Bypass used', value: 'bypass' },
  { label: 'Blocked', value: 'blocked' }
]

function formatTs(ts: string): string {
  if (!ts) return '—'
  try {
    return new Date(ts).toLocaleString()
  } catch {
    return ts
  }
}

function kindColor(k: string): 'warning' | 'error' | 'neutral' {
  return k === 'bypass' ? 'warning' : k === 'blocked' ? 'error' : 'neutral'
}

watch([kind, toolFilter, limit], async () => {
  await refresh()
})
</script>

<template>
  <UDashboardPanel id="audit">
    <template #header>
      <UDashboardNavbar title="Audit log">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #trailing>
          <UBadge v-if="data?.total" :label="`${data.total} event${data.total === 1 ? '' : 's'}`" variant="subtle" />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <DashboardState
        :status="status"
        :error="error"
        :empty="!events.length"
        empty-title="No audit events"
        empty-description="Hook bypass + block events show up here. Nothing yet — good news."
        empty-icon="i-lucide-shield-check"
        loading-label="Loading audit"
        :on-retry="() => refresh()"
      >
        <div class="flex flex-wrap items-center gap-3 mb-4">
          <USelect
            v-model="kind"
            :items="kindOptions"
            placeholder="Kind"
            class="min-w-40"
            aria-label="Filter by kind"
          />
          <UInput
            v-model="toolFilter"
            class="max-w-xs"
            icon="i-lucide-wrench"
            placeholder="Filter by tool…"
          />
          <span class="ml-auto text-xs text-muted">
            {{ events.length }} match{{ events.length === 1 ? '' : 'es' }}
          </span>
        </div>

        <ul class="space-y-2 max-w-5xl">
          <li
            v-for="(ev, idx) in events"
            :key="`${ev.ts}-${idx}`"
            class="rounded-lg border border-default p-3"
          >
            <div class="flex items-center gap-3 flex-wrap text-xs mb-1.5">
              <UBadge
                :label="ev.kind"
                :color="kindColor(ev.kind)"
                variant="subtle"
                size="sm"
              />
              <UBadge :label="ev.tool || '—'" variant="outline" size="sm" />
              <span class="text-muted font-mono">{{ formatTs(ev.ts) }}</span>
            </div>
            <p class="text-sm">
              {{ ev.reason || '(no reason recorded)' }}
            </p>
            <p v-if="ev.cwd" class="text-xs text-muted font-mono mt-1 truncate" :title="ev.cwd">
              {{ ev.cwd }}
            </p>
          </li>
        </ul>
      </DashboardState>
    </template>
  </UDashboardPanel>
</template>
