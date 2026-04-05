<script setup lang="ts">
import type { Agent } from '~/types'

const route = useRoute()
const agentId = route.params.id as string

const { fetchApi } = useApi()

const { data: agent, status, error, refresh } = await fetchApi<Agent>(`/api/agents/${agentId}`)

const tierColor = (tier: number) => {
  const colors: Record<number, string> = {
    0: 'error',
    1: 'warning',
    2: 'primary',
    3: 'neutral'
  }
  return (colors[tier] ?? 'neutral') as 'error' | 'warning' | 'primary' | 'neutral'
}

const tierLabel = (tier: number) => {
  const labels: Record<number, string> = {
    0: 'C-Suite',
    1: 'Squad Lead',
    2: 'Specialist',
    3: 'Support'
  }
  return labels[tier] ?? `Tier ${tier}`
}

const bigFiveLabels: Record<string, string> = {
  O: 'Openness',
  C: 'Conscientiousness',
  E: 'Extraversion',
  A: 'Agreeableness',
  N: 'Neuroticism'
}

const authorityItems = computed(() => {
  if (!agent.value?.authority) return []
  const auth = agent.value.authority
  return [
    { key: 'veto', label: 'Veto', active: !!auth.veto },
    { key: 'approve_budget', label: 'Approve Budget', active: !!auth.approve_budget },
    { key: 'approve_architecture', label: 'Approve Architecture', active: !!auth.approve_architecture },
    { key: 'orchestrate', label: 'Orchestrate', active: !!auth.orchestrate },
    { key: 'block_release', label: 'Block Release', active: !!auth.block_release }
  ]
})

function goBack() {
  navigateTo('/agents')
}
</script>

