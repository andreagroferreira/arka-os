<script setup lang="ts">
interface HealthCheck {
  name: string
  status: 'pass' | 'fail'
  message?: string
  fix?: string
}

interface HealthData {
  status: string
  checks: HealthCheck[]
  passed: number
  total: number
}

const { fetchApi } = useApi()

const { data: health, pending, error, refresh } = await fetchApi<HealthData>('/api/health')

const passedCount = computed(() => health.value?.passed ?? 0)
const totalCount = computed(() => health.value?.total ?? 0)
const failedChecks = computed(() =>
  health.value?.checks.filter((c) => c.status === 'fail') ?? [],
)
const passedChecks = computed(() =>
  health.value?.checks.filter((c) => c.status === 'pass') ?? [],
)
const allPassing = computed(() => passedCount.value === totalCount.value)
</script>

<template>
  <div>
    <div class="flex items-center justify-between mb-6">
      <h2 class="text-2xl font-bold text-white">
        System Health
      </h2>
      <UButton
        color="primary"
        variant="soft"
        size="sm"
        :loading="pending"
        @click="refresh()"
      >
        Re-check
      </UButton>
    </div>

    <!-- Loading -->
    <UCard v-if="pending">
      <div class="animate-pulse space-y-4 py-8">
        <div class="h-6 bg-gray-700 rounded w-48" />
        <div v-for="i in 6" :key="i" class="h-8 bg-gray-800 rounded" />
      </div>
    </UCard>

    <!-- Error -->
    <UCard v-else-if="error">
      <div role="alert" class="text-center py-8">
        <p class="text-red-400 font-medium mb-2">
          Failed to load health data
        </p>
        <p class="text-sm text-gray-500 mb-4">
          The API server may be unreachable.
        </p>
        <UButton color="primary" variant="soft" @click="refresh()">
          Retry
        </UButton>
      </div>
    </UCard>

    <!-- Empty -->
    <div v-else-if="!health" class="text-center py-12">
      <p class="text-gray-500">
        No health data available.
      </p>
    </div>

    <template v-else>
      <!-- Summary -->
      <UCard class="mb-6">
        <div class="flex items-center gap-4">
          <div
            class="w-12 h-12 rounded-full flex items-center justify-center text-xl font-bold"
            :class="allPassing
              ? 'bg-green-500/10 text-green-400'
              : 'bg-yellow-500/10 text-yellow-400'"
          >
            {{ allPassing ? '✓' : '!' }}
          </div>
          <div>
            <p class="text-lg font-semibold text-white">
              {{ passedCount }}/{{ totalCount }} checks passing
            </p>
            <p class="text-sm" :class="allPassing ? 'text-green-400' : 'text-yellow-400'">
              {{ allPassing ? 'All systems operational' : `${failedChecks.length} check${failedChecks.length !== 1 ? 's' : ''} need attention` }}
            </p>
          </div>
        </div>
      </UCard>

      <!-- Failed checks first -->
      <div v-if="failedChecks.length" class="mb-6">
        <h3 class="text-sm font-semibold text-red-400 uppercase tracking-wider mb-3">
          Failed Checks
        </h3>
        <div class="space-y-2">
          <UCard v-for="check in failedChecks" :key="check.name">
            <div class="flex items-start gap-3">
              <span class="mt-0.5 text-red-400 font-bold text-sm" aria-hidden="true">
                ✗
              </span>
              <div class="flex-1">
                <div class="flex items-center justify-between">
                  <p class="font-medium text-white">{{ check.name }}</p>
                  <UBadge color="error" variant="subtle" size="sm">FAIL</UBadge>
                </div>
                <p v-if="check.message" class="text-sm text-gray-400 mt-1">
                  {{ check.message }}
                </p>
                <div v-if="check.fix" class="mt-2 p-2 bg-gray-800 rounded text-xs">
                  <span class="text-gray-500">Fix: </span>
                  <span class="text-yellow-400">{{ check.fix }}</span>
                </div>
              </div>
            </div>
          </UCard>
        </div>
      </div>

      <!-- Passing checks -->
      <div>
        <h3 class="text-sm font-semibold text-green-400 uppercase tracking-wider mb-3">
          Passing Checks ({{ passedChecks.length }})
        </h3>
        <div class="space-y-1">
          <UCard v-for="check in passedChecks" :key="check.name">
            <div class="flex items-center gap-3">
              <span class="text-green-400 font-bold text-sm" aria-hidden="true">
                ✓
              </span>
              <p class="text-sm text-gray-300">{{ check.name }}</p>
              <p v-if="check.message" class="text-xs text-gray-600">
                {{ check.message }}
              </p>
            </div>
          </UCard>
        </div>
      </div>
    </template>
  </div>
</template>
