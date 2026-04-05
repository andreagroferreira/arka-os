<script setup lang="ts">
interface Agent {
  name: string
  role: string
  department: string
  tier: number
  disc: string
  mbti: string
  enneagram?: string
  big_five?: {
    openness: number
    conscientiousness: number
    extraversion: number
    agreeableness: number
    neuroticism: number
  }
  frameworks?: string[]
}

const { fetchApi } = useApi()

const { data: agents, pending, error, refresh } = await fetchApi<Agent[]>('/api/agents')

const departments = computed(() => {
  if (!agents.value) return []
  const depts = [...new Set(agents.value.map((a) => a.department))].sort()
  return [{ label: 'All Departments', value: '' }, ...depts.map((d) => ({ label: d, value: d }))]
})

const selectedDepartment = ref('')
const expandedAgent = ref<string | null>(null)

const filteredAgents = computed(() => {
  if (!agents.value) return []
  if (!selectedDepartment.value) return agents.value
  return agents.value.filter((a) => a.department === selectedDepartment.value)
})

const columns = [
  { key: 'name', label: 'Name' },
  { key: 'role', label: 'Role' },
  { key: 'department', label: 'Department' },
  { key: 'tier', label: 'Tier' },
  { key: 'disc', label: 'DISC' },
  { key: 'mbti', label: 'MBTI' },
]

function toggleExpand(name: string) {
  expandedAgent.value = expandedAgent.value === name ? null : name
}

function discColor(disc: string): 'error' | 'warning' | 'success' | 'info' | 'neutral' {
  const primary = disc.charAt(0).toUpperCase()
  const map: Record<string, 'error' | 'warning' | 'success' | 'info'> = {
    D: 'error',
    I: 'warning',
    S: 'success',
    C: 'info',
  }
  return map[primary] ?? 'neutral'
}

function tierColor(tier: number): 'primary' | 'info' | 'neutral' {
  const map: Record<number, 'primary' | 'info' | 'neutral'> = {
    0: 'primary',
    1: 'info',
    2: 'neutral',
  }
  return map[tier] ?? 'neutral'
}
</script>

<template>
  <div>
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
      <h2 class="text-2xl font-bold text-white">
        Agents
      </h2>
      <USelect
        v-model="selectedDepartment"
        :items="departments"
        placeholder="Filter by department"
        class="w-full sm:w-64"
      />
    </div>

    <!-- Loading -->
    <UCard v-if="pending">
      <div class="animate-pulse space-y-4 py-8">
        <div v-for="i in 6" :key="i" class="h-10 bg-gray-800 rounded" />
      </div>
    </UCard>

    <!-- Error -->
    <UCard v-else-if="error">
      <div role="alert" class="text-center py-8">
        <p class="text-red-400 font-medium mb-2">
          Failed to load agents
        </p>
        <UButton color="primary" variant="soft" @click="refresh()">
          Retry
        </UButton>
      </div>
    </UCard>

    <!-- Empty -->
    <UCard v-else-if="!filteredAgents.length">
      <p class="text-gray-500 text-center py-8">
        No agents found.
      </p>
    </UCard>

    <!-- Agent list -->
    <div v-else class="space-y-2">
      <!-- Header row -->
      <div class="hidden md:grid grid-cols-6 gap-4 px-4 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wider">
        <span>Name</span>
        <span>Role</span>
        <span>Department</span>
        <span>Tier</span>
        <span>DISC</span>
        <span>MBTI</span>
      </div>

      <!-- Agent rows -->
      <UCard
        v-for="agent in filteredAgents"
        :key="agent.name"
        class="cursor-pointer hover:ring-1 hover:ring-gray-700 transition-all"
        @click="toggleExpand(agent.name)"
      >
        <div class="grid grid-cols-2 md:grid-cols-6 gap-4 items-center">
          <div>
            <p class="font-medium text-white">{{ agent.name }}</p>
          </div>
          <div>
            <p class="text-sm text-gray-400">{{ agent.role }}</p>
          </div>
          <div>
            <p class="text-sm text-gray-400">{{ agent.department }}</p>
          </div>
          <div>
            <UBadge :color="tierColor(agent.tier)" variant="subtle" size="sm">
              Tier {{ agent.tier }}
            </UBadge>
          </div>
          <div>
            <UBadge :color="discColor(agent.disc)" variant="subtle" size="sm">
              {{ agent.disc }}
            </UBadge>
          </div>
          <div>
            <span class="text-sm text-gray-300 font-mono">{{ agent.mbti }}</span>
          </div>
        </div>

        <!-- Expanded details -->
        <div
          v-if="expandedAgent === agent.name"
          class="mt-4 pt-4 border-t border-gray-800 space-y-4"
        >
          <!-- Big Five -->
          <div v-if="agent.big_five">
            <p class="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
              Big Five (OCEAN)
            </p>
            <div class="grid grid-cols-1 sm:grid-cols-5 gap-3">
              <div v-for="(value, trait) in agent.big_five" :key="trait">
                <div class="flex justify-between text-xs mb-1">
                  <span class="text-gray-400 capitalize">{{ trait }}</span>
                  <span class="text-gray-300">{{ value }}</span>
                </div>
                <UProgress :value="value" size="xs" color="primary" />
              </div>
            </div>
          </div>

          <!-- Enneagram -->
          <div v-if="agent.enneagram" class="flex items-center gap-2">
            <span class="text-xs font-semibold text-gray-500 uppercase tracking-wider">Enneagram:</span>
            <span class="text-sm text-gray-300">{{ agent.enneagram }}</span>
          </div>

          <!-- Frameworks -->
          <div v-if="agent.frameworks?.length">
            <p class="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
              Frameworks
            </p>
            <div class="flex flex-wrap gap-2">
              <UBadge
                v-for="fw in agent.frameworks"
                :key="fw"
                color="neutral"
                variant="subtle"
                size="sm"
              >
                {{ fw }}
              </UBadge>
            </div>
          </div>
        </div>
      </UCard>
    </div>
  </div>
</template>
