<script setup lang="ts">
import type { HealthCheck } from '~/types'

const { fetchApi } = useApi()

const { data, status, error, refresh } = await fetchApi<{ checks: HealthCheck[], passed: number, total: number }>('/api/health')

const checks = computed(() => data.value?.checks ?? [])
const passed = computed(() => data.value?.passed ?? 0)
const total = computed(() => data.value?.total ?? 0)
const allPassed = computed(() => passed.value === total.value && total.value > 0)
</script>

<template>
  <UDashboardPanel id="health">
    <template #header>
      <UDashboardNavbar title="Health Checks">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #trailing>
          <UBadge
            v-if="data"
            :label="`${passed}/${total}`"
            :color="allPassed ? 'success' : 'warning'"
            variant="subtle"
          />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <!-- Loading -->
      <div v-if="status === 'pending'" class="flex items-center justify-center py-12">
        <UIcon name="i-lucide-loader-2" class="size-8 animate-spin text-muted" />
      </div>

      <!-- Error -->
      <div v-else-if="error" class="flex flex-col items-center justify-center gap-4 py-12" role="alert">
        <UIcon name="i-lucide-alert-triangle" class="size-12 text-red-500" />
        <p class="text-sm text-muted">Failed to load health checks.</p>
        <UButton label="Retry" variant="outline" color="primary" icon="i-lucide-refresh-cw" @click="refresh()" />
      </div>

      <!-- Empty -->
      <div v-else-if="!checks.length" class="flex flex-col items-center justify-center gap-4 py-12">
        <UIcon name="i-lucide-heart-pulse" class="size-12 text-muted" />
        <p class="text-sm text-muted">No health checks available.</p>
      </div>

      <!-- Content -->
      <template v-else>
        <!-- Overall Status -->
        <div
          class="mb-6 rounded-lg border p-6 text-center"
          :class="allPassed ? 'border-green-500/30 bg-green-500/5' : 'border-yellow-500/30 bg-yellow-500/5'"
        >
          <UIcon
            :name="allPassed ? 'i-lucide-check-circle' : 'i-lucide-alert-circle'"
            :class="allPassed ? 'text-green-500' : 'text-yellow-500'"
            class="size-12"
          />
          <p class="mt-2 text-lg font-semibold text-highlighted">
            {{ allPassed ? 'All Checks Passing' : `${total - passed} Check(s) Failing` }}
          </p>
          <p class="text-sm text-muted">{{ passed }} of {{ total }} checks passed</p>
        </div>

        <!-- Individual Checks -->
        <div class="space-y-3">
          <div
            v-for="check in checks"
            :key="check.name"
            class="flex items-start gap-3 rounded-lg border border-default p-4"
          >
            <UIcon
              :name="check.passed ? 'i-lucide-check-circle' : 'i-lucide-x-circle'"
              :class="check.passed ? 'text-green-500' : 'text-red-500'"
              class="mt-0.5 size-5 shrink-0"
            />
            <div class="flex-1">
              <h4 class="font-medium text-highlighted">{{ check.name }}</h4>
              <p v-if="!check.passed && check.fix" class="mt-1 text-sm text-muted">
                Fix: {{ check.fix }}
              </p>
            </div>
            <UBadge
              :label="check.passed ? 'Pass' : 'Fail'"
              :color="check.passed ? 'success' : 'error'"
              variant="subtle"
              size="sm"
            />
          </div>
        </div>
      </template>
    </template>
  </UDashboardPanel>
</template>
