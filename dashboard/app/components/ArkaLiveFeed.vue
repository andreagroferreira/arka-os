<script setup lang="ts">
// One stream, two sources: /api/audit (poll) for enforcement events and
// /ws/tasks for job lifecycle. WS failure degrades to poll-only.
import { useDocumentVisibility } from '@vueuse/core'

interface AuditEvent {
  ts: string
  tool: string
  reason: string
  kind: string
}
interface FeedItem {
  id: string
  ts: number
  icon: string
  tone: 'primary' | 'warning' | 'error' | 'neutral'
  title: string
  detail: string
}

const props = withDefaults(defineProps<{
  limit?: number
  pollInterval?: number
}>(), {
  limit: 12,
  pollInterval: 15_000
})

const { apiBase } = useApi()
const visibility = useDocumentVisibility()
const items = ref<FeedItem[]>([])
let timer: ReturnType<typeof setInterval> | undefined

function pushItems(next: FeedItem[]) {
  const seen = new Set(items.value.map(i => i.id))
  const fresh = next.filter(i => !seen.has(i.id))
  if (!fresh.length) return
  items.value = [...fresh, ...items.value]
    .sort((a, b) => b.ts - a.ts)
    .slice(0, props.limit)
}

async function pollAudit() {
  try {
    const res = await $fetch<{ events: AuditEvent[] }>(`${apiBase}/api/audit`, { query: { limit: props.limit } })
    pushItems((res.events || []).map(e => ({
      id: `audit-${e.ts}-${e.tool}-${(e.reason || '').slice(0, 32)}`,
      ts: Date.parse(e.ts) || Date.now(),
      icon: e.kind === 'bypass' ? 'i-lucide-shield-off' : 'i-lucide-shield',
      tone: e.kind === 'bypass' ? 'warning' : 'neutral',
      title: e.tool || e.kind,
      detail: e.reason || e.kind
    })))
  } catch {
    // API down — keep whatever we have
  }
}

useTaskStream((e) => {
  const toneMap = { job_complete: 'primary', job_failed: 'error', job_cancelled: 'warning', job_progress: 'neutral' } as const
  const iconMap = {
    job_complete: 'i-lucide-check-circle',
    job_failed: 'i-lucide-x-circle',
    job_cancelled: 'i-lucide-circle-slash',
    job_progress: 'i-lucide-loader'
  } as const
  pushItems([{
    id: `job-${e.job_id}-${e.type}-${e.ts}`,
    ts: e.ts,
    icon: iconMap[e.type],
    tone: toneMap[e.type],
    title: e.type.replace('job_', 'job '),
    detail: e.message || e.error || e.job_id
  }])
})

onMounted(() => {
  pollAudit()
  timer = setInterval(() => {
    if (visibility.value === 'visible') pollAudit()
  }, props.pollInterval)
})
onUnmounted(() => clearInterval(timer))

function timeLabel(ts: number) {
  return new Date(ts).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}
const toneClass = { primary: 'text-primary', warning: 'text-warning', error: 'text-error', neutral: 'text-muted' }
</script>

<template>
  <ArkaGlowCard :padded="false">
    <div v-if="!items.length" class="p-6 text-center">
      <p class="arka-data text-xs text-muted">
        listening for signals…
      </p>
    </div>
    <TransitionGroup
      v-else
      tag="ul"
      class="divide-y divide-default"
      enter-active-class="arka-stream-in"
    >
      <li
        v-for="item in items"
        :key="item.id"
        class="flex items-center gap-3 px-4 py-2.5"
      >
        <UIcon :name="item.icon" class="size-4 shrink-0" :class="toneClass[item.tone]" />
        <div class="min-w-0 flex-1">
          <p class="truncate text-sm">
            {{ item.title }}
          </p>
          <p class="truncate text-xs text-muted">
            {{ item.detail }}
          </p>
        </div>
        <span class="arka-data shrink-0 text-[10px] text-muted">{{ timeLabel(item.ts) }}</span>
      </li>
    </TransitionGroup>
  </ArkaGlowCard>
</template>
