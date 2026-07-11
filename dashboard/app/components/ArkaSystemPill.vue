<script setup lang="ts">
// "all systems live" — the shell's heartbeat. Polls /api/health (30s),
// pauses while the tab is hidden.
import { useDocumentVisibility } from '@vueuse/core'

interface HealthPayload {
  healthy: boolean
  passed: number
  total: number
  failed_blocking: number
}

const { apiBase } = useApi()
const health = ref<HealthPayload | null>(null)
const visibility = useDocumentVisibility()
let timer: ReturnType<typeof setInterval> | undefined

async function poll() {
  try {
    health.value = await $fetch<HealthPayload>(`${apiBase}/api/health`)
  } catch {
    health.value = null
  }
}

onMounted(() => {
  poll()
  timer = setInterval(() => {
    if (visibility.value === 'visible') poll()
  }, 30_000)
})
onUnmounted(() => clearInterval(timer))

const label = computed(() => {
  if (!health.value) return 'link down'
  if (health.value.healthy) return 'all systems live'
  return `${health.value.failed_blocking || health.value.total - health.value.passed} degraded`
})
const tone = computed(() => {
  if (!health.value) return 'text-muted'
  return health.value.healthy ? 'text-primary' : 'text-warning'
})
</script>

<template>
  <NuxtLink
    to="/health"
    class="flex items-center gap-2 rounded-full border border-default bg-elevated px-3 py-1.5 transition-colors hover:border-primary/40"
  >
    <span v-if="health?.healthy" class="arka-live-dot" />
    <span v-else class="size-2 rounded-full" :class="health ? 'bg-warning' : 'bg-carbon-500'" />
    <span class="arka-data text-xs" :class="tone">{{ label }}</span>
  </NuxtLink>
</template>
