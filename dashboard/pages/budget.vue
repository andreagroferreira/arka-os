<script setup lang="ts">
interface TierBudget {
  tier: number
  label: string
  allocated: number
  used: number
  remaining: number
  percent_used: number
  status: string
}

interface BudgetData {
  tiers: TierBudget[]
}

const { fetchApi } = useApi()

const { data: budget, pending, error, refresh } = await fetchApi<BudgetData>('/api/budget')

function progressColor(percent: number): 'success' | 'warning' | 'error' {
  if (percent < 50) return 'success'
  if (percent < 80) return 'warning'
  return 'error'
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value)
}
</script>

<template>
  <div>
    <h2 class="text-2xl font-bold text-white mb-6">
      Budget
    </h2>

    <!-- Loading -->
    <div v-if="pending" class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <UCard v-for="i in 4" :key="i">
        <div class="animate-pulse space-y-4">
          <div class="h-4 bg-gray-700 rounded w-24" />
          <div class="h-8 bg-gray-700 rounded w-32" />
          <div class="h-2 bg-gray-700 rounded" />
        </div>
      </UCard>
    </div>

    <!-- Error -->
    <UCard v-else-if="error">
      <div role="alert" class="text-center py-8">
        <p class="text-red-400 font-medium mb-2">
          Failed to load budget data
        </p>
        <UButton color="primary" variant="soft" @click="refresh()">
          Retry
        </UButton>
      </div>
    </UCard>

    <!-- Empty -->
    <div v-else-if="!budget?.tiers?.length" class="text-center py-12">
      <p class="text-gray-500">
        No budget data available.
      </p>
    </div>

    <!-- Budget tiers -->
    <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <UCard v-for="tier in budget.tiers" :key="tier.tier">
        <div class="space-y-4">
          <!-- Header -->
          <div class="flex items-center justify-between">
            <div>
              <h3 class="text-lg font-semibold text-white">
                Tier {{ tier.tier }}
              </h3>
              <p class="text-sm text-gray-500">
                {{ tier.label }}
              </p>
            </div>
            <StatusBadge :status="tier.status" />
          </div>

          <!-- Amounts -->
          <div class="grid grid-cols-3 gap-4">
            <div>
              <p class="text-xs text-gray-500">Allocated</p>
              <p class="text-sm font-semibold text-gray-200">
                {{ formatCurrency(tier.allocated) }}
              </p>
            </div>
            <div>
              <p class="text-xs text-gray-500">Used</p>
              <p class="text-sm font-semibold text-gray-200">
                {{ formatCurrency(tier.used) }}
              </p>
            </div>
            <div>
              <p class="text-xs text-gray-500">Remaining</p>
              <p
                class="text-sm font-semibold"
                :class="tier.remaining > 0 ? 'text-green-400' : 'text-red-400'"
              >
                {{ formatCurrency(tier.remaining) }}
              </p>
            </div>
          </div>

          <!-- Progress -->
          <div>
            <div class="flex justify-between text-xs mb-1">
              <span class="text-gray-500">Usage</span>
              <span
                :class="{
                  'text-green-400': tier.percent_used < 50,
                  'text-yellow-400': tier.percent_used >= 50 && tier.percent_used < 80,
                  'text-red-400': tier.percent_used >= 80,
                }"
              >
                {{ tier.percent_used }}%
              </span>
            </div>
            <UProgress
              :value="tier.percent_used"
              :color="progressColor(tier.percent_used)"
              size="sm"
            />
          </div>
        </div>
      </UCard>
    </div>
  </div>
</template>
