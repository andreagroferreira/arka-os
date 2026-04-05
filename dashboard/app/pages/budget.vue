<script setup lang="ts">
import type { BudgetTier } from '~/types'

const { fetchApi } = useApi()

const { data, status, error, refresh } = await fetchApi<{ tiers: BudgetTier[] }>('/api/budget')

const tiers = computed(() => data.value?.tiers ?? [])

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(value)
}

function tierLabel(tier: number): string {
  const labels: Record<number, string> = {
    0: 'C-Suite',
    1: 'Squad Leads',
    2: 'Specialists',
    3: 'Operations'
  }
  return labels[tier] ?? `Tier ${tier}`
}

function statusColor(status: string) {
  const colors: Record<string, 'success' | 'warning' | 'error' | 'neutral'> = {
    healthy: 'success',
    warning: 'warning',
    critical: 'error',
    unlimited: 'neutral'
  }
  return colors[status] ?? 'neutral'
}
</script>

<template>
  <UDashboardPanel id="budget">
    <template #header>
      <UDashboardNavbar title="Budget">
        <template #leading>
          <UDashboardSidebarCollapse />
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
        <p class="text-sm text-muted">Failed to load budget data.</p>
        <UButton label="Retry" variant="outline" color="primary" icon="i-lucide-refresh-cw" @click="refresh()" />
      </div>

      <!-- Empty -->
      <div v-else-if="!tiers.length" class="flex flex-col items-center justify-center gap-4 py-12">
        <UIcon name="i-lucide-wallet" class="size-12 text-muted" />
        <p class="text-sm text-muted">No budget data available.</p>
      </div>

      <!-- Content -->
      <div v-else class="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div
          v-for="tier in tiers"
          :key="tier.tier"
          class="rounded-lg border border-default p-6"
        >
          <div class="mb-4 flex items-center justify-between">
            <div>
              <h3 class="text-lg font-semibold text-highlighted">Tier {{ tier.tier }}</h3>
              <p class="text-sm text-muted">{{ tierLabel(tier.tier) }}</p>
            </div>
            <UBadge :label="tier.status" :color="statusColor(tier.status)" variant="subtle" class="capitalize" />
          </div>

          <div v-if="tier.is_unlimited" class="text-sm text-muted">
            Unlimited budget configured.
          </div>
          <div v-else class="space-y-3">
            <div class="flex items-center justify-between text-sm">
              <span class="text-muted">Used: {{ formatCurrency(tier.used) }}</span>
              <span class="text-muted">Allocated: {{ formatCurrency(tier.allocated) }}</span>
            </div>
            <UProgress :value="tier.percent_used" :max="100" size="md" />
            <div class="flex items-center justify-between text-xs text-muted">
              <span>{{ tier.percent_used.toFixed(1) }}% used</span>
              <span>Remaining: {{ formatCurrency(tier.remaining) }}</span>
            </div>
          </div>
        </div>
      </div>
    </template>
  </UDashboardPanel>
</template>
