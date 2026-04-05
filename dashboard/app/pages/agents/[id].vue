<script setup lang="ts">
const route = useRoute()
const agentId = route.params.id as string

const { fetchApi } = useApi()
const { data: agent, status, error } = fetchApi<any>(`/api/agents/${agentId}`)

const tierLabel: Record<number, string> = {
  0: 'C-Suite',
  1: 'Squad Lead',
  2: 'Specialist',
  3: 'Support'
}

const bigFiveLabels: Record<string, string> = {
  O: 'Openness',
  C: 'Conscientiousness',
  E: 'Extraversion',
  A: 'Agreeableness',
  N: 'Neuroticism'
}
</script>

<template>
  <UDashboardPanel id="agent-detail">
    <template #header>
      <UDashboardNavbar :title="agent?.name ?? 'Agent'">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #trailing>
          <UButton label="Back" variant="ghost" icon="i-lucide-arrow-left" to="/agents" />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div v-if="status === 'pending'" class="flex items-center justify-center py-12">
        <UIcon name="i-lucide-loader-2" class="size-8 animate-spin text-muted" />
      </div>

      <div v-else-if="error || !agent" class="text-center py-12">
        <p class="text-muted">Agent not found.</p>
        <UButton label="Back to Agents" variant="outline" icon="i-lucide-arrow-left" to="/agents" class="mt-4" />
      </div>

      <div v-else class="space-y-8">
        <!-- Header -->
        <div>
          <div class="flex flex-wrap items-center gap-3">
            <h1 class="text-2xl font-bold">{{ agent.name }}</h1>
            <UBadge :label="agent.department" variant="subtle" />
            <UBadge :label="`Tier ${agent.tier} — ${tierLabel[agent.tier] ?? ''}`" variant="subtle" color="warning" />
          </div>
          <p class="mt-1 text-muted">{{ agent.role }}</p>
          <p class="mt-1 text-xs text-muted font-mono">{{ agent.id }}</p>
        </div>

        <!-- Behavioral DNA -->
        <div>
          <h2 class="text-lg font-semibold mb-4">Behavioral DNA</h2>
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <!-- DISC -->
            <UCard>
              <p class="text-xs font-semibold text-muted uppercase mb-2">DISC</p>
              <p class="text-2xl font-bold">{{ agent.disc?.primary ?? '-' }}</p>
              <p v-if="agent.disc?.secondary" class="text-sm text-muted">Secondary: {{ agent.disc.secondary }}</p>
              <p v-if="agent.disc?.label" class="text-xs text-muted mt-1">{{ agent.disc.label }}</p>
            </UCard>

            <!-- Enneagram -->
            <UCard>
              <p class="text-xs font-semibold text-muted uppercase mb-2">Enneagram</p>
              <p class="text-2xl font-bold">
                Type {{ agent.enneagram?.type ?? '-' }}
                <span v-if="agent.enneagram?.wing" class="text-base font-normal text-muted">w{{ agent.enneagram.wing }}</span>
              </p>
              <p v-if="agent.enneagram?.label" class="text-sm text-muted">{{ agent.enneagram.label }}</p>
            </UCard>

            <!-- Big Five -->
            <UCard>
              <p class="text-xs font-semibold text-muted uppercase mb-2">Big Five (OCEAN)</p>
              <div v-if="agent.big_five" class="space-y-3">
                <div v-for="key in ['O', 'C', 'E', 'A', 'N']" :key="key">
                  <div class="flex items-center justify-between text-xs mb-1">
                    <span class="text-muted">{{ bigFiveLabels[key] }}</span>
                    <span class="font-mono">{{ agent.big_five[key] ?? 0 }}</span>
                  </div>
                  <UProgress :value="agent.big_five[key] ?? 0" :max="100" size="xs" />
                </div>
              </div>
            </UCard>

            <!-- MBTI -->
            <UCard>
              <p class="text-xs font-semibold text-muted uppercase mb-2">MBTI</p>
              <p class="text-4xl font-bold font-mono tracking-widest">{{ agent.mbti || '-' }}</p>
            </UCard>
          </div>
        </div>

        <!-- Authority -->
        <div v-if="agent.authority">
          <h2 class="text-lg font-semibold mb-4">Authority</h2>
          <UCard>
            <div class="flex flex-wrap gap-2">
              <UBadge v-if="agent.authority.veto" label="Veto" color="error" variant="subtle" />
              <UBadge v-if="agent.authority.approve_budget" label="Approve Budget" color="success" variant="subtle" />
              <UBadge v-if="agent.authority.approve_quality" label="Approve Quality" color="success" variant="subtle" />
              <UBadge v-if="agent.authority.orchestrate" label="Orchestrate" color="primary" variant="subtle" />
              <UBadge v-if="agent.authority.approve_architecture" label="Approve Architecture" color="success" variant="subtle" />
              <UBadge v-if="agent.authority.block_release" label="Block Release" color="error" variant="subtle" />
            </div>
            <div v-if="agent.authority.delegates_to?.length" class="mt-3">
              <p class="text-xs text-muted mb-1">Delegates to:</p>
              <div class="flex flex-wrap gap-1">
                <UBadge v-for="d in agent.authority.delegates_to" :key="d" :label="d" variant="outline" size="xs" />
              </div>
            </div>
            <div v-if="agent.authority.escalates_to" class="mt-2">
              <p class="text-xs text-muted">Escalates to: <span class="font-mono">{{ agent.authority.escalates_to }}</span></p>
            </div>
          </UCard>
        </div>

        <!-- Expertise -->
        <div>
          <h2 class="text-lg font-semibold mb-4">Expertise</h2>
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <UCard>
              <p class="text-xs font-semibold text-muted uppercase mb-2">Domains</p>
              <div v-if="agent.expertise_domains?.length" class="flex flex-wrap gap-2">
                <UBadge v-for="d in agent.expertise_domains" :key="d" :label="d" color="primary" variant="subtle" size="sm" />
              </div>
              <p v-else class="text-sm text-muted">No domains listed.</p>
            </UCard>
            <UCard>
              <p class="text-xs font-semibold text-muted uppercase mb-2">Frameworks</p>
              <ul v-if="agent.frameworks?.length" class="space-y-1">
                <li v-for="f in agent.frameworks" :key="f" class="text-sm text-muted">{{ f }}</li>
              </ul>
              <p v-else class="text-sm text-muted">No frameworks listed.</p>
            </UCard>
          </div>
        </div>
      </div>
    </template>
  </UDashboardPanel>
</template>
