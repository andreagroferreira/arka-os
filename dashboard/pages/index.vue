<script setup lang="ts">
interface OverviewData {
  agents: number
  skills: number
  departments: number
  tests: number
  budget: {
    tier2: {
      allocated: number
      used: number
    }
  }
  active_tasks: number
  knowledge: {
    chunks: number
    files: number
  }
  health: {
    passed: number
    total: number
  }
  synapse_latency_ms: number
}

const { fetchApi } = useApi()

const { data: overview, pending, error, refresh } = await fetchApi<OverviewData>('/api/overview')

const budgetPercent = computed(() => {
  if (!overview.value?.budget?.tier2) return 0
  const { allocated, used } = overview.value.budget.tier2
  return allocated > 0 ? Math.round((used / allocated) * 100) : 0
})

const budgetColor = computed(() => {
  const pct = budgetPercent.value
  if (pct < 50) return 'success'
  if (pct < 80) return 'warning'
  return 'error'
})

const healthPercent = computed(() => {
  if (!overview.value?.health) return 0
  const { passed, total } = overview.value.health
  return total > 0 ? Math.round((passed / total) * 100) : 0
})
</script>

<template>
  <div>
    <h2 class="text-2xl font-bold text-white mb-6">
      Overview
    </h2>

    <!-- Loading state -->
    <div v-if="pending" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      <UCard v-for="i in 8" :key="i">
        <div class="animate-pulse space-y-3">
          <div class="h-3 bg-gray-700 rounded w-20" />
          <div class="h-8 bg-gray-700 rounded w-16" />
        </div>
      </UCard>
    </div>

    <!-- Error state -->
    <UCard v-else-if="error" class="border-red-800">
      <div role="alert" class="text-center py-4">
        <p class="text-red-400 font-medium mb-2">
          Failed to load overview data
        </p>
        <p class="text-sm text-gray-500 mb-4">
          Make sure the API server is running on port 3334.
        </p>
        <UButton color="primary" variant="soft" @click="refresh()">
          Retry
        </UButton>
      </div>
    </UCard>

    <!-- Success state -->
    <template v-else-if="overview">
      <!-- Primary stats -->
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatsCard
          title="Agents"
          :value="overview.agents"
          subtitle="Across all departments"
          color="primary"
        />
        <StatsCard
          title="Skills"
          :value="`${overview.skills}+`"
          subtitle="Available commands"
          color="info"
        />
        <StatsCard
          title="Departments"
          :value="overview.departments"
          subtitle="Specialized teams"
          color="success"
        />
        <StatsCard
          title="Tests"
          :value="overview.tests"
          subtitle="Passing test suite"
          color="neutral"
        />
      </div>

      <!-- Secondary stats -->
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
        <!-- Budget card -->
        <UCard>
          <div class="space-y-3">
            <p class="text-sm font-medium text-gray-400">
              Tier 2 Budget
            </p>
            <div class="flex justify-between text-sm">
              <span class="text-gray-300">
                ${{ overview.budget.tier2.used.toLocaleString() }}
                / ${{ overview.budget.tier2.allocated.toLocaleString() }}
              </span>
              <span
                :class="{
                  'text-green-400': budgetPercent < 50,
                  'text-yellow-400': budgetPercent >= 50 && budgetPercent < 80,
                  'text-red-400': budgetPercent >= 80,
                }"
              >
                {{ budgetPercent }}%
              </span>
            </div>
            <UProgress
              :value="budgetPercent"
              :color="budgetColor"
              size="sm"
            />
          </div>
        </UCard>

        <!-- Active tasks -->
        <StatsCard
          title="Active Tasks"
          :value="overview.active_tasks"
          subtitle="Currently processing"
          color="warning"
        />

        <!-- Synapse latency -->
        <StatsCard
          title="Synapse Latency"
          :value="`${overview.synapse_latency_ms}ms`"
          subtitle="Avg context injection"
          :color="overview.synapse_latency_ms < 5 ? 'success' : 'warning'"
        />
      </div>

      <!-- Knowledge & Health -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <!-- Knowledge -->
        <UCard>
          <div class="space-y-2">
            <p class="text-sm font-medium text-gray-400">
              Knowledge Base
            </p>
            <div class="flex gap-8">
              <div>
                <p class="text-2xl font-bold text-blue-400">
                  {{ overview.knowledge.chunks.toLocaleString() }}
                </p>
                <p class="text-xs text-gray-500">
                  chunks indexed
                </p>
              </div>
              <div>
                <p class="text-2xl font-bold text-gray-300">
                  {{ overview.knowledge.files }}
                </p>
                <p class="text-xs text-gray-500">
                  source files
                </p>
              </div>
            </div>
          </div>
        </UCard>

        <!-- Health -->
        <UCard>
          <div class="space-y-3">
            <p class="text-sm font-medium text-gray-400">
              System Health
            </p>
            <div class="flex items-baseline gap-2">
              <p class="text-2xl font-bold" :class="healthPercent === 100 ? 'text-green-400' : 'text-yellow-400'">
                {{ overview.health.passed }}/{{ overview.health.total }}
              </p>
              <p class="text-sm text-gray-500">
                checks passing
              </p>
            </div>
            <UProgress
              :value="healthPercent"
              :color="healthPercent === 100 ? 'success' : 'warning'"
              size="sm"
            />
          </div>
        </UCard>
      </div>
    </template>

    <!-- Empty state -->
    <div v-else class="text-center py-12">
      <p class="text-gray-500">
        No overview data available.
      </p>
    </div>
  </div>
</template>