<template>
  <UDashboardPanel id="agent-detail">
    <template #header>
      <UDashboardNavbar :title="agent?.name ?? 'Agent Detail'">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #trailing>
          <UButton
            label="Back to Agents"
            variant="ghost"
            icon="i-lucide-arrow-left"
            @click="goBack"
            aria-label="Navigate back to agents list"
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
        <p class="text-sm text-muted">Failed to load agent details.</p>
        <UButton label="Retry" variant="outline" color="primary" icon="i-lucide-refresh-cw" @click="refresh()" />
      </div>

      <!-- Not Found -->
      <div v-else-if="!agent" class="flex flex-col items-center justify-center gap-4 py-12">
        <UIcon name="i-lucide-user-x" class="size-12 text-muted" />
        <p class="text-sm text-muted">Agent not found.</p>
        <UButton label="Back to Agents" variant="outline" icon="i-lucide-arrow-left" @click="goBack" />
      </div>

      <!-- Content -->
      <template v-else>
        <!-- Header Section -->
        <div class="mb-8">
          <div class="flex flex-wrap items-center gap-3">
            <h1 class="text-2xl font-bold text-highlighted">{{ agent.name }}</h1>
            <UBadge :label="agent.department" variant="subtle" size="sm" />
            <UBadge :label="`Tier ${agent.tier} — ${tierLabel(agent.tier)}`" :color="tierColor(agent.tier)" variant="subtle" size="sm" />
          </div>
          <p class="mt-1 text-sm text-muted">{{ agent.role }}</p>
        </div>

        <!-- Behavioral DNA -->
        <section aria-label="Behavioral DNA">
          <h2 class="text-lg font-semibold text-highlighted mb-4">Behavioral DNA</h2>
          <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <!-- DISC Card -->
            <div class="rounded-lg border border-default p-5">
              <h3 class="text-sm font-semibold text-muted uppercase tracking-wider mb-3">DISC</h3>
              <p class="text-xl font-bold text-highlighted">{{ agent.disc?.primary ?? '-' }}</p>
              <p v-if="agent.disc?.secondary" class="text-sm text-muted mt-1">
                Secondary: {{ agent.disc.secondary }}
              </p>
              <p v-if="agent.disc?.description" class="text-xs text-muted mt-2">
                {{ agent.disc.description }}
              </p>
            </div>

            <!-- Enneagram Card -->
            <div class="rounded-lg border border-default p-5">
              <h3 class="text-sm font-semibold text-muted uppercase tracking-wider mb-3">Enneagram</h3>
              <p class="text-xl font-bold text-highlighted">
                Type {{ agent.enneagram?.type ?? '-' }}
                <span v-if="agent.enneagram?.wing" class="text-base font-normal text-muted">
                  w{{ agent.enneagram.wing }}
                </span>
              </p>
              <p v-if="agent.enneagram?.label" class="text-sm text-muted mt-1">
                {{ agent.enneagram.label }}
              </p>
            </div>

            <!-- Big Five Card -->
            <div class="rounded-lg border border-default p-5">
              <h3 class="text-sm font-semibold text-muted uppercase tracking-wider mb-3">Big Five (OCEAN)</h3>
              <div class="space-y-3">
                <div v-for="(value, key) in agent.big_five" :key="key">
                  <div class="flex items-center justify-between text-xs mb-1">
                    <span class="text-muted">{{ bigFiveLabels[key] ?? key }}</span>
                    <span class="font-mono text-highlighted">{{ value }}</span>
                  </div>
                  <UProgress :value="value" :max="100" size="xs" />
                </div>
              </div>
            </div>

            <!-- MBTI Card -->
            <div class="rounded-lg border border-default p-5">
              <h3 class="text-sm font-semibold text-muted uppercase tracking-wider mb-3">MBTI</h3>
              <p class="text-4xl font-bold font-mono text-highlighted tracking-widest">
                {{ agent.mbti || '-' }}
              </p>
            </div>
          </div>
        </section>

        <!-- Authority -->
        <section v-if="agent.authority" class="mt-8" aria-label="Authority">
          <h2 class="text-lg font-semibold text-highlighted mb-4">Authority</h2>
          <div class="rounded-lg border border-default p-5">
            <div class="flex flex-wrap gap-2">
              <UBadge
                v-for="item in authorityItems"
                :key="item.key"
                :label="item.label"
                :color="item.active ? 'success' : 'neutral'"
                :variant="item.active ? 'subtle' : 'outline'"
                size="sm"
              />
            </div>
          </div>
        </section>

        <!-- Expertise & Frameworks -->
        <section class="mt-8" aria-label="Expertise and frameworks">
          <h2 class="text-lg font-semibold text-highlighted mb-4">Expertise</h2>
          <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <!-- Domains -->
            <div class="rounded-lg border border-default p-5">
              <h3 class="text-sm font-semibold text-muted uppercase tracking-wider mb-3">Domains</h3>
              <div v-if="agent.expertise_domains?.length" class="flex flex-wrap gap-2">
                <UBadge
                  v-for="domain in agent.expertise_domains"
                  :key="domain"
                  :label="domain"
                  variant="subtle"
                  color="primary"
                  size="sm"
                />
              </div>
              <p v-else class="text-sm text-muted">No domains listed.</p>
            </div>

            <!-- Frameworks -->
            <div class="rounded-lg border border-default p-5">
              <h3 class="text-sm font-semibold text-muted uppercase tracking-wider mb-3">Frameworks</h3>
              <ul v-if="agent.frameworks?.length" class="space-y-1">
                <li v-for="fw in agent.frameworks" :key="fw" class="text-sm text-muted">
                  {{ fw }}
                </li>
              </ul>
              <p v-else class="text-sm text-muted">No frameworks listed.</p>
            </div>
          </div>
        </section>

        <!-- Delegation -->
        <section v-if="agent.authority?.delegates_to?.length || agent.authority?.escalates_to?.length" class="mt-8 mb-8" aria-label="Delegation">
          <h2 class="text-lg font-semibold text-highlighted mb-4">Delegation</h2>
          <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div v-if="agent.authority?.delegates_to?.length" class="rounded-lg border border-default p-5">
              <h3 class="text-sm font-semibold text-muted uppercase tracking-wider mb-3">Delegates To</h3>
              <div class="flex flex-wrap gap-2">
                <UBadge
                  v-for="name in agent.authority.delegates_to"
                  :key="name"
                  :label="name"
                  variant="subtle"
                  size="sm"
                />
              </div>
            </div>
            <div v-if="agent.authority?.escalates_to?.length" class="rounded-lg border border-default p-5">
              <h3 class="text-sm font-semibold text-muted uppercase tracking-wider mb-3">Escalates To</h3>
              <div class="flex flex-wrap gap-2">
                <UBadge
                  v-for="name in agent.authority.escalates_to"
                  :key="name"
                  :label="name"
                  variant="subtle"
                  color="warning"
                  size="sm"
                />
              </div>
            </div>
          </div>
        </section>
      </template>
    </template>
  </UDashboardPanel>
</template>
