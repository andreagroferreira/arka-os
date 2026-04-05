<script setup lang="ts">
const { fetchApi } = useApi()

const { data, status, error, refresh } = fetchApi<any>('/api/budget')

const summary = computed(() => data.value?.summary ?? { total_tokens: 0, total_ops: 0, active_departments: 0, estimated_cost_usd: 0 })
const departments = computed(() => data.value?.departments ?? [])
const tiers = computed(() => data.value?.tiers ?? [])

const showLimits = ref(false)

const tierLabels: Record<number, string> = {
  0: 'C-Suite (Unlimited)',
  1: 'Squad Leads',
  2: 'Specialists',
  3: 'Support'
}
</script>

<template>
  <UDashboardPanel id="budget">
    <template #header>
      <UDashboardNavbar title="Usage & Budget">
        <template #leading>
          <UDashboardSidebarCollapse />
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
      <div v-if="status === 'pending'" class="flex items-center justify-center py-12">
        <UIcon name="i-lucide-loader-2" class="size-8 animate-spin text-muted" />
      </div>

      <div v-else-if="error" class="flex flex-col items-center justify-center gap-4 py-12" role="alert">
        <UIcon name="i-lucide-alert-triangle" class="size-12 text-red-500" />
        <p class="text-sm text-muted">Failed to load budget data.</p>
        <UButton label="Retry" variant="outline" icon="i-lucide-refresh-cw" @click="refresh()" />
      </div>

      <div v-else class="space-y-6">
        <!-- Monthly Summary -->
        <UCard>
          <div class="space-y-3">
            <p class="text-xs font-semibold text-muted uppercase tracking-wider">This Month's Usage</p>
            <div class="flex flex-wrap items-baseline gap-6">
              <div>
                <span class="text-3xl font-bold">{{ summary.total_tokens.toLocaleString() }}</span>
                <span class="text-sm text-muted ml-1">tokens</span>
              </div>
              <div>
                <span class="text-xl font-semibold">{{ summary.total_ops }}</span>
                <span class="text-sm text-muted ml-1">operations</span>
              </div>
              <div>
                <span class="text-xl font-semibold">{{ summary.active_departments }}</span>
                <span class="text-sm text-muted ml-1">departments active</span>
              </div>
              <div v-if="summary.estimated_cost_usd > 0">
                <span class="text-sm text-muted">Est. cost: ~${{ summary.estimated_cost_usd.toFixed(4) }}</span>
              </div>
            </div>
          </div>
        </UCard>

        <!-- Department Breakdown -->
        <div v-if="departments.length">
          <h2 class="text-sm font-semibold text-muted uppercase tracking-wider mb-4">Usage by Department</h2>
          <div class="space-y-3">
            <div
              v-for="dept in departments"
              :key="dept.department"
              class="flex items-center gap-4"
            >
              <span class="w-28 text-sm font-medium truncate">{{ dept.department }}</span>
              <div class="flex-1 h-3 rounded-full bg-muted/20 overflow-hidden">
                <div
                  class="h-3 rounded-full bg-primary transition-none"
                  :style="{ width: `${dept.percent}%` }"
                />
              </div>
              <span class="w-24 text-right text-sm font-mono">{{ dept.tokens.toLocaleString() }}</span>
              <span class="w-16 text-right text-xs text-muted">{{ dept.operations }} ops</span>
            </div>
          </div>
        </div>

        <!-- Empty state -->
        <div v-else class="flex flex-col items-center justify-center gap-4 py-12">
          <UIcon name="i-lucide-bar-chart-3" class="size-12 text-muted" />
          <p class="text-sm text-muted">No usage data yet.</p>
          <p class="text-xs text-muted">Token usage is tracked automatically when ArkaOS processes prompts and indexes knowledge.</p>
        </div>

        <!-- System Limits (collapsible) -->
        <div class="pt-4 border-t border-default">
          <button
            class="flex items-center gap-2 text-xs text-muted hover:text-highlighted transition-colors"
            @click="showLimits = !showLimits"
          >
            <UIcon :name="showLimits ? 'i-lucide-chevron-down' : 'i-lucide-chevron-right'" class="size-3" />
            System Limits
          </button>

          <div v-if="showLimits" class="mt-3 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <div
              v-for="tier in tiers"
              :key="tier.tier"
              class="rounded-lg border border-default p-3"
            >
              <p class="text-xs font-semibold">Tier {{ tier.tier }}</p>
              <p class="text-xs text-muted">{{ tierLabels[tier.tier] ?? '' }}</p>
              <p class="text-xs text-muted mt-1">
                <template v-if="tier.is_unlimited">Unlimited</template>
                <template v-else>{{ (tier.allocated ?? 0).toLocaleString() }} tokens/month</template>
              </p>
            </div>
          </div>
        </div>
      </div>
    </template>
  </UDashboardPanel>
</template>
