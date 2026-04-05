<script setup lang="ts">
import type { OverviewData } from '~/types'

const { fetchApi } = useApi()

const { data: overview, status, error, refresh } = await fetchApi<OverviewData>('/api/overview')

const stats = computed(() => [
  { label: 'Agents', value: overview.value?.agents ?? 0, icon: 'i-lucide-users' },
  { label: 'Skills', value: overview.value?.skills ?? 0, icon: 'i-lucide-sparkles' },
  { label: 'Departments', value: overview.value?.departments ?? 0, icon: 'i-lucide-building-2' },
  { label: 'Tests', value: overview.value?.tests ?? 0, icon: 'i-lucide-test-tubes' },
  { label: 'Commands', value: overview.value?.commands ?? 0, icon: 'i-lucide-terminal' },
  { label: 'Workflows', value: overview.value?.workflows ?? 0, icon: 'i-lucide-git-branch' }
])

const budgetPercent = computed(() => overview.value?.budget?.percent_used ?? 0)
const budgetUsed = computed(() => overview.value?.budget?.used ?? 0)
const budgetAllocated = computed(() => overview.value?.budget?.allocated ?? 0)
const budgetUnlimited = computed(() => overview.value?.budget?.is_unlimited ?? false)

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(value)
}
</script>

<template>
  <UDashboardPanel id="overview">
    <template #header>
      <UDashboardNavbar title="Overview">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>

        <template #right>
          <UBadge v-if="overview?.version" :label="`v${overview.version}`" variant="subtle" color="primary" />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <!-- Loading State -->
      <div v-if="status === 'pending'" class="flex items-center justify-center py-12">
        <UIcon name="i-lucide-loader-2" class="size-8 animate-spin text-muted" />
      </div>

      <!-- Error State -->
      <div v-else-if="error" class="flex flex-col items-center justify-center gap-4 py-12" role="alert">
        <UIcon name="i-lucide-alert-triangle" class="size-12 text-red-500" />
        <p class="text-sm text-muted">Failed to load overview data.</p>
        <UButton label="Retry" variant="outline" color="primary" icon="i-lucide-refresh-cw" @click="refresh()" />
      </div>

      <!-- Content -->
      <template v-else>
        <!-- Stats Grid -->
        <div class="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
          <div
            v-for="stat in stats"
            :key="stat.label"
            class="flex flex-col gap-2 rounded-lg border border-default p-4"
          >
            <div class="flex items-center gap-2">
              <UIcon :name="stat.icon" class="size-4 text-muted" />
              <span class="text-sm text-muted">{{ stat.label }}</span>
            </div>
            <span class="text-2xl font-semibold text-highlighted">{{ stat.value }}</span>
          </div>
        </div>

        <!-- Budget Gauge -->
        <div class="mt-6 rounded-lg border border-default p-6">
          <h3 class="mb-4 text-lg font-semibold text-highlighted">Budget</h3>
          <div v-if="budgetUnlimited" class="text-sm text-muted">
            Unlimited budget configured.
          </div>
          <div v-else class="space-y-3">
            <div class="flex items-center justify-between text-sm">
              <span class="text-muted">Used: {{ formatCurrency(budgetUsed) }}</span>
              <span class="text-muted">Allocated: {{ formatCurrency(budgetAllocated) }}</span>
            </div>
            <UProgress :value="budgetPercent" :max="100" size="md" />
            <p class="text-xs text-muted">{{ budgetPercent.toFixed(1) }}% of budget used</p>
          </div>
        </div>

        <!-- Bottom Row: Tasks + Knowledge -->
        <div class="mt-6 grid grid-cols-1 gap-4 md:grid-cols-2">
          <!-- Tasks Summary -->
          <div class="rounded-lg border border-default p-6">
            <h3 class="mb-4 text-lg font-semibold text-highlighted">Tasks</h3>
            <div class="grid grid-cols-3 gap-4">
              <div class="text-center">
                <p class="text-2xl font-semibold text-highlighted">{{ overview?.tasks?.total ?? 0 }}</p>
                <p class="text-xs text-muted">Total</p>
              </div>
              <div class="text-center">
                <p class="text-2xl font-semibold text-primary">{{ overview?.tasks?.active ?? 0 }}</p>
                <p class="text-xs text-muted">Active</p>
              </div>
              <div class="text-center">
                <p class="text-2xl font-semibold text-muted">{{ overview?.tasks?.queued ?? 0 }}</p>
                <p class="text-xs text-muted">Queued</p>
              </div>
            </div>
          </div>

          <!-- Knowledge Summary -->
          <div class="rounded-lg border border-default p-6">
            <h3 class="mb-4 text-lg font-semibold text-highlighted">Knowledge Base</h3>
            <div class="grid grid-cols-2 gap-4">
              <div class="text-center">
                <p class="text-2xl font-semibold text-highlighted">{{ overview?.knowledge?.total_chunks ?? 0 }}</p>
                <p class="text-xs text-muted">Chunks</p>
              </div>
              <div class="text-center">
                <p class="text-2xl font-semibold text-highlighted">{{ overview?.knowledge?.total_files ?? 0 }}</p>
                <p class="text-xs text-muted">Files</p>
              </div>
            </div>
          </div>
        </div>
      </template>
    </template>
  </UDashboardPanel>
</template>
